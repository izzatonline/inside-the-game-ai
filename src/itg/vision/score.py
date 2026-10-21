"""Score tracked output against synthetic ground truth: python -m itg.vision.score out.json clip.truth.json"""
import json
import sys

import numpy as np
from scipy.optimize import linear_sum_assignment

L, W = 105.0, 68.0


def score(tracked: dict, truth: dict, gate_m: float = 3.0) -> dict:
    fps_t = truth["fps"]
    errs, found, total, team_ok, team_n = [], 0, 0, 0, 0
    teams = {int(k): v["team"] for k, v in tracked["tracks"].items()}
    for fr in tracked["frames"]:
        tr = truth["frames"][min(len(truth["frames"]) - 1, int(round(fr["t"] * fps_t)))]
        gt = np.array(tr["pos"]) * [L / 100, W / 100]
        det = np.array([[x, y] for _, x, y in fr["players"]]).reshape(-1, 2) * [L / 100, W / 100]
        total += len(gt)
        if not len(det):
            continue
        d = np.linalg.norm(gt[:, None] - det[None], axis=2)
        gi, di = linear_sum_assignment(d)
        for g, k in zip(gi, di):
            if d[g, k] <= gate_m:
                found += 1
                errs.append(d[g, k])
                tid = fr["players"][k][0]
                if tid in teams:
                    team_n += 1
                    team_ok += 0  # filled below via majority mapping
    # team accuracy: best of the two label permutations
    best = 0.0
    for flip in (0, 1):
        ok = n = 0
        for fr in tracked["frames"]:
            tr = truth["frames"][min(len(truth["frames"]) - 1, int(round(fr["t"] * fps_t)))]
            gt = np.array(tr["pos"]) * [L / 100, W / 100]
            det = np.array([[x, y] for _, x, y in fr["players"]]).reshape(-1, 2) * [L / 100, W / 100]
            if not len(det):
                continue
            d = np.linalg.norm(gt[:, None] - det[None], axis=2)
            for g, k in zip(*linear_sum_assignment(d)):
                tid = fr["players"][k][0]
                if d[g, k] <= gate_m and tid in teams:
                    n += 1
                    ok += (teams[tid] ^ flip) == (0 if g < 11 else 1)
        if n:
            best = max(best, ok / n)
    return {"recall": found / max(total, 1), "mean_err_m": float(np.mean(errs)) if errs else None,
            "median_err_m": float(np.median(errs)) if errs else None, "team_acc": best,
            "avg_detected": float(np.mean([len(f["players"]) for f in tracked["frames"]])),
            "unique_ids": len({p[0] for f in tracked["frames"] for p in f["players"]})}


if __name__ == "__main__":
    print(json.dumps(score(json.load(open(sys.argv[1])), json.load(open(sys.argv[2]))), indent=1))
