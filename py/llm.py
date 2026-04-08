"""AI text processor — unified interface for multiple LLM backends.

Supports OpenAI-compatible APIs (OpenAI, Ollama, Qwen, etc.)
via the official openai Python SDK.

Processing modes:
  - polish:     Revise spoken text into polished written prose.
  - note:       Extract knowledge points into structured notes.
  - mindmap:    Generate Markmap-format mind map.
  - brainstorm: Propose critical-thinking questions and extensions.
"""

from __future__ import annotations

import threading
from typing import Any

from py.config import AiConfig

# Prompt templates for each processing mode.
_PROMPTS: dict[str, str] = {
    "polish": (
        "You are a professional text editor. "
        "Revise the following speech transcript into fluent written prose:\n"
        "- Fix colloquialisms and grammatical errors\n"
        "- Remove filler words and repetitions\n"
        "- Preserve original meaning\n"
        "- Output plain text only, no extra commentary\n\n"
        "Text:\n{text}"
    ),
    "note": (
        "You are an efficient study assistant. "
        "Organize the following content into structured notes:\n"
        "- Extract key knowledge points\n"
        "- Organize by hierarchy (level 1, 2, 3 headings)\n"
        "- Highlight important items\n"
        "- Use Markdown format\n\n"
        "Content:\n{text}"
    ),
    "mindmap": (
        "Convert the following content into a Markmap-format mind map:\n"
        "- Start with a central topic\n"
        "- Expand key concepts hierarchically\n"
        "- Use Markdown heading levels for hierarchy\n\n"
        "Content:\n{text}"
    ),
    "brainstorm": (
        "You are a critical-thinking mentor. Based on the following content:\n"
        "- Propose 3-5 extension questions\n"
        "- Point out weaknesses or gaps\n"
        "- Provide relevant background context\n"
        "- Suggest directions for further exploration\n\n"
        "Content:\n{text}"
    ),
}


class AIProcessor:
    """Unified AI text processor supporting multiple LLM backends."""

    def __init__(self, config: AiConfig) -> None:
        self._config = config
        self._client = None
        self._cancel_event = threading.Event()

    def _get_client(self) -> Any:
        """Lazy-initialize the OpenAI-compatible client."""
        if self._client is not None:
            return self._client

        from openai import OpenAI

        kwargs: dict[str, Any] = {}
        if self._config.api_key:
            kwargs["api_key"] = self._config.api_key
        if self._config.base_url:
            kwargs["base_url"] = self._config.base_url

        self._client = OpenAI(**kwargs)
        return self._client

    def cancel(self) -> None:
        """Signal cancellation of the current streaming request."""
        self._cancel_event.set()

    def _reset_cancel(self) -> None:
        """Reset the cancel flag for a new request."""
        self._cancel_event.clear()

    def process(self, text: str, mode: str) -> str:
        """Process text non-streamingly. Returns the full result string."""
        prompt = _PROMPTS.get(mode, _PROMPTS["polish"]).format(text=text)

        client = self._get_client()
        response = client.chat.completions.create(
            model=self._config.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self._config.temperature,
            max_tokens=self._config.max_tokens,
        )
        return response.choices[0].message.content or ""

    def process_stream(self, text: str, mode: str, on_token: Any) -> str:
        """Process text with streaming. Calls on_token(chunk) for each token.

        Returns the full accumulated result text.
        Checks self._cancel_event between chunks for cancellation support.
        """
        self._reset_cancel()
        prompt = _PROMPTS.get(mode, _PROMPTS["polish"]).format(text=text)

        client = self._get_client()
        stream = client.chat.completions.create(
            model=self._config.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self._config.temperature,
            max_tokens=self._config.max_tokens,
            stream=True,
        )

        full = ""
        for chunk in stream:
            if self._cancel_event.is_set():
                break
            delta = chunk.choices[0].delta.content
            if delta:
                full += delta
                on_token(delta)
        return full
