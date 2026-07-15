#!/usr/bin/env python3
"""Post-process a chunked inference result: merge consecutive same-type events that
are close in time into a single spanning event. The per-chunk model cannot see
across chunk boundaries, so it re-reports the same ongoing condition every chunk
(e.g. repeated sop_violation). Merging them into one event per span matches how the
ground truth is scored and lifts precision without dropping any detection.

Usage: python merge_events.py <in_json> <out_json> [gap_seconds]
"""
import json
import sys
from pathlib import Path

inp = sys.argv[1]
out = sys.argv[2]
gap = float(sys.argv[3]) if len(sys.argv) > 3 else 20.0

SEV_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def mmss_to_sec(v) -> float:
    p = str(v).strip().split(":")
    try:
        return int(p[0]) * 60 + float(p[1]) if len(p) >= 2 else float(p[0])
    except ValueError:
        return 0.0


def sec_to_mmss(s: float) -> str:
    s = max(0, int(round(s)))
    return f"{s // 60:02d}:{s % 60:02d}"


data = json.loads(Path(inp).read_text(encoding="utf-8"))
events = data.get("events", [])
for e in events:
    e["_s"] = mmss_to_sec(e.get("start", "0:00"))
    e["_e"] = max(mmss_to_sec(e.get("end", e.get("start", "0:00"))), mmss_to_sec(e.get("start", "0:00")))

events.sort(key=lambda e: (e.get("event_type", ""), e["_s"]))

merged: list[dict] = []
for e in events:
    prev = merged[-1] if merged else None
    if (prev and prev.get("event_type") == e.get("event_type")
            and e["_s"] - prev["_e"] <= gap):
        # extend the span; keep the most severe/among-first description
        prev["_e"] = max(prev["_e"], e["_e"])
        if SEV_RANK.get(e.get("severity"), 0) > SEV_RANK.get(prev.get("severity"), 0):
            prev["severity"] = e.get("severity")
        prev["_merged"] = prev.get("_merged", 1) + 1
    else:
        merged.append(dict(e))

for m in merged:
    m["start"] = sec_to_mmss(m["_s"])
    m["end"] = sec_to_mmss(m["_e"])
    for k in ("_s", "_e"):
        m.pop(k, None)

merged.sort(key=lambda e: mmss_to_sec(e["start"]))
data["events"] = merged
data["method"] = data.get("method", "") + f"+merged{int(gap)}s"
Path(out).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"{len(events)} events -> {len(merged)} merged (gap {gap:.0f}s) -> {out}")
