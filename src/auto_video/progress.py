from __future__ import annotations

from dataclasses import dataclass

try:
    from rich.console import Console
    from rich.progress import (
        BarColumn,
        Progress,
        SpinnerColumn,
        TaskID,
        TaskProgressColumn,
        TextColumn,
        TimeElapsedColumn,
    )
except ImportError:  # pragma: no cover
    Console = None
    Progress = None
    SpinnerColumn = None
    BarColumn = None
    TaskID = int
    TaskProgressColumn = None
    TextColumn = None
    TimeElapsedColumn = None


@dataclass
class ProgressHandles:
    section_task: TaskID | None
    stage_task: TaskID | None
    export_task: TaskID | None


class RenderProgress:
    def __init__(self):
        self.enabled = Progress is not None
        if not self.enabled:
            self.console = None
            self.progress = None
            self.handles = ProgressHandles(None, None, None)
            return

        self.console = Console()
        self.progress = Progress(
            SpinnerColumn(style="cyan"),
            TextColumn("[bold white]{task.description}"),
            BarColumn(bar_width=34, complete_style="bright_magenta", finished_style="green"),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=self.console,
            transient=False,
        )
        self.handles = ProgressHandles(None, None, None)

    def __enter__(self):
        if self.progress is not None:
            self.progress.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.progress is not None:
            self.progress.stop()

    def start_sections(self, total: int):
        if self.progress is None:
            return
        self.handles.section_task = self.progress.add_task("[cyan]Generating sections", total=total)

    def advance_section(self, message: str):
        if self.progress is None or self.handles.section_task is None:
            return
        self.progress.update(self.handles.section_task, advance=1, description=f"[cyan]{message}")

    def start_stages(self, total: int):
        if self.progress is None:
            return
        self.handles.stage_task = self.progress.add_task("[red]Pipeline", total=total)

    def advance_stage(self, message: str):
        if self.progress is None or self.handles.stage_task is None:
            return
        self.progress.update(self.handles.stage_task, advance=1, description=f"[red]{message}")

    def start_export(self):
        if self.progress is None:
            return
        self.handles.export_task = self.progress.add_task("[green]Final export", total=100)

    def update_export(self, percent: int, message: str = "Final export"):
        if self.progress is None or self.handles.export_task is None:
            return
        self.progress.update(
            self.handles.export_task,
            completed=max(0, min(percent, 100)),
            description=f"[green]{message}",
        )

    def finish_export(self, message: str = "Final export complete"):
        if self.progress is None or self.handles.export_task is None:
            return
        self.progress.update(self.handles.export_task, completed=100, description=f"[green]{message}")

    def print(self, message: str):
        if self.console is not None:
            self.console.print(message)
        else:
            print(message)
