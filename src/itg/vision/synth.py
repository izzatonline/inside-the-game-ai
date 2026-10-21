"""Render a fixed wide-camera video of a *synthetic* match from the generator's tracking frames.

Gives the vision pipeline footage with known ground truth: python -m itg.vision.synth out.mp4 --seed 3 --start 560 --seconds 12
Writes out.mp4, out.truth.json (true positions per video frame, 0-100 pitch frame) and out.calib.json (pixel<->pitch points).
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
from typing import Dict, List, Tuple

import cv2
import numpy as np

from ..generator import generate_match

L, Wd = 105.0, 68.0  # metres
W, H = 3200, 1000
CY = H / 2 - 215  # principal-point row: keeps the pitch centred and trims dead sky
CAM = np.array([52.5, -6.0, 30.0])
TARGET = np.array([52.5, 36.0, 0.0])
FOCAL = 633.0
KITS = {0: ((40, 40, 200), (30, 30, 150)), 1: ((235, 235, 235), (200, 200, 200))}  # BGR shirt, shorts; team 1 white
KEEPERS = ((40, 200, 240), (40, 40, 40))


def _camera():
    f = (TARGET - CAM) / np.linalg.norm(TARGET - CAM)
    r = np.cross(f, [0, 0, 1.0]); r /= np.linalg.norm(r)
    d = np.cross(f, r)
    R = np.stack([r, d, f])
    return R, -R @ CAM


_R, _T = _camera()
_K = np.array([[FOCAL, 0, W / 2], [0, FOCAL, CY], [0, 0, 1.0]])


def project(pts: np.ndarray) -> np.ndarray:
    """World metres (N,3) -> pixels (N,2)."""
    c = pts @ _R.T + _T
    return (c[:, :2] / c[:, 2:3]) * FOCAL + np.array([W / 2, CY])


def pitch_to_world(x: float, y: float, z: float = 0.0) -> np.ndarray:
    return np.array([x * L / 100, y * Wd / 100, z])


def _background() -> np.ndarray:
    img = np.zeros((H, W, 3), np.uint8)
    img[:] = (35, 28, 22)  # dark stands
    # grass: mowing stripes in world space
    ys, xs = np.mgrid[0:H, 0:W]
    # back-project each pixel to the ground plane z=0
    dirs = np.stack([(xs - W / 2) / FOCAL, (ys - CY) / FOCAL, np.ones_like(xs, dtype=float)], -1) @ _R  # cam->world
    with np.errstate(divide="ignore", invalid="ignore"):
        s = -CAM[2] / dirs[..., 2]
    gx, gy = CAM[0] + s * dirs[..., 0], CAM[1] + s * dirs[..., 1]
    ok = (s > 0) & (gx > -6) & (gx < L + 6) & (gy > -5) & (gy < Wd + 5)
    stripe = ((np.floor(np.nan_to_num(gx) / 7.0).astype(int) % 2) == 0)
    grass = np.where(stripe[..., None], np.array([50, 130, 60]), np.array([45, 118, 55])).astype(np.uint8)
    img[ok] = grass[ok]
    lines = [np.array([[0, 0], [L, 0], [L, Wd], [0, Wd], [0, 0]]), np.array([[L / 2, 0], [L / 2, Wd]])]
    for sx in (0, 1):  # boxes
        x0 = 0 if sx == 0 else L
        d = 1 if sx == 0 else -1
        lines.append(np.array([[x0, 13.84], [x0 + d * 16.5, 13.84], [x0 + d * 16.5, 54.16], [x0, 54.16]]))
        lines.append(np.array([[x0, 24.84], [x0 + d * 5.5, 24.84], [x0 + d * 5.5, 43.16], [x0, 43.16]]))
    ang = np.linspace(0, 2 * math.pi, 60)
    lines.append(np.stack([L / 2 + 9.15 * np.cos(ang), Wd / 2 + 9.15 * np.sin(ang)], 1))
    for ln in lines:
        pix = project(np.c_[ln, np.zeros(len(ln))]).astype(np.int32)
        cv2.polylines(img, [pix], False, (235, 235, 235), 3, cv2.LINE_AA)
    return img


def _figure(img, x_m, y_m, kit, phase, keeper):
    foot = project(np.array([[x_m, y_m, 0.0]]))[0]
    head = project(np.array([[x_m, y_m, 1.8]]))[0]
    hip = project(np.array([[x_m, y_m, 0.95]]))[0]
    sh = project(np.array([[x_m, y_m, 1.5]]))[0]
    hgt = foot[1] - head[1]
    if hgt < 4:
        return
    shirt, shorts = KEEPERS if keeper else kit
    wid = max(2.0, hgt * 0.26)
    cv2.ellipse(img, (int(foot[0]), int(foot[1])), (int(wid * 1.1) + 1, int(wid * 0.35) + 1), 0, 0, 360, (30, 80, 40), -1, cv2.LINE_AA)
    swing = math.sin(phase) * hgt * 0.10
    for sgn in (-1, 1):  # legs
        cv2.line(img, (int(hip[0] + sgn * wid * 0.25), int(hip[1])), (int(foot[0] + sgn * swing + sgn * wid * 0.2), int(foot[1])),
                 (150, 190, 225) if sgn else (140, 180, 215), max(1, int(wid * 0.3)), cv2.LINE_AA)
    cv2.rectangle(img, (int(hip[0] - wid * 0.5), int(hip[1] - hgt * 0.06)), (int(hip[0] + wid * 0.5), int(hip[1] + hgt * 0.14)), shorts, -1)
    cv2.rectangle(img, (int(sh[0] - wid * 0.55), int(sh[1])), (int(sh[0] + wid * 0.55), int(hip[1])), shirt, -1)
    cv2.circle(img, (int(head[0]), int(head[1] + hgt * 0.06)), max(2, int(hgt * 0.07)), (150, 190, 225), -1, cv2.LINE_AA)


def render(out: str, seed: int = 3, start: float = 560.0, seconds: float = 12.0, fps: int = 25) -> None:
    frames = [e for e in generate_match(seed) if e.type == "tracking" and start - 10 <= e.t <= start + seconds + 12]
    t_k = np.array([e.t for e in frames])
    pos_k = np.array([e.meta["pos"] for e in frames], float)  # (K,22,2)
    ball_k = np.array([e.meta["ball"] for e in frames], float)
    # ball positions are in the possessing team's frame in the generator; use players-only truth + ball approximated
    poss = [e.meta["poss"] for e in frames]
    codes = sorted(set(poss))
    first = list(generate_match(seed, duration=60.0))[0].team
    bg = _background()
    vw = cv2.VideoWriter(out, cv2.VideoWriter_fourcc(*"mp4v"), fps, (W, H))
    truth: List[Dict] = []
    for n in range(int(seconds * fps)):
        t = start + n / fps
        pos = np.stack([np.interp(t, t_k, pos_k[:, i, k]) for i in range(22) for k in (0, 1)]).reshape(22, 2)
        ball = np.array([np.interp(t, t_k, ball_k[:, k]) for k in (0, 1)])
        img = bg.copy()
        order = sorted(range(22), key=lambda i: pos[i, 1])  # far players first
        for i in order:
            x_m, y_m = pos[i, 0] * L / 100, pos[i, 1] * Wd / 100
            _figure(img, x_m, y_m, KITS[0 if i < 11 else 1], t * 6.0 + i, i in (0, 11))
        bp = project(np.array([[ball[0] * L / 100, ball[1] * Wd / 100, 0.11]]))[0]
        cv2.circle(img, (int(bp[0]), int(bp[1])), 4, (250, 250, 250), -1, cv2.LINE_AA)
        img = cv2.GaussianBlur(img, (3, 3), 0.8)
        img = np.clip(img.astype(np.int16) + np.random.default_rng(n).normal(0, 3, img.shape), 0, 255).astype(np.uint8)
        vw.write(img)
        truth.append({"t": round(n / fps, 3), "pos": np.round(pos, 2).tolist(), "ball": np.round(ball, 2).tolist()})
    vw.release()
    pts = [(0, 0), (100, 0), (100, 100), (0, 100), (50, 0), (50, 100), (16.5 / 1.05, 20.3), (100 - 16.5 / 1.05, 79.7)]
    cal = {"points": [{"px": project(pitch_to_world(*p)[None])[0].round(1).tolist(), "pitch": list(p)} for p in pts]}
    base = pathlib.Path(out).with_suffix("")
    pathlib.Path(str(base) + ".truth.json").write_text(json.dumps({"fps": fps, "frames": truth}))
    pathlib.Path(str(base) + ".calib.json").write_text(json.dumps(cal))
    print(f"wrote {out} ({seconds}s, {W}x{H})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("out"); ap.add_argument("--seed", type=int, default=3)
    ap.add_argument("--start", type=float, default=560.0); ap.add_argument("--seconds", type=float, default=12.0)
    a = ap.parse_args()
    render(a.out, a.seed, a.start, a.seconds)
