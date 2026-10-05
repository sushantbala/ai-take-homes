"""Data model shared across the pipeline.

The important shape here is `Candidate`. It separates two things that are easy
to conflate:

  * `Observation` -- facts about the transcript that require reading
    comprehension ("the customer retracted this later in the call"). The model
    fills these in.
  * The disposition -- whether those facts mean we file, merge, or drop. Code
    decides that, in `gates.py`, by reading the observation.

Keeping the two apart is what makes the policy reviewable in a diff instead of
buried in a prompt, and it's why the gate layer is testable with no model at
all.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from typing import Literal

from .config import DropReason, Outcome

# --- transcript --------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Turn:
    """One line of dialogue. `idx` is 1-based and stable: it is the citation key."""

    idx: int
    line_no: int  # line in the source file, for clickable provenance
    side: Literal["EXTERNAL", "INTERNAL"]
    speaker: str
    text: str

    @property
    def is_external(self) -> bool:
        return self.side == "EXTERNAL"


@dataclass(frozen=True, slots=True)
class Participant:
    side: Literal["EXTERNAL", "INTERNAL"]
    name: str
    role: str
    org: str | None


@dataclass(slots=True)
class Transcript:
    call_id: str
    title: str
    date: str
    path: str
    content_hash: str
    participants: list[Participant]
    turns: list[Turn]
    # Turn indices carrying instructions aimed at an automated reader, split by
    # intent. Detected deterministically at ingest. `injection_turns` can cause
    # evidence to be refused; `suppression_turns` never reduces an action and
    # only raises a review flag. See the comment block in ingest.py.
    injection_turns: frozenset[int] = frozenset()
    suppression_turns: frozenset[int] = frozenset()

    @property
    def has_external(self) -> bool:
        return any(t.is_external for t in self.turns)

    @property
    def account(self) -> str:
        for p in self.participants:
            if p.side == "EXTERNAL" and p.org:
                return p.org
        return "unknown"

    def turn(self, idx: int) -> Turn | None:
        if 1 <= idx <= len(self.turns):
            return self.turns[idx - 1]
        return None


# --- what the model is asked to observe --------------------------------------


@dataclass(slots=True)
class Observation:
    """Reading-comprehension judgements about one candidate issue.

    Every field is a fact about what was said on the call, not a decision about
    what to do with it. The model is never asked "should we file this?" -- only
    "did the customer take it back?", "did they experience it themselves?".
    Those are questions a second engineer could check against the transcript
    and agree or disagree with, which is exactly what makes the eval auditable.
    """

    raised_by_external: bool
    firsthand: bool  # the speaker experienced it, vs. relaying hearsay
    retracted_on_call: bool  # speaker withdrew it ("don't file that")
    resolved_on_call: bool  # turned out to be user error, fixed live
    customer_side_root_cause: bool  # their IdP, their VPN, their gateway
    actionable_specificity: bool  # enough detail to hand an engineer
    not_a_product_issue: bool  # competitor intel, account/CSM request
    customer_declined_filing: bool  # explicitly asked us not to file

    # Cosmetic splits two ways and the distinction decides file-vs-drop:
    #   "preference" -> subjective taste (font size, header colour) -> drop
    #   "defect"     -> objectively wrong (misspelled brand) -> file, lowest
    cosmetic_kind: Literal["preference", "defect"] | None = None

    # Impact factors feeding the deterministic priority matrix.
    data_correctness_impact: bool = False
    blocks_workflow: bool = False
    compliance_or_revenue_driver: bool = False
    has_workaround: bool = False
    users_affected: Literal["one", "team", "org", "unknown"] = "unknown"

    # Recorded for the human reviewer. Deliberately NOT an input to priority:
    # see assemble.compute_priority. A customer calling a footer typo a P0
    # does not make it one.
    customer_urgency: Literal["low", "medium", "high"] = "medium"


@dataclass(slots=True)
class Candidate:
    """A possible product issue extracted from one call, before any gating."""

    call_id: str
    title: str
    type: Literal["Bug", "Feature"]
    problem: str  # model prose: what is happening, 1-3 sentences
    evidence_turns: list[int]  # citations INTO the transcript, never quoted text

    # The structured discriminators. De-duplication compares these rather than
    # comparing titles, because titles agree far too easily.
    component: str
    trigger: str  # what sets it off
    symptom: str  # what the user sees
    scope: str  # who/what is affected
    workaround: str | None

    observation: Observation

    # --- filled in downstream ---
    snippets: list[Snippet] = field(default_factory=list)
    outcome: Outcome | None = None
    drop_reason: DropReason | None = None
    drop_detail: str = ""
    dedup_target: str | None = None  # existing issue key, when corroborating
    dedup_rationale: str = ""
    near_misses: list[NearMiss] = field(default_factory=list)
    priority: str = "P3"
    severity: str = "minor"
    priority_rationale: str = ""
    fingerprint: str = ""
    cluster_id: str = ""

    def identity_tokens(self) -> frozenset[str]:
        """Token set used for similarity. Order-insensitive by construction."""
        return normalize_tokens(f"{self.trigger} {self.symptom}")

    def compute_fingerprint(self) -> str:
        """Stable identity for idempotency.

        Deliberately built from the closed-vocabulary `component` plus a sorted
        token set, never from model prose or a random id -- prose drifts
        between runs and would re-file the same issue every night.
        """
        tokens = " ".join(sorted(self.identity_tokens()))
        basis = f"{self.type}|{self.component}|{tokens}"
        return hashlib.sha256(basis.encode()).hexdigest()[:16]


@dataclass(frozen=True, slots=True)
class Snippet:
    """Verbatim transcript text, resolved by code from a cited turn index.

    The model supplies `turn_idx`; this text is read out of the file. A
    hallucinated citation fails the lookup in `gates.py` instead of quietly
    becoming the body of a Jira ticket.
    """

    turn_idx: int
    line_no: int
    speaker: str
    side: str
    text: str


@dataclass(frozen=True, slots=True)
class NearMiss:
    """An existing issue we compared against and rejected.

    Surfaced to the reviewer. "We considered PROJ-064 and here is why this
    isn't it" is the single most useful thing on a de-duplication review card.
    """

    key: str
    summary: str
    reason: str
    similarity: float
    decided_by: Literal["structured", "model"]


@dataclass(slots=True)
class ProposedAction:
    """One reviewable unit of work. The unit is the issue, not the call.

    A single action can carry sources from several calls (one bug reported by
    two accounts collapses into one ticket with two corroborating sources).
    """

    fingerprint: str
    outcome: Outcome
    type: str
    title: str
    component: str
    priority: str
    severity: str
    priority_rationale: str
    body: str
    sources: list[Source]
    dedup_target: str | None = None
    dedup_rationale: str = ""
    near_misses: list[NearMiss] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)

    @property
    def primary_call(self) -> str:
        return self.sources[0].call_id if self.sources else "unknown"


@dataclass(frozen=True, slots=True)
class Source:
    call_id: str
    account: str
    date: str
    reporter: str
    transcript_path: str
    snippets: tuple[Snippet, ...]


# --- helpers -----------------------------------------------------------------

_STOPWORDS = frozenset(
    """
    a an the and or but if then than that this these those is are was were be been
    being of in on at to for with from by as it its it's into over under about
    some any all not no nor so such only own same too very can will just don
    when while after before during our your their my his her we you they i he she
    there here what which who whom how why does do did doing done get gets got
    """.split()
)

_WORD_RE = re.compile(r"[a-z0-9]+")

# Crude suffix stripping, applied identically to both sides of every
# comparison. Without it "member" and "members" are different tokens and
# de-duplication silently under-matches on ordinary English plurals.
_SUFFIXES = ("ings", "ing", "edly", "ed", "es", "s")


def _stem(word: str) -> str:
    for suffix in _SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            return word[: -len(suffix)]
    return word


def normalize_tokens(text: str) -> frozenset[str]:
    """Lowercase, strip punctuation and stopwords, stem, return a set.

    Set semantics make similarity insensitive to the model rewording the same
    observation in a different order between runs.
    """
    words = _WORD_RE.findall(text.lower())
    return frozenset(_stem(w) for w in words if w not in _STOPWORDS and len(w) > 2)


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    """Symmetric similarity. Use when both sides are comparable in size."""
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def containment(needle: frozenset[str], haystack: frozenset[str]) -> float:
    """Fraction of `needle` present in `haystack`.

    The right metric when the two sides differ wildly in length, which is
    exactly the de-duplication case: a four-word `trigger` compared against a
    forty-word issue description scores near zero under Jaccard purely because
    of the size gap, even when every single trigger word is present. That
    asymmetry would make structured de-duplication useless and push every
    comparison to the model.
    """
    if not needle:
        return 0.0
    return len(needle & haystack) / len(needle)


def to_jsonable(obj) -> object:
    """Dataclass -> plain JSON types.

    `StrEnum` members are already `str` subclasses so they serialise as-is;
    the cases that actually need handling are nested dataclasses and the
    frozensets, which `json` refuses.
    """
    if hasattr(obj, "__dataclass_fields__"):
        return {k: to_jsonable(v) for k, v in asdict(obj).items()}
    if isinstance(obj, (set, frozenset)):
        return sorted(to_jsonable(v) for v in obj)
    if isinstance(obj, (tuple, list)):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, dict):
        return {k: to_jsonable(v) for k, v in obj.items()}
    return obj
