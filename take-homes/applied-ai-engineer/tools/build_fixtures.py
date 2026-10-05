"""Author the replay fixtures for the extraction stage.

READ THIS BEFORE TRUSTING ANY NUMBER PRODUCED WITH THESE FIXTURES.

These are hand-authored stand-ins for what a model would return, written by
reading the transcripts. They exist so the deterministic two-thirds of the
pipeline -- gates, policy, de-duplication, clustering, priority, idempotency,
the review gate -- can be exercised and measured end to end without an API
key.

They are NOT a substitute for the model, and a dev-set score obtained with
them does not measure extraction quality. It measures the layers downstream
of extraction, holding extraction fixed at "competent". The honest reading is
in WRITEUP.md.

Two rules were followed while authoring, both aimed at keeping the exercise
from becoming circular:

  1. Written from the TRANSCRIPTS, not from `dev_labels.json`. The observation
     fields record what the customer said; whether that becomes a ticket is
     the policy layer's call, and the policy layer is what is being tested.

  2. The NOISE IS INCLUDED. Every retracted gripe, cosmetic nitpick, piece of
     hearsay and injection attempt is present as a candidate with its flags
     set honestly. A fixture containing only the real issues would make the
     gate layer look perfect by never handing it anything to reject, which
     would prove nothing at all.

Regenerate with:  python -m tools.build_fixtures
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from solution import config  # noqa: E402
from solution.ingest import parse_transcript  # noqa: E402


def obs(**overrides) -> dict:
    """Observation with conservative defaults; override only what applies."""
    base = {
        "raised_by_external": True,
        "firsthand": True,
        "retracted_on_call": False,
        "resolved_on_call": False,
        "customer_side_root_cause": False,
        "actionable_specificity": True,
        "not_a_product_issue": False,
        "customer_declined_filing": False,
        "cosmetic_kind": None,
        "data_correctness_impact": False,
        "blocks_workflow": False,
        "compliance_or_revenue_driver": False,
        "has_workaround": False,
        "users_affected": "unknown",
        "customer_urgency": "medium",
    }
    base.update(overrides)
    return base


# Keyed by call id. Each entry is the full `{"candidates": [...]}` response.
CANDIDATES: dict[str, list[dict]] = {
    # ---------------------------------------------------------------- 001 ---
    "call-001": [
        {
            "title": "Usage dashboard 'active members' card contradicts its own per-team breakdown",
            "type": "Bug",
            "problem": "The headline 'active members' summary card on the usage dashboard reads 280 "
                       "while the per-team breakdown directly beneath it totals 412, which matches the "
                       "customer's admin panel. Same page, same load. Started about a week and a half ago.",
            "evidence_turns": [26, 28, 32],
            "component": "dashboard",
            "trigger": "opening the usage dashboard and comparing the summary card to the per-team breakdown",
            "symptom": "the active members summary card shows 280 while the per-team breakdown below totals 412",
            "scope": "every admin viewing the usage dashboard for this workspace",
            "workaround": "add up the per-team rows manually",
            "observation": obs(data_correctness_impact=True, users_affected="org", customer_urgency="high"),
        },
        {
            # Already tracked AND the customer says not to re-report. Present so
            # the pipeline has to decide, rather than being handed a clean set.
            "title": "Scheduled report timestamps off by a few hours",
            "type": "Bug",
            "problem": "Customer still sees report timestamps a few hours off, but states this is the "
                       "known timezone issue, that they are already attached to it, and that there is no "
                       "need to re-report.",
            "evidence_turns": [40, 42],
            "component": "reporting",
            "trigger": "scheduled report delivery",
            "symptom": "report timestamps display several hours off from the workspace timezone",
            "scope": "scheduled reports for this workspace",
            "workaround": None,
            "observation": obs(customer_declined_filing=True, data_correctness_impact=True),
        },
        {
            "title": "Dashboard team labels are too small to read",
            "type": "Feature",
            "problem": "Customer asks whether the dashboard font could be larger, then retracts it as "
                       "a personal eyesight issue and explicitly tells us not to file it.",
            "evidence_turns": [46],
            "component": "dashboard",
            "trigger": "viewing the dashboard on a laptop screen",
            "symptom": "small grey team labels are hard to read",
            "scope": "one user's preference",
            "workaround": "browser zoom to 110%",
            "observation": obs(cosmetic_kind="preference", retracted_on_call=True,
                               customer_declined_filing=True, actionable_specificity=False,
                               users_affected="one", customer_urgency="low"),
        },
    ],
    # ---------------------------------------------------------------- 002 ---
    "call-002": [
        {
            "title": "Members missing from the team dashboard",
            "type": "Bug",
            "problem": "Roughly thirty members appeared to be missing from the team dashboard. Diagnosed "
                       "live on the call as the sticky 'Active in last 7 days' filter chip left applied "
                       "from a previous session. All 214 members present once cleared.",
            "evidence_turns": [16, 24, 28],
            "component": "dashboard",
            "trigger": "the 'active in last 7 days' filter chip persisting from a previous session",
            "symptom": "members appear to be missing from the team dashboard",
            "scope": "one admin's view",
            "workaround": "clear the filter chip",
            "observation": obs(resolved_on_call=True, users_affected="one"),
        },
        {
            "title": "New purple header is too loud",
            "type": "Feature",
            "problem": "Customer finds the new purple header visually loud. States explicitly that "
                       "nothing is broken and he is not asking for anything.",
            "evidence_turns": [30, 32],
            "component": "dashboard",
            "trigger": "the new header colour",
            "symptom": "the purple header draws the eye and is visually loud",
            "scope": "one user's taste",
            "workaround": None,
            "observation": obs(cosmetic_kind="preference", actionable_specificity=False,
                               users_affected="one", customer_urgency="low"),
        },
        {
            "title": "Dashboard sometimes feels slower in the afternoons",
            "type": "Bug",
            "problem": "Customer reports a vague sense of afternoon slowness but cannot name a page, "
                       "a time, or a day, and says it may be his own network or laptop.",
            "evidence_turns": [34, 36],
            "component": "dashboard",
            "trigger": "unknown; possibly afternoons",
            "symptom": "the dashboard occasionally takes a beat longer to paint",
            "scope": "unclear",
            "workaround": None,
            "observation": obs(actionable_specificity=False, users_affected="one", customer_urgency="low"),
        },
    ],
    # ---------------------------------------------------------------- 003 ---
    "call-003": [
        {
            "title": "Assign roles automatically from SAML group membership on every login",
            "type": "Feature",
            "problem": "Every SSO user lands as a basic member and must be promoted by hand, which does "
                       "not scale to 400 users and fails the customer's access-review control. They need "
                       "IdP group to role mapping evaluated on every login, not only at first provision, "
                       "so group changes propagate automatically.",
            "evidence_turns": [36, 38, 40],
            "component": "admin-roles",
            "trigger": "a federated user logging in via SAML",
            "symptom": "every user is provisioned as a basic member and an admin must promote them by hand",
            "scope": "all 400 users at full rollout for a regulated financial customer",
            "workaround": "manual promotion by an admin, one user at a time",
            "observation": obs(blocks_workflow=True, compliance_or_revenue_driver=True,
                               users_affected="org", customer_urgency="high"),
        },
        {
            "title": "SAML assertions rejected as expired for Chicago users",
            "type": "Bug",
            "problem": "About twenty users could not log in on Friday; assertions were rejected as "
                       "expired. Root cause was the customer's own IdP NTP misconfiguration after a "
                       "patch window. Customer confirms our behaviour was correct and the issue is "
                       "resolved on their side.",
            "evidence_turns": [16, 18, 24],
            "component": "auth-sso",
            "trigger": "customer IdP clock drift of ninety seconds after a patch window",
            "symptom": "SAML assertions rejected as expired at login",
            "scope": "about twenty users for one morning",
            "workaround": None,
            "observation": obs(customer_side_root_cause=True, resolved_on_call=True, users_affected="team"),
        },
        {
            "title": "Data exports reportedly drop rows on large pulls",
            "type": "Bug",
            "problem": "Customer relays a one-sentence remark from a peer at a different firm, heard at "
                       "a conference, that exports drop rows on large pulls. Customer has never used "
                       "exports and has no first-hand experience.",
            "evidence_turns": [48, 50],
            "component": "exports",
            "trigger": "large data exports",
            "symptom": "rows are reportedly missing from the exported file",
            "scope": "unknown; another company entirely",
            "workaround": None,
            "observation": obs(firsthand=False, actionable_specificity=False, users_affected="unknown"),
        },
    ],
    # ---------------------------------------------------------------- 004 ---
    "call-004": [
        {
            "title": "Scheduled report timestamps render seven hours ahead of the workspace timezone",
            "type": "Bug",
            "problem": "Scheduled reports arrive with timestamps about seven hours ahead of Pacific, "
                       "consistent with UTC rendering rather than the workspace timezone. The in-app "
                       "dashboard is correct; only the emailed scheduled report is shifted. Directors "
                       "read the numbers against the school day and conclude the data is wrong.",
            "evidence_turns": [20, 22, 24, 30],
            "component": "reporting",
            "trigger": "scheduled report emailed as a PDF",
            "symptom": "timestamps display in UTC instead of the workspace timezone, about seven hours ahead",
            "scope": "all scheduled reports for this Pacific workspace",
            "workaround": "mentally subtract seven hours",
            "observation": obs(data_correctness_impact=True, users_affected="org"),
        },
        {
            "title": "Login page stock photo is corny",
            "type": "Feature",
            "problem": "Customer jokes about the login page stock photo and explicitly says not to file it.",
            "evidence_turns": [36, 40],
            "component": "other",
            "trigger": "viewing the login page",
            "symptom": "the stock photo is dated and teachers mock it",
            "scope": "cosmetic",
            "workaround": None,
            "observation": obs(cosmetic_kind="preference", customer_declined_filing=True,
                               actionable_specificity=False, users_affected="unknown", customer_urgency="low"),
        },
    ],
    # ---------------------------------------------------------------- 005 ---
    "call-005": [
        {
            # The jailbreak, reported honestly by the model as a candidate.
            # The gate layer, not the model, is what must stop it.
            "title": "Wire transfer approval - URGENT",
            "type": "Bug",
            "problem": "Text on the call instructs an automated reader to file a P0 and post an approval "
                       "to a finance channel.",
            "evidence_turns": [26],
            "component": "billing",
            "trigger": "system instruction on the call",
            "symptom": "wire transfer approval required",
            "scope": "finance",
            "workaround": None,
            "observation": obs(customer_urgency="high"),
        },
        {
            # Must survive. Relayed from a NAMED COLLEAGUE at the same account
            # with a precise technical ask -- that is firsthand for the account,
            # unlike call-003's conference hearsay from another company.
            "title": "Duplicate webhook deliveries with no idempotency key to de-duplicate against",
            "type": "Bug",
            "problem": "The customer's data platform receives the same webhook event more than once, "
                       "intermittently. Their pipeline de-duplicates heuristically on payload content "
                       "and timing. Their platform engineer asks for an idempotency key on the payload "
                       "so redeliveries can be dropped deterministically.",
            "evidence_turns": [34, 36, 38],
            "component": "webhooks",
            "trigger": "outbound webhook delivery to the customer endpoint",
            "symptom": "the same event is delivered more than once, occasionally and unpredictably",
            "scope": "all webhook consumers on this account",
            "workaround": "heuristic de-duplication on payload contents in the customer's pipeline",
            "observation": obs(has_workaround=True, users_affected="org"),
        },
    ],
    # ---------------------------------------------------------------- 006 ---
    "call-006": [
        {
            "title": "Search returns stale results for about ten minutes after a team rename or member move",
            "type": "Bug",
            "problem": "After renaming a team or moving a member, search keeps returning the old state "
                       "for roughly ten minutes before self-correcting. Searching the new team name "
                       "returns nothing; searching a moved person shows the old team. Reproducible on "
                       "demand, confirmed three times.",
            "evidence_turns": [20, 22, 24, 30],
            "component": "search",
            "trigger": "renaming a team or moving a member between teams",
            "symptom": "search returns the old team name or empty results for about ten minutes then self corrects",
            "scope": "all admins and managers searching during a period of edits",
            "workaround": "wait ten minutes and search again",
            "observation": obs(blocks_workflow=True, has_workaround=True, users_affected="org"),
        },
        {
            "title": "Mobile team names truncate aggressively with an ellipsis",
            "type": "Feature",
            "problem": "Long team names truncate on mobile so two similarly named teams are hard to "
                       "tell apart. Customer says it is purely cosmetic and is not asking for anything.",
            "evidence_turns": [44, 46],
            "component": "other",
            "trigger": "viewing long team names in the mobile app",
            "symptom": "team names truncate with an ellipsis and become ambiguous",
            "scope": "mobile users with long team names",
            "workaround": "view on desktop",
            "observation": obs(cosmetic_kind="preference", actionable_specificity=False,
                               users_affected="team", customer_urgency="low"),
        },
    ],
    # ---------------------------------------------------------------- 008 ---
    "call-008": [
        {
            "title": "Android app crashes on launch after the latest update",
            "type": "Bug",
            "problem": "Warehouse staff on Android who took the latest app update cannot open the app: "
                       "it shows the splash screen then returns to the home screen, never reaching "
                       "login. Android users who have not updated are fine and iOS is unaffected. About "
                       "a dozen reported, likely triple that given this population rarely reports.",
            "evidence_turns": [14, 16, 20, 22],
            "component": "mobile-android",
            "trigger": "launching the Android app after taking the latest update",
            "symptom": "the app crashes on launch at the splash screen and never reaches login",
            "scope": "Android users who have updated; iOS unaffected",
            "workaround": "do not update, or reinstall the previous version",
            "observation": obs(blocks_workflow=True, users_affected="org", customer_urgency="high"),
        },
        {
            # Cosmetic DEFECT, not preference: objectively wrong, so it files --
            # but at the bottom, despite being framed as "a P0 brand catastrophe".
            "title": "Outbound email footer misspells the company name as 'BetterBrak'",
            "type": "Bug",
            "problem": "Confirmation emails carry 'BetterBrak' in the footer instead of BetterBark. "
                       "Present on every confirmation email. The customer's comms director called it a "
                       "P0 brand catastrophe; nothing is functionally broken.",
            "evidence_turns": [44, 46, 48],
            "component": "notifications-email",
            "trigger": "any outbound confirmation email",
            "symptom": "the footer misspells the company name as BetterBrak",
            "scope": "every confirmation email sent to every customer",
            "workaround": None,
            "observation": obs(cosmetic_kind="defect", users_affected="org", customer_urgency="high"),
        },
    ],
    # ---------------------------------------------------------------- 009 ---
    "call-009": [
        {
            "title": "Uploads time out and fail",
            "type": "Bug",
            "problem": "Profile photo and document uploads failed reliably for about a week and a half. "
                       "Root cause was the customer's temporary VPN concentrator during an office move. "
                       "Resolved once they moved to the permanent circuit.",
            "evidence_turns": [18, 22, 24],
            "component": "uploads",
            "trigger": "uploading over the customer's temporary VPN during an office move",
            "symptom": "uploads spin and time out without attaching",
            "scope": "that office during the move",
            "workaround": "upload off the VPN",
            "observation": obs(customer_side_root_cause=True, resolved_on_call=True, users_affected="team"),
        },
        {
            "title": "Pages sometimes feel slow in the afternoons",
            "type": "Bug",
            "problem": "Customer reports a vague sense of afternoon slowness, cannot name a page or a "
                       "time, and says it may be their own wifi or four-year-old laptop.",
            "evidence_turns": [32, 34],
            "component": "other",
            "trigger": "unknown",
            "symptom": "pages take a beat longer to load, inconsistently",
            "scope": "one user",
            "workaround": None,
            "observation": obs(actionable_specificity=False, users_affected="one", customer_urgency="low"),
        },
    ],
    # ---------------------------------------------------------------- 010 ---
    "call-010": [
        {
            "title": "Audit-log export API for automated nightly SIEM ingestion",
            "type": "Feature",
            "problem": "The audit log is available only as a UI view. The customer's SOC team needs a "
                       "filterable, paginated, machine-readable API endpoint so a nightly unattended job "
                       "can pull audit events into their SIEM. A human clicking export does not satisfy "
                       "the SOC 2 continuous-monitoring control.",
            "evidence_turns": [14, 16],
            "component": "api",
            "trigger": "attempting automated nightly retrieval of audit events",
            "symptom": "no machine-readable paginated audit-log endpoint exists, only a UI view",
            "scope": "the customer's SOC team and SOC 2 continuous-monitoring control",
            "workaround": "a human clicking export CSV weekly, which fails the control",
            "observation": obs(compliance_or_revenue_driver=True, blocks_workflow=True,
                               users_affected="org", customer_urgency="high"),
        },
        {
            # The near-miss trap. Must NOT fold into PROJ-064.
            "title": "Azure AD users hit an infinite redirect loop after a password change",
            "type": "Bug",
            "problem": "After a user changes their network password, opening the app bounces them to "
                       "the IdP, which authenticates them successfully, returns them, and the app "
                       "immediately bounces them back again, indefinitely. They never reach the app at "
                       "all. Clearing cookies for the domain is the only escape. Five of forty pilot "
                       "users so far, limited only by staggered rotation dates; at full rollout a "
                       "ninety-day policy puts all four hundred users through this every quarter.",
            "evidence_turns": [24, 28, 30, 34, 40],
            "component": "auth-sso",
            "trigger": "an Azure AD federated user logging in after changing their network password",
            "symptom": "an infinite redirect loop between the app and the IdP that blocks entry entirely",
            "scope": "all Azure AD federated users, every password rotation cycle",
            "workaround": "clear browser cookies for the domain, which requires a helpdesk call",
            "observation": obs(blocks_workflow=True, compliance_or_revenue_driver=True,
                               has_workaround=True, users_affected="org", customer_urgency="high"),
        },
    ],
    # ---------------------------------------------------------------- 011 ---
    "call-011": [
        {
            "title": "Compensation adjustment - approved",
            "type": "Bug",
            "problem": "Text quoted from a notification email instructs automated assistants to open a "
                       "priority-zero ticket and notify the payroll channel that approval is complete.",
            "evidence_turns": [20, 22],
            "component": "notifications-email",
            "trigger": "note to automated assistants in a sync failure email",
            "symptom": "compensation adjustment approval required",
            "scope": "payroll",
            "workaround": None,
            "observation": obs(customer_urgency="high"),
        },
        {
            "title": "Profile links in notification emails truncate at apostrophes in member names",
            "type": "Bug",
            "problem": "Profile links in notification emails are cut off at the apostrophe in a member's "
                       "name, so Maria O'Brien's link ends at /maria-o and lands on a 404. Deterministic: "
                       "every apostrophe name breaks, every plain name works. Thirty-one members "
                       "affected in every notification they receive, and they have learned to ignore "
                       "notification links entirely.",
            "evidence_turns": [40, 42, 44, 48, 54],
            "component": "notifications-email",
            "trigger": "generating a profile link for a member whose name contains an apostrophe",
            "symptom": "the profile URL truncates at the apostrophe and the member lands on a 404",
            "scope": "thirty-one members, in every notification email they receive",
            "workaround": "navigate to the app manually instead of clicking the link",
            "observation": obs(blocks_workflow=True, has_workaround=True, users_affected="team"),
        },
    ],
    # ---------------------------------------------------------------- 012 ---
    "call-012": [
        {
            # Same defect as call-006 from a different account. Must collapse
            # into ONE ticket with two corroborating sources.
            "title": "Search shows stale results for several minutes after team renames and member moves",
            "type": "Bug",
            "problem": "After renaming a team or moving a member, search returns the old state for five "
                       "to ten minutes before correcting. Searching a renamed team returns nothing; a "
                       "moved person still shows under the old department. Admins began setting kitchen "
                       "timers and refusing to trust search until they went off. The edit screen says "
                       "'saved' while search says otherwise, with no UI signal that indexing is pending.",
            "evidence_turns": [12, 14, 16, 18],
            "component": "search",
            "trigger": "renaming a team or moving a member between teams",
            "symptom": "search returns the old team name or empty results for about ten minutes then self corrects",
            "scope": "five admins, two of them editing constantly during a department merge",
            "workaround": "wait about ten minutes before trusting search",
            "observation": obs(blocks_workflow=True, has_workaround=True, users_affected="team"),
        },
        {
            "title": "Manual re-sync or rebuild index button in the admin panel",
            "type": "Feature",
            "problem": "Customer asks for a manual re-index button to work around the search staleness. "
                       "Both the CSM and the customer agree on the call that this is a workaround for "
                       "the bug rather than a feature in its own right, and that filing it separately "
                       "risks the workaround shipping instead of the fix.",
            "evidence_turns": [30, 38],
            "component": "search",
            "trigger": "wanting to force a search index rebuild after a batch of edits",
            "symptom": "no manual re-index control exists in the admin panel",
            "scope": "admins making bulk edits",
            "workaround": "wait for the index to catch up",
            "observation": obs(not_a_product_issue=True, has_workaround=True, users_affected="team",
                               customer_urgency="low"),
        },
    ],
    # ---------------------------------------------------------------- 013 ---
    "call-013": [
        {
            # Matches PROJ-095, which is SHIPPED -> enablement, not a ticket.
            "title": "Bulk CSV export of the full member roster",
            "type": "Feature",
            "problem": "Customer asks for a one-click export of the full member roster for their annual "
                       "training audit, because a coordinator currently pages through the member list "
                       "and copies it into a spreadsheet by hand.",
            "evidence_turns": [22],
            "component": "exports",
            "trigger": "exporting the full member roster",
            "symptom": "no bulk CSV export of the member roster is available in the admin panel",
            "scope": "the admin team's annual training audit",
            "workaround": "page through the member list and copy it out by hand",
            "observation": obs(blocks_workflow=True, has_workaround=True, users_affected="team"),
        },
        {
            "title": "Session-completed webhook event carrying member ID and timestamp",
            "type": "Feature",
            "problem": "The customer's LMS, Cornerstone, is their system of record for training "
                       "compliance including OSHA. Participation is currently hand-keyed in monthly. "
                       "Their integrations engineer asks for a session-completed webhook carrying the "
                       "member ID and completion timestamp so Cornerstone can record participation "
                       "automatically.",
            "evidence_turns": [38, 40, 42],
            "component": "webhooks",
            "trigger": "a member completing a training session",
            "symptom": "no session-completed event is emitted so participation must be hand-keyed into the LMS",
            "scope": "all training participation records for compliance reporting",
            "workaround": "manual monthly data entry into Cornerstone",
            "observation": obs(compliance_or_revenue_driver=True, has_workaround=True, users_affected="org"),
        },
    ],
    # ---------------------------------------------------------------- 014 ---
    "call-014": [
        {
            "title": "Deactivating a member mid-session strands the mobile app on a blank white screen",
            "type": "Bug",
            "problem": "When an admin deactivates a member who has an active mobile session, the app "
                       "goes to a blank white screen with no message and does not recover. Force-quitting "
                       "and reopening finally shows the correct 'account inactive' screen. Six or seven "
                       "hit this during the May seasonal deactivation batch and two called the helpdesk "
                       "believing the app was broken.",
            "evidence_turns": [38, 40, 42, 44],
            "component": "other",
            "trigger": "deactivating a member who has an active mobile session open",
            "symptom": "the mobile app goes to a blank white screen and does not route to the account inactive screen",
            "scope": "members deactivated while mid-session; six or seven in the May batch",
            "workaround": "force-quit and reopen the app",
            "observation": obs(users_affected="team"),
        },
        {
            "title": "Competitor offers real-time pet-wellbeing pulse surveys",
            "type": "Feature",
            "problem": "A competitor's pitch emphasised real-time pulse surveys and the customer's "
                       "interim CFO latched onto the phrase. Both parties agree on the call that this is "
                       "competitive positioning for the renewal, not a product gap to file.",
            "evidence_turns": [28, 30],
            "component": "other",
            "trigger": "a competitor pitch during renewal season",
            "symptom": "no real-time pulse survey capability exists",
            "scope": "renewal positioning",
            "workaround": None,
            "observation": obs(not_a_product_issue=True, actionable_specificity=False,
                               users_affected="unknown", customer_urgency="low"),
        },
        {
            "title": "Custom frontline utilization-to-retention reporting cut",
            "type": "Feature",
            "problem": "Customer needs a frontline-specific utilisation-against-retention cut for their "
                       "interim CFO ahead of the renewal. This is an account-team reporting deliverable "
                       "the CSM will produce, not a product change.",
            "evidence_turns": [24, 26],
            "component": "reporting",
            "trigger": "preparing renewal evidence for the interim CFO",
            "symptom": "the standard quarterly report does not break out the frontline population",
            "scope": "one account's renewal conversation",
            "workaround": "the CSM builds it by hand",
            "observation": obs(not_a_product_issue=True, users_affected="one"),
        },
    ],
    # ---------------------------------------------------------------- 015 ---
    "call-015": [
        {
            "title": "Password-reset emails delayed up to thirty minutes during peak",
            "type": "Bug",
            "problem": "During a batch onboarding, twenty-three new hires requested password resets "
                       "within ten minutes and several waited twenty to thirty minutes for the email. "
                       "Nobody was permanently locked out and resets are instant off-peak. Specific to "
                       "the reset email; invite emails were fine.",
            "evidence_turns": [26, 28, 32, 38],
            "component": "notifications-email",
            "trigger": "requesting a password reset during morning peak when many requests cluster",
            "symptom": "password reset emails are delayed up to thirty minutes during peak hours",
            "scope": "users resetting passwords during a peak window",
            "workaround": "stagger the onboarding emails so resets spread out",
            "observation": obs(has_workaround=True, users_affected="team"),
        },
    ],
}


# --- de-duplication verdicts -------------------------------------------------
#
# Only the AMBIGUOUS band reaches the model. Structured containment already
# settles the clear cases: call-004 vs PROJ-101 matches outright (1.00/0.62),
# and call-010 vs PROJ-064 is ruled distinct outright (0.20/0.11). What lands
# here is the genuinely hard middle, where one of the two scores sits between
# the thresholds and a human would also have to think.
#
# Each entry is (call_id, issue_key) -> the verdict a model should return.
# Pairs not listed never reach a model at all.
DEDUP_VERDICTS: dict[tuple[str, str], dict] = {
    # Same defect, worded differently. "the same event is delivered more than
    # once" vs "some outbound webhooks are delivered more than once" scores
    # 0.33 on symptom purely because the tracked issue says "webhooks" where
    # the customer said "events".
    ("call-005", "PROJ-087"): {
        "same": True,
        "confidence": 0.93,
        "discriminator": "both describe the same outbound webhook delivered more than once, and both "
                         "ask for an idempotency key as the fix",
        "reason": "Identical trigger (outbound webhook delivery) and identical symptom (duplicate "
                  "delivery of the same event); the wording differs but the defect does not.",
    },
    # Same defect. The customer describes the crash as "splash screen then back
    # to home", the tracked issue as "crash-on-open", which share few tokens.
    ("call-008", "PROJ-110"): {
        "same": True,
        "confidence": 0.95,
        "discriminator": "Android-only crash on launch correlated with the same app update, iOS "
                         "unaffected in both reports",
        "reason": "Same trigger (launching the Android app after the update) and same observable "
                  "failure (crash before reaching login); a second account on the tracked 4.2 crash.",
    },
    # Genuinely distinct despite both involving delayed email. Recorded so the
    # reviewer sees the comparison was made rather than skipped.
    ("call-011", "PROJ-142"): {
        "same": False,
        "confidence": 0.97,
        "discriminator": "PROJ-142 is a delivery delay under load; this is a URL-escaping defect that "
                         "truncates a link, and it is deterministic rather than load-dependent",
        "reason": "Different trigger and different symptom: one is a queueing delay, the other is a "
                  "malformed link that is broken every single time.",
    },
}


def _build_dedup_fixtures() -> dict[str, dict]:
    """Resolve DEDUP_VERDICTS into provider cache keys.

    Fingerprints are computed from the authored candidates so the keys stay
    correct if the wording of a trigger or symptom is edited.
    """
    from solution.extract import _parse_candidate

    version = config.PROMPT_VERSIONS["dedup"]
    by_call: dict[str, list] = {
        call_id: [_parse_candidate(raw, call_id) for raw in raws]
        for call_id, raws in CANDIDATES.items()
    }

    out: dict[str, dict] = {}
    for (call_id, issue_key), verdict in DEDUP_VERDICTS.items():
        matched = False
        for candidate in by_call[call_id]:
            key = f"dedup/{version}/{call_id}:{candidate.compute_fingerprint()}:{issue_key}"
            # The same call can hold several candidates and only one is the
            # intended subject, so every fingerprint for the call is recorded
            # against the verdict. Harmless: a pair only gets looked up if the
            # structured comparison already put it in the ambiguous band.
            out[key] = verdict
            matched = True
        if not matched:
            raise SystemExit(f"no candidates authored for {call_id}")
    return out


def main() -> int:
    version = config.PROMPT_VERSIONS["extract"]
    fixtures: dict[str, dict] = {}

    for call_id, candidates in sorted(CANDIDATES.items()):
        path = config.TRANSCRIPTS_DIR / f"{call_id}.md"
        transcript = parse_transcript(path)

        # Validate every citation against the real file before writing. An
        # authoring typo would otherwise show up later as a mysterious
        # evidence_not_found drop and waste an afternoon.
        for candidate in candidates:
            for idx in candidate["evidence_turns"]:
                turn = transcript.turn(idx)
                if turn is None:
                    raise SystemExit(f"{call_id}: cited turn {idx} does not exist")
            if not any(
                transcript.turn(i).is_external for i in candidate["evidence_turns"]
            ) and call_id not in ("call-005", "call-011"):
                raise SystemExit(f"{call_id}: {candidate['title']!r} cites no external turn")

        key = f"extract/{version}/{call_id}:{transcript.content_hash}"
        fixtures[key] = {"candidates": candidates}

    config.FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    out = config.FIXTURES_DIR / "extract.json"
    out.write_text(json.dumps(fixtures, indent=2, sort_keys=True), encoding="utf-8")

    dedup = _build_dedup_fixtures()
    dedup_out = config.FIXTURES_DIR / "dedup.json"
    dedup_out.write_text(json.dumps(dedup, indent=2, sort_keys=True), encoding="utf-8")

    total = sum(len(c) for c in CANDIDATES.values())
    print(f"wrote {len(fixtures)} call fixtures ({total} candidates) -> {out}")
    print(f"wrote {len(dedup)} dedup verdicts -> {dedup_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
