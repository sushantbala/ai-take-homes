"""Score the pipeline against `data/dev_labels.json`.

PASS/FAIL DEFINITION, stated so a second engineer can agree or disagree with
it before seeing any number:

    A call PASSES iff the multiset of actions the pipeline proposes for it
    exactly equals the multiset the labels expect -- same number of new
    tickets, same set of corroboration targets, same already-shipped
    routing. No partial credit. A call with two labelled issues where we get
    one right and miss the other fails.

Mapping the labels onto that, with the two judgement calls made explicit:

  * `file-new` and `file-new-low` both mean "one new ticket". The labels
    distinguish them to say the second should be low priority, which is
    checked by a trap rather than by the score.
  * `none` means "no ticket". `already-shipped` satisfies it, because routing
    a customer to a feature that already exists files nothing -- which is
    exactly what call-013's label describes.
  * `corroborate` with `target: "same ticket as call-006"` is cross-call
    clustering: the call must appear as a non-primary source on another
    call's ticket, not as a ticket of its own.

The score is set-matching, which is deliberate. Comparing a generated title
to a labelled summary needs a judge, and a judge is one more non-deterministic
component between the system and its own score. Matching on structure --
how many tickets, against which targets -- is checkable by hand.

What this costs: a call can pass with a correct action count and a badly
worded ticket. That gap is covered by the traps and by reading the review
digest, and it is named in WRITEUP.md rather than hidden.
"""

from __future__ import annotations

import json
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

from .. import config
from ..config import Outcome
from ..ledger import Ledger
from ..llm.provider import LLMProvider
from ..models import ProposedAction
from ..pipeline import run
from .traps import TrapResult, run_traps

DEV_CALLS = [f"call-{i:03d}" for i in range(1, 16)]


@dataclass(frozen=True, slots=True)
class Expected:
    new_tickets: int
    corroborate_targets: tuple[str, ...]
    cluster_corroborations: int


def load_expectations() -> dict[str, Expected]:
    raw = json.loads(config.DEV_LABELS.read_text(encoding="utf-8"))["labels"]
    out: dict[str, Expected] = {}
    for call_id, entries in raw.items():
        new_tickets = 0
        targets: list[str] = []
        cluster = 0
        for entry in entries:
            action = entry["action"]
            if action in ("file-new", "file-new-low"):
                new_tickets += 1
            elif action == "corroborate":
                target = entry.get("target", "")
                if target.startswith("PROJ-"):
                    targets.append(target)
                else:
                    # "same ticket as call-006": expect cluster membership.
                    cluster += 1
        out[call_id] = Expected(new_tickets, tuple(sorted(targets)), cluster)
    return out


@dataclass(frozen=True, slots=True)
class Actual:
    new_tickets: int
    corroborate_targets: tuple[str, ...]
    cluster_corroborations: int
    shipped: int


def observe(call_id: str, actions: list[ProposedAction]) -> Actual:
    """What the pipeline actually proposed for one call."""
    new_tickets = 0
    targets: list[str] = []
    cluster = 0
    shipped = 0

    for action in actions:
        call_ids = [s.call_id for s in action.sources]
        if call_id not in call_ids:
            continue
        is_primary = call_ids[0] == call_id

        if action.outcome is Outcome.FILE_NEW:
            if is_primary:
                new_tickets += 1
            else:
                # Attached to someone else's ticket as a second source: that
                # is corroboration via clustering, not a ticket of our own.
                cluster += 1
        elif action.outcome is Outcome.CORROBORATE:
            targets.append(action.dedup_target or "?")
        elif action.outcome is Outcome.ALREADY_SHIPPED:
            shipped += 1

    return Actual(new_tickets, tuple(sorted(targets)), cluster, shipped)


@dataclass
class CaseResult:
    call_id: str
    passed: bool
    expected: Expected
    actual: Actual
    detail: str


@dataclass
class EvalReport:
    cases: list[CaseResult] = field(default_factory=list)
    traps: list[TrapResult] = field(default_factory=list)
    repeats: int = 1
    pass_rates: dict[str, float] = field(default_factory=dict)
    trap_pass_rates: dict[str, float] = field(default_factory=dict)
    action_set_stability: float = 1.0

    @property
    def passed_count(self) -> int:
        return sum(c.passed for c in self.cases)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.cases) and all(t.passed for t in self.traps)

    @property
    def stable_pass(self) -> int:
        return sum(1 for r in self.pass_rates.values() if r == 1.0)

    @property
    def flaky(self) -> int:
        return sum(1 for r in self.pass_rates.values() if 0.0 < r < 1.0)

    @property
    def stable_fail(self) -> int:
        return sum(1 for r in self.pass_rates.values() if r == 0.0)

    def as_dict(self) -> dict[str, Any]:
        return {
            "repeats": self.repeats,
            "cases_total": len(self.cases),
            "cases_passed": self.passed_count,
            "stable_pass": self.stable_pass,
            "flaky": self.flaky,
            "stable_fail": self.stable_fail,
            "action_set_stability": round(self.action_set_stability, 4),
            "traps_passed": sum(t.passed for t in self.traps),
            "traps_total": len(self.traps),
            "pass_rates": self.pass_rates,
            "trap_pass_rates": self.trap_pass_rates,
            "cases": [
                {
                    "call_id": c.call_id,
                    "passed": c.passed,
                    "detail": c.detail,
                    "expected": {
                        "new_tickets": c.expected.new_tickets,
                        "corroborate": list(c.expected.corroborate_targets),
                        "cluster": c.expected.cluster_corroborations,
                    },
                    "actual": {
                        "new_tickets": c.actual.new_tickets,
                        "corroborate": list(c.actual.corroborate_targets),
                        "cluster": c.actual.cluster_corroborations,
                        "already_shipped": c.actual.shipped,
                    },
                }
                for c in self.cases
            ],
            "traps": [
                {"name": t.name, "passed": t.passed, "severity": t.severity, "detail": t.detail}
                for t in self.traps
            ],
        }

    def render(self) -> str:
        lines = ["", "DEV-SET EVAL  (calls 001-015)", "=" * 72, ""]
        lines.append(f"{'call':<10} {'result':<7} expected -> actual")
        lines.append("-" * 72)
        for case in self.cases:
            mark = "PASS" if case.passed else "FAIL"
            lines.append(f"{case.call_id:<10} {mark:<7} {case.detail}")

        lines += ["", f"score: {self.passed_count}/{len(self.cases)} calls "
                      f"({self.passed_count / max(len(self.cases), 1):.0%})", ""]

        lines += ["TRAPS  (deterministic, no judge)", "-" * 72]
        for trap in self.traps:
            mark = "PASS" if trap.passed else f"FAIL [{trap.severity.upper()}]"
            lines.append(f"  {mark:<16} {trap.name}")
            lines.append(f"  {'':<16} {trap.detail}")
        lines.append("")

        if self.repeats > 1:
            lines += [f"RELIABILITY  ({self.repeats} repeated runs)", "-" * 72]
            lines.append(f"  stable pass (every run)   {self.stable_pass}/{len(self.pass_rates)}")
            lines.append(f"  flaky (some runs)         {self.flaky}/{len(self.pass_rates)}")
            lines.append(f"  stable fail (never)       {self.stable_fail}/{len(self.pass_rates)}")
            lines.append(f"  action-set stability      {self.action_set_stability:.1%} mean Jaccard")
            flaky = [c for c, r in sorted(self.pass_rates.items()) if 0.0 < r < 1.0]
            if flaky:
                lines.append(f"  FLAKY CASES: {', '.join(flaky)}")
            lines.append("")
            lines.append("  Headline number is stable-pass, not the single-run score: a case that")
            lines.append("  passes 3 times in 5 is not passing, it is a coin flip with good PR.")
        else:
            lines.append("Single run. Use --runs 5 for the reliability breakdown.")
        lines.append("")
        return "\n".join(lines)


def _score_once(provider: LLMProvider, run_index: int) -> tuple[list[CaseResult], list[TrapResult], frozenset[str]]:
    """One full pipeline run over the dev set, scored.

    Each repeat gets a throwaway ledger. Sharing one would make run 2 suppress
    everything run 1 already proposed -- correct idempotency behaviour, and
    completely wrong for measuring per-run agreement. Idempotency is tested
    separately, in tests/.
    """
    import tempfile
    from pathlib import Path

    expectations = load_expectations()
    with tempfile.TemporaryDirectory() as tmp:
        with Ledger(Path(tmp) / "eval.db") as ledger:
            result = run(provider, ledger, only=DEV_CALLS, force=True,
                         run_id=f"eval-{run_index}-{id(provider) % 10000}")

    cases: list[CaseResult] = []
    for call_id in DEV_CALLS:
        expected = expectations.get(call_id, Expected(0, (), 0))
        actual = observe(call_id, result.actions)
        passed = (
            actual.new_tickets == expected.new_tickets
            and actual.corroborate_targets == expected.corroborate_targets
            and actual.cluster_corroborations == expected.cluster_corroborations
        )
        detail = (
            f"{expected.new_tickets} new + {list(expected.corroborate_targets)}"
            f"{f' + {expected.cluster_corroborations} cluster' if expected.cluster_corroborations else ''}"
            f"  ->  {actual.new_tickets} new + {list(actual.corroborate_targets)}"
            f"{f' + {actual.cluster_corroborations} cluster' if actual.cluster_corroborations else ''}"
            f"{f' + {actual.shipped} shipped' if actual.shipped else ''}"
        )
        cases.append(CaseResult(call_id, passed, expected, actual, detail))

    traps = run_traps(result.actions)
    signature = frozenset(f"{a.outcome}:{a.title}" for a in result.actions)
    return cases, traps, signature


def run_eval(provider: LLMProvider, *, repeats: int = 1) -> EvalReport:
    """Run the eval `repeats` times and report per-case pass RATES.

    The brief asks how reliability is measured across repeated runs rather
    than from one green result. With a replay provider the answer is trivially
    100% because replay is deterministic by construction -- that is the point
    of replay, and it is also why the number means nothing about the model.
    Against a live provider this is the measurement that matters, and the
    machinery is identical.
    """
    per_case: dict[str, list[bool]] = defaultdict(list)
    per_trap: dict[str, list[bool]] = defaultdict(list)
    signatures: list[frozenset[str]] = []
    last_cases: list[CaseResult] = []
    last_traps: list[TrapResult] = []

    for i in range(repeats):
        cases, traps, signature = _score_once(provider, i)
        for case in cases:
            per_case[case.call_id].append(case.passed)
        for trap in traps:
            per_trap[trap.name].append(trap.passed)
        signatures.append(signature)
        last_cases, last_traps = cases, traps

    # Mean pairwise Jaccard over the proposed action sets. 1.0 means every run
    # produced identical output; anything lower quantifies the drift a
    # non-deterministic model introduces.
    stability = 1.0
    if len(signatures) > 1:
        pairs = [
            len(a & b) / len(a | b) if (a | b) else 1.0
            for i, a in enumerate(signatures)
            for b in signatures[i + 1:]
        ]
        stability = statistics.fmean(pairs) if pairs else 1.0

    return EvalReport(
        cases=last_cases,
        traps=last_traps,
        repeats=repeats,
        pass_rates={k: sum(v) / len(v) for k, v in sorted(per_case.items())},
        trap_pass_rates={k: sum(v) / len(v) for k, v in sorted(per_trap.items())},
        action_set_stability=stability,
    )
