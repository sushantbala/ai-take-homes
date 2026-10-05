"""De-duplication, in two layers.

  Layer A -- against `data/existing_issues.json`. Don't open a second ticket
             for a known problem; record the corroboration instead. A match
             against a *Shipped* issue is a third outcome entirely: the
             customer wants something that already exists, which is an
             enablement conversation, not a ticket.

  Layer B -- across calls within the run. Two accounts reporting one bug is
             one ticket with two sources, not two tickets.

Both layers use the same escalation: a deterministic structured comparison
decides the clear cases, and only the ambiguous middle band costs a model
call. That is not just a cost optimisation. It means most de-duplication
decisions carry an arithmetic explanation a reviewer can check, and it keeps
the model away from comparisons where it is likely to be lazily agreeable.

The hard cases in this corpus are near-misses engineered to look like
duplicates:

  * call-010 (Azure AD, redirect LOOP after a password change, needs a cookie
    clear) against PROJ-064 (Okta, session expires EARLY, self-recoverable).
    Same component. Different trigger, different symptom, different IdP.
  * call-006 (search stale ~10 min after a team rename, self-corrects) against
    PROJ-131 (newly INVITED members not searchable until the next day).

Folding either one in loses a real bug permanently, which is why `component`
agreement is treated as necessary and nowhere near sufficient, and why the
tie goes to DIFFERENT.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from . import config
from .config import Outcome
from .llm.prompts import build_cluster_prompt, build_dedup_prompt
from .llm.provider import LLMError, LLMProvider, LLMRequest
from .models import Candidate, NearMiss, containment, jaccard, normalize_tokens


@dataclass(frozen=True, slots=True)
class ExistingIssue:
    key: str
    type: str
    status: str
    summary: str
    description: str
    component: str
    reported_by_accounts: tuple[str, ...]
    tokens: frozenset[str]

    @property
    def is_shipped(self) -> bool:
        return self.status.lower() == "shipped"


# `existing_issues.json` has no component field, so one is derived here with
# ordered keyword rules. Deterministic and auditable -- a reviewer can read
# the table and predict the answer. A model call per tracked issue would be
# both slower and less inspectable for a classification this mechanical.
_COMPONENT_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("mobile-android", ("android",)),
    ("mobile-ios", ("ios", "iphone")),
    ("webhooks", ("webhook",)),
    ("auth-sso", ("sso", "saml", "okta", "idp", "login-history", "session expires", "federated")),
    # "calendar invite", not bare "invite" -- PROJ-131 ("members created via
    # invite") is a search-indexing bug and matched `calendar` on the loose
    # keyword, which would have mis-bucketed one of the near-miss traps.
    ("calendar", ("calendar", "outlook", "ics", "calendar invite", "rescheduled session")),
    ("uploads", ("upload", "attachment")),
    ("exports", ("export", "csv")),
    ("search", ("search", "searchable", "index")),
    # Before notifications-email: "Slack notifications" is an integration, and
    # the bare "notification" keyword below would otherwise swallow it.
    ("integrations", ("slack", "integration", "lms", "cornerstone", "siem")),
    ("reporting", ("scheduled report", "report", "pdf")),
    ("admin-roles", ("scim", "deprovision", "role", "permission", "provision")),
    ("notifications-email", ("email", "notification", "password-reset", "reset email")),
    ("billing", ("billing", "invoice", "payment")),
    ("api", ("api", "endpoint")),
    ("dashboard", ("dashboard", "summary card")),
    ("scheduling", ("session", "booking", "schedule")),
)


def infer_component(text: str) -> str:
    """Map free text onto the closed component vocabulary. First rule wins."""
    low = text.lower()
    for component, keywords in _COMPONENT_RULES:
        if any(keyword in low for keyword in keywords):
            return component
    return "other"


def load_existing_issues(path: Path | None = None) -> list[ExistingIssue]:
    raw = json.loads((path or config.EXISTING_ISSUES).read_text(encoding="utf-8"))
    return [
        ExistingIssue(
            key=item["key"],
            type=item["type"],
            status=item["status"],
            summary=item["summary"],
            description=item.get("description", ""),
            component=infer_component(f"{item['summary']} {item.get('description', '')}"),
            reported_by_accounts=tuple(item.get("reported_by_accounts", [])),
            tokens=normalize_tokens(f"{item['summary']} {item.get('description', '')}"),
        )
        for item in raw
    ]


# --- layer A: against tracked issues -----------------------------------------


@dataclass
class DedupDecision:
    outcome: Outcome
    target: str | None
    rationale: str
    near_misses: list[NearMiss]
    model_calls: int = 0


def dedup_against_existing(
    candidate: Candidate,
    issues: Iterable[ExistingIssue],
    provider: LLMProvider,
    *,
    on_model_error: str = "distinct",
) -> DedupDecision:
    """Decide whether `candidate` duplicates a tracked issue."""
    near_misses: list[NearMiss] = []
    model_calls = 0
    cand_tokens = candidate.identity_tokens()

    for issue in issues:
        # Different type is decided without a model call and without being
        # recorded as a near miss -- there is nothing interesting about a
        # Feature failing to match a Bug.
        if issue.type != candidate.type:
            continue

        # Same component means "same neighbourhood", and every neighbour is
        # compared and reported even when the token overlap is low. That is
        # deliberate: the reviewer's most useful line is "we checked PROJ-064
        # and here is the discriminator", and a pure-similarity shortlist
        # would silently skip exactly the near-misses worth showing.
        same_area = issue.component == candidate.component
        overlap = containment(cand_tokens, issue.tokens)
        if not same_area and overlap < config.DEDUP_DISTINCT_THRESHOLD:
            continue

        trigger_sim = containment(normalize_tokens(candidate.trigger), issue.tokens)
        symptom_sim = containment(normalize_tokens(candidate.symptom), issue.tokens)

        if trigger_sim >= config.DEDUP_SAME_THRESHOLD and symptom_sim >= config.DEDUP_SAME_THRESHOLD:
            return _match(
                candidate,
                issue,
                f"trigger ({trigger_sim:.2f}) and symptom ({symptom_sim:.2f}) both match",
                "structured",
            )

        if min(trigger_sim, symptom_sim) < config.DEDUP_DISTINCT_THRESHOLD:
            near_misses.append(
                NearMiss(
                    key=issue.key,
                    summary=issue.summary,
                    reason=(
                        f"same area but {'trigger' if trigger_sim < symptom_sim else 'symptom'} "
                        f"does not match (trigger {trigger_sim:.2f}, symptom {symptom_sim:.2f})"
                    ),
                    similarity=round(overlap, 3),
                    decided_by="structured",
                )
            )
            continue

        # Genuinely ambiguous. This is the band worth paying a model for.
        model_calls += 1
        try:
            verdict = _ask_same(provider, "dedup", *build_dedup_prompt(candidate, _as_dict(issue)),
                               cache_key=f"{candidate.call_id}:{candidate.compute_fingerprint()}:{issue.key}")
        except LLMError as exc:
            # Failing closed here would mean "call it a duplicate", which
            # silently buries a possibly-real bug. Failing open costs a human
            # ten seconds of merging. Open wins.
            near_misses.append(
                NearMiss(
                    key=issue.key,
                    summary=issue.summary,
                    reason=f"adjudication unavailable ({exc}); defaulted to distinct",
                    similarity=round(overlap, 3),
                    decided_by="model",
                )
            )
            continue

        if verdict.get("same") is True:
            return _match(
                candidate,
                issue,
                verdict.get("reason", "model adjudicated same"),
                "model",
                extra_near_misses=near_misses,
                model_calls=model_calls,
            )

        near_misses.append(
            NearMiss(
                key=issue.key,
                summary=issue.summary,
                reason=verdict.get("discriminator") or verdict.get("reason", "model adjudicated distinct"),
                similarity=round(overlap, 3),
                decided_by="model",
            )
        )

    return DedupDecision(
        outcome=Outcome.FILE_NEW,
        target=None,
        rationale="no tracked issue matches on both trigger and symptom",
        near_misses=near_misses,
        model_calls=model_calls,
    )


def _match(
    candidate: Candidate,
    issue: ExistingIssue,
    reason: str,
    decided_by: str,
    *,
    extra_near_misses: list[NearMiss] | None = None,
    model_calls: int = 0,
) -> DedupDecision:
    # A match against something already shipped is not a duplicate ticket --
    # the customer is asking for a feature that exists and nobody told them.
    outcome = Outcome.ALREADY_SHIPPED if issue.is_shipped else Outcome.CORROBORATE
    prefix = "already shipped as" if issue.is_shipped else "duplicate of"
    return DedupDecision(
        outcome=outcome,
        target=issue.key,
        rationale=f"{prefix} {issue.key} ({issue.status}): {reason} [decided by {decided_by}]",
        near_misses=extra_near_misses or [],
        model_calls=model_calls,
    )


def _as_dict(issue: ExistingIssue) -> dict[str, Any]:
    return {
        "key": issue.key,
        "type": issue.type,
        "status": issue.status,
        "summary": issue.summary,
        "description": issue.description,
    }


# --- layer B: clustering across calls ----------------------------------------


def cluster_candidates(
    candidates: list[Candidate], provider: LLMProvider
) -> tuple[dict[str, list[Candidate]], int]:
    """Group candidates from different calls that describe one defect.

    Returns (cluster_id -> members, model_calls).

    Order-independence matters here: the pipeline must produce the same
    clusters regardless of the order transcripts happened to be processed in,
    or a re-run would produce different tickets. Candidates are sorted before
    pairing and each cluster is identified by its lexicographically smallest
    member, so the result is a pure function of the set.
    """
    ordered = sorted(candidates, key=lambda c: (c.call_id, c.title))
    parent = {i: i for i in range(len(ordered))}

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[max(ri, rj)] = min(ri, rj)

    model_calls = 0
    for i in range(len(ordered)):
        for j in range(i + 1, len(ordered)):
            a, b = ordered[i], ordered[j]
            if a.call_id == b.call_id:
                continue  # two issues on one call are two issues
            if a.type != b.type or a.component != b.component:
                continue
            if find(i) == find(j):
                continue

            similarity = jaccard(a.identity_tokens(), b.identity_tokens())
            if similarity < config.CLUSTER_PAIR_THRESHOLD:
                continue
            if similarity >= config.DEDUP_SAME_THRESHOLD:
                union(i, j)
                continue

            model_calls += 1
            try:
                verdict = _ask_same(
                    provider, "cluster", *build_cluster_prompt(a, b),
                    # Sorted so the pair has one cache key regardless of which
                    # call was processed first.
                    cache_key=":".join(sorted([f"{a.call_id}|{a.compute_fingerprint()}",
                                               f"{b.call_id}|{b.compute_fingerprint()}"])),
                )
            except LLMError:
                continue  # fail open: two tickets, not one lost bug
            if verdict.get("same") is True:
                union(i, j)

    clusters: dict[str, list[Candidate]] = {}
    for i, candidate in enumerate(ordered):
        root = find(i)
        key = f"{ordered[root].call_id}:{ordered[root].compute_fingerprint()[:8]}"
        clusters.setdefault(key, []).append(candidate)
    for members in clusters.values():
        members.sort(key=lambda c: c.call_id)
    return clusters, model_calls


# --- shared ------------------------------------------------------------------


def _ask_same(
    provider: LLMProvider, task: str, system: str, user: str, *, cache_key: str
) -> dict[str, Any]:
    response = provider.complete(
        LLMRequest(
            task=task,
            cache_key=cache_key,
            system=system,
            user=user,
            prompt_version=config.PROMPT_VERSIONS[task],
        )
    )
    return response.data
