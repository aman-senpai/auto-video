# src/scenes/base_scene.py
from manim import *
from auto_video.config import VIDEO_CONFIG, THEME

class BaseProductionScene(Scene):
    def construct(self):
        # Set background
        self.camera.background_color = VIDEO_CONFIG["background_color"]
        
    def get_styled_text(self, text, is_main=True):
        size = THEME["font_size_main"] if is_main else THEME["font_size_sub"]
        color = THEME["primary_color"]
        
        return Text(
            text,
            font=THEME["font"],
            font_size=size,
            color=color,
            line_spacing=1.2,
            t2c={word: THEME["secondary_color"] for word in ["Manim", "Apple", "Silicon", "TikTok", "Reels"]}
        ).set_max_width(THEME["text_width"])
