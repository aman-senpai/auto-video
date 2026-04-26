import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf
from manim import config as manim_config

from auto_video.config import OUTPUT_DIR, SCRIPT_OUTPUT_DIR, VIDEO_CONFIG
from auto_video.engine.scene_generator import SceneCodeGenerator
from auto_video.engine.transcription_engine import TranscriptionEngine
from auto_video.engine.tts_engine import TTSEngine
from auto_video.utils import normalize_script, slugify


@dataclass
class RenderBundle:
    project_dir: Path
    script_path: Path
    assets_path: Path
    full_audio_path: Path
    scene_path: Path


class VideoOrchestrator:
    def __init__(self, voice="af_bella"):
        self.tts = TTSEngine()
        self.transcriber = TranscriptionEngine()
        self.scene_generator = SceneCodeGenerator()
        self.voice = voice
        self._setup_manim()

    def _setup_manim(self):
        manim_config.pixel_height = VIDEO_CONFIG["pixel_height"]
        manim_config.pixel_width = VIDEO_CONFIG["pixel_width"]
        manim_config.frame_height = VIDEO_CONFIG["frame_height"]
        manim_config.frame_width = VIDEO_CONFIG["frame_width"]
        manim_config.frame_rate = VIDEO_CONFIG["frame_rate"]
        manim_config.background_color = VIDEO_CONFIG["background_color"]

    def prepare_project(self, script, force_regenerate=False, section_progress=None):
        script = normalize_script(script)
        project_name = slugify(script.get("title", "video"))
        project_dir = OUTPUT_DIR / project_name
        project_dir.mkdir(parents=True, exist_ok=True)

        script_path = SCRIPT_OUTPUT_DIR / f"{project_name}.json"
        assets_path = project_dir / "assets.json"
        full_audio_path = project_dir / "full_audio.wav"
        scene_path = project_dir / "main_scene.py"

        with open(script_path, "w", encoding="utf-8") as handle:
            json.dump(script, handle, ensure_ascii=False, indent=2)

        if (
            force_regenerate
            or not assets_path.exists()
            or not full_audio_path.exists()
            or not scene_path.exists()
        ):
            assets = self._build_assets(script, section_progress=section_progress)
            with open(assets_path, "w", encoding="utf-8") as handle:
                json.dump(assets, handle, ensure_ascii=False, indent=2)
            intro_silence = project_dir / "intro_silence.wav"
            outro_silence = project_dir / "outro_silence.wav"
            self.generate_silence(VIDEO_CONFIG["intro_duration"], intro_silence)
            self.generate_silence(VIDEO_CONFIG["outro_duration"], outro_silence)
            audio_paths = [
                intro_silence,
                *[asset["audio"] for asset in assets["sections"]],
                outro_silence,
            ]
            self.concatenate_audio(audio_paths, full_audio_path)

            scene_code = self.scene_generator.generate_scene_code(
                script_data=assets, topic=script.get("title", "Video")
            )
            with open(scene_path, "w", encoding="utf-8") as handle:
                handle.write(scene_code)

        return RenderBundle(
            project_dir=project_dir,
            script_path=script_path,
            assets_path=assets_path,
            full_audio_path=full_audio_path,
            scene_path=scene_path,
        )

    def _build_assets(self, script, section_progress=None):
        sections = []
        total_sections = len(script["sections"])
        for index, section in enumerate(script["sections"], start=1):
            if section_progress is not None:
                section_progress(index, total_sections, section)
            narration_text = section["text"]
            audio_path = Path(self.tts.generate(narration_text, voice=self.voice))
            words_timing = self.transcriber.transcribe(audio_path)
            duration = sf.info(str(audio_path)).duration
            padded_audio_path = audio_path.with_name(f"{audio_path.stem}_scene.wav")
            self.pad_audio_for_scene(
                audio_path,
                padded_audio_path,
                VIDEO_CONFIG["section_preroll"],
                VIDEO_CONFIG["section_postroll"],
            )
            padded_duration = sf.info(str(padded_audio_path)).duration
            sections.append(
                {
                    "headline": section.get("headline")
                    or narration_text.split(".")[0].strip(),
                    "text": narration_text,
                    "bullets": section.get("bullets", []),
                    "keywords": section.get("keywords", []),
                    "visual": section.get("visual", "concept"),
                    "accent_color": section.get("accent_color"),
                    "audio": str(padded_audio_path),
                    "timing": words_timing,
                    "duration": duration,
                    "padded_duration": padded_duration,
                }
            )

        return {
            "title": script["title"],
            "hook": script.get("hook", script["title"]),
            "outro": script.get("outro", "Follow for more."),
            "sections": sections,
        }

    def concatenate_audio(self, audio_paths, output_path):
        arrays = []
        sample_rate = None
        for path in audio_paths:
            audio, current_rate = sf.read(str(path), dtype="float32")
            if sample_rate is None:
                sample_rate = current_rate
            elif current_rate != sample_rate:
                raise ValueError(
                    f"Sample-rate mismatch while concatenating audio: {path}"
                )
            arrays.append(audio)

        if not arrays or sample_rate is None:
            raise ValueError("No audio paths supplied for concatenation.")

        combined = np.concatenate(arrays)
        sf.write(str(output_path), combined, sample_rate)
        return output_path

    def generate_silence(self, duration, output_path):
        sample_rate = 24000
        frame_count = max(int(round(duration * sample_rate)), 1)
        silence = np.zeros(frame_count, dtype=np.float32)
        sf.write(str(output_path), silence, sample_rate)
        return output_path

    def pad_audio_for_scene(self, source_audio_path, output_path, preroll, postroll):
        audio, sample_rate = sf.read(str(source_audio_path), dtype="float32")
        pre = np.zeros(max(int(round(preroll * sample_rate)), 1), dtype=np.float32)
        post = np.zeros(max(int(round(postroll * sample_rate)), 1), dtype=np.float32)
        padded = np.concatenate([pre, audio, post])
        sf.write(str(output_path), padded, sample_rate)
        return output_path

    def finalize_video(self, video_path, audio_path, output_path, export_progress=None):
        if os.name == "posix" and Path("/usr/bin/xcrun").exists():
            try:
                self._finalize_video_native(
                    video_path, audio_path, output_path, export_progress=export_progress
                )
                return
            except Exception as exc:
                if export_progress is not None:
                    export_progress(0, "Falling back to ffmpeg export")
                else:
                    print(
                        f"Native export unavailable, falling back to ffmpeg mux: {exc}"
                    )
        self._finalize_video_ffmpeg(
            video_path, audio_path, output_path, export_progress=export_progress
        )

    def _finalize_video_native(
        self, video_path, audio_path, output_path, export_progress=None
    ):
        exporter_bin = self._ensure_native_exporter()
        cmd = [
            str(exporter_bin),
            str(video_path),
            str(audio_path),
            str(output_path),
        ]
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        assert process.stdout is not None
        for line in process.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("event") == "started":
                preset = event.get("preset", "native")
                if export_progress is not None:
                    export_progress(0, f"Native export ({preset})")
                else:
                    print(f"Native export preset: {preset}")
            elif event.get("event") == "progress":
                value = float(event.get("value", "0"))
                percent = int(value * 100)
                if export_progress is not None:
                    export_progress(percent, "Native export")

        stderr = ""
        if process.stderr is not None:
            stderr = process.stderr.read().strip()
        returncode = process.wait()
        if returncode != 0:
            raise RuntimeError(stderr or "Apple native exporter failed.")
        if export_progress is not None:
            export_progress(100, "Native export complete")
        print(f"Final video saved to: {output_path}")

    def _finalize_video_ffmpeg(
        self, video_path, audio_path, output_path, export_progress=None
    ):
        if export_progress is not None:
            export_progress(15, "Muxing audio and video")
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(video_path),
            "-i",
            str(audio_path),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "h264_videotoolbox",
            "-allow_sw",
            "1",
            "-b:v",
            "12M",
            "-maxrate",
            "18M",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            "-shortest",
            str(output_path),
        ]
        subprocess.run(
            cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        if export_progress is not None:
            export_progress(100, "Fallback export complete")
        print(f"Final video saved to: {output_path}")

    def _ensure_native_exporter(self):
        source_path = Path(__file__).with_name("apple_exporter.swift")
        binary_dir = OUTPUT_DIR / "bin"
        binary_dir.mkdir(parents=True, exist_ok=True)
        binary_path = binary_dir / "apple_exporter"

        if (
            binary_path.exists()
            and binary_path.stat().st_mtime >= source_path.stat().st_mtime
        ):
            return binary_path

        cmd = [
            "/usr/bin/xcrun",
            "swiftc",
            "-parse-as-library",
            "-O",
            "-framework",
            "AVFoundation",
            str(source_path),
            "-o",
            str(binary_path),
        ]
        env = {**os.environ, "CLANG_MODULE_CACHE_PATH": "/tmp/clang-module-cache"}
        subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
        )
        return binary_path
