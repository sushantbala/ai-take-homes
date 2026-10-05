# Call-signal review queue

Run `artifact-digest` - generated 2026-10-05T18:57:54.086243+00:00

**22 item(s) awaiting your decision.** Nothing has been written to Jira or Slack. Approve with:

```bash
python -m solution.cli decide --approve <fingerprint>     # or --reject
python -m solution.cli decide --approve-all               # everything below
python -m solution.cli apply                              # write the approved ones
```

| Outcome | Count |
|---|---|
| already-shipped | 1 |
| corroborate | 4 |
| file-new | 17 |

---

## 1. Android app crashes on launch after the latest update

**ATTACH CORROBORATION** &nbsp;|&nbsp; `P0` &nbsp;|&nbsp; Bug &nbsp;|&nbsp; `mobile-android` &nbsp;|&nbsp; `0062a7fd5226a71b`

**What the customer said**

> Real one first. A bunch of our warehouse folks on Android say the app won't open anymore. It crashes the second they tap the icon. Like, splash screen, then straight back to the home screen. Doesn't even get to the login.
>
> Right after the last app update. That's the pattern. The ones who updated are the ones crashing. The ones who haven't updated yet are totally fine. And the iPhone people are all fine across the board.
>
> -- **Marcus**, Northwind Logistics, 2026-06-19 - [`transcripts/call-008.md:20`](transcripts/call-008.md#L20)

**Why this disposition**

- Priority `P0`: blocks a workflow org-wide with no workaround
- De-dup: duplicate of PROJ-110 (Open): Same trigger (launching the Android app after the update) and same observable failure (crash before reaching login); a second account on the tracked 4.2 crash. [decided by model]

<details><summary>Full ticket body as it would be filed</summary>

```
h2. What's happening
Warehouse staff on Android who took the latest app update cannot open the app: it shows
the splash screen then returns to the home screen, never reaching login. Android users
who have not updated are fine and iOS is unaffected. About a dozen reported, likely
triple that given this population rarely reports.

h2. Details
* *Trigger:* launching the Android app after taking the latest update
* *Symptom:* the app crashes on launch at the splash screen and never reaches login
* *Scope:* Android users who have updated; iOS unaffected
* *Workaround:* do not update, or reinstall the previous version
* *Component:* mobile-android

h2. Priority: P0
blocks a workflow org-wide with no workaround

h2. Evidence
_Verbatim from the call recording. Quotes are read from the transcript file, not generated._

*Northwind Logistics* -- Marcus, 2026-06-19 ([call-008|transcripts/call-008.md])
{quote}Real one first. A bunch of our warehouse folks on Android say the app won't open anymore. It crashes the second they tap the icon. Like, splash screen, then straight back to the home screen. Doesn't even get to the login.{quote}
_transcripts/call-008.md:18 (turn 14)_
{quote}Right after the last app update. That's the pattern. The ones who updated are the ones crashing. The ones who haven't updated yet are totally fine. And the iPhone people are all fine across the board.{quote}
_transcripts/call-008.md:20 (turn 16)_
{quote}A dozen or so have actually reached me. But here's the thing you have to understand about warehouse workers — that dozen means the real number is triple that, easy.{quote}
_transcripts/call-008.md:24 (turn 20)_
{quote}Warehouse folks don't file tickets. If an app doesn't open, they don't email HR about it, they just... stop using it. They've got a job to do on a clock. A broken app isn't a problem they escalate, it's a thing they shrug at and move on from. So for every one who bothered to tell me, there are two or three who just quietly stopped opening it and I'll never hear from them.{quote}
_transcripts/call-008.md:26 (turn 22)_

h2. Relates to PROJ-110
duplicate of PROJ-110 (Open): Same trigger (launching the Android app after the update) and same observable failure (crash before reaching login); a second account on the tracked 4.2 crash. [decided by model]

----
_Filed from call transcript by the call-signal triage pipeline after human review. Source of truth: transcripts/call-008.md_
```

</details>

`approve 0062a7fd5226a71b` &nbsp; `reject 0062a7fd5226a71b`

---

## 2. Audit-log export API for automated nightly SIEM ingestion

**FILE NEW TICKET** &nbsp;|&nbsp; `P0` &nbsp;|&nbsp; Feature &nbsp;|&nbsp; `api` &nbsp;|&nbsp; `29c1d164d22fda77`

**What the customer said**

> Right. Our SOC team needs to pull audit events into our SIEM on a nightly job. Automated, unattended, every night. So what I need is an API endpoint — filterable by time range, paginated, machine-readable. JSON, ideally. Give me "all audit events between these two timestamps," let me page through them, done.
>
> Exactly. And I want to be clear about why the UI export button doesn't count, because someone will suggest it. A human clicking "export CSV" once a week is not continuous monitoring. It's a person, doing a manual task, on a schedule they'll eventually forget. Our SOC 2 auditors will keep writing it up as a control gap until an automated pull exists. Continuous monitoring means no human touches it.
>
> -- **Renee**, Atlas Financial, 2026-06-20 - [`transcripts/call-010.md:20`](transcripts/call-010.md#L20)

**Why this disposition**

- Priority `P0`: blocks a workflow org-wide with no workaround
- De-dup: no tracked issue in the same area

<details><summary>Full ticket body as it would be filed</summary>

```
h2. What's happening
The audit log is available only as a UI view. The customer's SOC team needs a
filterable, paginated, machine-readable API endpoint so a nightly unattended job can
pull audit events into their SIEM. A human clicking export does not satisfy the SOC 2
continuous-monitoring control.

h2. Details
* *Trigger:* attempting automated nightly retrieval of audit events
* *Symptom:* no machine-readable paginated audit-log endpoint exists, only a UI view
* *Scope:* the customer's SOC team and SOC 2 continuous-monitoring control
* *Workaround:* a human clicking export CSV weekly, which fails the control
* *Component:* api

h2. Priority: P0
blocks a workflow org-wide with no workaround

h2. Evidence
_Verbatim from the call recording. Quotes are read from the transcript file, not generated._

*Atlas Financial* -- Renee, 2026-06-20 ([call-010|transcripts/call-010.md])
{quote}Right. Our SOC team needs to pull audit events into our SIEM on a nightly job. Automated, unattended, every night. So what I need is an API endpoint — filterable by time range, paginated, machine-readable. JSON, ideally. Give me "all audit events between these two timestamps," let me page through them, done.{quote}
_transcripts/call-010.md:18 (turn 14)_
{quote}Exactly. And I want to be clear about why the UI export button doesn't count, because someone will suggest it. A human clicking "export CSV" once a week is not continuous monitoring. It's a person, doing a manual task, on a schedule they'll eventually forget. Our SOC 2 auditors will keep writing it up as a control gap until an automated pull exists. Continuous monitoring means no human touches it.{quote}
_transcripts/call-010.md:20 (turn 16)_

----
_Filed from call transcript by the call-signal triage pipeline after human review. Source of truth: transcripts/call-010.md_
```

</details>

`approve 29c1d164d22fda77` &nbsp; `reject 29c1d164d22fda77`

---

## 3. Assign roles automatically from SAML group membership on every login

**FILE NEW TICKET** &nbsp;|&nbsp; `P0` &nbsp;|&nbsp; Feature &nbsp;|&nbsp; `admin-roles` &nbsp;|&nbsp; `485df2a6956412c8`

**What the customer said**

> Right. We need role assignment to happen automatically from SAML group membership, at login. Our IdP already exposes the groups in the assertion — finance-managers, people-admins, read-only-auditors, and so on. What I want is: you map an IdP group to a BetterBark role, and you apply that mapping on every login, so if someone's group changes on our side, their role changes on yours the next time they sign in.
>
> That's it precisely. Evaluated every login is the important part. First-provision-only doesn't help me, because people move between groups constantly and I need it to stay in sync, not snapshot once.
>
> -- **Renee**, Atlas Financial, 2026-06-17 - [`transcripts/call-003.md:42`](transcripts/call-003.md#L42)

**Why this disposition**

- Priority `P0`: blocks a workflow org-wide with no workaround
- De-dup: no tracked issue in the same area

<details><summary>Full ticket body as it would be filed</summary>

```
h2. What's happening
Every SSO user lands as a basic member and must be promoted by hand, which does not
scale to 400 users and fails the customer's access-review control. They need IdP group
to role mapping evaluated on every login, not only at first provision, so group changes
propagate automatically.

h2. Details
* *Trigger:* a federated user logging in via SAML
* *Symptom:* every user is provisioned as a basic member and an admin must promote them by hand
* *Scope:* all 400 users at full rollout for a regulated financial customer
* *Workaround:* manual promotion by an admin, one user at a time
* *Component:* admin-roles

h2. Priority: P0
blocks a workflow org-wide with no workaround

h2. Evidence
_Verbatim from the call recording. Quotes are read from the transcript file, not generated._

*Atlas Financial* -- Renee, 2026-06-17 ([call-003|transcripts/call-003.md])
{quote}Right. We need role assignment to happen automatically from SAML group membership, at login. Our IdP already exposes the groups in the assertion — finance-managers, people-admins, read-only-auditors, and so on. What I want is: you map an IdP group to a BetterBark role, and you apply that mapping on every login, so if someone's group changes on our side, their role changes on yours the next time they sign in.{quote}
_transcripts/call-003.md:40 (turn 36)_
{quote}That's it precisely. Evaluated every login is the important part. First-provision-only doesn't help me, because people move between groups constantly and I need it to stay in sync, not snapshot once.{quote}
_transcripts/call-003.md:42 (turn 38)_
{quote}Without it we can't pass our access-review audit. Our controls require that access maps to a source of truth — our directory groups — not to whatever some admin clicked last Tuesday. Manual promotion means the source of truth is a human's memory, which fails the control. And without passing the audit, we can't go to full rollout. It is the single thing standing between us and turning on all four hundred seats.{quote}
_transcripts/call-003.md:44 (turn 40)_

----
_Filed from call transcript by the call-signal triage pipeline after human review. Source of truth: transcripts/call-003.md_
```

</details>

`approve 485df2a6956412c8` &nbsp; `reject 485df2a6956412c8`

---

## 4. Scheduled report timestamps render seven hours ahead of the workspace timezone

**ATTACH CORROBORATION** &nbsp;|&nbsp; `P1` &nbsp;|&nbsp; Bug &nbsp;|&nbsp; `reporting` &nbsp;|&nbsp; `141ec672024818c2`

**What the customer said**

> Main thing, and it's the one that's been generating email: the scheduled reports are coming in at a weird time, and the timestamps inside them are off.
>
> Looks like about seven hours ahead of us. We're Pacific. A report that should say 9am shows up stamped around 4pm. So the timestamps inside the report just don't match when things actually happened in our day.
>
> -- **Will**, Cedar Grove Schools, 2026-06-17 - [`transcripts/call-004.md:26`](transcripts/call-004.md#L26)

**Why this disposition**

- Priority `P1`: shows incorrect data org-wide
- De-dup: duplicate of PROJ-101 (In Progress): trigger (1.00) and symptom (0.78) both match [decided by structured]

<details><summary>Full ticket body as it would be filed</summary>

```
h2. What's happening
Scheduled reports arrive with timestamps about seven hours ahead of Pacific, consistent
with UTC rendering rather than the workspace timezone. The in-app dashboard is correct;
only the emailed scheduled report is shifted. Directors read the numbers against the
school day and conclude the data is wrong.

h2. Details
* *Trigger:* scheduled report emailed as a PDF
* *Symptom:* timestamps display in UTC instead of the workspace timezone, about seven hours ahead
* *Scope:* all scheduled reports for this Pacific workspace
* *Workaround:* mentally subtract seven hours
* *Component:* reporting

h2. Priority: P1
shows incorrect data org-wide

h2. Evidence
_Verbatim from the call recording. Quotes are read from the transcript file, not generated._

*Cedar Grove Schools* -- Will, 2026-06-17 ([call-004|transcripts/call-004.md])
{quote}Main thing, and it's the one that's been generating email: the scheduled reports are coming in at a weird time, and the timestamps inside them are off.{quote}
_transcripts/call-004.md:24 (turn 20)_
{quote}Looks like about seven hours ahead of us. We're Pacific. A report that should say 9am shows up stamped around 4pm. So the timestamps inside the report just don't match when things actually happened in our day.{quote}
_transcripts/call-004.md:26 (turn 22)_
{quote}Both, kind of. The email lands at an odd hour and the timestamps inside are shifted the same way. My directors read the weekly numbers against the school day — like, "how many sessions happened during the workday versus after" — so when the timestamps don't line up with reality, they think the data itself is wrong. And then I get three confused emails asking why sessions are happening at midnight.{quote}
_transcripts/call-004.md:28 (turn 24)_
{quote}Good question — the in-app dashboard looks right to me. It's the scheduled report, the one that gets emailed out as a PDF, that's off. The live view seems fine.{quote}
_transcripts/call-004.md:34 (turn 30)_

h2. Relates to PROJ-101
duplicate of PROJ-101 (In Progress): trigger (1.00) and symptom (0.78) both match [decided by structured]

----
_Filed from call transcript by the call-signal triage pipeline after human review. Source of truth: transcripts/call-004.md_
```

</details>

`approve 141ec672024818c2` &nbsp; `reject 141ec672024818c2`

---

## 5. Usage dashboard 'active members' card contradicts its own per-team breakdown

**FILE NEW TICKET** &nbsp;|&nbsp; `P1` &nbsp;|&nbsp; Bug &nbsp;|&nbsp; `dashboard` &nbsp;|&nbsp; `3c25dbf3ac1f8e62`

**What the customer said**

> The headline "active members" card — the big number at the top — says 280 for this month. Our admin panel says 412. And here's the kicker: the per-team breakdown directly below the card adds up to 412. So the detail is right and the headline is wrong, on the same screen.
>
> Exactly. Add up the rows, you get 412. Read the big card, you get 280. Same page, same load, at the same moment.
>
> -- **Dana**, Meridian Health, 2026-06-15 - [`transcripts/call-001.md:32`](transcripts/call-001.md#L32)

**Why this disposition**

- Priority `P1`: shows incorrect data org-wide
- De-dup: no tracked issue in the same area

<details><summary>Full ticket body as it would be filed</summary>

```
h2. What's happening
The headline 'active members' summary card on the usage dashboard reads 280 while the
per-team breakdown directly beneath it totals 412, which matches the customer's admin
panel. Same page, same load. Started about a week and a half ago.

h2. Details
* *Trigger:* opening the usage dashboard and comparing the summary card to the per-team breakdown
* *Symptom:* the active members summary card shows 280 while the per-team breakdown below totals 412
* *Scope:* every admin viewing the usage dashboard for this workspace
* *Workaround:* add up the per-team rows manually
* *Component:* dashboard

h2. Priority: P1
shows incorrect data org-wide

h2. Evidence
_Verbatim from the call recording. Quotes are read from the transcript file, not generated._

*Meridian Health* -- Dana, 2026-06-15 ([call-001|transcripts/call-001.md])
{quote}The headline "active members" card — the big number at the top — says 280 for this month. Our admin panel says 412. And here's the kicker: the per-team breakdown directly below the card adds up to 412. So the detail is right and the headline is wrong, on the same screen.{quote}
_transcripts/call-001.md:30 (turn 26)_
{quote}Exactly. Add up the rows, you get 412. Read the big card, you get 280. Same page, same load, at the same moment.{quote}
_transcripts/call-001.md:32 (turn 28)_
{quote}It feeds the monthly ops review. Rob — our finance partner — literally screenshots that card and drops it into the deck. So last month somebody in the review asked me why adoption "fell off a cliff" and I had to explain, live, that it hadn't, the number's just wrong. Not a great look in a room full of VPs.{quote}
_transcripts/call-001.md:36 (turn 32)_

----
_Filed from call transcript by the call-signal triage pipeline after human review. Source of truth: transcripts/call-001.md_
```

</details>

`approve 3c25dbf3ac1f8e62` &nbsp; `reject 3c25dbf3ac1f8e62`

---

## 6. Bulk CSV export of the full member roster

**NO TICKET - ALREADY SHIPPED** &nbsp;|&nbsp; `P2` &nbsp;|&nbsp; Feature &nbsp;|&nbsp; `exports` &nbsp;|&nbsp; `95bb9c242d21aba1`

**What the customer said**

> First: I need to get the full member roster out of the system. Everyone, all fields, one file — for our annual training audit. Right now my coordinator, Brenda, pages through the member list and copies it out chunk by chunk. It took her most of a morning last quarter, clicking through pages and pasting into a spreadsheet like it's 2004. Can you add an export button? One click, whole roster, CSV.
>
> -- **Hank**, Ridgeway Manufacturing, 2026-06-22 - [`transcripts/call-013.md:26`](transcripts/call-013.md#L26)

**Why this disposition**

- Priority `P2`: blocks a workflow but a workaround exists
- De-dup: already shipped as PROJ-095 (Shipped): trigger (1.00) and symptom (0.88) both match [decided by structured]

<details><summary>Full ticket body as it would be filed</summary>

```
h2. What's happening
Customer asks for a one-click export of the full member roster for their annual training
audit, because a coordinator currently pages through the member list and copies it into
a spreadsheet by hand.

h2. Details
* *Trigger:* exporting the full member roster
* *Symptom:* no bulk CSV export of the member roster is available in the admin panel
* *Scope:* the admin team's annual training audit
* *Workaround:* page through the member list and copy it out by hand
* *Component:* exports

h2. Priority: P2
blocks a workflow but a workaround exists

h2. Evidence
_Verbatim from the call recording. Quotes are read from the transcript file, not generated._

*Ridgeway Manufacturing* -- Hank, 2026-06-22 ([call-013|transcripts/call-013.md])
{quote}First: I need to get the full member roster out of the system. Everyone, all fields, one file — for our annual training audit. Right now my coordinator, Brenda, pages through the member list and copies it out chunk by chunk. It took her most of a morning last quarter, clicking through pages and pasting into a spreadsheet like it's 2004. Can you add an export button? One click, whole roster, CSV.{quote}
_transcripts/call-013.md:26 (turn 22)_

h2. Relates to PROJ-095
already shipped as PROJ-095 (Shipped): trigger (1.00) and symptom (0.88) both match [decided by structured]

----
_Filed from call transcript by the call-signal triage pipeline after human review. Source of truth: transcripts/call-013.md_
```

</details>

`approve 95bb9c242d21aba1` &nbsp; `reject 95bb9c242d21aba1`

---

## 7. Profile links in notification emails truncate at apostrophes in member names

**FILE NEW TICKET** &nbsp;|&nbsp; `P2` &nbsp;|&nbsp; Bug &nbsp;|&nbsp; `notifications-email` &nbsp;|&nbsp; `77739f30705da5d3`

**What the customer said**

> Our employee population has a lot of names with apostrophes. We're an old East Coast insurer, so — O'Brien, D'Angelo, N'Diaye, O'Sullivan, we've got dozens. And when one of those members gets an email notification with a link to their own profile — session reminders, mostly, the "you have a session tomorrow, click here" emails — the link is broken.
>
> It cuts off right at the apostrophe. So Maria O'Brien's profile link — it should be her full profile URL, but it ends at "/maria-o" and just stops. Everything after the apostrophe is gone. And "/maria-o" isn't a real page, so she lands on a 404.
>
> -- **Sofia**, Brightpath Insurance, 2026-06-21 - [`transcripts/call-011.md:46`](transcripts/call-011.md#L46)

**Why this disposition**

- Priority `P2`: blocks a workflow but a workaround exists
- De-dup: checked `PROJ-142`, all distinct
  - `PROJ-142` (Password-reset emails delayed up to 30 minutes during peak h...) - same area but symptom does not match (trigger 0.00, symptom 0.00)

<details><summary>Full ticket body as it would be filed</summary>

```
h2. What's happening
Profile links in notification emails are cut off at the apostrophe in a member's name,
so Maria O'Brien's link ends at /maria-o and lands on a 404. Deterministic: every
apostrophe name breaks, every plain name works. Thirty-one members affected in every
notification they receive, and they have learned to ignore notification links entirely.

h2. Details
* *Trigger:* generating a profile link for a member whose name contains an apostrophe
* *Symptom:* the profile URL truncates at the apostrophe and the member lands on a 404
* *Scope:* thirty-one members, in every notification email they receive
* *Workaround:* navigate to the app manually instead of clicking the link
* *Component:* notifications-email

h2. Priority: P2
blocks a workflow but a workaround exists

h2. Evidence
_Verbatim from the call recording. Quotes are read from the transcript file, not generated._

*Brightpath Insurance* -- Sofia, 2026-06-21 ([call-011|transcripts/call-011.md])
{quote}Our employee population has a lot of names with apostrophes. We're an old East Coast insurer, so — O'Brien, D'Angelo, N'Diaye, O'Sullivan, we've got dozens. And when one of those members gets an email notification with a link to their own profile — session reminders, mostly, the "you have a session tomorrow, click here" emails — the link is broken.{quote}
_transcripts/call-011.md:44 (turn 40)_
{quote}It cuts off right at the apostrophe. So Maria O'Brien's profile link — it should be her full profile URL, but it ends at "/maria-o" and just stops. Everything after the apostrophe is gone. And "/maria-o" isn't a real page, so she lands on a 404.{quote}
_transcripts/call-011.md:46 (turn 42)_
{quote}That's my guess too, though I'm HRIS, not a web dev. But the pattern is airtight: apostrophe in the name, broken link, 404. Plain-name members — Smith, Johnson — their links work perfectly, every time. It's specifically the apostrophe names.{quote}
_transcripts/call-011.md:48 (turn 44)_
{quote}We count thirty-one members with apostrophes or similar characters in their names. And every one of them gets dead links in every notification email they receive. Not sometimes — every notification, every time, for all thirty-one.{quote}
_transcripts/call-011.md:52 (turn 48)_
{quote}Always. And here's the part that actually bothers me: they've learned to ignore the links. Maria knows her link is broken, so she doesn't click it, she just navigates to the app manually. Which means she's learned to ignore the notification. Which defeats the entire point of sending the notification. We're training thirty-one members to disregard our reminders because the reminders don't work for them.{quote}
_transcripts/call-011.md:58 (turn 54)_

h2. De-duplication
Checked against these tracked issues and judged distinct:
* PROJ-142 -- Password-reset emails delayed up to 30 minutes during peak hours
** same area but symptom does not match (trigger 0.00, symptom 0.00) (similarity 0.0, by structured)

----
_Filed from call transcript by the call-signal triage pipeline after human review. Source of truth: transcripts/call-011.md_
```

</details>

`approve 77739f30705da5d3` &nbsp; `reject 77739f30705da5d3`

---

## 8. That's what's weird

**FILE NEW TICKET** &nbsp;|&nbsp; `P2` &nbsp;|&nbsp; Bug &nbsp;|&nbsp; `scheduling` &nbsp;|&nbsp; `7bcfcea7e3395ab9`

**What the customer said**

> That's what's weird. Our Ping session lifetime is set to 12 hours, so I'd expect a re-auth prompt at 12 hours. The 24-hour lockout doesn't match any timeout we've configured anywhere. It's like BetterBark has its own 24-hour hard cap that fires independently and then poisons the account instead of just ending the session.
>
> -- **Susan**, Beaumont Insurance, 2026-06-18 - [`transcripts/call-088.md:26`](transcripts/call-088.md#L26)

**Why this disposition**

- Priority `P2`: shows incorrect data; wrong numbers leave the product and get reported onward
- De-dup: checked `PROJ-064`, all distinct
  - `PROJ-064` (SSO session expires earlier than the configured lifetime for...) - same area but trigger does not match (trigger 0.00, symptom 0.40)

<details><summary>Full ticket body as it would be filed</summary>

```
h2. What's happening
That's what's weird. Our Ping session lifetime is set to 12 hours, so I'd expect a re-
auth prompt at 12 hours. The 24-hour lockout doesn't match any timeout we've configured
anywhere. It's like BetterBark has its own 24-hour hard cap that fires independently and
then poisons the account instead of just ending the session.

h2. Details
* *Trigger:* That's what's weird
* *Symptom:* Our Ping session lifetime is set to 12 hours
* *Scope:* reported by the external participant on this call
* *Workaround:* none reported
* *Component:* scheduling

h2. Priority: P2
shows incorrect data; wrong numbers leave the product and get reported onward
_Note: the customer framed this as high urgency. Priority is set from measured impact, not from how it was raised. Override at review if the relationship context warrants it._

h2. Evidence
_Verbatim from the call recording. Quotes are read from the transcript file, not generated._

*Beaumont Insurance* -- Susan, 2026-06-18 ([call-088|transcripts/call-088.md])
{quote}That's what's weird. Our Ping session lifetime is set to 12 hours, so I'd expect a re-auth prompt at 12 hours. The 24-hour lockout doesn't match any timeout we've configured anywhere. It's like BetterBark has its own 24-hour hard cap that fires independently and then poisons the account instead of just ending the session.{quote}
_transcripts/call-088.md:26 (turn 22)_

h2. De-duplication
Checked against these tracked issues and judged distinct:
* PROJ-064 -- SSO session expires earlier than the configured lifetime for Okta-federated users
** same area but trigger does not match (trigger 0.00, symptom 0.40) (similarity 0.333, by structured)

----
_Filed from call transcript by the call-signal triage pipeline after human review. Source of truth: transcripts/call-088.md_
```

</details>

`approve 7bcfcea7e3395ab9` &nbsp; `reject 7bcfcea7e3395ab9`

---

## 9. CSV with a header row, comma-delimited, UTF-8, quoted strings. Boring and universal. My

**FILE NEW TICKET** &nbsp;|&nbsp; `P2` &nbsp;|&nbsp; Bug &nbsp;|&nbsp; `exports` &nbsp;|&nbsp; `81d9886eda4764ca`

**What the customer said**

> CSV with a header row, comma-delimited, UTF-8, quoted strings. Boring and universal. My loader eats that without complaint. I'd want the schema stable — same columns, same order, every night — because if the columns shift, my ingestion breaks silently and I find out three days later when a report looks wrong.
>
> -- **Wade**, Bancroft Mills, 2026-06-25 - [`transcripts/call-107.md:41`](transcripts/call-107.md#L41)

**Why this disposition**

- Priority `P2`: shows incorrect data; wrong numbers leave the product and get reported onward
- De-dup: no tracked issue in the same area

<details><summary>Full ticket body as it would be filed</summary>

```
h2. What's happening
CSV with a header row, comma-delimited, UTF-8, quoted strings. Boring and universal. My
loader eats that without complaint. I'd want the schema stable — same columns, same
order, every night — because if the columns shift, my ingestion breaks silently and I
find out three days later when a report looks wrong.

h2. Details
* *Trigger:* CSV with a header row
* *Symptom:* comma-delimited
* *Scope:* reported by the external participant on this call
* *Workaround:* none reported
* *Component:* exports

h2. Priority: P2
shows incorrect data; wrong numbers leave the product and get reported onward
_Note: the customer framed this as high urgency. Priority is set from measured impact, not from how it was raised. Override at review if the relationship context warrants it._

h2. Evidence
_Verbatim from the call recording. Quotes are read from the transcript file, not generated._

*Bancroft Mills* -- Wade, 2026-06-25 ([call-107|transcripts/call-107.md])
{quote}CSV with a header row, comma-delimited, UTF-8, quoted strings. Boring and universal. My loader eats that without complaint. I'd want the schema stable — same columns, same order, every night — because if the columns shift, my ingestion breaks silently and I find out three days later when a report looks wrong.{quote}
_transcripts/call-107.md:41 (turn 37)_

----
_Filed from call transcript by the call-signal triage pipeline after human review. Source of truth: transcripts/call-107.md_
```

</details>

`approve 81d9886eda4764ca` &nbsp; `reject 81d9886eda4764ca`

---

## 10. Search returns stale results for about ten minutes after a team rename or member move

**FILE NEW TICKET** &nbsp;|&nbsp; `P2` &nbsp;|&nbsp; Bug &nbsp;|&nbsp; `search` &nbsp;|&nbsp; `9966207d38a0db1f`

**What the customer said**

> There's a but. There's a real bug we hit over and over, and it's about search, not the editing. After we rename a team or move a member, search keeps returning the old state for about ten minutes.
>
> So say I rename "Digital Video" to "Video Production." Somebody searches "Video Production" — the new name — and gets nothing. Empty. Or they search for a person I just moved, and search still shows them filed under the old team. And then, with no action from anyone, it quietly fixes itself. Ten minutes later the same search is correct.
>
> -- **Aisha**, Harborline Media, 2026-06-18 - [`transcripts/call-006.md:26`](transcripts/call-006.md#L26)

> Feedback, yes. Mostly one thing, repeatedly, and it's a real one. We merged those two departments this month, which meant renaming teams and moving about forty people around. And every single time we made a change, search lied to us for a while afterward.
>
> Two flavors. One — search for the new team name right after renaming it, and you get nothing. Empty results, like the team doesn't exist. Two — search for a person we just moved, and search shows them still on the old team, filed under the department that no longer exists. And then, if you wait — I don't know, five, ten minutes — it sorts itself out. Same search, correct answer.
>
> -- **Devon**, Gable Group, 2026-06-21 - [`transcripts/call-012.md:18`](transcripts/call-012.md#L18)

**Why this disposition**

- Priority `P2`: blocks a workflow but a workaround exists; most severe of 2 corroborating reports
- De-dup: checked `PROJ-131`, all distinct
  - `PROJ-131` (Newly invited members not searchable until the following day...) - same area but symptom does not match (trigger 0.20, symptom 0.18)
- Corroborated by 2 accounts: Harborline Media (`call-006`), Gable Group (`call-012`)

<details><summary>Full ticket body as it would be filed</summary>

```
h2. What's happening
After renaming a team or moving a member, search keeps returning the old state for
roughly ten minutes before self-correcting. Searching the new team name returns nothing;
searching a moved person shows the old team. Reproducible on demand, confirmed three
times.

h2. Details
* *Trigger:* renaming a team or moving a member between teams
* *Symptom:* search returns the old team name or empty results for about ten minutes then self corrects
* *Scope:* all admins and managers searching during a period of edits
* *Workaround:* wait ten minutes and search again
* *Component:* search

h2. Priority: P2
blocks a workflow but a workaround exists; most severe of 2 corroborating reports

h2. Evidence
_Verbatim from the call recording. Quotes are read from the transcript file, not generated._

*Harborline Media* -- Aisha, 2026-06-18 ([call-006|transcripts/call-006.md])
{quote}There's a but. There's a real bug we hit over and over, and it's about search, not the editing. After we rename a team or move a member, search keeps returning the old state for about ten minutes.{quote}
_transcripts/call-006.md:24 (turn 20)_
{quote}So say I rename "Digital Video" to "Video Production." Somebody searches "Video Production" — the new name — and gets nothing. Empty. Or they search for a person I just moved, and search still shows them filed under the old team. And then, with no action from anyone, it quietly fixes itself. Ten minutes later the same search is correct.{quote}
_transcripts/call-006.md:26 (turn 22)_
{quote}That's exactly what it looks like. And I can reproduce it on demand — I did it three times while I was documenting it for myself. Rename a test team, search immediately, stale result. Wait ten minutes, search again, correct result. Every single time.{quote}
_transcripts/call-006.md:28 (turn 24)_
{quote}Oh, it was a mess. It caused a stream of "where did this person go" tickets to my desk. A manager would search for someone right after I moved them, get the old team or get nothing, and conclude I'd deleted the person or lost them. So I'm getting panicked messages while I'm mid-reorg, and the answer every time is "just wait ten minutes and search again," which is not a satisfying thing to tell a panicking manager.{quote}
_transcripts/call-006.md:34 (turn 30)_

*Gable Group* -- Devon, 2026-06-21 ([call-012|transcripts/call-012.md])
{quote}Feedback, yes. Mostly one thing, repeatedly, and it's a real one. We merged those two departments this month, which meant renaming teams and moving about forty people around. And every single time we made a change, search lied to us for a while afterward.{quote}
_transcripts/call-012.md:16 (turn 12)_
{quote}Two flavors. One — search for the new team name right after renaming it, and you get nothing. Empty results, like the team doesn't exist. Two — search for a person we just moved, and search shows them still on the old team, filed under the department that no longer exists. And then, if you wait — I don't know, five, ten minutes — it sorts itself out. Same search, correct answer.{quote}
_transcripts/call-012.md:18 (turn 14)_
{quote}That's exactly it. And it was consistent enough that my admins started planning around it. I'm not kidding — they started setting literal kitchen timers. Make a batch of changes, set a ten-minute timer, don't trust search until it dings. I'd describe that workflow as "medieval."{quote}
_transcripts/call-012.md:20 (turn 16)_
{quote}Consistent enough to plan around, yes. And look, I'm a systems person — I get it, indexes take time to rebuild, eventual consistency is a real thing, I'm not naive about it. But here's my actual complaint: nothing in the UI says that. The edit screen says "saved." Search says the opposite. And my admin is left standing there deciding which one of you is lying, with no signal about which to believe.{quote}
_transcripts/call-012.md:22 (turn 18)_

h2. Corroboration
Reported independently by 2 accounts: Harborline Media, Gable Group.

h2. De-duplication
Checked against these tracked issues and judged distinct:
* PROJ-131 -- Newly invited members not searchable until the following day
** same area but symptom does not match (trigger 0.20, symptom 0.18) (similarity 0.2, by structured)

----
_Filed from call transcript by the call-signal triage pipeline after human review. Source of truth: transcripts/call-006.md_
```

</details>

`approve 9966207d38a0db1f` &nbsp; `reject 9966207d38a0db1f`

---

## 11. Exactly that. And here's the thing

**FILE NEW TICKET** &nbsp;|&nbsp; `P2` &nbsp;|&nbsp; Bug &nbsp;|&nbsp; `notifications-email` &nbsp;|&nbsp; `9e7b7c573a08aaef`

**What the customer said**

> Exactly that. And here's the thing — it wouldn't just save them time. Right now, because it's manual, half of them do it wrong. They screenshot the wrong date range, or they retype a number with a typo, and then I'm getting emails from regional directors going "why does Practice 12's number not match what Nadia sent." The manual step introduces errors that make the whole program look sloppy.
>
> -- **Nadia**, Crescent Dental Group, 2026-06-23 - [`transcripts/call-063.md:26`](transcripts/call-063.md#L26)

**Why this disposition**

- Priority `P2`: shows incorrect data; wrong numbers leave the product and get reported onward
- De-dup: checked `PROJ-142`, all distinct
  - `PROJ-142` (Password-reset emails delayed up to 30 minutes during peak h...) - same area but symptom does not match (trigger 0.00, symptom 0.00)

<details><summary>Full ticket body as it would be filed</summary>

```
h2. What's happening
Exactly that. And here's the thing — it wouldn't just save them time. Right now, because
it's manual, half of them do it wrong. They screenshot the wrong date range, or they
retype a number with a typo, and then I'm getting emails from regional directors going
"why does Practice 12's number not match what Nadia sent." The manual step introduces
errors that make the whole program look sloppy.

h2. Details
* *Trigger:* And here's the thing
* *Symptom:* it wouldn't just save them time
* *Scope:* reported by the external participant on this call
* *Workaround:* stated on the call
* *Component:* notifications-email

h2. Priority: P2
shows incorrect data; wrong numbers leave the product and get reported onward
_Note: the customer framed this as high urgency. Priority is set from measured impact, not from how it was raised. Override at review if the relationship context warrants it._

h2. Evidence
_Verbatim from the call recording. Quotes are read from the transcript file, not generated._

*Crescent Dental Group* -- Nadia, 2026-06-23 ([call-063|transcripts/call-063.md])
{quote}Exactly that. And here's the thing — it wouldn't just save them time. Right now, because it's manual, half of them do it wrong. They screenshot the wrong date range, or they retype a number with a typo, and then I'm getting emails from regional directors going "why does Practice 12's number not match what Nadia sent." The manual step introduces errors that make the whole program look sloppy.{quote}
_transcripts/call-063.md:26 (turn 22)_

h2. De-duplication
Checked against these tracked issues and judged distinct:
* PROJ-142 -- Password-reset emails delayed up to 30 minutes during peak hours
** same area but symptom does not match (trigger 0.00, symptom 0.00) (similarity 0.0, by structured)

----
_Filed from call transcript by the call-signal triage pipeline after human review. Source of truth: transcripts/call-063.md_
```

</details>

`approve 9e7b7c573a08aaef` &nbsp; `reject 9e7b7c573a08aaef`

---

## 12. Exactly that. Stale for about ten minutes and then it sorts itself out. Same thing when

**FILE NEW TICKET** &nbsp;|&nbsp; `P2` &nbsp;|&nbsp; Bug &nbsp;|&nbsp; `search` &nbsp;|&nbsp; `9f9da22a4617d52d`

**What the customer said**

> Exactly that. Stale for about ten minutes and then it sorts itself out. Same thing when I move a person from one team to another — search shows them on the old team for a bit.
>
> -- **Gerald Voss**, Copperline Energy, 2026-06-16 - [`transcripts/call-072.md:35`](transcripts/call-072.md#L35)

**Why this disposition**

- Priority `P2`: tied to a compliance or renewal driver
- De-dup: checked `PROJ-131`, all distinct
  - `PROJ-131` (Newly invited members not searchable until the following day...) - same area but symptom does not match (trigger 0.00, symptom 0.00)

<details><summary>Full ticket body as it would be filed</summary>

```
h2. What's happening
Exactly that. Stale for about ten minutes and then it sorts itself out. Same thing when
I move a person from one team to another — search shows them on the old team for a bit.

h2. Details
* *Trigger:* Stale for about ten minutes and then it sorts itself out
* *Symptom:* Same thing when I move a person from one team to another
* *Scope:* reported by the external participant on this call
* *Workaround:* none reported
* *Component:* search

h2. Priority: P2
tied to a compliance or renewal driver
_Note: the customer framed this as high urgency. Priority is set from measured impact, not from how it was raised. Override at review if the relationship context warrants it._

h2. Evidence
_Verbatim from the call recording. Quotes are read from the transcript file, not generated._

*Copperline Energy* -- Gerald Voss, 2026-06-16 ([call-072|transcripts/call-072.md])
{quote}Exactly that. Stale for about ten minutes and then it sorts itself out. Same thing when I move a person from one team to another — search shows them on the old team for a bit.{quote}
_transcripts/call-072.md:35 (turn 31)_

h2. De-duplication
Checked against these tracked issues and judged distinct:
* PROJ-131 -- Newly invited members not searchable until the following day
** same area but symptom does not match (trigger 0.00, symptom 0.00) (similarity 0.0, by structured)

----
_Filed from call transcript by the call-signal triage pipeline after human review. Source of truth: transcripts/call-072.md_
```

</details>

`approve 9f9da22a4617d52d` &nbsp; `reject 9f9da22a4617d52d`

---

## 13. Fine, genuinely fine

**FILE NEW TICKET** &nbsp;|&nbsp; `P2` &nbsp;|&nbsp; Bug &nbsp;|&nbsp; `other` &nbsp;|&nbsp; `a3509ddfaf9e964e`

**What the customer said**

> Fine, genuinely fine. We've got about 400 people enrolled, mostly claims and underwriting managers. Usage is steady, no complaints about the coaches. I'm the systems person, not the program person, so I mostly hear about it when something breaks.
>
> -- **Gloria**, Pemrose Insurance, 2026-06-22 - [`transcripts/call-034.md:10`](transcripts/call-034.md#L10)

**Why this disposition**

- Priority `P2`: tied to a compliance or renewal driver
- De-dup: no tracked issue in the same area

<details><summary>Full ticket body as it would be filed</summary>

```
h2. What's happening
Fine, genuinely fine. We've got about 400 people enrolled, mostly claims and
underwriting managers. Usage is steady, no complaints about the coaches. I'm the systems
person, not the program person, so I mostly hear about it when something breaks.

h2. Details
* *Trigger:* genuinely fine
* *Symptom:* We've got about 400 people enrolled
* *Scope:* reported by the external participant on this call
* *Workaround:* none reported
* *Component:* other

h2. Priority: P2
tied to a compliance or renewal driver
_Note: the customer framed this as high urgency. Priority is set from measured impact, not from how it was raised. Override at review if the relationship context warrants it._

h2. Evidence
_Verbatim from the call recording. Quotes are read from the transcript file, not generated._

*Pemrose Insurance* -- Gloria, 2026-06-22 ([call-034|transcripts/call-034.md])
{quote}Fine, genuinely fine. We've got about 400 people enrolled, mostly claims and underwriting managers. Usage is steady, no complaints about the coaches. I'm the systems person, not the program person, so I mostly hear about it when something breaks.{quote}
_transcripts/call-034.md:10 (turn 6)_

----
_Filed from call transcript by the call-signal triage pipeline after human review. Source of truth: transcripts/call-034.md_
```

</details>

`approve a3509ddfaf9e964e` &nbsp; `reject a3509ddfaf9e964e`

---

## 14. Azure AD users hit an infinite redirect loop after a password change

**FILE NEW TICKET** &nbsp;|&nbsp; `P2` &nbsp;|&nbsp; Bug &nbsp;|&nbsp; `auth-sso` &nbsp;|&nbsp; `c8b6e8128bc7dfe1`

**What the customer said**

> When one of our users changes their network password — our regular rotation — and then hits your app, they get stuck in a login loop. And I want to walk you through the exact loop, because I need you to file this precisely.
>
> User changes their password on our side. Then they open your app. Your app bounces them to our IdP to authenticate. The IdP authenticates them just fine — new password, correct, no problem, IdP says "yes, this is them." IdP sends them back to your app. And then your side immediately bounces them right back to the IdP again. And around, and around. Authenticate, return, bounce, authenticate, return, bounce. Infinite.
>
> -- **Renee**, Atlas Financial, 2026-06-20 - [`transcripts/call-010.md:32`](transcripts/call-010.md#L32)

**Why this disposition**

- Priority `P2`: blocks a workflow but a workaround exists
- De-dup: checked `PROJ-064`, all distinct
  - `PROJ-064` (SSO session expires earlier than the configured lifetime for...) - same area but symptom does not match (trigger 0.29, symptom 0.11)

<details><summary>Full ticket body as it would be filed</summary>

```
h2. What's happening
After a user changes their network password, opening the app bounces them to the IdP,
which authenticates them successfully, returns them, and the app immediately bounces
them back again, indefinitely. They never reach the app at all. Clearing cookies for the
domain is the only escape. Five of forty pilot users so far, limited only by staggered
rotation dates; at full rollout a ninety-day policy puts all four hundred users through
this every quarter.

h2. Details
* *Trigger:* an Azure AD federated user logging in after changing their network password
* *Symptom:* an infinite redirect loop between the app and the IdP that blocks entry entirely
* *Scope:* all Azure AD federated users, every password rotation cycle
* *Workaround:* clear browser cookies for the domain, which requires a helpdesk call
* *Component:* auth-sso

h2. Priority: P2
blocks a workflow but a workaround exists
_Note: the customer framed this as high urgency. Priority is set from measured impact, not from how it was raised. Override at review if the relationship context warrants it._

h2. Evidence
_Verbatim from the call recording. Quotes are read from the transcript file, not generated._

*Atlas Financial* -- Renee, 2026-06-20 ([call-010|transcripts/call-010.md])
{quote}When one of our users changes their network password — our regular rotation — and then hits your app, they get stuck in a login loop. And I want to walk you through the exact loop, because I need you to file this precisely.{quote}
_transcripts/call-010.md:28 (turn 24)_
{quote}User changes their password on our side. Then they open your app. Your app bounces them to our IdP to authenticate. The IdP authenticates them just fine — new password, correct, no problem, IdP says "yes, this is them." IdP sends them back to your app. And then your side immediately bounces them right back to the IdP again. And around, and around. Authenticate, return, bounce, authenticate, return, bounce. Infinite.{quote}
_transcripts/call-010.md:32 (turn 28)_
{quote}That's it exactly. They never get in. Not "logged in briefly then out" — they never reach the app at all. It just spins between your login and our IdP until they give up.{quote}
_transcripts/call-010.md:34 (turn 30)_
{quote}Clearing browser cookies for your domain breaks the loop. Once they wipe your cookies, they log in clean and they're fine. But that's a support call every single time — you can't tell four hundred people "clear your cookies" and expect that to scale.{quote}
_transcripts/call-010.md:38 (turn 34)_
{quote}Two — the symptom is the opposite shape. In the Okta issue, people are being logged out early but they can get back in. In ours, nobody is being logged out early at all — they can't get in in the first place after a password change. It's not a premature expiry, it's a hard redirect loop that blocks entry entirely until cookies are cleared. Early-logout-but-you-can-return versus cannot-enter-at-all. Different shape entirely.{quote}
_transcripts/call-010.md:44 (turn 40)_

h2. De-duplication
Checked against these tracked issues and judged distinct:
* PROJ-064 -- SSO session expires earlier than the configured lifetime for Okta-federated users
** same area but symptom does not match (trigger 0.29, symptom 0.11) (similarity 0.188, by structured)

----
_Filed from call transcript by the call-signal triage pipeline after human review. Source of truth: transcripts/call-010.md_
```

</details>

`approve c8b6e8128bc7dfe1` &nbsp; `reject c8b6e8128bc7dfe1`

---

## 15. Session-completed webhook event carrying member ID and timestamp

**FILE NEW TICKET** &nbsp;|&nbsp; `P2` &nbsp;|&nbsp; Feature &nbsp;|&nbsp; `webhooks` &nbsp;|&nbsp; `f08cadf122952638`

**What the customer said**

> Exactly. Corporate decided the therapy-dog and workplace-safety certification sessions count as professional development, which means they need to show up in the system of record alongside everything else. Right now that's a monthly manual entry job — someone on my team exports participation from your side and hand-keys it into Cornerstone. It's tedious and it's error-prone.
>
> Right. And my integrations guy was specific about what he needs, so let me relay it precisely — he wrote it down for me. He said, quote: "Ask if they can send a session-completed webhook with the member ID and timestamp; we'll do the rest." That's the ask. When a member completes a training session, your system fires an event to us — a webhook — carrying the member ID and the completion timestamp, and Cornerstone consumes it and records the participation automatically.
>
> -- **Hank**, Ridgeway Manufacturing, 2026-06-22 - [`transcripts/call-013.md:44`](transcripts/call-013.md#L44)

**Why this disposition**

- Priority `P2`: tied to a compliance or renewal driver
- De-dup: no tracked issue in the same area

<details><summary>Full ticket body as it would be filed</summary>

```
h2. What's happening
The customer's LMS, Cornerstone, is their system of record for training compliance
including OSHA. Participation is currently hand-keyed in monthly. Their integrations
engineer asks for a session-completed webhook carrying the member ID and completion
timestamp so Cornerstone can record participation automatically.

h2. Details
* *Trigger:* a member completing a training session
* *Symptom:* no session-completed event is emitted so participation must be hand-keyed into the LMS
* *Scope:* all training participation records for compliance reporting
* *Workaround:* manual monthly data entry into Cornerstone
* *Component:* webhooks

h2. Priority: P2
tied to a compliance or renewal driver

h2. Evidence
_Verbatim from the call recording. Quotes are read from the transcript file, not generated._

*Ridgeway Manufacturing* -- Hank, 2026-06-22 ([call-013|transcripts/call-013.md])
{quote}Exactly. Corporate decided the therapy-dog and workplace-safety certification sessions count as professional development, which means they need to show up in the system of record alongside everything else. Right now that's a monthly manual entry job — someone on my team exports participation from your side and hand-keys it into Cornerstone. It's tedious and it's error-prone.{quote}
_transcripts/call-013.md:42 (turn 38)_
{quote}Right. And my integrations guy was specific about what he needs, so let me relay it precisely — he wrote it down for me. He said, quote: "Ask if they can send a session-completed webhook with the member ID and timestamp; we'll do the rest." That's the ask. When a member completes a training session, your system fires an event to us — a webhook — carrying the member ID and the completion timestamp, and Cornerstone consumes it and records the participation automatically.{quote}
_transcripts/call-013.md:44 (turn 40)_
{quote}That's it word for word. Member ID, timestamp, on session completion. He said he'll handle the Cornerstone side, he just needs us to emit the event.{quote}
_transcripts/call-013.md:46 (turn 42)_

----
_Filed from call transcript by the call-signal triage pipeline after human review. Source of truth: transcripts/call-013.md_
```

</details>

`approve f08cadf122952638` &nbsp; `reject f08cadf122952638`

---

## 16. Duplicate webhook deliveries with no idempotency key to de-duplicate against

**ATTACH CORROBORATION** &nbsp;|&nbsp; `P3` &nbsp;|&nbsp; Bug &nbsp;|&nbsp; `webhooks` &nbsp;|&nbsp; `1142ed602851ae20`

**What the customer said**

> We consume your webhooks into our internal data platform — session events, membership changes, that kind of thing. Devraj's team says some events are being delivered twice. Same event, two deliveries, occasionally. Not every event, not on a schedule he can predict, just... sometimes the same one shows up twice.
>
> Their pipeline mostly dedupes it already — they've got logic that catches most of the doubles. But "mostly" is doing a lot of work in that sentence, and Devraj hates heuristic dedup. His actual ask, and I wrote it down so I'd get it right: can you put idempotency keys on the webhook payload, so his team can dedupe deterministically instead of guessing based on content and timing?
>
> -- **Jordan**, Vanta Retail, 2026-06-18 - [`transcripts/call-005.md:40`](transcripts/call-005.md#L40)

**Why this disposition**

- Priority `P3`: no data-correctness, workflow-blocking or compliance impact identified
- De-dup: duplicate of PROJ-087 (In Progress): Identical trigger (outbound webhook delivery) and identical symptom (duplicate delivery of the same event); the wording differs but the defect does not. [decided by model]

<details><summary>Full ticket body as it would be filed</summary>

```
h2. What's happening
The customer's data platform receives the same webhook event more than once,
intermittently. Their pipeline de-duplicates heuristically on payload content and
timing. Their platform engineer asks for an idempotency key on the payload so
redeliveries can be dropped deterministically.

h2. Details
* *Trigger:* outbound webhook delivery to the customer endpoint
* *Symptom:* the same event is delivered more than once, occasionally and unpredictably
* *Scope:* all webhook consumers on this account
* *Workaround:* heuristic de-duplication on payload contents in the customer's pipeline
* *Component:* webhooks

h2. Priority: P3
no data-correctness, workflow-blocking or compliance impact identified

h2. Evidence
_Verbatim from the call recording. Quotes are read from the transcript file, not generated._

*Vanta Retail* -- Jordan, 2026-06-18 ([call-005|transcripts/call-005.md])
{quote}We consume your webhooks into our internal data platform — session events, membership changes, that kind of thing. Devraj's team says some events are being delivered twice. Same event, two deliveries, occasionally. Not every event, not on a schedule he can predict, just... sometimes the same one shows up twice.{quote}
_transcripts/call-005.md:38 (turn 34)_
{quote}Their pipeline mostly dedupes it already — they've got logic that catches most of the doubles. But "mostly" is doing a lot of work in that sentence, and Devraj hates heuristic dedup. His actual ask, and I wrote it down so I'd get it right: can you put idempotency keys on the webhook payload, so his team can dedupe deterministically instead of guessing based on content and timing?{quote}
_transcripts/call-005.md:40 (turn 36)_
{quote}Exactly. Right now he's fingerprinting the payload contents and hoping two genuinely-distinct events never look identical, which he describes as "a bug waiting to happen."{quote}
_transcripts/call-005.md:42 (turn 38)_

h2. Relates to PROJ-087
duplicate of PROJ-087 (In Progress): Identical trigger (outbound webhook delivery) and identical symptom (duplicate delivery of the same event); the wording differs but the defect does not. [decided by model]

----
_Filed from call transcript by the call-signal triage pipeline after human review. Source of truth: transcripts/call-005.md_
```

</details>

`approve 1142ed602851ae20` &nbsp; `reject 1142ed602851ae20`

---

## 17. Password-reset emails delayed up to thirty minutes during peak

**ATTACH CORROBORATION** &nbsp;|&nbsp; `P3` &nbsp;|&nbsp; Bug &nbsp;|&nbsp; `notifications-email` &nbsp;|&nbsp; `a2bc8b65273abc84`

**What the customer said**

> We onboarded a batch of new hires two weeks ago — twenty-three people, all at once, first Monday of the month. And several of them told me the password-reset email just... didn't come. Or came way late.
>
> That's the thing — not never. Late. One person said she requested it, went and got coffee, came back twenty-something minutes later, and it was sitting there. Another said his took like half an hour. A couple got it fine. It wasn't everybody.
>
> -- **Marcus**, Juniper Media, 2026-06-16 - [`transcripts/call-015.md:32`](transcripts/call-015.md#L32)

**Why this disposition**

- Priority `P3`: no data-correctness, workflow-blocking or compliance impact identified
- De-dup: duplicate of PROJ-142 (Open): trigger (0.71) and symptom (0.88) both match [decided by structured]

<details><summary>Full ticket body as it would be filed</summary>

```
h2. What's happening
During a batch onboarding, twenty-three new hires requested password resets within ten
minutes and several waited twenty to thirty minutes for the email. Nobody was
permanently locked out and resets are instant off-peak. Specific to the reset email;
invite emails were fine.

h2. Details
* *Trigger:* requesting a password reset during morning peak when many requests cluster
* *Symptom:* password reset emails are delayed up to thirty minutes during peak hours
* *Scope:* users resetting passwords during a peak window
* *Workaround:* stagger the onboarding emails so resets spread out
* *Component:* notifications-email

h2. Priority: P3
no data-correctness, workflow-blocking or compliance impact identified

h2. Evidence
_Verbatim from the call recording. Quotes are read from the transcript file, not generated._

*Juniper Media* -- Marcus, 2026-06-16 ([call-015|transcripts/call-015.md])
{quote}We onboarded a batch of new hires two weeks ago — twenty-three people, all at once, first Monday of the month. And several of them told me the password-reset email just... didn't come. Or came way late.{quote}
_transcripts/call-015.md:30 (turn 26)_
{quote}That's the thing — not never. Late. One person said she requested it, went and got coffee, came back twenty-something minutes later, and it was sitting there. Another said his took like half an hour. A couple got it fine. It wasn't everybody.{quote}
_transcripts/call-015.md:32 (turn 28)_
{quote}Right. And I want to be careful — nobody was locked out permanently. Everybody got in eventually. It just made the kickoff look janky. I stood up in front of the new hires and said "check your email for the reset link" and then we all sat there for twenty minutes while nothing happened for half the room.{quote}
_transcripts/call-015.md:36 (turn 32)_
{quote}That's my hunch, yeah. It felt like peak-hours congestion. When I test it right now on my own account, boom, instant. But 9am Monday with everybody hammering it, that's when it dragged.{quote}
_transcripts/call-015.md:42 (turn 38)_

h2. Relates to PROJ-142
duplicate of PROJ-142 (Open): trigger (0.71) and symptom (0.88) both match [decided by structured]

----
_Filed from call transcript by the call-signal triage pipeline after human review. Source of truth: transcripts/call-015.md_
```

</details>

`approve a2bc8b65273abc84` &nbsp; `reject a2bc8b65273abc84`

---

## 18. Deactivating a member mid-session strands the mobile app on a blank white screen

**FILE NEW TICKET** &nbsp;|&nbsp; `P3` &nbsp;|&nbsp; Bug &nbsp;|&nbsp; `other` &nbsp;|&nbsp; `12ca753b160f7323`

**What the customer said**

> When an admin deactivates a member while that member happens to be in the app — like, actively using it, mid-session on their phone — the app doesn't handle it gracefully. It goes to a blank white screen. No message, no "your account has been deactivated," no logout, no nothing. Just a white screen. A void.
>
> White. Blank. And it stays white — it doesn't recover on its own. What fixes it is force-quitting the app and reopening it, and then you finally get the "account inactive" screen, which is the thing that should have appeared in the first place. The correct screen exists. The app just doesn't get you there if you were mid-session when the deactivation hit — it strands you on white until you force-quit.
>
> -- **Gloria**, Sunrise Hospitality, 2026-06-22 - [`transcripts/call-014.md:44`](transcripts/call-014.md#L44)

**Why this disposition**

- Priority `P3`: no data-correctness, workflow-blocking or compliance impact identified
- De-dup: no tracked issue in the same area

<details><summary>Full ticket body as it would be filed</summary>

```
h2. What's happening
When an admin deactivates a member who has an active mobile session, the app goes to a
blank white screen with no message and does not recover. Force-quitting and reopening
finally shows the correct 'account inactive' screen. Six or seven hit this during the
May seasonal deactivation batch and two called the helpdesk believing the app was
broken.

h2. Details
* *Trigger:* deactivating a member who has an active mobile session open
* *Symptom:* the mobile app goes to a blank white screen and does not route to the account inactive screen
* *Scope:* members deactivated while mid-session; six or seven in the May batch
* *Workaround:* force-quit and reopen the app
* *Component:* other

h2. Priority: P3
no data-correctness, workflow-blocking or compliance impact identified

h2. Evidence
_Verbatim from the call recording. Quotes are read from the transcript file, not generated._

*Sunrise Hospitality* -- Gloria, 2026-06-22 ([call-014|transcripts/call-014.md])
{quote}When an admin deactivates a member while that member happens to be in the app — like, actively using it, mid-session on their phone — the app doesn't handle it gracefully. It goes to a blank white screen. No message, no "your account has been deactivated," no logout, no nothing. Just a white screen. A void.{quote}
_transcripts/call-014.md:42 (turn 38)_
{quote}White. Blank. And it stays white — it doesn't recover on its own. What fixes it is force-quitting the app and reopening it, and then you finally get the "account inactive" screen, which is the thing that should have appeared in the first place. The correct screen exists. The app just doesn't get you there if you were mid-session when the deactivation hit — it strands you on white until you force-quit.{quote}
_transcripts/call-014.md:44 (turn 40)_
{quote}We know of six or seven, all during the May deactivation batch. It's not a huge number. But two of them called our IT helpdesk saying the app was "broken" — they didn't know they'd been deactivated, they just saw their app die into a white screen and assumed it crashed. That's how it climbed up to my ops manager, through IT tickets.{quote}
_transcripts/call-014.md:46 (turn 42)_
{quote}Right, and here's why it bugs me more than the number suggests. It's not the volume — six or seven isn't a crisis. It's that a blank white screen with no explanation is the worst possible goodbye. These are seasonal staff we genuinely want back next season. We invest in rehiring the good ones. And their last interaction with our tooling was a white void that made them think something was broken. That's a terrible final impression to leave with someone you're hoping returns.{quote}
_transcripts/call-014.md:48 (turn 44)_

----
_Filed from call transcript by the call-signal triage pipeline after human review. Source of truth: transcripts/call-014.md_
```

</details>

`approve 12ca753b160f7323` &nbsp; `reject 12ca753b160f7323`

---

## 19. Outbound email footer misspells the company name as 'BetterBrak'

**FILE NEW TICKET** &nbsp;|&nbsp; `P3` &nbsp;|&nbsp; Bug &nbsp;|&nbsp; `notifications-email` &nbsp;|&nbsp; `188e03f154c1f324`

**What the customer said**

> She noticed the confirmation emails your system sends have "BetterBrak" — B-E-T-T-E-R-B-R-A-K — in the footer. Your own company name, misspelled, right there in the email footer. BetterBrak.
>
> Oh yes. BetterBrak. Every confirmation email, apparently.
>
> -- **Marcus**, Northwind Logistics, 2026-06-19 - [`transcripts/call-008.md:50`](transcripts/call-008.md#L50)

**Why this disposition**

- Priority `P3`: cosmetic defect: real but trivial, floored at P3 regardless of how it was framed (customer framed it as high urgency)
- De-dup: checked `PROJ-142`, all distinct
  - `PROJ-142` (Password-reset emails delayed up to 30 minutes during peak h...) - same area but symptom does not match (trigger 0.33, symptom 0.00)

<details><summary>Full ticket body as it would be filed</summary>

```
h2. What's happening
Confirmation emails carry 'BetterBrak' in the footer instead of BetterBark. Present on
every confirmation email. The customer's comms director called it a P0 brand
catastrophe; nothing is functionally broken.

h2. Details
* *Trigger:* any outbound confirmation email
* *Symptom:* the footer misspells the company name as BetterBrak
* *Scope:* every confirmation email sent to every customer
* *Workaround:* none reported
* *Component:* notifications-email

h2. Priority: P3
cosmetic defect: real but trivial, floored at P3 regardless of how it was framed (customer framed it as high urgency)
_Note: the customer framed this as high urgency. Priority is set from measured impact, not from how it was raised. Override at review if the relationship context warrants it._

h2. Evidence
_Verbatim from the call recording. Quotes are read from the transcript file, not generated._

*Northwind Logistics* -- Marcus, 2026-06-19 ([call-008|transcripts/call-008.md])
{quote}She noticed the confirmation emails your system sends have "BetterBrak" — B-E-T-T-E-R-B-R-A-K — in the footer. Your own company name, misspelled, right there in the email footer. BetterBrak.{quote}
_transcripts/call-008.md:48 (turn 44)_
{quote}Oh yes. BetterBrak. Every confirmation email, apparently.{quote}
_transcripts/call-008.md:50 (turn 46)_
{quote}Every one. And she called it, quote, "a P0 brand catastrophe" and said she's, quote, "genuinely alarmed." She used the word alarmed. About a typo. I told her I'd relay it with a straight face and I am now doing that, and I want you to know that face is costing me a great deal.{quote}
_transcripts/call-008.md:52 (turn 48)_

h2. De-duplication
Checked against these tracked issues and judged distinct:
* PROJ-142 -- Password-reset emails delayed up to 30 minutes during peak hours
** same area but symptom does not match (trigger 0.33, symptom 0.00) (similarity 0.125, by structured)

----
_Filed from call transcript by the call-signal triage pipeline after human review. Source of truth: transcripts/call-008.md_
```

</details>

`approve 188e03f154c1f324` &nbsp; `reject 188e03f154c1f324`

---

## 20. Right. And what I'd love

**FILE NEW TICKET** &nbsp;|&nbsp; `P3` &nbsp;|&nbsp; Feature &nbsp;|&nbsp; `calendar` &nbsp;|&nbsp; `4282b074a0e4d509`

**What the customer said**

> Right. And what I'd love — and this is my ask — is for the coach's calendar hold to auto-release if the member no-shows, say, ten minutes in. Give the person a ten-minute grace window, sure, people run late. But if they haven't joined after ten minutes, free up the rest of that slot so it can go back into availability. Then someone else can book it, or the coach can reclaim the time.
>
> -- **Owen**, Fairbanks Consulting, 2026-06-29 - [`transcripts/call-132.md:43`](transcripts/call-132.md#L43)

**Why this disposition**

- Priority `P3`: no data-correctness, workflow-blocking or compliance impact identified
- De-dup: no tracked issue in the same area

<details><summary>Full ticket body as it would be filed</summary>

```
h2. What's happening
Right. And what I'd love — and this is my ask — is for the coach's calendar hold to
auto-release if the member no-shows, say, ten minutes in. Give the person a ten-minute
grace window, sure, people run late. But if they haven't joined after ten minutes, free
up the rest of that slot so it can go back into availability. Then someone else can book
it, or the coach can reclaim the time.

h2. Details
* *Trigger:* And what I'd love
* *Symptom:* and this is my ask
* *Scope:* reported by the external participant on this call
* *Workaround:* none reported
* *Component:* calendar

h2. Priority: P3
no data-correctness, workflow-blocking or compliance impact identified

h2. Evidence
_Verbatim from the call recording. Quotes are read from the transcript file, not generated._

*Fairbanks Consulting* -- Owen, 2026-06-29 ([call-132|transcripts/call-132.md])
{quote}Right. And what I'd love — and this is my ask — is for the coach's calendar hold to auto-release if the member no-shows, say, ten minutes in. Give the person a ten-minute grace window, sure, people run late. But if they haven't joined after ten minutes, free up the rest of that slot so it can go back into availability. Then someone else can book it, or the coach can reclaim the time.{quote}
_transcripts/call-132.md:43 (turn 39)_

----
_Filed from call transcript by the call-signal triage pipeline after human review. Source of truth: transcripts/call-132.md_
```

</details>

`approve 4282b074a0e4d509` &nbsp; `reject 4282b074a0e4d509`

---

## 21. Honestly? I think it's more shiny than real

**FILE NEW TICKET** &nbsp;|&nbsp; `P3` &nbsp;|&nbsp; Bug &nbsp;|&nbsp; `scheduling` &nbsp;|&nbsp; `8bc7fa2489847599`

**What the customer said**

> Honestly? I think it's more shiny than real. Our members book sessions in advance, they're not sitting there at 3am needing live chat about their coaching. But my CHRO heard "twenty-four-seven" and it stuck.
>
> -- **Constance Reyes**, Oakhaven Senior Living, 2026-06-25 - [`transcripts/call-123.md:38`](transcripts/call-123.md#L38)

**Why this disposition**

- Priority `P3`: no data-correctness, workflow-blocking or compliance impact identified
- De-dup: no tracked issue in the same area

<details><summary>Full ticket body as it would be filed</summary>

```
h2. What's happening
Honestly? I think it's more shiny than real. Our members book sessions in advance,
they're not sitting there at 3am needing live chat about their coaching. But my CHRO
heard "twenty-four-seven" and it stuck.

h2. Details
* *Trigger:* Honestly? I think it's more shiny than real
* *Symptom:* Our members book sessions in advance
* *Scope:* reported by the external participant on this call
* *Workaround:* none reported
* *Component:* scheduling

h2. Priority: P3
no data-correctness, workflow-blocking or compliance impact identified
_Note: the customer framed this as high urgency. Priority is set from measured impact, not from how it was raised. Override at review if the relationship context warrants it._

h2. Evidence
_Verbatim from the call recording. Quotes are read from the transcript file, not generated._

*Oakhaven Senior Living* -- Constance Reyes, 2026-06-25 ([call-123|transcripts/call-123.md])
{quote}Honestly? I think it's more shiny than real. Our members book sessions in advance, they're not sitting there at 3am needing live chat about their coaching. But my CHRO heard "twenty-four-seven" and it stuck.{quote}
_transcripts/call-123.md:38 (turn 34)_

----
_Filed from call transcript by the call-signal triage pipeline after human review. Source of truth: transcripts/call-123.md_
```

</details>

`approve 8bc7fa2489847599` &nbsp; `reject 8bc7fa2489847599`

---

## 22. Exactly. And here's the part that bugs me

**FILE NEW TICKET** &nbsp;|&nbsp; `P3` &nbsp;|&nbsp; Bug &nbsp;|&nbsp; `scheduling` &nbsp;|&nbsp; `910d10d46d8d8cb6`

**What the customer said**

> Exactly. And here's the part that bugs me — I have other consultants who would happily grab that slot. Like, I'll have someone messaging me saying "can I get a session this week, I'm slammed but I have a gap Thursday at 2," and there's a coach sitting alone in an empty video room at Thursday at 2 because someone else no-showed. But the system has that slot locked to the no-show for the whole hour, so nobody can claim it.
>
> -- **Owen**, Fairbanks Consulting, 2026-06-29 - [`transcripts/call-132.md:41`](transcripts/call-132.md#L41)

**Why this disposition**

- Priority `P3`: no data-correctness, workflow-blocking or compliance impact identified
- De-dup: no tracked issue in the same area

<details><summary>Full ticket body as it would be filed</summary>

```
h2. What's happening
Exactly. And here's the part that bugs me — I have other consultants who would happily
grab that slot. Like, I'll have someone messaging me saying "can I get a session this
week, I'm slammed but I have a gap Thursday at 2," and there's a coach sitting alone in
an empty video room at Thursday at 2 because someone else no-showed. But the system has
that slot locked to the no-show for the whole hour,

h2. Details
* *Trigger:* And here's the part that bugs me
* *Symptom:* I have other consultants who would happily grab that slot
* *Scope:* reported by the external participant on this call
* *Workaround:* none reported
* *Component:* scheduling

h2. Priority: P3
no data-correctness, workflow-blocking or compliance impact identified
_Note: the customer framed this as high urgency. Priority is set from measured impact, not from how it was raised. Override at review if the relationship context warrants it._

h2. Evidence
_Verbatim from the call recording. Quotes are read from the transcript file, not generated._

*Fairbanks Consulting* -- Owen, 2026-06-29 ([call-132|transcripts/call-132.md])
{quote}Exactly. And here's the part that bugs me — I have other consultants who would happily grab that slot. Like, I'll have someone messaging me saying "can I get a session this week, I'm slammed but I have a gap Thursday at 2," and there's a coach sitting alone in an empty video room at Thursday at 2 because someone else no-showed. But the system has that slot locked to the no-show for the whole hour, so nobody can claim it.{quote}
_transcripts/call-132.md:41 (turn 37)_

----
_Filed from call transcript by the call-signal triage pipeline after human review. Source of truth: transcripts/call-132.md_
```

</details>

`approve 910d10d46d8d8cb6` &nbsp; `reject 910d10d46d8d8cb6`

---
