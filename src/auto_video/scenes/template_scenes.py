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
    def __init__(self, title, hook, **kwargs):
        self.title_text = title
        self.hook_text = hook
        super().__init__(**kwargs)

    def play_on(self, scene):
        # --- 1. Background ambience ---
        particles = scene.get_particle_field(count=20, color=THEME["secondary_color"])
        for p in particles:
            p.set_opacity(0)
        scene.add(particles)
        scene.play(
            *[p.animate.set_opacity(np.random.uniform(0.15, 0.4)) for p in particles],
            run_time=0.6,
        )

        bg_glow = Circle(
            radius=3.5,
            color=THEME["secondary_color"],
            stroke_width=0,
            fill_opacity=0.04,
        )
        scene.play(FadeIn(bg_glow, scale=2.0), run_time=0.5)

        # --- 2. Word-by-word title reveal ---
        title = scene.get_styled_text(self.title_text)
        if title.width > scene.camera.frame_width * 0.85:
            title.scale_to_fit_width(scene.camera.frame_width * 0.85)
        title.move_to(ORIGIN)
        title.save_state()
        title.scale(0.5).set_opacity(0)

        scene.play(
            title.animate.restore(),
            rate_func=rate_functions.ease_out_bounce,
            run_time=1.2,
        )
        scene.wait(0.15)

        # --- 3. Dynamic underline that grows from center ---
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

        scene.play(
            accent_line.animate.restore(),
            FadeIn(line_glow, scale=0),
            run_time=0.5,
        )

        # --- 4. Stylish dot accent at center of line ---
        accent_dot = Dot(
            accent_line.get_center(),
            color=THEME["accent_color"],
            radius=0.08,
        )
        scene.play(
            FadeIn(accent_dot, scale=3.0),
            run_time=0.3,
        )

        # --- 5. Subtitle fades in with smooth reveal ---
        hook = scene.get_styled_text(self.hook_text, is_main=False)
        if hook.width > scene.camera.frame_width * 0.75:
            hook.scale_to_fit_width(scene.camera.frame_width * 0.75)
        hook.next_to(accent_line, DOWN, buff=0.45)
        hook.set_opacity(0)

        scene.play(
            hook.animate.set_opacity(1),
            run_time=0.6,
        )

        # --- 6. Final polished pulse ---
        content_group = VGroup(title, accent_line, line_glow, accent_dot, hook, bg_glow)
        scene.play(
            content_group.animate.scale(1.04),
            rate_func=there_and_back,
            run_time=0.6,
        )

        scene.wait(0.6)

        # --- 7. Clean exit ---
        scene.play(
            FadeOut(content_group, shift=UP * 0.3),
            FadeOut(particles),
            run_time=0.5,
        )


class DynamicContentScene(BaseProductionScene):
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

        headline = scene.get_styled_text(self.section["headline"]).scale(1.05)
        if headline.width > scene.camera.frame_width * 0.85:
            headline.scale_to_fit_width(scene.camera.frame_width * 0.85)

        header = VGroup(icon_group, headline).arrange(DOWN, buff=0.4)
        if header.width > scene.camera.frame_width * 0.9:
            header.scale_to_fit_width(scene.camera.frame_width * 0.9)
        header.to_edge(UP, buff=1.0)

        bullets_group = self._build_bullets(scene, header)
        caption_words = self._build_caption(scene)

        # Animations (Total time must be < VIDEO_CONFIG["section_preroll"])
        scene.play(
            FadeIn(icon_group, scale=1.2, shift=UP * 0.5), Write(headline), run_time=0.5
        )

        if len(bullets_group) > 0:
            scene.play(
                LaggedStart(
                    *[FadeIn(mob, shift=UP * 0.25) for mob in bullets_group],
                    lag_ratio=0.2,
                ),
                run_time=min(len(bullets_group) * 0.2, 0.6),
            )

        self._play_captions(scene, caption_words)
        scene.play(FadeOut(VGroup(header, bullets_group)), run_time=0.4)

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
        lead_time = 0.15  # Stronger lead for aggressive sync

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
    def __init__(self, cta="Follow for more!", **kwargs):
        self.cta = cta
        super().__init__(**kwargs)

    def play_on(self, scene):
        cta_text = scene.get_styled_text(self.cta)
        if cta_text.width > scene.camera.frame_width * 0.75:
            cta_text.scale_to_fit_width(scene.camera.frame_width * 0.75)

        ring = Circle(color=THEME["accent_color"], stroke_width=4)
        ring.surround(cta_text, buffer_factor=1.1)

        group = VGroup(cta_text, ring)
        if group.width > scene.camera.frame_width * 0.85:
            group.scale_to_fit_width(scene.camera.frame_width * 0.85)

        scene.play(FadeIn(cta_text, scale=0.95), Create(ring), run_time=0.7)
        scene.play(
            ring.animate.scale(1.05).set_stroke(THEME["secondary_color"], 5),
            rate_func=there_and_back,
            run_time=0.8,
        )
        scene.wait(1.5)
        scene.play(FadeOut(VGroup(cta_text, ring)), run_time=0.5)
