from pathlib import Path


ROOT_DIR = Path(__file__).parent.parent.parent
CACHE_DIR = ROOT_DIR / "cache"
OUTPUT_DIR = ROOT_DIR / "output"
SCRIPT_OUTPUT_DIR = OUTPUT_DIR / "scripts"

for directory in [CACHE_DIR, OUTPUT_DIR, SCRIPT_OUTPUT_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

VIDEO_CONFIG = {
    "pixel_height": 1920,
    "pixel_width": 1080,
    "frame_height": 16.0,
    "frame_width": 9.0,
    "frame_rate": 60,
    "background_color": "#000000",
    "intro_duration": 4.0,
    "section_preroll": 1.4,
    "section_postroll": 0.5,
    "outro_duration": 3.0,
}

THEME = {
    "primary_color": "#F8FAFC",
    "secondary_color": "#22D3EE",
    "accent_color": "#F97316",
    "font": "Helvetica",
    "font_size_main": 48,
    "font_size_sub": 32,
    "text_width": 0.8,
}

KOKORO_MODEL = "mlx-community/Kokoro-82M-bf16"
WHISPER_MODEL = "base"
WHISPER_DEVICE = "mps"
