# src/scenes/base_scene.py
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
        max_chars = 22 if is_main else 32

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
            line_spacing=1.4,
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

    def play_captions(self, timing_data, section_start_time=None, offset=None):
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

        chunk_lead = 0.25
        highlight_lead = 0.25

        for chunk in chunks:
            word_mobs = VGroup(
                *[
                    Text(
                        w["text"].strip().upper(),
                        font=THEME["font"],
                        font_size=30,
                        color=WHITE,
                        weight=BOLD,
                    )
                    for w in chunk
                ]
            )

            word_mobs.arrange(RIGHT, buff=0.15)
            if word_mobs.width > self.camera.frame_width * 0.85:
                word_mobs.scale_to_fit_width(self.camera.frame_width * 0.85)

            shadow = (
                word_mobs.copy()
                .set_color(BLACK)
                .shift(0.05 * DOWN + 0.05 * RIGHT)
                .set_opacity(0.5)
            )
            for m in word_mobs:
                m.set_stroke(BLACK, width=8, background=True)

            caption_group = VGroup(shadow, word_mobs)
            caption_group.to_edge(DOWN, buff=1.5)

            first_word_start = (
                section_start_time + offset + chunk[0]["start"] - chunk_lead
            )
            wait_time = first_word_start - self.renderer.time
            if wait_time > 0:
                self.wait(wait_time)

            self.add(caption_group)

            for i, word_data in enumerate(chunk):
                word_start = (
                    section_start_time + offset + word_data["start"] - highlight_lead
                )
                word_end = (
                    section_start_time + offset + word_data["end"] - highlight_lead
                )

                wait_start = word_start - self.renderer.time
                if wait_start > 0:
                    self.wait(wait_start)

                word_mobs[i].set_fill(THEME["secondary_color"])

                wait_end = word_end - self.renderer.time
                if wait_end > 0:
                    self.wait(wait_end)

                word_mobs[i].set_fill(WHITE)

            self.remove(caption_group)
