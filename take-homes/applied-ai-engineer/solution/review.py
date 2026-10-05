"""The human gate: what the reviewer sees, and how decisions get recorded.

The brief asks what the human sees and how the review stays fast. The design
target is roughly fifteen seconds per item, and the things that buy that are
less about UI than about what is on the card:

  * The verbatim customer quote, first, with a `file:line` pointer into the
    transcript. The reviewer's real question is "did this actually happen",
    and a quote they can trust answers it without opening anything.
  * The de-duplication reasoning, including the near-misses we rejected.
    "Checked against PROJ-064 and here is the discriminator" is what turns a
    de-dup decision from an assertion into something checkable.
  * The priority rule that fired, by name, so disagreement is actionable.
  * Hard cases pulled to the top. Everything the gates already killed is in
    the log, not the queue -- the reviewer's attention is the scarce resource,
    so it is spent only on things that would otherwise be written.

Two artefacts, deliberately: a markdown digest for humans (skimmable,
diffable, reviewable in a PR) and a JSON queue for machines. `decisions.json`
is the only input to `apply`, so approving is an explicit, auditable act.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import config
from .config import Outcome
from .models import ProposedAction, to_jsonable

_OUTCOME_LABEL = {
    Outcome.FILE_NEW: "FILE NEW TICKET",
    Outcome.CORROBORATE: "ATTACH CORROBORATION",
    Outcome.ALREADY_SHIPPED: "NO TICKET - ALREADY SHIPPED",
}

# Flags that mean "a human should look harder at this one". Anything carrying
# one of these sorts to the top of the digest.
_ATTENTION_FLAGS = (
    "suppression_attempt_in_call",
    "injection_turns_stripped",
    "hallucinated_citations",
)


@dataclass
class ReviewQueue:
    run_id: str
    actions: list[ProposedAction]
    generated_at: str

    @classmethod
    def build(cls, run_id: str, actions: list[ProposedAction]) -> ReviewQueue:
        return cls(
            run_id=run_id,
            actions=sorted(actions, key=_review_sort_key),
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    def write(self) -> tuple[Path, Path]:
        config.REVIEW_DIR.mkdir(parents=True, exist_ok=True)
        queue_path = config.REVIEW_DIR / f"queue-{self.run_id}.json"
        digest_path = config.REVIEW_DIR / f"review-{self.run_id}.md"

        queue_path.write_text(
            json.dumps(
                {
                    "run_id": self.run_id,
                    "generated_at": self.generated_at,
                    "actions": [to_jsonable(a) for a in self.actions],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        digest_path.write_text(self.render(), encoding="utf-8")

        # Stable names so a reviewer always has one path to open.
        for stable, source in (("latest-queue.json", queue_path), ("REVIEW.md", digest_path)):
            target = config.REVIEW_DIR / stable
            tmp = target.with_suffix(target.suffix + ".tmp")
            tmp.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
            os.replace(tmp, target)

        return queue_path, digest_path

    def render(self) -> str:
        lines: list[str] = [
            f"# Call-signal review queue",
            "",
            f"Run `{self.run_id}` - generated {self.generated_at}",
            "",
            f"**{len(self.actions)} item(s) awaiting your decision.** Nothing has been written to "
            f"Jira or Slack. Approve with:",
            "",
            "```bash",
            "python -m solution.cli decide --approve <fingerprint>     # or --reject",
            "python -m solution.cli decide --approve-all               # everything below",
            "python -m solution.cli apply                              # write the approved ones",
            "```",
            "",
        ]

        if not self.actions:
            lines += [
                "No new issues this run.",
                "",
                "If that is unexpected, check the run summary for health alerts - "
                "an empty queue and a broken extractor look identical from here.",
            ]
            return "\n".join(lines)

        counts: dict[str, int] = {}
        for action in self.actions:
            counts[str(action.outcome)] = counts.get(str(action.outcome), 0) + 1
        lines.append("| Outcome | Count |")
        lines.append("|---|---|")
        for outcome, n in sorted(counts.items()):
            lines.append(f"| {outcome} | {n} |")
        lines.append("")
        lines.append("---")
        lines.append("")

        for i, action in enumerate(self.actions, start=1):
            lines.extend(_render_card(i, action))

        return "\n".join(lines)


def _review_sort_key(action: ProposedAction) -> tuple:
    """Needs-attention first, then by priority, then deterministically.

    The final `fingerprint` term keeps the ordering stable across runs so the
    digest diffs cleanly instead of reshuffling.
    """
    needs_attention = any(f.startswith(_ATTENTION_FLAGS) for f in action.flags)
    return (
        0 if needs_attention else 1,
        config.PRIORITIES.index(action.priority) if action.priority in config.PRIORITIES else 9,
        str(action.outcome),
        action.fingerprint,
    )


def _render_card(index: int, action: ProposedAction) -> list[str]:
    label = _OUTCOME_LABEL[action.outcome]
    source = action.sources[0]

    lines = [
        f"## {index}. {action.title}",
        "",
        f"**{label}** &nbsp;|&nbsp; `{action.priority}` &nbsp;|&nbsp; {action.type} "
        f"&nbsp;|&nbsp; `{action.component}` &nbsp;|&nbsp; `{action.fingerprint}`",
        "",
    ]

    attention = [f for f in action.flags if f.startswith(_ATTENTION_FLAGS)]
    if attention:
        lines += [f"> **Needs a closer look:** {', '.join(attention)}", ""]

    # The quote comes first: it is the fastest possible answer to "is this real".
    lines.append("**What the customer said**")
    lines.append("")
    for src in action.sources:
        external = [s for s in src.snippets if s.side == "EXTERNAL"][:2]
        if not external:
            continue
        for snippet in external:
            lines.append(f"> {snippet.text}")
            lines.append(">")
        last = external[-1]
        lines.append(
            f"> -- **{last.speaker}**, {src.account}, {src.date} - "
            f"[`{src.transcript_path}:{last.line_no}`]({src.transcript_path}#L{last.line_no})"
        )
        lines.append("")

    lines.append("**Why this disposition**")
    lines.append("")
    lines.append(f"- Priority `{action.priority}`: {action.priority_rationale}")

    if action.outcome == Outcome.FILE_NEW:
        if action.near_misses:
            checked = ", ".join(f"`{nm.key}`" for nm in action.near_misses)
            lines.append(f"- De-dup: checked {checked}, all distinct")
            for nm in action.near_misses:
                lines.append(f"  - `{nm.key}` ({nm.summary[:60]}...) - {nm.reason}")
        else:
            lines.append("- De-dup: no tracked issue in the same area")
    else:
        lines.append(f"- De-dup: {action.dedup_rationale}")

    if len(action.sources) > 1:
        accounts = ", ".join(f"{s.account} (`{s.call_id}`)" for s in action.sources)
        lines.append(f"- Corroborated by {len(action.sources)} accounts: {accounts}")

    lines.append("")
    lines.append("<details><summary>Full ticket body as it would be filed</summary>")
    lines.append("")
    lines.append("```")
    lines.append(action.body)
    lines.append("```")
    lines.append("")
    lines.append("</details>")
    lines.append("")
    lines.append(f"`approve {action.fingerprint}` &nbsp; `reject {action.fingerprint}`")
    lines.append("")
    lines.append("---")
    lines.append("")
    return lines


# --- decisions ---------------------------------------------------------------


@dataclass
class Decisions:
    """Human approvals, persisted. The only thing `apply` will act on."""

    path: Path
    data: dict[str, Any]

    @classmethod
    def load(cls, path: Path | None = None) -> Decisions:
        path = path or config.DECISIONS_FILE
        if path.exists():
            return cls(path=path, data=json.loads(path.read_text(encoding="utf-8")))
        return cls(path=path, data={"decisions": {}})

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)

    def record(self, fingerprint: str, verdict: str, *, reviewer: str, note: str = "") -> None:
        if verdict not in ("approve", "reject"):
            raise ValueError(f"verdict must be approve or reject, got {verdict!r}")
        self.data.setdefault("decisions", {})[fingerprint] = {
            "verdict": verdict,
            "reviewer": reviewer,
            "note": note,
            "decided_at": datetime.now(timezone.utc).isoformat(),
        }

    def verdict(self, fingerprint: str) -> str | None:
        entry = self.data.get("decisions", {}).get(fingerprint)
        return entry["verdict"] if entry else None

    def is_approved(self, fingerprint: str) -> bool:
        return self.verdict(fingerprint) == "approve"

    def reviewer(self, fingerprint: str) -> str:
        entry = self.data.get("decisions", {}).get(fingerprint)
        return entry.get("reviewer", "unknown") if entry else "unknown"
