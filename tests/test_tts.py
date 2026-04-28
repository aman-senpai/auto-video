# test_tts.py
import os
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

try:
    from auto_video.engine.tts_engine import TTSEngine

    engine = TTSEngine()
    path = engine.generate("Hello world")
    print(f"Success: {path}")
except Exception as e:
    print(f"Error: {e}")
    import traceback

    traceback.print_exc()
