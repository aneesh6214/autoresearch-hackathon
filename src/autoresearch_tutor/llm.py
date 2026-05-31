from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

from openai import OpenAI

from .config import ModelSettings


@dataclass(frozen=True)
class LLMResponse:
    text: str
    usage: dict[str, int]


@dataclass(frozen=True)
class JSONLLMResponse:
    data: dict[str, Any]
    usage: dict[str, int]


class LLMClient(Protocol):
    def complete_text(
        self,
        *,
        model: str,
        system: str,
        user: str,
        reasoning_effort: str,
        text_verbosity: str,
        max_output_tokens: int,
    ) -> LLMResponse:
        ...

    def complete_json(
        self,
        *,
        model: str,
        system: str,
        user: str,
        reasoning_effort: str,
        text_verbosity: str,
        max_output_tokens: int,
    ) -> dict[str, Any]:
        ...

    def complete_json_response(
        self,
        *,
        model: str,
        system: str,
        user: str,
        reasoning_effort: str,
        text_verbosity: str,
        max_output_tokens: int,
    ) -> JSONLLMResponse:
        ...


class OpenAIResponsesClient:
    """Thin wrapper around the OpenAI Responses API."""

    def __init__(self, settings: ModelSettings, client: OpenAI | None = None) -> None:
        self.settings = settings
        self.client = client or OpenAI()

    def complete_text(
        self,
        *,
        model: str,
        system: str,
        user: str,
        reasoning_effort: str,
        text_verbosity: str,
        max_output_tokens: int,
    ) -> LLMResponse:
        response = self.client.responses.create(
            model=model,
            input=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            reasoning={"effort": reasoning_effort},
            text={"verbosity": text_verbosity},
            max_output_tokens=max_output_tokens,
        )
        text = getattr(response, "output_text", None)
        if text is None:
            text = _extract_output_text(response)
        return LLMResponse(text=text, usage=_extract_usage(response))

    def complete_json(
        self,
        *,
        model: str,
        system: str,
        user: str,
        reasoning_effort: str,
        text_verbosity: str,
        max_output_tokens: int,
    ) -> dict[str, Any]:
        return self.complete_json_response(
            model=model,
            system=system,
            user=user,
            reasoning_effort=reasoning_effort,
            text_verbosity=text_verbosity,
            max_output_tokens=max_output_tokens,
        ).data

    def complete_json_response(
        self,
        *,
        model: str,
        system: str,
        user: str,
        reasoning_effort: str,
        text_verbosity: str,
        max_output_tokens: int,
    ) -> JSONLLMResponse:
        json_system = f"{system}\n\nReturn only valid JSON. Do not wrap the JSON in markdown."
        for attempt in range(2):
            response = self.client.responses.create(
                model=model,
                input=[
                    {"role": "system", "content": json_system},
                    {"role": "user", "content": user},
                ],
                reasoning={"effort": reasoning_effort},
                text={
                    "format": {"type": "json_object"},
                    "verbosity": text_verbosity,
                },
                max_output_tokens=max(max_output_tokens, 8192),
            )
            text = getattr(response, "output_text", None) or _extract_output_text(response)
            try:
                return JSONLLMResponse(
                    data=parse_json_object(text),
                    usage=_extract_usage(response),
                )
            except json.JSONDecodeError:
                if attempt == 1:
                    raise
                user = (
                    "Your prior response was invalid or truncated JSON. Return a smaller, "
                    "valid JSON object only. Keep strings concise.\n\n"
                    f"Original request:\n{user}"
                )
        raise AssertionError("unreachable")


class QueueLLMClient:
    """Deterministic fake LLM for tests."""

    def __init__(self, responses: list[str | dict[str, Any]]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, str]] = []

    def complete_text(
        self,
        *,
        model: str,
        system: str,
        user: str,
        reasoning_effort: str,
        text_verbosity: str,
        max_output_tokens: int,
    ) -> LLMResponse:
        self.calls.append({"model": model, "system": system, "user": user})
        if not self.responses:
            raise AssertionError("QueueLLMClient has no responses left")
        value = self.responses.pop(0)
        if isinstance(value, dict):
            text = json.dumps(value)
        else:
            text = value
        return LLMResponse(text=text, usage={"input_tokens": 1, "output_tokens": 1})

    def complete_json(
        self,
        *,
        model: str,
        system: str,
        user: str,
        reasoning_effort: str,
        text_verbosity: str,
        max_output_tokens: int,
    ) -> dict[str, Any]:
        return self.complete_json_response(
            model=model,
            system=system,
            user=user,
            reasoning_effort=reasoning_effort,
            text_verbosity=text_verbosity,
            max_output_tokens=max_output_tokens,
        ).data

    def complete_json_response(
        self,
        *,
        model: str,
        system: str,
        user: str,
        reasoning_effort: str,
        text_verbosity: str,
        max_output_tokens: int,
    ) -> JSONLLMResponse:
        response = self.complete_text(
            model=model,
            system=system,
            user=user,
            reasoning_effort=reasoning_effort,
            text_verbosity=text_verbosity,
            max_output_tokens=max_output_tokens,
        )
        return JSONLLMResponse(
            data=parse_json_object(response.text),
            usage=response.usage,
        )


class HeuristicLLMClient:
    """Offline client that returns plausible tutor text without network calls."""

    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def complete_text(
        self,
        *,
        model: str,
        system: str,
        user: str,
        reasoning_effort: str,
        text_verbosity: str,
        max_output_tokens: int,
    ) -> LLMResponse:
        self.calls.append({"model": model, "system": system, "user": user})
        system_l = system.lower()
        if "hidden diagnosis" in user.lower() or "classify the student's" in user.lower():
            text = (
                "The student likely has a misconception or local error. "
                "Give one concrete hint and avoid revealing the final answer."
            )
        elif "draft tutor response" in user.lower():
            text = (
                "I think the key mistake is in the step where you connect the setup "
                "to the next operation. Try checking that step first: what quantity "
                "should stay the same, and what changes?"
            )
        elif "self-critique" in system_l:
            text = (
                "Let's focus on the exact step that changed. What did you assume there, "
                "and how could you test whether that assumption is valid?"
            )
        else:
            text = (
                "I see a possible mistake because one step is doing more work than the "
                "reasoning supports. Try checking that step first, then tell me what "
                "you think should happen next."
            )
        return LLMResponse(text=text, usage={"input_tokens": 20, "output_tokens": 45, "total_tokens": 65})

    def complete_json(
        self,
        *,
        model: str,
        system: str,
        user: str,
        reasoning_effort: str,
        text_verbosity: str,
        max_output_tokens: int,
    ) -> dict[str, Any]:
        raise NotImplementedError("HeuristicLLMClient does not generate JSON")

    def complete_json_response(
        self,
        *,
        model: str,
        system: str,
        user: str,
        reasoning_effort: str,
        text_verbosity: str,
        max_output_tokens: int,
    ) -> JSONLLMResponse:
        raise NotImplementedError("HeuristicLLMClient does not generate JSON")


def parse_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.removeprefix("```json").removeprefix("```").strip()
        stripped = stripped.removesuffix("```").strip()
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        value = json.loads(stripped[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object")
    return value


def _extract_output_text(response: Any) -> str:
    parts: list[str] = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            text = getattr(content, "text", None)
            if text:
                parts.append(text)
    return "\n".join(parts)


def _extract_usage(response: Any) -> dict[str, int]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return {}
    return {
        "input_tokens": int(getattr(usage, "input_tokens", 0) or 0),
        "output_tokens": int(getattr(usage, "output_tokens", 0) or 0),
        "total_tokens": int(getattr(usage, "total_tokens", 0) or 0),
    }
