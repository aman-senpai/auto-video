import json
import logging
import os
import re
from typing import Any

from .llm.base import LLMProvider
from .llm.factory import get_llm_provider


class SceneGenerationError(RuntimeError):
    pass


# ──────────────────────────────────────────────
#  CODE SANITIZER — auto-fixes common LLM mistakes
# ──────────────────────────────────────────────

_BAD_IMPORT_PATTERNS = [
    re.compile(
        r"^from manim import (?!\*|config)"
    ),  # catches `from manim import ease_out_bounce, ...`
    re.compile(r"^import manim\b(?!$)"),
]

_ARROW_LEFT_RIGHT = re.compile(r"\bArrow\([^)]*\bleft\s*=")
_LINE_LEFT_RIGHT = re.compile(r"\bLine\([^)]*\bleft\s*=")


def sanitize_scene_code(code: str) -> str:
    """Post-process LLM-generated Manim code to fix common errors automatically."""

    lines = code.split("\n")
    cleaned = []

    for line in lines:
        # ── 1. Strip bad imports ──
        if any(p.match(line.strip()) for p in _BAD_IMPORT_PATTERNS):
            logging.debug("sanitizer: removed bad import: %s", line.strip())
            continue

        # ── 2. Fix Arrow(left=X, right=Y) → Arrow(start=X, end=Y) ──
        if _ARROW_LEFT_RIGHT.search(line):
            line = line.replace("left=", "start=").replace("right=", "end=")
            logging.debug("sanitizer: fixed Arrow left/right → start/end")

        # ── 3. Fix Line(left=X, right=Y) → Line(start=X, end=Y) ──
        if _LINE_LEFT_RIGHT.search(line):
            line = line.replace("left=", "start=").replace("right=", "end=")
            logging.debug("sanitizer: fixed Line left/right → start/end")

        cleaned.append(line)

    return "\n".join(cleaned)


# ──────────────────────────────────────────────
#  PROMPT  (kept as a constant for clarity)
# ──────────────────────────────────────────────

_INTRO_PROMPT_BLOCK = """
## 🏆 PREMIUM INTRO — TIMING & DESIGN

The intro is the MOST IMPORTANT part of the video.

### ⏱ HARD TIMING CONSTRAINT
Total duration for ALL intro animations MUST be ≤ VIDEO_CONFIG["intro_duration"] ({intro_duration}s).
The system will fill remaining time with a wait. If your animations exceed this, captions will be OUT OF SYNC.

### 📐 INTRO STRUCTURE — title MUST appear FIRST
The title must be visible from the VERY FIRST FRAME (within your first self.play() call).
DO NOT play background effects before the title.

Follow this flow:
1. Title appears IMMEDIATELY (fade in or scale in within the first 0.3s)
2. While title is visible, add accent elements around it (underline, glow, decorative lines)
3. Hook/subtitle appears next (around 1.0s–1.5s into the intro)
4. Final polish pulse on whole group
5. System waits remaining time automatically

### ❌ FORBIDDEN
- self.play_ai_reveal() — too generic and slow
- Animations before the title appears
- Total animation run_time > VIDEO_CONFIG["intro_duration"]
"""


def _build_intro_prompt() -> str:
    import auto_video.config as cfg

    duration = cfg.VIDEO_CONFIG["intro_duration"]
    return _INTRO_PROMPT_BLOCK.format(intro_duration=duration)


# ──────────────────────────────────────────────
#  SCENE CODE GENERATOR
# ──────────────────────────────────────────────


class SceneCodeGenerator:
    def __init__(self, provider: str | None = None, model: str | None = None):
        try:
            self.llm = get_llm_provider(provider, model)
        except Exception as exc:
            raise SceneGenerationError(
                f"Failed to initialize LLM provider: {exc}"
            ) from exc

    def generate_scene_code(self, script_data: dict[str, Any], topic: str) -> str:
        script_data_str = json.dumps(script_data, indent=2)

        prompt = f"""
You are a TOP-TIER Manim production engineer.

Your job is to EXECUTE a precise, production-grade animation system.
If you deviate from instructions, the output is considered FAILED.

---

## 🎯 OBJECTIVE
Generate a COMPLETE, EXECUTABLE Manim script for a 9:16 vertical cinematic video on:

TOPIC: {topic}

You MUST strictly follow architecture, timing, and animation rules.

---

{_build_intro_prompt()}

---

## 🧠 INPUT DATA
This is the SINGLE SOURCE OF TRUTH — do NOT modify structure.

{script_data_str}

---

## ⚠️ HARD CONSTRAINTS

1. OUTPUT ONLY VALID PYTHON CODE — no markdown, no explanations.

2. CLASS SIGNATURE: `class ProductionScene(BaseProductionScene):`

3. TRACK STATE via `current_visual` — NEVER leave old elements on screen, ALWAYS transform or remove.

4. TIMING IS STRICT — NEVER overshoot durations. Total animation time for intro must be ≤ VIDEO_CONFIG["intro_duration"].

5. PERFORMANCE — MAX 3–5 active mobjects at once. NO heavy loops. NO always_redraw on complex objects.

---

## 🎬 ANIMATION PRINCIPLES

1. PREMIUM ANIMATIONS — Use Create, Write, DrawBorderThenFill, MoveAlongPath, ValueTracker. Build multi-stage sequences. No static or boring jump/tilt/wiggle effects.

2. CENTERED LAYOUT — Always center the combined group of headline + visual on screen.

3. CONTINUITY — Use ReplacementTransform to morph between scenes. No slide-switching cuts.

4. DEPTH — Use self.get_particle_field() ONCE globally at the start.

5. CORRECT MANIM API:
   - Arrow(start=..., end=...) — NOT left=/right=
   - Line(start=..., end=...) — NOT left=/right=
   - rate_functions.ease_out_bounce — NOT imported from manim directly
   - `from manim import *` gives you everything — DO NOT add extra import lines

---

## 🏗️ IMPORTS (EXACT — DO NOT CHANGE)
```python
import json
import os
import numpy as np
from manim import *
from manim import config as manim_config
from auto_video.config import VIDEO_CONFIG, THEME
from auto_video.scenes.base_scene import BaseProductionScene
```

---

## 🏗️ CONFIGURATION (EXACT)
```python
manim_config.pixel_height = VIDEO_CONFIG["pixel_height"]
manim_config.pixel_width = VIDEO_CONFIG["pixel_width"]
manim_config.frame_height = VIDEO_CONFIG["frame_height"]
manim_config.frame_width = VIDEO_CONFIG["frame_width"]
manim_config.frame_rate = VIDEO_CONFIG["frame_rate"]
manim_config.background_color = VIDEO_CONFIG["background_color"]
```

---

## 🧱 CORE FLOW (MANDATORY)

```python
def construct(self):
    assets = json.load(open(os.environ["AUTO_VIDEO_ASSETS"]))
    self.add(self.get_particle_field())
    intro_start_time = self.renderer.time

    # ── INTRO ──────────────────────────────────
    # title appears IMMEDIATELY (within first animation)
    title = self.get_styled_text(assets["title"], is_main=True)
    if title.width > manim_config.frame_width * 0.85:
        title.scale_to_fit_width(manim_config.frame_width * 0.85)

    hook = self.get_styled_text(assets["hook"], is_main=False)
    if hook.width > manim_config.frame_width * 0.75:
        hook.scale_to_fit_width(manim_config.frame_width * 0.75)

    # Stage 1: Title appears first (fast, <0.3s)
    title.move_to(ORIGIN + UP * 0.5)
    self.play(FadeIn(title, scale=0.8), run_time=0.3)

    # Stage 2: Accent elements while title is visible (e.g. underline, glow)
    # ... design your accent animations here ...

    # Stage 3: Hook appears
    hook.next_to(title, DOWN, buff=0.6)
    hook.set_opacity(0)
    self.play(hook.animate.set_opacity(1), run_time=0.4)

    # Stage 4: Final polish
    current_visual = VGroup(title, hook)
    self.play(current_visual.animate.scale(1.03), rate_func=there_and_back, run_time=0.4)

    # Fill remaining intro time (DO NOT REMOVE)
    remaining_intro = (intro_start_time + VIDEO_CONFIG["intro_duration"]) - self.renderer.time
    if remaining_intro > 0:
        self.wait(remaining_intro)
    # ── END INTRO ──────────────────────────────

    # ── SECTIONS ───────────────────────────────
    for section in assets["sections"]:
        section_start_time = self.renderer.time

        new_headline = self.get_styled_text(section["headline"], is_main=True)
        if new_headline.width > manim_config.frame_width * 0.85:
            new_headline.scale_to_fit_width(manim_config.frame_width * 0.85)

        section_visual = self.create_custom_visual(section)
        if section_visual.width > manim_config.frame_width * 0.85:
            section_visual.scale_to_fit_width(manim_config.frame_width * 0.85)

        new_group = VGroup(new_headline, section_visual).arrange(DOWN, buff=1.0)
        new_group.move_to(ORIGIN + UP * 0.5)

        self.play(ReplacementTransform(current_visual, new_group), run_time=1.0)
        current_visual = new_group

        remaining_preroll = (section_start_time + VIDEO_CONFIG["section_preroll"]) - self.renderer.time
        if remaining_preroll > 0:
            self.wait(remaining_preroll)

        caption_container = self.start_captions(section["timing"], section_start_time=section_start_time)
        self.play_dynamic_animations(section_visual, section["padded_duration"])

        remaining = (section_start_time + section["padded_duration"]) - self.renderer.time
        if remaining > 0:
            self.wait(remaining)

        self.clear_captions(caption_container)

    # ── OUTRO ──────────────────────────────────
    outro_start_time = self.renderer.time
    outro_text = self.get_styled_text(assets["outro"], is_main=True)
    self.play(ReplacementTransform(current_visual, outro_text), run_time=0.8)

    remaining = (outro_start_time + VIDEO_CONFIG["outro_duration"]) - self.renderer.time
    if remaining > 0:
        self.wait(remaining)
```

---

## 🎨 VISUAL / ANIMATION FUNCTIONS

You MUST implement these methods:

### def create_custom_visual(self, section) -> VGroup
Return ONE cohesive VGroup (shapes + text) representing the section graphic.
- Use Circle, Rectangle, Arrow, Text, etc.
- Check width: `if visual.width > manim_config.frame_width * 0.85: visual.scale_to_fit_width(...)`

### def play_dynamic_animations(self, visual, duration)
Animate the visual with multi-step engaging sequences (Create, Write, DrawBorderThenFill, Transform, etc).
- Total run_time ≤ duration × 0.8
- Never leave the visual completely static

---

## 📱 VERTICAL DESIGN RULES
- Center or stack vertically
- Never overflow horizontally
- Use .next_to() for spacing
- Keep margins safe

---

## ✅ FINAL CHECKLIST
- Code runs without modification ✓
- Timing is exact ✓ (total intro anim time ≤ VIDEO_CONFIG["intro_duration"])
- current_visual always updated ✓
- No leftover objects ✓
- Only Python output ✓

---

Return ONLY the Python script.
"""

        try:
            code = self.llm.generate_text(prompt=prompt)
        except Exception as exc:
            raise SceneGenerationError(f"Scene generation failed: {exc}") from exc

        # Clean markdown fences if model still outputs them
        if code.startswith("```python"):
            code = code[9:]
        elif code.startswith("```"):
            code = code[3:]
        if code.endswith("```"):
            code = code[:-3]

        code = code.strip() + "\n"

        # Apply sanitizer to fix common LLM errors
        code = sanitize_scene_code(code)

        return code
