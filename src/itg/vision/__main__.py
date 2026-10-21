"""CLI:  python -m itg.vision frame clip.mp4 frame.png
        python -m itg.vision track clip.mp4 calib.json out.json [--preview prev.mp4] [--seconds 60]"""
import argparse

from .pipeline import grab_frame, track_video

ap = argparse.ArgumentParser(prog="itg.vision")
sub = ap.add_subparsers(dest="cmd", required=True)
f = sub.add_parser("frame"); f.add_argument("video"); f.add_argument("out"); f.add_argument("--at", type=float, default=5.0)
t = sub.add_parser("track"); t.add_argument("video"); t.add_argument("calibration"); t.add_argument("out")
t.add_argument("--preview"); t.add_argument("--seconds", type=float); t.add_argument("--model", default="yolov8s.pt")
t.add_argument("--fps", type=float, default=5.0)
a = ap.parse_args()
if a.cmd == "frame":
    grab_frame(a.video, a.out, a.at)
else:
    track_video(a.video, a.calibration, a.out, model=a.model, fps=a.fps, preview=a.preview, max_seconds=a.seconds)
