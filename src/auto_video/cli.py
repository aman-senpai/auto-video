"""
Production-grade CLI for auto-video.

Orchestrates the full video production pipeline: script generation,
scene creation, audio synthesis, Manim rendering, and final export.
"""

from __future__ import annotations

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
    """Orchestrates the full video production pipeline."""

    def __init__(
        self,
        input_value: str,
        quality: str = "h",
        voice: str = "af_bella",
        force_regenerate: bool = False,
        llm_provider: Optional[str] = None,
        llm_model: Optional[str] = None,
    ) -> None:
        self.input_value = input_value
        self.quality = quality
        self.voice = voice
        self.force_regenerate = force_regenerate
        self.llm_provider = llm_provider
        self.llm_model = llm_model
        self.orchestrator = VideoOrchestrator(
            voice=voice, llm_provider=llm_provider, llm_model=llm_model
        )

    # ── Script Loading ────────────────────────────────────────────────────

    def _load_or_generate_script(self) -> dict:
        """Load a script file or generate one from a topic prompt."""
        if is_existing_script_path(self.input_value):
            script = load_script(self.input_value)
            validate_script(script)
            return script

        generator = ContentGenerator(provider=self.llm_provider, model=self.llm_model)
        try:
            return generator.generate_script(self.input_value)
        except ContentGenerationError as exc:
            raise SystemExit(str(exc)) from exc

    # ── Quality Presets ───────────────────────────────────────────────────

    def _quality_settings(self) -> tuple[int, int, int]:
        """Return (width, height, frame_rate) for the chosen quality preset."""
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

    # ── RENDER LOOP ───────────────────────────────────────────────────────

    def _heal_manim_scene(
        self,
        bundle: object,
        error_output: str,
        attempt: int,
        max_retries: int,
        progress: RenderProgress,
    ) -> str:
        """Send the broken scene + error back to the LLM for a targeted fix."""
        with open(bundle.scene_path, "r", encoding="utf-8") as handle:
            bad_code = handle.read()

        error_snippet = error_output[-4000:] if error_output else ""

        prompt = f"""
The following Manim script failed to run or timed out:

```python
{bad_code}
```

The error was:
```
{error_snippet}
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
            progress.print(f"[red]AI Healing failed:[/red] {e}")
            raise SystemExit(f"Healing failed: {e}") from e

        fixed_code = fixed_code.strip()
        if fixed_code.startswith("```python"):
            fixed_code = fixed_code[9:]
        elif fixed_code.startswith("```"):
            fixed_code = fixed_code[3:]
        if fixed_code.endswith("```"):
            fixed_code = fixed_code[:-3]

        fixed_code = sanitize_scene_code(fixed_code)

        with open(bundle.scene_path, "w", encoding="utf-8") as handle:
            handle.write(fixed_code.strip() + "\n")

        return fixed_code

    # ── MAIN ENTRY POINT ──────────────────────────────────────────────────

    def run(self) -> None:
        """Execute the full production pipeline."""
        os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
        os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

        with RenderProgress() as progress:
            # ── Banner ────────────────────────────────────────────────
            progress.print_banner(stage_hint=1)

            # ── Force Regeneration ────────────────────────────────────
            if self.force_regenerate:
                progress.print(
                    "[yellow]Force regeneration enabled. Clearing caches...[/yellow]"
                )
                cache_dir = Path("media/cache")
                if cache_dir.exists():
                    shutil.rmtree(cache_dir)
                trans_cache = self.orchestrator.transcriber.cache_dir
                if trans_cache.exists():
                    shutil.rmtree(trans_cache)
                progress.print("[green]Caches cleared.[/green]")

            progress.start_stages(total=5)

            # ═══════════════════════════════════════════════════════════
            # STAGE 1 - Script & Planning
            # ═══════════════════════════════════════════════════════════
            progress.print_stage_header(1)
            progress.print(f"  Topic: {self.input_value}")
            if self.llm_provider:
                model_info = self.llm_model or "default"
                progress.print(f"  Engine: {self.llm_provider} ({model_info})")

            script = self._load_or_generate_script()
            section_count = len(script["sections"])
            progress.print(
                f'  Script generated - {section_count} sections ("{script["title"]}")'
            )
            progress.print_stage_done(
                1, message=f"Generated script with {section_count} sections"
            )

            # ═══════════════════════════════════════════════════════════
            # STAGE 2 - Scene Generation
            # ═══════════════════════════════════════════════════════════
            progress.print_stage_header(2)
            progress.start_sections(total=section_count)

            def _section_progress(index: int, total: int, section: str) -> None:
                progress.advance_section_detailed(
                    section_type="scene",
                    current=index,
                    total=total,
                    title=section,
                )

            bundle = self.orchestrator.prepare_project(
                script,
                force_regenerate=self.force_regenerate,
                section_progress=lambda index, total, section: _section_progress(
                    index, total, section
                ),
            )

            progress.print_stage_done(
                2, message=f"Created {section_count} scenes with AI guidance"
            )

            # ═══════════════════════════════════════════════════════════
            # STAGE 3 - Audio & Transcription
            # ═══════════════════════════════════════════════════════════
            progress.print_stage_header(3)
            progress.print_stage_done(
                3,
                message=f"Voice: {self.voice} - Whisper captions generated",
            )

            # ═══════════════════════════════════════════════════════════
            # STAGE 4 - Manim Rendering (with self-healing loop)
            # ═══════════════════════════════════════════════════════════
            progress.print_stage_header(4)

            width, height, frame_rate = self._quality_settings()
            progress.print(f"  Render target: {width}x{height} @ {frame_rate}fps")
            progress.set_stage_description("Validating scene code...")

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
            # ── Dry-run validation loop ───────────────────────────────
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
                    if attempt > 0:
                        progress.print(
                            f"  Scene validated after {attempt + 1} attempt(s)"
                        )
                    break
                except (
                    subprocess.CalledProcessError,
                    subprocess.TimeoutExpired,
                ) as exc:
                    error_out = getattr(exc, "stdout", None) or ""
                    is_timeout = isinstance(exc, subprocess.TimeoutExpired)

                    if is_timeout:
                        progress.print(
                            f"  [yellow]Manim timed out "
                            f"(Attempt {attempt + 1}/{max_retries})[/yellow]"
                        )
                    else:
                        progress.print(
                            f"  [yellow]Validation failed "
                            f"(Attempt {attempt + 1}/{max_retries})[/yellow]"
                        )

                    if attempt == max_retries - 1:
                        progress.print(
                            f"[red]Manim failed after {max_retries} attempts.[/red]"
                        )
                        if error_out:
                            progress.print(error_out[-2000:])
                        raise SystemExit(
                            "Video rendering failed due to Manim errors."
                        ) from exc

                    progress.set_stage_description(
                        f"Healing scene code ({attempt + 1}/{max_retries - 1})"
                    )

                    self._heal_manim_scene(
                        bundle, error_out, attempt, max_retries, progress
                    )

            progress.set_stage_description("Rendering video...")

            # ── Production Render ─────────────────────────────────────
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
                progress.print("[red]Final video rendering failed.[/red]")

                if isinstance(exc, subprocess.TimeoutExpired):
                    progress.print(
                        "[red]  Error: Rendering timed out after 10 minutes."
                    )

                if error_out:
                    progress.print("[white]Manim output:[/white]")
                    progress.print(error_out[-2000:])

                debug_path = bundle.project_dir / "debug_failed_scene.py"
                shutil.copy(bundle.scene_path, debug_path)
                progress.print(
                    f"[yellow]  Failing scene saved at: {debug_path}[/yellow]"
                )
                raise SystemExit("Final Manim rendering failed.") from exc

            progress.print("  Render complete.")
            progress.print_stage_done(
                4, message=f"Rendered at {width}x{height} - {frame_rate}fps"
            )

            # ═══════════════════════════════════════════════════════════
            # STAGE 5 - Final Export
            # ═══════════════════════════════════════════════════════════
            progress.print_stage_header(5)
            progress.set_stage_description("Assembling final video...")

            found_videos = list(
                (bundle.project_dir / "media").glob("**/ProductionScene.mp4")
            )
            if not found_videos:
                raise FileNotFoundError("Manim failed to produce ProductionScene.mp4")
            found_videos.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            video_path = found_videos[0]

            final_output = bundle.project_dir / f"{bundle.project_dir.name}.mp4"

            progress.start_export()

            self.orchestrator.finalize_video(
                video_path,
                bundle.full_audio_path,
                final_output,
                export_progress=lambda percent, message: progress.update_export(
                    percent, message
                ),
            )
            progress.finish_export()

            # ── Summary & Completion ──────────────────────────────────
            summary_data = {
                "title": script["title"],
                "script": str(bundle.script_path),
                "assets": str(bundle.assets_path),
                "audio": str(bundle.full_audio_path),
                "video": str(final_output),
            }

            quality_label = {
                "l": "480p (Low)",
                "m": "720p (Medium)",
                "h": "1080p (High)",
                "p": "1440p (2K)",
                "k": "2160p (4K)",
            }.get(self.quality, f"{self.quality}")

            extra_tip = f"Rendered at {quality_label} - video saved to {final_output}"

            progress.print_summary(summary_data)
            progress.print_completion(extra_tip=extra_tip)


# ─── CLI Command ─────────────────────────────────────────────────────────────


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
        Optional[str],
        typer.Option(help="Specific LLM model name (e.g., gpt-4o, deepseek-v4-flash)"),
    ] = None,
) -> None:
    """Render a production-style vertical video from a topic or script."""
    manager = ProductionManager(
        input_value,
        quality=quality,
        voice=voice,
        force_regenerate=force_regenerate,
        llm_provider=provider,
        llm_model=model,
    )
    manager.run()


def main() -> None:
    app()


if __name__ == "__main__":
    main()
