# Key Design Decisions

## 1. One LLM call per transcript, returning all fields in one JSON object

- **Alternatives considered:** separate calls per field group (extraction / scoring / next-action);
  a chained "planner → extractor → scorer" setup.
- **Why this:** A single call is ~3× cheaper in tokens and keeps latency under ~2 s per transcript —
  which matters for the live upload flow the grader will test. Spot-checks on 10 transcripts
  showed <5% drift in scoring versus a chained 3-call pipeline, not worth the extra latency.
  The rubric and field semantics are embedded in the system prompt so the model reasons about
  extraction + scoring jointly.
- **What I'd change with more time:** Add a cheap verifier pass that re-reads the output JSON
  alongside the transcript and only flags disagreements — closes the ~5% accuracy gap without
  paying the full chained-call tax.

## 2. SQLite with pre-seeded DB committed to the repo

- **Alternatives considered:** Supabase / Postgres; run the pipeline at server start; empty DB
  that fills as the user clicks around.
- **Why this:** The grading rubric explicitly says "deployed URL must show 150 calls on first
  load, not an empty state." Pre-processing once locally and committing the `.db` file means
  the deployed service has zero runtime LLM cost to display the dashboard, survives free-tier
  restarts without re-hitting the API, and has no external DB dependency. SQLite is plenty for
  the data size (~2 MB).
- **What I'd change with more time:** Switch to a managed Postgres when real ingestion starts
  (calls flowing in from a phone system), so many managers can collaborate.

## 3. Single-file vanilla JS frontend instead of Next.js / React build

- **Alternatives considered:** Next.js (which is what Zetta uses internally), Vite + React.
- **Why this:** The dashboard is a list + a detail modal + an upload form + a leaderboard —
  it doesn't need a build toolchain, routing library, or state manager. A single `index.html`
  with Tailwind via CDN keeps deployment to one service (no separate frontend host), the code
  is easy to skim during a walkthrough, and there are no Node-version-mismatch surprises on
  Render. The grading emphasises "operator fit over visual polish," so I spent time on useful
  columns and filters instead of a component framework.
- **What I'd change with more time:** Migrate to Next.js with the same layout; the payoff
  would come from adding a real edit UI (S2) and per-telecaller drill-down pages.

## 4. Rubric defined in code (`rubric.py`) and surfaced both to the LLM and the UI

- **Alternatives considered:** Hand-crafted prompt strings kept separate from the UI legend;
  hard-coding anchor text in two places.
- **Why this:** 15% of the grade is rubric quality, and the brief explicitly warns that UI
  legend + LLM prompt diverging is a common failure. Having `rubric.py` as the single source
  of truth — consumed by both the prompt (`rubric_as_prompt_block()`) and the frontend tooltip
  (`/api/rubric`) — means any rubric tweak propagates everywhere at once. Also documents the
  "objection_handling = 3 when no objections raised" rule in one place so it's actually
  applied consistently.
- **What I'd change with more time:** Add per-anchor exemplar transcripts next to each score,
  so managers can click a score and see "here's what a 4 on pitch looks like in the wild."

## 5. Idempotent upload by transcript hash (caching / stretch S5)

- **Alternatives considered:** Always re-run the pipeline; require the client to send a
  call_id and check that.
- **Why this:** Transcripts are long, managers may re-upload them, and the grader will POST
  held-out transcripts — so skipping an LLM call when we've already seen exact text is free
  savings on free-tier quota. SHA-256 of the trimmed transcript is the cache key (stored in
  a dedicated indexed column). If the key hits, we return the stored analysis with
  `"cached": true`. If it misses, we run the pipeline and store by both call_id and hash.
- **What I'd change with more time:** Normalise whitespace / punctuation before hashing so
  trivial reformat of a transcript still hits the cache, and expose a "reprocess" button to
  force regeneration.

## 6. Auto-generated IDs for uploaded transcripts

- **Alternatives considered:** Require the client to supply a `call_id` and
  `telecaller_name` with each upload; prompt the user for these via extra form
  fields before processing.
- **Why this:** The brief specifies the upload payload is transcript-only.
  Asking the grader (or a real manager pasting a fresh transcript) to also
  come up with a lead ID and telecaller name adds friction for fields that
  are easily synthesised. IDs use `UPLOAD_<UTC-timestamp>` (e.g.
  `UPLOAD_20260420T133000`) which is guaranteed unique on this single-writer
  SQLite setup. Telecaller / lead names default to "Uploaded" and "Uploaded Lead"
  so uploaded calls are visually distinct from the 150 seeded calls in the list.
- **What I'd change with more time:** Parse the first "Agent: ..." line of
  the transcript to auto-extract the telecaller name ("Hello sir, Karthik
  from Casagrand" → `Karthik`) so uploads slot correctly into the leaderboard
  ranking.