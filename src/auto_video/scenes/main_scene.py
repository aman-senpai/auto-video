import json
import os

from manim import config as manim_config

from auto_video.config import VIDEO_CONFIG
from auto_video.scenes.base_scene import BaseProductionScene
from auto_video.scenes.template_scenes import DynamicContentScene, IntroScene, OutroScene

manim_config.pixel_height = VIDEO_CONFIG["pixel_height"]
manim_config.pixel_width = VIDEO_CONFIG["pixel_width"]
manim_config.frame_height = VIDEO_CONFIG["frame_height"]
manim_config.frame_width = VIDEO_CONFIG["frame_width"]
manim_config.frame_rate = VIDEO_CONFIG["frame_rate"]
manim_config.background_color = VIDEO_CONFIG["background_color"]


class ProductionScene(BaseProductionScene):
    def construct(self):
        with open(self.get_assets_path(), "r", encoding="utf-8") as handle:
            assets = json.load(handle)

        intro = IntroScene(assets.get("title", "AI Video Automation"), assets.get("hook", ""))
        intro.play_on(self)

        for section in assets["sections"]:
            DynamicContentScene(section).play_on(self)

        outro = OutroScene(assets.get("outro", "Follow for more!"))
        outro.play_on(self)

    def get_assets_path(self):
        return os.environ["AUTO_VIDEO_ASSETS"]
