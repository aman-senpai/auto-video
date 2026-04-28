# auto-video: auto_video/scenes/base_scene.py
import numpy as np
from manim import *

from auto_video.config import THEME, VIDEO_CONFIG


class BaseProductionScene(Scene):
    def construct(self):
        # Set background
        self.camera.background_color = VIDEO_CONFIG["background_color"]

    def get_styled_text(self, text, is_main=True):
        size = THEME["font_size_main"] if is_main else THEME["font_size_sub"]
        weight = BOLD if is_main else NORMAL
        color = THEME["primary_color"]

        # Manual wrapping for vertical video
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
            font=THEME["font"],
            font_size=size,
            weight=weight,
            color=color,
            line_spacing=1.6,
            t2c={
                word: THEME["secondary_color"]
                for word in [
                    "Manim",
                    "Apple",
                    "Silicon",
                    "TikTok",
                    "Reels",
                    "Future",
                    "Digital",
                    "Global",
                    "Japanese",
                    "Animation",
                    "Anime",
                ]
            },
        ).set_max_width(self.camera.frame_width * THEME["text_width"])

    def start_captions(self, timing_data, section_start_time=None, offset=None):
        if offset is None:
            offset = VIDEO_CONFIG["section_preroll"]
        if section_start_time is None:
            section_start_time = self.renderer.time

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
            word_mobs = VGroup(
                *[
                    Text(
                        w["text"].strip().upper().replace(",", "").replace(".", ""),
                        font=THEME["font"],
                        font_size=30,
                        color=WHITE,
                        weight=BOLD,
                    )
                    for w in chunk
                ]
            ).arrange(RIGHT, buff=0.15)

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

    def play_ai_reveal(self, mobject, run_time=1.5):
        """Plays a complex 'AI-style' reveal animation."""
        mobject.set_opacity(0)

        # Grid/Scanner effect
        scanner = Line(
            LEFT * 4, RIGHT * 4, color=THEME["secondary_color"], stroke_width=2
        )
        scanner.set_opacity(0)
        scanner.move_to(mobject.get_top())

        self.play(
            scanner.animate.set_opacity(1).move_to(mobject.get_bottom()),
            UpdateFromAlphaFunc(mobject, lambda m, a: m.set_opacity(a)),
            rate_func=linear,
            run_time=run_time,
        )
        self.play(FadeOut(scanner), run_time=0.3)
