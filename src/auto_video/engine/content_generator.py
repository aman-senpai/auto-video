import json
import logging
import os
from string import Template
from typing import Any

from google import genai
from google.genai import types

logging.getLogger("google_genai").setLevel(logging.ERROR)
logging.getLogger("google").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.WARNING)


PROMPT_TEMPLATE = Template(
    """
You are building a production-grade short-form educational video.

Return valid JSON only with this schema:
{
  "title": "Short punchy title",
  "hook": "One-sentence opening hook",
  "outro": "One-sentence closing CTA",
  "sections": [
    {
      "headline": "Section headline",
      "text": "Natural narration for TTS, 1-3 sentences",
      "bullets": ["Short fact", "Short fact", "Short fact"],
      "keywords": ["term", "term", "term"],
      "visual": "timeline|comparison|process|stat|concept",
      "accent_color": "#RRGGBB"
    }
  ]
}

Requirements:
- Topic: "$topic"
- Make it informative, accurate, and concise.
- Aim for 4-6 sections.
- Each narration block should sound good when spoken aloud.
- Bullets should be scannable and visually useful.
- Use varied visual types across sections when it helps.
- No markdown fences. No prose outside JSON.
""".strip()
)


class ContentGenerationError(RuntimeError):
    pass


class ContentGenerator:
    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or os.getenv("AUTO_VIDEO_GEMINI_MODEL", "gemini-3-flash-preview")
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ContentGenerationError("GEMINI_API_KEY is required to generate content from a topic.")
        self.client = genai.Client(api_key=api_key)

    def generate_script(self, topic: str) -> dict[str, Any]:
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.5,
            top_p=0.9,
            system_instruction=PROMPT_TEMPLATE.substitute(topic=topic),
        )
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=topic,
                config=config,
            )
        except Exception as exc:
            raise ContentGenerationError(f"Gemini content generation failed: {exc}") from exc

        if not response.text:
            raise ContentGenerationError("Gemini returned an empty response.")

        try:
            script = json.loads(response.text)
        except json.JSONDecodeError as exc:
            raise ContentGenerationError("Gemini returned invalid JSON for the video script.") from exc

        self._validate_generated_script(script)
        return script

    def _validate_generated_script(self, script: dict[str, Any]) -> None:
        if not script.get("title"):
            raise ContentGenerationError("Generated script is missing a title.")
        sections = script.get("sections")
        if not isinstance(sections, list) or not sections:
            raise ContentGenerationError("Generated script must contain at least one section.")
        for index, section in enumerate(sections):
            if not section.get("text"):
                raise ContentGenerationError(f"Generated section {index} is missing narration text.")
