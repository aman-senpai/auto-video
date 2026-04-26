# src/config.py
import os
from pathlib import Path

# Project Roots
ROOT_DIR = Path(__file__).parent.parent.parent
SRC_DIR = ROOT_DIR / "src"
CACHE_DIR = ROOT_DIR / "cache"
OUTPUT_DIR = ROOT_DIR / "output"

# Ensure dirs exist
for d in [CACHE_DIR, OUTPUT_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Video Settings
VIDEO_CONFIG = {
    "pixel_height": 1920,
    "pixel_width": 1080,
    "frame_rate": 60,
    "background_color": "#000000",
}

# FFmpeg Hardware Acceleration (Apple Silicon)
FFMPEG_ACCEL_ARGS = [
    "-vcodec", "h264_videotoolbox",
    "-b:v", "8000k",
    "-pix_fmt", "yuv420p",
]

# Theme / Styling
THEME = {
    "primary_color": "#FFFFFF",
    "secondary_color": "#00FFCC",  # Vibrant Teal
    "accent_color": "#FF3366",    # Neon Pink
    "font": "Inter",              # Assuming Inter is installed
    "font_size_main": 48,
    "font_size_sub": 32,
    "text_width": 0.8,
}

# TTS & Whisper
KOKORO_MODEL = "mlx-community/Kokoro-82M-bf16"
WHISPER_MODEL = "base"  # base/small for speed on M1/M2
WHISPER_DEVICE = "mps"  # Metal Performance Shaders for Apple Silicon
