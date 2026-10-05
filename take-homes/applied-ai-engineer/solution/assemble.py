"""Build the reviewable action: priority, ticket body, Slack text.

All deterministic. The model contributed a title and a short problem
statement; everything structural -- what priority this is, what the body
looks like, which snippets are quoted -- is assembled here from code, so the
output shape is stable, diffable across runs, and impossible for transcript
text to influence.

The priority matrix is the part worth arguing about, so it is a visible table
rather than a prompt. Two rules in it are load-bearing:

  * `customer_urgency` is recorded and displayed but NEVER raises priority.
    A customer calling a footer typo a P0 does not make it one. It is their
    framing, not our severity, and a pipeline that lets the caller set the
    priority field will be P0-saturated within a month.
  * A cosmetic defect is floored at the bottom regardless of everything else.
"""

from __future__ import annotations

import textwrap

from . import config
from .config import JIRA_PROJECT, Outcome
from .models import Candidate, ProposedAction, Snippet, Source, Transcript

_SEVERITY_FOR_PRIORITY = {"P0": "critical", "P1": "major", "P2": "minor", "P3": "trivial"}


def compute_priority(candidate: Candidate) -> tuple[str, str, str]:
    """Return (priority, severity, rationale).

    Ordered most severe first; the first matching rule wins and the rationale
    names the rule so a reviewer disagreeing with the priority knows exactly
    which line to go argue with.
    """
    obs = candidate.observation
    org_wide = obs.users_affected == "org"

    # Cosmetic defects short-circuit everything below. Checked first precisely
    # so that no amount of customer urgency can promote one.
    if obs.cosmetic_kind == "defect":
        return "P3", "trivial", (
            "cosmetic defect: real but trivial, floored at P3 regardless of how it was framed"
            + (f" (customer framed it as {obs.customer_urgency} urgency)" if obs.customer_urgency == "high" else "")
        )

    if obs.blocks_workflow and not obs.has_workaround and org_wide:
        return "P0", "critical", "blocks a workflow org-wide with no workaround"

    if obs.compliance_or_revenue_driver and obs.blocks_workflow and not obs.has_workaround:
        return "P1", "major", "blocks a compliance- or revenue-driving workflow with no workaround"

    if obs.blocks_workflow and not obs.has_workaround:
        return "P1", "major", "blocks a workflow with no workaround"

    if obs.data_correctness_impact and org_wide:
        return "P1", "major", "shows incorrect data org-wide"

    if obs.data_correctness_impact:
        return "P2", "minor", "shows incorrect data; wrong numbers leave the product and get reported onward"

    if obs.blocks_workflow:
        return "P2", "minor", "blocks a workflow but a workaround exists"

    if obs.compliance_or_revenue_driver:
        return "P2", "minor", "tied to a compliance or renewal driver"

    return "P3", "trivial", "no data-correctness, workflow-blocking or compliance impact identified"


def build_action(
    members: list[Candidate],
    transcripts: dict[str, Transcript],
    outcome: Outcome,
    *,
    dedup_target: str | None = None,
    dedup_rationale: str = "",
    flags: list[str] | None = None,
) -> ProposedAction:
    """Collapse one cluster of candidates into a single reviewable action.

    `members` may span several calls. When it does, the ticket carries every
    source rather than being filed twice -- the unit of work is the issue, not
    the call.
    """
    primary = members[0]

    # Priority is taken as the most severe across the cluster: if one account
    # is blocked org-wide and another merely inconvenienced, the bug is the
    # severe one.
    priorities = [compute_priority(c) for c in members]
    priority, severity, rationale = min(priorities, key=lambda p: config.PRIORITIES.index(p[0]))
    if len(members) > 1:
        rationale += f"; most severe of {len(members)} corroborating reports"

    sources = [
        Source(
            call_id=c.call_id,
            account=transcripts[c.call_id].account,
            date=transcripts[c.call_id].date,
            reporter=_reporter(c),
            transcript_path=f"transcripts/{c.call_id}.md",
            snippets=tuple(c.snippets),
        )
        for c in members
    ]

    all_flags = list(flags or [])
    if len(members) > 1:
        all_flags.append(f"corroborated_by_{len(members)}_accounts")

    return ProposedAction(
        fingerprint=primary.compute_fingerprint(),
        outcome=outcome,
        type=primary.type,
        title=primary.title,
        component=primary.component,
        priority=priority,
        severity=severity,
        priority_rationale=rationale,
        body=_render_body(primary, members, sources, priority, rationale, dedup_target, dedup_rationale),
        sources=sources,
        dedup_target=dedup_target,
        dedup_rationale=dedup_rationale,
        near_misses=primary.near_misses,
        flags=all_flags,
    )


def _reporter(candidate: Candidate) -> str:
    for snippet in candidate.snippets:
        if snippet.side == "EXTERNAL":
            return snippet.speaker
    return "unknown"


def _render_body(
    primary: Candidate,
    members: list[Candidate],
    sources: list[Source],
    priority: str,
    priority_rationale: str,
    dedup_target: str | None,
    dedup_rationale: str,
) -> str:
    """Assemble the Jira description from structured fields and verbatim quotes.

    Templated rather than model-written so that two runs over an unchanged
    transcript produce a byte-identical body, which is what makes the
    idempotency check meaningful and the diff reviewable.
    """
    out: list[str] = []

    out.append("h2. What's happening")
    out.append(textwrap.fill(primary.problem, 88) if primary.problem else "_(no summary extracted)_")
    out.append("")

    out.append("h2. Details")
    out.append(f"* *Trigger:* {primary.trigger}")
    out.append(f"* *Symptom:* {primary.symptom}")
    out.append(f"* *Scope:* {primary.scope}")
    out.append(f"* *Workaround:* {primary.workaround or 'none reported'}")
    out.append(f"* *Component:* {primary.component}")
    out.append("")

    out.append(f"h2. Priority: {priority}")
    out.append(priority_rationale)
    obs = primary.observation
    if obs.customer_urgency == "high" and priority in ("P2", "P3"):
        # Stated explicitly so the reviewer sees the disagreement rather than
        # discovering it when the customer escalates.
        out.append(
            f"_Note: the customer framed this as high urgency. Priority is set from "
            f"measured impact, not from how it was raised. Override at review if the "
            f"relationship context warrants it._"
        )
    out.append("")

    out.append("h2. Evidence")
    out.append("_Verbatim from the call recording. Quotes are read from the transcript file, "
               "not generated._")
    out.append("")
    for source in sources:
        out.append(f"*{source.account}* -- {source.reporter}, {source.date} "
                   f"([{source.call_id}|{source.transcript_path}])")
        for snippet in source.snippets:
            if snippet.side != "EXTERNAL":
                continue
            out.append(f"{{quote}}{snippet.text}{{quote}}")
            out.append(f"_{source.transcript_path}:{snippet.line_no} (turn {snippet.turn_idx})_")
        out.append("")

    if len(sources) > 1:
        out.append(f"h2. Corroboration")
        out.append(f"Reported independently by {len(sources)} accounts: "
                   + ", ".join(s.account for s in sources) + ".")
        out.append("")

    if primary.near_misses:
        out.append("h2. De-duplication")
        out.append("Checked against these tracked issues and judged distinct:")
        for nm in primary.near_misses:
            out.append(f"* {nm.key} -- {nm.summary}")
            out.append(f"** {nm.reason} (similarity {nm.similarity}, by {nm.decided_by})")
        out.append("")

    if dedup_target:
        out.append(f"h2. Relates to {dedup_target}")
        out.append(dedup_rationale)
        out.append("")

    out.append("----")
    out.append(f"_Filed from call transcript by the call-signal triage pipeline after human review. "
               f"Source of truth: {sources[0].transcript_path}_")
    return "\n".join(out).strip()


# --- sink payloads -----------------------------------------------------------


def jira_payload(action: ProposedAction) -> dict:
    """The exact dict handed to `stubs.jira_stub.create_issue`."""
    return {
        "project": JIRA_PROJECT,
        "type": action.type,
        "summary": action.title,
        "description": action.body,
        "priority": action.priority,
        "severity": action.severity,
        "labels": ["from-customer-call", f"component/{action.component}"]
        + (["corroborated"] if len(action.sources) > 1 else []),
        "source": {
            "pipeline": "call-signal-triage",
            "fingerprint": action.fingerprint,
            "calls": [s.call_id for s in action.sources],
            "transcripts": [s.transcript_path for s in action.sources],
            "accounts": [s.account for s in action.sources],
            "snippet": _primary_snippet(action),
            "snippet_location": _primary_location(action),
        },
    }


def slack_payload(action: ProposedAction, jira_key: str | None) -> dict:
    """Notification for the call owner.

    Written to be actionable at a glance in a notification list: what was
    found, on whose call, in the customer's own words, and what happened.
    """
    source = action.sources[0]
    verb = {
        Outcome.FILE_NEW: "Filed a new ticket",
        Outcome.CORROBORATE: f"Attached corroboration to {action.dedup_target}",
        Outcome.ALREADY_SHIPPED: f"No ticket needed -- already shipped as {action.dedup_target}",
    }[action.outcome]

    lines = [
        f"*{verb}* from your call with {source.account}",
        f"> {_primary_snippet(action)}",
        f"-- {source.reporter}, {source.date} (`{source.transcript_path}`)",
        "",
    ]

    if action.outcome == Outcome.FILE_NEW:
        lines.append(f"*{jira_key or 'PROJ-?'}* [{action.priority}/{action.type}] {action.title}")
        lines.append(f"_{action.priority_rationale}_")
    elif action.outcome == Outcome.CORROBORATE:
        lines.append(f"Added {source.account} as a reporting account on *{action.dedup_target}*. "
                     f"No new ticket opened.")
        lines.append(f"_{action.dedup_rationale}_")
    else:
        lines.append(f"This already exists as *{action.dedup_target}*. Worth walking "
                     f"{source.account} through it rather than filing anything.")

    if len(action.sources) > 1:
        lines.append(f"\n:link: Also reported by: "
                     + ", ".join(f"{s.account} ({s.call_id})" for s in action.sources[1:]))

    return {
        "channel": "#cs-call-signal",
        "text": "\n".join(lines),
        "metadata": {
            "fingerprint": action.fingerprint,
            "outcome": str(action.outcome),
            "call_ids": [s.call_id for s in action.sources],
            "jira_key": jira_key,
            "priority": action.priority,
        },
    }


def _primary_snippet(action: ProposedAction) -> str:
    for source in action.sources:
        for snippet in source.snippets:
            if snippet.side == "EXTERNAL":
                return snippet.text
    return ""


def _primary_location(action: ProposedAction) -> str:
    for source in action.sources:
        for snippet in source.snippets:
            if snippet.side == "EXTERNAL":
                return f"{source.transcript_path}:{snippet.line_no}"
    return ""
