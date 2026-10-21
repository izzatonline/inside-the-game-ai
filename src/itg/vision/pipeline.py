"""Fixed-camera football video -> player/ball tracks in pitch coordinates (0-100 x 0-100, same frame as the app).

Steps: YOLO detects people + ball, ByteTrack keeps IDs, a homography from 4+ clicked pitch points maps each
player's feet to the pitch, jersey colours are clustered into two teams.
"""
from __future__ import annotations

import json
import pathlib
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

Point = Tuple[float, float]


def homography(pairs: Sequence[Tuple[Point, Point]]) -> np.ndarray:
    """3x3 matrix mapping image pixels -> pitch coordinates from >=4 (pixel, pitch) pairs."""
    import cv2

    if len(pairs) < 4:
        raise ValueError("need at least 4 calibration points")
    src = np.array([p for p, _ in pairs], dtype=np.float32)
    dst = np.array([q for _, q in pairs], dtype=np.float32)
    h, _ = cv2.findHomography(src, dst, cv2.RANSAC if len(pairs) > 4 else 0, 3.0)
    if h is None:
        raise ValueError("calibration points are degenerate (collinear?)")
    return h


def to_pitch(h: np.ndarray, px: float, py: float) -> Point:
    v = h @ np.array([px, py, 1.0])
    return float(v[0] / v[2]), float(v[1] / v[2])


def load_calibration(path: str) -> np.ndarray:
    """JSON: {"points": [{"px": [x, y], "pitch": [X, Y]}, ...]} with pitch coords 0-100 (team A attacks +X)."""
    d = json.loads(pathlib.Path(path).read_text())
    return homography([(tuple(p["px"]), tuple(p["pitch"])) for p in d["points"]])


def grab_frame(video: str, out_png: str, at_s: float = 5.0) -> None:
    """Save one frame so the pitch points can be picked on it."""
    import cv2

    cap = cv2.VideoCapture(video)
    cap.set(cv2.CAP_PROP_POS_MSEC, at_s * 1000)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        raise RuntimeError(f"cannot read {video}")
    cv2.imwrite(out_png, frame)
    print(f"saved {out_png} ({frame.shape[1]}x{frame.shape[0]})")


def _jersey_feature(frame: np.ndarray, box) -> Optional[np.ndarray]:
    """Mean Lab colour of the torso (upper-middle of the box); ignores grass-green pixels."""
    import cv2

    x1, y1, x2, y2 = [int(v) for v in box]
    h, w = y2 - y1, x2 - x1
    if h < 12 or w < 6:
        return None
    crop = frame[y1 + int(0.2 * h): y1 + int(0.55 * h), x1 + int(0.25 * w): x1 + int(0.75 * w)]
    if crop.size == 0:
        return None
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    grass = (hsv[..., 0] > 35) & (hsv[..., 0] < 90) & (hsv[..., 1] > 60)
    keep = ~grass
    if keep.sum() < 8:
        return None
    lab = cv2.cvtColor(crop, cv2.COLOR_BGR2LAB)[keep]
    return lab.mean(axis=0)


class PitchTracker:
    """Nearest-neighbour association in pitch metres. Boxes of far-away players are only a few pixels wide, so IoU
    trackers (ByteTrack) lose them between frames; distance on the ground plane does not care about box size."""

    def __init__(self, max_speed: float = 9.0, max_miss: int = 10):
        self.tracks: Dict[int, Dict[str, Any]] = {}
        self.next_id = 1
        self.max_speed, self.max_miss = max_speed, max_miss

    def update(self, t: float, dets: List[Point]) -> List[int]:
        from scipy.optimize import linear_sum_assignment

        scale = np.array([1.05, 0.68])
        alive = [i for i, v in self.tracks.items() if v["miss"] <= self.max_miss]
        ids = [-1] * len(dets)
        if alive and dets:
            tp = np.array([self.tracks[i]["pos"] for i in alive]) * scale
            dp = np.array(dets) * scale
            d = np.linalg.norm(tp[:, None] - dp[None], axis=2)
            for a, i in enumerate(alive):
                gate = max(2.0, self.max_speed * (t - self.tracks[i]["t"]))
                d[a, d[a] > gate] = 1e6
            for a, k in zip(*linear_sum_assignment(d)):
                if d[a, k] < 1e6:
                    ids[k] = alive[a]
        for k, i in enumerate(ids):
            if i < 0:
                i = ids[k] = self.next_id
                self.next_id += 1
                self.tracks[i] = {"pos": dets[k], "t": t, "miss": 0}
            self.tracks[i].update(pos=dets[k], t=t, miss=0)
        for i in alive:
            if i not in ids:
                self.tracks[i]["miss"] += 1
        return ids


def track_video(video: str, calibration: str, out_json: str, model: str = "yolov8s.pt", fps: float = 5.0,
                conf: float = 0.25, imgsz: int = 1280, preview: Optional[str] = None, margin: float = 4.0,
                max_seconds: Optional[float] = None, tracker: Optional[str] = None) -> Dict[str, Any]:
    """Run detection + tracking; writes JSON {fps, tracks:{id:{team,...}}, frames:[{t, players:[[id,x,y]], ball}]}."""
    import cv2
    from sklearn.cluster import KMeans
    from ultralytics import YOLO

    h = load_calibration(calibration)
    hinv = np.linalg.inv(h)
    cap = cv2.VideoCapture(video)
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    stride = max(1, round(src_fps / fps))
    yolo = YOLO(model)
    frames: List[Dict[str, Any]] = []
    feats: Dict[int, List[np.ndarray]] = {}
    writer = None
    n = 0
    pt = PitchTracker()
    for r in yolo.predict(source=video, stream=True, classes=[0, 32], conf=conf, imgsz=imgsz, vid_stride=stride, verbose=False):
        t = n * stride / src_fps
        n += 1
        if max_seconds and t > max_seconds:
            break
        img = r.orig_img
        ball, ball_conf, dets, boxes_ = None, 0.0, [], []
        boxes = r.boxes
        for k in range(len(boxes)):
            cls, c = int(boxes.cls[k]), float(boxes.conf[k])
            x1, y1, x2, y2 = boxes.xyxy[k].tolist()
            if cls == 32:
                if c > ball_conf:
                    X, Y = to_pitch(h, (x1 + x2) / 2, (y1 + y2) / 2)
                    ball, ball_conf = [round(X, 1), round(Y, 1)], c
                continue
            X, Y = to_pitch(h, (x1 + x2) / 2, y2)  # feet
            if not (-margin <= X <= 100 + margin and -margin <= Y <= 100 + margin):
                continue  # spectators, bench, coaches
            dets.append((X, Y))
            boxes_.append((x1, y1, x2, y2))
        players = []
        for tid, (X, Y), bb in zip(pt.update(t, dets), dets, boxes_):
            f = _jersey_feature(img, bb)
            if f is not None:
                feats.setdefault(tid, []).append(f)
            players.append([tid, round(X, 1), round(Y, 1)])
        frames.append({"t": round(t, 2), "players": players, "ball": ball})
        if preview:
            if writer is None:
                H, W = img.shape[:2]
                writer = cv2.VideoWriter(preview, cv2.VideoWriter_fourcc(*"mp4v"), fps, (W, H))
            vis = img.copy()
            for tid, X, Y in players:
                p = hinv @ np.array([X, Y, 1.0])
                cv2.circle(vis, (int(p[0] / p[2]), int(p[1] / p[2])), 5, (0, 255, 255), -1)
                cv2.putText(vis, str(tid), (int(p[0] / p[2]) + 6, int(p[1] / p[2])), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            writer.write(vis)
        if n % 50 == 0:
            print(f"  {n} frames ({t:.0f}s of ~{total / src_fps:.0f}s)")
    if writer:
        writer.release()

    ids = [i for i, v in feats.items() if len(v) >= 5]
    tracks: Dict[str, Dict[str, Any]] = {}
    if len(ids) >= 4:
        med = np.array([np.median(feats[i], axis=0) for i in ids])
        lab = KMeans(n_clusters=2, n_init=10, random_state=0).fit_predict(med)
        for i, g in zip(ids, lab):
            tracks[str(i)] = {"team": int(g), "frames": len(feats[i])}
    out = {"video": pathlib.Path(video).name, "fps": fps, "tracks": tracks, "frames": frames}
    pathlib.Path(out_json).write_text(json.dumps(out))
    print(f"wrote {out_json}: {len(frames)} frames, {len(tracks)} teamed tracks")
    return out


def to_app_frames(data: Dict[str, Any], team0_attacks_right: bool = True) -> List[Dict[str, Any]]:
    """Reduce raw tracks to the app's 22-slot frames: per team the 11 longest-lived tracks, ordered goalkeeper-first
    by depth (median position along the attacking axis), missing samples held from the last sighting."""
    tracks = data["tracks"]
    by_team: Dict[int, List[str]] = {0: [], 1: []}
    for tid, v in sorted(tracks.items(), key=lambda kv: -kv[1]["frames"]):
        if len(by_team[v["team"]]) < 11:
            by_team[v["team"]].append(tid)
    seen: Dict[str, List[Point]] = {}
    for f in data["frames"]:
        for tid, x, y in f["players"]:
            seen.setdefault(str(tid), []).append((x, y))
    flip = not team0_attacks_right

    def depth(tid: str, team: int) -> float:
        x = float(np.median([p[0] for p in seen.get(tid, [(50, 50)])]))
        return x if (team == 0) != flip else 100 - x

    order = {t: sorted(ids, key=lambda i: depth(i, t)) for t, ids in by_team.items()}
    last: Dict[str, Point] = {}
    out = []
    for f in data["frames"]:
        cur = {str(i): (x, y) for i, x, y in f["players"]}
        last.update(cur)
        pos = []
        for t in (0, 1):
            for tid in order[t]:
                x, y = last.get(tid, (50.0, 50.0))
                pos.append([round(x if not flip else 100 - x, 1), round(y if not flip else 100 - y, 1)])
            pos.extend([[50.0, 50.0]] * (11 - len(order[t])))
        out.append({"t": f["t"], "pos": pos, "ball": f["ball"]})
    return out
