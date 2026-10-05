"""Structured event log and run health.

The requirement this module exists for: if the pipeline ran unattended and
silently started mis-filing, or silently stopped, someone should be able to
tell from the output alone.

Two mechanisms:

  * An append-only JSONL event per decision, carrying `run_id`, `call_id`,
    `stage`, a closed-enum `reason`, and the `fingerprint`. Because reasons are
    a closed enum, the drop distribution is aggregatable -- "dropped_hearsay
    fell to zero this week" is a visible, queryable signal that the extractor
    changed behaviour even though nothing raised.

  * A run summary checked against health bands. The key judgement encoded here
    is that silence is not success: a run that files zero tickets across 140
    transcripts is as alarming as one that files sixty, and both trip.

Every event also carries `prompt_version` and `model`, so a behaviour change
is attributable to a specific prompt revision rather than guessed at.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from . import config
from .models import to_jsonable


def new_run_id() -> str:
    return f"run-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:6]}"


@dataclass
class RunLogger:
    """Append-only JSONL writer plus in-memory counters for the run summary."""

    run_id: str
    log_path: Path
    counters: Counter = field(default_factory=Counter)
    drop_reasons: Counter = field(default_factory=Counter)
    errors: list[dict[str, Any]] = field(default_factory=list)
    _fh: Any = None
    echo: bool = False

    @classmethod
    def start(cls, run_id: str, *, echo: bool = False) -> RunLogger:
        config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
        path = config.LOGS_DIR / f"{run_id}.jsonl"
        logger = cls(run_id=run_id, log_path=path, echo=echo)
        logger._fh = path.open("a", encoding="utf-8")
        logger.event("run", "run_started", run_id=run_id)
        return logger

    def event(self, stage: str, reason: str, **fields: Any) -> None:
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id,
            "stage": stage,
            "reason": str(reason),
            **{k: to_jsonable(v) for k, v in fields.items()},
        }
        line = json.dumps(record, ensure_ascii=False)
        self._fh.write(line + "\n")
        # Flushed per event on purpose. If the process is killed mid-run, the
        # log of what it had already decided must survive -- that log is how a
        # partial run gets reconciled on the next pass.
        self._fh.flush()
        self.counters[f"{stage}.{reason}"] += 1
        if self.echo:
            print(f"  [{stage}] {reason} " + " ".join(f"{k}={v}" for k, v in fields.items() if k != "detail"))

    def dropped(self, call_id: str, reason: str, **fields: Any) -> None:
        self.drop_reasons[str(reason)] += 1
        self.event("gate", f"dropped_{reason}", call_id=call_id, **fields)

    def error(self, call_id: str, exc: BaseException, stage: str) -> None:
        """Record a per-transcript failure without aborting the run.

        The `failed_stage` key is deliberately not called `stage`: splatting a
        dict containing `stage` into `event(stage, reason, **fields)` collides
        on that parameter and raises TypeError. That turned the one code path
        whose entire job is to contain a failure into the path that crashed
        the whole run, and it was invisible until a transcript actually failed.
        """
        entry = {
            "call_id": call_id,
            "failed_stage": stage,
            "error_type": type(exc).__name__,
            "error": str(exc)[:500],
        }
        self.errors.append(entry)
        self.event("error", "transcript_failed", **entry)

    @contextmanager
    def timed(self, stage: str, **fields: Any) -> Iterator[None]:
        start = time.perf_counter()
        try:
            yield
        finally:
            self.event(stage, "timing", duration_ms=round((time.perf_counter() - start) * 1000, 1), **fields)

    def close(self, summary: dict[str, Any]) -> None:
        self.event("run", "run_finished", **summary)
        self._fh.close()


# --- run summary and health --------------------------------------------------


@dataclass
class RunSummary:
    run_id: str
    transcripts_seen: int = 0
    transcripts_processed: int = 0
    transcripts_skipped_internal: int = 0
    transcripts_errored: int = 0
    transcripts_unchanged: int = 0
    candidates_extracted: int = 0
    candidates_dropped: int = 0
    actions_file_new: int = 0
    actions_corroborate: int = 0
    actions_already_shipped: int = 0
    actions_suppressed_idempotent: int = 0
    drop_reasons: dict[str, int] = field(default_factory=dict)
    health: list[str] = field(default_factory=list)

    @property
    def error_rate(self) -> float:
        return self.transcripts_errored / max(self.transcripts_seen, 1)

    @property
    def candidates_per_call(self) -> float:
        return self.candidates_extracted / max(self.transcripts_processed, 1)

    @property
    def file_rate(self) -> float:
        return self.actions_file_new / max(self.transcripts_processed, 1)

    def check_health(self) -> list[str]:
        """Return alert strings. Empty list means the run looks normal.

        These bands are what distinguishes "ran and found nothing" from
        "stopped working and nobody noticed". Both look like an empty outbox.
        """
        alerts: list[str] = []

        if self.transcripts_seen == 0:
            alerts.append("CRITICAL: no transcripts found at all -- source path may be wrong")
            self.health = alerts
            return alerts

        if self.error_rate > config.HEALTH_MAX_ERROR_RATE:
            alerts.append(
                f"HIGH: error rate {self.error_rate:.1%} exceeds "
                f"{config.HEALTH_MAX_ERROR_RATE:.1%} ({self.transcripts_errored} transcripts failed)"
            )

        if self.transcripts_processed == 0 and self.transcripts_unchanged == 0:
            alerts.append("CRITICAL: zero transcripts processed -- the pipeline did nothing")
        elif self.transcripts_processed > 0:
            cpc = self.candidates_per_call
            if cpc < config.HEALTH_MIN_CANDIDATES_PER_CALL:
                # The silent-stop signal. Extraction returning nothing looks
                # identical to a clean month unless you alert on it.
                alerts.append(
                    f"HIGH: {cpc:.2f} candidates/call is below the floor of "
                    f"{config.HEALTH_MIN_CANDIDATES_PER_CALL} -- extraction may have silently stopped"
                )
            elif cpc > config.HEALTH_MAX_CANDIDATES_PER_CALL:
                alerts.append(
                    f"MEDIUM: {cpc:.2f} candidates/call exceeds the ceiling of "
                    f"{config.HEALTH_MAX_CANDIDATES_PER_CALL} -- extraction may be over-firing"
                )

            if self.file_rate > config.HEALTH_MAX_FILE_RATE:
                # The silent-mis-filing signal.
                alerts.append(
                    f"HIGH: {self.file_rate:.1%} of calls produced a new ticket, above "
                    f"{config.HEALTH_MAX_FILE_RATE:.1%} -- gates may have stopped filtering"
                )

        if self.candidates_extracted and self.candidates_dropped == self.candidates_extracted:
            alerts.append("MEDIUM: every candidate was dropped -- check the gate rules")

        self.health = alerts
        return alerts

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "transcripts_seen": self.transcripts_seen,
            "transcripts_processed": self.transcripts_processed,
            "transcripts_skipped_internal": self.transcripts_skipped_internal,
            "transcripts_unchanged": self.transcripts_unchanged,
            "transcripts_errored": self.transcripts_errored,
            "error_rate": round(self.error_rate, 4),
            "candidates_extracted": self.candidates_extracted,
            "candidates_dropped": self.candidates_dropped,
            "candidates_per_call": round(self.candidates_per_call, 3),
            "actions_file_new": self.actions_file_new,
            "actions_corroborate": self.actions_corroborate,
            "actions_already_shipped": self.actions_already_shipped,
            "actions_suppressed_idempotent": self.actions_suppressed_idempotent,
            "file_rate": round(self.file_rate, 4),
            "drop_reasons": dict(sorted(self.drop_reasons.items())),
            "health_alerts": self.health,
        }

    def render(self) -> str:
        d = self.as_dict()
        lines = [
            f"run            {d['run_id']}",
            f"transcripts    {d['transcripts_processed']} processed, "
            f"{d['transcripts_skipped_internal']} internal-only, "
            f"{d['transcripts_unchanged']} unchanged, {d['transcripts_errored']} errored",
            f"candidates     {d['candidates_extracted']} extracted, {d['candidates_dropped']} dropped "
            f"({d['candidates_per_call']}/call)",
            f"actions        {d['actions_file_new']} new, {d['actions_corroborate']} corroborate, "
            f"{d['actions_already_shipped']} already-shipped, "
            f"{d['actions_suppressed_idempotent']} suppressed as duplicate",
        ]
        if d["drop_reasons"]:
            lines.append("drops by reason")
            width = max(len(k) for k in d["drop_reasons"])
            for reason, n in sorted(d["drop_reasons"].items(), key=lambda kv: (-kv[1], kv[0])):
                lines.append(f"    {reason:<{width}}  {n}")
        if d["health_alerts"]:
            lines.append("HEALTH ALERTS")
            lines += [f"    {a}" for a in d["health_alerts"]]
        else:
            lines.append("health         all bands nominal")
        return "\n".join(lines)


def write_summary(summary: RunSummary) -> Path:
    config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    path = config.LOGS_DIR / f"{summary.run_id}.summary.json"
    path.write_text(json.dumps(summary.as_dict(), indent=2), encoding="utf-8")
    # A stable filename so a scheduler or dashboard can always read the latest
    # run without globbing for the newest timestamp.
    latest = config.LOGS_DIR / "latest.summary.json"
    tmp = latest.with_suffix(".tmp")
    tmp.write_text(json.dumps(summary.as_dict(), indent=2), encoding="utf-8")
    os.replace(tmp, latest)
    return path
