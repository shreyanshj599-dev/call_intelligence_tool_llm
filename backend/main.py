"""FastAPI app — serves REST API + static frontend from a single service."""

from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import db
import pipeline
from rubric import rubric_as_json

ROOT = Path(__file__).parent.parent
FRONTEND = ROOT / "frontend"

app = FastAPI(title="Call Intelligence Tool")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

db.init()


class UploadBody(BaseModel):
    transcript: str | None = None
    text: str | None = None
    content: str | None = None
    call_transcript: str | None = None
    telecaller_name: str | None = None
    lead_name: str | None = None

    def pick_transcript(self) -> str:
        for key in ("transcript", "text", "content", "call_transcript"):
            v = getattr(self, key, None)
            if v and v.strip():
                return v.strip()
        return ""


class EditBody(BaseModel):
    field: str  # dotted: "extraction.site_visit_outcome" or "quality_scores.pitch.score"
    value: object


@app.get("/api/health")
def health():
    return {"status": "ok", "calls": db.total_calls()}


@app.get("/api/calls")
def list_calls():
    return {"calls": db.get_all()}


@app.get("/api/calls/{call_id}")
def get_call(call_id: str):
    row = db.get_one(call_id)
    if not row:
        raise HTTPException(404, "call not found")
    return row


@app.get("/api/leaderboard")
def leaderboard():
    return {"rows": db.leaderboard()}


@app.get("/api/rubric")
def get_rubric():
    return rubric_as_json()


@app.get("/api/admin/telemetry")
def telemetry():
    s = pipeline.STATS
    return {
        "llm_calls": s.calls,
        "errors": s.errors,
        "p50_ms": round(s.p(0.5), 0),
        "p95_ms": round(s.p(0.95), 0),
        "avg_ms": round(s.total_latency_ms / s.calls, 0) if s.calls else 0,
        "total_calls_in_db": db.total_calls(),
        "model": pipeline.MODEL_NAME,
        "estimated_cost_usd": 0.0,  # Gemini 2.0 Flash free tier
        "notes": "Running on Gemini free tier. Per-transcript cost ~$0 under free quota.",
    }


@app.post("/api/upload")
def upload(body: UploadBody):
    transcript = body.pick_transcript()
    if not transcript:
        raise HTTPException(400, "transcript is required (keys tried: transcript, text, content, call_transcript)")

    # Caching / idempotency (stretch S5): reuse result if same transcript already processed
    h = db.transcript_hash(transcript)
    cached = db.get_by_hash(h)
    if cached:
        analysis = json.loads(cached["analysis_json"])
        return {
            "call_id": cached["call_id"],
            "cached": True,
            **analysis,
        }

    analysis = pipeline.analyze_transcript(transcript)
    overall = pipeline.overall_score(analysis["quality_scores"])

    ts = dt.datetime.now(dt.timezone.utc).astimezone()
    call_id = f"UPLOAD_{ts.strftime('%Y%m%dT%H%M%S')}"
    duration = _estimate_duration_from_transcript(transcript)

    db.upsert_call(
        {
            "call_id": call_id,
            "telecaller_id": "UPLOAD",
            "telecaller_name": body.telecaller_name or "Uploaded",
            "lead_id": "UPLOAD",
            "lead_name": body.lead_name or "Uploaded Lead",
            "duration_sec": duration,
            "timestamp": ts.isoformat(),
            "transcript": transcript,
            "analysis_json": json.dumps(analysis),
            "overall_score": overall,
            "transcript_hash": h,
        }
    )

    return {"call_id": call_id, "cached": False, **analysis}


@app.post("/api/calls/{call_id}/edit")
def edit_call(call_id: str, body: EditBody):
    """Stretch S2: edit a field and recompute overall score + next-action fit."""
    row = db.get_one(call_id)
    if not row:
        raise HTTPException(404, "call not found")

    analysis = row["analysis"]
    keys = body.field.split(".")
    target = analysis
    for k in keys[:-1]:
        if k not in target:
            raise HTTPException(400, f"invalid field path: {body.field}")
        target = target[k]
    target[keys[-1]] = body.value

    overall = pipeline.overall_score(analysis["quality_scores"])
    db.update_analysis(call_id, analysis, overall)
    return {"call_id": call_id, "analysis": analysis, "overall_score": overall}


def _estimate_duration_from_transcript(text: str) -> int:
    """Pull the last [MM:SS-MM:SS] timestamp to estimate duration."""
    import re

    matches = re.findall(r"\[(\d+):(\d+)-(\d+):(\d+)\]", text)
    if not matches:
        return 0
    last = matches[-1]
    return int(last[2]) * 60 + int(last[3])


# ----- Static frontend -----

if FRONTEND.exists():
    @app.get("/")
    def root():
        return FileResponse(FRONTEND / "index.html")

    app.mount("/static", StaticFiles(directory=str(FRONTEND)), name="static")
