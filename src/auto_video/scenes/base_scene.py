import os
import random
import re

import numpy as np
from manim import *

from auto_video.config import SUPPORTED_LANGUAGES, THEME, VIDEO_CONFIG, resolve_font


class BaseProductionScene(Scene):
    def construct(self):
        # Set background
        self.camera.background_color = VIDEO_CONFIG["background_color"]

    # ──────────────────────────────────────────────
    #  STYLED TEXT
    # ──────────────────────────────────────────────

    def _get_active_font(self) -> str:
        """Return the best font for the current language (from env var)."""
        lang = os.environ.get("AUTO_VIDEO_LANGUAGE", "en")
        return resolve_font(lang)

    def get_styled_text(self, text, is_main=True):
        size = THEME["font_size_main"] if is_main else THEME["font_size_sub"]
        weight = BOLD if is_main else NORMAL
        color = THEME["primary_color"]
        active_font = self._get_active_font()

        # Detect CJK text (Chinese, Japanese, Korean)
        has_cjk = bool(
            re.search(r"[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af]", text)
        )

        if has_cjk:
            # For CJK: use character-level wrapping with different max chars
            max_chars = 14 if is_main else 20
            lines = []
            # Group characters, but keep Western words together
            current_line = []
            char_count = 0
            for char in text:
                if char == "\n":
                    lines.append("".join(current_line))
                    current_line = []
                    char_count = 0
                    continue
                # Count CJK chars as 2, others as 1 for better wrapping
                char_width = 2 if ord(char) >= 0x2000 else 1
                if char_count + char_width > max_chars:
                    lines.append("".join(current_line))
                    current_line = [char]
                    char_count = char_width
                else:
                    current_line.append(char)
                    char_count += char_width
            if current_line:
                lines.append("".join(current_line))
            wrapped_text = "\n".join(lines)
        else:
            # Original word-level wrapping for non-CJK
            words = text.split(" ")
            lines = []
            current_line = []
            max_chars = 18 if is_main else 26

            for word in words:
                if (
                    sum(len(w) for w in current_line) + len(word) + len(current_line)
                    > max_chars
                ):
                    lines.append(" ".join(current_line))
                    current_line = [word]
                else:
                    current_line.append(word)
            lines.append(" ".join(current_line))
            wrapped_text = "\n".join(lines)

        return Text(
            wrapped_text,
            font=active_font,
            font_size=size,
            weight=weight,
            color=color,
            line_spacing=1.6,
        ).set_max_width(self.camera.frame_width * THEME["text_width"])

    # ──────────────────────────────────────────────
    #  CAPTIONS SYSTEM
    # ──────────────────────────────────────────────

    def start_captions(self, timing_data, section_start_time=None, offset=None):
        if offset is None:
            offset = VIDEO_CONFIG["section_preroll"]
        if section_start_time is None:
            section_start_time = self.renderer.time

        active_font = self._get_active_font()

        # Detect if this is a non-Latin script (CJK, Devanagari, etc.) to skip .upper()
        has_non_latin = any(
            ord(w["text"][0]) > 0x2000 for w in timing_data if w["text"].strip()
        )

        valid_timing = [w for w in timing_data if w["text"].strip()]
        chunk_size = 3
        chunks = [
            valid_timing[i : i + chunk_size]
            for i in range(0, len(valid_timing), chunk_size)
        ]

        highlight_lead = 0.1
        container = VGroup()
        self.add(container)

        all_items = []
        for chunk in chunks:
            caption_words = []
            for w in chunk:
                caption_word = w["text"].strip()
                # Only uppercase for Latin scripts
                if not has_non_latin:
                    caption_word = caption_word.upper()
                caption_word = (
                    caption_word.replace(",", "").replace(".", "").replace("।", "")
                )
                tw = Text(
                    caption_word,
                    font=active_font,
                    font_size=30,
                    color=WHITE,
                    weight=BOLD,
                )
                caption_words.append(tw)
            word_mobs = VGroup(*caption_words).arrange(RIGHT, buff=0.15)

            for m in word_mobs:
                m.set_stroke(BLACK, width=8, background=True)

            if word_mobs.width > self.camera.frame_width * 0.85:
                word_mobs.scale_to_fit_width(self.camera.frame_width * 0.85)

            shadow = word_mobs.copy().set_color(BLACK).shift(0.05 * DOWN + 0.05 * RIGHT)
            for m in shadow:
                m.set_stroke(BLACK, width=8, background=True)

            caption_group = VGroup(shadow, word_mobs).to_edge(DOWN, buff=0.8)
            caption_group.set_z_index(100)  # Force to top layer
            for m in word_mobs:
                m.set_opacity(0)
            for s in shadow:
                s.set_opacity(0)
            container.add(caption_group)

            all_items.append(
                {
                    "group": caption_group,
                    "mobs": word_mobs,
                    "shadow": shadow,
                    "chunk": chunk,
                    "start": section_start_time + offset + chunk[0]["start"] - 0.25,
                    "end": section_start_time + offset + chunk[-1]["end"],
                }
            )

        def caption_updater(mob, dt):
            now = self.renderer.time
            # Find strictly the single active item
            active_item = None
            for item in all_items:
                if item["start"] <= now <= item["end"]:
                    active_item = item
                    break

            for item in all_items:
                if item == active_item:
                    for m in item["mobs"]:
                        m.set_opacity(1)
                    for s in item["shadow"]:
                        s.set_opacity(0.5)
                else:
                    for m in item["mobs"]:
                        m.set_opacity(0)
                    for s in item["shadow"]:
                        s.set_opacity(0)

            if active_item:
                # Highlight active word
                for i, w_data in enumerate(active_item["chunk"]):
                    w_s = section_start_time + offset + w_data["start"] - highlight_lead
                    w_e = section_start_time + offset + w_data["end"] - highlight_lead
                    color = THEME["secondary_color"] if w_s <= now <= w_e else WHITE
                    active_item["mobs"][i].set_color(color)
                    active_item["mobs"][i].set_stroke(BLACK, width=8, background=True)

        container.add_updater(caption_updater)
        return container

    def clear_captions(self, container):
        """Stops and removes the caption container."""
        if container:
            container.clear_updaters()
            self.remove(container)

    # ──────────────────────────────────────────────
    #  AMBIENT PARTICLES
    # ──────────────────────────────────────────────

    def get_particle_field(self, count=15, color=THEME["secondary_color"]):
        """Creates a simple static particle field."""
        return VGroup(
            *[
                Dot(
                    point=[np.random.uniform(-4, 4), np.random.uniform(-8, 8), 0],
                    radius=np.random.uniform(0.01, 0.03),
                    fill_opacity=np.random.uniform(0.2, 0.4),
                    color=color,
                )
                for _ in range(count)
            ]
        )

    def get_glowing_path(self, path, color=THEME["accent_color"]):
        """Creates a high-end glowing path effect."""
        glow = path.copy().set_stroke(color, width=12, opacity=0.2)
        core = path.copy().set_stroke(WHITE, width=2, opacity=0.8)
        return VGroup(glow, core)

    # ══════════════════════════════════════════════
    #  🏆 PREMIUM GENERATIVE ANIMATION PRIMITIVES
    #  Each method creates a unique "emergence" or
    #  "generation" effect — the element looks like
    #  it is being CREATED in real-time.
    # ══════════════════════════════════════════════

    # ─────────── 1. SCAN REVEAL ───────────────

    def play_scan_reveal(
        self,
        mobject,
        direction=UP,
        run_time=2.0,
        scanner_color=THEME["secondary_color"],
    ):
        """
        A glowing scanner beam sweeps across the mobject,
        revealing it progressively as if being scanned into existence.
        """
        mobject.set_opacity(0)
        mobject.save_state()

        # Build a scanner line perpendicular to scan direction
        if abs(direction[1]) > abs(direction[0]):  # Vertical direction
            scanner = Line(
                LEFT * mobject.width * 0.6,
                RIGHT * mobject.width * 0.6,
                color=scanner_color,
                stroke_width=3,
            )
            scanner_glow = Line(
                LEFT * mobject.width * 0.6,
                RIGHT * mobject.width * 0.6,
                color=scanner_color,
                stroke_width=12,
            )
            scanner_glow.set_opacity(0.15)
            start_pos = (
                mobject.get_bottom()
                if np.array_equal(direction, UP)
                else mobject.get_top()
            )
            end_pos = (
                mobject.get_top()
                if np.array_equal(direction, UP)
                else mobject.get_bottom()
            )
        else:
            scanner = Line(
                DOWN * mobject.height * 0.5,
                UP * mobject.height * 0.5,
                color=scanner_color,
                stroke_width=3,
            )
            scanner_glow = Line(
                DOWN * mobject.height * 0.5,
                UP * mobject.height * 0.5,
                color=scanner_color,
                stroke_width=12,
            )
            scanner_glow.set_opacity(0.15)
            start_pos = (
                mobject.get_left()
                if np.array_equal(direction, RIGHT)
                else mobject.get_right()
            )
            end_pos = (
                mobject.get_right()
                if np.array_equal(direction, RIGHT)
                else mobject.get_left()
            )

        scanner.move_to(start_pos)
        scanner_glow.move_to(start_pos)

        scanner_group = VGroup(scanner_glow, scanner)

        # Reveal using a custom updater that slices opacity based on scanner position
        def make_reveal_updater(scanner_line, scan_dir):
            def updater(m, dt):
                s_pos = scanner_line.get_center()
                m_center = mobject.get_center()

                if abs(scan_dir[1]) > abs(scan_dir[0]):  # Vertical direction
                    progress = (s_pos[1] - start_pos[1]) / (
                        end_pos[1] - start_pos[1] + 0.001
                    )
                else:
                    progress = (s_pos[0] - start_pos[0]) / (
                        end_pos[0] - start_pos[0] + 0.001
                    )

                progress = np.clip(progress, 0, 1)
                # Restore saved state first, then apply opacity and scale
                mobject.restore()
                mobject.set_opacity(progress)
                mobject.scale(0.9 + progress * 0.1)

            return updater

        reveal_updater = make_reveal_updater(scanner, direction)
        mobject.add_updater(reveal_updater)

        self.add(scanner_group, mobject)

        self.play(
            scanner.animate.move_to(end_pos),
            scanner_glow.animate.move_to(end_pos),
            rate_func=rate_functions.ease_out_cubic,
            run_time=run_time,
        )

        mobject.clear_updaters()
        mobject.set_opacity(1)
        mobject.restore()

        self.play(
            FadeOut(scanner_group, scale=0.5),
            run_time=0.2,
        )

    # ─────────── 2. EMERGE ───────────────

    def play_emerge(self, mobject, run_time=1.5, scale_from=0.3, rotation=TAU / 12):
        """
        Elements burst forth from the center of the mobject,
        rotating and scaling up as if materialising from a point.
        """
        mobject.save_state()
        mobject.scale(scale_from).set_opacity(0).rotate(rotation)

        self.play(
            mobject.animate.restore(),
            rate_func=rate_functions.ease_out_back,
            run_time=run_time,
        )

    # ─────────── 3. RIPPLE REVEAL ───────────────

    def play_ripple_reveal(self, mobject, run_time=1.5, n_rings=3):
        """
        Concentric ripple rings expand outward from the center
        while the mobject fades in — like a pebble dropped in water.
        """
        mobject.set_opacity(0)

        rings = VGroup()
        for i in range(n_rings):
            r = Circle(
                radius=0.3,
                color=THEME["secondary_color"],
                stroke_width=3 - i,
                fill_opacity=0,
            )
            r.move_to(mobject.get_center())
            rings.add(r)

        self.add(rings)

        # Animate rings expanding while mobject fades in
        anims = [
            r.animate.scale(8 - i * 2).set_stroke(opacity=0)
            for i, r in enumerate(rings)
        ]

        self.play(
            *anims,
            mobject.animate.set_opacity(1).scale(
                0.95, about_point=mobject.get_center()
            ),
            rate_func=rate_functions.ease_out_cubic,
            run_time=run_time,
        )

        self.play(
            mobject.animate.scale(1.05, about_point=mobject.get_center()),
            rate_func=there_and_back,
            run_time=run_time * 0.3,
        )

        self.remove(rings)

    # ─────────── 4. DRAW REVEAL ───────────────

    def play_draw_reveal(
        self, mobject, run_time=2.0, stroke_color=THEME["accent_color"]
    ):
        """
        Draws the mobject's outline first (like a sketch),
        then fills it in. Works best on VectorizedMobject/VMobject subclasses.
        """
        mobject.set_fill(opacity=0)
        mobject.set_stroke(color=stroke_color, width=4, opacity=1)

        self.play(
            Create(mobject),
            rate_func=rate_functions.ease_out_cubic,
            run_time=run_time * 0.6,
        )

        self.play(
            mobject.animate.set_fill(opacity=1).set_stroke(
                color=THEME["primary_color"], width=1, opacity=0.3
            ),
            rate_func=rate_functions.ease_out_sine,
            run_time=run_time * 0.4,
        )

    # ─────────── 5. STAGGERED ASSEMBLE ───────────────

    def play_staggered_assemble(self, elements, run_time=2.0, lag_ratio=0.15):
        """
        Each element in the group assembles with its own unique animation
        (randomly chosen from fade+shift, scale, spin, sweep).
        """
        if not elements or len(elements.submobjects) == 0:
            return

        mobs = elements.submobjects
        anims = []
        for mob in mobs:
            style = random.choice(["fade_shift", "scale_up", "spin_in", "sweep"])
            mob.save_state()

            if style == "fade_shift":
                mob.shift(DOWN * 0.3).set_opacity(0)
                anims.append(mob.animate.restore())
            elif style == "scale_up":
                mob.scale(0.3).set_opacity(0)
                anims.append(mob.animate.restore())
            elif style == "spin_in":
                mob.scale(0.5).rotate(TAU / 4).set_opacity(0)
                anims.append(mob.animate.restore())
            elif style == "sweep":
                mob.shift(LEFT * 0.4).set_opacity(0)
                anims.append(mob.animate.restore())

        self.play(
            LaggedStart(*anims, lag_ratio=lag_ratio),
            run_time=run_time,
        )

    # ─────────── 6. SPIRAL REVEAL ───────────────

    def play_spiral_reveal(self, mobject, run_time=2.0):
        """
        The mobject is revealed as if drawn by a spiral path —
        pieces of it materialise along an Archimedean spiral trajectory.
        """
        mobject.set_opacity(0)

        # Create a spiral path
        center = mobject.get_center()
        spiral = ParametricFunction(
            lambda t: (
                center
                + np.array(
                    [
                        t * np.cos(t * TAU * 1.5) * mobject.width * 0.3,
                        t * np.sin(t * TAU * 1.5) * mobject.height * 0.3,
                        0,
                    ]
                )
            ),
            t_range=[0, 1],
            color=THEME["secondary_color"],
            stroke_width=2,
        )
        spiral.set_opacity(0.3)

        # Create a little glowing orb that travels the spiral
        orb = Dot(color=THEME["secondary_color"], radius=0.04)
        orb.move_to(spiral.get_start())

        self.add(spiral, orb)

        self.play(
            MoveAlongPath(orb, spiral),
            mobject.animate.set_opacity(1),
            rate_func=rate_functions.ease_out_cubic,
            run_time=run_time,
        )

        self.play(
            FadeOut(spiral),
            FadeOut(orb, scale=2.0),
            run_time=0.3,
        )

    # ─────────── 7. GLOW IN ───────────────

    def play_glow_in(self, mobject, run_time=1.0, glow_color=THEME["secondary_color"]):
        """
        A soft glow expands behind the mobject, then the mobject fades in
        with a subtle brightness pop — like a light turning on.
        """
        mobject.set_opacity(0)

        glow = Dot(
            mobject.get_center(),
            color=glow_color,
            radius=0.3,
            fill_opacity=0.4,
        )

        self.add(glow)

        self.play(
            glow.animate.scale(6).set_opacity(0),
            mobject.animate.set_opacity(1).scale(1.05),
            rate_func=rate_functions.ease_out_cubic,
            run_time=run_time * 0.7,
        )

        self.play(
            mobject.animate.scale(1 / 1.05),
            rate_func=rate_functions.ease_out_sine,
            run_time=run_time * 0.3,
        )

        self.remove(glow)

    # ─────────── 8. PARTICLE ASSEMBLE ───────────────

    def play_particle_assemble(
        self,
        mobject,
        run_time=2.0,
        particle_count=30,
        particle_color=THEME["secondary_color"],
    ):
        """
        Particles fly in from random off-screen positions and converge
        to form the mobject's shape — like nanotech assembly.
        """
        mobject.set_opacity(0)

        # Sample random points within the mobject's bounding box
        bb = mobject.get_bounding_box()
        points = [
            np.array(
                [
                    np.random.uniform(bb[0][0], bb[1][0]),
                    np.random.uniform(bb[0][1], bb[1][1]),
                    0,
                ]
            )
            for _ in range(particle_count)
        ]

        # Create particles at random off-screen positions
        particles = VGroup()
        for pt in points:
            # Random spawn location off-screen
            spawn = np.array(
                [
                    np.random.uniform(-12, 12),
                    np.random.uniform(-18, 18),
                    0,
                ]
            )
            dot = Dot(
                point=spawn,
                radius=np.random.uniform(0.02, 0.05),
                color=particle_color,
                fill_opacity=0.8,
            )
            particles.add(dot)

        self.add(particles)

        # Animate particles flying to their target positions
        self.play(
            *[p.animate.move_to(pt) for p, pt in zip(particles, points)],
            mobject.animate.set_opacity(1),
            rate_func=rate_functions.ease_out_quint,
            run_time=run_time,
        )

        # Fade particles out
        self.play(
            *[p.animate.set_opacity(0).scale(0.1) for p in particles],
            run_time=0.4,
        )

        self.remove(particles)

    # ─────────── 9. AI REVEAL (enhanced) ───────────────

    def play_ai_reveal(self, mobject, run_time=1.5):
        """
        Scanner-bar reveal with enhanced glow and trailing particles.
        """
        mobject.set_opacity(0)

        # Grid/Scanner effect with neon styling
        scanner = Line(
            LEFT * 4, RIGHT * 4, color=THEME["secondary_color"], stroke_width=3
        )
        scanner_glow = Line(
            LEFT * 4, RIGHT * 4, color=THEME["secondary_color"], stroke_width=14
        )
        scanner_glow.set_opacity(0.15)

        scanner_group = VGroup(scanner_glow, scanner)
        scanner_group.set_opacity(0)
        scanner_group.move_to(mobject.get_top())

        # Small trailing particles
        trail = VGroup(
            *[
                Dot(
                    color=THEME["accent_color"],
                    radius=0.02,
                ).move_to(scanner_group.get_center() + np.random.uniform(-0.3, 0.3, 3))
                for _ in range(5)
            ]
        )

        self.add(scanner_group, trail)

        self.play(
            scanner_group.animate.set_opacity(1).move_to(mobject.get_bottom()),
            trail.animate.move_to(mobject.get_bottom() + DOWN * 0.2),
            UpdateFromAlphaFunc(mobject, lambda m, a: m.set_opacity(a)),
            rate_func=rate_functions.ease_out_cubic,
            run_time=run_time,
        )

        self.play(
            FadeOut(scanner_group, scale=0.5),
            FadeOut(trail, scale=0.1),
            run_time=0.3,
        )

    # ─────────── 10. MORPH REVEAL ───────────────

    def play_morph_reveal(
        self,
        mobject,
        run_time=1.5,
        morph_color=THEME["secondary_color"],
    ):
        """
        A circle morphs into the target mobject's shape —
        like a shape-shifting emergence effect.
        """
        mobject.set_opacity(0)

        # Create a circle at the mobject's center
        morph_shape = Circle(
            radius=0.3,
            color=morph_color,
            fill_opacity=0.2,
            stroke_width=3,
        ).move_to(mobject.get_center())

        self.add(morph_shape)

        # Morph the circle into the mobject
        self.play(
            Transform(morph_shape, mobject.copy().set_fill(opacity=0.3)),
            mobject.animate.set_opacity(1),
            rate_func=rate_functions.ease_out_cubic,
            run_time=run_time,
        )

        self.remove(morph_shape)
        mobject.set_opacity(1)

    # ─────────── 11. HELPER: GENERATE TRANSITION ───────────────

    def play_generative_transition(
        self,
        old_mobject,
        new_mobject,
        run_time=1.0,
    ):
        """
        A rich scene transition that plays a subtle decorative
        animation while transforming content.
        - Old content dissolves with particles
        - New content emerges with a glow-in effect
        - Background accent elements animate throughout
        """
        # Particle burst from old content
        old_particles = VGroup(
            *[
                Dot(
                    point=old_mobject.get_center() + np.random.uniform(-0.5, 0.5, 3),
                    radius=np.random.uniform(0.02, 0.05),
                    color=THEME["secondary_color"],
                    fill_opacity=0.6,
                )
                for _ in range(8)
            ]
        )
        self.add(old_particles)

        # Subtle ring expansion during transition
        ring = Circle(
            radius=0.2,
            color=THEME["secondary_color"],
            stroke_width=2,
            fill_opacity=0,
        ).move_to(new_mobject.get_center())

        self.add(ring)

        new_mobject.set_opacity(0)

        self.play(
            ReplacementTransform(old_mobject, new_mobject),
            *[
                p.animate.move_to(
                    p.get_center() + np.random.uniform(-1.5, 1.5, 3)
                ).set_opacity(0)
                for p in old_particles
            ],
            ring.animate.scale(4).set_opacity(0),
            rate_func=rate_functions.ease_in_out_sine,
            run_time=run_time * 0.7,
        )

        # Glow-in the new content
        glow = Dot(
            new_mobject.get_center(),
            color=THEME["secondary_color"],
            radius=0.2,
            fill_opacity=0.3,
        )
        self.add(glow)

        self.play(
            glow.animate.scale(5).set_opacity(0),
            new_mobject.animate.set_opacity(1),
            rate_func=rate_functions.ease_out_sine,
            run_time=run_time * 0.3,
        )

        self.remove(glow, ring, old_particles)

    # ─────────── 12. PICK RANDOM REVEAL ───────────────

    def play_random_reveal(self, mobject, run_time=1.5):
        """
        Picks a random generative animation from the available pool
        and plays it. Used for variety between different sections.
        """
        methods = [
            self.play_scan_reveal,
            self.play_emerge,
            self.play_ripple_reveal,
            self.play_glow_in,
            self.play_spiral_reveal,
            self.play_morph_reveal,
        ]
        chosen = random.choice(methods)

        # Some methods need special handling
        if chosen == self.play_scan_reveal:
            direction = random.choice([UP, DOWN, LEFT, RIGHT])
            chosen(mobject, direction=direction, run_time=run_time)
        else:
            chosen(mobject, run_time=run_time)

    # ─────────── 13. PREMIUM TRANSITIONS ───────────────

    def play_premium_transition(
        self,
        old_mobject,
        new_mobject,
        style=None,
        run_time=1.5,
        accent_color=None,
    ):
        """
        Dispatches to one of several premium transition styles.
        If style is None, picks randomly from available styles.
        Each style has a distinct visual character and strong ease-out deceleration.
        """
        if accent_color is None:
            accent_color = THEME["secondary_color"]

        styles = [
            self._transition_spiral_wipe,
            self._transition_radial_scan,
            self._transition_particle_morph,
            self._transition_fold_unfold,
            self._transition_glow_sweep,
        ]

        if style is not None and 0 <= style < len(styles):
            chosen = styles[style]
        else:
            chosen = random.choice(styles)

        chosen(old_mobject, new_mobject, run_time=run_time, accent_color=accent_color)

    # ── A. SPIRAL WIPE ────────────────────────

    def _transition_spiral_wipe(self, old, new, run_time=1.5, accent_color=None):
        """Old spirals out & fades, new spirals in from center with glow."""
        if accent_color is None:
            accent_color = THEME["secondary_color"]

        new.set_opacity(0)
        old.save_state()

        center = old.get_center()

        # Spiral path for old content to follow outwards
        spiral_out = ParametricFunction(
            lambda t: (
                center
                + np.array(
                    [
                        t * 2.5 * np.cos(t * TAU * 2),
                        t * 2.5 * np.sin(t * TAU * 2),
                        0,
                    ]
                )
            ),
            t_range=[0, 1],
            color=accent_color,
            stroke_width=1,
        )

        # Small orb at the center that grows
        orb = Dot(center, color=accent_color, radius=0.05, fill_opacity=0.8)
        self.add(orb, spiral_out)

        self.play(
            old.animate.move_to(spiral_out.get_end())
            .scale(0.3)
            .set_opacity(0)
            .rotate(TAU * 2),
            orb.animate.scale(3).set_opacity(0),
            rate_func=rate_functions.ease_out_cubic,
            run_time=run_time * 0.4,
        )

        self.remove(old, spiral_out, orb)
        self.add(new)
        new.scale(0.3).rotate(-TAU).set_opacity(0)
        new.move_to(center)

        # Spiral in for new content
        spiral_in = ParametricFunction(
            lambda t: (
                center
                + np.array(
                    [
                        (1 - t) * 2.5 * np.cos((1 - t) * TAU * 2),
                        (1 - t) * 2.5 * np.sin((1 - t) * TAU * 2),
                        0,
                    ]
                )
            ),
            t_range=[0, 1],
            color=accent_color,
            stroke_width=2,
        )

        glow = Dot(center, color=accent_color, radius=0.2, fill_opacity=0.4)
        self.add(spiral_in, glow)

        self.play(
            new.animate.move_to(center).scale(1 / 0.3).rotate(TAU).set_opacity(1),
            glow.animate.scale(5).set_opacity(0),
            rate_func=rate_functions.ease_out_quint,
            run_time=run_time * 0.6,
        )

        self.remove(spiral_in, glow)

    # ── B. RADIAL SCAN ────────────────────────

    def _transition_radial_scan(self, old, new, run_time=1.5, accent_color=None):
        """A circular scanner grows from center, revealing new content behind it."""
        if accent_color is None:
            accent_color = THEME["secondary_color"]

        new.set_opacity(0)
        center = old.get_center()
        max_radius = max(old.width, old.height) * 0.8

        # Create a circular mask / scanner ring
        scanner_ring = Circle(
            radius=0.1,
            color=accent_color,
            stroke_width=8,
            fill_opacity=0,
        ).move_to(center)
        scanner_glow = Circle(
            radius=0.1,
            color=accent_color,
            stroke_width=20,
            fill_opacity=0,
        ).move_to(center)
        scanner_glow.set_opacity(0.12)

        self.add(scanner_ring, scanner_glow, old, new)

        self.play(
            scanner_ring.animate.scale(max_radius / 0.1).set_stroke(opacity=0),
            scanner_glow.animate.scale(max_radius / 0.1).set_opacity(0),
            old.animate.set_opacity(0),
            new.animate.set_opacity(1),
            rate_func=rate_functions.ease_out_cubic,
            run_time=run_time,
        )

        self.remove(scanner_ring, scanner_glow, old)

    # ── C. PARTICLE MORPH ─────────────────────

    def _transition_particle_morph(self, old, new, run_time=1.5, accent_color=None):
        """Old shatters into particles that converge to form new content."""
        if accent_color is None:
            accent_color = THEME["secondary_color"]

        new.set_opacity(0)
        center = old.get_center()

        particles = VGroup(
            *[
                Dot(
                    point=center + np.random.uniform(-0.4, 0.4, 3),
                    radius=np.random.uniform(0.02, 0.06),
                    color=accent_color,
                    fill_opacity=0.7,
                )
                for _ in range(20)
            ]
        )
        self.add(particles)

        # Explode old outward while spawning particles
        self.play(
            old.animate.scale(0.1).set_opacity(0).move_to(center),
            *[
                p.animate.move_to(
                    center
                    + np.array(
                        [
                            np.random.uniform(-4, 4),
                            np.random.uniform(-6, 6),
                            0,
                        ]
                    )
                ).set_opacity(0.3)
                for p in particles
            ],
            rate_func=rate_functions.ease_out_sine,
            run_time=run_time * 0.35,
        )
        self.remove(old)

        new.move_to(center)
        new_targets = [
            new.get_center() + np.random.uniform(-0.3, 0.3, 3) for _ in particles
        ]

        self.add(new)
        self.play(
            *[
                p.animate.move_to(t).set_opacity(0)
                for p, t in zip(particles, new_targets)
            ],
            new.animate.set_opacity(1),
            rate_func=rate_functions.ease_out_quint,
            run_time=run_time * 0.65,
        )
        self.remove(particles)

    # ── D. FOLD / UNFOLD ──────────────────────

    def _transition_fold_unfold(self, old, new, run_time=1.5, accent_color=None):
        """Old compresses vertically and folds away; new unfolds from a horizontal line."""
        if accent_color is None:
            accent_color = THEME["secondary_color"]

        new.set_opacity(0)
        center = old.get_center()

        # Fold line
        fold_line = Line(
            LEFT * old.width * 0.6,
            RIGHT * old.width * 0.6,
            color=accent_color,
            stroke_width=3,
        ).move_to(center)

        self.add(fold_line)

        # Old compresses to the fold line
        self.play(
            old.animate.scale(1, about_point=center)
            .scale_to_fit_height(0.05)
            .set_opacity(0),
            fold_line.animate.set_stroke(opacity=0.6),
            rate_func=rate_functions.ease_out_cubic,
            run_time=run_time * 0.4,
        )

        self.remove(old)

        # New content unfolds from the line
        new.save_state()
        new.scale_to_fit_height(0.05).set_opacity(0).move_to(center)

        self.play(
            new.animate.restore(),
            fold_line.animate.set_opacity(0),
            rate_func=rate_functions.ease_out_back,
            run_time=run_time * 0.6,
        )

        self.remove(fold_line)

    # ── E. GLOW SWEEP ─────────────────────────

    def _transition_glow_sweep(self, old, new, run_time=1.5, accent_color=None):
        """A wave of light sweeps across; old dissolves in the wave, new appears behind it."""
        if accent_color is None:
            accent_color = THEME["secondary_color"]

        new.set_opacity(0)

        # Wide glow bar that sweeps across
        sweep_bar = Rectangle(
            width=old.width * 1.5,
            height=0.3,
            fill_color=accent_color,
            fill_opacity=0.15,
            stroke_width=0,
        ).move_to(old.get_left() + LEFT * 0.5)

        sweep_glow = Rectangle(
            width=old.width * 1.5,
            height=0.6,
            fill_color=accent_color,
            fill_opacity=0.06,
            stroke_width=0,
        ).move_to(sweep_bar.get_center())

        self.add(sweep_bar, sweep_glow, old, new)

        sweep_end = old.get_right() + RIGHT * 0.5

        self.play(
            sweep_bar.animate.move_to(sweep_end),
            sweep_glow.animate.move_to(sweep_end),
            old.animate.set_opacity(0),
            new.animate.set_opacity(1),
            rate_func=rate_functions.ease_out_cubic,
            run_time=run_time,
        )

        self.remove(sweep_bar, sweep_glow, old)

    # ─────────── 14. FULL-DURATION VISUAL ANIMATION ───────────────

    def play_full_duration_animation(self, visual, total_time, accent_color=None):
        """
        Animates a visual continuously across the full remaining section time.
        - Phase 1 (first 40%): A slow emergence/breathing-in with strong ease-out
        - Phase 2 (remaining 60%): Subtle continuous gentle pulse that coasts to stillness
        Returns a stop function to clean up updaters when the section ends.
        """
        if accent_color is None:
            accent_color = THEME["secondary_color"]

        phase1_time = max(total_time * 0.4, 1.5)
        phase1_time = min(phase1_time, 3.0)

        # Phase 1: Slow, elegant ease-in with subtle scale
        visual.save_state()
        visual.scale(0.92).set_opacity(0.85)

        self.play(
            visual.animate.restore(),
            rate_func=rate_functions.ease_out_quint,
            run_time=phase1_time,
        )

        # Phase 2: Continuous gentle breathing that decelerates toward end
        original_center = visual.get_center()
        original_width = visual.width
        original_height = visual.height
        start_time = self.renderer.time
        phase2_start = start_time
        total_phase2 = max(total_time - phase1_time, 0.5)

        def breathing_updater(m, dt):
            elapsed = self.renderer.time - phase2_start
            progress = min(elapsed / total_phase2, 1.0)
            # Decay factor: animation fades toward a gentle stop
            decay = 1.0 - rate_functions.ease_out_cubic(progress) * 0.7
            t = self.renderer.time
            drift = 0.004 * decay * np.sin(t * 1.2)
            # Absolute scale: oscillate around original size, no compounding
            scale_factor = 1.0 + 0.008 * decay * np.sin(t * 0.9)
            m.move_to(original_center + UP * drift)
            # Use absolute scale: stretch/shrink relative to original, not current
            if original_width > 0 and original_height > 0:
                m.scale_to_fit_width(original_width * scale_factor)

        visual.add_updater(breathing_updater)

        def stop_animation():
            visual.clear_updaters()
            visual.restore()
            visual.move_to(original_center)

        return stop_animation

    # ─────────── 15. AMBIENT LOOP ───────────────

    def add_ambient_animation(self, mobject):
        """
        Adds a subtle floating/breathing animation to a mobject
        that plays continuously until cleared.
        Used to keep elements feeling alive during scene turns.
        """
        original_center = mobject.get_center()

        def ambient_updater(m, dt):
            t = self.renderer.time
            # Very subtle bobbing motion — feels alive
            drift = 0.006 * np.sin(t * 1.5)
            m.move_to(original_center + UP * drift)

        mobject.add_updater(ambient_updater)

        # Return a function to stop the ambient animation
        def stop_ambient():
            mobject.clear_updaters()
            mobject.move_to(original_center)

        return stop_ambient
