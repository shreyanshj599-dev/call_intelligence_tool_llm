"""
Eval harness (stretch S3).

Runs the pipeline against a labeled test set (JSONL with one `{..., "label": {...}}`
entry per line) and reports per-field accuracy. Useful during development and as
proof of rubric stability.

Usage:
    python backend/eval.py --labels data/labels.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pipeline


def field_eq(pred, gold):
    if isinstance(gold, list):
        return sorted([s.lower() for s in (pred or [])]) == sorted([s.lower() for s in gold])
    if isinstance(gold, dict):
        return pred == gold
    return pred == gold


def score_accuracy(labels_path: Path):
    lines = [l for l in labels_path.read_text().splitlines() if l.strip()]
    rows = [json.loads(l) for l in lines]
    print(f"Loaded {len(rows)} labeled examples")

    field_correct = {
        "unit_configuration": 0,
        "budget_range": 0,
        "timeline": 0,
        "preferred_locations": 0,
        "site_visit_outcome": 0,
        "last_stage_reached": 0,
        "recommended_next_action": 0,
    }
    total = 0

    # Scoring dims: within ±1 counts as "adjacent" (matches grader policy)
    dim_exact = {k: 0 for k in ("discovery", "pitch", "objection_handling", "next_step")}
    dim_adjacent = {k: 0 for k in dim_exact}

    for r in rows:
        try:
            out = pipeline.analyze_transcript(r["transcript"])
        except Exception as e:  # noqa: BLE001
            print(f"FAIL {r.get('call_id')}: {e}", file=sys.stderr)
            continue

        gold = r["label"]
        total += 1
        ex = out["extraction"]
        gx = gold.get("extraction", {})

        for f in ("unit_configuration", "timeline", "site_visit_outcome"):
            if field_eq(ex.get(f), gx.get(f)):
                field_correct[f] += 1
        if field_eq(ex.get("preferred_locations"), gx.get("preferred_locations", [])):
            field_correct["preferred_locations"] += 1
        if field_eq(ex.get("budget_range"), gx.get("budget_range")):
            field_correct["budget_range"] += 1

        for f in ("last_stage_reached", "recommended_next_action"):
            if field_eq(out.get(f), gold.get(f)):
                field_correct[f] += 1

        for k in dim_exact:
            g = gold.get("quality_scores", {}).get(k, {}).get("score")
            p = out["quality_scores"][k]["score"]
            if g is None:
                continue
            if p == g:
                dim_exact[k] += 1
            if abs(p - g) <= 1:
                dim_adjacent[k] += 1

    print(f"\nEvaluated {total} transcripts")
    print("\n-- Field accuracy --")
    for f, c in field_correct.items():
        print(f"  {f:28s} {c}/{total}  ({100*c/total:.1f}%)")

    print("\n-- Scoring accuracy (exact / within ±1) --")
    for k in dim_exact:
        print(f"  {k:20s} exact={dim_exact[k]}/{total}  adj={dim_adjacent[k]}/{total}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", required=True, type=Path)
    args = ap.parse_args()
    score_accuracy(args.labels)


if __name__ == "__main__":
    main()
