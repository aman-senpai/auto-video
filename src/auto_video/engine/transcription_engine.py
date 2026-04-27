# src/engine/transcription_engine.py
import json
import hashlib
import contextlib
import io
import threading
from pathlib import Path
import whisper_timestamped as whisper
from auto_video.config import WHISPER_MODEL, WHISPER_DEVICE, CACHE_DIR

class TranscriptionEngine:
    def __init__(self, model_name=WHISPER_MODEL, device=WHISPER_DEVICE):
        self.model_name = model_name
        self.device = device
        self.model = None
        self.cache_dir = CACHE_DIR / "transcription"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._inference_lock = threading.Lock()

    def _load_model(self):
        with self._lock:
            if self.model is None:
                print(f"Loading Whisper model: {self.model_name} on {self.device}...")
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    self.model = whisper.load_model(self.model_name, device=self.device)
            return self.model

    def transcribe(self, audio_path):
        """Transcribes audio with word-level timestamps."""
        audio_path = Path(audio_path)
        cache_key = hashlib.md5(f"{audio_path.name}_{audio_path.stat().st_size}".encode()).hexdigest()
        cache_path = self.cache_dir / f"{cache_key}.json"

        if cache_path.exists():
            with open(cache_path, "r") as f:
                return json.load(f)

        model = self._load_model()
        with self._inference_lock:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                result = whisper.transcribe(model, str(audio_path), language="en")

        # Extract word-level data
        words = []
        for segment in result.get("segments", []):
            for word in segment.get("words", []):
                words.append({
                    "text": word["text"],
                    "start": word["start"],
                    "end": word["end"]
                })

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w") as f:
            json.dump(words, f)

        return words
