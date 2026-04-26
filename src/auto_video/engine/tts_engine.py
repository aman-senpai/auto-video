# src/engine/tts_engine.py
import os
import sys
import hashlib
import numpy as np
import soundfile as sf
from pathlib import Path

try:
    import mlx.core as mx
    from mlx_audio.tts.utils import load_model
except ImportError:
    mx = None
    load_model = None

from auto_video.config import KOKORO_MODEL, CACHE_DIR

class TTSEngine:
    def __init__(self, model_id=KOKORO_MODEL):
        self.model_id = model_id
        self.model = None
        self._ensure_cache()

    def _ensure_cache(self):
        self.cache_dir = CACHE_DIR / "tts"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _load_model(self):
        if self.model is None:
            if load_model is None:
                raise ImportError("mlx-audio not installed. Cannot run Kokoro MLX.")
            print(f"Loading Kokoro MLX model: {self.model_id}...")
            self.model = load_model(self.model_id)
        return self.model

    def generate(self, text, voice="af_bella", speed=1.0):
        """Generates audio and returns path."""
        # Cache check
        text_hash = hashlib.md5(f"{text}_{voice}_{speed}".encode()).hexdigest()
        output_path = self.cache_dir / f"{text_hash}.wav"

        if output_path.exists():
            return str(output_path)

        model = self._load_model()
        lang_code = "b" if voice.startswith("b") else "a"

        audio_chunks = []
        for result in model.generate(text=text, voice=voice, lang_code=lang_code, speed=speed):
            audio_chunks.append(result.audio)

        if not audio_chunks:
            raise RuntimeError("TTS generation failed: No audio chunks produced.")

        full_audio = np.array(mx.concatenate(audio_chunks))
        sf.write(str(output_path), full_audio, 24000)

        return str(output_path)
