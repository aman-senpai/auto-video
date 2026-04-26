# Manim Video Automation Pipeline (Apple Silicon)

Production-grade pipeline for generating 9:16 vertical videos with Manim and Kokoro TTS.

## Setup

1. **Install Dependencies**:
   ```bash
   uv sync
   ```

2. **System Requirements**:
   - macOS (Apple Silicon M1/M2/M3)
   - FFmpeg with `videotoolbox` support
   - Manim Community Edition

3. **Kokoro MLX**:
   The pipeline automatically downloads the Kokoro model on first run.

## Usage

```bash
uv run render example_script.json --quality h
```

## Features

- **9:16 Vertical Layout**: Optimized for TikTok, Reels, Shorts.
- **Apple Silicon Optimized**: Uses `mlx-audio` for TTS and `videotoolbox` for encoding.
- **Word-Level Sync**: Precise synchronization using `whisper-timestamped`.
- **Dynamic Themes**: Configurable colors and fonts in `src/config.py`.
- **Caching**: Audio and transcription results are cached to speed up re-renders.

## Performance Tips

- Use `--quality l` (low) for fast previews (480p).
- Use `--quality h` (high) for production (1080p).
- Ensure `WHISPER_DEVICE="mps"` in `src/config.py` for GPU-accelerated transcription.
