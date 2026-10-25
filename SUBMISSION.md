# Inside the Game: project description

Text for the Innovation Studio project page, plus instructions for judges to test the project.

## Pitch

**Inside the Game** turns a stream of synthetic football events into explainable, personalised match intelligence.
A seeded generator produces football-realistic passes, shots, tackles, pressure and possession events with pass-difficulty,
ball-speed and xG metadata. An interpreter folds them into live state (possession, xG, pressure share, momentum) and
detects moments: goals, big chances, momentum swings, control-vs-chaos spells, sprints, pass-quality and milestones.
A team of specialised agents on **Microsoft Agent Framework** explains *why* each moment matters and writes it for the viewer.
The Explainer and Narrator draft; the FactChecker checks every number against the moment's facts and sends a bad draft back to
its writer with the offending numbers (a real review loop in the workflow, up to two rewrites); the Editor decides how the card airs;
the Personalizer and Recap agents tailor and summarise. Personalisation covers casual or analyst mode, favourite club, player-focus mode,
a single metric (xG / speed / passing), and language (English, Spanish and Malay built in; French, Arabic and Portuguese written by the model and fact-checked).
A fact-checker rejects any generated number not present in the source facts, so the narrative stays grounded and the system
degrades gracefully if a model fails. Overlays are timed, machine-readable JSON streamed over SSE, ready to render over a live feed.
Narration runs on a gpt-5-mini model deployed in **Microsoft Foundry**, with the Agent Framework workflow orchestrating the agents;
if the model is slow or unavailable the app falls back to grounded templates, so it keeps working.
Every card has a "How this was made" panel showing what code calculated, what the AI wrote, each agent step and what the fact-checker verified.
The FactChecker also checks meaning on goal cards (a goal must read as a goal, "level" only when level, own goals name the right team)
and sends wrong drafts back. Measured on 202 live cards (gpt-5-mini, English/Spanish/French, `docs/evaluation.md`): 91% approved first time,
the other 9% approved after the FactChecker sent them back, 0 template fallbacks, 0 ungrounded numbers and 0 wrong-meaning goal cards aired,
3.9 s median from moment to verified card.
Under the hood, synthetic tracking moves 22 players every second with human speed limits, real set pieces and offside; the app infers
formations and roles from positions alone, measures distance and top speed, and its Restart Watch times throw-ins, goal kicks and
keeper holds against the countdowns in the Premier League and Pro Ref Competition Guidance Handbook 2026/27.
Problem: broadcasters and streamers need trustworthy, localised, per-audience insight in real time, without a human writing each caption.

## Microsoft and Azure technologies used

Microsoft Agent Framework (agent workflow with a review loop), Microsoft Foundry (gpt-5-mini deployment),
Azure Container Apps (live demo, scales to zero), Azure Container Registry, Azure AI Speech (spoken full-time recap, neural voices),
managed identity / Microsoft Entra ID (no keys stored in the cloud: the app reaches the model and Speech through its identity),
Log Analytics. Also Python/FastAPI and React.

Live demo: https://itg-app.bravecoast-6297858c.westus3.azurecontainerapps.io (it scales to zero when idle, so the first load can take up to ~40 s).
All data, clubs, players and stadiums are synthetic and fictional.

## Testing instructions (for judges)

The project runs locally; no account, login or key is needed (offline mode uses grounded templates for the wording).

```bash
git clone https://github.com/izzatonline/inside-the-game-ai.git && cd inside-the-game-ai
python3 -m venv .venv && . .venv/bin/activate
pip install --upgrade pip && pip install -e ".[dev]"
./run.sh --offline          # then open http://localhost:8000
```

Things to try: pick a match in the sidebar (Riverside Cup Tie and Redcrest Rain Night have scripted storylines with VAR and penalties),
switch Casual/Analyst, language, favourite club or player in the gear menu, tap a moment's label to see how it was made (each agent step),
tap the score to open the match timeline and jump to any minute, open Stats for Restart Watch and the player radar with distance and top speed,
toggle 2D/3D and the offside line, and watch the full-time recap (with a spoken version when Azure AI Speech is configured).
To use a model, copy `.env.example` to `.env` and fill in an Azure OpenAI / Foundry deployment, then run `./run.sh`.
The Agent Framework workflow needs Python 3.10+ (`pip install agent-framework`); without it the same agents run as plain Python.
