import json
import logging
import re
from typing import Any

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


# Methods that are ALREADY implemented on BaseProductionScene
# and must NOT be overridden by the LLM
_PROTECTED_METHODS = [
    "play_scan_reveal",
    "play_emerge",
    "play_ripple_reveal",
    "play_draw_reveal",
    "play_staggered_assemble",
    "play_spiral_reveal",
    "play_glow_in",
    "play_particle_assemble",
    "play_ai_reveal",
    "play_morph_reveal",
    "play_random_reveal",
    "play_generative_transition",
    "add_ambient_animation",
    "start_captions",
    "clear_captions",
    "get_particle_field",
    "get_glowing_path",
    "get_styled_text",
]

_PROTECTED_METHOD_PATTERN = re.compile(
    r"^\s+def (" + "|".join(_PROTECTED_METHODS) + r")\s*\("
)

_END_OF_METHOD = re.compile(r"^\S|^$")


def sanitize_scene_code(code: str) -> str:
    """Post-process LLM-generated Manim code to fix common errors automatically.
    Strips overrides of BaseProductionScene's protected methods.
    """

    lines = code.split("\n")
    cleaned = []
    skip_until_outdent = False
    skip_depth = 0

    for line in lines:
        # ── 0. Strip overrides of protected methods ──
        if _PROTECTED_METHOD_PATTERN.match(line):
            logging.debug(
                "sanitizer: stripping override of protected method: %s",
                line.strip(),
            )
            skip_until_outdent = True
            skip_depth = 0
            continue

        if skip_until_outdent:
            # Count indentation to find end of method body
            stripped = line.lstrip()
            if not stripped:
                # Empty line inside method body
                continue
            if stripped.startswith("#") and not stripped.startswith("# Override"):
                # Comment inside method body
                continue
            indent = len(line) - len(stripped)
            if indent <= 4 and indent >= 0:
                # Back to class-level or top-level
                skip_until_outdent = False
                cleaned.append(line)
                continue
            # Still inside method body — skip
            continue

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
## 🏆 PREMIUM INTRO — GENERATIVE ANIMATIONS

The intro is the MOST IMPORTANT part of the video.
Use VARIED "GENERATION" animation techniques — no repetitive zoom/scale effects.

### ⏱ HARD TIMING CONSTRAINT
Total duration for ALL intro animations MUST be ≤ VIDEO_CONFIG["intro_duration"] ({intro_duration}s).
The system will fill remaining time with a wait. If your animations exceed this, captions will be OUT OF SYNC.

### 📐 INTRO STRUCTURE — title MUST appear FIRST
The title must be visible from the VERY FIRST FRAME (within your first self.play() call).
DO NOT play background effects before the title.

Follow this flow with **DIFFERENT generative animations** at each stage:
1. Title appears IMMEDIATELY — use `self.play_scan_reveal(title, direction=UP, run_time=0.9)` (NOT a simple FadeIn/scale)
2. While title is visible, add accent elements (underline draws itself with `Create`, glow expands with `FadeIn`)
3. Hook/subtitle emerges — use `self.play_ripple_reveal(hook, run_time=0.8)` or `self.play_glow_in(hook, run_time=0.6)` (NOT just set_opacity)
4. Final subtle polish with a soft ring glow (NOT an aggressive scale pulse)
5. Exit: dissolve group with `FadeOut(group, shift=UP*0.2)` and scatter particles outward

### ✅ AVAILABLE GENERATIVE METHODS (use these INSTEAD of FadeIn/scale)
- `self.play_scan_reveal(mob, direction=UP/DOWN/LEFT/RIGHT, run_time=...)` — scanner beam reveals content
- `self.play_emerge(mob, run_time=..., scale_from=0.3, rotation=TAU/12)` — burst forth from a point
- `self.play_ripple_reveal(mob, run_time=..., n_rings=3)` — concentric rings expand, mob fades in
- `self.play_draw_reveal(mob, run_time=..., stroke_color=...)` — draw outline then fill
- `self.play_glow_in(mob, run_time=..., glow_color=...)` — soft glow expands, mob fades in
- `self.play_spiral_reveal(mob, run_time=...)` — spiral trajectory reveals content
- `self.play_morph_reveal(mob, run_time=..., morph_color=...)` — circle morphs into mob shape
- `self.play_staggered_assemble(elements, run_time=..., lag_ratio=0.15)` — each sub-element gets unique animation
- `self.play_particle_assemble(mob, run_time=..., particle_count=30)` — particles converge to form shape
- `self.play_premium_transition(old, new, style=0-4, run_time=1.2, accent_color=...)` — 5 distinct transition styles
- `self.play_full_duration_animation(visual, total_time, accent_color=...)` — slow breathing animation that fills entire section

### ❌ FORBIDDEN
- `self.play_ai_reveal()` — too generic and slow
- Animations before the title appears
- Total animation run_time > VIDEO_CONFIG["intro_duration"]
- Simple FadeIn or scale-up for the title/hook — MUST use a generative method instead
- `smooth` or `linear` rate functions — they lack premium deceleration character
- Quick burst animations that finish early — every animation should fill its allocated time
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

6. **🚫 CRITICAL: DO NOT OVERRIDE BaseProductionScene methods** — The following methods are ALREADY implemented on `BaseProductionScene` and your generated class MUST NOT define, override, or re-implement them. Any `def method_name(...)` line matching one of these will be automatically stripped by the sanitizer:
   - `play_scan_reveal`, `play_emerge`, `play_ripple_reveal`, `play_draw_reveal`
   - `play_staggered_assemble`, `play_spiral_reveal`, `play_glow_in`
   - `play_particle_assemble`, `play_ai_reveal`, `play_morph_reveal`
   - `play_random_reveal`, `play_generative_transition`, `add_ambient_animation`
   - `play_premium_transition`, `play_full_duration_animation`
   - `_transition_spiral_wipe`, `_transition_radial_scan`, `_transition_particle_morph`
   - `_transition_fold_unfold`, `_transition_glow_sweep`
   - `start_captions`, `clear_captions`, `get_particle_field`, `get_glowing_path`, `get_styled_text`
   Simply call them via `self.method_name(...)` — they work perfectly.


---

## 🎬 ANIMATION PRINCIPLES — GENERATIVE FIRST + PREMIUM DECELERATION

1. **GENERATIVE ANIMATIONS** — Use the `self.play_*()` methods listed above from `BaseProductionScene`. These create true "emergence" effects where content looks like it is being created in real-time. NO repetitive zoom/scale patterns. NO boring FadeIn/scale.

2. **PREMIUM DECELERATION (CRITICAL)** — Every animation MUST "slow down at the end" like a luxury car coming to a stop. Use strong ease-out rate functions:
   - `rate_functions.ease_out_quint` — strongest deceleration, most premium feel
   - `rate_functions.ease_out_cubic` — smooth premium deceleration
   - `rate_functions.ease_out_back` — premium with a subtle overshoot
   - `rate_functions.ease_out_sine` — gentle coast to stop
   - ❌ NEVER use `smooth` (symmetric ease) for reveal/emergence animations — it has no deceleration character
   - ❌ NEVER use `linear` — it feels robotic

3. **PREMIUM SECTION TRANSITIONS** — Use `self.play_premium_transition(old, new, style=..., run_time=1.2, accent_color=...)` instead of generic ReplacementTransform. The 5 built-in styles (spiral_wipe, radial_scan, particle_morph, fold_unfold, glow_sweep) each have unique visual character and strong ease-out. Never use the same transition style twice in a row.

4. **FULL-DURATION ANIMATION** — Use `self.play_full_duration_animation(visual, remaining_time)` to make the section visual animate **for the entire remaining section duration**. This creates a slow, elegant breathing motion that coasts to stillness at the end — not a quick burst that leaves content static.

5. **VARIETY BETWEEN SECTIONS** — Each section MUST use a DIFFERENT animation style. If section 1 uses `scan_reveal`, section 2 must use `ripple_reveal`, section 3 must use `glow_in`, etc. Never repeat the same animation method for two consecutive sections.

6. **SUBTLE AMBIENT ANIMATION** — Use `self.add_ambient_animation(mobject)` to apply a gentle floating motion to elements during their time on screen. This keeps elements feeling "alive" during scene turns.

7. **CENTERED LAYOUT** — Always center the combined group of headline + visual on screen.

8. **CONTINUITY** — Use `ReplacementTransform` to morph between scenes. No slide-switching cuts.

9. **DEPTH** — Use `self.get_particle_field()` ONCE globally at the start.

10. **CORRECT MANIM API:**
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

    # ── INTRO (GENERATIVE ANIMATIONS) ──────────
    # title appears IMMEDIATELY — use SCAN REVEAL (NOT FadeIn/scale)
    title = self.get_styled_text(assets["title"], is_main=True)
    if title.width > manim_config.frame_width * 0.85:
        title.scale_to_fit_width(manim_config.frame_width * 0.85)
    title.move_to(ORIGIN + UP * 0.4)
    self.play_scan_reveal(title, direction=UP, run_time=0.9)

    hook = self.get_styled_text(assets["hook"], is_main=False)
    if hook.width > manim_config.frame_width * 0.75:
        hook.scale_to_fit_width(manim_config.frame_width * 0.75)

    # Stage 2: Accent line draws itself (Create) + glow aura expands
    accent_line = Line(LEFT * title.width * 0.45, RIGHT * title.width * 0.45, color=THEME["secondary_color"], stroke_width=5)
    accent_line.next_to(title, DOWN, buff=0.35)
    self.play(Create(accent_line), run_time=0.35)
    line_glow = Line(LEFT * title.width * 0.45, RIGHT * title.width * 0.45, color=THEME["secondary_color"], stroke_width=16)
    line_glow.next_to(title, DOWN, buff=0.35).set_opacity(0.25)
    self.play(FadeIn(line_glow, scale=0.3), run_time=0.25)

    # Stage 3: Hook appears with GLOW IN or RIPPLE reveal (NOT simple opacity)
    hook.next_to(accent_line, DOWN, buff=0.45)
    self.play_glow_in(hook, run_time=0.6, glow_color=THEME["secondary_color"])

    # Stage 4: Final subtle polish — soft ring glow, NO aggressive scale pulse
    intro_group = VGroup(title, accent_line, line_glow, hook)
    polish_ring = Circle(radius=2.8, color=THEME["secondary_color"], stroke_width=1, fill_opacity=0)
    polish_ring.move_to(intro_group.get_center()).set_opacity(0.15)
    self.add(polish_ring)
    self.play(polish_ring.animate.scale(1.4).set_opacity(0), rate_func=rate_functions.ease_out_cubic, run_time=0.5)

    # Fill remaining intro time (DO NOT REMOVE)
    remaining_intro = (intro_start_time + VIDEO_CONFIG["intro_duration"]) - self.renderer.time
    if remaining_intro > 0:
        self.wait(remaining_intro)

    # Fade out intro completely — DO NOT transform it into sections
    self.play(FadeOut(intro_group, shift=UP * 0.2), run_time=0.4)
    # ── END INTRO ──────────────────────────────

    # ── SECTIONS (VARIED GENERATIVE TRANSITIONS) ──
    current_visual = None
    # Track audio-visual offset — intro FadeOut can add ~0.4s gap
    video_audio_offset = self.renderer.time - VIDEO_CONFIG["intro_duration"]
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

        if current_visual is None:
            # First section — fade in fresh (no prior visual to transform)
            self.play(FadeIn(new_group, shift=UP * 0.3), run_time=0.6)
        else:
            # PREMIUM TRANSITION with strong ease-out deceleration
            # Uses one of 5 distinct transition styles (never repeats)
            self.play_premium_transition(
                current_visual,
                new_group,
                style=None,  # auto-picks random unique style
                run_time=1.2,
                accent_color=THEME["secondary_color"],
            )
        current_visual = new_group

        # Subtle ambient float during preroll
        stop_ambient = self.add_ambient_animation(new_group)

        remaining_preroll = (section_start_time + VIDEO_CONFIG["section_preroll"]) - self.renderer.time
        if remaining_preroll > 0:
            self.wait(remaining_preroll)

        # Pass audio-offset-corrected timing so captions sync with the continuous audio track
        caption_container = self.start_captions(
            section["timing"],
            section_start_time=section_start_time,
            offset=VIDEO_CONFIG["section_preroll"] - video_audio_offset,
        )

        # FULL-DURATION VISUAL ANIMATION — breathes for entire section
        remaining_time = (section_start_time + section["padded_duration"]) - self.renderer.time
        if remaining_time > 0.5:
            anim_stop = self.play_full_duration_animation(
                section_visual, remaining_time,
                accent_color=section.get("accent_color") or THEME["secondary_color"]
            )

        stop_ambient()

        remaining = (section_start_time + section["padded_duration"]) - self.renderer.time
        if remaining > 0:
            self.wait(remaining)

        if remaining_time > 0.5:
            anim_stop()

        self.clear_captions(caption_container)

    # ── OUTRO (SPIRAL REVEAL + RING) ───────────
    outro_start_time = self.renderer.time
    outro_text = self.get_styled_text(assets["outro"], is_main=True)
    # Particle burst old content away
    particles = VGroup(*[Dot(point=current_visual.get_center()+np.random.uniform(-0.3,0.3,3), radius=np.random.uniform(0.02,0.05), color=THEME["accent_color"], fill_opacity=0.6) for _ in range(10)])
    self.add(particles)
    self.play(FadeOut(current_visual, scale=0.8), *[p.animate.move_to(p.get_center()+np.random.uniform(-2,2,3)).set_opacity(0) for p in particles], run_time=0.5)
    self.remove(particles)
    # Outro emerges with spiral reveal
    outro_text.move_to(ORIGIN)
    self.play_spiral_reveal(outro_text, run_time=1.0)
    ring = Circle(color=THEME["accent_color"], stroke_width=3, fill_opacity=0).surround(outro_text, buffer_factor=1.15)
    self.play(Create(ring), run_time=0.5)
    # Gentle glow pulse
    glow = Dot(outro_text.get_center(), color=THEME["accent_color"], radius=0.3, fill_opacity=0.15)
    self.add(glow)
    self.play(glow.animate.scale(4).set_opacity(0), run_time=0.8)
    self.remove(glow)

    remaining = (outro_start_time + VIDEO_CONFIG["outro_duration"]) - self.renderer.time
    if remaining > 0:
        self.wait(remaining)
```

---

## 🎨 VISUAL / ANIMATION FUNCTIONS

You MUST implement these methods:

### def create_custom_visual(self, section) -> VGroup
Return ONE cohesive VGroup (shapes + text) representing the section graphic.
- **CRITICAL: Each section MUST have a UNIQUE visual** — design it based on the section's actual content (headline, bullets, keywords, visual_description), NOT just the visual type.
- Use Circle, Rectangle, Arrow, Text, etc. Be creative with layouts specific to the content.
- **IMPORTANT: For any `Text()` elements within visuals, always use `font=THEME["font"]`** to ensure the correct script (Latin, Devanagari, CJK, etc.) renders properly. NEVER hardcode a font name like `"Sans"` or `"Helvetica"`.
- Check width: `if visual.width > manim_config.frame_width * 0.85: visual.scale_to_fit_width(...)`

### def play_dynamic_animations(self, visual, duration)
Animate the visual with **the generative animation methods from BaseProductionScene**:
- Choose a DIFFERENT method for each section: `self.play_scan_reveal()`, `self.play_emerge()`, `self.play_ripple_reveal()`, `self.play_glow_in()`, `self.play_spiral_reveal()`, `self.play_morph_reveal()`, `self.play_draw_reveal()`, or `self.play_staggered_assemble()`
- **CRITICAL: Each section MUST use a DIFFERENT animation method** — track which ones you've used and never repeat within the same video.
- **PREMIUM DECELERATION**: Use strong ease-out rate functions — `rate_functions.ease_out_quint` or `rate_functions.ease_out_cubic` — NEVER `smooth` or `linear`.
- **FULL DURATION**: Spread the animation across the entire duration, not a quick burst. The visual should animate until the very end of the section, coasting to stillness.
- Total run_time ≤ duration × 0.85 (but should be close to this for maximum impact)

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
