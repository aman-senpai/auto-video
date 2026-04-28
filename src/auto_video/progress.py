"""
Progress display module for auto-video.

Professional CLI rendering with Rich: live progress bars, stage tracking,
thread-safe updates, and polished completion summaries.
"""

from __future__ import annotations

import random
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from rich.console import Console, Group
    from rich.panel import Panel
    from rich.progress import (
        BarColumn,
        Progress,
        SpinnerColumn,
        TaskID,
        TextColumn,
        TimeElapsedColumn,
    )
    from rich.rule import Rule
    from rich.table import Table
    from rich.text import Text
    from rich import box
except ImportError:  # pragma: no cover
    Console = None  # type: ignore
    Group = None  # type: ignore
    Panel = None  # type: ignore
    Progress = None  # type: ignore
    SpinnerColumn = None  # type: ignore
    BarColumn = None  # type: ignore
    TaskID = int  # type: ignore
    TextColumn = None  # type: ignore
    TimeElapsedColumn = None  # type: ignore
    Text = None  # type: ignore
    Rule = None  # type: ignore
    Table = None  # type: ignore
    box = None  # type: ignore

# ─── Stage Metadata ───────────────────────────────────────────────────────────

STAGE_META: Dict[int, Dict[str, str]] = {
    1: {"name": "Script & Planning",   "icon": "✏",  "color": "cyan",    "desc": "Generating structured script from topic"},
    2: {"name": "Scene Generation",    "icon": "⚙",  "color": "magenta", "desc": "Creating visual scenes with AI guidance"},
    3: {"name": "Audio & Transcription","icon": "\U0001f3a4","color": "yellow",  "desc": "Synthesizing narration and captions"},
    4: {"name": "Manim Rendering",     "icon": "▶",  "color": "green",   "desc": "Rendering animation frames"},
    5: {"name": "Final Export",        "icon": "✨",  "color": "blue",    "desc": "Assembling final video file"},
}

EXPORT_MILESTONES: Dict[int, str] = {
    0:   "Initializing export engine",
    15:  "Muxing audio and video streams",
    35:  "Applying color profile",
    55:  "Normalizing audio levels",
    75:  "Encoding final frames",
    90:  "Writing output container",
    100: "Export complete",
}

SECTION_LABELS: Dict[str, str] = {
    "scene":   "Scene",
    "section": "Section",
    "slide":   "Slide",
    "frame":   "Frame",
    "audio":   "Audio clip",
    "caption": "Caption",
}

TIPS: List[str] = [
    "Use --quality l for fast prototyping renders",
    "Use --provider deepseek --model deepseek-v4-flash for faster generation",
    "Set AUTO_VIDEO_LLM_PROVIDER in .env to skip --provider each time",
    "Try --voice af_sky for a different narration style",
    "Use -f (--force-regenerate) to clear all caches and rebuild from scratch",
    "Pass a JSON/YAML script file instead of a topic to skip LLM generation",
    "For 4K renders use --quality k (2160x3840 @ 60fps)",
    "The self-healing loop auto-retries broken scenes up to 5 times",
]


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _fmt_duration(seconds: float) -> str:
    seconds = max(0.0, seconds)
    h, r = divmod(int(seconds), 3600)
    m, s = divmod(r, 60)
    if h:
        return f"{h}h {m}m {s}s"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


def _fmt_size(path: Path) -> str:
    try:
        size = path.stat().st_size
    except OSError:
        return "—"
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}" if unit != "B" else f"{size} B"
        size /= 1024
    return f"{size:.1f} TB"


def _rich_ok() -> bool:
    return all(x is not None for x in (Console, Panel, Progress, Text, Rule, Table, Group, box))


# ─── Data Classes ─────────────────────────────────────────────────────────────


@dataclass
class StageTiming:
    name: str
    started_at: float
    finished_at: Optional[float] = None

    @property
    def elapsed(self) -> float:
        end = self.finished_at if self.finished_at is not None else time.time()
        return end - self.started_at

    @property
    def formatted(self) -> str:
        return _fmt_duration(self.elapsed)


@dataclass
class ProgressHandles:
    section_task: Optional[TaskID] = None
    stage_task: Optional[TaskID] = None
    export_task: Optional[TaskID] = None


# ─── Thread-Safe Log Buffer ───────────────────────────────────────────────────

class _LogBuffer:
    """Thread-safe ring buffer for log lines displayed above progress bars."""

    def __init__(self, max_lines: int = 6):
        self._lock = threading.Lock()
        self._lines: List[str] = []
        self._max = max_lines

    def append(self, line: str) -> None:
        with self._lock:
            self._lines.append(line)
            if len(self._lines) > self._max:
                self._lines = self._lines[-self._max:]

    def snapshot(self) -> List[str]:
        with self._lock:
            return list(self._lines)

    def clear(self) -> None:
        with self._lock:
            self._lines.clear()


# ─── RenderProgress ───────────────────────────────────────────────────────────

class RenderProgress:
    """Professional CLI progress tracker for the auto-video pipeline.

    Features:
      - Rich Live display for flicker-free progress bars
      - Thread-safe log buffer for parallel worker output
      - Stage-aware progress with colour-coded headers
      - Polished completion summary with file sizes and timing
      - Graceful fallback to plain print() when Rich is unavailable
    """

    def __init__(self) -> None:
        self._rich = _rich_ok()
        self.start_time: Optional[float] = None
        self.stages: Dict[int, StageTiming] = {}
        self._current_stage: Optional[int] = None
        self._log = _LogBuffer(max_lines=8)

        if not self._rich:
            self.console = sys.stdout
            self.progress = None
            self.handles = ProgressHandles()
            self._live = None
            return

        self.console = Console()
        self.progress = Progress(
            SpinnerColumn(spinner_name="dots", style="cyan"),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(
                bar_width=None,
                pulse_style="cyan",
                complete_style="green",
                finished_style="green",
            ),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=self.console,
            expand=True,
            transient=False,
        )
        self.handles = ProgressHandles()

    # ── Context Manager ───────────────────────────────────────────────────

    def __enter__(self) -> "RenderProgress":
        self.start_time = time.time()
        if self.progress is not None:
            self.progress.start()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self.progress is not None:
            self.progress.stop()

    # ── Timing ────────────────────────────────────────────────────────────

    def elapsed(self) -> str:
        if self.start_time is None:
            return "0s"
        return _fmt_duration(time.time() - self.start_time)

    # ── Print (thread-safe log) ───────────────────────────────────────────

    def print(self, message: str) -> None:
        """Print a message — goes to the log buffer when Rich is active."""
        if self.console is not None and self._rich:
            self._log.append(message)
            self.console.print(message)
        else:
            print(message, flush=True)

    # ── Banner ────────────────────────────────────────────────────────────

    def print_banner(self, stage_hint: int = 1) -> None:
        if not self._rich:
            print("\n  AUTO VIDEO — Production-grade Manim Automation\n", flush=True)
            return

        self.console.print()
        logo = Text()
        logo.append("▄▀▄ █ ▀█▀ ▄▀▄\n", style="bold cyan")
        logo.append("█▄█ █  █  █▄█\n", style="bold cyan")
        logo.append("█ ▌ █  █  █ ▌\n", style="bold cyan")
        logo.append("\n", "")
        logo.append("Production-grade Manim Video Pipeline", style="grey50 italic")

        panel = Panel(
            logo,
            border_style="cyan",
            box=box.HEAVY,
            padding=(1, 3),
        )
        self.console.print(panel)

        # Version / environment line
        py_ver = sys.version_info
        self.console.print(
            Text(
                f"  Python {py_ver.major}.{py_ver.minor}.{py_ver.micro}  •  Manim  •  {self.elapsed()}",
                style="grey50",
            ),
        )
        self.console.print()

    # ── Section Progress ──────────────────────────────────────────────────

    def start_sections(self, total: int) -> None:
        if self.progress is None:
            return
        self.handles.section_task = self.progress.add_task(
            "[cyan]Building sections", total=total
        )

    def advance_section(self, message: str) -> None:
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
        label = SECTION_LABELS.get(section_type, section_type.capitalize())
        if total:
            msg = f"[dim]{label} {current}/{total}[/dim]"
        else:
            msg = f"[dim]{label} {current}[/dim]"
        if title:
            # Truncate long titles
            short = title[:60] + "…" if len(title) > 60 else title
            msg += f"  {short}"
        self.advance_section(msg)

    # ── Stage Progress ────────────────────────────────────────────────────

    def start_stages(self, total: int = 5) -> None:
        if self.progress is None:
            return
        self.handles.stage_task = self.progress.add_task(
            "[bold]Pipeline", total=total
        )

    def advance_stage(self, message: str) -> None:
        if self.progress is None or self.handles.stage_task is None:
            return
        self.progress.update(self.handles.stage_task, advance=1, description=message)

    def set_stage_description(self, message: str) -> None:
        if self.progress is None or self.handles.stage_task is None:
            return
        self.progress.update(self.handles.stage_task, description=f"[bold]{message}")

    # ── Export Progress ───────────────────────────────────────────────────

    def start_export(self) -> None:
        if self.progress is None:
            return
        self.handles.export_task = self.progress.add_task(
            EXPORT_MILESTONES[0], total=100
        )

    def update_export(self, percent: int, message: str = "") -> None:
        if self.progress is None or self.handles.export_task is None:
            return
        clamped = max(0, min(percent, 100))
        if not message:
            milestone = 0
            for t in sorted(EXPORT_MILESTONES):
                if t <= clamped:
                    milestone = t
            message = EXPORT_MILESTONES[milestone]
        self.progress.update(
            self.handles.export_task, completed=clamped, description=message
        )

    def finish_export(self) -> None:
        if self.progress is None or self.handles.export_task is None:
            return
        self.progress.update(
            self.handles.export_task,
            completed=100,
            description="[green]" + EXPORT_MILESTONES[100] + "[/green]",
        )

    # ── Stage Header ──────────────────────────────────────────────────────

    def print_stage_header(self, stage_num: int) -> None:
        meta = STAGE_META.get(stage_num)
        if meta is None:
            self.print(f"\n── Stage {stage_num} ──")
            return

        if self._rich:
            header = Text()
            header.append(f" {meta['icon']}  ", style=f"bold {meta['color']}")
            header.append(meta["name"], style=f"bold {meta['color']}")
            header.append(f"  — {meta['desc']}", style="grey50")

            self.console.print()
            self.console.print(Rule(header, style=meta["color"]))
        else:
            self.print(f"\n── {meta['name']} — {meta['desc']}")

        self._current_stage = stage_num
        self.stages[stage_num] = StageTiming(name=meta["name"], started_at=time.time())

    # ── Stage Done ────────────────────────────────────────────────────────

    def print_stage_done(self, stage_num: int, message: Optional[str] = None) -> None:
        meta = STAGE_META.get(stage_num)
        name = meta["name"] if meta else f"Stage {stage_num}"
        color = meta["color"] if meta else "white"

        if stage_num in self.stages:
            self.stages[stage_num].finished_at = time.time()

        # Advance the overall pipeline progress bar
        self.advance_stage(f"[{color}]{name}[/{color}]")

        elapsed = ""
        if stage_num in self.stages:
            elapsed = f" ({self.stages[stage_num].formatted})"

        if self._rich:
            done = Text()
            done.append("✓", style=f"bold green")
            done.append(f" {name}", style=f"bold {color}")
            done.append(elapsed, style="dim")
            self.console.print(done)
            if message:
                self.console.print(f"  {message}", style="dim")
        else:
            self.print(f"✓ {name}{elapsed}")
            if message:
                self.print(f"  {message}")

    # ── Transition ────────────────────────────────────────────────────────

    def transition_stage(self, from_stage: int, to_stage: int) -> None:
        self.print_stage_done(from_stage)
        self.print_stage_header(to_stage)

    # ── Completion ────────────────────────────────────────────────────────

    def print_completion(self, extra_tip: Optional[str] = None) -> None:
        total = self.elapsed()

        if not self._rich:
            print(f"\n✓ Pipeline complete! Total: {total}\n", flush=True)
            return

        self.console.print()

        # Title line
        title = Text()
        title.append("✦  ", style="bold green")
        title.append("Pipeline Complete", style="bold green")
        title.append(f"  (total: {total})", style="dim")
        self.console.print(title)
        self.console.print()

        # Stage timing table
        table = Table(
            show_header=True,
            header_style="bold grey50",
            box=box.SIMPLE,
            padding=(0, 2),
            expand=False,
        )
        table.add_column("", width=2, justify="center")
        table.add_column("Stage", style="white", width=28)
        table.add_column("Time", style="cyan", justify="right", width=10)
        table.add_column("", width=8)

        for num in sorted(self.stages):
            s = self.stages[num]
            meta = STAGE_META.get(num, {})
            icon = meta.get("icon", "•")
            color = meta.get("color", "white")
            status = "✓" if s.finished_at else "…"
            table.add_row(
                icon,
                f"[{color}]{s.name}[/{color}]",
                s.formatted,
                f"[green]{status}[/green]",
            )

        self.console.print(table)
        self.console.print()

        # Tip
        tip = self.random_tip()
        self.console.print(f"  {tip}", style="grey50 italic")
        if extra_tip:
            self.console.print(f"  {extra_tip}", style="grey50 italic")
        self.console.print()

    # ── Summary ───────────────────────────────────────────────────────────

    def print_summary(self, summary_data: Dict[str, Any]) -> None:
        if not self._rich:
            import json
            print(json.dumps(summary_data, indent=2), flush=True)
            return

        table = Table(show_header=False, box=None, padding=(0, 1), expand=False)
        for key, value in summary_data.items():
            display_key = key.replace("_", " ").title()
            val_str = str(value)

            # Add file size for paths
            try:
                p = Path(str(value))
                if p.exists():
                    val_str = f"{value}  [dim]({_fmt_size(p)})[/dim]"
            except (OSError, ValueError):
                pass

            table.add_row(f"[cyan]{display_key}:[/cyan]", val_str)

        self.console.print(
            Panel(
                table,
                title="[bold green]Output Files[/bold green]",
                border_style="green",
                box=box.ROUNDED,
                padding=(1, 2),
            )
        )

    # ── Random Tip ────────────────────────────────────────────────────────

    @staticmethod
    def random_tip() -> str:
        return random.choice(TIPS)

    # ── Deprecated compat ─────────────────────────────────────────────────

    @property
    def _last_export_threshold(self) -> int:
        return 0
