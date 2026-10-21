# Submission kit (not part of the app: copy into the Innovation Studio project page)

Deadline: **2026-10-27 11:59 PM PT**. Needs: pitch, public GitHub repo URL, public video URL (YouTube/Vimeo/Facebook/Youku) under **2:00**.

## Pitch (paste, edit the [brackets] once true)

**Inside the Game** turns a stream of synthetic football events into explainable, personalised match intelligence.
A seeded generator produces football-realistic passes, shots, tackles, pressure and possession events with pass-difficulty,
ball-speed and xG metadata. An interpreter folds them into live state (possession, xG, pressure share, momentum) and
detects moments: goals, big chances, momentum swings, control-vs-chaos spells, sprints, pass-quality and milestones.
A team of specialised agents on **Microsoft Agent Framework** (Explainer -> Narrator -> FactChecker, plus Personalizer and Recap)
explains *why* each moment matters and writes it for the viewer: casual or analyst mode, favourite club, player-focus mode,
a single metric (xG / speed / passing), and language (English, Spanish, Malay offline; any language with a model).
A FactChecker rejects any generated number not present in the source facts, so the narrative stays grounded and the system
degrades gracefully if a model fails. Overlays are timed, machine-readable JSON streamed over SSE, ready to render over a live feed.
Narration runs on a gpt-5-mini model deployed in **Microsoft Foundry**, with the Agent Framework workflow orchestrating the agents;
if the model is slow or unavailable the app falls back to grounded templates, so the demo never dies.
Problem: broadcasters and streamers need trustworthy, localised, per-audience insight in real time, without a human writing each caption.

Tech: Microsoft Agent Framework, Microsoft Foundry (gpt-5-mini deployment), GitHub Copilot [only if actually used], Python/FastAPI, React.
**Only list a service once the demo actually uses it.** Verified: Agent Framework workflow, live Foundry model calls (33 narrated moments in a full-match run), offline fallback, SSE, tests.
Not used / not verified (do NOT list): Azure Event Hubs, Azure Container Apps (drafts exist in `infra/`).

## Demo video script (target 1:45, screen recording + voiceover, no music, no logos)

| Time | On screen | Say |
|---|---|---|
| 0:00-0:10 | UI, Kick off at 60x | "Football stories don't end at the scoreline. Inside the Game explains the match as it happens." |
| 0:10-0:30 | Casual mode, goal overlay appears | "Same synthetic match, casual mode: a goal, in plain words, with the score." |
| 0:30-0:55 | Switch to Analyst + Spanish; goal overlay shows xG, shot speed, pressure chips and the 'why' line | "Analyst mode in Spanish: xG, shot speed, and *why it matters*: this team had 92% of the pressure, so the goal rewards control." |
| 0:55-1:10 | Player focus + metric = speed; sprint overlays; open JSON panel | "Player focus or a single metric. Every overlay is timed, machine-readable JSON for a broadcast renderer." |
| 1:10-1:35 | Terminal: `python -m itg.demo` | "Agents hand off: explainer, narrator, fact-checker on Agent Framework. Here the model hallucinates numbers; the fact-checker rejects them and falls back to grounded text." |
| 1:35-1:45 | Recap panel, then architecture diagram from README | "Full-time recap, powered by Foundry with grounded fallbacks. Inside the Game." |

Record at 1080p; trim to < 2:00 (judges stop at 2:00). Say "synthetic data" once. Don't show real club logos/kits.

## Pre-submission checklist

- [ ] Repo public, README renders, no secrets (`.env` is gitignored)
- [ ] Tests green in CI
- [x] Demo run once with Foundry (done 2026-10-21 via Azure OpenAI vars in `.env`); update any remaining bracketed items
- [ ] Video < 2:00, public URL, plays logged-out
- [ ] Project page: pitch, repo URL, video URL, category (Foundry / Multi-Agent; skip Azure Cloud Native unless deployed)
- [ ] English text throughout
