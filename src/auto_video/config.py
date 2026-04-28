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
FISH_MODEL = "fishaudio/fish-speech-1.5"
WHISPER_MODEL = "base"
WHISPER_DEVICE = "mps"

# ── Multi-Language Support ──────────────────────────────────────────────
#
# The Kokoro-82M model ships with only 4 English voices:
#   af_bella, af_heart, af_sarah, am_liam
#
# For non-English languages, Kokoro falls back to English voices.
# Use `--tts-engine fish` for proper native pronunciation (Hindi, etc.)
#
# Whisper transcription supports all listed languages natively.
# Scene text rendering uses macOS system fonts matched to each script.

_AVAILABLE_VOICES = ["af_bella", "af_heart", "af_sarah", "am_liam"]

SUPPORTED_LANGUAGES = {
    "en": {
        "name": "English",
        "voice": "af_bella",
        "kokoro_lang": "a",
        "whisper_lang": "en",
        "font": "Helvetica",
        "has_tts": True,
    },
    "es": {
        "name": "Spanish",
        "voice": "af_bella",
        "kokoro_lang": "a",
        "whisper_lang": "es",
        "font": "Helvetica",
        "has_tts": False,
    },
    "fr": {
        "name": "French",
        "voice": "af_bella",
        "kokoro_lang": "a",
        "whisper_lang": "fr",
        "font": "Helvetica",
        "has_tts": False,
    },
    "de": {
        "name": "German",
        "voice": "af_bella",
        "kokoro_lang": "a",
        "whisper_lang": "de",
        "font": "Helvetica",
        "has_tts": False,
    },
    "it": {
        "name": "Italian",
        "voice": "af_bella",
        "kokoro_lang": "a",
        "whisper_lang": "it",
        "font": "Helvetica",
        "has_tts": False,
    },
    "pt": {
        "name": "Portuguese",
        "voice": "af_bella",
        "kokoro_lang": "a",
        "whisper_lang": "pt",
        "font": "Helvetica",
        "has_tts": False,
    },
    "ja": {
        "name": "Japanese",
        "voice": "af_bella",
        "kokoro_lang": "a",
        "whisper_lang": "ja",
        "font": "Hiragino Sans",
        "has_tts": False,
    },
    "zh": {
        "name": "Chinese",
        "voice": "af_bella",
        "kokoro_lang": "a",
        "whisper_lang": "zh",
        "font": "PingFang SC",
        "has_tts": False,
    },
    "ko": {
        "name": "Korean",
        "voice": "af_bella",
        "kokoro_lang": "b",
        "whisper_lang": "ko",
        "font": "Apple SD Gothic Neo",
        "has_tts": False,
    },
    "hi": {
        "name": "Hindi",
        "voice": "af_bella",
        "kokoro_lang": "a",
        "whisper_lang": "hi",
        "font": "Kohinoor Devanagari",
        "has_tts": False,
    },
}

DEFAULT_LANGUAGE = "en"


def resolve_font(language_code: str) -> str:
    """Return the best font for the given language code."""
    info = SUPPORTED_LANGUAGES.get(language_code)
    if info and info.get("font"):
        return info["font"]
    return THEME["font"]


def has_tts_support(language_code: str) -> bool:
    """Check if the configured voice file actually exists in the Kokoro model."""
    info = SUPPORTED_LANGUAGES.get(language_code)
    if info:
        return info.get("has_tts", False)
    return False


def get_available_voices() -> list[str]:
    """Return the list of voices known to exist in the Kokoro-82M model."""
    return _AVAILABLE_VOICES[:]
