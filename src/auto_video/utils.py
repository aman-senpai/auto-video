import json
import re
from pathlib import Path

import yaml


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
                "headline": section.get("headline") or section["text"].split(".")[0].strip(),
                "text": section["text"],
                "bullets": section.get("bullets", []),
                "keywords": section.get("keywords", []),
                "visual": section.get("visual", "concept"),
                "accent_color": section.get("accent_color"),
            }
        )
    return normalized


def slugify(value):
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()
    return cleaned or "video"
