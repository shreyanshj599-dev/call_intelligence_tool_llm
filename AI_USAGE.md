# AI Usage

## LLM in the pipeline

- **Provider:** Google AI Studio (Gemini)
- **Model:** `gemini-2.0-flash`
- **Mode:** structured JSON output (`response_mime_type: "application/json"`,
  `temperature: 0.1`)
- **Call count across the 150 transcripts:** 150 (one call per transcript, no retries
  on the successful run). Upload flow adds one call per uploaded transcript — cached
  by transcript hash so repeats cost zero.
- **Estimated cost:** $0 — comfortably inside Gemini free tier (1,500 requests/day,
  15 RPM). Seeding all 150 transcripts took ~3.5 minutes with a 0.5 s pacing sleep.
- **Why this model:** Free-tier generosity, fast enough that upload feels interactive
  (p95 under ~2 s in my local runs), and strong enough to follow the rubric in
  Tamil-English code-switched text.

## AI coding tool usage

- **Tool:** Claude Code (Anthropic) — used for the bulk of scaffolding.
- **Roughly what % was AI-assisted:** ~75%. Core prompt engineering, rubric anchor
  text, and the field-validation coercion logic were written/edited by hand after
  reading the TAKEHOME brief carefully.
- **What I accepted:** the FastAPI + SQLite scaffold, Tailwind + vanilla-JS dashboard
  layout, the Dockerfile, and the first draft of the seeder script.
- **What I rejected / rewrote:**
  1. First draft of the Gemini prompt asked the model to "summarize the call" before
     extracting fields, which wasted tokens and made outputs noisier. Rewrote to a
     single schema-first prompt with semantics documented inline — cheaper and more
     consistent.
  2. First draft of the scoring rubric used vague qualifiers ("good pitch = 4").
     Replaced with concrete count-based anchors ("covered 4 of location / price /
     specs / amenities / builder credibility / EMI / RERA") so two graders would
     agree on the same score.
  3. First draft stored each extraction field in its own SQLite column. Collapsed
     to a single `analysis_json` blob because the shape is query-light and column
     sprawl was making migrations for rubric tweaks painful.

## Honesty note

Tamil-English interpretation was checked against ~10 sample transcripts from
`calls.jsonl` before shipping — spot-checked that `preferred_locations` correctly
ignored locations the telecaller mentioned but the lead did not agree to, and
that scores for calls that ended abruptly landed in the `call_cut` / low-score
cluster as expected.
