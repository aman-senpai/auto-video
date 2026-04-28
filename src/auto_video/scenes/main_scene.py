import json
import os

import numpy as np
from manim import *
from manim import config as manim_config

from auto_video.config import THEME, VIDEO_CONFIG
from auto_video.scenes.base_scene import BaseProductionScene

manim_config.pixel_height = VIDEO_CONFIG["pixel_height"]
manim_config.pixel_width = VIDEO_CONFIG["pixel_width"]
manim_config.frame_height = VIDEO_CONFIG["frame_height"]
manim_config.frame_width = VIDEO_CONFIG["frame_width"]
manim_config.frame_rate = VIDEO_CONFIG["frame_rate"]
manim_config.background_color = VIDEO_CONFIG["background_color"]


class ProductionScene(BaseProductionScene):
    def construct(self):
        assets = json.load(open(os.environ["AUTO_VIDEO_ASSETS"]))
        self.add(self.get_particle_field(count=20))
        self._intro_start_time = self.renderer.time

        # --- PREMIUM INTRO ---
        current_visual = self._play_intro(assets)

        # --- SECTIONS ---
        for section in assets["sections"]:
            section_start_time = self.renderer.time

            new_headline = self.get_styled_text(section["headline"], is_main=True)
            if new_headline.width > manim_config.frame_width * 0.85:
                new_headline.scale_to_fit_width(manim_config.frame_width * 0.85)

            section_visual = self._create_section_visual(section)
            if section_visual.width > manim_config.frame_width * 0.85:
                section_visual.scale_to_fit_width(manim_config.frame_width * 0.85)

            new_group = VGroup(new_headline, section_visual).arrange(DOWN, buff=1.0)
            new_group.move_to(ORIGIN + UP * 0.5)

            self.play(
                ReplacementTransform(current_visual, new_group),
                run_time=1.0,
            )
            current_visual = new_group

            remaining_preroll = (
                section_start_time + VIDEO_CONFIG["section_preroll"]
            ) - self.renderer.time
            if remaining_preroll > 0:
                self.wait(remaining_preroll)

            caption_container = self.start_captions(
                section["timing"], section_start_time=section_start_time
            )

            self._animate_section_visual(
                section_visual, section.get("padded_duration", 6.0)
            )

            remaining = (
                section_start_time + section["padded_duration"]
            ) - self.renderer.time
            if remaining > 0:
                self.wait(remaining)

            self.clear_captions(caption_container)

        # --- OUTRO ---
        outro_start_time = self.renderer.time
        outro_text = self.get_styled_text(assets.get("outro", "Follow for more."))
        self.play(ReplacementTransform(current_visual, outro_text), run_time=0.8)

        remaining = (
            outro_start_time + VIDEO_CONFIG["outro_duration"]
        ) - self.renderer.time
        if remaining > 0:
            self.wait(remaining)

    # ──────────────────────────────────────────────
    #  PREMIUM INTRO
    # ──────────────────────────────────────────────

    def _play_intro(self, assets):
        """Multi-stage premium intro animation. Returns the final VGroup."""

        # 1. Background glow
        bg_glow = Circle(
            radius=3.5,
            color=THEME["secondary_color"],
            stroke_width=0,
            fill_opacity=0.04,
        )
        self.play(FadeIn(bg_glow, scale=2.0), run_time=0.5)

        # 2. Title — scale-up with bounce
        title = self.get_styled_text(assets.get("title", "Video"), is_main=True)
        if title.width > manim_config.frame_width * 0.85:
            title.scale_to_fit_width(manim_config.frame_width * 0.85)
        title.move_to(ORIGIN + UP * 0.5)
        title.save_state()
        title.scale(0.4).set_opacity(0)

        self.play(
            title.animate.restore(),
            rate_func=rate_functions.ease_out_bounce,
            run_time=1.2,
        )
        self.wait(0.15)

        # 3. Accent line — grows from center
        accent_line = Line(
            LEFT * title.width * 0.45,
            RIGHT * title.width * 0.45,
            color=THEME["secondary_color"],
            stroke_width=5,
        )
        accent_line.next_to(title, DOWN, buff=0.35)
        accent_line.save_state()
        accent_line.scale(0)

        line_glow = Line(
            LEFT * title.width * 0.45,
            RIGHT * title.width * 0.45,
            color=THEME["secondary_color"],
            stroke_width=14,
        )
        line_glow.next_to(title, DOWN, buff=0.35)
        line_glow.set_opacity(0.2)
        line_glow.save_state()
        line_glow.scale(0)

        self.play(
            accent_line.animate.restore(),
            line_glow.animate.restore(),
            run_time=0.5,
        )

        # 4. Accent dot at center
        accent_dot = Dot(
            accent_line.get_center(),
            color=THEME["accent_color"],
            radius=0.08,
        )
        self.play(FadeIn(accent_dot, scale=3.0), run_time=0.3)

        # 5. Hook / subtitle
        hook = self.get_styled_text(assets.get("hook", ""), is_main=False)
        if hook.width > manim_config.frame_width * 0.75:
            hook.scale_to_fit_width(manim_config.frame_width * 0.75)
        hook.next_to(accent_line, DOWN, buff=0.45)
        hook.set_opacity(0)

        self.play(hook.animate.set_opacity(1), run_time=0.6)

        # 6. Final pulse
        group = VGroup(title, accent_line, line_glow, accent_dot, hook, bg_glow)
        self.play(
            group.animate.scale(1.04),
            rate_func=there_and_back,
            run_time=0.6,
        )

        remaining = (
            self._intro_start_time + VIDEO_CONFIG["intro_duration"]
        ) - self.renderer.time
        if remaining > 0:
            self.wait(remaining)

        return group

    # ──────────────────────────────────────────────
    #  SECTION VISUALS
    # ──────────────────────────────────────────────

    def _create_section_visual(self, section):
        """Build a simple visual representation for a section."""
        visual_type = section.get("visual", "concept")
        accent_color = section.get("accent_color") or THEME["secondary_color"]
        bullets = section.get("bullets", [])[:3]
        keywords = section.get("keywords", [])[:3]

        elements = VGroup()

        if visual_type in ("stat", "comparison") and keywords:
            for kw in keywords[:2]:
                kw_text = Text(
                    kw.upper(),
                    font=THEME["font"],
                    font_size=44,
                    weight=BOLD,
                    color=accent_color,
                )
                elements.add(kw_text)
        elif visual_type in ("process", "timeline") and bullets:
            for bullet in bullets[:3]:
                dot = Dot(radius=0.08, color=accent_color)
                line = self.get_styled_text(bullet, is_main=False)
                if line.width > manim_config.frame_width * 0.6:
                    line.scale_to_fit_width(manim_config.frame_width * 0.6)
                row = VGroup(dot, line).arrange(RIGHT, buff=0.3, aligned_edge=UP)
                elements.add(row)
        else:
            for kw in keywords[:3]:
                chip = RoundedRectangle(
                    corner_radius=0.2,
                    width=len(kw) * 0.3 + 0.4,
                    height=0.4,
                    stroke_color=accent_color,
                    stroke_width=2,
                    fill_opacity=0.1,
                )
                label = Text(
                    kw.upper(),
                    font=THEME["font"],
                    font_size=24,
                    color=accent_color,
                )
                elements.add(VGroup(chip, label))

        if not elements:
            fallback = self.get_styled_text(section.get("text", "")[:80], is_main=False)
            elements.add(fallback)

        elements.arrange(DOWN, buff=0.4, aligned_edge=LEFT)
        elements.move_to(ORIGIN)
        return elements

    def _animate_section_visual(self, visual, duration):
        """Animate the section visual elements."""
        if not visual or not visual.submobjects:
            return

        max_anim_time = min(duration * 0.7, 3.0)
        if max_anim_time <= 0:
            return

        self.play(
            LaggedStart(
                *[FadeIn(mob, shift=UP * 0.2, scale=0.9) for mob in visual.submobjects],
                lag_ratio=0.15,
            ),
            run_time=min(max_anim_time, len(visual.submobjects) * 0.2 + 0.5),
        )
