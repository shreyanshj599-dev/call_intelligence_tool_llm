"""
Call Intelligence pipeline: single LLM call per transcript returning all fields.

Supports two providers, auto-selected by env vars:
  * Groq (preferred if GROQ_API_KEY is set) — OpenAI-compatible API, fast + free tier
  * Gemini (fallback) — Google AI Studio

Design decisions (documented in DECISIONS.md):
  * One LLM call per transcript returning structured JSON — cheaper in tokens
    and faster than chained calls, with minimal accuracy hit in spot-checks.
  * JSON is validated and coerced against enums after the call; invalid values
    fall back to safe defaults rather than erroring out.
  * Prompt includes the full rubric so scoring is consistent with the UI legend.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field

from rubric import rubric_as_prompt_block

# ----- Provider selection -----

PROVIDER = os.environ.get("LLM_PROVIDER", "").lower().strip()
if not PROVIDER:
    PROVIDER = "groq" if os.environ.get("GROQ_API_KEY") else "gemini"

if PROVIDER == "groq":
    from openai import OpenAI

    MODEL_NAME = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
    API_KEY = os.environ.get("GROQ_API_KEY", "")
    _groq_client = OpenAI(api_key=API_KEY, base_url="https://api.groq.com/openai/v1") if API_KEY else None
else:
    import google.generativeai as genai

    MODEL_NAME = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")
    API_KEY = os.environ.get("GEMINI_API_KEY", "")
    if API_KEY:
        genai.configure(api_key=API_KEY)

# ----- Enum definitions (mirror TAKEHOME.md) -----

UNIT_CONFIGS = {"2BHK", "3BHK", "4BHK", "villa", "plot", "not_discussed"}
TIMELINES = {"immediate", "3_to_6_months", "6_to_12_months", "exploring", "unclear"}
SITE_VISIT_OUTCOMES = {
    "committed_with_date",
    "committed_no_date",
    "declined",
    "not_asked",
    "call_cut",
}
LAST_STAGES = {
    "greeting",
    "discovery",
    "pitch",
    "objection_handling",
    "close_attempt",
    "next_step_confirmed",
}
ACTIONS = {
    "schedule_callback_3_days",
    "confirm_site_visit",
    "escalate_to_manager",
    "send_brochure_whatsapp",
    "mark_cold",
    "no_action",
}

# ----- Telemetry -----


@dataclass
class PipelineStats:
    calls: int = 0
    total_latency_ms: float = 0.0
    latencies_ms: list = field(default_factory=list)
    errors: int = 0

    def record(self, ms: float):
        self.calls += 1
        self.total_latency_ms += ms
        self.latencies_ms.append(ms)

    def p(self, q: float) -> float:
        if not self.latencies_ms:
            return 0.0
        s = sorted(self.latencies_ms)
        idx = min(int(q * len(s)), len(s) - 1)
        return s[idx]


STATS = PipelineStats()


# ----- Prompt -----


SYSTEM_PROMPT = f"""You are an AI assistant analyzing Tamil-English code-switched real estate
sales call transcripts. Telecallers and leads mix Tamil, English, and Tamil-written-in-English
(e.g., "vanakkam", "sollunga", "veedu", "irukku") naturally.

For the transcript provided, return a SINGLE valid JSON object matching the exact schema below.
Do not wrap in markdown fences. Do not add commentary.

---
SCHEMA
---
{{
  "extraction": {{
    "unit_configuration": "2BHK" | "3BHK" | "4BHK" | "villa" | "plot" | "not_discussed",
    "budget_range": {{"min_lakhs": number, "max_lakhs": number}} | "not_discussed",
    "timeline": "immediate" | "3_to_6_months" | "6_to_12_months" | "exploring" | "unclear",
    "preferred_locations": [string, ...],
    "site_visit_outcome": "committed_with_date" | "committed_no_date" | "declined" | "not_asked" | "call_cut"
  }},
  "quality_scores": {{
    "discovery":          {{"score": 0-5, "reason": "one concrete sentence citing transcript evidence"}},
    "pitch":              {{"score": 0-5, "reason": "one concrete sentence citing transcript evidence"}},
    "objection_handling": {{"score": 0-5, "reason": "one concrete sentence citing transcript evidence"}},
    "next_step":          {{"score": 0-5, "reason": "one concrete sentence citing transcript evidence"}}
  }},
  "last_stage_reached": "greeting" | "discovery" | "pitch" | "objection_handling" | "close_attempt" | "next_step_confirmed",
  "recommended_next_action": "schedule_callback_3_days" | "confirm_site_visit" | "escalate_to_manager" | "send_brochure_whatsapp" | "mark_cold" | "no_action",
  "next_action_reason": "one sentence explaining why this action fits the call outcome",
  "summary": "exactly two sentences summarizing what was discussed and the outcome"
}}

---
FIELD SEMANTICS
---
- budget_range: Use the lead's stated range. If the lead engaged with the telecaller's
  quoted price without pushback, infer that as the range. Otherwise "not_discussed".
- preferred_locations: ONLY locations the LEAD expressed preference for. Not locations
  mentioned by the telecaller unless the lead agreed. Can contain multiple entries.
  If the lead only mentioned where they WORK (not where they want to buy), do not include.
- site_visit_outcome: state at call-end. A soft "I'll let you know" = committed_no_date OR declined.
- timeline: only use "unclear" when no timeline signal exists at all.
- last_stage_reached: the LAST stage the call reached before ending.
- next_step_confirmed vs close_attempt: "confirmed" requires an explicit lead agreement.
- reasons must cite concrete transcript evidence ("asked about budget and timeline but
  skipped family size"), not generic praise.

---
RUBRIC (use these anchors exactly)
---
{rubric_as_prompt_block()}

---
INSTRUCTIONS
---
1. Read the transcript carefully. Tamil words written in English are common — interpret the meaning.
2. Fill every field. Missing fields break downstream systems.
3. Reasons must be specific and cite evidence.
4. If the call ended abruptly ([call ended] or similar), set last_stage_reached accordingly
   and site_visit_outcome to "call_cut" if no visit was discussed.
5. Return ONE JSON object only. No markdown fences, no preamble.
"""


# ----- Helpers -----


def _extract_json(text: str) -> dict:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object found in LLM response")
    return json.loads(text[start : end + 1])


def _coerce_enum(value, allowed: set, default: str) -> str:
    if isinstance(value, str) and value in allowed:
        return value
    if isinstance(value, str):
        v = value.strip()
        if v in allowed:
            return v
    return default


def _coerce_score(value) -> int:
    try:
        s = int(round(float(value)))
    except Exception:
        return 0
    return max(0, min(5, s))


def _coerce_budget(value):
    if value == "not_discussed" or value is None:
        return "not_discussed"
    if isinstance(value, dict):
        try:
            lo = float(value.get("min_lakhs", 0))
            hi = float(value.get("max_lakhs", lo))
            if lo <= 0 and hi <= 0:
                return "not_discussed"
            if hi < lo:
                lo, hi = hi, lo
            return {"min_lakhs": lo, "max_lakhs": hi}
        except Exception:
            return "not_discussed"
    return "not_discussed"


def _validate(obj: dict) -> dict:
    extraction = obj.get("extraction", {}) or {}
    quality = obj.get("quality_scores", {}) or {}

    def _qs(name):
        q = quality.get(name, {}) or {}
        return {
            "score": _coerce_score(q.get("score", 0)),
            "reason": str(q.get("reason") or "")[:400],
        }

    return {
        "extraction": {
            "unit_configuration": _coerce_enum(
                extraction.get("unit_configuration"), UNIT_CONFIGS, "not_discussed"
            ),
            "budget_range": _coerce_budget(extraction.get("budget_range")),
            "timeline": _coerce_enum(extraction.get("timeline"), TIMELINES, "unclear"),
            "preferred_locations": [
                str(x).strip()
                for x in (extraction.get("preferred_locations") or [])
                if str(x).strip()
            ],
            "site_visit_outcome": _coerce_enum(
                extraction.get("site_visit_outcome"), SITE_VISIT_OUTCOMES, "not_asked"
            ),
        },
        "quality_scores": {
            "discovery": _qs("discovery"),
            "pitch": _qs("pitch"),
            "objection_handling": _qs("objection_handling"),
            "next_step": _qs("next_step"),
        },
        "last_stage_reached": _coerce_enum(
            obj.get("last_stage_reached"), LAST_STAGES, "greeting"
        ),
        "recommended_next_action": _coerce_enum(
            obj.get("recommended_next_action"), ACTIONS, "no_action"
        ),
        "next_action_reason": str(obj.get("next_action_reason") or "")[:400],
        "summary": str(obj.get("summary") or "")[:600],
    }


# ----- Public API -----


def _call_llm(transcript: str) -> str:
    if PROVIDER == "groq":
        if not _groq_client:
            raise RuntimeError("GROQ_API_KEY not set.")
        resp = _groq_client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": transcript},
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        return resp.choices[0].message.content
    else:
        if not API_KEY:
            raise RuntimeError("GEMINI_API_KEY not set.")
        model = genai.GenerativeModel(
            MODEL_NAME,
            system_instruction=SYSTEM_PROMPT,
            generation_config={
                "temperature": 0.1,
                "response_mime_type": "application/json",
            },
        )
        return model.generate_content(transcript).text


def analyze_transcript(transcript: str, *, retries: int = 2) -> dict:
    last_err = None
    for attempt in range(retries + 1):
        t0 = time.time()
        try:
            text = _call_llm(transcript)
            latency_ms = (time.time() - t0) * 1000
            STATS.record(latency_ms)
            data = _extract_json(text)
            return _validate(data)
        except Exception as e:  # noqa: BLE001
            last_err = e
            STATS.errors += 1
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
            continue

    raise RuntimeError(f"Pipeline failed after {retries + 1} attempts: {last_err}")


def overall_score(quality_scores: dict) -> float:
    vals = [quality_scores[k]["score"] for k in ("discovery", "pitch", "objection_handling", "next_step")]
    return round(sum(vals) / 4.0, 2)