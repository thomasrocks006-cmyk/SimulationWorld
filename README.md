# Living World Simulation Engine

This repo contains a Python CLI that simulates the lives of Thomas Francis and Jordan Shreeve across five years (2025-09-20 → 2030-09-20). The run is deterministic: all random choices are driven by a seeded RNG so repeated runs with the same inputs produce identical narratives and finance outputs.

Daily playbacks stream to the console and mirror to `.sim_logs/YYYY-MM-DD.log`, enabling log inspection or downstream tooling.

## Getting Started

```bash
# Install dependencies inside Codespaces or any Python 3.11 environment
pip install -r requirements.txt

# Run the daily simulation across the full window
python cli.py run --start 2025-09-20 --until 2030-09-20

# Fast weekly roll-up (headers + key beats only in the console)
python cli.py run --start 2025-09-20 --until 2030-09-20 --step week --fast

# Change the deterministic seed
python cli.py run --start 2025-09-20 --until 2025-09-22 --seed 1337
```

VS Code tasks and the `Makefile` expose the same commands (`Install deps`, `Run (daily)`, `Run (weekly, fast)`, `Tests`).

## Data-Driven World

Simulation inputs live in `sim/data/` and can be edited without touching Python code:

- `people.yaml` – character bios, traits sliders, drives, and base holdings.
- `relationships.yaml` – directed edges with weight (-100..100) and tags.
- `households.yaml` – homes, vehicles, businesses (valuation + stress factor).
- `coin_prices.csv` – daily USD price history for the Origin Layer (`ORIGIN`) coin with headers `date,price_usd`.

👉 Populate `coin_prices.csv` with every day from 2025-09-20 through 2030-09-20 so that the final price on 2030-09-20 yields a portfolio value of **$86,210.00** for the ORIGIN position. Missing dates currently fall back to the last known price, so providing the full curve is how you shape the 5-year trajectory.

## Daily Flow

1. A `SimClock` walks the inclusive date range (day or week increments).
2. Scripted events fire first (e.g. the ORIGIN buy-in on 2025-09-21 where both Thomas and Jordy each invest USD 100,000 at $0.05).
3. Finance rules mark to market any ORIGIN holdings using `coin_prices.csv`, logging valuations per holder.
4. Stubs exist for social, romance, legal, and economy rules—ready for future expansion without breaking determinism.

Quiet days produce `(quiet day)` in both console and log files so diffing reruns stays simple.

## Tests

Run the smoke suite with `pytest -q`. It currently asserts:

- Weekly clock ticks advance seven days.
- World bootstrap loads the minimal YAML/CSV seed data.

Add new tests near `tests/` to cover future rule engines or data regressions.

## Project Layout

```
.
├── cli.py              # CLI entrypoint
├── main.py             # Thin runner invoking the CLI
├── sim/                # Core simulation package (config, time, entities, engines, rules, output)
├── sim/data/           # YAML/CSV world data
├── events/             # Scripted story beats
├── tests/              # Pytest smoke tests
├── .devcontainer/      # Codespaces environment (Python 3.11)
├── .vscode/            # VS Code tasks & launch config
└── .github/workflows/  # CI (pytest)
```

## Roadmap / TODOs

- [ ] `sim/world/rules/social.py`: Implement relationship-driven hangouts, tensions, and support scenes.
- [ ] `sim/world/rules/romance.py`: Add honesty vs loyalty driven tension/repair loops.
- [ ] `sim/world/rules/legal.py`: Surface ATO milestones affecting Jordy’s stress and standing.
- [ ] `sim/engines/economy.py`: Model salaries, mortgage payments, lifestyle spend, and business volatility.
- [ ] `events/special.py`: Layer scripted beats (ATO verdict, group dinners, ex run-ins).
- [ ] `sim/data/*.yaml`: Expand cast list (Ella, Imogens, Lachlan, Ben D, Luke, Ben G, families, etc.).
- [ ] `sim/data/coin_prices.csv`: Fill the entire five-year ORIGIN curve ending at $86,210.00.
