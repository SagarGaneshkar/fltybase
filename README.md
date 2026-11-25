# Drone Security Analyst Agent

A small, offline-first prototype for replaying a docked drone's daily property patrol. It turns simulated text-described frames and telemetry into object detections, cross-frame context, rule alerts, SQLite/FTS records, and searchable question answering.

## Live demo

- **Dashboard:** [https://drone-security-agent-ui5a.onrender.com](https://drone-security-agent-ui5a.onrender.com)
- **GitHub:** [https://github.com/Abhay-Ingle/droneagent](https://github.com/Abhay-Ingle/droneagent)

The demo is hosted on Render's free service plan. It can take about 50 seconds to respond after inactivity, and its SQLite data may reset when the service restarts or redeploys.

## Setup

Requires Python 3.10 or newer and SQLite built with FTS5 (included with standard CPython builds).

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

The deterministic rules and all tests work without network access or API keys. To enable hosted LangChain extraction and tool-calling Q&A, first install the optional integrations with `python -m pip install langchain langchain-openai langchain-google-genai`, then set `LLM_PROVIDER=openai` with `OPENAI_API_KEY`, or `LLM_PROVIDER=gemini` with `GOOGLE_API_KEY` (or `GEMINI_API_KEY`) in `.env`. Hosted calls require a valid key and network access. With no key, both extraction and answers use the local implementation.

Set `DRONE_DB_PATH` to change the database location. By default, the CLI stores `data/drone_security.db` and writes alerts to `data/alerts.log`.

## Deploy on Render

The repository includes a Render Blueprint in `render.yaml`. To deploy:

1. Create a GitHub repository named `drone-security-agent` under `Abhay-Ingle` and push this project. Do not include `.env`, `.venv`, local database/log files, or unrelated files such as PDFs.
2. In Render, choose **New → Blueprint**, connect GitHub, and select `Abhay-Ingle/drone-security-agent`.
3. Review the `drone-security-agent` web service and choose **Apply**. Render will build from `requirements.txt` and start the dashboard bound to its assigned `$PORT`.
4. Open the `onrender.com` URL shown in the service dashboard. The `/healthz` route is configured for health checks. On first visit, press **Start patrol** to populate the demo data.

The Blueprint uses Render's free web-service plan. Free services have an ephemeral filesystem: SQLite records and `data/alerts.log` can be lost when the service restarts, spins down, or redeploys. The app contains only synthetic scenario data; do not add real camera footage, property telemetry, API keys, or credentials to a public repository. Upgrade to a plan with persistent storage or use a managed database before relying on hosted records.

## Run

```powershell
python main.py
python main.py ui
python main.py ui --host 127.0.0.1 --port 8765
python main.py run
python main.py run --speed 60
python main.py query --object truck
python main.py query --time 00:00-01:00
python main.py query --text "main gate"
python main.py ask "What objects were in the video?"
python main.py ask
python main.py summary
python main.py caption .\path\to\image.jpg
```

With no subcommand, `python main.py` opens the local dashboard server at `http://127.0.0.1:8765`; `python main.py ui` does the same. In the dashboard, select a replay speed, press **Run patrol**, inspect live detections and alerts, filter/search the frame timeline, and ask the analyst questions. Keep that terminal open while using the dashboard and press `Ctrl+C` to stop it. The dashboard is local-only by default and adds no web dependencies.

`--speed` is a replay multiplier: `0` (the default) runs immediately; `60` makes one simulated minute take one real second. `caption` is optional and separate from the main patrol pipeline; install `transformers` and `torch` separately to run the BLIP model. For the optional three-to-five-image batch demo, run `python -m src.vlm_caption image1.jpg image2.jpg image3.jpg`.

## Tests

```powershell
python -m pytest -q
```

All tests use a temporary/in-memory SQLite database and deterministic fallback behavior, so they do not call hosted services.

## Design decisions and trade-offs

- The scenario is human-readable JSON; timestamps are sorted by the simulator even when callers supply frames out of order.
- Data models use standard-library dataclasses and type hints to keep the offline install small.
- SQLite stores frame, object, and alert context. FTS5 supplies keyword search without a separate database service.
- The deterministic detector intentionally covers common scenario vocabulary rather than claiming to perform computer vision. An optional LangChain structured-output extractor is selected when a provider key is configured.
- The tracker uses stable, simple object identities (vehicle color/model; person by zone/color) and consecutive replay frames for persistence. It is not a production-grade visual identity tracker.
- Rules are local, inspectable, and configurable in `src/alert_engine.py`. Alert output is stored in both SQLite and the alert log.
- The offline Q&A routes known intents directly to indexer functions; configured LLM use binds those same operations as LangChain tools and retains a per-agent message history.

## AI tools and impact

_Fill in the AI tools used, the work they assisted with, and any changes you made after reviewing their output._

## Limitations

- Input frames are simulated descriptions, not video pixels; the fallback detector cannot recognize objects absent from the text.
- No production camera/drone integration, authentication, user roles, or multi-property isolation is included.
- Object identity is heuristic, so two visually similar objects can be conflated.
- Hosted LLM responses can vary and require external credentials. Tests deliberately force the deterministic path.
- SQLite FTS5 is lexical search, not semantic/vector retrieval.
- BLIP is an optional captioning demo, not part of alert detection or indexing.
