#!/usr/bin/env python3
"""Phase 2 — debounce raw per-frame signals (phase1_raw.json) into clean events.

Rule: a condition must hold for >= THRESHOLD consecutive sampled frames to become an
event (filters single-frame flicker). Emits event schema compatible with evaluate.py
and to_bulk_events.py.

Usage: python phase2_debounce.py <phase1_raw.json> <out.json> [threshold_frames]
"""
import json
import sys
from pathlib import Path

src = sys.argv[1] if len(sys.argv) > 1 else "phase1_raw.json"
out = sys.argv[2] if len(sys.argv) > 2 else "phase1_events.json"
THR = int(sys.argv[3]) if len(sys.argv) > 3 else 2

raw = json.loads(Path(src).read_text(encoding="utf-8"))
frames = raw["frames"]
secs = [f.get("sec", i) for i, f in enumerate(frames)]

TH_ITEM = {"cap": "หมวก", "gloves": "ถุงมือ", "mask": "หน้ากาก"}


def mmss(s):
    s = int(round(s))
    return f"{s//60:02d}:{s%60:02d}"


def runs(flags):
    """yield (i_start, i_end) index runs where flags[i] is True, length >= THR."""
    i = 0
    n = len(flags)
    while i < n:
        if flags[i]:
            j = i
            while j + 1 < n and flags[j + 1]:
                j += 1
            if (j - i + 1) >= THR:
                yield i, j
            i = j + 1
        else:
            i += 1


events = []

# ---- PPE per LINE worker (id 1/2 only — exclude visitors), same-worker+same-item ----
LINE_WORKERS = {"1", "2"}
for wid in sorted(LINE_WORKERS):
    # per-item boolean series (True = that item missing this frame)
    per_item = {it: [] for it in ("cap", "gloves", "mask")}
    for f in frames:
        w = next((x for x in (f.get("workers") or []) if str(x.get("id")) == wid), None)
        for it in per_item:
            per_item[it].append(bool(w) and not w.get(it))
    # keep an item as "missing" at frame i only if it is part of a >=THR run of that item
    stable = [set() for _ in frames]
    for it, series in per_item.items():
        for a, b in runs(series):
            for i in range(a, b + 1):
                stable[i].add(it)
    # worker event = consecutive frames with any stable-missing item (already per-item filtered)
    flags = [bool(s) for s in stable]
    i, n = 0, len(flags)
    while i < n:
        if not flags[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and flags[j + 1]:
            j += 1
        items = set().union(*stable[i:j + 1])
        named = [TH_ITEM[k] for k in ("cap", "gloves", "mask") if k in items]
        events.append({
            "start": mmss(secs[i]), "end": mmss(secs[j]),
            "event_type": "ppe_violation", "severity": "medium",
            "description_th": f"ผู้ปฏิบัติงานคนที่ {wid} ไม่สวม{'/'.join(named)}",
        })
        i = j + 1

# ---- unauthorized_person ----
for a, b in runs([bool(f.get("extra_person")) for f in frames]):
    events.append({"start": mmss(secs[a]), "end": mmss(secs[b]),
                   "event_type": "unauthorized_person", "severity": "low",
                   "description_th": "บุคคลอื่นที่ไม่ใช่พนักงานเข้ามาในพื้นที่ทำงาน"})

# ---- hygiene (foreign object) ----
for a, b in runs([bool(f.get("foreign_object")) for f in frames]):
    events.append({"start": mmss(secs[a]), "end": mmss(secs[b]),
                   "event_type": "hygiene_violation", "severity": "medium",
                   "description_th": "มีของไม่เกี่ยวข้อง (ขวดน้ำ) วางในพื้นที่ทำงาน"})

events.sort(key=lambda e: e["start"])
Path(out).write_text(json.dumps({"source": src, "threshold": THR, "events": events},
                                ensure_ascii=False, indent=2), encoding="utf-8")
print(f"threshold={THR} frames  ->  {len(events)} events -> {out}\n")
for e in events:
    print(f"  {e['start']}-{e['end']}  {e['event_type']:<20} {e['description_th']}")
