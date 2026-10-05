"""Orchestration: transcripts in, review queue out. Nothing is written here.

`run()` is deliberately split from `apply()`. `run()` is the expensive,
model-touching, failure-prone half and it produces only a proposal. `apply()`
is the cheap, deterministic half that performs writes, and it refuses to act
on anything a human has not explicitly approved. A bug in the first half
therefore cannot file a ticket.

Partial-failure handling is per transcript: each one is processed inside its
own try/except and its own ledger row, so a transcript that fails is recorded
as `error`, retried on the next run, and costs its 139 neighbours nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import assemble, config, obs
from .config import DropReason, Outcome
from .dedup import cluster_candidates, dedup_against_existing, load_existing_issues
from .extract import MalformedCandidate, extract_candidates
from .gates import apply_gates
from .ingest import TranscriptParseError, load_transcripts, parse_transcript
from .ledger import Ledger
from .llm.provider import LLMError, LLMProvider, ResponseNotRecorded
from .models import Candidate, ProposedAction, Transcript
from .review import Decisions, ReviewQueue
from .sinks import NOTIFICATION_KIND, GatedSink, read_outbox_fingerprints


@dataclass
class RunResult:
    run_id: str
    summary: obs.RunSummary
    actions: list[ProposedAction] = field(default_factory=list)
    queue_path: Path | None = None
    digest_path: Path | None = None


def run(
    provider: LLMProvider,
    ledger: Ledger,
    *,
    only: list[str] | None = None,
    force: bool = False,
    echo: bool = False,
    run_id: str | None = None,
) -> RunResult:
    """Propose actions for every transcript. Writes nothing to any sink."""
    run_id = run_id or obs.new_run_id()
    log = obs.RunLogger.start(run_id, echo=echo)
    ledger.start_run(run_id)
    summary = obs.RunSummary(run_id=run_id)

    # Resolve anything a previous crash left half-written before doing new
    # work, so a dangling intent cannot block this run's writes forever.
    for resolution in ledger.reconcile(read_outbox_fingerprints()):
        log.event("reconcile", resolution["action"], **resolution)

    paths = load_transcripts(config.TRANSCRIPTS_DIR, only=only)
    summary.transcripts_seen = len(paths)
    existing_issues = load_existing_issues()

    transcripts: dict[str, Transcript] = {}
    survivors: list[Candidate] = []

    for path in paths:
        call_id = path.stem
        try:
            candidates, transcript = _process_transcript(
                path, provider, ledger, log, summary, force=force
            )
        except Exception as exc:
            # The partial-failure boundary. One bad transcript is recorded and
            # skipped; the run continues and exits non-zero only if the error
            # rate breaches its band.
            summary.transcripts_errored += 1
            log.error(call_id, exc, stage="process_transcript")
            ledger.record_transcript(call_id, "", "error", run_id, error=f"{type(exc).__name__}: {exc}")
            continue

        if transcript is not None:
            transcripts[call_id] = transcript
        survivors.extend(candidates)

    # --- de-duplicate against tracked issues --------------------------------

    to_cluster: list[Candidate] = []
    resolved: list[tuple[Candidate, Outcome, str | None, str]] = []

    for candidate in survivors:
        decision = dedup_against_existing(candidate, existing_issues, provider)
        candidate.near_misses = decision.near_misses
        log.event(
            "dedup",
            str(decision.outcome),
            call_id=candidate.call_id,
            title=candidate.title,
            target=decision.target,
            rationale=decision.rationale,
            near_misses=[nm.key for nm in decision.near_misses],
            model_calls=decision.model_calls,
        )
        if decision.outcome is Outcome.FILE_NEW:
            to_cluster.append(candidate)
        else:
            resolved.append((candidate, decision.outcome, decision.target, decision.rationale))

    # --- cluster what's left across calls ------------------------------------

    clusters, cluster_model_calls = cluster_candidates(to_cluster, provider)
    log.event("cluster", "clustered", clusters=len(clusters),
              candidates=len(to_cluster), model_calls=cluster_model_calls)

    actions: list[ProposedAction] = []

    for cluster_id, members in sorted(clusters.items()):
        if len(members) > 1:
            log.event("cluster", "merged", cluster_id=cluster_id,
                      calls=[m.call_id for m in members], title=members[0].title)
        actions.append(assemble.build_action(members, transcripts, Outcome.FILE_NEW))

    for candidate, outcome, target, rationale in resolved:
        actions.append(
            assemble.build_action(
                [candidate], transcripts, outcome,
                dedup_target=target, dedup_rationale=rationale,
            )
        )

    # --- suppress anything already handled -----------------------------------

    proposals: list[ProposedAction] = []
    for action in actions:
        if _suppress(action, ledger, log, summary):
            continue
        _record_proposal(action, ledger, run_id)
        proposals.append(action)
        if action.outcome is Outcome.FILE_NEW:
            summary.actions_file_new += 1
        elif action.outcome is Outcome.CORROBORATE:
            summary.actions_corroborate += 1
        else:
            summary.actions_already_shipped += 1

    queue = ReviewQueue.build(run_id, proposals)
    queue_path, digest_path = queue.write()

    summary.drop_reasons = dict(log.drop_reasons)
    summary.check_health()
    obs.write_summary(summary)
    ledger.finish_run(run_id, summary.as_dict())
    log.close(summary.as_dict())

    return RunResult(
        run_id=run_id, summary=summary, actions=proposals,
        queue_path=queue_path, digest_path=digest_path,
    )


def _process_transcript(
    path: Path,
    provider: LLMProvider,
    ledger: Ledger,
    log: obs.RunLogger,
    summary: obs.RunSummary,
    *,
    force: bool,
) -> tuple[list[Candidate], Transcript | None]:
    """Parse, screen, extract and gate one call."""
    call_id = path.stem
    transcript = parse_transcript(path)

    # Skip unchanged transcripts. The content hash is the cheap, correct
    # version of "have we already done this one" -- editing a transcript
    # re-processes it, re-running does not.
    if not force and ledger.transcript_unchanged(call_id, transcript.content_hash):
        summary.transcripts_unchanged += 1
        log.event("ingest", "skipped_unchanged", call_id=call_id, content_hash=transcript.content_hash)
        return [], transcript

    # Requirement 1, settled without a model call: no external participant
    # means no customer to raise a product issue.
    if not transcript.has_external:
        summary.transcripts_skipped_internal += 1
        log.dropped(call_id, DropReason.INTERNAL_ONLY_CALL,
                    detail="no [EXTERNAL] participant on the call")
        ledger.record_transcript(call_id, transcript.content_hash, "skipped_internal", log.run_id)
        return [], transcript

    if transcript.injection_turns:
        log.event("ingest", "injection_detected", call_id=call_id,
                  turns=sorted(transcript.injection_turns))
    if transcript.suppression_turns:
        log.event("ingest", "suppression_detected", call_id=call_id,
                  turns=sorted(transcript.suppression_turns))

    try:
        candidates, malformed, meta = extract_candidates(transcript, provider)
    except ResponseNotRecorded as exc:
        # Expected for holdout calls with no fixture. Distinct from a real
        # failure so it does not pollute the error rate.
        summary.transcripts_unchanged += 0
        log.event("extract", "no_fixture", call_id=call_id, detail=str(exc)[:160])
        ledger.record_transcript(call_id, transcript.content_hash, "error", log.run_id,
                                 error="no recorded model response")
        return [], transcript
    except (LLMError, MalformedCandidate) as exc:
        raise

    summary.transcripts_processed += 1
    summary.candidates_extracted += len(candidates)
    log.event("extract", "extracted", call_id=call_id, count=len(candidates),
              malformed=len(malformed), model=meta["model"], source=meta["source"],
              input_tokens=meta["input_tokens"], output_tokens=meta["output_tokens"])

    for problem in malformed:
        summary.candidates_dropped += 1
        log.dropped(call_id, DropReason.SCHEMA_INVALID, detail=problem)

    kept: list[Candidate] = []
    for candidate in candidates:
        result = apply_gates(candidate, transcript)
        if not result.passed:
            summary.candidates_dropped += 1
            candidate.drop_reason = result.reason
            candidate.drop_detail = result.detail
            log.dropped(call_id, result.reason, title=candidate.title, detail=result.detail)
            continue
        candidate.fingerprint = candidate.compute_fingerprint()
        log.event("gate", "passed", call_id=call_id, title=candidate.title,
                  fingerprint=candidate.fingerprint, flags=list(result.flags),
                  evidence_turns=candidate.evidence_turns)
        kept.append(candidate)

    ledger.record_transcript(call_id, transcript.content_hash, "ok", log.run_id)
    return kept, transcript


def _suppress(action: ProposedAction, ledger: Ledger, log: obs.RunLogger, summary: obs.RunSummary) -> bool:
    """True if this action should not reach the reviewer at all.

    Two cases, both about not wasting human attention: work that is already
    done, and work a human already declined. The second is the one that keeps
    a scheduled run usable over months.
    """
    if ledger.is_rejected(action.fingerprint):
        summary.actions_suppressed_idempotent += 1
        log.event("idempotency", "suppressed_previously_rejected",
                  fingerprint=action.fingerprint, title=action.title)
        return True

    known = ledger.lookup(
        action.fingerprint, action.type, action.component,
        frozenset(_tokens(action)),
    )
    if known is None:
        return False

    if known.status == "filed":
        # Already tracked by us. A new call about it is corroboration, which
        # is recorded on the existing issue rather than re-proposed.
        is_new_source = any(
            ledger.add_source(known.fingerprint, s.call_id, s.account,
                              [sn.turn_idx for sn in s.snippets], log.run_id)
            for s in action.sources
        )
        summary.actions_suppressed_idempotent += 1
        log.event("idempotency", "suppressed_already_filed",
                  fingerprint=action.fingerprint, matched=known.fingerprint,
                  jira_key=known.jira_key, new_source=is_new_source,
                  calls=[s.call_id for s in action.sources])
        return True

    if known.fingerprint != action.fingerprint:
        # Near-match hit: same issue, different wording this run. Reuse the
        # established identity so the reviewer and the ledger agree.
        log.event("idempotency", "near_match_reused_fingerprint",
                  proposed=action.fingerprint, reused=known.fingerprint, title=action.title)
        action.fingerprint = known.fingerprint

    return False


def _tokens(action: ProposedAction) -> frozenset[str]:
    from .models import normalize_tokens

    return normalize_tokens(action.title)


def _record_proposal(action: ProposedAction, ledger: Ledger, run_id: str) -> None:
    ledger.upsert_issue(
        fingerprint=action.fingerprint,
        type_=action.type,
        component=action.component,
        tokens=_tokens(action),
        title=action.title,
        outcome=str(action.outcome),
        status="proposed",
        run_id=run_id,
        dedup_target=action.dedup_target,
    )
    for source in action.sources:
        ledger.add_source(
            action.fingerprint, source.call_id, source.account,
            [s.turn_idx for s in source.snippets], run_id,
        )


# --- apply -------------------------------------------------------------------


def apply_approved(
    ledger: Ledger,
    *,
    dry_run: bool = False,
    run_id: str | None = None,
    queue_path: Path | None = None,
) -> dict:
    """Write the approved actions. The only path that touches a sink."""
    run_id = run_id or obs.new_run_id()
    log = obs.RunLogger.start(run_id)
    decisions = Decisions.load()
    sink = GatedSink(ledger, run_id, log, dry_run=dry_run)

    path = queue_path or (config.REVIEW_DIR / "latest-queue.json")
    if not path.exists():
        log.event("apply", "no_queue", path=str(path))
        log.close({})
        return {"filed": 0, "notified": 0, "skipped": 0, "rejected": 0, "pending": 0}

    import json

    queue = json.loads(path.read_text(encoding="utf-8"))
    stats = {"filed": 0, "notified": 0, "skipped": 0, "rejected": 0, "pending": 0}

    for raw in queue["actions"]:
        action = _action_from_json(raw)
        verdict = decisions.verdict(action.fingerprint)

        if verdict is None:
            # No decision recorded. The default is to do nothing, which is the
            # whole point of the gate.
            stats["pending"] += 1
            log.event("apply", "skipped_no_decision", fingerprint=action.fingerprint, title=action.title)
            continue

        if verdict == "reject":
            # Persisted so it is never proposed again.
            ledger.set_status(action.fingerprint, "rejected")
            stats["rejected"] += 1
            log.event("apply", "rejected_by_reviewer", fingerprint=action.fingerprint,
                      reviewer=decisions.reviewer(action.fingerprint), title=action.title)
            continue

        jira_key = action.dedup_target
        if action.outcome is Outcome.FILE_NEW:
            result = sink.file_issue(action, assemble.jira_payload(action), approved=True)
            jira_key = result.jira_key
            stats["filed" if result.performed else "skipped"] += 1
        else:
            # Corroboration and already-shipped write no ticket. The source
            # attachment is the ledger row; the human gets the Slack note.
            for source in action.sources:
                ledger.add_source(action.fingerprint, source.call_id, source.account,
                                  [s.turn_idx for s in source.snippets], run_id)
            ledger.set_status(action.fingerprint, "filed")

        notified = sink.notify(
            action,
            assemble.slack_payload(action, jira_key),
            NOTIFICATION_KIND[action.outcome],
            approved=True,
        )
        if notified.performed:
            stats["notified"] += 1

    log.event("apply", "finished", **stats)
    log.close(stats)
    return stats


def _action_from_json(raw: dict) -> ProposedAction:
    from .models import NearMiss, Snippet, Source

    return ProposedAction(
        fingerprint=raw["fingerprint"],
        outcome=Outcome(raw["outcome"]),
        type=raw["type"],
        title=raw["title"],
        component=raw["component"],
        priority=raw["priority"],
        severity=raw["severity"],
        priority_rationale=raw["priority_rationale"],
        body=raw["body"],
        sources=[
            Source(
                call_id=s["call_id"], account=s["account"], date=s["date"],
                reporter=s["reporter"], transcript_path=s["transcript_path"],
                snippets=tuple(Snippet(**sn) for sn in s["snippets"]),
            )
            for s in raw["sources"]
        ],
        dedup_target=raw.get("dedup_target"),
        dedup_rationale=raw.get("dedup_rationale", ""),
        near_misses=[NearMiss(**nm) for nm in raw.get("near_misses", [])],
        flags=raw.get("flags", []),
    )
