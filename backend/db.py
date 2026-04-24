"""SQLite storage for processed calls. Keeps schema tiny and portable."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(os.environ.get("DB_PATH", Path(__file__).parent.parent / "data" / "processed.db"))


SCHEMA = """
CREATE TABLE IF NOT EXISTS calls (
    call_id TEXT PRIMARY KEY,
    telecaller_id TEXT,
    telecaller_name TEXT,
    lead_id TEXT,
    lead_name TEXT,
    duration_sec INTEGER,
    timestamp TEXT,
    transcript TEXT,
    analysis_json TEXT,       -- validated pipeline output
    overall_score REAL,
    transcript_hash TEXT,     -- for idempotency / caching
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_calls_telecaller ON calls(telecaller_id);
CREATE INDEX IF NOT EXISTS idx_calls_timestamp ON calls(timestamp);
CREATE INDEX IF NOT EXISTS idx_calls_hash ON calls(transcript_hash);
"""


@contextmanager
def conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(DB_PATH))
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init():
    with conn() as c:
        c.executescript(SCHEMA)


def transcript_hash(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()[:32]


def upsert_call(row: dict):
    with conn() as c:
        c.execute(
            """
            INSERT INTO calls (call_id, telecaller_id, telecaller_name, lead_id, lead_name,
                               duration_sec, timestamp, transcript, analysis_json,
                               overall_score, transcript_hash)
            VALUES (:call_id, :telecaller_id, :telecaller_name, :lead_id, :lead_name,
                    :duration_sec, :timestamp, :transcript, :analysis_json,
                    :overall_score, :transcript_hash)
            ON CONFLICT(call_id) DO UPDATE SET
                analysis_json=excluded.analysis_json,
                overall_score=excluded.overall_score,
                transcript_hash=excluded.transcript_hash
            """,
            row,
        )


def get_by_hash(h: str):
    with conn() as c:
        r = c.execute("SELECT * FROM calls WHERE transcript_hash = ? LIMIT 1", (h,)).fetchone()
        return dict(r) if r else None


def get_all(limit: int = 500, search: str | None = None):
    """List calls, optionally filtered by a case-insensitive substring match
    against transcript body + telecaller_name + lead_name. Empty/None search
    returns all rows (up to limit)."""
    with conn() as c:
        if search and search.strip():
            like = f"%{search.strip().lower()}%"
            rows = c.execute(
                "SELECT call_id, telecaller_id, telecaller_name, lead_id, lead_name, "
                "duration_sec, timestamp, overall_score, analysis_json FROM calls "
                "WHERE LOWER(transcript) LIKE ? "
                "   OR LOWER(telecaller_name) LIKE ? "
                "   OR LOWER(lead_name) LIKE ? "
                "ORDER BY timestamp DESC LIMIT ?",
                (like, like, like, limit),
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT call_id, telecaller_id, telecaller_name, lead_id, lead_name, "
                "duration_sec, timestamp, overall_score, analysis_json FROM calls "
                "ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        a = json.loads(d.pop("analysis_json"))
        d["site_visit_outcome"] = a["extraction"]["site_visit_outcome"]
        d["last_stage_reached"] = a["last_stage_reached"]
        d["recommended_next_action"] = a["recommended_next_action"]
        d["unit_configuration"] = a["extraction"]["unit_configuration"]
        d["timeline"] = a["extraction"]["timeline"]
        # Per-dimension quality scores (enables per-dimension filtering on the frontend)
        qs = a.get("quality_scores", {})
        d["discovery_score"] = qs.get("discovery", {}).get("score", 0)
        d["pitch_score"] = qs.get("pitch", {}).get("score", 0)
        d["objection_handling_score"] = qs.get("objection_handling", {}).get("score", 0)
        d["next_step_score"] = qs.get("next_step", {}).get("score", 0)
        out.append(d)
    return out


def get_one(call_id: str):
    with conn() as c:
        r = c.execute("SELECT * FROM calls WHERE call_id = ?", (call_id,)).fetchone()
    if not r:
        return None
    d = dict(r)
    d["analysis"] = json.loads(d.pop("analysis_json"))
    return d


def update_analysis(call_id: str, analysis: dict, overall: float):
    with conn() as c:
        c.execute(
            "UPDATE calls SET analysis_json = ?, overall_score = ? WHERE call_id = ?",
            (json.dumps(analysis), overall, call_id),
        )


def leaderboard():
    with conn() as c:
        rows = c.execute(
            """
            SELECT telecaller_id, telecaller_name,
                   COUNT(*) as calls,
                   ROUND(AVG(overall_score), 2) as avg_score,
                   ROUND(MIN(overall_score), 2) as min_score,
                   ROUND(MAX(overall_score), 2) as max_score
            FROM calls
            GROUP BY telecaller_id, telecaller_name
            ORDER BY avg_score DESC
            """
        ).fetchall()
    return [dict(r) for r in rows]


def total_calls() -> int:
    with conn() as c:
        return c.execute("SELECT COUNT(*) FROM calls").fetchone()[0]
