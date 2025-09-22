# Living World Simulation Engine

This repo contains a Python CLI that simulates the lives of Thomas Francis and Jordan Shreeve across five years (2025-09-20 -> 2030-09-20). The run is deterministic: all random choices are driven by a seeded RNG so repeated runs with the same inputs produce identical narratives and finance outputs.

Daily playbacks stream to the console and mirror to `.sim_logs/YYYY-MM-DD.log`, enabling log inspection or downstream tooling.

## Getting Started

```bash
# Install dependencies inside Codespaces or any Python 3.11 environment
pip install -r requirements.txt

# Run the daily simulation across the full window (narrative view)
python cli.py run --start 2025-09-20 --until 2030-09-20

# Fast weekly roll-up (concise bullets, quiet verbosity)
python cli.py run --start 2025-09-20 --until 2030-09-20 --step week --view concise --verbosity quiet

# Change the deterministic seed
python cli.py run --start 2025-09-20 --until 2025-09-22 --seed 1337

# Toggle output mode, verbosity, story settings, or line budget
python cli.py run --start 2025-09-20 --until 2025-09-22 --view mixed --verbosity detailed --story-length long --story-tone drama --max-lines 120

# Enable end-of-day branching choices
python cli.py run --start 2025-09-20 --until 2025-09-22 --interactive
```

VS Code tasks and the `Makefile` expose the same commands (`Install deps`, `Run (daily)`, `Run (weekly, fast)`, `Tests`).

## 🚀 Codespaces Preview

The project is optimized for GitHub Codespaces with pre-configured development environment:

### Quick Start Commands
- **Ctrl+Shift+P** → `Tasks: Run Task` → Select from:
  - `Quick Preview (3 days)` - Fast demo run
  - `Month Preview (30 days)` - See progression over time  
  - `Interactive Demo` - Make choices during simulation
  - `Run (weekly, fast)` - Full 5-year run in minutes

### Troubleshooting Rebuilds
If Codespaces rebuilds and extensions disappear:

1. **Extensions auto-install** - Wait ~30s for devcontainer to finish setup
2. **Manual reinstall** - Ctrl+Shift+P → `Extensions: Install Extensions` → Search for "Python"
3. **Python interpreter** - Ctrl+Shift+P → `Python: Select Interpreter` → Choose `/usr/local/bin/python`

The devcontainer is configured to automatically restore: Python, Pylance, GitHub Copilot, and other essential extensions.

## Data-Driven World

Simulation inputs live in `sim/data/` and can be edited without touching Python code:

- `people.yaml` - character bios, traits sliders, drives, and base holdings.
- `relationships.yaml` - directed edges with weight (-100..100) and tags.
- `households.yaml` - homes, vehicles, businesses (valuation + stress factor).
- `coin_prices.csv` - daily USD price history for the Origin Layer (`ORIGIN`) coin with headers `date,price_usd`.

Note: Populate `coin_prices.csv` with every day from 2025-09-20 through 2030-09-20 so that the final price on 2030-09-20 yields a portfolio value of **$86,210.00** for the ORIGIN position. Missing dates currently fall back to the last known price, so providing the full curve is how you shape the 5-year trajectory.

### Output design & saves

- `--view narrative|concise|mixed` selects the daily layout (cinematic prose, compact bullets, or blended).
- `--story-length short|medium|long|adaptive` keeps the story tight or lets big days sprawl; adaptive reacts to activity.
- `--story-tone neutral|drama|casual|journalistic` changes the narrator voice without touching the factual sections.
- `--verbosity quiet|normal|detailed` controls section density; quiet removes the `[STORY]` block, detailed raises the line cap.
- `--max-lines` trims lower-priority sections once the budget is hit (social first, then minor finance, romance, story).
- `--interactive` surfaces up to three choices each day and applies their effects immediately.
- Console output is mirrored to `.sim_logs/YYYY-MM-DD.log`; structured JSON exports live in `output/day_<date>.json`.
- Finance/social CSV appenders (`output/finance_<run>.csv`, `output/social_<run>.csv`) and state saves (`.sim_saves/<date>.json`) make downstream analysis deterministic.
- Weekly rollups (Sundays or weekly stepping) and monthly recaps (1st of each month) append summaries after the day's sections.

## Daily Flow

1. A `SimClock` walks the inclusive date range (day or week increments).
2. Scripted events fire first (e.g. the ORIGIN buy-in on 2025-09-21 where both Thomas and Jordy each invest USD 100,000 at $0.05).
3. Finance rules mark to market any ORIGIN holdings using `coin_prices.csv`, logging valuations per holder.
4. Stubs exist for social, romance, legal, and economy rules-ready for future expansion without breaking determinism.

Quiet days produce `(quiet day)` in both console and log files so diffing reruns stays simple.

## Tests

Install the UI tooling once with `npm install`, then run the combined suite via `make test` (or `pytest -q` / `npx playwright test` individually). The current checks cover:

- Weekly clock ticks advance seven days.
- World bootstrap loads the minimal YAML/CSV seed data.
- Browser automation confirms the menu music starts only after interaction, responds to the volume slider, and persists settings.

Add new tests near `tests/` to cover future rule engines or data regressions.

## Project Layout

```
.
|-- cli.py              # CLI entrypoint
|-- main.py             # Thin runner invoking the CLI
|-- sim/                # Core simulation package (config, time, entities, engines, rules, output)
|-- sim/data/           # YAML/CSV world data
|-- events/             # Scripted story beats
|-- tests/              # Pytest smoke tests
|-- .devcontainer/      # Codespaces environment (Python 3.11)
|-- .vscode/            # VS Code tasks & launch config
\-- .github/workflows/  # CI (pytest)
```

## Roadmap / TODOs

- [ ] `sim/world/rules/social.py`: Implement relationship-driven hangouts, tensions, and support scenes.
- [ ] `sim/world/rules/romance.py`: Add honesty vs loyalty driven tension/repair loops.
- [ ] `sim/world/rules/legal.py`: Surface ATO milestones affecting Jordy's stress and standing.
- [ ] `sim/engines/economy.py`: Model salaries, mortgage payments, lifestyle spend, and business volatility.
- [ ] `events/special.py`: Layer scripted beats (ATO verdict, group dinners, ex run-ins).
- [ ] `sim/data/*.yaml`: Expand cast list (Ella, Imogens, Lachlan, Ben D, Luke, Ben G, families, etc.).
- [ ] `sim/data/coin_prices.csv`: Fill the entire five-year ORIGIN curve ending at $86,210.00.

## Preview: Launching Both Servers

To run the full preview environment (web UI + API):

```bash
# 1. Start the static web server (serves index.html, script.js, styles.css)
python -m http.server 3000

# 2. In a separate terminal, start the FastAPI backend (for /api/simulations/launch and other endpoints)
uvicorn server.index:create_app --factory --host 0.0.0.0 --port 8000 --reload
```

- The web UI will be available at: http://localhost:3000
- The API server will be available at: http://localhost:8000

**Both servers must be running for full functionality (UI + API calls).**

You can also use VS Code tasks or Makefile targets to automate these steps.

## UI Playground (Live Preview)

A Vite-powered sandbox lives in `ui-playground/` for rapid UI iteration with hot reload.

- Dev server: http://localhost:5173 (port forwarded by the devcontainer)
- API proxy: requests to `/api/*` are forwarded to `http://localhost:8000` (FastAPI), so `/api/health` works out of the box.

Quick start:

```bash
# From the repo root
cd ui-playground
npm install
npm run dev
```

Or use VS Code: Ctrl+Shift+P → Tasks: Run Task → "UI Playground: Dev".

Edit `ui-playground/index.html` or any file in `ui-playground/src/` and your browser will update instantly. The sample page includes:

- Live "message" input bound to the preview panel
- Accent hue slider (updates CSS variable `--accent-hue`)
- "Ping API" button that calls `/api/health` through the proxy
