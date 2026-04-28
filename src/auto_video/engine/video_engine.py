import json
import os
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf
from manim import config as manim_config

from auto_video.config import (
    DEFAULT_LANGUAGE,
    OUTPUT_DIR,
    SCRIPT_OUTPUT_DIR,
    SUPPORTED_LANGUAGES,
    VIDEO_CONFIG,
    get_available_voices,
    has_tts_support,
)
from auto_video.engine.scene_generator import SceneCodeGenerator
from auto_video.engine.transcription_engine import TranscriptionEngine
from auto_video.engine.tts_engine import TTSEngine
from auto_video.utils import (
    normalize_script,
    slugify,
    validate_language,
)


@dataclass
class RenderBundle:
    project_dir: Path
    script_path: Path
    assets_path: Path
    full_audio_path: Path
    scene_path: Path


class VideoOrchestrator:
    def __init__(
        self,
        voice="af_bella",
        llm_provider: str | None = None,
        llm_model: str | None = None,
        language=None,
        tts_engine="kokoro",
    ):
        self.tts = TTSEngine(engine=tts_engine)
        self.transcriber = TranscriptionEngine()
        self.scene_generator = SceneCodeGenerator(
            provider=llm_provider, model=llm_model
        )
        self.voice = voice
        self.language = validate_language(language) if language else DEFAULT_LANGUAGE
        self._setup_manim()

        # Warn when using Kokoro for a non-English language — it only has
        # English voices, so pronunciation will be English-accented.
        # Uses a throwaway Console to render Rich markup correctly even when
        # called before the main progress context is active.
        if self.tts.engine == "kokoro" and not has_tts_support(self.language):
            lang_name = SUPPORTED_LANGUAGES.get(self.language, {}).get(
                "name", self.language
            )
            available = ", ".join(get_available_voices())
            try:
                from rich.console import Console
                Console().print(
                    f"[yellow]Warning: Kokoro-82M only has English voices "
                    f"({available}). '{lang_name}' audio will use an English "
                    f"voice — pronunciation will be English-accented. Subtitle "
                    f"text and scene visuals will still render correctly. "
                    f"Use --tts-engine fish for native pronunciation.[/yellow]"
                )
            except ImportError:
                print(
                    f"Warning: Kokoro-82M only has English voices ({available}). "
                    f"'{lang_name}' audio will use an English voice — pronunciation "
                    f"will be English-accented."
                )

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
        total_sections = len(script["sections"])
        processed_count = 0
        progress_lock = threading.Lock()

        # Pre-load Whisper model once before parallel work to avoid all threads
        # competing to load the same model simultaneously, which causes lock contention
        # and terminal output chaos.
        self.transcriber._load_model()

        def process_section_task(args):
            nonlocal processed_count
            index, section = args
            # Step 1: TTS generation (parallelizable - Kokoro model is already loaded)
            audio_path = Path(
                self.tts.generate(
                    section["text"],
                    voice=self.voice,
                    language=self.language,
                    engine=self.tts.engine,
                )
            )

            # Step 2: Transcription (serialized by _inference_lock inside TranscriptionEngine)
            words_timing = self.transcriber.transcribe(
                audio_path, language=self.language
            )

            # Step 3: Build section asset
            asset = self._build_section_asset(section, audio_path, words_timing)

            if section_progress is not None:
                with progress_lock:
                    processed_count += 1
                    section_progress(processed_count, total_sections, section)
            return index, asset

        # Use ThreadPoolExecutor for parallel TTS generation only
        # Transcription is already serialized internally, but TTS benefits from parallelism
        max_workers = min(os.cpu_count() or 4, 8)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            tasks = [(i, s) for i, s in enumerate(script["sections"], start=1)]
            results = list(executor.map(process_section_task, tasks))

        # Sort results by original index to maintain order
        results.sort(key=lambda x: x[0])
        sections = [r[1] for r in results]

        return {
            "title": script["title"],
            "hook": script.get("hook", script["title"]),
            "outro": script.get("outro", "Follow for more."),
            "_language": self.language,
            "sections": sections,
        }

    def _build_section_asset(self, section, audio_path, words_timing):
        """Build a section asset dict from the generated audio and timing data."""
        duration = sf.info(str(audio_path)).duration
        padded_audio_path = audio_path.with_name(f"{audio_path.stem}_scene.wav")
        self.pad_audio_for_scene(
            audio_path,
            padded_audio_path,
            VIDEO_CONFIG["section_preroll"],
            VIDEO_CONFIG["section_postroll"],
        )
        padded_duration = sf.info(str(padded_audio_path)).duration
        return {
            "headline": section.get("headline")
            or section["text"].split(".")[0].strip(),
            "text": section["text"],
            "bullets": section.get("bullets", []),
            "keywords": section.get("keywords", []),
            "visual": section.get("visual", "concept"),
            "accent_color": section.get("accent_color"),
            "audio": str(padded_audio_path),
            "timing": words_timing,
            "duration": duration,
            "padded_duration": padded_duration,
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
