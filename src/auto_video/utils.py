# src/utils.py
import json
import yaml
from pathlib import Path

def load_script(file_path):
    """Loads JSON or YAML script."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Script not found: {file_path}")

    with open(path, "r") as f:
        if path.suffix in [".yaml", ".yml"]:
            return yaml.safe_load(f)
        else:
            return json.load(f)

def validate_script(script):
    """Ensures script has required fields."""
    if "sections" not in script:
        raise ValueError("Script must have 'sections' list.")
    for i, section in enumerate(script["sections"]):
        if "text" not in section:
            raise ValueError(f"Section {i} missing 'text'.")
    return True
