"""The only code path allowed to call the stubs.

Funnelling every write through one place is what makes "nothing files
automatically" and "re-runs are safe" enforceable properties rather than
things we hope the pipeline remembers. Three invariants hold here:

  * APPROVAL. A write requires an explicit human decision. Approval is
    checked at the sink, not just at the caller, so a future bug in the
    pipeline cannot route around the gate.
  * IDEMPOTENCY. Jira and Slack are gated on separate ledger keys, so a crash
    after the ticket but before the notification retries only the
    notification.
  * CRASH SAFETY. Intent is recorded before the stub is called and settled
    after. A dangling intent is resolved by `Ledger.reconcile` on the next
    run against the real contents of the outbox.

The stubs are deliberately naive -- they append whatever they are handed and
de-duplicate nothing -- which is the point: all the safety is in this file.
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import config
from .config import Outcome
from .ledger import Ledger
from .models import ProposedAction

# The stubs live alongside `solution/` rather than inside it.
sys.path.insert(0, str(config.ROOT))

OUTBOX = config.ROOT / "stubs" / "outbox"


class ApprovalRequired(Exception):
    """Raised if anything attempts a write without a recorded approval."""


@dataclass(frozen=True, slots=True)
class WriteResult:
    performed: bool
    reason: str
    jira_key: str | None = None


def _payload_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


def read_outbox_fingerprints() -> dict[str, set[str]]:
    """Fingerprints already present in the outbox, per sink.

    This is the ground truth `reconcile` consults after a crash: the ledger
    may be wrong about whether a write landed, but the outbox is not.
    """
    found: dict[str, set[str]] = {"jira": set(), "slack": set()}
    for sink, filename in (("jira", "jira.jsonl"), ("slack", "slack.jsonl")):
        path = OUTBOX / filename
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            fingerprint = (
                record.get("source", {}).get("fingerprint")
                or record.get("metadata", {}).get("fingerprint")
            )
            if fingerprint:
                found[sink].add(fingerprint)
    return found


class GatedSink:
    """Approval-gated, idempotent wrapper over the Jira and Slack stubs."""

    def __init__(self, ledger: Ledger, run_id: str, logger, *, dry_run: bool = False):
        self.ledger = ledger
        self.run_id = run_id
        self.log = logger
        self.dry_run = dry_run

    # --- jira ----------------------------------------------------------------

    def file_issue(self, action: ProposedAction, payload: dict[str, Any], *, approved: bool) -> WriteResult:
        if not approved:
            raise ApprovalRequired(f"{action.fingerprint} reached the sink without approval")

        known = self.ledger.get_issue(action.fingerprint)
        if known and known.status == "filed" and known.jira_key:
            # The idempotency check that matters. Second run, same issue, no
            # second ticket.
            self.log.event("sink", "jira_skipped_already_filed",
                           fingerprint=action.fingerprint, jira_key=known.jira_key)
            return WriteResult(False, "already filed", known.jira_key)

        write_id = f"jira:{action.fingerprint}"
        if not self.ledger.begin_write(write_id, action.fingerprint, "jira", _payload_hash(payload), self.run_id):
            self.log.event("sink", "jira_skipped_write_claimed", fingerprint=action.fingerprint)
            return WriteResult(False, "write already claimed by another run")

        if self.dry_run:
            self.ledger.commit_write(write_id, "DRY-RUN")
            self.log.event("sink", "jira_dry_run", fingerprint=action.fingerprint)
            return WriteResult(False, "dry run", None)

        try:
            from stubs.jira_stub import create_issue

            record = create_issue(payload)
        except Exception as exc:
            self.ledger.fail_write(write_id, str(exc))
            self.log.event("sink", "jira_write_failed", fingerprint=action.fingerprint, error=str(exc)[:200])
            raise

        jira_key = record["key"]
        self.ledger.commit_write(write_id, jira_key)
        self.ledger.set_status(action.fingerprint, "filed", jira_key=jira_key)
        self.log.event("sink", "jira_filed", fingerprint=action.fingerprint,
                       jira_key=jira_key, priority=action.priority, calls=[s.call_id for s in action.sources])
        return WriteResult(True, "filed", jira_key)

    # --- slack ---------------------------------------------------------------

    def notify(self, action: ProposedAction, payload: dict[str, Any], kind: str, *, approved: bool) -> WriteResult:
        if not approved:
            raise ApprovalRequired(f"{action.fingerprint} reached the sink without approval")

        channel = payload["channel"]
        if self.ledger.notification_sent(action.fingerprint, channel, kind):
            self.log.event("sink", "slack_skipped_already_sent",
                           fingerprint=action.fingerprint, channel=channel, kind=kind)
            return WriteResult(False, "already notified")

        write_id = f"slack:{action.fingerprint}:{kind}"
        if not self.ledger.begin_write(write_id, action.fingerprint, "slack", _payload_hash(payload), self.run_id):
            return WriteResult(False, "write already claimed by another run")

        if self.dry_run:
            self.ledger.commit_write(write_id, "DRY-RUN")
            return WriteResult(False, "dry run")

        try:
            from stubs.slack_stub import post_message

            post_message(payload)
        except Exception as exc:
            self.ledger.fail_write(write_id, str(exc))
            self.log.event("sink", "slack_write_failed", fingerprint=action.fingerprint, error=str(exc)[:200])
            raise

        self.ledger.commit_write(write_id, channel)
        self.ledger.record_notification(action.fingerprint, channel, kind, self.run_id)
        self.log.event("sink", "slack_posted", fingerprint=action.fingerprint, channel=channel, kind=kind)
        return WriteResult(True, "notified")


NOTIFICATION_KIND = {
    Outcome.FILE_NEW: "new",
    Outcome.CORROBORATE: "corroboration",
    Outcome.ALREADY_SHIPPED: "shipped",
}
