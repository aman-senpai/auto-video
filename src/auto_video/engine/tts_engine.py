import contextlib
import hashlib
import io
import platform
import re
import threading

import numpy as np
import soundfile as sf

try:
    import mlx.core as mx
    from mlx_audio.tts.utils import load_model
except ImportError:
    mx = None
    load_model = None

from auto_video.config import CACHE_DIR, FISH_MODEL, KOKORO_MODEL
from auto_video.utils import get_language_config


class TTSEngine:
    def __init__(self, model_id=None, engine="kokoro"):
        self.engine = engine
        self.model_id = model_id or (KOKORO_MODEL if engine == "kokoro" else FISH_MODEL)
        self.model = None
        self.cache_dir = CACHE_DIR / "tts"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._inference_lock = threading.Lock()

    def _load_model(self):
        with self._lock:
            if self.model is None:
                if self.engine == "kokoro":
                    if load_model is None or mx is None:
                        raise ImportError(
                            "mlx-audio is not installed. Cannot run Kokoro MLX."
                        )
                    if platform.system() != "Darwin" or platform.machine() != "arm64":
                        raise RuntimeError(
                            "Kokoro MLX is intended for Apple Silicon (Darwin arm64)."
                        )
                    print(f"Loading Kokoro MLX model: {self.model_id}...")
                    with (
                        contextlib.redirect_stdout(io.StringIO()),
                        contextlib.redirect_stderr(io.StringIO()),
                    ):
                        self.model = load_model(self.model_id)
                elif self.engine == "fish":
                    print(f"Loading Fish Speech model: {self.model_id}...")
                    # Placeholder for local Fish Speech model loading or API initialization
                    self.model = "fish_model_placeholder"
            return self.model

    def generate(self, text, voice=None, speed=1.0, language=None, engine=None):
        engine = engine or self.engine

        # Resolve voice and language
        if language:
            lang_config = get_language_config(language)
            voice = voice or lang_config["voice"]
            lang_code = lang_config["kokoro_lang"]
        else:
            voice = voice or ("af_bella" if engine == "kokoro" else "hindi_female_1")
            lang_code = "b" if (voice or "").startswith("b") else "a"

        normalized_text = self._normalize_text(text)
        text_hash = hashlib.md5(
            f"{normalized_text}_{voice}_{speed}_{language}_{engine}".encode()
        ).hexdigest()
        output_path = self.cache_dir / f"{text_hash}.wav"

        if output_path.exists():
            return str(output_path)

        if engine == "kokoro":
            return self._generate_kokoro(
                normalized_text, voice, lang_code, speed, output_path
            )
        elif engine == "fish":
            return self._generate_fish(
                normalized_text, voice, language, speed, output_path
            )
        else:
            raise ValueError(f"Unsupported TTS engine: {engine}")

    def _generate_kokoro(self, text, voice, lang_code, speed, output_path):
        model = self._load_model()
        audio_chunks = []
        with self._inference_lock:
            for result in model.generate(
                text=text, voice=voice, lang_code=lang_code, speed=speed
            ):
                audio_chunks.append(result.audio)

        if not audio_chunks:
            raise RuntimeError("Kokoro TTS generation failed.")

        full_audio = np.array(mx.concatenate(audio_chunks))
        sf.write(str(output_path), full_audio, 24000)
        return str(output_path)

    def _generate_fish(self, text, voice, language, speed, output_path):
        """Generate TTS audio using Fish Speech (optimized for Hindi and global languages).

        If the fish-speech package is not installed, falls back to generating
        a sinusoidal placeholder so the pipeline can continue end-to-end.
        """
        print(f"Fish Speech: Generating audio for '{language}' with voice '{voice}'...")

        try:
            import fish_speech
        except ImportError:
            sample_rate = 24000
            estimated_secs = max(2.0, len(text) / 12.0)
            n = int(estimated_secs * sample_rate)
            t = np.linspace(0, estimated_secs, n, endpoint=False)
            # Generate a subtle carrier tone (220 Hz + 330 Hz) so Whisper can detect audio events
            audio = 0.05 * np.sin(2 * np.pi * 220 * t) + 0.03 * np.sin(
                2 * np.pi * 330 * t
            )
            audio = audio.astype(np.float32)
            sf.write(str(output_path), audio, sample_rate)
            print(
                f"  [yellow]fish-speech package not installed — using placeholder tone "
                f"({estimated_secs:.1f}s). Install with: pip install fish-speech[/yellow]"
            )
            return str(output_path)

        # Real Fish Speech integration path
        sample_rate = 24000
        model = self._load_model()
        audio = model.synthesize(text, voice=voice, speed=speed)
        sf.write(str(output_path), audio, sample_rate)
        return str(output_path)

    def _load_fish_model(self):
        """Lazy-load the Fish Speech model (placeholder for real integration)."""
        if self.model == "fish_model_placeholder":
            return self.model
        return self.model

    def _normalize_text(self, text, language=None):
        # Remove markdown-style brackets for all languages
        text = re.sub(r"[#*_~`]", "", text)
        text = text.strip()
        return text
