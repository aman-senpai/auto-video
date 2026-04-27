import json
import os
from typing import Any

from openai import OpenAI

from .base import LLMProvider

class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str | None = None, default_model: str = "gpt-4o"):
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAIProvider")
        
        self.client = OpenAI(api_key=api_key)
        self.default_model = default_model

    def generate_json(
        self, 
        prompt: str, 
        system_instruction: str | None = None,
        model: str | None = None
    ) -> dict[str, Any]:
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})
        
        response = self.client.chat.completions.create(
            model=model or self.default_model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.5,
        )
        
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("OpenAI returned empty response")
            
        return json.loads(content)

    def generate_text(
        self, 
        prompt: str, 
        system_instruction: str | None = None,
        model: str | None = None
    ) -> str:
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})
        
        response = self.client.chat.completions.create(
            model=model or self.default_model,
            messages=messages,
            temperature=0.2,
        )
        
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("OpenAI returned empty response")
            
        return content.strip()
