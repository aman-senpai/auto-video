# src/scenes/template_scenes.py
from manim import *
from auto_video.scenes.base_scene import BaseProductionScene
from auto_video.config import THEME

class IntroScene(BaseProductionScene):
    def __init__(self, title, **kwargs):
        self.title_text = title
        super().__init__(**kwargs)

    def play_on(self, scene):
        title = scene.get_styled_text(self.title_text)
        underline = Line(LEFT, RIGHT, color=THEME["secondary_color"]).scale(2).next_to(title, DOWN)
        
        scene.play(Write(title))
        scene.play(Create(underline))
        scene.wait(1)
        scene.play(FadeOut(title), FadeOut(underline))

class DynamicContentScene(BaseProductionScene):
    def __init__(self, text, words_timing, **kwargs):
        self.full_text = text
        self.words_timing = words_timing
        super().__init__(**kwargs)

    def play_on(self, scene):
        # Word-by-word highlight animation
        # Display base text
        main_text = scene.get_styled_text(self.full_text).shift(UP * 2)
        scene.add(main_text)
        
        # Captions at center
        caption_box = Rectangle(
            height=2, width=8, fill_color=BLACK, fill_opacity=0.5, stroke_width=0
        ).shift(DOWN * 3)
        scene.add(caption_box)

        # Sync loop
        for word_data in self.words_timing:
            word_str = word_data["text"]
            start = word_data["start"]
            end = word_data["end"]
            
            # Create word mobject
            word_mob = Text(word_str, font=THEME["font"], font_size=72, color=THEME["secondary_color"])
            word_mob.move_to(caption_box.get_center())
            
            # Wait until start
            current_time = scene.renderer.time
            wait_time = start - current_time
            if wait_time > 0:
                scene.wait(wait_time)
            
            scene.add(word_mob)
            scene.wait(end - start)
            scene.remove(word_mob)
        
        scene.remove(main_text, caption_box)

class OutroScene(BaseProductionScene):
    def __init__(self, cta="Follow for more!", **kwargs):
        self.cta = cta
        super().__init__(**kwargs)

    def play_on(self, scene):
        cta_text = scene.get_styled_text(self.cta)
        glow = cta_text.copy().set_stroke(THEME["accent_color"], 10).set_opacity(0.3)
        
        scene.play(FadeIn(cta_text, scale=1.5), FadeIn(glow))
        scene.play(glow.animate.set_stroke(opacity=0.8).scale(1.1), rate_func=there_and_back, run_time=2)
        scene.wait(2)
        scene.play(FadeOut(cta_text), FadeOut(glow))
