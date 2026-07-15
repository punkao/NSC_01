#!/usr/bin/env python3
"""
Score a model's detected events against the CAM-A05 ground-truth answer key.

Because the ground truth lists many repetitive point-events (e.g. an ongoing
sop_violation logged every ~2s), we first COLLAPSE consecutive same-type ground
truth events into segments, then check whether the model covered each segment at
the right time with the right event_type.

Metrics reported:
  - Recall  : ground-truth segments the model detected (the important one).
  - Precision: model events that landed on a real ground-truth segment.
  - Per-type breakdown + explicit near_miss (critical) check.
  - A time-only recall that ignores event_type (did the model flag *anything*
    at the right moment) so you can separate "wrong label" from "missed entirely".

Usage:
    python evaluate.py --pred result_cosmos.json --truth ground_truth_cam_a05.json
    python evaluate.py --pred result_cosmos.json --tolerance 4
"""
import argparse
import json
from pathlib import Path

# Map possible model event_type spellings onto our canonical taxonomy.
TYPE_SYNONYMS = {
    "sop_violation": "sop_violation",
    "sop": "sop_violation",
    "procedure_violation": "sop_violation",
    "ppe_violation": "ppe_violation",
    "ppe": "ppe_violation",
    "missing_ppe": "ppe_violation",
    "near_miss": "near_miss",
    "nearmiss": "near_miss",
    "near-miss": "near_miss",
    "unauthorized_person": "unauthorized_person",
    "intrusion": "unauthorized_person",
    "hygiene_violation": "hygiene_violation",
    "hygiene": "hygiene_violation",
}

MERGE_GAP_SEC = 12.0  # gap under which same-type GT events fuse into one segment


def mmss_to_sec(v: str) -> float:
    v = str(v).strip().replace(".", ":", v.count(":") == 0 and "." in v)
    parts = v.split(":")
    try:
        if len(parts) >= 2:
            return int(parts[0]) * 60 + float(parts[1])
        return float(parts[0])
    except ValueError:
        return 0.0


def norm_type(t: str | None) -> str:
    return TYPE_SYNONYMS.get((t or "").strip().lower(), (t or "").strip().lower())


def collapse_truth(events: list[dict]) -> list[dict]:
    """Fuse consecutive same-type ground-truth point events into segments."""
    segs: list[dict] = []
    for e in sorted(events, key=lambda x: x["timestamp_sec"]):
        t = norm_type(e["event_type"])
        sec = e["timestamp_sec"]
        if segs and segs[-1]["event_type"] == t and sec - segs[-1]["end"] <= MERGE_GAP_SEC:
            segs[-1]["end"] = sec
            segs[-1]["count"] += 1
        else:
            segs.append({"event_type": t, "start": sec, "end": sec, "count": 1,
                         "severity": e.get("severity"), "example": e.get("description", "")})
    return segs


def pred_events(pred: list[dict]) -> list[dict]:
    out = []
    for e in pred:
        s = mmss_to_sec(e.get("start", e.get("timestamp_mmss", "0:00")))
        en = mmss_to_sec(e.get("end", e.get("timestamp_end_mmss", e.get("start", e.get("timestamp_mmss", "0:00")))))
        out.append({"event_type": norm_type(e.get("event_type")),
                    "start": min(s, en), "end": max(s, en),
                    "severity": e.get("severity"),
                    "desc": e.get("description_th") or e.get("description", "")})
    return out


def overlaps(a_start, a_end, b_start, b_end, tol) -> bool:
    return a_start - tol <= b_end and b_start - tol <= a_end


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pred", required=True)
    ap.add_argument("--truth", default="ground_truth_cam_a05.json")
    ap.add_argument("--tolerance", type=float, default=4.0, help="seconds of slack")
    args = ap.parse_args()

    truth = json.loads(Path(args.truth).read_text(encoding="utf-8"))
    pred_raw = json.loads(Path(args.pred).read_text(encoding="utf-8"))
    preds = pred_events(pred_raw.get("events", []))
    segs = collapse_truth(truth["events"])
    tol = args.tolerance

    # ---- Recall: each GT segment detected? (type-aware and time-only) ----
    detected_typed = 0
    detected_timeonly = 0
    print("\n=== GROUND-TRUTH SEGMENTS ===")
    for s in segs:
        hit_typed = any(p["event_type"] == s["event_type"]
                        and overlaps(p["start"], p["end"], s["start"], s["end"], tol)
                        for p in preds)
        hit_time = any(overlaps(p["start"], p["end"], s["start"], s["end"], tol)
                       for p in preds)
        detected_typed += hit_typed
        detected_timeonly += hit_time
        mark = "OK " if hit_typed else ("~T " if hit_time else "MISS")
        span = f"{int(s['start'])//60:02d}:{int(s['start'])%60:02d}-{int(s['end'])//60:02d}:{int(s['end'])%60:02d}"
        print(f"  [{mark}] {s['event_type']:<20} {span}  (x{s['count']})")

    # ---- Precision: each model event lands on a real segment? ----
    tp = sum(1 for p in preds
             if any(p["event_type"] == s["event_type"]
                    and overlaps(p["start"], p["end"], s["start"], s["end"], tol)
                    for s in segs))
    precision = tp / len(preds) if preds else 0.0
    recall = detected_typed / len(segs) if segs else 0.0
    recall_time = detected_timeonly / len(segs) if segs else 0.0

    # ---- Per-type recall ----
    types = sorted({s["event_type"] for s in segs})
    print("\n=== PER-TYPE RECALL (type-aware) ===")
    for t in types:
        tsegs = [s for s in segs if s["event_type"] == t]
        got = sum(1 for s in tsegs
                  if any(p["event_type"] == t
                         and overlaps(p["start"], p["end"], s["start"], s["end"], tol)
                         for p in preds))
        print(f"  {t:<20} {got}/{len(tsegs)}")

    # ---- The money event: the critical near-miss ----
    nm = [s for s in segs if s["event_type"] == "near_miss"]
    if nm:
        s = nm[0]
        hit = any(p["event_type"] == "near_miss"
                  and overlaps(p["start"], p["end"], s["start"], s["end"], tol)
                  for p in preds)
        print(f"\n=== CRITICAL NEAR-MISS @ {int(s['start'])//60:02d}:{int(s['start'])%60:02d} ===")
        print("  DETECTED" if hit else "  *** MISSED — this is the most important event ***")

    print("\n=== SUMMARY ===")
    print(f"  GT segments        : {len(segs)}")
    print(f"  Model events       : {len(preds)}")
    print(f"  Recall  (type)     : {recall:.0%}  ({detected_typed}/{len(segs)})")
    print(f"  Recall  (time-only): {recall_time:.0%}  ({detected_timeonly}/{len(segs)})")
    print(f"  Precision (type)   : {precision:.0%}  ({tp}/{len(preds)})")


if __name__ == "__main__":
    main()
