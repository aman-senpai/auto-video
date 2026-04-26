# AutoVideo: AI-Powered Vertical Video Generator

AutoVideo is a production-grade, fully automated pipeline for generating highly engaging 9:16 vertical videos (perfect for TikTok, YouTube Shorts, and Instagram Reels). It leverages **Manim** for beautiful programmatic animations, **Gemini 3.5 Flash** for dynamic script and scene generation, **Kokoro MLX** for lifelike text-to-speech, and **Whisper** for precise word-level captioning.

Designed from the ground up for **Apple Silicon**, this tool features a revolutionary **Self-Healing Scene Engine** that writes, tests, and fixes its own animation code iteratively before rendering.

---

## 🌟 Features

- **Topic-to-Video in One Command:** Provide a text prompt or topic, and the system autonomously generates the script, audio, transcription, dynamic animations, and the final compiled `.mp4`.
- **Self-Healing Manim Generation:** Uses Gemini to dynamically write Manim Python scene code. It runs lightning-fast `--dry_run` loops to catch syntax or layout errors, iteratively fixing its own code until perfect, *before* rendering.
- **Apple Silicon Optimized:** Hardware-accelerated pipelines using `mlx-audio` for Kokoro TTS, `mps` for Whisper transcription, and native Swift/`videotoolbox` for fast H.264 final exports.
- **Word-Level Captions:** Precise audio-visual synchronization using `whisper-timestamped`.
- **Smart Caching:** Audio, TTS, and transcription steps are heavily cached. Tweak your visual prompts without wasting time regenerating voiceovers.

## 🛠 Prerequisites & Setup

### 1. System Dependencies
Ensure you have [Homebrew](https://brew.sh/) installed, then install the core Manim dependencies (FFmpeg, Pango, Cairo):
```bash
brew install ffmpeg pango pkg-config cairo
```

### 2. Python Environment
This project uses [`uv`](https://github.com/astral-sh/uv) for lightning-fast dependency management.
```bash
# Sync and install all dependencies
uv sync
```

### 3. Environment Variables
You will need a Gemini API key to generate video scripts and power the self-healing scene engine. 
Create a `.env` file in the root directory or export it directly in your terminal:
```bash
export GEMINI_API_KEY="your_api_key_here"
```

## 🚀 Usage

The primary entry point is the `render` CLI command.

### Generate from a Topic
Pass a string describing the video you want. AutoVideo will handle the script writing, voiceover, and visual generation:
```bash
uv run render "How Apple Silicon speeds up local AI video generation" --quality h
```

### Render an Existing Script
If you want to bypass AI content generation and use a carefully crafted JSON or YAML script:
```bash
uv run render path/to/script.json --quality h
```

### CLI Arguments
- `input_value`: The topic string OR the file path to a `.json`/`.yaml` script.
- `--quality`: Manim rendering quality. 
  - `l`: 480p @ 15fps (Low - Fast for previews)
  - `m`: 720p @ 30fps (Medium)
  - `h`: 1080p @ 60fps (High - Default for production)
  - `p`: 1440p @ 60fps (2K)
  - `k`: 2160p @ 60fps (4K)
- `--voice`: Kokoro TTS voice ID (default: `af_bella`).
- `--force-regenerate`: Ignores the media cache and forces a full rebuild of audio and transcription files.

## 🧠 Architecture: How It Works

1. **Content Generation:** Gemini expands your prompt into a highly structured presentation script containing a title, hook, distinct topic sections, and an outro.
2. **Audio & Transcription:** Kokoro generates the narration, and Whisper transcribes the audio to extract exact start and end timestamps for every word.
3. **Scene Generation:** Gemini acts as an expert Manim developer, taking the script, timings, and configuration assets to write a custom, highly animated `ProductionScene`.
4. **Iterative Healing (Dry-Run Loop):** The code is executed via `manim render --dry_run`. If Manim fails or times out, the traceback logs are fed back to Gemini, which surgically patches the Python script. This loop repeats up to 5 times to ensure complete stability.
5. **Final Rendering & Muxing:** Manim renders the fully validated video frames, which are then natively multiplexed with the audio stream into a final, cleanly named `.mp4` file.

## 🎨 Configuration & Styling

You can adjust global video themes, fonts, margins, and colors inside `src/auto_video/config.py`.

- Edit the `THEME` dictionary to customize `primary_color`, `secondary_color`, fonts, and text sizing.
- Ensure your custom fonts are installed at the system level on your macOS machine if you modify the `font` key.

## ⚡ Performance Tips

- Always use `--quality l` for rapid prototyping. It drastically speeds up iteration when testing scene logic and layouts. Switch to `--quality h` when you're ready for export.
- Keep `WHISPER_DEVICE="mps"` in `src/auto_video/config.py` for GPU-accelerated transcription.
- If your pipeline gets stuck using old audio assets after making sweeping script changes, pass the `--force-regenerate` flag to clear the cache.