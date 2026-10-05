"""Tunable constants and closed vocabularies.

Everything a reviewer might want to argue with lives here rather than being
scattered through the pipeline. The closed vocabularies matter more than they
look: `COMPONENTS` is what makes an issue fingerprint stable across runs of a
non-deterministic model, and `DropReason` is what makes the drop distribution
aggregatable in the logs.
"""

from __future__ import annotations

import os
from enum import StrEnum
from pathlib import Path

# --- paths -------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
TRANSCRIPTS_DIR = ROOT / "transcripts"
DATA_DIR = ROOT / "data"
EXISTING_ISSUES = DATA_DIR / "existing_issues.json"
DEV_LABELS = DATA_DIR / "dev_labels.json"

STATE_DIR = Path(os.environ.get("BB_STATE_DIR", ROOT / "solution" / "_state"))
LEDGER_DB = STATE_DIR / "ledger.db"
LOGS_DIR = STATE_DIR / "logs"
REVIEW_DIR = STATE_DIR / "review"
DECISIONS_FILE = REVIEW_DIR / "decisions.json"

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

JIRA_PROJECT = "PROJ"

# --- closed vocabularies -----------------------------------------------------

# The component taxonomy is deliberately coarse and closed. A free-text
# component would drift between runs and poison the fingerprint; a closed set
# gives us a stable blocking key for both de-duplication and idempotency.
COMPONENTS: tuple[str, ...] = (
    "dashboard",
    "reporting",
    "exports",
    "search",
    "auth-sso",
    "admin-roles",
    "notifications-email",
    "webhooks",
    "api",
    "mobile-ios",
    "mobile-android",
    "calendar",
    "scheduling",
    "uploads",
    "billing",
    "integrations",
    "other",
)

ISSUE_TYPES: tuple[str, ...] = ("Bug", "Feature")
PRIORITIES: tuple[str, ...] = ("P0", "P1", "P2", "P3")
SEVERITIES: tuple[str, ...] = ("critical", "major", "minor", "trivial")


class Outcome(StrEnum):
    """Terminal disposition of a candidate issue."""

    FILE_NEW = "file-new"
    CORROBORATE = "corroborate"
    ALREADY_SHIPPED = "already-shipped"
    DROP = "drop"


class DropReason(StrEnum):
    """Closed enum so drop reasons aggregate into a distribution in the logs.

    If `HEARSAY` suddenly goes to zero across a run, the extractor changed
    behaviour even though nothing threw. That signal is the point.
    """

    # --- structural / integrity (deterministic, non-negotiable) ---
    INTERNAL_ONLY_CALL = "internal_only_call"
    NO_EXTERNAL_EVIDENCE = "no_external_evidence"
    EVIDENCE_NOT_FOUND = "evidence_not_found"
    INJECTION_QUARANTINED = "injection_quarantined"
    SCHEMA_INVALID = "schema_invalid"

    # --- editorial policy (deterministic rules over model observations) ---
    HEARSAY = "hearsay"
    RETRACTED_ON_CALL = "retracted_on_call"
    RESOLVED_ON_CALL = "resolved_on_call"
    CUSTOMER_SIDE_ROOT_CAUSE = "customer_side_root_cause"
    UNACTIONABLE_VAGUE = "unactionable_vague"
    COSMETIC_PREFERENCE = "cosmetic_preference"
    NOT_A_PRODUCT_ISSUE = "not_a_product_issue"
    CUSTOMER_DECLINED_FILING = "customer_declined_filing"

    # --- human gate ---
    REVIEWER_REJECTED = "reviewer_rejected"


# --- de-duplication thresholds -----------------------------------------------
#
# Structured comparison decides the clear cases deterministically and only the
# ambiguous band reaches the model. Scores are CONTAINMENT of the candidate's
# trigger/symptom in the tracked issue's text, not Jaccard -- see
# models.containment for why the symmetric metric is wrong here.
#
# Both must clear SAME for a duplicate. That conjunction is what keeps the
# engineered near-misses apart: call-010 (Azure AD, redirect loop after a
# password change) scores 0.20 trigger / 0.11 symptom against PROJ-064 (Okta,
# early session expiry), so it is ruled distinct without a model call.

DEDUP_SAME_THRESHOLD = 0.60  # >= on BOTH trigger and symptom -> same, no model
DEDUP_DISTINCT_THRESHOLD = 0.30  # < on EITHER -> distinct, no model
CLUSTER_PAIR_THRESHOLD = 0.30  # below this, two candidates aren't even compared

# Idempotency fallback: a non-deterministic model will word `trigger` and
# `symptom` slightly differently between runs, so an exact fingerprint hash
# alone would re-file the same issue. On a hash miss we look for a near-match
# inside the same (type, component) bucket before deciding it's new.
FINGERPRINT_NEAR_MATCH_THRESHOLD = 0.60

# --- observability health bands ----------------------------------------------
#
# A run that files nothing across 140 transcripts is exactly as alarming as one
# that files sixty. Both trip. These are the bands for "is this run normal".

HEALTH_MAX_ERROR_RATE = 0.05
HEALTH_MIN_CANDIDATES_PER_CALL = 0.30
HEALTH_MAX_CANDIDATES_PER_CALL = 6.0
HEALTH_MAX_FILE_RATE = 0.60  # fraction of processed calls producing a new ticket

# --- prompt versions ---------------------------------------------------------
#
# Bumped whenever a prompt changes. Part of the response cache key, so changing
# a prompt invalidates recorded responses instead of silently replaying stale
# ones, and part of every log line, so a behaviour change is attributable.

PROMPT_VERSIONS = {
    "extract": "extract-v1",
    "dedup": "dedup-v1",
    "cluster": "cluster-v1",
}

DEFAULT_MODEL = "claude-sonnet-5"
