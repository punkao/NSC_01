#!/usr/bin/env python3
"""แปลง span (clean) -> granular point events ทุก ~2s (ให้หนาแน่นเหมือน mock เดิม
สำหรับ Event Timeline UI) โดย EXPAND แบบฉลาดต่อประเภท:
  - ต่อเนื่อง (sop/ppe/unauthorized/hygiene) -> point ทุก INTERVAL วินาทีตลอด span
  - ชั่วขณะ (near_miss) -> จุดเดียว (ห้ามสแปม critical alert)
ขยายจาก span ที่ clean แล้ว -> หนาแน่น + ถูกต้อง (ไม่เอา FP กลับมา).

Usage: python expand_granular.py <spans.json> <out_granular.json> [camera_id]
"""
import json
import sys
from pathlib import Path

INTERVAL = 2  # วินาที (เหมือน mock/GT)
MOMENTARY = {"near_miss"}  # ออกจุดเดียว
LABELS = {
    "sop_violation": "ทำงานข้ามขั้นตอน", "ppe_violation": "ไม่ใส่อุปกรณ์ PPE",
    "near_miss": "Near-Miss สายพานหนีบมือ", "unauthorized_person": "บุคคลอื่นเข้าพื้นที่",
    "hygiene_violation": "วางของไม่เกี่ยวข้อง",
}


def sec(v):
    p = str(v).split(":")
    return int(p[0]) * 60 + int(p[1]) if len(p) == 2 else int(p[0])


def mmss(s):
    return f"{s // 60:02d}:{s % 60:02d}"


src = sys.argv[1] if len(sys.argv) > 1 else "result_combined_final.json"
out = sys.argv[2] if len(sys.argv) > 2 else "cam_a05_ai_events.json"
cam = sys.argv[3] if len(sys.argv) > 3 else "CAM-A05"

spans = json.load(open(src, encoding="utf-8"))["events"]
events = []
for e in spans:
    et = e.get("event_type")
    s, en = sec(e.get("start", "00:00")), sec(e.get("end", e.get("start", "00:00")))
    desc = e.get("description_th") or e.get("description", "")
    times = [s] if et in MOMENTARY else list(range(s, en + 1, INTERVAL)) or [s]
    for t in times:
        events.append({
            "timestamp_mmss": mmss(t),
            "severity": e.get("severity", "medium"),
            "event_type": et,
            "event_type_label": LABELS.get(et, et),
            "description": desc,
        })
events.sort(key=lambda x: (x["timestamp_mmss"], x["event_type"]))

Path(out).write_text(json.dumps({"camera_id": cam, "replace": True, "events": events},
                                ensure_ascii=False, indent=2), encoding="utf-8")
by = {}
for e in events:
    by[e["event_type"]] = by.get(e["event_type"], 0) + 1
print(f"{len(spans)} spans -> {len(events)} granular events -> {out}")
print(f"  {by}")
