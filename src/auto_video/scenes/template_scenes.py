import numpy as np
from manim import *

from auto_video.config import THEME, VIDEO_CONFIG
from auto_video.scenes.base_scene import BaseProductionScene

VISUAL_ICON_MAP = {
    "timeline": "\u2192",
    "comparison": "\u2260",
    "process": "\u2699",
    "stat": "\u25b2",
    "concept": "\u25c6",
}


class IntroScene(BaseProductionScene):
    """
    A rich, multi-faceted intro that uses varied "generation" animations
    instead of repetitive zoom/scale effects. Each stage feels unique.
    """

    def __init__(self, title, hook, **kwargs):
        self.title_text = title
        self.hook_text = hook
        super().__init__(**kwargs)

    def play_on(self, scene):
        # ── Stage 1: Ambient particle field with a slow spiral-in ──
        particles = scene.get_particle_field(count=30, color=THEME["secondary_color"])
        for p in particles:
            # Scatter particles off-screen initially
            p.move_to(
                np.array(
                    [
                        np.random.uniform(-8, 8),
                        np.random.uniform(-14, 14),
                        0,
                    ]
                )
            )
            p.set_opacity(0)

        scene.add(particles)
        # Particles drift into view — like stars appearing
        scene.play(
            *[
                p.animate.move_to(
                    np.array(
                        [
                            np.random.uniform(-5, 5),
                            np.random.uniform(-7, 7),
                            0,
                        ]
                    )
                ).set_opacity(np.random.uniform(0.1, 0.35))
                for p in particles
            ],
            rate_func=rate_functions.ease_out_cubic,
            run_time=0.8,
        )

        # ── Stage 2: Title appears with a SCAN REVEAL (generation effect) ──
        title = scene.get_styled_text(self.title_text)
        if title.width > scene.camera.frame_width * 0.85:
            title.scale_to_fit_width(scene.camera.frame_width * 0.85)
        title.move_to(ORIGIN + UP * 0.4)

        # Use scan reveal for the title — looks like it's being read into existence
        scene.play_scan_reveal(
            title, direction=UP, run_time=1.0, scanner_color=THEME["secondary_color"]
        )

        scene.wait(0.1)

        # ── Stage 3: Accent line draws itself from left to right ──
        accent_line = Line(
            LEFT * title.width * 0.45,
            RIGHT * title.width * 0.45,
            color=THEME["secondary_color"],
            stroke_width=5,
        )
        accent_line.next_to(title, DOWN, buff=0.35)

        scene.play(
            Create(accent_line),
            rate_func=rate_functions.ease_out_cubic,
            run_time=0.4,
        )

        # ── Stage 3b: Glowing aura expands behind the accent line (ripple-like) ──
        line_glow = Line(
            LEFT * title.width * 0.45,
            RIGHT * title.width * 0.45,
            color=THEME["secondary_color"],
            stroke_width=16,
        )
        line_glow.next_to(title, DOWN, buff=0.35)
        line_glow.set_opacity(0.3)

        scene.play(
            FadeIn(line_glow, scale=0.3),
            run_time=0.3,
        )

        # ── Stage 4: Accent dot drops in with a bounce (emerge effect) ──
        accent_dot = Dot(
            accent_line.get_center(),
            color=THEME["accent_color"],
            radius=0.08,
        )
        scene.play_emerge(accent_dot, run_time=0.4, scale_from=2.0, rotation=TAU / 6)

        # ── Stage 5: Hook appears with a ripple reveal (generation effect) ──
        hook = scene.get_styled_text(self.hook_text, is_main=False)
        if hook.width > scene.camera.frame_width * 0.75:
            hook.scale_to_fit_width(scene.camera.frame_width * 0.75)
        hook.next_to(accent_line, DOWN, buff=0.45)

        scene.play_ripple_reveal(hook, run_time=0.8, n_rings=2)

        # ── Stage 6: Final gentle polish — a soft glow pulse (no aggressive zoom) ──
        content_group = VGroup(title, accent_line, line_glow, accent_dot, hook)
        bg_ring = Circle(
            radius=3.0,
            color=THEME["secondary_color"],
            stroke_width=1,
            fill_opacity=0,
        )
        bg_ring.move_to(content_group.get_center())
        bg_ring.set_opacity(0.2)
        scene.add(bg_ring)

        scene.play(
            bg_ring.animate.scale(1.3).set_opacity(0),
            rate_func=rate_functions.ease_out_cubic,
            run_time=0.6,
        )

        scene.wait(0.3)

        # ── Stage 7: Clean exit with particle scatter ──
        scene.play(
            FadeOut(content_group, shift=UP * 0.2),
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
            FadeOut(bg_ring),
            run_time=0.6,
        )


class DynamicContentScene(BaseProductionScene):
    """
    Content scene that uses varied generative animations per section.
    Each bullet/kewyord gets its own unique "emergence" style,
    so no two sections look the same.
    """

    def __init__(self, section, **kwargs):
        self.section = section
        self.full_text = section["text"]
        self.words_timing = section.get("timing", [])
        self.bullets = section.get("bullets", [])[:3]
        self.keywords = section.get("keywords", [])[:3]
        self.visual = section.get("visual", "concept")
        self.accent_color = section.get("accent_color") or THEME["secondary_color"]
        super().__init__(**kwargs)

    def play_on(self, scene):
        # ── 1. Icon with a morph-reveal (circle morphs into icon) ──
        icon = Text(
            VISUAL_ICON_MAP.get(self.visual, "\u25c6"),
            font=THEME["font"],
            font_size=64,
            color=self.accent_color,
        )
        icon_bg = Circle(
            radius=0.6, color=self.accent_color, stroke_width=2, fill_opacity=0.1
        ).move_to(icon)
        icon_group = VGroup(icon_bg, icon)

        scene.play_morph_reveal(icon_group, run_time=0.6, morph_color=self.accent_color)

        # ── 2. Headline with a glow-in appearance ──
        headline = scene.get_styled_text(self.section["headline"]).scale(1.05)
        if headline.width > scene.camera.frame_width * 0.85:
            headline.scale_to_fit_width(scene.camera.frame_width * 0.85)

        header = VGroup(icon_group, headline).arrange(DOWN, buff=0.4)
        if header.width > scene.camera.frame_width * 0.9:
            header.scale_to_fit_width(scene.camera.frame_width * 0.9)
        header.to_edge(UP, buff=1.0)

        scene.play_glow_in(headline, run_time=0.5, glow_color=self.accent_color)

        # ── 3. Bullets with staggered ASSEMBLE (each bullet gets a unique animation) ──
        bullets_group = self._build_bullets(scene, header)

        if len(bullets_group) > 0:
            scene.play_staggered_assemble(
                bullets_group,
                run_time=min(len(bullets_group.submobjects) * 0.3, 1.2),
                lag_ratio=0.2,
            )

            # ── 3b. Add subtle ambient animation to bullets during captions ──
            stop_ambient = scene.add_ambient_animation(bullets_group)

            # ── 4. Captions with word-by-word reveal ──
            caption_words = self._build_caption(scene)
            self._play_captions(scene, caption_words)

            # Stop the ambient float when section ends
            stop_ambient()

        else:
            caption_words = self._build_caption(scene)
            self._play_captions(scene, caption_words)

        # ── 5. Exit with a soft dissolve ──
        scene.play(
            FadeOut(header, shift=UP * 0.15),
            FadeOut(bullets_group, shift=DOWN * 0.1),
            run_time=0.4,
        )

    def _build_bullets(self, scene, header):
        group = VGroup()
        texts = self.bullets or [self.full_text]
        for index, bullet in enumerate(texts[:3]):
            marker = Dot(radius=0.1, color=self.accent_color)
            line = scene.get_styled_text(bullet, is_main=False)
            if line.width > scene.camera.frame_width * 0.7:
                line.scale_to_fit_width(scene.camera.frame_width * 0.7)
            row = VGroup(marker, line).arrange(RIGHT, buff=0.3, aligned_edge=UP)
            group.add(row)

        group.arrange(DOWN, buff=0.8, aligned_edge=LEFT)
        if group.width > scene.camera.frame_width * 0.85:
            group.scale_to_fit_width(scene.camera.frame_width * 0.85)
        if group.height > scene.camera.frame_height * 0.5:
            group.scale_to_fit_height(scene.camera.frame_height * 0.5)
        group.move_to(ORIGIN)
        return group

    def _build_caption(self, scene):
        chunk_size = 1  # Word-by-word for better sync
        chunks = [
            self.words_timing[i : i + chunk_size]
            for i in range(0, len(self.words_timing), chunk_size)
        ]
        caption_words = []
        for chunk in chunks:
            caption_text = " ".join(word["text"] for word in chunk).strip().upper()
            if not caption_text:
                continue
            mob = Text(
                caption_text, font=THEME["font"], font_size=48, color=WHITE, weight=BOLD
            )
            if mob.width > scene.camera.frame_width * 0.85:
                mob.scale_to_fit_width(scene.camera.frame_width * 0.85)

            # Premium shadow effect
            shadow = (
                mob.copy()
                .set_color(BLACK)
                .shift(0.05 * DOWN + 0.05 * RIGHT)
                .set_opacity(0.5)
            )
            mob.set_stroke(BLACK, width=8, background=True)
            caption_group = VGroup(shadow, mob)
            caption_group.to_edge(DOWN, buff=1.5)
            caption_words.append((chunk, caption_group))

        return caption_words

    def _play_captions(self, scene, caption_words):
        scene_start_time = scene.renderer.time
        offset = VIDEO_CONFIG["section_preroll"]
        lead_time = 0.15

        for chunk, word_mob in caption_words:
            start_time = scene_start_time + offset + chunk[0]["start"] - lead_time
            end_time = scene_start_time + offset + chunk[-1]["end"] - lead_time

            wait_time = start_time - scene.renderer.time
            if wait_time > 0:
                scene.wait(wait_time)

            scene.add(word_mob)
            scene.wait(max(end_time - scene.renderer.time, 0.05))
            scene.remove(word_mob)


class OutroScene(BaseProductionScene):
    """
    Premium outro with generative exit effects.
    CTA emerges with style, then dissolves gracefully.
    """

    def __init__(self, cta="Follow for more!", **kwargs):
        self.cta = cta
        super().__init__(**kwargs)

    def play_on(self, scene):
        # ── 1. Ambient particles fade in as backdrop ──
        particles = scene.get_particle_field(count=15, color=THEME["secondary_color"])
        for p in particles:
            p.set_opacity(0)
        scene.add(particles)

        scene.play(
            *[p.animate.set_opacity(np.random.uniform(0.1, 0.3)) for p in particles],
            run_time=0.4,
        )

        # ── 2. CTA text emerges with a spiral reveal ──
        cta_text = scene.get_styled_text(self.cta)
        if cta_text.width > scene.camera.frame_width * 0.75:
            cta_text.scale_to_fit_width(scene.camera.frame_width * 0.75)

        scene.play_spiral_reveal(cta_text, run_time=1.2)

        # ── 3. Contour ring draws around the CTA ──
        ring = Circle(color=THEME["accent_color"], stroke_width=4)
        ring.surround(cta_text, buffer_factor=1.1)

        scene.play(
            Create(ring),
            rate_func=rate_functions.ease_out_cubic,
            run_time=0.5,
        )

        # ── 4. Gentle pulse ripple from the ring ──
        ripple = Circle(color=THEME["accent_color"], stroke_width=2, fill_opacity=0)
        ripple.surround(cta_text, buffer_factor=1.1)
        ripple.set_opacity(0.4)
        scene.add(ripple)

        scene.play(
            ripple.animate.scale(1.5).set_opacity(0),
            rate_func=rate_functions.ease_out_cubic,
            run_time=0.8,
        )

        scene.wait(0.8)

        # ── 5. Graceful exit with particle scatter ──
        scene.play(
            FadeOut(VGroup(cta_text, ring), shift=DOWN * 0.2),
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
            run_time=0.6,
        )
