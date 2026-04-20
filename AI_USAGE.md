# AI Usage

## LLM in the pipeline

- **Provider:** Groq (OpenAI-compatible API)
- **Model:** `llama-3.1-8b-instant`
- **Mode:** structured JSON output (`response_format: {"type": "json_object"}`,
  `temperature: 0.1`)
- **Call count across the 150 transcripts:** 150 (one call per transcript,
  no retries on the successful run). Upload flow adds one call per uploaded
  transcript — cached by transcript hash so repeats cost zero.
- **Estimated cost:** $0 — inside Groq's free tier. Seeding all 150 transcripts
  took ~3 minutes with pacing between calls.
- **Why this model:** Initially targeted Gemini 2.0-flash, but hit free-tier
  quota issues (limit: 0 on my account) during seeding. Switched to Groq
  `llama-3.1-8b-instant` because (a) the most generous free quota on Groq
  (500K tokens/day) meant I could re-seed the full dataset without quota
  anxiety, (b) sub-second latency (~300ms per call) makes the live upload flow
  feel instant, (c) JSON-mode adherence is strong and the structured extraction
  task doesn't require the larger 70b model's reasoning depth, (d) the
  pipeline auto-detects provider via env vars so swapping to `llama-3.3-70b-versatile`
  or Gemini is a single environment-variable change.

## AI coding tool usage

- **Tool:** Claude Code (Anthropic) — used for the bulk of scaffolding.
- **Roughly what % was AI-assisted:** ~75%. Core prompt engineering, rubric
  anchor text, and the field-validation coercion logic were written/edited
  by hand after reading the TAKEHOME brief carefully.
- **What I accepted:** the FastAPI + SQLite scaffold, Tailwind + vanilla-JS
  dashboard layout, the Dockerfile, and the first draft of the seeder script.
- **What I rejected / rewrote:**
  1. First draft of the LLM prompt asked the model to "summarize the call"
     before extracting fields, which wasted tokens and made outputs noisier.
     Rewrote to a single schema-first prompt with semantics documented inline.
  2. First draft of the scoring rubric used vague qualifiers ("good pitch = 4").
     Replaced with concrete count-based anchors ("covered 4 of location / price /
     specs / amenities / builder credibility / EMI / RERA") so two graders
     would agree on the same score.
  3. First draft stored each extraction field in its own SQLite column.
     Collapsed to a single `analysis_json` blob because the shape is query-light
     and column sprawl was making migrations for rubric tweaks painful.
  4. After hitting Gemini free-tier quota limits mid-seeding, restructured
     `pipeline.py` with **Groq as the primary provider** (`llama-3.1-8b-instant`)
     and **Gemini retained as an automatic fallback**. Provider selection is
     env-var-driven (`GROQ_API_KEY` presence → use Groq; else fall back to
     Gemini) so the same code runs on either backend with zero code changes.
     Swapping to `llama-3.3-70b-versatile` is a one-line env-var change.

## Honesty note

Tamil-English interpretation was checked against ~10 sample transcripts from
`calls.jsonl` before shipping — spot-checked that `preferred_locations`
correctly ignored locations the telecaller mentioned but the lead did not
agree to, and that scores for calls that ended abruptly landed in the
`call_cut` / low-score cluster as expected.