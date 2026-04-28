import json
import os
import random

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
    """
    Premium production scene with varied generative animations.

    Key improvements over standard version:
    - No repetitive zoom/scale animations
    - Each section gets a unique "generation" animation style
    - Subtle ambient animations play during scene turns
    - Rich particle and decorative effects during transitions
    """

    def construct(self):
        assets = json.load(open(os.environ["AUTO_VIDEO_ASSETS"]))
        self.add(self.get_particle_field(count=25))
        self._intro_start_time = self.renderer.time

        # ── RICH INTRO ───────────────────────────
        current_visual = self._play_premium_intro(assets)

        # ── SECTIONS ─────────────────────────────
        # Track which animation styles we've used so every section is different
        used_animations = set()
        used_transitions = set()

        for i, section in enumerate(assets["sections"]):
            section_start_time = self.renderer.time

            new_headline = self.get_styled_text(section["headline"], is_main=True)
            if new_headline.width > manim_config.frame_width * 0.85:
                new_headline.scale_to_fit_width(manim_config.frame_width * 0.85)

            section_visual = self._create_section_visual(section)
            if section_visual.width > manim_config.frame_width * 0.85:
                section_visual.scale_to_fit_width(manim_config.frame_width * 0.85)

            new_group = VGroup(new_headline, section_visual).arrange(DOWN, buff=1.0)
            new_group.move_to(ORIGIN + UP * 0.5)

            if i == 0:
                # First section — premium transition from intro
                self._play_premium_section_transition(
                    current_visual, new_group, section, 0, used_transitions
                )
            else:
                # Subsequent sections get varied premium transitions
                self._play_premium_section_transition(
                    current_visual, new_group, section, 1, used_transitions
                )
            current_visual = new_group

            # ── Subtle ambient animation during the preroll ──
            ambient_stop = self.add_ambient_animation(new_group)

            remaining_preroll = (
                section_start_time + VIDEO_CONFIG["section_preroll"]
            ) - self.renderer.time
            if remaining_preroll > 0:
                self.wait(remaining_preroll)

            # ── Captions ──────────────────────
            caption_container = self.start_captions(
                section["timing"], section_start_time=section_start_time
            )

            # ── FULL-DURATION VISUAL ANIMATION (fills remaining section time) ──
            remaining_section_time = (
                section_start_time + section["padded_duration"]
            ) - self.renderer.time
            if remaining_section_time > 0.5:
                anim_stop = self.play_full_duration_animation(
                    section_visual, remaining_section_time,
                    accent_color=section.get("accent_color") or THEME["secondary_color"]
                )

            # Stop ambient during captions so it doesn't fight the captions
            ambient_stop()

            remaining = (
                section_start_time + section["padded_duration"]
            ) - self.renderer.time
            if remaining > 0:
                self.wait(remaining)

            # Stop the full-duration animation
            if remaining_section_time > 0.5:
                anim_stop()

            self.clear_captions(caption_container)

        # ── OUTRO ────────────────────────────────
        outro_start_time = self.renderer.time
        outro_text = self.get_styled_text(assets.get("outro", "Follow for more."))
        if outro_text.width > manim_config.frame_width * 0.85:
            outro_text.scale_to_fit_width(manim_config.frame_width * 0.85)

        self._play_outro_transition(current_visual, outro_text)

        remaining = (
            outro_start_time + VIDEO_CONFIG["outro_duration"]
        ) - self.renderer.time
        if remaining > 0:
            self.wait(remaining)

    # ══════════════════════════════════════════════
    #  PREMIUM INTRO — no repetitive zoom/scale
    # ══════════════════════════════════════════════

    def _play_premium_intro(self, assets):
        """Multi-stage intro with varied generative animations."""

        # ── Stage 1: Ambient particles drift in ──
        particles = self.get_particle_field(count=30, color=THEME["secondary_color"])
        for p in particles:
            p.set_opacity(0)
        self.add(particles)

        self.play(
            *[p.animate.set_opacity(np.random.uniform(0.1, 0.35)) for p in particles],
            rate_func=rate_functions.ease_out_cubic,
            run_time=0.5,
        )

        # ── Stage 2: Title revealed with a SCAN (generation effect) ──
        title = self.get_styled_text(assets.get("title", "Video"), is_main=True)
        if title.width > manim_config.frame_width * 0.85:
            title.scale_to_fit_width(manim_config.frame_width * 0.85)
        title.move_to(ORIGIN + UP * 0.4)

        self.play_scan_reveal(
            title, direction=UP, run_time=0.9, scanner_color=THEME["secondary_color"]
        )

        # ── Stage 3: Accent line draws itself ──
        accent_line = Line(
            LEFT * title.width * 0.45,
            RIGHT * title.width * 0.45,
            color=THEME["secondary_color"],
            stroke_width=5,
        )
        accent_line.next_to(title, DOWN, buff=0.35)

        self.play(
            Create(accent_line),
            rate_func=rate_functions.ease_out_cubic,
            run_time=0.35,
        )

        # ── Stage 3b: Soft glow behind it ──
        line_glow = Line(
            LEFT * title.width * 0.45,
            RIGHT * title.width * 0.45,
            color=THEME["secondary_color"],
            stroke_width=16,
        )
        line_glow.next_to(title, DOWN, buff=0.35)
        line_glow.set_opacity(0.25)

        self.play(FadeIn(line_glow, scale=0.3), run_time=0.25)

        # ── Stage 4: Accent dot emerges ──
        accent_dot = Dot(
            accent_line.get_center(),
            color=THEME["accent_color"],
            radius=0.08,
        )
        self.play_emerge(accent_dot, run_time=0.35, scale_from=2.0, rotation=TAU / 8)

        # ── Stage 5: Hook appears with GLOW IN ──
        hook = self.get_styled_text(assets.get("hook", ""), is_main=False)
        if hook.width > manim_config.frame_width * 0.75:
            hook.scale_to_fit_width(manim_config.frame_width * 0.75)
        hook.next_to(accent_line, DOWN, buff=0.45)

        self.play_glow_in(hook, run_time=0.6, glow_color=THEME["secondary_color"])

        # ── Stage 6: Final soft ring polish (no aggressive pulse) ──
        group = VGroup(title, accent_line, line_glow, accent_dot, hook)

        polish_ring = Circle(
            radius=2.8,
            color=THEME["secondary_color"],
            stroke_width=1,
            fill_opacity=0,
        )
        polish_ring.move_to(group.get_center())
        polish_ring.set_opacity(0.15)
        self.add(polish_ring)

        self.play(
            polish_ring.animate.scale(1.4).set_opacity(0),
            rate_func=rate_functions.ease_out_cubic,
            run_time=0.5,
        )

        # Fill remaining intro time
        remaining_intro = (
            self._intro_start_time + VIDEO_CONFIG["intro_duration"]
        ) - self.renderer.time
        if remaining_intro > 0:
            self.wait(remaining_intro)

        # ── Exit: dissolve with particles ──
        self.play(
            FadeOut(group, shift=UP * 0.15),
            *[
                p.animate.move_to(
                    np.array(
                        [
                            np.random.uniform(-10, 10),
                            np.random.uniform(-14, 14),
                            0,
                        ]
                    )
                ).set_opacity(0)
                for p in particles
            ],
            FadeOut(polish_ring),
            run_time=0.4,
        )

        return group

    # ══════════════════════════════════════════════
    #  SECTION TRANSITIONS — unique animations
    # ══════════════════════════════════════════════

    def _play_premium_section_transition(
        self, old_visual, new_visual, section, section_index, used_transitions
    ):
        """
        Dispatches to a unique premium transition style per section.
        Each style has strong ease-out deceleration and a distinct visual character.
        No two consecutive sections get the same transition.
        """
        accent_color = section.get("accent_color") or THEME["secondary_color"]

        # Map transition styles that work well with section content
        transition_styles = [0, 1, 2, 3, 4]  # spiral, radial, particle, fold, glow_sweep

        # Filter out recently used styles
        choices = [s for s in transition_styles if s not in used_transitions]
        if not choices:
            choices = transition_styles
            used_transitions.clear()

        # Pick a style that complements the section index
        chosen = random.choice(choices)
        used_transitions.add(chosen)

        # Longer run_time for first section, standard for rest
        rt = 1.4 if section_index == 0 else 1.2

        self.play_premium_transition(
            old_visual,
            new_visual,
            style=chosen,
            run_time=rt,
            accent_color=accent_color,
        )

    # ══════════════════════════════════════════════
    #  SECTION VISUALS — content-aware design
    # ══════════════════════════════════════════════

    def _create_section_visual(self, section):
        """Build a visual representation for the section's content."""
        visual_type = section.get("visual", "concept")
        accent_color = section.get("accent_color") or THEME["secondary_color"]
        bullets = section.get("bullets", [])[:3]
        keywords = section.get("keywords", [])[:3]

        elements = VGroup()

        if visual_type in ("stat", "comparison") and keywords:
            # Premium stat display: large keyword with a decorative underline
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
            # Timeline-style: connected dots with labels
            for i, bullet in enumerate(bullets[:3]):
                dot = Dot(radius=0.08, color=accent_color)
                line = self.get_styled_text(bullet, is_main=False)
                if line.width > manim_config.frame_width * 0.6:
                    line.scale_to_fit_width(manim_config.frame_width * 0.6)
                row = VGroup(dot, line).arrange(RIGHT, buff=0.3, aligned_edge=UP)
                elements.add(row)
        else:
            # Keyword chips with a more premium look
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

    # ══════════════════════════════════════════════
    #  GENERATIVE SECTION ANIMATION — unique per section ══════════════════════════════════════════════

    def _animate_section_visual_generative(self, visual, section, used_animations):
        """
        Animates the section visual using a generative animation style
        that is unique per section (no two sections use the same style).
        """
        if not visual or not visual.submobjects:
            return

        duration = section.get("padded_duration", 6.0)
        max_anim_time = min(duration * 0.7, 3.0)
        if max_anim_time <= 0:
            return

        # Pick a unique animation style not yet used
        available = [
            "scan_reveal",
            "emerge",
            "ripple_reveal",
            "staggered_assemble",
            "draw_reveal",
            "glow_in",
            "spiral_reveal",
            "morph_reveal",
        ]

        # Filter out already-used styles
        choices = [s for s in available if s not in used_animations]
        if not choices:
            # If all styles used, reset and allow repeats
            choices = available
            used_animations.clear()

        chosen = random.choice(choices)
        used_animations.add(chosen)

        anim_time = min(max_anim_time, len(visual.submobjects) * 0.25 + 0.5)

        if chosen == "scan_reveal":
            direction = random.choice([UP, DOWN])
            self.play_scan_reveal(visual, direction=direction, run_time=anim_time)
        elif chosen == "emerge":
            self.play_emerge(visual, run_time=anim_time)
        elif chosen == "ripple_reveal":
            self.play_ripple_reveal(visual, run_time=anim_time, n_rings=3)
        elif chosen == "staggered_assemble":
            self.play_staggered_assemble(visual, run_time=anim_time, lag_ratio=0.12)
        elif chosen == "draw_reveal":
            self.play_draw_reveal(
                visual, run_time=anim_time, stroke_color=THEME["accent_color"]
            )
        elif chosen == "glow_in":
            self.play_glow_in(visual, run_time=anim_time)
        elif chosen == "spiral_reveal":
            self.play_spiral_reveal(visual, run_time=anim_time)
        elif chosen == "morph_reveal":
            self.play_morph_reveal(
                visual, run_time=anim_time, morph_color=THEME["secondary_color"]
            )

    # ══════════════════════════════════════════════
    #  OUTRO TRANSITION — graceful emergence
    # ══════════════════════════════════════════════

    def _play_outro_transition(self, old_visual, outro_text):
        """Premium outro with a spiral reveal and particle send-off."""

        # Decorative particles burst outward
        particles = VGroup(
            *[
                Dot(
                    point=old_visual.get_center() + np.random.uniform(-0.3, 0.3, 3),
                    radius=np.random.uniform(0.02, 0.05),
                    color=THEME["accent_color"],
                    fill_opacity=0.6,
                )
                for _ in range(10)
            ]
        )
        self.add(particles)

        # Transform old content away while particles burst
        self.play(
            FadeOut(old_visual, scale=0.8),
            *[
                p.animate.move_to(
                    p.get_center() + np.random.uniform(-2, 2, 3)
                ).set_opacity(0)
                for p in particles
            ],
            run_time=0.5,
        )

        self.remove(particles)

        # Outro text emerges with a spiral reveal
        outro_text.move_to(ORIGIN)
        self.play_spiral_reveal(outro_text, run_time=1.0)

        # Surrounding ring draws
        ring = Circle(
            color=THEME["accent_color"],
            stroke_width=3,
            fill_opacity=0,
        )
        ring.surround(outro_text, buffer_factor=1.15)
        ring.set_opacity(0)

        self.play(
            Create(ring),
            run_time=0.5,
        )

        # Gentle glow pulse
        glow = Dot(
            outro_text.get_center(),
            color=THEME["accent_color"],
            radius=0.3,
            fill_opacity=0.15,
        )
        self.add(glow)

        self.play(
            glow.animate.scale(4).set_opacity(0),
            run_time=0.8,
        )

        self.remove(glow)
