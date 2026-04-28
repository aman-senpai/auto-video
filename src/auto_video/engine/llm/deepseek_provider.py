"""DeepSeek LLM provider — OpenAI-compatible API."""

import json
import os
from typing import Any

from openai import OpenAI

from .base import LLMProvider


class DeepSeekProvider(LLMProvider):
    """Provider for DeepSeek models via OpenAI-compatible API.

    Uses the OpenAI Python SDK with a custom base URL pointing to
    the DeepSeek API endpoint (https://api.deepseek.com).
    """

    def __init__(
        self,
        api_key: str | None = None,
        default_model: str = "deepseek-v4-pro",
    ):
        api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError(
                "DEEPSEEK_API_KEY environment variable is required for DeepSeekProvider"
            )

        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com",
        )
        self.default_model = default_model

    def _build_kwargs(
        self,
        model: str | None = None,
        temperature: float = 0.5,
        json_mode: bool = False,
    ) -> dict[str, Any]:
        """Build common keyword arguments for the chat completion call."""
        kwargs: dict[str, Any] = {
            "model": model or self.default_model,
            "temperature": temperature,
            "stream": False,
        }

        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        return kwargs

    def generate_json(
        self,
        prompt: str,
        system_instruction: str | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        messages: list[dict[str, str]] = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        kwargs = self._build_kwargs(model=model, temperature=0.5, json_mode=True)
        kwargs["messages"] = messages

        response = self.client.chat.completions.create(**kwargs)

        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("DeepSeek returned empty response")

        return json.loads(content)

    def generate_text(
        self,
        prompt: str,
        system_instruction: str | None = None,
        model: str | None = None,
    ) -> str:
        messages: list[dict[str, str]] = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        kwargs = self._build_kwargs(model=model, temperature=0.2, json_mode=False)
        kwargs["messages"] = messages

        response = self.client.chat.completions.create(**kwargs)

        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("DeepSeek returned empty response")

        return content.strip()
