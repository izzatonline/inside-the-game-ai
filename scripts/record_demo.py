"""Record the demo video: drives the running app in a headless browser and adds a synthetic voiceover.

    ./run.sh                      # server with Foundry on (warm the cache first, see DEMO_VIDEO_PLAN.md)
    python scripts/record_demo.py # writes videos/demo/demo.mp4 and demo.srt (gitignored)

Narration: ElevenLabs when ELEVEN_LABS_API_KEY (or ELEVENLABS_API_KEY) is set in the environment, else macOS `say`.
Each line is cached in videos/demo/vo/ by a hash of voice + text, so re-runs do not re-bill.
Nothing is drawn over the app: short call-outs sit in a strip below it, and the full narration goes to demo.srt
(upload it to YouTube as subtitles). If the server can read the recap aloud (Azure AI Speech), that audio is mixed in.

Requires: pip install playwright imageio-ffmpeg httpx && python -m playwright install chromium.
"""
import hashlib
import os
import pathlib
import re
import subprocess
import sys
import time

import httpx
import imageio_ffmpeg
from playwright.sync_api import sync_playwright

BASE = os.environ.get("ITG_BASE", "http://localhost:8000")
M = "/?match=riverside&seed=7"
OUT = pathlib.Path(__file__).resolve().parent.parent / "videos" / "demo"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
W, H, STRIP = 1440, 900, 64  # app viewport, plus a strip below it for call-outs
FONT = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
EL_KEY = os.environ.get("ELEVEN_LABS_API_KEY") or os.environ.get("ELEVENLABS_API_KEY")
EL_VOICE = os.environ.get("ELEVENLABS_VOICE_ID", "onwK4e9ZLuTAKqWW03F9")  # "Daniel": calm British presenter (stock voice)
extra_audio = []  # (file, start seconds, clip seconds) for sound the app itself makes, e.g. the spoken recap
GOAL_CARD = "Wolfe nets for Meridian"  # the goal shown on camera: Casper Wolfe, 36:40 (AI headline checked by eye)
GOAL_START = 36.05  # minutes: a few seconds before that goal
JUMP_TO = 66.5  # timeline jump: minute 66, just before Wolfe's second at 66:30
ES_START = 66.6  # Spanish scene: just after that goal
RECAP_CLIP_S = 5.0  # play this much of the spoken recap (it fades out), to stay under two minutes


def goto(pg, q):
    pg.goto(BASE + M + q)
    pg.wait_for_selector("canvas")


def pause(pg):
    pg.locator('button[aria-label="Pause match"]:visible').first.click()


def intro(pg, t0):
    pg.goto(BASE + "/?match=coastal&seed=7&mode=casual&start=0&speed=2")
    pg.wait_for_selector("canvas")
    pg.wait_for_timeout(9500)


def switch(pg, t0):
    pg.get_by_text("Riverside Cup Tie").first.click()  # sidebar: another synthetic match, its own clubs and colours
    pg.wait_for_timeout(5500)


def pitch(pg, t0):
    goto(pg, f"&mode=casual&start={GOAL_START}&speed=5&view=2d")  # a few seconds before the goal on camera
    pg.wait_for_timeout(9000)


def goal(pg, t0):
    pg.locator("li", has_text=GOAL_CARD).first.wait_for(timeout=30000)
    pg.wait_for_timeout(1500)
    pause(pg)
    pg.wait_for_timeout(4000)


def workflow(pg, t0):
    pg.locator("li", has_text=GOAL_CARD).locator('button[aria-label="How this was made"]').first.click()
    pg.wait_for_timeout(5000)
    pg.get_by_text("Agent workflow").scroll_into_view_if_needed()
    pg.wait_for_timeout(9000)
    pg.keyboard.press("Escape")


def timeline(pg, t0):
    pg.locator('[aria-label="Show match momentum"]:visible').first.click()
    pg.wait_for_timeout(2200)
    chart = pg.locator('[aria-label^="Match momentum by minute"]').first
    box = chart.bounding_box()
    jump = pg.get_by_role("button", name=re.compile(r"Jump to \d+")).last
    frac = JUMP_TO / 99.0
    for _ in range(4):  # click, read the minute it picked, nudge until it is the one we want
        pg.mouse.click(box["x"] + box["width"] * frac, box["y"] + box["height"] * 0.5)
        pg.wait_for_timeout(350)
        got = int(re.search(r"(\d+)", jump.inner_text()).group(1))
        if got == int(JUMP_TO):
            break
        frac += (int(JUMP_TO) - got + 0.5) / 105.0
    pg.wait_for_timeout(900)
    jump.click()
    pg.wait_for_timeout(1000)
    play = pg.locator('button[aria-label="Play match"]:visible')
    if play.count():
        play.first.click()
    pg.wait_for_timeout(10000)  # long enough to see the goal go in


def viewer(pg, t0):
    goto(pg, f"&mode=analyst&lang=es&start={ES_START}&speed=3&view=2d")  # just after a goal: its Spanish card is on top
    pg.wait_for_timeout(2500)
    pause(pg)
    pg.wait_for_timeout(3500)


def tactics(pg, t0):
    goto(pg, "&mode=analyst&lang=en&start=70&speed=3&view=2d")
    pg.wait_for_timeout(1500)
    pg.get_by_role("tab", name="Tactics").click()
    pg.wait_for_timeout(5000)


def restart_watch(pg, t0):
    pg.get_by_role("tab", name="Stats").click()
    pg.wait_for_timeout(800)
    pg.get_by_text("Restart Watch").first.scroll_into_view_if_needed()
    pg.wait_for_timeout(6500)


def players(pg, t0):
    pg.get_by_role("button", name=re.compile("Player stats and compare")).click()
    pg.wait_for_timeout(2500)
    pg.get_by_text("Distance covered").scroll_into_view_if_needed()
    pg.wait_for_timeout(4500)
    pg.keyboard.press("Escape")


def recap(pg, t0):
    goto(pg, "&mode=casual&lang=en&start=98.92&speed=6")
    pg.get_by_text("Full time").first.wait_for(timeout=60000)
    pg.wait_for_timeout(4500)
    listen = pg.get_by_role("button", name=re.compile("Listen to the recap"))
    if listen.count():
        audio = _recap_audio(listen.first.get_attribute("data-audio"))
        listen.first.click()
        if audio:
            extra_audio.append((audio, time.monotonic() - t0 + 0.6, RECAP_CLIP_S))
        pg.wait_for_timeout(int(RECAP_CLIP_S * 1000) + 600)
        pg.get_by_role("button", name=re.compile("Pause")).last.click()
    pg.wait_for_timeout(500)


def _recap_audio(path):
    """The spoken recap the app plays (headless video has no sound), fetched from the server so it can be mixed in."""
    try:
        r = httpx.get(BASE + path, timeout=30)
        if r.status_code == 200:
            f = OUT / "recap_voice.mp3"
            f.write_bytes(r.content)
            return f
    except Exception:  # noqa: BLE001
        pass
    return None


def close(pg, t0):
    pg.wait_for_timeout(2500)


# (name, action, call-out in the strip, narration)
SCENES = [
    ("intro", intro, "A synthetic match, replayed live",
     "Football stories don't end at the scoreline. Inside the Game turns synthetic match events into explainable, "
     "personalised match intelligence, live."),
    ("switch", switch, "Three synthetic matches · switch with one click",
     "Pick any of three synthetic matches, each with its own clubs, colours and storyline."),
    ("pitch", pitch, "22 players tracked every second · formations and roles read from positions",
     "Twenty-two synthetic players move every second, with real set pieces, offside and kick-offs. "
     "The app reads each team's formation and roles from the positions alone."),
    ("goal", goal, "The AI writes the words · code computes every number",
     "When a goal goes in, a model on Microsoft Foundry writes the story, and code computes every number in it."),
    ("workflow", workflow, "Agent Framework: write → fact-check → send back → air",
     "On Microsoft Agent Framework, agents write, a FactChecker checks every number and the meaning, "
     "and sends bad drafts back for a rewrite. Across two hundred live cards, none slipped through."),
    ("timeline", timeline, "Match timeline: who was on top · jump to any minute",
     "The timeline shows who was on top, minute by minute. Jump to any moment."),
    ("viewer", viewer, "Analyst mode · Spanish · your club, your player",
     "Every viewer gets their own version: casual or analyst, any club or player, and their own language. Here, in Spanish."),
    ("tactics", tactics, "Tactics agent: shape, pressing, how to respond",
     "The tactics agent explains each team's shape, and how the opponent can respond."),
    ("restart", restart_watch, "Restart Watch: timed against the 2026/27 limits",
     "Restart Watch times every throw-in, goal kick and keeper hold against the 2026/27 league limits."),
    ("players", players, "Distance, top speed and fast runs, measured from tracking",
     "Tap any player for a radar, with distance, top speed and fast runs measured from the tracking."),
    ("recap", recap, "Full-time recap, read aloud by Azure AI Speech",
     "At full time, an AI-written recap you can listen to, and a full match report."),
    ("close", close, "Inside the Game · Microsoft Foundry · Agent Framework · Azure",
     "Inside the Game. Built with Microsoft Foundry, Agent Framework and Azure."),
]


def media_seconds(path):
    out = subprocess.run([FFMPEG, "-i", str(path)], capture_output=True, text=True).stderr
    h, m, s = re.search(r"Duration: (\d+):(\d+):([\d.]+)", out).groups()
    return int(h) * 3600 + int(m) * 60 + float(s)


def voice(name, text):
    vo = OUT / "vo"
    vo.mkdir(parents=True, exist_ok=True)
    if EL_KEY:
        f = vo / (hashlib.sha1(f"{EL_VOICE}|{text}".encode()).hexdigest()[:16] + ".mp3")
        if not f.exists():
            r = httpx.post(f"https://api.elevenlabs.io/v1/text-to-speech/{EL_VOICE}", timeout=60,
                           headers={"xi-api-key": EL_KEY},
                           json={"text": text, "model_id": "eleven_multilingual_v2",
                                 "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}})
            r.raise_for_status()
            f.write_bytes(r.content)
    else:
        f = vo / f"{name}.aiff"
        subprocess.run(["say", "-v", "Samantha", "-r", "172", "-o", str(f), text], check=True)
    return f, media_seconds(f)


def srt_time(s):
    ms = int(round(s * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def esc(t):
    return t.replace("\\", "\\\\").replace(":", "\\:").replace("'", "’").replace("%", "\\%")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    lines = [voice(name, text) for name, _, _, text in SCENES]
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": W, "height": H}, record_video_dir=str(OUT / "raw"),
                            record_video_size={"width": W, "height": H})
        ctx.add_init_script("try { localStorage.setItem('itg-hint-seen', '1'); localStorage.setItem('itg-theme', 'light') } catch (e) {}")
        pg = ctx.new_page()
        t0 = time.monotonic()
        starts = []
        for (name, run, _, _), (_, dur) in zip(SCENES, lines):
            s = time.monotonic() - t0
            starts.append(s)
            run(pg, t0)
            left = s + dur + 0.7 - (time.monotonic() - t0)
            if left > 0:
                pg.wait_for_timeout(int(left * 1000))
            print(f"{name}: {s:.1f}s, voice {dur:.1f}s", flush=True)
        total = time.monotonic() - t0
        vid = pg.video.path()
        ctx.close()
        b.close()
    print("total", round(total, 1), "s")
    ends = starts[1:] + [total]
    srt = [f"{i + 1}\n{srt_time(s + 0.3)} --> {srt_time(min(s + 0.3 + d, e))}\n{text}\n"
           for i, ((_, _, _, text), (_, d), s, e) in enumerate(zip(SCENES, lines, starts, ends))]
    (OUT / "demo.srt").write_text("\n".join(srt))
    draw = ",".join(
        f"drawtext=fontfile='{FONT}':text='{esc(call)}':fontsize=26:fontcolor=white:x=(w-text_w)/2:y={H}+({STRIP}-text_h)/2:"
        f"enable='between(t,{s:.2f},{e:.2f})'" for (_, _, call, _), s, e in zip(SCENES, starts, ends))
    vf = f"[0:v]pad={W}:{H + STRIP}:0:0:color=0x140f24,{draw}[v]"
    sounds = [(f, s + 0.3, None) for (f, _), s in zip(lines, starts)] + extra_audio
    ins, filt = [], [vf]
    for i, (f, s, clip) in enumerate(sounds):
        ins += ["-i", str(f)]
        cut = f"atrim=0:{clip},afade=t=out:st={clip - 1.2}:d=1.2," if clip else ""
        filt.append(f"[{i + 1}:a]{cut}adelay={int(s * 1000)}|{int(s * 1000)}[a{i}]")
    filt.append("".join(f"[a{i}]" for i in range(len(sounds))) + f"amix=inputs={len(sounds)}:normalize=0[aout]")
    final = OUT / "demo.mp4"
    subprocess.run([FFMPEG, "-y", "-i", vid, *ins, "-filter_complex", ";".join(filt), "-map", "[v]", "-map", "[aout]",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-c:a", "aac", "-b:a", "160k", str(final)],
                   check=True, capture_output=True)
    print("wrote", final, "and", OUT / "demo.srt")


if __name__ == "__main__":
    sys.exit(main())
