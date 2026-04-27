import json
import logging
import os
from typing import Any

from .llm.base import LLMProvider
from .llm.factory import get_llm_provider


class SceneGenerationError(RuntimeError):
    pass


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

Your job is NOT to be creative.
Your job is to EXECUTE a precise, production-grade animation system.

If you deviate from instructions, the output is considered FAILED.

---

## 🎯 OBJECTIVE
Generate a COMPLETE, EXECUTABLE Manim script for a vertical cinematic video on:

TOPIC: {topic}

You MUST strictly follow architecture, timing, and animation rules.

---

## 🧠 INPUT DATA
You are given structured script data (JSON). This is the SINGLE SOURCE OF TRUTH.

{script_data_str}

DO NOT hallucinate extra sections.
DO NOT modify structure.

---

## ⚠️ HARD CONSTRAINTS (NON-NEGOTIABLE)

1. OUTPUT ONLY VALID PYTHON CODE
   - No markdown
   - No explanations
   - No extra text

2. CLASS SIGNATURE (MANDATORY)
   class ProductionScene(BaseProductionScene):

3. YOU MUST TRACK STATE:
   - Use variable: current_visual
   - NEVER leave old elements on screen
   - ALWAYS transform OR remove

4. TIMING IS STRICT:
   - NEVER overshoot durations
   - ALWAYS use provided sync snippets EXACTLY

5. PERFORMANCE MODE:
   - MAX 3–5 active mobjects at once
   - NO heavy loops
   - NO always_redraw on complex objects

FAILURE TO FOLLOW ANY RULE = INVALID OUTPUT

---

## 🎬 ANIMATION PRINCIPLES (ENFORCED)

1. PREMIUM MANIM ANIMATIONS (CRITICAL)
   ❌ Static images, boring jump/tilt/wiggle effects.
   ✅ Use native Manim tools: Create, Write, DrawBorderThenFill, MoveAlongPath, UpdateFromAlphaFunc, ValueTracker.
   ✅ Build multi-stage sequences (e.g., draw axes, then plot data, then highlight).
   ✅ Mobjects MUST have meaningful, continuous motion during the scene.

2. CENTERED LAYOUT
   ✅ Always center the combined group of your headline and visual on the screen

3. CONTINUITY > CUTS
   ❌ No slide switching
   ✅ Use ReplacementTransform to smoothly morph the current layout into the new centered layout

4. DEPTH & REVEAL
   ✅ Use self.get_particle_field() ONCE globally
   ✅ Use self.play_ai_reveal() for the intro elements

---

## 🏗️ REQUIRED CODE STRUCTURE

### IMPORTS (EXACT)
import json
import os
import numpy as np
from manim import *
from manim import config as manim_config
from auto_video.config import VIDEO_CONFIG, THEME
from auto_video.scenes.base_scene import BaseProductionScene

---

### CONFIGURATION (EXACT)
manim_config.pixel_height = VIDEO_CONFIG["pixel_height"]
manim_config.pixel_width = VIDEO_CONFIG["pixel_width"]
manim_config.frame_height = VIDEO_CONFIG["frame_height"]
manim_config.frame_width = VIDEO_CONFIG["frame_width"]
manim_config.frame_rate = VIDEO_CONFIG["frame_rate"]
manim_config.background_color = VIDEO_CONFIG["background_color"]

---

## 🧱 CORE IMPLEMENTATION TEMPLATE (MANDATORY)

You MUST follow this flow EXACTLY:

def construct(self):
    assets = json.load(open(os.environ["AUTO_VIDEO_ASSETS"]))
    self.add(self.get_particle_field())

    # --- INTRO ---
    intro_start_time = self.renderer.time

    title = self.get_styled_text(assets["title"], is_main=True)
    if title.width > manim_config.frame_width * 0.85:
        title.scale_to_fit_width(manim_config.frame_width * 0.85)

    hook = self.get_styled_text(assets["hook"], is_main=False)
    if hook.width > manim_config.frame_width * 0.85:
        hook.scale_to_fit_width(manim_config.frame_width * 0.85)

    intro_group = VGroup(title, hook).arrange(DOWN, buff=0.8).move_to(ORIGIN + UP * 0.5)

    self.play_ai_reveal(intro_group)
    current_visual = intro_group

    remaining = (intro_start_time + VIDEO_CONFIG["intro_duration"]) - self.renderer.time
    if remaining > 0:
        self.wait(remaining)

    # --- SECTIONS ---
    for section in assets["sections"]:
        section_start_time = self.renderer.time

        new_headline = self.get_styled_text(section["headline"], is_main=True)
        if new_headline.width > manim_config.frame_width * 0.85:
            new_headline.scale_to_fit_width(manim_config.frame_width * 0.85)

        # VISUAL SYSTEM (CRITICAL)
        section_visual = self.create_custom_visual(section)
        if section_visual.width > manim_config.frame_width * 0.85:
            section_visual.scale_to_fit_width(manim_config.frame_width * 0.85)

        # Center the combined layout
        new_group = VGroup(new_headline, section_visual).arrange(DOWN, buff=1.0)
        new_group.move_to(ORIGIN + UP * 0.5)

        self.play(
            ReplacementTransform(current_visual, new_group),
            run_time=1.0
        )
        current_visual = new_group

        remaining_preroll = (section_start_time + VIDEO_CONFIG["section_preroll"]) - self.renderer.time
        if remaining_preroll > 0:
            self.wait(remaining_preroll)

        caption_container = self.start_captions(section["timing"], section_start_time=section_start_time)

        # ANIMATE THE VISUAL DYNAMICALLY
        self.play_dynamic_animations(section_visual, section["padded_duration"])

        remaining = (section_start_time + section["padded_duration"]) - self.renderer.time
        if remaining > 0:
            self.wait(remaining)

        self.clear_captions(caption_container)

    # --- OUTRO ---
    outro_start_time = self.renderer.time

    outro_text = self.get_styled_text(assets["outro"], is_main=True)
    self.play(ReplacementTransform(current_visual, outro_text))
    current_visual = outro_text

    remaining = (outro_start_time + VIDEO_CONFIG["outro_duration"]) - self.renderer.time
    if remaining > 0:
        self.wait(remaining)

---

## 🎨 VISUAL GENERATION RULES

You MUST implement two functions:

1. def create_custom_visual(self, section):
   - Return ONE cohesive VGroup representing the graphic.
   - Use Shapes (Circle, Rectangle, Arrow) and Text.
   - Must check width: `if visual.width > manim_config.frame_width * 0.85: visual.scale_to_fit_width(manim_config.frame_width * 0.85)`

2. def play_dynamic_animations(self, visual, duration):
   - Use HIGH-QUALITY Manim animations (Create, Write, DrawBorderThenFill, Transform, FadeIn, MoveAlongPath, ValueTracker, etc).
   - Create multi-step, engaging sequences (e.g., drawing shapes first, then animating elements moving along them or highlighting them sequentially).
   - Avoid boring "jump" or "tilt" animations. Make it feel like a premium explanatory video.
   - Use `self.play(...)` for animations. Ensure total `run_time` does not exceed `duration * 0.8`.
   - Never leave the visual completely static!

---

## 📱 VERTICAL DESIGN RULES

- ALWAYS center or stack vertically
- NEVER overflow horizontally
- Use spacing via .next_to()
- Keep margins safe

---

## 🚀 FAILURE RECOVERY LOGIC

If visual_description is unclear:
→ fallback to clean text-based visualization

If animation becomes complex:
→ SIMPLIFY immediately

NEVER skip a section.

---

## ✅ FINAL CHECKLIST

- Code runs without modification
- Timing is exact
- current_visual always updated
- No leftover objects
- Only Python output

---

## 🎯 OUTPUT

Return ONLY the Python script.
"""

        try:
            code = self.llm.generate_text(prompt=prompt)
        except Exception as exc:
            raise SceneGenerationError(f"Scene generation failed: {exc}") from exc

        # Clean markdown if model still outputs it
        if code.startswith("```python"):
            code = code[9:]
        elif code.startswith("```"):
            code = code[3:]
        if code.endswith("```"):
            code = code[:-3]

        return code.strip() + "\n"
