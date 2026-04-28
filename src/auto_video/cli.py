import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Annotated, Optional

import typer
from dotenv import load_dotenv

from .config import VIDEO_CONFIG
from .engine.content_generator import ContentGenerationError, ContentGenerator
from .engine.scene_generator import sanitize_scene_code
from .engine.video_engine import VideoOrchestrator
from .progress import RenderProgress
from .utils import is_existing_script_path, load_script, validate_script

load_dotenv()

app = typer.Typer(
    help="Production-grade Manim video automation pipeline.", add_completion=False
)


class ProductionManager:
    def __init__(
        self,
        input_value: str,
        quality: str = "h",
        voice: str = "af_bella",
        force_regenerate: bool = False,
        llm_provider: Optional[str] = None,
        llm_model: Optional[str] = None,
    ):
        self.input_value = input_value
        self.quality = quality
        self.voice = voice
        self.force_regenerate = force_regenerate
        self.llm_provider = llm_provider
        self.llm_model = llm_model
        self.orchestrator = VideoOrchestrator(
            voice=voice, llm_provider=llm_provider, llm_model=llm_model
        )

    def _load_or_generate_script(self):
        if is_existing_script_path(self.input_value):
            script = load_script(self.input_value)
            validate_script(script)
            return script

        generator = ContentGenerator(provider=self.llm_provider, model=self.llm_model)
        try:
            return generator.generate_script(self.input_value)
        except ContentGenerationError as exc:
            raise SystemExit(str(exc)) from exc

    def run(self):
        os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
        os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

        with RenderProgress() as progress:
            progress.print_banner()

            if self.force_regenerate:
                progress.print(
                    "[yellow]Force regeneration enabled. Clearing caches...[/yellow]"
                )
                # Clear manim media cache
                cache_dir = Path("media/cache")
                if cache_dir.exists():
                    shutil.rmtree(cache_dir)

                # Transcription cache
                trans_cache = self.orchestrator.transcriber.cache_dir
                if trans_cache.exists():
                    shutil.rmtree(trans_cache)

            progress.start_stages(5)
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
                        timeout=300,
                    )
                    break
                except (
                    subprocess.CalledProcessError,
                    subprocess.TimeoutExpired,
                ) as exc:
                    error_out = getattr(exc, "stdout", None) or ""

                    if isinstance(exc, subprocess.TimeoutExpired):
                        progress.print(
                            f"[yellow]Manim timed out during validation (Attempt {attempt + 1}).[/yellow]"
                        )
                    else:
                        progress.print(
                            f"[yellow]Manim validation failed (Attempt {attempt + 1}).[/yellow]"
                        )

                    if attempt == max_retries - 1:
                        progress.print(
                            f"[bold red]Manim failed after {max_retries} attempts.[/bold red]"
                        )
                        if error_out:
                            progress.print(error_out[-2000:])
                        raise SystemExit(
                            "Video rendering failed due to Manim script errors or timeouts."
                        ) from exc

                    if progress.progress and progress.handles.stage_task:
                        progress.progress.update(
                            progress.handles.stage_task,
                            description=f"[red]Healing code ({attempt + 1}/{max_retries - 1})",
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

Please fix the script so that it runs successfully.

COMMON FIXES:
- If error mentions TypeError with unexpected keyword: Replace `Arrow(left=X, right=Y)` with `Arrow(start=X, end=Y)`, and `Line(left=X, right=Y)` with `Line(start=X, end=Y)`. Manim does NOT accept `left`/`right` on these classes.
- If error mentions ImportError with 'ease_out_bounce' or any rate function: Remove the `from manim import ease_out_bounce` line. `ease_out_bounce` is in `manim.rate_functions`, NOT in `manim` directly. Use `rate_functions.ease_out_bounce` instead (available from `from manim import *`).
- If error mentions 'UpdateFromAlpha': Use 'UpdateFromAlphaFunc' instead.
- If error mentions 'self' positional argument: Make sure methods have `self` as first parameter.
- Do NOT attempt to hack builtins or use monkey-patches.

Return ONLY the valid Python code. No markdown fences, no explanations. Just python code.
"""
                    generator = self.orchestrator.scene_generator

                    try:
                        fixed_code = generator.llm.generate_text(prompt=prompt)
                    except Exception as e:
                        progress.print(
                            f"[bold red]AI Healing failed to respond:[/bold red] {e}"
                        )
                        raise SystemExit(f"Healing failed: {e}") from e

                    fixed_code = fixed_code.strip()
                    if fixed_code.startswith("```python"):
                        fixed_code = fixed_code[9:]
                    elif fixed_code.startswith("```"):
                        fixed_code = fixed_code[3:]
                    if fixed_code.endswith("```"):
                        fixed_code = fixed_code[:-3]

                    # Sanitize healed code to fix common LLM errors
                    fixed_code = sanitize_scene_code(fixed_code)

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
                    timeout=1200,
                )
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
                error_out = getattr(exc, "stdout", None) or ""
                progress.print("[bold red]Final video rendering failed.[/bold red]")

                if isinstance(exc, subprocess.TimeoutExpired):
                    progress.print(
                        "[red]Error: Rendering timed out after 10 minutes. The scene might be too complex.[/red]"
                    )

                if error_out:
                    progress.print("[bold white]Manim Output logs:[/bold white]")
                    progress.print(error_out[-2000:])

                debug_path = bundle.project_dir / "debug_failed_scene.py"
                shutil.copy(bundle.scene_path, debug_path)
                progress.print(
                    f"[yellow]Failing scene code saved for inspection at: {debug_path}[/yellow]"
                )

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
                "script": str(bundle.script_path),
                "assets": str(bundle.assets_path),
                "audio": str(bundle.full_audio_path),
                "video": str(final_output),
            }
            progress.print_summary(summary)

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


@app.command()
def render(
    input_value: Annotated[
        str, typer.Argument(help="Topic string or path to script (JSON/YAML)")
    ],
    quality: Annotated[str, typer.Option(help="Manim quality (l, m, h, p, k)")] = "h",
    voice: Annotated[str, typer.Option(help="Kokoro voice ID")] = "af_bella",
    force_regenerate: Annotated[
        bool,
        typer.Option(
            "--force-regenerate",
            "--force-generate",
            "--force",
            "-f",
            help="Ignore cache and regenerate all assets.",
        ),
    ] = False,
    provider: Annotated[
        Optional[str],
        typer.Option(help="LLM provider (gemini, openai, anthropic, deepseek)"),
    ] = None,
    model: Annotated[
        Optional[str], typer.Option(help="Specific LLM model name")
    ] = None,
):
    """
    Render a production-style vertical video from a topic or script.
    """
    manager = ProductionManager(
        input_value,
        quality=quality,
        voice=voice,
        force_regenerate=force_regenerate,
        llm_provider=provider,
        llm_model=model,
    )
    manager.run()


def main():
    app()


if __name__ == "__main__":
    main()
