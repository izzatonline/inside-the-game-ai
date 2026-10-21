"""Make a short before/after clip: synthetic footage with detections on top, and a pitch minimap comparing
tracked players (filled) with ground truth (rings).

    python -m itg.vision.demo_clip videos/synth.mp4 videos/synth.tracking.json videos/synth.truth.json videos/synth.calib.json docs/video-prototype.mp4
"""
from __future__ import annotations

import json
import sys

import cv2
import numpy as np
from scipy.optimize import linear_sum_assignment

from .pipeline import load_calibration

L, W = 105.0, 68.0
COL = {0: (60, 60, 230), 1: (240, 240, 240)}  # BGR: team A red, team B white


def main(video, tracked, truth, calib, out):
    tr, gt = json.load(open(tracked)), json.load(open(truth))
    hinv = np.linalg.inv(load_calibration(calib))
    teams = {int(k): v["team"] for k, v in tr["tracks"].items()}
    # map arbitrary kit clusters to the true sides by majority over matched players
    votes = np.zeros(2)
    for fr in tr["frames"]:
        g = np.array(gt["frames"][min(len(gt["frames"]) - 1, int(round(fr["t"] * gt["fps"])))]["pos"]) * [L / 100, W / 100]
        d = np.array([[x, y] for _, x, y in fr["players"]]).reshape(-1, 2) * [L / 100, W / 100]
        if not len(d):
            continue
        c = np.linalg.norm(g[:, None] - d[None], axis=2)
        for gi, di in zip(*linear_sum_assignment(c)):
            tid = fr["players"][di][0]
            if c[gi, di] < 3 and tid in teams:
                votes[int((teams[tid] != (0 if gi < 11 else 1)))] += 1
    flip = int(votes[1] > votes[0])
    cap = cv2.VideoCapture(video)
    fps = cap.get(cv2.CAP_PROP_FPS)
    top_w, top_h, mw, mh = 1280, 400, 640, 415
    vw = cv2.VideoWriter(out, cv2.VideoWriter_fourcc(*"mp4v"), 5, (top_w, top_h + mh + 40))
    for fr in tr["frames"]:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(round(fr["t"] * fps)))
        ok, img = cap.read()
        if not ok:
            break
        sx = top_w / img.shape[1]
        top = cv2.resize(img, (top_w, int(img.shape[0] * sx)))
        gpos = gt["frames"][min(len(gt["frames"]) - 1, int(round(fr["t"] * gt["fps"])))]["pos"]
        mini = np.full((mh, mw, 3), (46, 110, 52), np.uint8)
        cv2.rectangle(mini, (0, 0), (mw - 1, mh - 1), (235, 235, 235), 2)
        cv2.line(mini, (mw // 2, 0), (mw // 2, mh), (235, 235, 235), 2)
        cv2.circle(mini, (mw // 2, mh // 2), 55, (235, 235, 235), 2)
        pt = lambda x, y: (int(x / 100 * mw), int(y / 100 * mh))  # noqa: E731
        for i, (x, y) in enumerate(gpos):
            cv2.circle(mini, pt(x, y), 9, COL[0 if i < 11 else 1], 2, cv2.LINE_AA)  # truth ring
        for tid, x, y in fr["players"]:
            c = COL[teams[tid] ^ flip] if tid in teams else (160, 160, 160)
            cv2.circle(mini, pt(x, y), 5, c, -1, cv2.LINE_AA)
            p = hinv @ np.array([x, y, 1.0])
            cv2.circle(top, (int(p[0] / p[2] * sx), int(p[1] / p[2] * sx + 0)), 6, c, 2, cv2.LINE_AA)
        canvas = np.zeros((top_h + mh + 40, top_w, 3), np.uint8)
        canvas[:top.shape[0]] = top[:top_h]
        canvas[top_h + 40: top_h + 40 + mh, (top_w - mw) // 2:(top_w - mw) // 2 + mw] = mini
        cv2.putText(canvas, "Synthetic fixed-camera footage -> detected players (top)  |  tracked = filled dot, ground truth = ring (bottom)",
                    (14, top_h + 26), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
        vw.write(canvas)
    vw.release()
    print("wrote", out)


if __name__ == "__main__":
    main(*sys.argv[1:6])
