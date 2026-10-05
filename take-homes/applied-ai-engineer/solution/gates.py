"""Deterministic gates. The model proposes; this module disposes.

Every reason a candidate never becomes a ticket is decided here, in ordinary
Python, from the observations the model reported. That split is the core design
claim of the build:

  * The model answers "did the customer take this back?" -- reading
    comprehension, genuinely hard, worth a model call.
  * This module answers "does that mean we skip it?" -- policy, trivially
    expressible as code, and far better off as code: it is unit-testable
    without an API key, it shows up in a diff when someone changes it, and it
    cannot be argued out of its position by anything written in a transcript.

Gates run in two tiers. INTEGRITY gates are non-negotiable and come first:
they protect the write path from hallucination and injection, and no model
output can satisfy its way past them. EDITORIAL gates encode "is this worth a
human's attention", and those are the ones a reasonable person might tune.
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import COMPONENTS, ISSUE_TYPES, DropReason
from .models import Candidate, Snippet, Transcript


@dataclass(frozen=True, slots=True)
class GateResult:
    passed: bool
    reason: DropReason | None = None
    detail: str = ""
    flags: tuple[str, ...] = ()


def apply_gates(candidate: Candidate, transcript: Transcript) -> GateResult:
    """Run every gate in order. First failure wins and explains itself."""
    flags: list[str] = []

    for gate in (_gate_schema, _gate_evidence, _gate_injection, _gate_external_speaker):
        result = gate(candidate, transcript)
        flags.extend(result.flags)
        if not result.passed:
            return GateResult(False, result.reason, result.detail, tuple(flags))

    for gate in (
        _gate_not_product_issue,
        _gate_hearsay,
        _gate_retracted,
        _gate_declined,
        _gate_resolved,
        _gate_customer_root_cause,
        _gate_cosmetic,
        _gate_specificity,
    ):
        result = gate(candidate, transcript)
        flags.extend(result.flags)
        if not result.passed:
            return GateResult(False, result.reason, result.detail, tuple(flags))

    # A suppression attempt anywhere in the call never blocks the candidate --
    # that is the attacker's goal -- but it does force human eyes on it.
    if transcript.suppression_turns:
        flags.append("suppression_attempt_in_call")

    return GateResult(True, flags=tuple(flags))


# --- tier 1: integrity -------------------------------------------------------


def _gate_schema(candidate: Candidate, transcript: Transcript) -> GateResult:
    """Closed vocabularies, enforced. An unknown enum means the model drifted."""
    problems = []
    if candidate.type not in ISSUE_TYPES:
        problems.append(f"type={candidate.type!r} not in {ISSUE_TYPES}")
    if candidate.component not in COMPONENTS:
        problems.append(f"component={candidate.component!r} not in vocabulary")
    if not candidate.trigger or not candidate.symptom:
        # Without both, the candidate has no stable identity, so it can be
        # neither de-duplicated nor made idempotent. Filing it would guarantee
        # a duplicate on the next run.
        problems.append("missing trigger or symptom (no stable identity)")
    if problems:
        return GateResult(False, DropReason.SCHEMA_INVALID, "; ".join(problems))
    return GateResult(True)


def _gate_evidence(candidate: Candidate, transcript: Transcript) -> GateResult:
    """Resolve cited turn indices into verbatim text, or reject the candidate.

    This is where "the raw transcript is the source of truth" stops being a
    principle and becomes a mechanism. The model never supplied the quote; it
    supplied an integer, and the quote is read out of the file here. An index
    that does not resolve is a hallucination and the candidate dies.
    """
    if not candidate.evidence_turns:
        return GateResult(False, DropReason.EVIDENCE_NOT_FOUND, "no evidence turns cited")

    resolved: list[Snippet] = []
    bad: list[int] = []
    for idx in candidate.evidence_turns:
        turn = transcript.turn(idx)
        if turn is None:
            bad.append(idx)
            continue
        resolved.append(
            Snippet(
                turn_idx=turn.idx,
                line_no=turn.line_no,
                speaker=turn.speaker,
                side=turn.side,
                text=turn.text,
            )
        )

    if not resolved:
        return GateResult(
            False,
            DropReason.EVIDENCE_NOT_FOUND,
            f"none of the cited turns exist (cited {candidate.evidence_turns}, "
            f"transcript has {len(transcript.turns)})",
        )

    candidate.snippets = resolved
    # Partial hallucination: keep the candidate on the strength of the turns
    # that do resolve, but flag it so the reviewer knows the citation set was
    # not clean. Dropping outright would let one bad index bury a real bug.
    flags = (f"hallucinated_citations:{bad}",) if bad else ()
    return GateResult(True, flags=flags)


def _gate_injection(candidate: Candidate, transcript: Transcript) -> GateResult:
    """Refuse evidence that is itself an instruction aimed at an automation.

    Surgical by design. Calls 005, 011 and 053 each contain an injection
    attempt alongside a genuine product issue that must still be filed, so the
    injection turns are stripped from the evidence set and the candidate is
    only killed if nothing legitimate is left holding it up. Quarantining the
    whole call would fail all three.
    """
    if not transcript.injection_turns:
        return GateResult(True)

    tainted = [s for s in candidate.snippets if s.turn_idx in transcript.injection_turns]
    if not tainted:
        return GateResult(True)

    clean = [s for s in candidate.snippets if s.turn_idx not in transcript.injection_turns]
    if not clean:
        return GateResult(
            False,
            DropReason.INJECTION_QUARANTINED,
            f"every cited turn {[s.turn_idx for s in tainted]} is text addressed to an "
            f"automated reader; refusing to treat an injected instruction as a bug report",
        )

    candidate.snippets = clean
    candidate.evidence_turns = [s.turn_idx for s in clean]
    return GateResult(True, flags=(f"injection_turns_stripped:{[s.turn_idx for s in tainted]}",))


def _gate_external_speaker(candidate: Candidate, transcript: Transcript) -> GateResult:
    """At least one surviving citation must be an [EXTERNAL] speaker.

    Requirement 1 of the brief, enforced against the file rather than trusted
    from `observation.raised_by_external`. The model can be wrong or talked
    into being wrong about who said something; the speaker tag cannot.
    """
    if any(s.side == "EXTERNAL" for s in candidate.snippets):
        return GateResult(True)
    cited = [(s.turn_idx, s.side) for s in candidate.snippets]
    return GateResult(
        False,
        DropReason.NO_EXTERNAL_EVIDENCE,
        f"no cited turn is spoken by an external participant (cited {cited})",
    )


# --- tier 2: editorial policy ------------------------------------------------


def _gate_not_product_issue(candidate: Candidate, _: Transcript) -> GateResult:
    if candidate.observation.not_a_product_issue:
        return GateResult(
            False, DropReason.NOT_A_PRODUCT_ISSUE, "competitor intel, account or CSM task, not product"
        )
    return GateResult(True)


def _gate_hearsay(candidate: Candidate, _: Transcript) -> GateResult:
    """Secondhand reports do not become tickets.

    "Someone at a conference said exports drop rows" is unactionable and
    unverifiable; an engineer handed it has nothing to reproduce. If it is
    real, a firsthand report will arrive.
    """
    if not candidate.observation.firsthand:
        return GateResult(False, DropReason.HEARSAY, "not a firsthand report")
    return GateResult(True)


def _gate_retracted(candidate: Candidate, _: Transcript) -> GateResult:
    if candidate.observation.retracted_on_call:
        return GateResult(False, DropReason.RETRACTED_ON_CALL, "speaker withdrew it during the call")
    return GateResult(True)


def _gate_declined(candidate: Candidate, _: Transcript) -> GateResult:
    """Honour an explicit "don't file this".

    Worth stating plainly because it looks like the suppression-injection case
    and is the opposite of it: this is a named participant speaking in their
    own voice about their own report, which is authority we respect. An
    instruction embedded in pasted text addressed to "AI systems" is not, and
    is handled upstream in `_gate_injection`.
    """
    if candidate.observation.customer_declined_filing:
        return GateResult(
            False, DropReason.CUSTOMER_DECLINED_FILING, "customer explicitly asked us not to file"
        )
    return GateResult(True)


def _gate_resolved(candidate: Candidate, _: Transcript) -> GateResult:
    if candidate.observation.resolved_on_call:
        return GateResult(
            False, DropReason.RESOLVED_ON_CALL, "user error or resolved live during the call"
        )
    return GateResult(True)


def _gate_customer_root_cause(candidate: Candidate, _: Transcript) -> GateResult:
    if candidate.observation.customer_side_root_cause:
        return GateResult(
            False,
            DropReason.CUSTOMER_SIDE_ROOT_CAUSE,
            "root cause is on the customer's side (their IdP, VPN or gateway)",
        )
    return GateResult(True)


def _gate_cosmetic(candidate: Candidate, _: Transcript) -> GateResult:
    """Split cosmetic into taste and defect, because they get opposite answers.

    A font-size request or a dislike of a header colour is a preference: no
    objective defect exists, so there is nothing to fix and we drop it. A
    misspelled brand name in an outbound email footer is objectively wrong and
    does belong in the backlog -- just at the bottom of it, which the priority
    matrix handles rather than this gate.
    """
    if candidate.observation.cosmetic_kind == "preference":
        return GateResult(
            False, DropReason.COSMETIC_PREFERENCE, "subjective styling preference, no defect to fix"
        )
    return GateResult(True)


def _gate_specificity(candidate: Candidate, _: Transcript) -> GateResult:
    """Reject the unactionably vague.

    "Things feel slow in the afternoons", with no page, no timestamp and no
    repro, cannot be worked. A cosmetic defect is exempt: "the footer says
    BetterBrak" needs no repro steps because the report is already complete.
    """
    if candidate.observation.cosmetic_kind == "defect":
        return GateResult(True)
    if not candidate.observation.actionable_specificity:
        return GateResult(
            False,
            DropReason.UNACTIONABLE_VAGUE,
            "no page, no timing, no reproduction -- nothing an engineer can act on",
        )
    return GateResult(True)
