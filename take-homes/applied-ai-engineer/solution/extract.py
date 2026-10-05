"""Turn a model response into `Candidate` objects. Nothing is trusted here.

This module is the airlock. Everything arriving is attacker-or-hallucination
controlled, so parsing is total: unknown fields are ignored, missing fields
take conservative defaults, and anything structurally unusable is reported as
a malformed candidate rather than raised. A single bad candidate must not cost
us the other three in the same response.

Note the defaults in `_parse_observation`. They are chosen so that a model
that omits a field produces a candidate that gets dropped or de-prioritised,
never one that gets filed. Absence of evidence is not evidence of a filable
bug.
"""

from __future__ import annotations

from typing import Any

from . import config
from .llm.prompts import build_extract_prompt
from .llm.provider import LLMProvider, LLMRequest
from .models import Candidate, Observation, Transcript


class MalformedCandidate(Exception):
    """A candidate too broken to represent. Counted as a schema drop."""


def extract_candidates(
    transcript: Transcript, provider: LLMProvider
) -> tuple[list[Candidate], list[str], dict[str, Any]]:
    """Return (candidates, malformed_reasons, call_metadata).

    Raises only if the provider itself fails, which the pipeline treats as a
    per-transcript error so the other 139 transcripts still complete.
    """
    system, user = build_extract_prompt(transcript)
    request = LLMRequest(
        task="extract",
        # The content hash is in the key so an edited transcript re-extracts
        # rather than silently replaying the previous version's answer.
        cache_key=f"{transcript.call_id}:{transcript.content_hash}",
        system=system,
        user=user,
        prompt_version=config.PROMPT_VERSIONS["extract"],
    )
    response = provider.complete(request)

    raw_candidates = response.data.get("candidates")
    if not isinstance(raw_candidates, list):
        raise MalformedCandidate(f"'candidates' missing or not a list for {transcript.call_id}")

    candidates: list[Candidate] = []
    malformed: list[str] = []
    for i, raw in enumerate(raw_candidates):
        try:
            candidates.append(_parse_candidate(raw, transcript.call_id))
        except MalformedCandidate as exc:
            malformed.append(f"candidate[{i}]: {exc}")

    meta = {
        "model": response.model,
        "source": response.source,
        "input_tokens": response.input_tokens,
        "output_tokens": response.output_tokens,
    }
    return candidates, malformed, meta


def _parse_candidate(raw: Any, call_id: str) -> Candidate:
    if not isinstance(raw, dict):
        raise MalformedCandidate(f"expected object, got {type(raw).__name__}")

    title = _str(raw.get("title")).strip()
    if not title:
        raise MalformedCandidate("missing title")

    # Enum values are NOT coerced to a default here. An out-of-vocabulary type
    # is a real signal that the model misbehaved, so it is preserved verbatim
    # and rejected by the schema gate, where it gets logged as such. Silently
    # rewriting "Epic" to "Bug" would hide exactly the drift we want to see.
    return Candidate(
        call_id=call_id,
        title=title[:200],
        type=_str(raw.get("type")).strip(),
        problem=_str(raw.get("problem")).strip(),
        evidence_turns=_int_list(raw.get("evidence_turns")),
        component=_str(raw.get("component")).strip().lower(),
        trigger=_str(raw.get("trigger")).strip(),
        symptom=_str(raw.get("symptom")).strip(),
        scope=_str(raw.get("scope")).strip(),
        workaround=(_str(raw["workaround"]).strip() or None) if raw.get("workaround") else None,
        observation=_parse_observation(raw.get("observation")),
    )


def _parse_observation(raw: Any) -> Observation:
    """Build an Observation, defaulting toward 'do not file' on absence.

    `firsthand` and `actionable_specificity` default to False: if the model
    did not affirm that the customer experienced this and described it
    concretely, we have no business opening a ticket. The remaining booleans
    default False because they are drop triggers, and asserting a drop reason
    the model never reported would be its own kind of wrong.
    """
    d = raw if isinstance(raw, dict) else {}
    return Observation(
        raised_by_external=_bool(d.get("raised_by_external"), False),
        firsthand=_bool(d.get("firsthand"), False),
        retracted_on_call=_bool(d.get("retracted_on_call"), False),
        resolved_on_call=_bool(d.get("resolved_on_call"), False),
        customer_side_root_cause=_bool(d.get("customer_side_root_cause"), False),
        actionable_specificity=_bool(d.get("actionable_specificity"), False),
        not_a_product_issue=_bool(d.get("not_a_product_issue"), False),
        customer_declined_filing=_bool(d.get("customer_declined_filing"), False),
        cosmetic_kind=_enum(d.get("cosmetic_kind"), ("preference", "defect"), None),
        data_correctness_impact=_bool(d.get("data_correctness_impact"), False),
        blocks_workflow=_bool(d.get("blocks_workflow"), False),
        compliance_or_revenue_driver=_bool(d.get("compliance_or_revenue_driver"), False),
        has_workaround=_bool(d.get("has_workaround"), False),
        users_affected=_enum(d.get("users_affected"), ("one", "team", "org", "unknown"), "unknown"),
        customer_urgency=_enum(d.get("customer_urgency"), ("low", "medium", "high"), "medium"),
    )


# --- coercion helpers --------------------------------------------------------


def _str(value: Any) -> str:
    return value if isinstance(value, str) else ("" if value is None else str(value))


def _bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        # Models occasionally return "true"/"yes" as strings.
        low = value.strip().lower()
        if low in ("true", "yes"):
            return True
        if low in ("false", "no", "null", "none", ""):
            return False
    return default


def _enum(value: Any, allowed: tuple[str, ...], default):
    return value if isinstance(value, str) and value in allowed else default


def _int_list(value: Any) -> list[int]:
    """Coerce to a de-duplicated, sorted list of ints, discarding junk.

    Sorted so that the same citation set in a different order produces an
    identical candidate -- one less source of run-to-run drift.
    """
    if not isinstance(value, list):
        return []
    out: set[int] = set()
    for item in value:
        if isinstance(item, bool):
            continue
        if isinstance(item, int):
            out.add(item)
        elif isinstance(item, str) and item.strip().lstrip("-").isdigit():
            out.add(int(item.strip()))
    return sorted(out)
