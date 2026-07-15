#!/usr/bin/env python3
"""Combine Track A (video temporal events, already merged) + Track B (PPE from the
per-frame image pass, debounced) into ONE timeline JSON — the full 5-type result
that drives the demo. Track B PPE frames are clustered by temporal persistence so a
sustained missing-PPE condition becomes one event and single-frame flickers drop.

Usage: python merge_ab.py <trackA_merged.json> <ppe_batch_result.json> <out.json>
"""
import json
import sys
from pathlib import Path

CLUSTER_GAP = 16     # s: flagged PPE frames within this fuse into one event
MIN_RUN = 2          # frames a PPE condition must persist to count (debounce)

a_path, b_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]


def mmss(s):
    s = int(round(s)); return f"{s//60:02d}:{s%60:02d}"


# ---- Track A: temporal events (keep as-is) ----
a = json.loads(Path(a_path).read_text(encoding="utf-8"))
events = list(a.get("events", []))

# ---- Track B: debounce the per-frame PPE flags into sustained events ----
b = json.loads(Path(b_path).read_text(encoding="utf-8"))
flagged = [x for x in sorted(b, key=lambda x: x["t"]) if x.get("ppe_violation")]
runs = []
for x in flagged:
    if runs and x["t"] - runs[-1][-1]["t"] <= CLUSTER_GAP:
        runs[-1].append(x)
    else:
        runs.append([x])

ppe_events = []
for r in runs:
    if len(r) < MIN_RUN:
        continue                       # drop single-frame flickers
    s, e = r[0]["t"], r[-1]["t"]
    ppe_events.append({
        "start": mmss(s), "end": mmss(e),
        "event_type": "ppe_violation", "severity": "medium",
        "description_th": r[-1].get("note", "ไม่สวมอุปกรณ์ PPE ครบ"),
        "reason": "ตรวจพบผู้ปฏิบัติงานไม่สวม PPE ครบต่อเนื่อง (image pass)",
        "source": "trackB_ppe",
    })

events.extend(ppe_events)
events.sort(key=lambda e: int(e["start"].split(":")[0]) * 60 + int(e["start"].split(":")[1]))

res = {"model": "cosmos", "method": "trackA_video + trackB_ppe (merged)",
       "events": events}
Path(out_path).write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Track A: {len(a.get('events', []))} events + Track B PPE: {len(ppe_events)} events "
      f"-> {len(events)} total -> {out_path}")
for e in events:
    print(f"  {e['start']:>5}  {e['event_type']:<20} {e.get('severity','')}")
