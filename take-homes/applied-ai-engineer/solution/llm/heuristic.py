"""A deterministic, rule-based stand-in for the extraction model.

WHY THIS EXISTS. The authored replay fixtures cover the 15 labelled dev calls.
That is enough to measure the policy layer against the labels, but it leaves
125 calls unprocessed, so nothing in the output demonstrates that the
pipeline survives the full corpus: de-duplication at 140-call scale,
cross-call clustering finding real clusters, the ledger staying idempotent
over hundreds of actions, partial-failure isolation.

This provider closes that gap without an API key. It reads the external turns
of a transcript and emits candidates from keyword rules. It is a BASELINE,
not a model:

  * Precision is poor by construction. It fires on surface cues, so it
    proposes things a model would not and misses things a model would catch.
  * It is therefore NOT used to score against `dev_labels.json`. The dev-set
    score uses the replay provider. Mixing them would be dishonest in both
    directions.

What a full-corpus run with this provider DOES prove, and it is the part that
was unproven before: every one of the 140 transcripts parses, gates, de-dups,
clusters and lands in the ledger; a second run writes nothing new; and one
injected failure does not disturb the other 139. Those are properties of the
deterministic machinery, and the machinery is what this exercises.

Being rule-based, it is also perfectly reproducible, which makes the
idempotency and re-run diffs exact rather than approximate.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .. import config
from ..ingest import parse_transcript
from .provider import LLMRequest, LLMResponse

# --- signal vocabularies -----------------------------------------------------

_BUG_CUES = (
    "broken", "breaks", "crash", "crashes", "crashed", "fails", "failing", "failed",
    "doesn't work", "does not work", "not working", "error", "errors", "bug",
    "stale", "wrong", "incorrect", "mismatch", "truncat", "times out", "timing out",
    "timed out", "404", "blank", "white screen", "stuck", "loop", "hangs", "hanging",
    "duplicate", "delayed", "delay", "lag", "lags", "off by", "can't log in",
    "cannot log in", "won't open", "doesn't match", "disappear",
)

_FEATURE_CUES = (
    "can you add", "could you add", "could we get", "can we get", "we need",
    "i need", "what i need", "feature request", "would be great if", "i'd like",
    "it would help if", "is there a way to", "any plans to", "wish list",
    "my ask", "the ask", "asking for", "request is",
)

# Cues that set observation flags. The pipeline's policy layer turns these
# into drops; this provider only reports them.
_RETRACT_CUES = (
    "don't file", "do not file", "nothing to file", "not a real complaint",
    "i'm not asking", "not really asking", "i'm nitpicking", "forget it",
    "take it or leave it", "you're allowed to ignore", "not a complaint",
)
_RESOLVED_CUES = (
    "false alarm", "my fault", "turned out to be", "resolved itself", "fixed itself",
    "already resolved", "cross this off", "it resolved", "was user error",
    "feel appropriately sheepish", "nothing got deleted",
)
_CUSTOMER_CAUSE_CUES = (
    "our vpn", "our idp", "our network", "our wifi", "on our side", "our gateway",
    "our clocks", "our servers", "temporary network", "our email-security",
    "ntp", "client-side", "our own",
)
_HEARSAY_CUES = (
    "a peer of mine", "at a conference", "someone told me", "i heard", "hearsay",
    "secondhand", "i haven't seen", "have not seen it", "gossip", "rumor", "rumour",
    "another firm", "a friend of mine",
)
_COSMETIC_CUES = (
    "cosmetic", "aesthetic", "nitpick", "font", "purple", "color", "colour",
    "stock photo", "corny", "a little loud", "squint", "too small",
)
_VAGUE_CUES = (
    "it's a vibe", "a feeling", "can't tell you", "cannot tell you", "i don't know if it's you",
    "feels a little slow", "feels a touch slow", "might be our", "genuinely can't say",
    "i feel a little silly",
)
_WORKAROUND_CUES = ("workaround", "work around", "clearing", "clear your cookies",
                    "wait ten minutes", "force-quit", "manually", "off the vpn")
_BLOCKING_CUES = ("blocker", "blocking", "can't", "cannot", "locked out", "never get in",
                  "stops", "swamp", "audit", "rollout")
_COMPLIANCE_CUES = ("soc 2", "soc2", "audit", "auditor", "osha", "compliance", "regulated",
                    "renewal", "procurement", "control gap", "segregation of duties")
_DATA_CUES = ("number", "numbers", "count", "total", "report", "timestamp", "data",
              "adds up", "doesn't match", "figures")
_SPECIFIC_RE = re.compile(r"\b(\d+|ten minutes|thirty minutes|seven hours|reproduc)\w*", re.I)

_MAX_CANDIDATES_PER_CALL = 4
_MIN_TURN_WORDS = 12  # ignore one-line reactions; they carry no report


@dataclass
class HeuristicProvider:
    """Rule-based extraction. Deterministic given the same transcript."""

    name: str = "heuristic"
    _cache: dict[str, dict[str, Any]] = field(default_factory=dict)

    def complete(self, request: LLMRequest) -> LLMResponse:
        if request.task == "extract":
            call_id = request.cache_key.split(":")[0]
            data = self._cache.get(call_id) or self._extract(call_id)
            self._cache[call_id] = data
            return LLMResponse(data=data, model="heuristic-v1", source="heuristic")

        # De-duplication and clustering adjudication: abstain. Returning
        # `same: false` makes the pipeline fail open to a separate ticket,
        # which is the safe direction -- a duplicate a human merges, rather
        # than a real issue buried as a duplicate.
        return LLMResponse(
            data={"same": False, "confidence": 0.0,
                  "reason": "heuristic provider abstains on ambiguous pairs; failing open to distinct"},
            model="heuristic-v1",
            source="heuristic",
        )

    def _extract(self, call_id: str) -> dict[str, Any]:
        from .prompts import build_extract_prompt  # noqa: F401  (parity with real path)
        from ..dedup import infer_component

        transcript = parse_transcript(config.TRANSCRIPTS_DIR / f"{call_id}.md")
        full_text = " ".join(t.text.lower() for t in transcript.turns)

        candidates: list[dict[str, Any]] = []
        seen_components: set[str] = set()

        for turn in transcript.turns:
            if not turn.is_external or len(turn.text.split()) < _MIN_TURN_WORDS:
                continue
            low = turn.text.lower()

            is_bug = any(cue in low for cue in _BUG_CUES)
            is_feature = any(cue in low for cue in _FEATURE_CUES)
            if not (is_bug or is_feature):
                continue

            component = infer_component(turn.text)
            # One candidate per component per call. Without this the same
            # complaint discussed over six turns becomes six candidates.
            if component in seen_components:
                continue
            seen_components.add(component)

            # Local window: the flags are usually set a turn or two away from
            # the report itself ("...actually, cross that off, it was our VPN").
            window = " ".join(
                transcript.turns[i].text.lower()
                for i in range(max(0, turn.idx - 3), min(len(transcript.turns), turn.idx + 4))
            )

            candidates.append({
                "title": _title(turn.text),
                "type": "Bug" if is_bug else "Feature",
                "problem": turn.text[:400],
                "evidence_turns": [turn.idx],
                "component": component,
                "trigger": _clause(turn.text, 0),
                "symptom": _clause(turn.text, 1),
                "scope": "reported by the external participant on this call",
                "workaround": "stated on the call" if any(c in window for c in _WORKAROUND_CUES) else None,
                "observation": {
                    "raised_by_external": True,
                    "firsthand": not any(c in window for c in _HEARSAY_CUES),
                    "retracted_on_call": any(c in window for c in _RETRACT_CUES),
                    "resolved_on_call": any(c in window for c in _RESOLVED_CUES),
                    "customer_side_root_cause": any(c in window for c in _CUSTOMER_CAUSE_CUES),
                    "actionable_specificity": bool(_SPECIFIC_RE.search(turn.text)),
                    "not_a_product_issue": False,
                    "customer_declined_filing": any(c in window for c in _RETRACT_CUES),
                    "cosmetic_kind": "preference" if any(c in low for c in _COSMETIC_CUES) else None,
                    "data_correctness_impact": any(c in low for c in _DATA_CUES),
                    "blocks_workflow": any(c in low for c in _BLOCKING_CUES),
                    "compliance_or_revenue_driver": any(c in full_text for c in _COMPLIANCE_CUES),
                    "has_workaround": any(c in window for c in _WORKAROUND_CUES),
                    "users_affected": "org" if "everyone" in low or "all " in low else "team",
                    "customer_urgency": "high" if any(c in low for c in _VAGUE_CUES) is False and is_bug else "low",
                },
            })
            if len(candidates) >= _MAX_CANDIDATES_PER_CALL:
                break

        return {"candidates": candidates}


def _title(text: str) -> str:
    """First clause, cleaned up, as a stand-in summary."""
    cleaned = re.sub(r"\s+", " ", text).strip()
    cleaned = re.sub(r"^(so|okay|right|yeah|and|but|well|oh)[,\s]+", "", cleaned, flags=re.I)
    for sep in (" — ", ". ", ", and ", " because "):
        if sep in cleaned:
            cleaned = cleaned.split(sep)[0]
            break
    return (cleaned[:88] or "unspecified issue").strip(" .,")


def _clause(text: str, index: int) -> str:
    """Rough trigger/symptom split: successive clauses of the report.

    Crude on purpose. The point is that `trigger` and `symptom` carry
    *different* text so the fingerprint and the de-dup comparison have
    something to work with; a real model writes these properly.
    """
    parts = [p.strip() for p in re.split(r"[—.,;]", re.sub(r"\s+", " ", text)) if len(p.strip()) > 12]
    if not parts:
        return text[:70].strip() or "unspecified"
    return parts[min(index, len(parts) - 1)][:110]
