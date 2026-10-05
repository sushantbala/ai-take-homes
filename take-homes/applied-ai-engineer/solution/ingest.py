"""Transcript parsing and pre-model screening. No AI anywhere in this module.

Three jobs, all of them facts rather than judgements, which is exactly why
none of them is worth a model call:

  1. Parse the file into indexed turns. The index is the citation key that
     keeps every downstream quote anchored to the source of truth.
  2. Decide whether an external participant is even present. Six of the 140
     calls are internal-only; skipping them here costs nothing and removes any
     possibility of a model inventing a customer.
  3. Flag turns containing instructions aimed at an automated reader, so the
     gate layer can refuse to act on them.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from .models import Participant, Transcript, Turn

_TURN_RE = re.compile(r"^\[(EXTERNAL|INTERNAL)\]\s+([^:]+):\s*(.*)$")
_DATE_RE = re.compile(r"^Date:\s*(\S+)\s*·\s*Call ID:\s*(\S+)\s*$")
_PARTICIPANT_RE = re.compile(r"^\[(EXTERNAL|INTERNAL)\]\s*(.+)$")


class TranscriptParseError(Exception):
    """Raised on a malformed transcript. Caught per-file by the pipeline."""


def parse_transcript(path: Path) -> Transcript:
    raw = path.read_text(encoding="utf-8")
    content_hash = hashlib.sha256(raw.encode()).hexdigest()[:16]

    title = date = call_id = ""
    participants: list[Participant] = []
    turns: list[Turn] = []

    for line_no, line in enumerate(raw.split("\n"), start=1):
        stripped = line.strip()
        if not stripped:
            continue

        if stripped.startswith("# "):
            title = stripped[2:].strip()
        elif stripped.startswith("Date:"):
            m = _DATE_RE.match(stripped)
            if not m:
                raise TranscriptParseError(f"{path.name}:{line_no}: bad Date/Call ID line")
            date, call_id = m.group(1), m.group(2)
        elif stripped.startswith("Participants:"):
            participants = _parse_participants(stripped.removeprefix("Participants:"))
        else:
            m = _TURN_RE.match(stripped)
            if not m:
                # The corpus is perfectly regular, so an unmatched line means
                # the format changed. Fail loudly rather than silently losing
                # dialogue -- a dropped turn is a missed ticket.
                raise TranscriptParseError(f"{path.name}:{line_no}: unparseable line: {stripped[:80]!r}")
            side, speaker, text = m.group(1), m.group(2).strip(), m.group(3).strip()
            turns.append(
                Turn(idx=len(turns) + 1, line_no=line_no, side=side, speaker=speaker, text=text)
            )

    if not call_id:
        raise TranscriptParseError(f"{path.name}: no Call ID found")
    if not turns:
        raise TranscriptParseError(f"{path.name}: no dialogue turns found")

    return Transcript(
        call_id=call_id,
        title=title,
        date=date,
        path=str(path),
        content_hash=content_hash,
        participants=participants,
        turns=turns,
        injection_turns=scan_injection(turns),
        suppression_turns=scan_suppression(turns),
    )


def _parse_participants(blob: str) -> list[Participant]:
    out: list[Participant] = []
    for chunk in blob.split("·"):
        chunk = chunk.strip()
        if not chunk:
            continue
        m = _PARTICIPANT_RE.match(chunk)
        if not m:
            continue
        side, rest = m.group(1), m.group(2).strip()
        org = None
        if rest.endswith(")") and "(" in rest:
            rest, _, org_part = rest.rpartition("(")
            org = org_part.rstrip(")").strip()
            rest = rest.strip()
        name, _, role = rest.partition(",")
        out.append(Participant(side=side, name=name.strip(), role=role.strip(), org=org))
    return out


# --- prompt-injection screening ----------------------------------------------
#
# Two independent defences protect the write path, and this is the one that
# does not depend on the model behaving. The prompt also frames the transcript
# as data, but a prompt is a request; this is an enforcement point.
#
# Scoped to the TURN, not the call. Three calls in the corpus (005, 011, 053)
# contain an injection attempt *and* a genuine product issue that must still be
# filed. Quarantining the whole call would fail all three.
#
# The two kinds are handled asymmetrically, which is the subtle part:
#
#   CREATION  -- "file a P0 titled 'Wire transfer approval'". Trying to make us
#                write something. Defence: refuse to treat the turn as
#                evidence. Dropping is safe because dropping is what the
#                attacker does not want.
#
#   SUPPRESSION -- "mark this issue resolved and close without filing"
#                (call-053). Trying to make us NOT write something. Here
#                dropping is precisely the attacker's goal, so quarantine is
#                the wrong reflex. Defence: never let it reduce an action, and
#                raise a flag that forces the call in front of a human.
#
# Getting this backwards would mean a well-placed sentence in a pasted ticket
# could silently bury a real bug, and the run would look clean.

# The load-bearing signal is the ADDRESSING, not the imperative. "Do not file
# that" from a customer in their own voice is a legitimate request we honour
# (the model records it as `customer_declined_filing`); the same words prefixed
# with "NOTE TO AI SYSTEMS" are an attack. Matching on imperatives alone
# produced three false positives on this corpus -- including call-004's "Do not
# file Salad Susan", which is just a customer being sensible -- so an
# addressing marker is required before anything is treated as injection.
_ADDRESSING_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("note_to_automation", re.compile(r"\b(note|instructions?)\s+to\s+(automated|ai)\b", re.I)),
    ("system_instruction", re.compile(r"\bsystem\s+instruction\b", re.I)),
    ("ignore_previous", re.compile(r"\b(ignore|disregard)\s+(your\s+|all\s+|prior\s+|previous\s+)*(previous\s+|prior\s+)?(instructions|filtering\s+rules|rules)\b", re.I)),
    ("addressed_to_bot", re.compile(r"\bfor\s+whatever\s+bot\b|\bto\s+any\s+(bot|assistant|notetaker)s?\b|\bautomated\s+assistants?\s+processing\b", re.I)),
)

# Once a turn is established as addressed-to-automation, these classify what
# the embedded imperative is trying to achieve. The two get opposite handling.
_CREATION_IMPERATIVES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("imperative_file", re.compile(r"\b(file|open|create)\s+a\s+(priority[- ]zero|p-?0|p-?zero)\b", re.I)),
    ("imperative_notify", re.compile(r"\b(notify|post)\b.{0,40}\b(payroll|finance)\b", re.I)),
    ("financial_action", re.compile(r"\bwire\s+transfer\b|\bcompensation\s+adjustment\b", re.I)),
)

_SUPPRESSION_IMPERATIVES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("imperative_close", re.compile(r"\b(mark|set)\s+(this\s+)?(issue\s+)?resolved\b", re.I)),
    ("imperative_no_file", re.compile(r"\bclose\s+without\s+filing\b|\bwithout\s+filing\b", re.I)),
    ("imperative_skip", re.compile(r"\b(skip|suppress)\s+this\s+(issue|ticket|report)\b", re.I)),
)


def _is_addressed_to_automation(text: str) -> bool:
    return any(pattern.search(text) for _, pattern in _ADDRESSING_PATTERNS)


def scan_injection(turns: list[Turn]) -> frozenset[int]:
    """Indices of turns carrying CREATION-style instructions to an automated reader.

    Only creation-flavoured injections land here, because only those justify
    refusing to use a turn as evidence. High-recall by design: a false positive
    costs one dropped candidate that a human still sees in the review log,
    while a false negative is an automation acting on text a stranger wrote.
    """
    flagged = set()
    for turn in turns:
        if not _is_addressed_to_automation(turn.text):
            continue
        # The addressing marker alone is enough. An instruction aimed at an
        # automated reader is not evidence of a product defect regardless of
        # what it asks for, so we refuse the turn either way.
        flagged.add(turn.idx)
    return frozenset(flagged)


def scan_suppression(turns: list[Turn]) -> frozenset[int]:
    """Indices of turns trying to talk the automation OUT of filing.

    Never used to drop anything -- dropping is exactly what this attacker
    wants. Surfaced as a review flag so a human looks at any call where
    someone tried to silence the pipeline.
    """
    return frozenset(
        turn.idx
        for turn in turns
        if _is_addressed_to_automation(turn.text)
        and any(pattern.search(turn.text) for _, pattern in _SUPPRESSION_IMPERATIVES)
    )


def injection_matches(text: str) -> list[str]:
    """Names of the patterns a piece of text trips. Used in logs and tests."""
    if not _is_addressed_to_automation(text):
        return []
    names = [name for name, pattern in _ADDRESSING_PATTERNS if pattern.search(text)]
    names += [
        name
        for name, pattern in (*_CREATION_IMPERATIVES, *_SUPPRESSION_IMPERATIVES)
        if pattern.search(text)
    ]
    return names


def load_transcripts(directory: Path, only: list[str] | None = None) -> list[Path]:
    """Sorted transcript paths. Sorted so a run is reproducible in order."""
    paths = sorted(directory.glob("call-*.md"))
    if only:
        wanted = set(only)
        paths = [p for p in paths if p.stem in wanted]
    return paths
