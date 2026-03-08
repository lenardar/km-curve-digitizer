"""Provider abstractions for Vision LLM integrations."""

from __future__ import annotations

from abc import ABC, abstractmethod
import base64
from copy import deepcopy
import json
import mimetypes
import os
from pathlib import Path
from typing import Any, Callable, Dict, Optional
from urllib import error, request

from ..exceptions import SemanticExtractionError


class VisionProvider(ABC):
    """Abstract provider for semantic extraction from an image."""

    @abstractmethod
    def extract_semantics(
        self,
        image_path: str,
        *,
        prompt: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return raw semantic payload."""


class StaticVisionProvider(VisionProvider):
    """Provider used in tests and deterministic flows."""

    def __init__(self, payload: Dict[str, Any]):
        self._payload = deepcopy(payload)

    def extract_semantics(
        self,
        image_path: str,
        *,
        prompt: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        return deepcopy(self._payload)


class CallableVisionProvider(VisionProvider):
    """Provider wrapper around an arbitrary callable."""

    def __init__(self, callback: Callable[..., Dict[str, Any]]):
        self._callback = callback

    def extract_semantics(
        self,
        image_path: str,
        *,
        prompt: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self._callback(
            image_path=image_path,
            prompt=prompt,
            model=model,
            api_key=api_key,
        )


class OpenAICompatibleVisionProvider(VisionProvider):
    """Vision provider for OpenAI-compatible chat completion endpoints."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: Optional[str] = None,
        default_model: Optional[str] = None,
        timeout: int = 120,
        temperature: float = 0.0,
        max_tokens: int = 2000,
        extra_headers: Optional[Dict[str, str]] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.default_model = default_model
        self.timeout = timeout
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.extra_headers = extra_headers or {}

    def extract_semantics(
        self,
        image_path: str,
        *,
        prompt: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        resolved_model = model or self.default_model
        if not resolved_model:
            raise SemanticExtractionError("A model name is required for the online vision provider.")

        resolved_key = api_key or self.api_key or os.getenv("OPENAI_API_KEY")
        if not resolved_key:
            raise SemanticExtractionError(
                "No API key provided. Pass api_key or set OPENAI_API_KEY."
            )

        payload = {
            "model": resolved_model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt or ""},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": _encode_image_as_data_url(image_path)
                            },
                        },
                    ],
                }
            ],
        }

        headers = {
            "Authorization": f"Bearer {resolved_key}",
            "Content-Type": "application/json",
        }
        headers.update(self.extra_headers)

        endpoint = f"{self.base_url}/chat/completions"
        http_request = request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            with request.urlopen(http_request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
        except error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="ignore")
            raise SemanticExtractionError(
                f"Vision provider request failed with HTTP {exc.code}: {details}"
            ) from exc
        except error.URLError as exc:
            raise SemanticExtractionError(f"Vision provider request failed: {exc.reason}") from exc

        return _parse_chat_completion_payload(body)


def _encode_image_as_data_url(image_path: str) -> str:
    """Encode a local image into a data URL accepted by vision APIs."""
    mime_type, _ = mimetypes.guess_type(image_path)
    mime_type = mime_type or "image/png"
    raw = Path(image_path).read_bytes()
    encoded = base64.b64encode(raw).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _parse_chat_completion_payload(body: str) -> Dict[str, Any]:
    """Parse OpenAI-compatible chat completion JSON into a semantic payload."""
    payload = json.loads(body)
    choices = payload.get("choices") or []
    if not choices:
        raise SemanticExtractionError("Vision provider returned no choices.")

    message = choices[0].get("message", {})
    content = message.get("content")
    text = _coerce_content_to_text(content)
    parsed = _extract_json_block(text)
    if not isinstance(parsed, dict):
        raise SemanticExtractionError("Vision provider response did not contain a JSON object.")
    return parsed


def _coerce_content_to_text(content: Any) -> str:
    """Normalize provider message content into a plain string."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks = []
        for item in content:
            if isinstance(item, dict) and item.get("type") in {"text", "output_text"}:
                chunks.append(str(item.get("text", "")))
            elif isinstance(item, dict) and "text" in item:
                chunks.append(str(item["text"]))
            else:
                chunks.append(str(item))
        return "\n".join(chunks)
    return str(content)


def _extract_json_block(text: str) -> Any:
    """Extract a JSON object from raw model text, tolerating code fences."""
    stripped = text.strip()
    if not stripped:
        raise SemanticExtractionError("Vision provider returned empty content.")

    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    if "```" in stripped:
        fence_start = stripped.find("```")
        fence_end = stripped.rfind("```")
        if fence_end > fence_start:
            fenced = stripped[fence_start + 3 : fence_end].strip()
            if fenced.startswith("json"):
                fenced = fenced[4:].strip()
            try:
                return json.loads(fenced)
            except json.JSONDecodeError:
                pass

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = stripped[start : end + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as exc:
            raise SemanticExtractionError(
                f"Vision provider returned non-JSON content: {candidate[:200]}"
            ) from exc

    raise SemanticExtractionError("Vision provider response did not contain JSON.")
