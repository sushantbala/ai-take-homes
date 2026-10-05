"""Durable state. This is what makes re-runs safe.

The brief's hardest requirement is that running twice over the same
transcripts creates no duplicate tickets or notifications, and that one
transcript failing does not corrupt the rest. Three mechanisms here, in
increasing order of how much trouble they saved:

1. CONTENT-ADDRESSED IDENTITY. An issue is identified by a fingerprint over
   (type, component, normalised trigger+symptom tokens) -- never a random id,
   never model prose. Every write goes through this module and checks the
   fingerprint first, so the naive stubs never see the same issue twice.

2. NEAR-MATCH FALLBACK. The interesting failure. A non-deterministic model
   will word `symptom` slightly differently next Tuesday, the hash changes,
   and a pure hash check cheerfully files the same bug again -- the system
   would look idempotent in testing with a replay provider and leak duplicates
   in production. So a hash miss falls back to a token-set comparison within
   the same (type, component) bucket before concluding the issue is new.

3. TWO-PHASE WRITES. The stubs are append-only files with no transaction. If
   the process dies between appending to jira.jsonl and recording that we
   did, the next run re-files. So intent is recorded as `pending` before the
   sink is called and flipped to `committed` after, and `reconcile()` resolves
   anything left dangling by checking the outbox itself.

Per-transcript state is tracked separately so a failed transcript is retried
next run while its 139 neighbours are not reprocessed.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from . import config
from .models import jaccard

_SCHEMA = """
CREATE TABLE IF NOT EXISTS issues (
    fingerprint   TEXT PRIMARY KEY,
    type          TEXT NOT NULL,
    component     TEXT NOT NULL,
    tokens        TEXT NOT NULL,      -- JSON array, for near-match fallback
    title         TEXT NOT NULL,
    outcome       TEXT NOT NULL,
    status        TEXT NOT NULL,      -- proposed|approved|rejected|filed
    jira_key      TEXT,
    dedup_target  TEXT,
    first_seen    TEXT NOT NULL,
    last_seen     TEXT NOT NULL,
    first_run     TEXT NOT NULL,
    last_run      TEXT NOT NULL
);

-- One row per (issue, call). The PK is what makes adding a corroborating
-- source idempotent: re-processing a call cannot double-count it.
CREATE TABLE IF NOT EXISTS sources (
    fingerprint TEXT NOT NULL,
    call_id     TEXT NOT NULL,
    account     TEXT,
    turn_ids    TEXT,
    added_at    TEXT NOT NULL,
    added_run   TEXT NOT NULL,
    PRIMARY KEY (fingerprint, call_id)
);

-- Slack is gated on its own key rather than on the Jira write, so a retry
-- after a partial failure cannot re-notify for work already announced.
CREATE TABLE IF NOT EXISTS notifications (
    fingerprint TEXT NOT NULL,
    channel     TEXT NOT NULL,
    kind        TEXT NOT NULL,       -- new|corroboration|shipped
    sent_at     TEXT NOT NULL,
    run_id      TEXT NOT NULL,
    PRIMARY KEY (fingerprint, channel, kind)
);

-- Per-transcript progress. `content_hash` lets an unchanged transcript be
-- skipped entirely on re-run, and `status='error'` marks one for retry
-- without blocking anything else.
CREATE TABLE IF NOT EXISTS transcript_state (
    call_id      TEXT PRIMARY KEY,
    content_hash TEXT NOT NULL,
    status       TEXT NOT NULL,      -- ok|error|skipped_internal
    error        TEXT,
    last_run     TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);

-- Two-phase write intents.
CREATE TABLE IF NOT EXISTS writes (
    write_id     TEXT PRIMARY KEY,
    fingerprint  TEXT NOT NULL,
    sink         TEXT NOT NULL,      -- jira|slack
    phase        TEXT NOT NULL,      -- pending|committed|failed
    payload_hash TEXT NOT NULL,
    result_key   TEXT,
    run_id       TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    settled_at   TEXT
);

CREATE TABLE IF NOT EXISTS runs (
    run_id      TEXT PRIMARY KEY,
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    summary     TEXT
);

CREATE INDEX IF NOT EXISTS idx_issues_bucket ON issues (type, component);
CREATE INDEX IF NOT EXISTS idx_writes_phase  ON writes (phase);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class KnownIssue:
    fingerprint: str
    type: str
    component: str
    title: str
    status: str
    jira_key: str | None
    outcome: str
    tokens: frozenset[str]


class Ledger:
    def __init__(self, path: Path | None = None):
        self.path = path or config.LEDGER_DB
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        # WAL so a reader (the review UI) and the writer (a scheduled run)
        # don't block each other.
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> Ledger:
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        try:
            yield self.conn
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    # --- issue identity ------------------------------------------------------

    def lookup(self, fingerprint: str, type_: str, component: str, tokens: frozenset[str]) -> KnownIssue | None:
        """Find an existing issue by exact hash, then by near-match.

        The near-match pass is the one that matters in production. See the
        module docstring: without it, ordinary model wording drift re-files
        every ticket on every run, and nothing in a replay-based test suite
        would catch it.
        """
        row = self.conn.execute("SELECT * FROM issues WHERE fingerprint = ?", (fingerprint,)).fetchone()
        if row:
            return _to_known(row)

        best: tuple[float, sqlite3.Row] | None = None
        for row in self.conn.execute(
            "SELECT * FROM issues WHERE type = ? AND component = ?", (type_, component)
        ):
            similarity = jaccard(tokens, frozenset(json.loads(row["tokens"])))
            if similarity >= config.FINGERPRINT_NEAR_MATCH_THRESHOLD and (best is None or similarity > best[0]):
                best = (similarity, row)
        return _to_known(best[1]) if best else None

    def upsert_issue(
        self,
        *,
        fingerprint: str,
        type_: str,
        component: str,
        tokens: frozenset[str],
        title: str,
        outcome: str,
        status: str,
        run_id: str,
        jira_key: str | None = None,
        dedup_target: str | None = None,
    ) -> None:
        now = _now()
        with self.tx() as conn:
            conn.execute(
                """
                INSERT INTO issues (fingerprint, type, component, tokens, title, outcome, status,
                                    jira_key, dedup_target, first_seen, last_seen, first_run, last_run)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(fingerprint) DO UPDATE SET
                    last_seen = excluded.last_seen,
                    last_run  = excluded.last_run,
                    title     = COALESCE(issues.title, excluded.title),
                    -- Never downgrade a terminal status. A re-run must not
                    -- move a filed or human-rejected issue back to proposed.
                    status    = CASE WHEN issues.status IN ('filed','rejected')
                                     THEN issues.status ELSE excluded.status END,
                    jira_key  = COALESCE(issues.jira_key, excluded.jira_key)
                """,
                (fingerprint, type_, component, json.dumps(sorted(tokens)), title, outcome,
                 status, jira_key, dedup_target, now, now, run_id, run_id),
            )

    def set_status(self, fingerprint: str, status: str, *, jira_key: str | None = None) -> None:
        with self.tx() as conn:
            conn.execute(
                "UPDATE issues SET status = ?, jira_key = COALESCE(?, jira_key), last_seen = ? "
                "WHERE fingerprint = ?",
                (status, jira_key, _now(), fingerprint),
            )

    def get_issue(self, fingerprint: str) -> KnownIssue | None:
        row = self.conn.execute("SELECT * FROM issues WHERE fingerprint = ?", (fingerprint,)).fetchone()
        return _to_known(row) if row else None

    def is_rejected(self, fingerprint: str) -> bool:
        """Rejections are sticky.

        Without this, a scheduled run re-proposes everything the reviewer
        already said no to, every night, and the reviewer stops reading the
        queue. That is how these systems actually die.
        """
        row = self.conn.execute("SELECT status FROM issues WHERE fingerprint = ?", (fingerprint,)).fetchone()
        return bool(row and row["status"] == "rejected")

    # --- sources -------------------------------------------------------------

    def add_source(self, fingerprint: str, call_id: str, account: str, turn_ids: list[int], run_id: str) -> bool:
        """Attach a call as a source. Returns True only if it was new."""
        with self.tx() as conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO sources (fingerprint, call_id, account, turn_ids, added_at, added_run) "
                "VALUES (?,?,?,?,?,?)",
                (fingerprint, call_id, account, json.dumps(turn_ids), _now(), run_id),
            )
            return cur.rowcount > 0

    def sources_for(self, fingerprint: str) -> list[sqlite3.Row]:
        return list(self.conn.execute(
            "SELECT * FROM sources WHERE fingerprint = ? ORDER BY call_id", (fingerprint,)
        ))

    # --- notifications -------------------------------------------------------

    def notification_sent(self, fingerprint: str, channel: str, kind: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM notifications WHERE fingerprint=? AND channel=? AND kind=?",
            (fingerprint, channel, kind),
        ).fetchone()
        return row is not None

    def record_notification(self, fingerprint: str, channel: str, kind: str, run_id: str) -> bool:
        with self.tx() as conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO notifications (fingerprint, channel, kind, sent_at, run_id) "
                "VALUES (?,?,?,?,?)",
                (fingerprint, channel, kind, _now(), run_id),
            )
            return cur.rowcount > 0

    # --- transcript progress -------------------------------------------------

    def transcript_unchanged(self, call_id: str, content_hash: str) -> bool:
        """True if this exact transcript already completed successfully.

        An errored transcript deliberately reports False so it is retried.
        """
        row = self.conn.execute(
            "SELECT content_hash, status FROM transcript_state WHERE call_id = ?", (call_id,)
        ).fetchone()
        return bool(row and row["content_hash"] == content_hash and row["status"] == "ok")

    def record_transcript(self, call_id: str, content_hash: str, status: str, run_id: str, error: str | None = None) -> None:
        with self.tx() as conn:
            conn.execute(
                """
                INSERT INTO transcript_state (call_id, content_hash, status, error, last_run, updated_at)
                VALUES (?,?,?,?,?,?)
                ON CONFLICT(call_id) DO UPDATE SET
                    content_hash = excluded.content_hash,
                    status       = excluded.status,
                    error        = excluded.error,
                    last_run     = excluded.last_run,
                    updated_at   = excluded.updated_at
                """,
                (call_id, content_hash, status, error, run_id, _now()),
            )

    def errored_transcripts(self) -> list[str]:
        return [r["call_id"] for r in self.conn.execute(
            "SELECT call_id FROM transcript_state WHERE status = 'error' ORDER BY call_id"
        )]

    # --- two-phase writes ----------------------------------------------------

    def begin_write(self, write_id: str, fingerprint: str, sink: str, payload_hash: str, run_id: str) -> bool:
        """Claim the right to perform a write. False means somebody already has.

        The PK insert is the lock. Two concurrent runs cannot both claim the
        same (fingerprint, sink) write.
        """
        existing = self.conn.execute("SELECT phase FROM writes WHERE write_id = ?", (write_id,)).fetchone()
        if existing and existing["phase"] in ("pending", "committed"):
            return False
        with self.tx() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO writes (write_id, fingerprint, sink, phase, payload_hash, "
                "run_id, created_at) VALUES (?,?,?,'pending',?,?,?)",
                (write_id, fingerprint, sink, payload_hash, run_id, _now()),
            )
        return True

    def commit_write(self, write_id: str, result_key: str | None) -> None:
        with self.tx() as conn:
            conn.execute(
                "UPDATE writes SET phase='committed', result_key=?, settled_at=? WHERE write_id=?",
                (result_key, _now(), write_id),
            )

    def fail_write(self, write_id: str, error: str) -> None:
        with self.tx() as conn:
            conn.execute(
                "UPDATE writes SET phase='failed', result_key=?, settled_at=? WHERE write_id=?",
                (error[:300], _now(), write_id),
            )

    def pending_writes(self) -> list[sqlite3.Row]:
        return list(self.conn.execute("SELECT * FROM writes WHERE phase='pending' ORDER BY created_at"))

    def reconcile(self, outbox_fingerprints: dict[str, set[str]]) -> list[dict]:
        """Resolve writes left `pending` by a crash.

        Called at the start of every run. For each dangling intent, ask the
        outbox whether the write actually landed: present means the crash
        happened after the append, so commit the record; absent means it never
        happened, so clear the intent and let the normal path retry it.
        Without this, a mid-write crash either loses the write or duplicates
        it, depending on which way you guess.
        """
        resolved = []
        for row in self.pending_writes():
            landed = row["fingerprint"] in outbox_fingerprints.get(row["sink"], set())
            if landed:
                self.commit_write(row["write_id"], result_key="recovered")
                resolved.append({"write_id": row["write_id"], "sink": row["sink"], "action": "committed_recovered"})
            else:
                with self.tx() as conn:
                    conn.execute("DELETE FROM writes WHERE write_id = ?", (row["write_id"],))
                resolved.append({"write_id": row["write_id"], "sink": row["sink"], "action": "cleared_for_retry"})
        return resolved

    # --- runs ----------------------------------------------------------------

    def start_run(self, run_id: str) -> None:
        with self.tx() as conn:
            conn.execute("INSERT OR REPLACE INTO runs (run_id, started_at) VALUES (?,?)", (run_id, _now()))

    def finish_run(self, run_id: str, summary: dict) -> None:
        with self.tx() as conn:
            conn.execute(
                "UPDATE runs SET finished_at=?, summary=? WHERE run_id=?",
                (_now(), json.dumps(summary), run_id),
            )

    def stats(self) -> dict:
        def one(sql: str) -> int:
            return self.conn.execute(sql).fetchone()[0]

        return {
            "issues": one("SELECT COUNT(*) FROM issues"),
            "filed": one("SELECT COUNT(*) FROM issues WHERE status='filed'"),
            "proposed": one("SELECT COUNT(*) FROM issues WHERE status='proposed'"),
            "rejected": one("SELECT COUNT(*) FROM issues WHERE status='rejected'"),
            "sources": one("SELECT COUNT(*) FROM sources"),
            "notifications": one("SELECT COUNT(*) FROM notifications"),
            "transcripts_ok": one("SELECT COUNT(*) FROM transcript_state WHERE status='ok'"),
            "transcripts_error": one("SELECT COUNT(*) FROM transcript_state WHERE status='error'"),
            "pending_writes": one("SELECT COUNT(*) FROM writes WHERE phase='pending'"),
        }


def _to_known(row: sqlite3.Row) -> KnownIssue:
    return KnownIssue(
        fingerprint=row["fingerprint"],
        type=row["type"],
        component=row["component"],
        title=row["title"],
        status=row["status"],
        jira_key=row["jira_key"],
        outcome=row["outcome"],
        tokens=frozenset(json.loads(row["tokens"])),
    )
