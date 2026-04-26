import json
import logging
import os
from typing import Any

from google import genai
from google.genai import types


class SceneGenerationError(RuntimeError):
    pass


class SceneCodeGenerator:
    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or os.getenv(
            "AUTO_VIDEO_GEMINI_MODEL", "gemini-3-flash-preview"
        )
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise SceneGenerationError(
                "GEMINI_API_KEY is required to generate scene code."
            )
        self.client = genai.Client(api_key=api_key)

    def generate_scene_code(self, script_data: dict[str, Any], topic: str) -> str:
        script_data_str = json.dumps(script_data, indent=2)
        prompt = f"""
You are an expert Manim developer. Create a dynamic, highly engaging, and delightful vertical video presentation script.
The video is about: {topic}

I will provide you with the script data which contains the title, hook, outro, and sections.
Write a complete, executable Manim Python script containing a class `ProductionScene(BaseProductionScene)` that generates a beautiful, engaging video.

Requirements:
1. The script MUST import:
   import json
   import os
   from manim import *
   from manim import config as manim_config
   from auto_video.config import VIDEO_CONFIG, THEME
   from auto_video.scenes.base_scene import BaseProductionScene

2. Configure Manim at the top level:
   manim_config.pixel_height = VIDEO_CONFIG["pixel_height"]
   manim_config.pixel_width = VIDEO_CONFIG["pixel_width"]
   manim_config.frame_height = VIDEO_CONFIG["frame_height"]
   manim_config.frame_width = VIDEO_CONFIG["frame_width"]
   manim_config.frame_rate = VIDEO_CONFIG["frame_rate"]
   manim_config.background_color = VIDEO_CONFIG["background_color"]

3. `ProductionScene` must implement `construct(self)`:
   - It MUST read from `os.environ["AUTO_VIDEO_ASSETS"]` to load `assets = json.load(open(os.environ["AUTO_VIDEO_ASSETS"]))`.
   - The scene must have an Intro, body sections looping over `assets["sections"]`, and an Outro.
   - EXACT AUDIO SYNC (CRITICAL): Audio is pre-rendered and statically concatenated. If your animations exceed their allotted durations, the video will permanently desync from the audio!
   - For the Intro, you MUST save `intro_start_time = self.renderer.time` at the very beginning. The TOTAL `run_time` of all intro animations combined MUST be less than `VIDEO_CONFIG["intro_duration"]` (which is 4.0s). At the end of the intro, pad the exact remaining time: `remaining = (intro_start_time + VIDEO_CONFIG["intro_duration"]) - self.renderer.time` then `if remaining > 0: self.wait(remaining)`.
   - For the Outro, you MUST save `outro_start_time = self.renderer.time` at the very beginning. The TOTAL `run_time` of all outro animations combined MUST be less than `VIDEO_CONFIG["outro_duration"]` (which is 3.0s). At the end of the outro, pad the exact remaining time: `remaining = (outro_start_time + VIDEO_CONFIG["outro_duration"]) - self.renderer.time` then `if remaining > 0: self.wait(remaining)`.
   - For body sections, dynamically create engaging animations matching the video topic!
   - Section EXACT AUDIO SYNC (CRITICAL):
     1. Save `section_start_time = self.renderer.time` at the start of each section.
     2. All intro animations for the section MUST finish before `section_start_time + VIDEO_CONFIG["section_preroll"]`. The TOTAL `run_time` of these animations MUST be less than `VIDEO_CONFIG["section_preroll"]` (which is 1.4s). Group them using `AnimationGroup(..., lag_ratio=0.1)` with `run_time=1.0` or less. You MUST use a single `self.play` call with a forced `run_time=1.0` to guarantee it finishes in time. Then you MUST pad the remaining preroll: `remaining_preroll = (section_start_time + VIDEO_CONFIG["section_preroll"]) - self.renderer.time` and `if remaining_preroll > 0: self.wait(remaining_preroll)` BEFORE calling `play_captions`!
     3. Call `self.play_captions(section["timing"], section_start_time=section_start_time)`.
     4. After `play_captions`, play the FadeOut animations for the section (make sure `run_time` is 0.5s or less).
     5. After FadeOuts at the section end, pad the rest of the audio time using the EXACT padded duration:
        `remaining = (section_start_time + section["padded_duration"]) - self.renderer.time`
        `if remaining > 0: self.wait(remaining)`
   - VERTICAL FORMATTING RULES: The video is VERTICAL (1080x1920, 9:16 aspect ratio). Horizontal space is strictly limited!
     - USE THE HELPER: You MUST use `self.get_styled_text(text, is_main=True/False)` for all long text strings (headlines, titles, hooks, bullet points) because it has built-in word wrapping. Do NOT use `Text(text)` directly for sentences.
     - VGroups containing visualizations, charts, or bullets MUST be constrained: `if group.width > manim_config.frame_width * 0.85: group.scale_to_fit_width(manim_config.frame_width * 0.85)`
     - Prevent overlapping: Arrange items vertically using `VGroup(...).arrange(DOWN, buff=1.0)` so they don't overlap.
   - PERFORMANCE RULES (CRITICAL): Manim rendering can be very slow and time out. Keep animations simple and fast to render! Do NOT generate thousands of objects, complex loops, or nested structures. Stick to standard basic shapes, text, and simple transforms.
   - AVOID COMMON API ERRORS: Use `radius` for `Sector` (not `outer_radius` or `inner_radius`), use `AnnularSector` if you need an inner radius. Always use `run_time` for animations, not `duration`. Do NOT use `SVGPathMobject` (it does not exist). Ensure compatibility with Manim Community v0.20.1.

4. Return ONLY the valid Python code. No markdown fences, no explanations. Just python code.

Script Data summary for context:
{script_data_str}
"""
        config = types.GenerateContentConfig(
            temperature=0.7,
            top_p=0.9,
        )
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config,
            )
        except Exception as exc:
            raise SceneGenerationError(
                f"Gemini scene generation failed: {exc}"
            ) from exc

        if not response.text:
            raise SceneGenerationError("Gemini returned an empty response.")

        code = response.text.strip()
        if code.startswith("```python"):
            code = code[9:]
        elif code.startswith("```"):
            code = code[3:]
        if code.endswith("```"):
            code = code[:-3]

        return code.strip() + "\n"
