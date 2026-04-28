import json
import logging
import os
from string import Template
from typing import Any

from auto_video.config import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES
from auto_video.utils import validate_language

from .llm.base import LLMProvider
from .llm.factory import get_llm_provider

logging.getLogger("google_genai").setLevel(logging.ERROR)
logging.getLogger("google").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.ERROR)
logging.getLogger("anthropic").setLevel(logging.ERROR)


PROMPT_TEMPLATE = Template(
    """
You are a HIGH-PRECISION content generator for short-form educational videos.

You do NOT behave like a writer.
You behave like a structured content engine.

Your output will be parsed programmatically.
If you deviate from the schema or format, the result is INVALID.

---

## 🎯 OBJECTIVE
Generate a complete short-form educational video script.

TOPIC: "$topic"
LANGUAGE: "$language" ($language_name)

---

## ⚠️ OUTPUT RULES (STRICT)

- Output MUST be valid JSON
- NO markdown
- NO explanations
- NO trailing commas
- MUST strictly match schema
- ALL fields must be present
- Do NOT rename or add fields

---

## 📦 REQUIRED SCHEMA (DO NOT MODIFY)

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
      "visual": "timeline|comparison|process|stat|concept|network|scale|cycle|hierarchy|globe|explosion",
      "accent_color": "#RRGGBB",
      "visual_description": "Cinematic transformation description"
    }
  ]
}

---

## 🧠 CONTENT RULES

1. TITLE
- Max 8 words
- High curiosity or clarity
- No fluff
- Must be written in $language_name

2. HOOK
- Exactly ONE sentence
- Must create curiosity or tension
- Must be written in $language_name

3. OUTRO
- Exactly ONE sentence
- Must feel like a natural conclusion or CTA
- Must be written in $language_name

4. SECTIONS
- 4 to 6 sections ONLY
- Each section must introduce NEW information
- Logical progression from simple → advanced
- ALL text content must be written in $language_name

---

## ✍️ WRITING STYLE (ENFORCED)

- Clear, spoken-friendly language
- Avoid jargon unless explained
- Sentences must flow naturally in TTS
- No repetition across sections
- Narration language: $language_name

---

## 📊 BULLETS RULES

- EXACTLY 3 bullets per section
- Each bullet ≤ 6 words
- Must be concrete and visualizable
- No full sentences

---

## 🔑 KEYWORDS RULES

- EXACTLY 3 keywords
- Single words or short phrases
- Relevant to visuals and concept

---

## 🎨 VISUAL SYSTEM (CRITICAL)

You are designing a SINGLE CONTINUOUS VISUAL SYSTEM across the entire video.

DO NOT create slides.
DO NOT reset visuals between sections.

Instead:
- Each section MUST EVOLVE from the previous one
- Objects persist, transform, or rearrange

---

## 🎬 VISUAL TYPES USAGE

Use a mix across sections when useful:
- timeline → progression over time
- comparison → side-by-side contrast
- process → step-by-step flow
- stat → numbers/graphs
- concept → abstract visualization
- network → connected nodes/relationships
- scale → measurement/quantification
- cycle → circular/repeating process
- hierarchy → tree/organizational structure
- globe → geographical/worldwide context
- explosion → breaking apart/expanding into parts

NEVER use the same visual type twice in the same video.
Each and every section MUST have a UNIQUE visual type.
If you have more sections than types, invent new descriptive types beyond this list.

---

## 🔥 visual_description (MOST IMPORTANT FIELD)

This must be EXTREMELY DETAILED and CINEMATIC.

Each description MUST:

1. Start from the PREVIOUS visual state
2. Describe EXACT transformations:
   - morphing
   - splitting
   - merging
   - repositioning
   - scaling
3. Mention motion and transitions
4. Maintain continuity of objects

---

### GOOD EXAMPLE STYLE:
"The circular diagram from the previous section stretches horizontally, its segments reshaping into a flowing timeline. The central node expands and splits into three labeled branches, while connecting lines animate into directional arrows showing progression."

---

### BAD (DO NOT DO):
"Show a chart explaining growth"

---

## 🎯 COLOR RULES

- accent_color MUST be valid hex (#RRGGBB)
- Keep colors visually distinct across sections

---

## 🚀 FAILURE PREVENTION

If unsure:
- Prefer SIMPLE over complex
- Maintain continuity over creativity
- Never skip transformations

---

## ✅ FINAL CHECK (MANDATORY)

Before output:
- Is JSON valid?
- Are there 4–6 sections?
- Does each section evolve from previous?
- Are bullets EXACTLY 3 per section?
- Are keywords EXACTLY 3?
- Is visual_description detailed and continuous?
- Is ALL text content written in $language_name?

---

## OUTPUT

Return ONLY valid JSON.
""".strip()
)


class ContentGenerationError(RuntimeError):
    pass


class ContentGenerator:
    def __init__(
        self,
        provider: str | None = None,
        model: str | None = None,
        language: str | None = None,
    ):
        try:
            self.llm = get_llm_provider(provider, model)
        except Exception as exc:
            raise ContentGenerationError(
                f"Failed to initialize LLM provider: {exc}"
            ) from exc
        self.language = validate_language(language) if language else DEFAULT_LANGUAGE

    def generate_script(self, topic: str) -> dict[str, Any]:
        lang_config = SUPPORTED_LANGUAGES[self.language]
        try:
            script = self.llm.generate_json(
                prompt=topic,
                system_instruction=PROMPT_TEMPLATE.substitute(
                    topic=topic,
                    language=self.language,
                    language_name=lang_config["name"],
                ),
            )
        except Exception as exc:
            raise ContentGenerationError(f"Content generation failed: {exc}") from exc

        # Add language metadata to the script
        script["_language"] = self.language

        self._validate_generated_script(script)
        return script

    def _validate_generated_script(self, script: dict[str, Any]) -> None:
        if not script.get("title"):
            raise ContentGenerationError("Generated script is missing a title.")
        sections = script.get("sections")
        if not isinstance(sections, list) or not sections:
            raise ContentGenerationError(
                "Generated script must contain at least one section."
            )
        for index, section in enumerate(sections):
            if not section.get("text"):
                raise ContentGenerationError(
                    f"Generated section {index} is missing narration text."
                )
            if not section.get("visual_description"):
                raise ContentGenerationError(
                    f"Generated section {index} is missing a visual description."
                )
