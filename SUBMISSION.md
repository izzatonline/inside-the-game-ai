# Submission kit (not part of the app: copy into the Innovation Studio project page)

Deadline: **2026-10-27 11:59 PM PT**. Needs: pitch, public GitHub repo URL, public video URL (YouTube/Vimeo/Facebook/Youku) under **2:00**.

## Pitch (paste, edit the [brackets] once true)

**Inside the Game** turns a stream of synthetic football events into explainable, personalised match intelligence.
A seeded generator produces football-realistic passes, shots, tackles, pressure and possession events with pass-difficulty,
ball-speed and xG metadata. An interpreter folds them into live state (possession, xG, pressure share, momentum) and
detects moments: goals, big chances, momentum swings, control-vs-chaos spells, sprints, pass-quality and milestones.
A team of specialised agents on **Microsoft Agent Framework** (Explainer -> Narrator -> FactChecker, plus Personalizer and Recap)
explains *why* each moment matters and writes it for the viewer: casual or analyst mode, favourite club, player-focus mode,
a single metric (xG / speed / passing), and language (English, Spanish and Malay built in; French, Arabic and Portuguese written by the model and fact-checked).
A FactChecker rejects any generated number not present in the source facts, so the narrative stays grounded and the system
degrades gracefully if a model fails. Overlays are timed, machine-readable JSON streamed over SSE, ready to render over a live feed.
Narration runs on a gpt-5-mini model deployed in **Microsoft Foundry**, with the Agent Framework workflow orchestrating the agents;
if the model is slow or unavailable the app falls back to grounded templates, so the demo never dies.
Problem: broadcasters and streamers need trustworthy, localised, per-audience insight in real time, without a human writing each caption.

Tech: Microsoft Agent Framework, Microsoft Foundry (gpt-5-mini deployment), GitHub Copilot [only if actually used], Python/FastAPI, React.
**Only list a service once the demo actually uses it.** Verified: Agent Framework workflow, live Foundry model calls (33 narrated moments in a full-match run), offline fallback, SSE, tests.
Not used / not verified (do NOT list): Azure Event Hubs, Azure Container Apps (drafts exist in `infra/`).
Video auto-eventing: only a prototype (tracks players in synthetic footage; no pass/shot detection from video). If mentioned, say "early prototype", never as a finished feature.

## Demo video script (target 1:50, screen recording + voiceover, no music, no logos)

Match: **Redcrest Rain Night** (goal at 29', then 42', 61', 68', 82'). Desktop browser, ~1440x900, server started with `./run.sh` (Foundry on).
Before recording: play the match once in **Casual/English** and once in **Analyst/Spanish** at 300x, so the AI wording is cached and appears instantly (it is shared per match, language and mode).

| Time | On screen | Say |
|---|---|---|
| 0:00-0:12 | App open on Redcrest, 3D pitch, kick off at 60x | "Football stories don't end at the scoreline. Inside the Game turns synthetic match events into explainable intelligence, live." |
| 0:12-0:30 | Casual mode: goal at 29' (use timeline "Jump to 29'"), toast + card | "A synthetic match, casual mode: the goal in plain words, the score, and the pitch shows the shape of both teams." |
| 0:30-0:50 | Gear: Analyst + Spanish, Apply; timeline, jump to 42'; goal card with xG, speed, pressure chips and the why line | "Same match, analyst mode in Spanish: xG, shot speed, and why it matters. Favourite club and player focus work the same way." |
| 0:50-1:15 | Tap "AI · fact-checked" on the card: How this was made. Then flip AI narration Off in Settings (3 s) and back | "Code spots the moment and calculates every number. A gpt-5-mini model on Microsoft Foundry writes the words. A fact-checker rejects any number not in the facts, and falls back to grounded text, so it never breaks." |
| 1:15-1:35 | Tactics tab (formation, line height, roles), then Line-ups tab | "Agents on Microsoft Agent Framework also read shape: formation, pressing, player roles, line-ups and substitutions." |
| 1:35-1:50 | Jump to full time: end card, recap, match report | "A full-time recap and match report, all from synthetic data. Inside the Game." |

Record at 1080p; trim to < 2:00 (judges stop at 2:00). Say "synthetic data" once. No real club logos or kits (none in the app). If you dislike voiceover, use large English captions instead.
Recording tips: macOS Cmd+Shift+5 (record selected window), hide the bookmarks bar, close other tabs, Do Not Disturb on, 100% zoom. Upload to YouTube as Unlisted or Public and check it plays logged-out.

## Pre-submission checklist

- [ ] Repo public, README renders, no secrets (`.env` is gitignored)
- [ ] Tests green in CI
- [x] Demo run once with Foundry (done 2026-10-21 via Azure OpenAI vars in `.env`); update any remaining bracketed items
- [ ] Video < 2:00, public URL, plays logged-out
- [ ] Project page: pitch, repo URL, video URL, category (Foundry / Multi-Agent; skip Azure Cloud Native unless deployed)
- [ ] English text throughout
