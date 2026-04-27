import json
import os
import re
from typing import Any

from anthropic import Anthropic

from .base import LLMProvider

class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str | None = None, default_model: str = "claude-3-5-sonnet-20240620"):
        # The user has CLAUDE in .env
        api_key = api_key or os.getenv("CLAUDE")
        if not api_key:
            raise ValueError("CLAUDE API key is required for AnthropicProvider")
        
        self.client = Anthropic(api_key=api_key)
        self.default_model = default_model

    def generate_json(
        self, 
        prompt: str, 
        system_instruction: str | None = None,
        model: str | None = None
    ) -> dict[str, Any]:
        # Anthropic uses system as a top-level param
        response = self.client.messages.create(
            model=model or self.default_model,
            max_tokens=4096,
            system=system_instruction or "",
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
        )
        
        content = response.content[0].text
        if not content:
            raise RuntimeError("Anthropic returned empty response")
            
        # Try to find JSON block if it exists, otherwise parse whole text
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        
        return json.loads(content)

    def generate_text(
        self, 
        prompt: str, 
        system_instruction: str | None = None,
        model: str | None = None
    ) -> str:
        response = self.client.messages.create(
            model=model or self.default_model,
            max_tokens=4096,
            system=system_instruction or "",
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
        )
        
        content = response.content[0].text
        if not content:
            raise RuntimeError("Anthropic returned empty response")
            
        return content.strip()
