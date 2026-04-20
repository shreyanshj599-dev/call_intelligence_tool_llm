"""
Pre-process all 150 calls from calls.jsonl through the pipeline.

Usage:
    python backend/seed.py                # process calls not yet in DB
    python backend/seed.py --force        # reprocess everything
    python backend/seed.py --limit 10     # smoke test on first 10

Respects Groq (primary) / Gemini (fallback) free-tier rate limits with a tiny sleep between calls.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import db
import pipeline

DATA = Path(__file__).parent.parent / "data" / "calls.jsonl"


def already_processed(call_id: str) -> bool:
    return db.get_one(call_id) is not None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--sleep", type=float, default=0.5, help="sec between calls (RPM budget)")
    args = parser.parse_args()

    db.init()

    rows = [json.loads(l) for l in DATA.read_text().splitlines() if l.strip()]
    if args.limit:
        rows = rows[: args.limit]

    ok = fail = skipped = 0
    t0 = time.time()
    for i, row in enumerate(rows, 1):
        cid = row["call_id"]
        if not args.force and already_processed(cid):
            skipped += 1
            continue

        try:
            analysis = pipeline.analyze_transcript(row["transcript"])
            overall = pipeline.overall_score(analysis["quality_scores"])
            db.upsert_call(
                {
                    "call_id": cid,
                    "telecaller_id": row["telecaller_id"],
                    "telecaller_name": row["telecaller_name"],
                    "lead_id": row["lead_id"],
                    "lead_name": row["lead_name"],
                    "duration_sec": row["duration_sec"],
                    "timestamp": row["timestamp"],
                    "transcript": row["transcript"],
                    "analysis_json": json.dumps(analysis),
                    "overall_score": overall,
                    "transcript_hash": db.transcript_hash(row["transcript"]),
                }
            )
            ok += 1
            print(f"[{i:3}/{len(rows)}] {cid} ok  overall={overall}")
        except Exception as e:  # noqa: BLE001
            fail += 1
            print(f"[{i:3}/{len(rows)}] {cid} FAIL  {e}", file=sys.stderr)

        time.sleep(args.sleep)

    dt = time.time() - t0
    print(f"\nDone. ok={ok} fail={fail} skipped={skipped} in {dt:.1f}s")


if __name__ == "__main__":
    main()
