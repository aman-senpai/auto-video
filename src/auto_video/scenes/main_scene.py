# src/scenes/main_scene.py
from manim import *
from auto_video.scenes.template_scenes import IntroScene, DynamicContentScene, OutroScene
from auto_video.scenes.base_scene import BaseProductionScene
from auto_video.utils import load_script
from auto_video.engine.video_engine import VideoOrchestrator

class ProductionScene(BaseProductionScene):
    def construct(self):
        script_path = self.get_script_path()
        orchestrator = VideoOrchestrator()
        script = load_script(script_path)
        assets, _ = orchestrator.process_script(script)
        
        # 1. Intro
        intro = IntroScene(script.get("title", "AI Video Automation"))
        intro.play_on(self)
        
        # 2. Content Sections
        for asset in assets:
            content = DynamicContentScene(asset["text"], asset["timing"])
            content.play_on(self)
            
        # 3. Outro
        outro = OutroScene()
        outro.play_on(self)

    def get_script_path(self):
        import os
        return os.environ.get("AUTO_VIDEO_SCRIPT", "example_script.json")
