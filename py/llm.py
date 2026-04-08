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

_PUNCT_PROMPT = (
    "Add appropriate punctuation marks (commas, periods, question marks, "
    "exclamation marks, semicolons, etc.) to the following text. "
    "Output ONLY the punctuated text, with no other changes, "
    "no added words, and no extra commentary.\n\n"
    "Text:\n{text}"
)


class AIProcessor:
    """Unified AI text processor supporting multiple LLM backends."""

    def __init__(self, config: AiConfig, max_tokens_mode: str = "auto") -> None:
        self._config = config
        self._max_tokens_mode = max_tokens_mode  # "auto" | "custom" | "default"
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

    def _resolve_prompt(self, mode: str, text: str, custom_prompt: str | None = None) -> str:
        """Resolve the prompt template for a given mode.

        If a custom_prompt is provided that contains {text}, use it directly.
        Otherwise fall back to the built-in _PROMPTS dict.
        """
        if custom_prompt and "{text}" in custom_prompt:
            return custom_prompt.format(text=text)
        return _PROMPTS.get(mode, _PROMPTS["polish"]).format(text=text)

    def restore_punctuation(self, text: str) -> str:
        """Use AI to add punctuation marks to raw ASR transcription.

        Uses a non-streaming call for speed. Returns the original text
        unchanged if the AI call fails.
        """
        if not text.strip():
            return text
        try:
            prompt = _PUNCT_PROMPT.format(text=text)
            client = self._get_client()
            response = client.chat.completions.create(
                model=self._config.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=min(len(text) + 200, 4096),
            )
            result = response.choices[0].message.content or ""
            return result.strip() if result.strip() else text
        except Exception:
            return text

    def _estimate_max_tokens(self, text_len: int) -> int | None:
        """Calculate max_tokens for the API call based on mode.

        Returns None when mode is "default" (let the model decide).
        Returns configured_max when mode is "custom".
        Returns auto-estimated value when mode is "auto".

        For Chinese text, 1 character ~= 1.5 tokens on average.
        """
        if self._max_tokens_mode == "default":
            return None
        if self._max_tokens_mode == "custom":
            return self._config.max_tokens
        # "auto" mode
        configured_max = self._config.max_tokens
        if text_len < 500:
            estimated = text_len * 3
        elif text_len < 3000:
            estimated = text_len * 2
        elif text_len < 10000:
            estimated = int(text_len * 1.5)
        else:
            estimated = text_len
        return max(2048, min(estimated, configured_max))

    def _build_create_kwargs(self, prompt: str, stream: bool = False) -> dict[str, Any]:
        """Build kwargs for the OpenAI chat completions create call."""
        max_tokens = self._estimate_max_tokens(len(prompt))
        kwargs: dict[str, Any] = {
            "model": self._config.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self._config.temperature,
        }
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        if stream:
            kwargs["stream"] = True
        return kwargs

    def process(self, text: str, mode: str, custom_prompt: str | None = None) -> tuple[str, bool]:
        """Process text non-streamingly. Returns (result_text, was_truncated)."""
        prompt = self._resolve_prompt(mode, text, custom_prompt)

        client = self._get_client()
        response = client.chat.completions.create(**self._build_create_kwargs(prompt))
        result = response.choices[0].message.content or ""
        truncated = response.choices[0].finish_reason == "length"
        return result, truncated

    def process_stream(self, text: str, mode: str, on_token: Any, custom_prompt: str | None = None) -> tuple[str, bool]:
        """Process text with streaming. Calls on_token(chunk) for each token.

        Returns (full_text, was_truncated).
        Checks self._cancel_event between chunks for cancellation support.
        """
        self._reset_cancel()
        prompt = self._resolve_prompt(mode, text, custom_prompt)

        client = self._get_client()
        stream = client.chat.completions.create(**self._build_create_kwargs(prompt, stream=True))

        full = ""
        finish_reason = "stop"
        try:
            for chunk in stream:
                if self._cancel_event.is_set():
                    break
                delta = chunk.choices[0].delta.content
                if delta:
                    full += delta
                    on_token(delta)
                if chunk.choices[0].finish_reason:
                    finish_reason = chunk.choices[0].finish_reason
        finally:
            stream.close()

        truncated = finish_reason == "length"
        return full, truncated

    def continue_stream(self, previous_output: str, mode: str, on_token: Any, custom_prompt: str | None = None) -> tuple[str, bool]:
        """Continue AI output from where it was truncated.

        Sends a follow-up message asking the AI to continue from the
        last sentence boundary of the previous output.
        """
        self._reset_cancel()

        # Find the last sentence boundary to continue from
        last_period = max(previous_output.rfind("."), previous_output.rfind("。"), previous_output.rfind("!"), previous_output.rfind("？"))
        if last_period > 0:
            context = previous_output[:last_period + 1]
        else:
            context = previous_output

        continue_prompt = (
            "You were in the middle of generating content and were cut off. "
            "Here is what you have produced so far:\n\n"
            f"{context}\n\n"
            "Please CONTINUE from where you left off. Do NOT repeat what was already written. "
            "Start directly from the next sentence/section."
        )

        client = self._get_client()
        kwargs: dict[str, Any] = {
            "model": self._config.model,
            "messages": [{"role": "user", "content": continue_prompt}],
            "temperature": self._config.temperature,
            "stream": True,
        }
        # For continuation, respect the max_tokens_mode:
        # "default" -> no limit, "auto" -> full configured max, "custom" -> configured value
        if self._max_tokens_mode != "default":
            kwargs["max_tokens"] = self._config.max_tokens

        stream = client.chat.completions.create(**kwargs)

        full = ""
        finish_reason = "stop"
        try:
            for chunk in stream:
                if self._cancel_event.is_set():
                    break
                delta = chunk.choices[0].delta.content
                if delta:
                    full += delta
                    on_token(delta)
                if chunk.choices[0].finish_reason:
                    finish_reason = chunk.choices[0].finish_reason
        finally:
            stream.close()

        truncated = finish_reason == "length"
        return full, truncated
