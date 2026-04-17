# Call Intelligence Tool

A tool for a real-estate sales manager to review her telecaller team's performance.
Processes Tamil-English code-switched call transcripts, extracts structured data,
scores telecaller quality on a 0–5 rubric, and surfaces everything in a single
dashboard.

Built for the **Zetta Technologies** Full-Stack Engineering Intern take-home.

## Quick start (local, one command)

```bash
# 1. Get a free Gemini API key at https://aistudio.google.com/apikey
# 2. Put it in a .env file next to this README:
echo "GEMINI_API_KEY=your_key_here" > .env

# 3. Run with docker compose
docker compose up --build
# Dashboard: http://localhost:8000
```

If you prefer not to use Docker:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export GEMINI_API_KEY=your_key_here
uvicorn main:app --app-dir backend --reload
```

## Pre-seeded data

The repo ships with `data/processed.db` containing all **150 calls already processed**.
The deployed URL shows a populated dashboard with zero runtime LLM cost.

To regenerate locally:

```bash
python backend/seed.py            # only processes calls not already in DB
python backend/seed.py --force    # reprocess everything
python backend/seed.py --limit 5  # smoke test
```

## What's in here

| Path | What it does |
|------|--------------|
| `backend/pipeline.py` | Single-shot Gemini call → validated extraction + scoring JSON |
| `backend/rubric.py` | 0–5 anchors for each of the 4 scoring dimensions |
| `backend/main.py` | FastAPI app: REST API + serves the static frontend |
| `backend/db.py` | SQLite storage, idempotency by transcript hash |
| `backend/seed.py` | Pre-processes all 150 calls once |
| `backend/eval.py` | Eval harness for a labeled test set (stretch S3) |
| `frontend/index.html` | Single-file dashboard (Tailwind CDN, no build step) |

## Features

**Must-haves (all done):**
- Per-call extraction of 5 structured fields
- Per-call quality scoring on 4 dimensions with explicit 0–5 anchors
- Last-stage identification, next-action recommendation, 2-sentence summary
- List view with filter (telecaller, site-visit, action, min-score), sort (any column), search (lead / telecaller)
- Detail view with full transcript formatting, all scores + reasons, tooltipped rubric legend
- Upload flow (`POST /api/upload`) accepting `transcript | text | content | call_transcript` keys

**Stretch goals delivered:**
- **S1 Leaderboard** — `/api/leaderboard`, ranked telecaller scores
- **S2 Edit + recompute** — `POST /api/calls/{id}/edit` (wired in API; not yet surfaced in UI)
- **S3 Eval harness** — `backend/eval.py`
- **S4 Admin telemetry** — `/api/admin/telemetry` → Admin tab
- **S5 Caching / idempotency** — re-uploading the same transcript returns cached result

## API

| Method | Path | Notes |
|--------|------|-------|
| GET    | `/api/health` | liveness |
| GET    | `/api/calls` | list all 150 calls |
| GET    | `/api/calls/{id}` | detail incl. analysis & transcript |
| POST   | `/api/upload` | body `{transcript: "..."}` — runs full pipeline |
| POST   | `/api/calls/{id}/edit` | `{field, value}` — edit + recompute |
| GET    | `/api/leaderboard` | aggregated telecaller scores |
| GET    | `/api/rubric` | rubric JSON (feeds the UI tooltip) |
| GET    | `/api/admin/telemetry` | LLM call count, p50/p95 latency |

## Deploy to Render

1. Push this repo to GitHub (private).
2. New → Web Service → point at the repo; Render auto-detects `render.yaml`.
3. In the service's Environment tab, set `GEMINI_API_KEY`.
4. Deploy. First build installs deps; the pre-seeded DB is baked into the image.

See `DECISIONS.md` and `AI_USAGE.md` for design notes.
