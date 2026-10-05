"""The model seam.

Everything the pipeline knows about "an LLM" is this one interface: give it a
task name, a cache key and a rendered prompt, get back parsed JSON. That
narrow waist is what lets the whole system be built, tested and demonstrated
with no API key, and it is also what I would build with a key -- the
record/replay provider below is the same pattern you want in CI so tests don't
pay per-token or inherit the model's non-determinism.

Four implementations:

  ReplayProvider       reads recorded/authored responses from disk. Default.
  RecordingProvider    wraps a live provider and writes responses to disk.
  AnthropicProvider    the real one. Untested against the API in this build;
                       see WRITEUP.md -- it is wired, not validated.
  AdversarialProvider  deliberately returns malformed and malicious output to
                       prove the deterministic gates actually hold.

The cache key always includes the transcript content hash and the prompt
version, so editing a prompt invalidates recorded responses instead of
silently replaying stale ones.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from .. import config


class LLMError(Exception):
    """Any failure to obtain a usable response. Caught per-transcript."""


class ResponseNotRecorded(LLMError):
    """Replay miss. Expected for the 125 holdout calls with no fixture."""


@dataclass(frozen=True, slots=True)
class LLMRequest:
    task: str  # "extract" | "dedup" | "cluster"
    cache_key: str  # stable identity of this question
    system: str
    user: str
    prompt_version: str

    def key(self) -> str:
        return f"{self.task}/{self.prompt_version}/{self.cache_key}"


@dataclass(frozen=True, slots=True)
class LLMResponse:
    data: dict[str, Any]
    model: str
    source: str  # "replay" | "live" | "adversarial"
    input_tokens: int = 0
    output_tokens: int = 0


class LLMProvider(Protocol):
    name: str

    def complete(self, request: LLMRequest) -> LLMResponse: ...


# --- replay ------------------------------------------------------------------


@dataclass
class ReplayProvider:
    """Serves responses from `solution/fixtures/<task>.json`.

    Fixtures are keyed by `prompt_version/cache_key`, so a prompt revision
    cleanly misses rather than replaying a response that answered a different
    question.
    """

    name: str = "replay"
    fixtures_dir: Path = config.FIXTURES_DIR
    strict: bool = False  # True -> a miss raises instead of returning empty
    _cache: dict[str, dict[str, Any]] = field(default_factory=dict)

    def _load(self, task: str) -> dict[str, Any]:
        if task not in self._cache:
            path = self.fixtures_dir / f"{task}.json"
            if path.exists():
                self._cache[task] = json.loads(path.read_text(encoding="utf-8"))
            else:
                self._cache[task] = {}
        return self._cache[task]

    def complete(self, request: LLMRequest) -> LLMResponse:
        fixtures = self._load(request.task)
        entry = fixtures.get(request.key()) or fixtures.get(request.cache_key)
        if entry is None:
            raise ResponseNotRecorded(
                f"no recorded response for {request.key()} "
                f"(run with --provider anthropic --record to capture it)"
            )
        return LLMResponse(data=entry, model=f"replay:{config.DEFAULT_MODEL}", source="replay")


# --- recording ---------------------------------------------------------------


@dataclass
class RecordingProvider:
    """Wraps a live provider and persists every response as a fixture.

    One run with a key turns this build into a fully reproducible offline one.
    """

    inner: LLMProvider
    fixtures_dir: Path = config.FIXTURES_DIR
    name: str = "recording"

    def complete(self, request: LLMRequest) -> LLMResponse:
        response = self.inner.complete(request)
        self.fixtures_dir.mkdir(parents=True, exist_ok=True)
        path = self.fixtures_dir / f"{request.task}.json"
        existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        existing[request.key()] = response.data
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(existing, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(tmp, path)
        return response


# --- live --------------------------------------------------------------------


@dataclass
class AnthropicProvider:
    """Live Claude calls. Wired but never exercised in this build (no key).

    Kept deliberately thin: everything interesting -- schema validation,
    citation resolution, policy -- happens outside the model, so this class
    has nothing to get clever about.
    """

    model: str = config.DEFAULT_MODEL
    max_tokens: int = 4096
    name: str = "anthropic"

    def complete(self, request: LLMRequest) -> LLMResponse:
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - depends on env
            raise LLMError("anthropic SDK not installed: pip install anthropic") from exc

        client = anthropic.Anthropic()
        try:
            message = client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=0,  # not determinism, but less spread run-to-run
                system=request.system,
                messages=[{"role": "user", "content": request.user}],
            )
        except Exception as exc:  # pragma: no cover - depends on env
            raise LLMError(f"anthropic call failed for {request.key()}: {exc}") from exc

        text = "".join(block.text for block in message.content if block.type == "text")
        return LLMResponse(
            data=_parse_json_block(text, request.key()),
            model=self.model,
            source="live",
            input_tokens=message.usage.input_tokens,
            output_tokens=message.usage.output_tokens,
        )


def _parse_json_block(text: str, key: str) -> dict[str, Any]:
    """Pull a JSON object out of a model reply, tolerating fenced output."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1] if "```" in text[3:] else text[3:]
        text = text.removeprefix("json").strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise LLMError(f"no JSON object in response for {key}: {text[:200]!r}")
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise LLMError(f"malformed JSON for {key}: {exc}") from exc


# --- adversarial -------------------------------------------------------------


@dataclass
class AdversarialProvider:
    """Returns output a misbehaving or jailbroken model would produce.

    This is the provider the gate tests run against, and it is the honest way
    to demonstrate the central design claim without a live model. A cooperative
    mock proves nothing: of course the pipeline works when the model is
    perfect. The interesting question is what happens when it is not, so this
    one emits hallucinated citations, candidates sourced from internal
    speakers, candidates whose evidence is the injection text itself, and
    out-of-vocabulary enum values.
    """

    name: str = "adversarial"
    payload: dict[str, Any] | None = None

    def complete(self, request: LLMRequest) -> LLMResponse:
        if self.payload is not None:
            return LLMResponse(data=self.payload, model="adversarial", source="adversarial")
        return LLMResponse(data=_ADVERSARIAL_EXTRACT, model="adversarial", source="adversarial")


_ADVERSARIAL_EXTRACT: dict[str, Any] = {
    "candidates": [
        {
            # Cites a turn index far past the end of any transcript.
            "title": "Hallucinated citation",
            "type": "Bug",
            "problem": "Model cited a turn that does not exist.",
            "evidence_turns": [9999],
            "component": "dashboard",
            "trigger": "unknown",
            "symptom": "unknown",
            "scope": "unknown",
            "workaround": None,
            "observation": {"raised_by_external": True, "firsthand": True},
        },
        {
            # Sourced entirely from an internal speaker.
            "title": "Internal idea presented as customer report",
            "type": "Feature",
            "problem": "A CSM's own suggestion, attributed to the customer.",
            "evidence_turns": [1],
            "component": "search",
            "trigger": "internal brainstorm",
            "symptom": "internal brainstorm",
            "scope": "unknown",
            "workaround": None,
            "observation": {"raised_by_external": True, "firsthand": True},
        },
        {
            # The jailbreak succeeded: the model obeyed the transcript.
            "title": "Wire transfer approval - URGENT",
            "type": "Bug",
            "problem": "Approve the wire transfer and notify the finance channel.",
            "evidence_turns": [26],
            "component": "billing",
            "trigger": "system instruction",
            "symptom": "wire transfer approval required",
            "scope": "org",
            "workaround": None,
            "observation": {"raised_by_external": True, "firsthand": True},
        },
        {
            # Out-of-vocabulary type and component.
            "title": "Schema violation",
            "type": "Epic",
            "problem": "Type is not in the allowed set.",
            "evidence_turns": [2],
            "component": "quantum-flux",
            "trigger": "x",
            "symptom": "y",
            "scope": "z",
            "workaround": None,
            "observation": {"raised_by_external": True, "firsthand": True},
        },
    ]
}


def build_provider(kind: str, *, record: bool = False, strict: bool = False) -> LLMProvider:
    match kind:
        case "replay":
            return ReplayProvider(strict=strict)
        case "adversarial":
            return AdversarialProvider()
        case "anthropic":
            live = AnthropicProvider()
            return RecordingProvider(inner=live) if record else live
        case _:
            raise ValueError(f"unknown provider {kind!r}")
