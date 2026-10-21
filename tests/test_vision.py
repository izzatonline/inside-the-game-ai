import pytest

pytest.importorskip("cv2")
from itg.vision.pipeline import homography, to_pitch, to_app_frames  # noqa: E402


def test_homography_roundtrip():
    pairs = [((100, 100), (0, 0)), ((900, 120), (100, 0)), ((950, 600), (100, 100)), ((60, 580), (0, 100))]
    h = homography(pairs)
    for px, pt in pairs:
        x, y = to_pitch(h, *px)
        assert abs(x - pt[0]) < 0.5 and abs(y - pt[1]) < 0.5


def test_app_frames_orders_goalkeeper_first():
    tracks = {str(i): {"team": 0 if i < 12 else 1, "frames": 10} for i in range(1, 23)}
    frames = [{"t": 0.0, "players": [[i, 5 + i * 3.0, 50.0] for i in range(1, 23)], "ball": None}]
    out = to_app_frames({"tracks": tracks, "frames": frames})
    assert len(out[0]["pos"]) == 22
    assert out[0]["pos"][0][0] < out[0]["pos"][10][0]
