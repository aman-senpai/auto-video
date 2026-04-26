import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

from .config import VIDEO_CONFIG
from .engine.content_generator import ContentGenerationError, ContentGenerator
from .engine.video_engine import VideoOrchestrator
from .progress import RenderProgress
from .utils import is_existing_script_path, load_script, validate_script


class ProductionManager:
    def __init__(
        self, input_value, quality="h", voice="af_bella", force_regenerate=False
    ):
        self.input_value = input_value
        self.quality = quality
        self.voice = voice
        self.force_regenerate = force_regenerate
        self.orchestrator = VideoOrchestrator(voice=voice)

    def _load_or_generate_script(self):
        if is_existing_script_path(self.input_value):
            script = load_script(self.input_value)
            validate_script(script)
            return script

        generator = ContentGenerator()
        try:
            return generator.generate_script(self.input_value)
        except ContentGenerationError as exc:
            raise SystemExit(str(exc)) from exc

    def run(self):
        os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
        os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
        if self.force_regenerate:
            # Clear manim media cache
            cache_dir = Path("media/cache")
            if cache_dir.exists():
                shutil.rmtree(cache_dir)

            # Transcription cache
            trans_cache = self.orchestrator.transcriber.cache_dir
            if trans_cache.exists():
                shutil.rmtree(trans_cache)

        with RenderProgress() as progress:
            progress.start_stages(4)
            script = self._load_or_generate_script()
            section_total = len(script["sections"])
            progress.start_sections(section_total)
            progress.advance_stage("Script ready")
            bundle = self.orchestrator.prepare_project(
                script,
                force_regenerate=self.force_regenerate,
                section_progress=lambda index, total, section: progress.advance_section(
                    f"Generating sections ({index}/{total})"
                ),
            )

            progress.advance_stage("Audio and transcription ready")
            width, height, frame_rate = self._quality_settings()
            cmd = [
                "manim",
                "render",
                "-r",
                f"{width},{height}",
                "--fps",
                str(frame_rate),
                "--format",
                "mp4",
                "--disable_caching",
                "--media_dir",
                str(bundle.project_dir / "media"),
                str(bundle.scene_path),
                "ProductionScene",
            ]

            env = {
                **os.environ,
                "AUTO_VIDEO_SCRIPT": str(bundle.script_path),
                "AUTO_VIDEO_ASSETS": str(bundle.assets_path),
            }

            max_retries = 5
            for attempt in range(max_retries):
                try:
                    subprocess.run(
                        cmd + ["--dry_run"],
                        env=env,
                        check=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        timeout=60,
                    )
                    break
                except (
                    subprocess.CalledProcessError,
                    subprocess.TimeoutExpired,
                ) as exc:
                    error_out = getattr(exc, "stdout", None) or ""
                    if attempt == max_retries - 1:
                        progress.print(
                            f"[bold red]Manim failed after {max_retries} attempts.[/bold red]"
                        )
                        if error_out:
                            progress.print(error_out[-2000:])
                        raise SystemExit(
                            "Video rendering failed due to Manim script errors or timeouts."
                        ) from exc

                    progress.advance_stage(
                        f"Healing scene code (Attempt {attempt + 1}/{max_retries - 1})"
                    )
                    with open(bundle.scene_path, "r", encoding="utf-8") as handle:
                        bad_code = handle.read()

                    error_output = error_out[-4000:] if error_out else str(exc)
                    prompt = f"""
The following Manim script failed to run or timed out:

```python
{bad_code}
```

The error was:
```
{error_output}
```

Please fix the script so that it runs successfully. Return ONLY the valid Python code. No markdown fences, no explanations. Just python code.
"""
                    generator = self.orchestrator.scene_generator
                    from google.genai import types

                    config = types.GenerateContentConfig(temperature=0.2, top_p=0.9)

                    try:
                        response = generator.client.models.generate_content(
                            model=generator.model_name,
                            contents=prompt,
                            config=config,
                        )
                    except Exception as e:
                        raise SystemExit(f"Healing failed: {e}") from e

                    fixed_code = response.text.strip()
                    if fixed_code.startswith("```python"):
                        fixed_code = fixed_code[9:]
                    elif fixed_code.startswith("```"):
                        fixed_code = fixed_code[3:]
                    if fixed_code.endswith("```"):
                        fixed_code = fixed_code[:-3]

                    with open(bundle.scene_path, "w", encoding="utf-8") as handle:
                        handle.write(fixed_code.strip() + "\n")

            progress.advance_stage("Rendering actual video")
            try:
                subprocess.run(
                    cmd,
                    env=env,
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    timeout=300,
                )
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
                error_out = getattr(exc, "stdout", None) or ""
                progress.print("[bold red]Final video rendering failed.[/bold red]")
                if error_out:
                    progress.print(error_out[-2000:])
                raise SystemExit("Final Manim rendering failed.") from exc

            progress.advance_stage("Vertical video rendered")

            found_videos = list(
                (bundle.project_dir / "media").glob("**/ProductionScene.mp4")
            )
            if not found_videos:
                raise FileNotFoundError("Manim failed to produce ProductionScene.mp4")
            found_videos.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            video_path = found_videos[0]

            final_output = bundle.project_dir / f"{bundle.project_dir.name}.mp4"

            progress.start_export()
            progress.advance_stage("Finalizing export")
            self.orchestrator.finalize_video(
                video_path,
                bundle.full_audio_path,
                final_output,
                export_progress=lambda percent, message: progress.update_export(
                    percent, message
                ),
            )
            progress.finish_export()

            summary = {
                "title": script["title"],
                "script_path": str(bundle.script_path),
                "assets_path": str(bundle.assets_path),
                "audio_path": str(bundle.full_audio_path),
                "video_path": str(final_output),
            }
            progress.print(json.dumps(summary, indent=2))
            progress.print(
                f"\n[bold green]SUCCESS![/bold green] Video ready at: {final_output}"
            )

    def _quality_settings(self):
        quality_map = {
            "l": (480, 854, 15),
            "m": (720, 1280, 30),
            "h": (1080, 1920, 60),
            "p": (1440, 2560, 60),
            "k": (2160, 3840, 60),
        }
        return quality_map.get(
            self.quality,
            (
                VIDEO_CONFIG["pixel_width"],
                VIDEO_CONFIG["pixel_height"],
                VIDEO_CONFIG["frame_rate"],
            ),
        )


def main():
    parser = argparse.ArgumentParser(
        description="Render a production-style vertical video from a topic or a script file.",
    )
    parser.add_argument(
        "input_value",
        help="Either a topic string to generate from Gemini, or a JSON/YAML script path.",
    )
    parser.add_argument("--quality", default="h", help="Manim quality (l, m, h, p, k)")
    parser.add_argument("--voice", default="af_bella", help="Kokoro voice id")
    parser.add_argument(
        "--force-regenerate",
        action="store_true",
        help="Ignore cached script assets and regenerate audio/transcription.",
    )
    args = parser.parse_args()

    manager = ProductionManager(
        args.input_value,
        quality=args.quality,
        voice=args.voice,
        force_regenerate=args.force_regenerate,
    )
    manager.run()


if __name__ == "__main__":
    main()
