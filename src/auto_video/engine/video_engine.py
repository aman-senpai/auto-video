# src/engine/video_engine.py
import subprocess
from pathlib import Path
from manim import config as manim_config
from auto_video.engine.tts_engine import TTSEngine
from auto_video.engine.transcription_engine import TranscriptionEngine
from auto_video.config import VIDEO_CONFIG, FFMPEG_ACCEL_ARGS, OUTPUT_DIR

class VideoOrchestrator:
    def __init__(self):
        self.tts = TTSEngine()
        self.transcriber = TranscriptionEngine()
        self._setup_manim()

    def _setup_manim(self):
        manim_config.pixel_height = VIDEO_CONFIG["pixel_height"]
        manim_config.pixel_width = VIDEO_CONFIG["pixel_width"]
        manim_config.frame_rate = VIDEO_CONFIG["frame_rate"]
        manim_config.background_color = VIDEO_CONFIG["background_color"]

    def process_script(self, script):
        """Processes script, generates assets, renders scenes."""
        project_name = script.get("title", "video").replace(" ", "_").lower()
        project_dir = OUTPUT_DIR / project_name
        project_dir.mkdir(exist_ok=True)

        assets = []
        for i, section in enumerate(script["sections"]):
            print(f"Processing section {i+1}...")
            text = section["text"]
            
            # 1. TTS
            audio_path = self.tts.generate(text)
            
            # 2. Transcribe
            words_timing = self.transcriber.transcribe(audio_path)
            
            assets.append({
                "text": text,
                "audio": audio_path,
                "timing": words_timing
            })

        return assets, project_dir

    def concatenate_audio(self, audio_paths, output_path):
        """Concatenates multiple audio files into one."""
        # Simple concat using ffmpeg filter
        inputs = []
        for p in audio_paths:
            inputs.extend(["-i", str(p)])
        
        filter_complex = "".join([f"[{i}:a]" for i in range(len(audio_paths))])
        filter_complex += f"concat=n={len(audio_paths)}:v=0:a=1[a]"
        
        cmd = [
            "ffmpeg", "-y",
            *inputs,
            "-filter_complex", filter_complex,
            "-map", "[a]",
            str(output_path)
        ]
        subprocess.run(cmd, check=True)
        return output_path

    def finalize_video(self, video_path, audio_path, output_path):
        """Combines video and audio using FFmpeg with hardware acceleration."""
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-i", str(audio_path),
            *FFMPEG_ACCEL_ARGS,
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-shortest",
            str(output_path)
        ]
        subprocess.run(cmd, check=True)
        print(f"Final video saved to: {output_path}")
