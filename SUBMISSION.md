# Inside the Game: project description

Text for the Innovation Studio project page, plus instructions for judges to test the project.

## Pitch

**Inside the Game** turns a stream of synthetic football events into explainable, personalised match intelligence.
A seeded generator produces football-realistic passes, shots, tackles, pressure and possession events with pass-difficulty,
ball-speed and xG metadata. An interpreter folds them into live state (possession, xG, pressure share, momentum) and
detects moments: goals, big chances, momentum swings, control-vs-chaos spells, sprints, pass-quality and milestones.
A team of specialised agents on **Microsoft Agent Framework** (Explainer -> Narrator -> FactChecker, plus Personalizer and Recap)
explains *why* each moment matters and writes it for the viewer: casual or analyst mode, favourite club, player-focus mode,
a single metric (xG / speed / passing), and language (English, Spanish and Malay built in; French, Arabic and Portuguese written by the model and fact-checked).
A fact-checker rejects any generated number not present in the source facts, so the narrative stays grounded and the system
degrades gracefully if a model fails. Overlays are timed, machine-readable JSON streamed over SSE, ready to render over a live feed.
Narration runs on a gpt-5-mini model deployed in **Microsoft Foundry**, with the Agent Framework workflow orchestrating the agents;
if the model is slow or unavailable the app falls back to grounded templates, so it keeps working.
Every card has a "How this was made" panel showing what code calculated, what the AI wrote and what the fact-checker verified.
Problem: broadcasters and streamers need trustworthy, localised, per-audience insight in real time, without a human writing each caption.

## Microsoft and Azure technologies used

Microsoft Agent Framework (agent workflow), Microsoft Foundry (gpt-5-mini deployment). Also Python/FastAPI and React.
All data, clubs, players and stadiums are synthetic and fictional.

## Testing instructions (for judges)

The project runs locally; no account, login or key is needed (offline mode uses grounded templates for the wording).

```bash
git clone <this repository> && cd insidethegame
python3 -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"
./run.sh --offline          # then open http://localhost:8000
```

Things to try: pick a match in the sidebar (Redcrest Rain Night has a scripted storyline), switch Casual/Analyst, language, favourite club or player in
the gear menu, tap a player in Line-ups for the radar and compare view, tap a moment's label to see how it was made, and drag the timeline to jump to a minute.
To use a model, copy `.env.example` to `.env` and fill in an Azure OpenAI / Foundry deployment, then run `./run.sh`.
The Agent Framework workflow needs Python 3.10+ (`pip install agent-framework`); without it the same agents run as plain Python.
