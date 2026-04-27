import json
import logging
import os
from typing import Any

from google import genai
from google.genai import types

from .base import LLMProvider

logger = logging.getLogger(__name__)

class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str | None = None, default_model: str = "gemini-3-flash-preview"):
        api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY is required for GeminiProvider")
        
        self.client = genai.Client(api_key=api_key)
        self.default_model = default_model

    def generate_json(
        self, 
        prompt: str, 
        system_instruction: str | None = None,
        model: str | None = None
    ) -> dict[str, Any]:
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.5,
            top_p=0.9,
            system_instruction=system_instruction,
        )
        
        response = self.client.models.generate_content(
            model=model or self.default_model,
            contents=prompt,
            config=config,
        )
        
        if not response.text:
            raise RuntimeError("Gemini returned empty response")
            
        return json.loads(response.text)

    def generate_text(
        self, 
        prompt: str, 
        system_instruction: str | None = None,
        model: str | None = None
    ) -> str:
        config = types.GenerateContentConfig(
            temperature=0.2,
            top_p=0.9,
            system_instruction=system_instruction,
        )
        
        response = self.client.models.generate_content(
            model=model or self.default_model,
            contents=prompt,
            config=config,
        )
        
        if not response.text:
            raise RuntimeError("Gemini returned empty response")
            
        return response.text.strip()
