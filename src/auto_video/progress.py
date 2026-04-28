"""
Progress display module for auto-video.

Provides stage-aware progress tracking with Rich progress bars
and a clean, minimal terminal experience.
"""

from __future__ import annotations

import random
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

try:
    from rich.console import Console, Group
    from rich.panel import Panel
    from rich.progress import (
        BarColumn,
        Progress,
        SpinnerColumn,
        TaskID,
        TaskProgressColumn,
        TextColumn,
        TimeElapsedColumn,
    )
    from rich.rule import Rule
    from rich.table import Table
    from rich.text import Text
except ImportError:  # pragma: no cover
    Console = None  # type: ignore
    Panel = None  # type: ignore
    Progress = None  # type: ignore
    SpinnerColumn = None  # type: ignore
    BarColumn = None  # type: ignore
    TaskID = int  # type: ignore
    TaskProgressColumn = None  # type: ignore
    TextColumn = None  # type: ignore
    TimeElapsedColumn = None  # type: ignore
    Text = None  # type: ignore
    Rule = None  # type: ignore
    Table = None  # type: ignore
    Group = None  # type: ignore

# ─── Stage Metadata ───────────────────────────────────────────────────────────

STAGE_DESCRIPTIONS: Dict[int, Tuple[str, str, str]] = {
    1: ("Script & Planning", "cyan", "Generating structured script from topic..."),
    2: ("Scene Generation", "magenta", "Creating visual scenes with AI..."),
    3: ("Audio & Transcription", "yellow", "Synthesizing narration and captions..."),
    4: ("Manim Rendering", "green", "Rendering animations..."),
    5: ("Final Export", "blue", "Assembling final video..."),
}

STAGE_SUBTITLES: Dict[int, str] = {
    1: "Pre-Production",
    2: "Scene Generation",
    3: "Audio Mastering",
    4: "Rendering",
    5: "Export",
}

EXPORT_THRESHOLD_MESSAGES: Dict[int, str] = {
    0: "Initializing export...",
    25: "Multiplexing audio and video...",
    50: "Applying color grading...",
    75: "Normalizing audio levels...",
    90: "Packaging final file...",
    100: "Export complete!",
}

SECTION_DISPLAY_NAMES: Dict[str, str] = {
    "scene": "Scene",
    "section": "Section",
    "slide": "Slide",
    "frame": "Frame",
    "audio": "Audio clip",
    "caption": "Caption block",
}

TIPS: List[str] = [
    "Tip: Use --quality l for fast prototyping",
    "Tip: Use --provider deepseek --model deepseek-v4-flash for faster generation",
    "Tip: Set AUTO_VIDEO_LLM_PROVIDER in .env to skip --provider",
    "Tip: Use --voice af_sky for a different narration voice",
    "Tip: Use -f (--force-regenerate) to clear caches and rebuild",
    "Tip: Pass a JSON/YAML script file instead of a topic to skip LLM generation",
    "Tip: For 4K renders use --quality k (2160x3840)",
    "Tip: The self-healing loop retries up to 5 times automatically",
]

# ─── Data Classes ─────────────────────────────────────────────────────────────


@dataclass
class StageTiming:
    """Timing data for a single pipeline stage."""

    name: str
    started_at: float
    finished_at: Optional[float] = None

    @property
    def elapsed(self) -> float:
        end = self.finished_at if self.finished_at is not None else time.time()
        return end - self.started_at

    @property
    def formatted(self) -> str:
        return _format_duration(self.elapsed)


@dataclass
class ProgressHandles:
    """Container for Rich progress bar task IDs."""

    section_task: Optional[TaskID] = None
    stage_task: Optional[TaskID] = None
    export_task: Optional[TaskID] = None


# ─── Internal Helpers ─────────────────────────────────────────────────────────


def _format_duration(seconds: float) -> str:
    """Format a duration in seconds into a human-readable string."""
    seconds = max(0.0, seconds)
    hours, remainder = divmod(int(seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m {secs}s"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def _rich_available() -> bool:
    """Check if Rich library components are available."""
    return all(
        x is not None for x in (Console, Panel, Progress, Text, Rule, Table, Group)
    )


# ─── RenderProgress Class ─────────────────────────────────────────────────────


class RenderProgress:
    """Clean, minimal progress tracker for the auto-video pipeline.

    Provides stage-aware progress bars, timing tracking, export progress,
    and a completion summary. Falls back to plain print when Rich is absent.
    All console output is flushed immediately.
    """

    def __init__(self) -> None:
        self._rich = _rich_available()
        self.start_time: Optional[float] = None
        self.stages: Dict[int, StageTiming] = {}
        self._current_stage: Optional[int] = None
        self._last_export_threshold: int = 0

        if not self._rich:
            self.console = sys.stdout
            self.progress = None
            self.handles = ProgressHandles(None, None, None)
            return

        self.console = Console()
        self.progress = Progress(
            SpinnerColumn(style="cyan"),
            TextColumn("{task.description}"),
            BarColumn(bar_width=34, complete_style="magenta", finished_style="green"),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=self.console,
            transient=False,
        )
        self.handles = ProgressHandles(None, None, None)

    # ── Context Manager ───────────────────────────────────────────────────

    def __enter__(self) -> RenderProgress:
        self.start_time = time.time()
        if self.progress is not None:
            self.progress.start()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self.progress is not None:
            self.progress.stop()

    # ── Timing ────────────────────────────────────────────────────────────

    def elapsed(self) -> str:
        """Return the total elapsed time since context entry."""
        if self.start_time is None:
            return "0s"
        return _format_duration(time.time() - self.start_time)

    # ── Random Tips ───────────────────────────────────────────────────────

    @staticmethod
    def random_tip() -> str:
        """Return a randomly selected tip."""
        return random.choice(TIPS)

    # ── Section Progress ──────────────────────────────────────────────────

    def start_sections(self, total: int) -> None:
        """Start tracking section-level progress with *total* items."""
        if self.progress is None:
            return
        self.handles.section_task = self.progress.add_task(
            "Generating sections...", total=total
        )

    def advance_section(self, message: str) -> None:
        """Advance section progress by one and update the display *message*."""
        if self.progress is None or self.handles.section_task is None:
            return
        self.progress.update(self.handles.section_task, advance=1, description=message)

    def advance_section_detailed(
        self,
        section_type: str = "scene",
        current: int = 0,
        total: int = 0,
        title: str = "",
    ) -> None:
        """Advance section progress with a contextual message."""
        label = SECTION_DISPLAY_NAMES.get(section_type, section_type.capitalize())
        if total:
            msg = f"{label} {current}/{total}"
        else:
            msg = f"{label} {current}"
        if title:
            msg += f" — {title}"
        self.advance_section(msg)

    # ── Stage Progress ────────────────────────────────────────────────────

    def start_stages(self, total: int = 5) -> None:
        """Start tracking stage-level progress (default 5 stages)."""
        if self.progress is None:
            return
        self.handles.stage_task = self.progress.add_task("Pipeline", total=total)

    def advance_stage(self, message: str) -> None:
        """Advance stage progress by one and update the display *message*."""
        if self.progress is None or self.handles.stage_task is None:
            return
        self.progress.update(self.handles.stage_task, advance=1, description=message)

    def set_stage_description(self, message: str) -> None:
        """Update the current stage description without advancing."""
        if self.progress is None or self.handles.stage_task is None:
            return
        self.progress.update(self.handles.stage_task, description=message)

    # ── Export Progress ───────────────────────────────────────────────────

    def start_export(self) -> None:
        """Start the export progress bar at 0%."""
        if self.progress is None:
            return
        self._last_export_threshold = 0
        self.handles.export_task = self.progress.add_task(
            EXPORT_THRESHOLD_MESSAGES[0], total=100
        )

    def update_export(self, percent: int, message: str = "") -> None:
        """Update the export progress bar to *percent*."""
        if self.progress is None or self.handles.export_task is None:
            return

        clamped = max(0, min(percent, 100))

        if not message:
            threshold = 0
            for t in sorted(EXPORT_THRESHOLD_MESSAGES):
                if t <= clamped:
                    threshold = t
            message = EXPORT_THRESHOLD_MESSAGES[threshold]
            self._last_export_threshold = threshold

        self.progress.update(
            self.handles.export_task,
            completed=clamped,
            description=message,
        )

    def finish_export(self) -> None:
        """Mark the export as 100% done."""
        if self.progress is None or self.handles.export_task is None:
            return
        self.progress.update(
            self.handles.export_task,
            completed=100,
            description="Export complete!",
        )

    # ── Stage Header ──────────────────────────────────────────────────────

    def print_stage_header(self, stage_num: int) -> None:
        """Print a clean header announcing the start of *stage_num*."""
        info = STAGE_DESCRIPTIONS.get(stage_num)
        if info is None:
            self.print(f"\n-- Stage {stage_num} --\n")
            return

        name, colour, _ = info
        if self.console is not None and self._rich:
            self.console.print(f"\n[{colour}]==> {name}[/{colour}]")
        else:
            self.print(f"\n==> {name}")

        # Record stage timing
        self._current_stage = stage_num
        self.stages[stage_num] = StageTiming(name=name, started_at=time.time())

    # ── Stage Done ────────────────────────────────────────────────────────

    def print_stage_done(self, stage_num: int, message: Optional[str] = None) -> None:
        """Print a completion message for *stage_num*."""
        info = STAGE_DESCRIPTIONS.get(stage_num)
        if info is None:
            name = f"Stage {stage_num}"
            default_msg = ""
        else:
            name, _, default_msg = info

        if message is None:
            message = default_msg

        if stage_num in self.stages:
            self.stages[stage_num].finished_at = time.time()

        elapsed_str = ""
        if stage_num in self.stages:
            elapsed_str = f" ({self.stages[stage_num].formatted})"

        if self.console is not None and self._rich:
            self.console.print(f"[green]Done:[/green] {name}{elapsed_str}")
            if message:
                self.console.print(f"  {message}")
        else:
            self.print(f"Done: {name}{elapsed_str}")
            if message:
                self.print(f"  {message}")

    # ── Transition (convenience) ─────────────────────────────────────────

    def transition_stage(self, from_stage: int, to_stage: int) -> None:
        """Mark *from_stage* as done and print the header for *to_stage*."""
        self.print_stage_done(from_stage)
        self.print_stage_header(to_stage)
        info = STAGE_DESCRIPTIONS.get(from_stage, ("", "", ""))[0]
        if info:
            self.advance_stage(info)

    # ── Print ─────────────────────────────────────────────────────────────

    def print(self, message: str) -> None:
        """Print *message* to the console and flush."""
        if self.console is not None and self._rich:
            self.console.print(message)
        else:
            print(message, flush=True)

    # ── Banner ────────────────────────────────────────────────────────────

    def print_banner(self, stage_hint: int = 1) -> None:
        """Print the application banner."""
        if self.console is None or not self._rich:
            print("\nAUTO VIDEO - Production-grade Manim Automation\n", flush=True)
            return

        banner = Text.assemble(
            ("AUTO VIDEO", "bold cyan"),
            ("\n", ""),
            ("Production-grade Manim Automation\n", "grey50 italic"),
        )
        panel = Panel(
            banner,
            border_style="cyan",
            expand=False,
            padding=(1, 2),
        )
        self.console.print()
        self.console.print(panel)
        self.console.print()

    # ── Completion Screen ─────────────────────────────────────────────────

    def print_completion(self, extra_tip: Optional[str] = None) -> None:
        """Print a clean completion summary with timing breakdown."""
        total = self.elapsed()

        if self.console is None or not self._rich:
            print(f"\nPipeline complete! Total time: {total}\n", flush=True)
            return

        info_lines: List[Any] = [
            Text(f"\nPipeline complete! Total time: {total}\n", style="bold green"),
        ]

        table = Table(
            show_header=True,
            header_style="grey50",
            box=None,
            padding=(0, 2),
        )
        table.add_column("Stage", style="white", width=34)
        table.add_column("Time", style="cyan", justify="right", width=10)
        table.add_column("Status", style="green", width=6)

        for num in sorted(self.stages):
            s = self.stages[num]
            status = "Done" if s.finished_at else "..."
            colour = STAGE_DESCRIPTIONS.get(num, ("", "white", ""))[1]
            table.add_row(
                f"[{colour}]{s.name}[/{colour}]",
                s.formatted,
                status,
            )

        info_lines.append(table)
        info_lines.append(Text(f"\n{self.random_tip()}", style="grey50 italic"))
        if extra_tip:
            info_lines.append(Text(extra_tip, style="grey50 italic"))

        panel = Panel(
            Group(*info_lines),
            title="[bold green]Success[/bold green]",
            border_style="green",
            expand=False,
            padding=(1, 2),
        )
        self.console.print()
        self.console.print(panel)
        self.console.print()

    # ── Summary (Legacy Support) ──────────────────────────────────────────

    def print_summary(self, summary_data: Dict[str, Any]) -> None:
        """Print a production summary table."""
        if self.console is None or not self._rich:
            import json

            print(json.dumps(summary_data, indent=2), flush=True)
            return

        table = Table(show_header=False, box=None, padding=(0, 1))
        for key, value in summary_data.items():
            display_key = key.replace("_", " ").title()
            table.add_row(f"[cyan]{display_key}:[/cyan]", str(value))

        self.console.print(
            Panel(
                table,
                title="[green]Production Summary[/green]",
                border_style="green",
                expand=False,
            )
        )
