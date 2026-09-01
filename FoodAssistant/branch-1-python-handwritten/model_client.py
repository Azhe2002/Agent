"""Minimal OpenAI-compatible multi-provider client using the standard library."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from config import Settings


MAX_RESPONSE_BYTES = 2_000_000


class ModelClientError(RuntimeError):
    def __init__(
        self,
        error_type: str,
        message: str,
        *,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.error_type = error_type
        self.status_code = status_code


@dataclass(frozen=True)
class ChatResponse:
    message: dict[str, Any]
    latency_ms: int
    usage: dict[str, int] = field(default_factory=dict)
    finish_reason: str | None = None


def _classify_http_error(status_code: int) -> str:
    if status_code in (401, 403):
        return "authentication_error"
    if status_code == 402:
        return "budget_exceeded"
    if status_code == 404:
        return "model_or_endpoint_not_found"
    if status_code == 429:
        return "rate_limit"
    if status_code >= 500:
        return "provider_error"
    return "http_error"


def build_chat_payload(
    settings: Settings,
    messages: list[dict[str, Any]],
    tool_schemas: list[dict[str, Any]],
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": settings.model,
        "messages": messages,
        "stream": False,
    }
    if settings.provider != "kimi":
        payload["temperature"] = settings.temperature
    if settings.provider == "mimo":
        payload["max_completion_tokens"] = settings.max_output_tokens
    else:
        payload["max_tokens"] = settings.max_output_tokens
    if settings.provider == "nvidia":
        payload["reasoning_effort"] = settings.reasoning_effort
    else:
        # Non-thinking mode keeps tool turns compact and avoids
        # provider-specific reasoning-message requirements.
        payload["thinking"] = {"type": "disabled"}
    if tool_schemas:
        payload["tools"] = tool_schemas
        payload["tool_choice"] = "auto"
    return payload


class OpenAICompatibleChatClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def chat(
        self,
        messages: list[dict[str, Any]],
        tool_schemas: list[dict[str, Any]],
    ) -> ChatResponse:
        payload = build_chat_payload(self._settings, messages, tool_schemas)

        request = Request(
            f"{self._settings.base_url}/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {self._settings.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": f"FoodAssistant-Handwritten/0.2 ({self._settings.provider})",
            },
        )
        started = time.perf_counter()
        try:
            with urlopen(request, timeout=self._settings.timeout_seconds) as response:
                status_code = response.status
                body = response.read(MAX_RESPONSE_BYTES)
        except HTTPError as exc:
            raise ModelClientError(
                _classify_http_error(exc.code),
                "Model provider rejected the request",
                status_code=exc.code,
            ) from exc
        except (TimeoutError, URLError) as exc:
            raise ModelClientError(
                "timeout", "Model provider could not be reached before the timeout"
            ) from exc

        latency_ms = round((time.perf_counter() - started) * 1000)
        if status_code == 202:
            raise ModelClientError(
                "provider_pending",
                "Model provider returned an asynchronous response that this MVP does not poll",
                status_code=status_code,
            )
        if status_code != 200:
            raise ModelClientError(
                _classify_http_error(status_code),
                "Model provider returned an unexpected status",
                status_code=status_code,
            )

        try:
            decoded = json.loads(body)
            choices = decoded["choices"]
            first_choice = choices[0]
            raw_message = first_choice["message"]
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
            raise ModelClientError(
                "invalid_response", "Model provider returned an invalid response shape"
            ) from exc
        if not isinstance(raw_message, dict):
            raise ModelClientError(
                "invalid_response", "Model provider returned a non-object message"
            )

        message: dict[str, Any] = {
            "role": "assistant",
            "content": raw_message.get("content"),
        }
        if isinstance(raw_message.get("tool_calls"), list):
            message["tool_calls"] = raw_message["tool_calls"]
        if isinstance(raw_message.get("reasoning_content"), str):
            message["reasoning_content"] = raw_message["reasoning_content"]

        raw_usage = decoded.get("usage", {}) if isinstance(decoded, dict) else {}
        usage = {
            key: int(value)
            for key, value in raw_usage.items()
            if isinstance(key, str) and isinstance(value, int)
        }
        finish_reason = first_choice.get("finish_reason")
        if not isinstance(finish_reason, str):
            finish_reason = None
        return ChatResponse(
            message=message,
            latency_ms=latency_ms,
            usage=usage,
            finish_reason=finish_reason,
        )


# Backward-compatible name for existing imports and learning notes.
NvidiaChatClient = OpenAICompatibleChatClient
