import json
import re
from pathlib import Path

import yaml

from auto_video.config import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES


def is_existing_script_path(value):
    return Path(value).expanduser().exists()


def load_script(file_path):
    path = Path(file_path).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"Script not found: {file_path}")

    with open(path, "r", encoding="utf-8") as handle:
        if path.suffix in [".yaml", ".yml"]:
            return yaml.safe_load(handle)
        return json.load(handle)


def validate_script(script):
    if "sections" not in script:
        raise ValueError("Script must have 'sections' list.")
    for index, section in enumerate(script["sections"]):
        if "text" not in section:
            raise ValueError(f"Section {index} missing 'text'.")
    return True


def normalize_script(script):
    validate_script(script)
    normalized = {
        "title": script.get("title", "Auto Video"),
        "hook": script.get("hook", script.get("title", "Auto Video")),
        "outro": script.get("outro", "Follow for more."),
        "sections": [],
    }
    for section in script["sections"]:
        normalized["sections"].append(
            {
                "headline": section.get("headline")
                or section["text"].split(".")[0].strip(),
                "text": section["text"],
                "bullets": section.get("bullets", []),
                "keywords": section.get("keywords", []),
                "visual": section.get("visual", "concept"),
                "accent_color": section.get("accent_color"),
            }
        )
    return normalized


def slugify(value):
    """Convert to a safe filename slug, preserving non-ASCII characters for multi-language support."""
    # Allow hyphens and alphanumeric (including non-ASCII unicode)
    cleaned = re.sub(r"[^\w\s-]", "", value).strip().lower()
    cleaned = re.sub(r"[-\s]+", "-", cleaned)
    return cleaned or "video"


def validate_language(lang: str) -> str:
    """Validate and normalize a language code. Returns the normalized code or default."""
    lang = lang.lower().strip()
    if lang in SUPPORTED_LANGUAGES:
        return lang
    # Also check if it's a full language name
    for code, info in SUPPORTED_LANGUAGES.items():
        if info["name"].lower() == lang:
            return code
    supported = ", ".join(
        f"{c} ({info['name']})" for c, info in SUPPORTED_LANGUAGES.items()
    )
    raise ValueError(
        f"Unsupported language: '{lang}'. Supported languages: {supported}"
    )


def get_language_config(lang: str | None = None) -> dict:
    """Get the full language configuration dict for a given language code."""
    if lang is None:
        lang = DEFAULT_LANGUAGE
    lang = validate_language(lang)
    return SUPPORTED_LANGUAGES[lang]
