# render.py
import argparse
import sys
import os
import subprocess
from pathlib import Path
from manim import tempconfig, Scene, config
from .utils import load_script, validate_script
from .engine.video_engine import VideoOrchestrator
from .scenes.template_scenes import IntroScene, DynamicContentScene, OutroScene

class ProductionManager:
    def __init__(self, script_path, quality="h"):
        self.script_path = script_path
        self.quality = quality
        self.orchestrator = VideoOrchestrator()
        self.script = load_script(script_path)
        validate_script(self.script)

    def run(self):
        # Use subprocess to run Manim CLI
        # This is more robust for path handling
        cmd = [
            "manim",
            f"-q{self.quality}",
            "src/auto_video/scenes/main_scene.py",
            "ProductionScene"
        ]
        
        print(f"Running Manim: {' '.join(cmd)}")
        subprocess.run(cmd, env={**os.environ, "AUTO_VIDEO_SCRIPT": str(self.script_path)}, check=True)
        
        # 3. Finalize
        # Find the rendered video
        # Manim quality codes: l->480p15, m->720p30, h->1080p60, p->1440p60, k->2160p60
        res_map = {"l": "480p15", "m": "720p30", "h": "1080p60", "p": "1440p60", "k": "2160p60"}
        res_folder = res_map.get(self.quality, "1080p60")
        
        # Manim might use the larger dimension for the folder name if it's vertical
        # From earlier find: media/videos/1920p60/...
        # So for 'h' (1080x1920), it uses 1920p60.
        video_path = Path("media/videos/main_scene/1920p60/ProductionScene.mp4")
        if not video_path.exists():
            # Fallback search
            found = list(Path("media/videos").glob("**/ProductionScene.mp4"))
            if found:
                video_path = found[0]
            else:
                raise FileNotFoundError("Manim failed to produce ProductionScene.mp4")
        assets, project_dir = self.orchestrator.process_script(self.script)
        audio_paths = [a["audio"] for a in assets]
        
        temp_audio = project_dir / "full_audio.wav"
        final_output = project_dir / f"{video_path.stem}_final.mp4"
        
        print("Finalizing audio/video merge...")
        self.orchestrator.concatenate_audio(audio_paths, temp_audio)
        self.orchestrator.finalize_video(video_path, temp_audio, final_output)
        
        print(f"\nSUCCESS! Video ready at: {final_output}")

def main():
    parser = argparse.ArgumentParser(description="Production Manim Pipeline")
    parser.add_argument("script", help="Path to JSON/YAML script")
    parser.add_argument("--quality", default="h", help="Manim quality (l, m, h, p, k)")
    args = parser.parse_args()

    manager = ProductionManager(args.script, args.quality)
    manager.run()

if __name__ == "__main__":
    main()
