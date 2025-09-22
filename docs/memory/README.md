# Memory Subsystem

The memory subsystem captures long-lived context for the simulation so RAG pipelines can rebuild a 256k-token view of the world on demand. It stores deterministic truths (entities, attributes, states, events) separately from narrative summaries and retrieval chunks, with optional vector search when pgvector/sqlite-vec are available. When `MEMORY_ENABLED=true`, the simulation invokes `MemoryBridge` at the end of each day so ticks land in memory automatically.

## Data Model

| Table | Purpose |
| --- | --- |
| `entities` | Canonical people, wallets, properties, businesses, securities. |
| `attributes` | Slowly changing key/value facts scoped to an entity with validity windows. |
| `relations` | Graph edges between entities (ally, owns, member_of, etc.). |
| `events` | Point-in-time activity logs (`txn`, `price_move`, `decision`, `life_event`, `note`) with linked entities. |
| `daily_state` | Global snapshot JSON + summary for each simulation day. |
| `entity_state` | Truthy numeric state per entity per day + an LLM-ready short summary. |
| `chunks` | Retrieval-ready text fragments for summaries, events, policy docs. |
| `embeddings` | Vector representations for each chunk (pgvector or sqlite blob fallback). |

Refer to `server/db/migrations/*.sql` for the exact schema (Postgres defaults) and `server/db/migrations/sqlite/*.sql` for the SQLite variant.

## Configuration

Environment variables control the subsystem:

- `MEMORY_ENABLED` (`true|false`) — feature flag; the API returns `503` when disabled.
- `MEMORY_DB_VENDOR` (`postgres|sqlite`) — explicit vendor override; auto-detected from URL when omitted.
- `MEMORY_DB_URL` — connection string (SQLite dev default: `sqlite:///./memory.db`).
- `EMBEDDINGS_MODEL` — name recorded for generated embeddings.
- `LLM_MODEL` — summarizer attribution; real LLMs can replace the stub summarizer later.
- `MEMORY_MAX_TOKENS` — upper bound for prompt-pack assembly (default `30000`).
- `VECTOR_DIM` — embedding dimension (default `1536`, must match pgvector column width).
- `RETRIEVER_LIMIT_*` — tune chunk/event/state windows (`chunks`, `events`, `states_days`).
- `MEMORY_SQL_ECHO` — set to `true` to surface SQL debugging output.
- `LLM_API_KEY` / `OPENAI_API_KEY` — enables remote chat completions for summaries (`LLM_MODEL`).
- `LLM_API_BASE` — override the chat completion endpoint base URL (defaults to OpenAI-compatible `https://api.openai.com/v1`).
- `EMBEDDINGS_API_KEY` / `EMBEDDINGS_API_BASE` — custom embedding endpoint/credentials (fallbacks to the LLM values when omitted).
- `MEMORY_HTTP_TIMEOUT` — HTTP timeout (seconds) for LLM/embedding requests (default `15`).

## Running the API

```bash
pip install -r requirements.txt
export MEMORY_ENABLED=true
# SQLite dev store lives at ./memory.db by default
uvicorn server.index:app --reload
```

FastAPI routes mount under `/api/memory/*`:

- `GET /api/memory/status` – DB + vector health snapshot.
- `POST /api/memory/entity` – upsert an entity.
- `POST /api/memory/event` – append an event.
- `POST /api/memory/tick/run` – run the daily tick pipeline with supplied truths.
- `POST /api/memory/retrieve` – hybrid retriever returning a prompt pack.
- `GET /api/memory/entity/{id}/state/latest` – latest saved state for an entity.
- `GET /api/memory/daily/{date}` – global daily state by ISO date.

### App Brain (GPT-5 integration)

`server/src/brain.py` exposes an `AppBrain` class that orchestrates retrieval, token budgeting, and GPT-5 calls. Instantiate it anywhere in the app (CLI, background jobs, API routes):

```python
from server.src.brain import AppBrain

brain = AppBrain()
answer = brain.reason("How is the Origin wallet performing?", entity_scope=[wallet_id], mode="simulation")
```

Modes map to context/token budgets:

| Mode | Max Tokens | Output Cap | Retriever Limits |
| --- | --- | --- | --- |
| `simulation` | 20k | 2k | states 14d, 500 events, 30 chunks |
| `status` | 15k | 1.5k | states 10d, 400 events, 20 chunks |
| `narrative_long` | 60k | 60k | states 28d, 800 events, 60 chunks |

If no GPT credentials are configured the brain falls back to a deterministic summary, so local development remains fully offline.

## Daily Tick Pipeline

`server/src/memory/tick_pipeline.py` processes one simulation day:

1. Persist truthy numerics (`entity_state`, `daily_state`).
2. Generate summaries via the configured LLM; falls back to the local template when no credentials are provided.
3. Chunk new summaries/events (`Chunker`) targeting 900-token spans with 120-token overlap.
4. Embed new chunks via `embeddings.embed_batch`; pgvector is used when available, otherwise blobs are saved for keyword-only fallback.
5. Basic hygiene: deduplicate same-text chunks and refresh embeddings.

Call the pipeline manually via `POST /api/memory/tick/run`, reuse the `MemoryJobManager` to schedule `tick:run` background jobs, or simply run the simulation (`python cli.py run ...`) and let `MemoryBridge` push daily ticks automatically. Sundays emit weekly “arc” summaries that capture the last month of activity per entity; these feed long-form narrative mode.

## Retrieval

`Retriever` composes a prompt pack:

- Latest 14-day states for scoped entities.
- 60-day window of events touching those entities.
- Keyword + vector search across `chunks` with scoring (`0.45 semantic + 0.25 keyword + 0.20 recency + 0.10 entity graph bonus`).
- Truncates to stay under `MEMORY_MAX_TOKENS`.

Example request:

```bash
curl -X POST http://localhost:8000/api/memory/retrieve \
  -H 'content-type: application/json' \
  -d '{
        "question": "How has the Origin wallet changed this month?",
        "entity_scope": ["wallet:origin:..."],
        "keywords": ["origin", "wallet", "balance"]
      }'
```

The response contains `states`, `events`, and scored `chunks` ready to feed into an LLM.

## CLI Helpers

Scripts live in `scripts/memory/`:

- `python scripts/memory/seed.py` – creates sample people, wallets, a daily tick, and embeddings.
- `python scripts/memory/backfill.py data.csv` – consumes CSVs (`date,entity_id,metric,value[,ts,actor_id,type]`) to backfill ticks.

Hook them into package managers if desired (`pnpm memory:seed`, etc.).

## Testing

```
pip install -r requirements.txt
npm install
make test
```

`pytest` covers IDs, store round-trips, retriever scoring, tick pipeline, and FastAPI routes. Playwright continues to run the UI regression suite.

## Troubleshooting

- **pgvector missing** – run the `0003_memory_vector.sql` migration against Postgres (`CREATE EXTENSION vector`). The system still operates (keyword-only) without it.
- **sqlite-vec unavailable** – embeddings are stored as raw blobs; retrieval automatically skips vector reranking.
- **Embedding dim mismatch** – ensure `VECTOR_DIM` matches the column definition (`vector(1536)` in Postgres). Recreate or migrate the embeddings table after resizing.
- **fts5 not compiled** – SQLite needs the FTS5 module; install the standard `libsqlite3` or switch to Postgres.
- **Memory disabled responses** – set `MEMORY_ENABLED=true` and restart the server.

## Runbook

1. Ensure migrations ran: `python -c 'from server.src.memory.config import load_memory_config, create_engine_from_config; from server.src.memory.schema import run_migrations; cfg=load_memory_config(); eng=create_engine_from_config(cfg); run_migrations(eng, cfg.db_vendor)'`.
2. Seed or backfill data.
3. Launch `uvicorn server.index:app`.
4. Watch `/api/memory/status` for counts and last tick time.
5. Use `MemoryJobManager` (via custom bootstrap) to schedule the nightly tick.
6. For retriever quality issues, inspect the latest chunks via SQL and ensure embeddings exist.
