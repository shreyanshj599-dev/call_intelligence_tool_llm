# Zetta Technologies — Internship Take-Home Assignment

## Call Intelligence Tool for Real Estate Sales Teams

**Role:** Full Stack Engineering Intern / Forward Deployed Engineering Intern  
**Time budget:** 8–12 hours of focused work  
**Deadline:** 72 hours from receiving this brief  

---

## Context

You're building a tool for a real estate company's sales operations team. The company runs a telecaller team that makes hundreds of outbound calls daily to prospective homebuyers. These calls are recorded and transcribed. Today, a sales manager has no automated way to understand what happened on each call — she listens to random samples manually, which doesn't scale.

Your job: **build and deploy a Call Intelligence Tool** that processes call transcripts and gives the sales manager a dashboard to review her team's performance.

---

## What You're Given

A JSONL file (`calls.jsonl`) containing **150 call transcripts**. Each entry has:

```json
{
  "call_id": "CALL_0042",
  "telecaller_id": "TC_004",
  "telecaller_name": "Priya Shankar",
  "lead_id": "LEAD_1187",
  "lead_name": "Ramesh K",
  "duration_sec": 245,
  "timestamp": "2026-04-10T14:32:00+05:30",
  "transcript": "[00:00-00:04] Agent: Hello sir, vanakkam, ...\n[00:04-00:10] Lead: haan sollunga..."
}
```

**Important characteristics of the data:**
- Transcripts are in **Tamil-English code-switched** conversational style — telecallers and leads naturally mix Tamil and English within sentences
- Some transcripts are primarily Tamil with English numbers and real-estate terms
- Some calls end abruptly (lead hangs up mid-conversation)
- Transcription quality varies — occasional STT artifacts and misspellings
- Duration ranges from 30 seconds to 8 minutes

---

## What You Must Build

### 1. Per-Call Extraction

For each call transcript, extract the following structured fields:

| Field | Type | Values |
|-------|------|--------|
| `unit_configuration` | enum | `2BHK` · `3BHK` · `4BHK` · `villa` · `plot` · `not_discussed` |
| `budget_range` | object | `{ "min_lakhs": number, "max_lakhs": number }` or `"not_discussed"` |
| `timeline` | enum | `immediate` · `3_to_6_months` · `6_to_12_months` · `exploring` · `unclear` |
| `preferred_locations` | array | list of location strings mentioned by the lead (can be multiple), or `[]` |
| `site_visit_outcome` | enum | `committed_with_date` · `committed_no_date` · `declined` · `not_asked` · `call_cut` |

**Field semantics (read these before writing prompts):**

- `budget_range` — the price range the lead **stated or visibly engaged with without pushback**. If the lead explicitly states a budget ("I'm looking at 60–75 lakhs"), use that. If the telecaller quotes a price and the lead continues the conversation without pushing back, infer that as the range. If the lead neither stated a budget nor engaged with a specific price point, use `"not_discussed"`.
- `preferred_locations` — only locations the **lead** expressed a preference for. Ignore locations the telecaller mentioned unless the lead agreed. Can contain more than one entry.
- `site_visit_outcome` — the state of the site visit at call-end. If the lead deferred ("I'll discuss and let you know"), either `committed_no_date` or `declined` is acceptable — our grader gives partial credit for adjacent labels.
- `timeline` — the lead's purchase horizon. Use `unclear` only when no timeline can be inferred at all.

### 2. Per-Call Quality Scoring

Score the **telecaller's performance** on four dimensions. Each dimension is scored 0–5 with a one-sentence reason.

| Dimension | What it measures |
|-----------|-----------------|
| `discovery` | Did the telecaller ask about budget, timeline, unit preference, and current living situation? |
| `pitch` | Did the telecaller explain the project's value proposition — location, amenities, pricing, builder credibility? |
| `objection_handling` | When the lead raised concerns (price, location, timing, competition), did the telecaller address them substantively? |
| `next_step` | Did the telecaller attempt to secure a concrete next action — site visit date, callback time, document sharing? |

**Your rubric is part of what we evaluate.** 15% of your grade is "scoring rubric quality" — this means:

- Define explicit 0–5 anchors for each dimension. What does a 3 on `pitch` mean versus a 4? Be specific.
- Document your anchors in `DECISIONS.md` *or* surface them in the UI (a tooltip, a legend, wherever a sales manager would see them).
- The `reason` field for each score should cite concrete evidence from the transcript, not generic praise ("good call" is a zero-signal reason; "asked about budget and timeline but skipped family size and current living situation" is a useful reason).

**Starter anchor for `discovery`** (you may adopt, modify, or replace this — we grade the design decision, not conformance to ours):

| Score | Meaning |
|-------|---------|
| 5 | Asked about all four: budget, timeline, unit preference, current living situation |
| 4 | Asked about three of the four |
| 3 | Asked about two of the four |
| 2 | Asked one discovery question, or asked all four but very superficially |
| 1 | Vague discovery attempt ("what are you looking for?") with no follow-up |
| 0 | No discovery questions at all — went straight to pitch |

Design similar anchors for `pitch`, `objection_handling`, and `next_step`. Your anchors should be *applicable without arguing* — two graders reading the same transcript with your rubric should arrive at the same score most of the time.

### 3. Call Stage Identification

Identify the **last stage the call reached** before ending:

| Stage | Description |
|-------|-------------|
| `greeting` | Call ended during or just after the opening hello |
| `discovery` | Call ended while telecaller was asking questions |
| `pitch` | Call ended while telecaller was presenting the project |
| `objection_handling` | Call ended while addressing lead's concerns |
| `close_attempt` | Telecaller attempted to close (site visit, callback) but call ended |
| `next_step_confirmed` | A concrete next step was agreed upon before call ended |

### 4. Next-Action Recommendation

Based on the call outcome, classify into **one** recommended next action:

| Action | When to recommend |
|--------|-------------------|
| `schedule_callback_3_days` | Lead showed interest but needs time / family discussion |
| `confirm_site_visit` | Site visit was verbally committed, needs confirmation |
| `escalate_to_manager` | Lead has specific demands or complaints beyond telecaller scope |
| `send_brochure_whatsapp` | Lead wants more info but isn't ready for a visit |
| `mark_cold` | Lead explicitly not interested or unreachable |
| `no_action` | Next step already confirmed and scheduled |

### 5. Call Summary

A **2-sentence summary** of the call capturing: what was discussed, what the outcome was, and any notable context.

### 6. Manager Console (UI)

A web-based dashboard. We care about **operator fit** (would a non-technical sales manager actually use this?) more than visual polish.

**Must-have:**

*List view:*
- All 150 calls displayed with columns: telecaller name, lead name, date, duration, overall score (average of 4 dimensions), site visit outcome, last stage, recommended action
- At least **2 of {filter, sort, search}** implemented well — pick the ones that feel most useful to a sales manager and make them work cleanly, rather than implementing all three hurriedly

*Detail view (click a call):*
- Full transcript displayed with timestamp formatting
- All extracted fields
- All 4 quality scores with reasons
- Last stage reached
- Recommended next action with reasoning
- Call summary

**Nice-to-have (not required but rewarded under UI/operator fit or stretch goals):**
- Full filter set: by telecaller, date range, score range, site visit outcome, recommended action
- Sort by any column
- Search by lead name or telecaller name
- Inline rubric legend / tooltips explaining what each 0–5 score means

### 7. Upload Flow

A section in the UI where a user can **paste or upload a new transcript** and get it processed through the full pipeline.

**Upload input format (you must support this exact schema):**

```
[00:00-00:05] Agent: Hello sir, Suresh here from Skyline Properties
[00:05-00:12] Lead: haan sollunga, ena vishayam?
[00:12-00:25] Agent: Sir, naanga Velachery-la oru puthusa 3BHK launch pannirukom...
```

Requirements:
- Accept plain text in the above format (timestamp-bracketed, speaker-tagged lines)
- Run the full pipeline: extraction + scoring + stage + next-action + summary
- Display results in the same detail view format
- Add the processed call to the main list view
- The upload input contains **only the transcript text** — no telecaller/lead metadata. You may auto-generate placeholder IDs (e.g., `UPLOAD_<timestamp>`) or ask the user to supply them. Document your choice in `DECISIONS.md`.

**Recommended upload request body** (our grader will POST to your upload endpoint using this shape as its primary attempt):

```json
{ "transcript": "[00:00-00:05] Agent: ...\n[00:05-00:12] Lead: ..." }
```

Our grader also tries `text`, `content`, and `call_transcript` as fallback keys, but supporting `transcript` first avoids any guessing.

---

## Worked Example

Here is one sample transcript with a *plausible* ground-truth output. Use it to calibrate the level of detail expected in `reason` fields and how the enum values map to real calls. **This is one valid interpretation, not the only one** — your rubric may produce slightly different scores and still be correct.

**Input:**

```
[00:00-00:04] Agent: Good morning sir, Lakshmi here from Pearl City Properties
[00:04-00:08] Lead: yes Lakshmi, sollunga
[00:08-00:18] Agent: Sir, naanga Siruseri-la oru pudhu 2BHK launch pannirukkom, starting 42 lakhs. Budget-la fit aagumaa?
[00:18-00:28] Lead: 2BHK-ah? rate okay thaan. But location konjam dooram. I work in Guindy actually
[00:28-00:38] Agent: Sir, Siruseri-la IT corridor close-a iruku. OMR via bus or car, 45 min to Guindy. Future-la metro varum
[00:38-00:48] Lead: hmm okay. Sqft evlo iruku? EMI approximately how much?
[00:48-00:58] Agent: Sir, 850 sqft carpet, 1010 built-up. 42L-ku 20% down, 20-year loan, monthly EMI around 28K
[00:58-01:10] Lead: okay. Ipo just exploring thaan. Marriage-ku later plan. Probably 6 months-la think pannuven
[01:10-01:20] Agent: Understood sir. I'll share brochure on WhatsApp. Can I follow up in 2 weeks?
[01:20-01:26] Lead: yes, send details. 2 weeks call pannunga
[01:26-01:32] Agent: Thank you sir, details vanthu paathunga. Vanakkam
```

**Plausible output:**

```json
{
  "extraction": {
    "unit_configuration": "2BHK",
    "budget_range": {"min_lakhs": 42, "max_lakhs": 42},
    "timeline": "6_to_12_months",
    "preferred_locations": [],
    "site_visit_outcome": "not_asked"
  },
  "quality_scores": {
    "discovery": {"score": 2, "reason": "Asked about budget fit and surfaced location as a concern; never probed family size, current living situation, or timeline (lead volunteered timeline)."},
    "pitch": {"score": 3, "reason": "Covered price, sqft, EMI estimate, and future metro connectivity. Missing amenities, builder credibility, and RERA status."},
    "objection_handling": {"score": 4, "reason": "Addressed the Guindy-distance concern with commute time and metro expansion argument — concrete and responsive."},
    "next_step": {"score": 3, "reason": "No site visit attempt (appropriate given 6-month timeline). Secured WhatsApp brochure share and 2-week callback."}
  },
  "last_stage_reached": "close_attempt",
  "recommended_next_action": "send_brochure_whatsapp",
  "summary": "Lead exploring 2BHK at Pearl City Siruseri (42L) as post-marriage home on a 6-month horizon. Declined visit; accepted brochure on WhatsApp with 2-week follow-up callback."
}
```

**Note on `preferred_locations`:** The lead never expressed a location *preference* — they only flagged Siruseri as "far from Guindy." Since Guindy is where the lead works (not where they want to buy), and Siruseri is the telecaller's offering (not the lead's ask), this field is `[]`. If the lead had said "I'm looking in OMR or Siruseri," we'd use `["OMR", "Siruseri"]`.

**Recommended upload response shape** (the grader accepts both this nested shape and a flat variant, but returning this shape keeps auto-grading deterministic):

```json
{
  "call_id": "UPLOAD_20260420T133000",
  "extraction": {
    "unit_configuration": "3BHK",
    "budget_range": {"min_lakhs": 55, "max_lakhs": 70},
    "timeline": "3_to_6_months",
    "preferred_locations": ["Sholinganallur"],
    "site_visit_outcome": "committed_with_date"
  },
  "quality_scores": {
    "discovery":          {"score": 4, "reason": "..."},
    "pitch":              {"score": 3, "reason": "..."},
    "objection_handling": {"score": 2, "reason": "..."},
    "next_step":          {"score": 4, "reason": "..."}
  },
  "last_stage_reached": "close_attempt",
  "recommended_next_action": "confirm_site_visit",
  "summary": "Two-sentence summary of what happened and what's next."
}
```

---

## Stretch Goals

Complete the base requirements first. Then pick any of these, ordered roughly from easier to harder:

- **S1 — Telecaller Leaderboard:** Aggregate scores per telecaller across all their calls. Rank the team. Surface top and bottom performer.
- **S2 — Edit + Recompute:** Let a manager edit an extracted field (e.g., change `site_visit_outcome` from `committed_no_date` to `declined`) and have the lead score and next-action recompute.
- **S3 — Eval Harness:** Write a script that runs your pipeline against a labeled test set and reports per-field accuracy. (We may provide a labeled set during evaluation.)
- **S4 — Cost + Latency Telemetry:** An `/admin` view showing total LLM calls made, estimated cost, and p50/p95 latency per call.
- **S5 — Caching + Idempotency:** Re-running the pipeline on an already-processed call returns cached results without making a new LLM call.
- **S6 — Bulk Actions:** Select multiple calls in the list view and perform a bulk action (e.g., "reassign all selected to telecaller X").

**How stretch goals are scored** (the 10% bucket):

| Well-done stretch goals | Score |
|-------------------------|-------|
| 0                       | 0/10  |
| 1                       | 4–5/10 |
| 2                       | 6–7/10 |
| 3                       | 8–9/10 |
| 4+                      | 10/10 |

"Well-done" means the feature **actually works on the deployed URL**, is integrated with the rest of the app, and is mentioned in `DECISIONS.md` or the README. A partially-working stretch goal counts as 0.5.

---

## Technical Requirements

### LLM Usage
- You may use **any LLM provider** — Gemini Flash (recommended for free tier), Groq, Together.ai, OpenAI, or self-hosted
- Budget your LLM calls: 150 transcripts × your pipeline = your total call count. Stay within free-tier limits
- **Document your provider choice, model, total call count, and estimated cost** in `AI_USAGE.md`

### AI Coding Tools
- You **may and should** use AI coding tools freely — Claude Code, Cursor, Copilot, ChatGPT, etc.
- **Document your usage honestly** in `AI_USAGE.md`: which tools you used, for which parts, what you accepted vs. rejected and why

### Stack
- No stack restrictions. Use whatever you're fastest with.
- We use FastAPI + Next.js + Supabase internally, but you will not be penalized for different choices.

### Deployment
- **Your app must be deployed to a public URL** — Vercel, Render, Railway, Fly.io, or any hosting
- The deployed version must have **all 150 calls pre-processed and visible** — the reviewer should see a populated dashboard immediately, not an empty state
- **The upload flow must work on the deployed version** — we will test it live

---

## Self-Check Before You Submit

Before hitting send, verify:

- [ ] Your deployed URL loads in an **incognito window** without a login or password wall
- [ ] The dashboard shows **all 150 calls** with extraction and scoring visible (not an empty state)
- [ ] The upload flow **accepts the exact input format** shown in Section 7 and returns a detail view
- [ ] Your GitHub repo is **private** and you've invited **`@kamal-zetta`** as a collaborator (Settings → Collaborators → Add people → `kamal-zetta`)
- [ ] README has a **one-command local setup** (e.g., `docker compose up` or `npm i && npm run dev`)
- [ ] `AI_USAGE.md` and `DECISIONS.md` exist and are not empty
- [ ] Your Loom is **unlisted or public** (not "private to account holder")
- [ ] Spot-check 3–5 random calls on your deployed app — do the extractions and scores actually make sense?

If any of these fail, fix before submitting. We don't chase broken submissions.

---

## What You Submit

1. **Deployed URL** — live, populated, no login wall
2. **GitHub repository** — **private**, with **`@kamal-zetta` invited as a collaborator** before you submit. Your README should include a one-command local setup.
3. **Loom video (3–5 minutes)** — walk through your deployed app, show the key flows, highlight what you're proud of
4. **`AI_USAGE.md`** — LLM provider details + AI coding tool usage documentation
5. **`DECISIONS.md`** — 5 key technical decisions you made, what alternatives you considered, and why you chose what you chose

**Templates to guide (not constrain) your documentation:**

`AI_USAGE.md` could cover:
- LLM provider + exact model used in the pipeline (e.g., `gemini-2.5-flash`)
- Total LLM calls made across the 150 transcripts + estimated cost (or "within free tier")
- AI coding tools used (Claude Code, Cursor, Copilot, ChatGPT, etc.) and roughly what % of code was AI-assisted
- One or two concrete examples of AI suggestions you **rejected** and why

`DECISIONS.md` could cover 5 decisions of this shape:
- **Decision:** e.g., "One LLM call per transcript returning all fields in a single JSON object"
- **Alternatives considered:** e.g., "Separate call per field group; chained calls with planner"
- **Why this:** e.g., "Cheaper in tokens, latency matters for the upload flow, accuracy degradation was <5% in my spot-checks"
- **What I'd change with more time:** one sentence

Keep both files short. We read them in 2 minutes — make them count.

**Submit by emailing your deployed URL, GitHub link, and Loom link to careers@zettatech.in with subject line: `[Take-Home] Your Name — Role`**

---

## How We Evaluate

| Criteria | Weight | What we look at |
|----------|--------|-----------------|
| **Deployment** | 10% | Does the URL work? Is data pre-seeded? No setup required? |
| **Extraction accuracy** | 15% | We will run your pipeline on transcripts you haven't seen. How accurate are your extractions? |
| **Scoring rubric quality** | 15% | Is your quality scoring rubric thoughtful? Do the 0–5 anchors make sense? Are the reasons insightful or generic? |
| **Upload flow** | 10% | Does uploading a new transcript work end-to-end on the deployed version? |
| **Code quality** | 10% | Readable, reasonable abstractions, not over-engineered, not a pasted mess |
| **UI / operator fit** | 10% | Would a non-technical sales manager find this usable? |
| **Stretch goals** | 10% | How many, how well |
| **Documentation** | 5% | AI_USAGE.md + DECISIONS.md quality |
| **Video walkthrough** | 5% | Can you explain what you built clearly in 3–5 minutes? |
| **Overall engineering judgment** | 10% | The intangible: does this feel like something a thoughtful engineer built, or something an LLM generated and a human deployed? |

---

## Important Notes

- **This is not a trick question.** We want to see how you build real software under realistic constraints. There are no hidden gotchas in the data.
- **Speed matters, but shipping matters more.** A deployed app with 80% of features working is better than a local repo with 100% of features.
- **Tamil-English code-switching is intentional.** The transcripts reflect real sales conversations in South India. Your pipeline should handle this gracefully.
- **How we measure accuracy:** we POST ~30 held-out transcripts (that you have never seen) through your deployed upload endpoint and score the response against our labels. Design your pipeline for *unseen input*, not for the 150 transcripts you were given.
- **We will also test your upload flow live** in Round 2 with 5 additional transcripts, while watching you walk through your code.
- **Document your AI usage honestly.** We expect you to use AI tools — this is how we work at Zetta. We evaluate *how* you use them, not *whether* you use them.
- **LLM call budget tip:** re-processing the 150 transcripts every time you tweak a prompt will burn free-tier quotas. Consider caching intermediate results locally during development.

---

## Questions?

Email careers@zettatech.in with subject `[Take-Home Question] Your Name`. We'll respond within 4 hours during business hours (10 AM – 7 PM IST).

---

*Zetta Technologies — AI-native CRM for real estate sales operations*  
*zettatech.in*
