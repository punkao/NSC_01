#!/usr/bin/env python3
"""Convert a model result (start/end/event_type/severity/description_th) into the
EXACT schema the frontend/mock uses (POST /api/events/bulk) so it drives the same
video-synced Event Timeline as the hand-written mock.

Usage: python to_bulk_events.py <result.json> <out.json> [camera_id]
"""
import json
import sys
from pathlib import Path

# same Thai labels the mock uses (event_type -> event_type_label)
LABELS = {
    "sop_violation": "ทำงานข้ามขั้นตอน",
    "ppe_violation": "ไม่ใส่อุปกรณ์ PPE",
    "near_miss": "Near-Miss สายพานหนีบมือ",
    "unauthorized_person": "บุคคลอื่นเข้าพื้นที่",
    "hygiene_violation": "วางของไม่เกี่ยวข้อง",
    "falling_object": "ของตก/กระป๋องหล่น",
}

src = sys.argv[1] if len(sys.argv) > 1 else "result_cosmos_chunked.json"
out = sys.argv[2] if len(sys.argv) > 2 else "cam_a05_ai_events.json"
cam = sys.argv[3] if len(sys.argv) > 3 else "CAM-A05"

d = json.loads(Path(src).read_text(encoding="utf-8"))
events = []
for e in d.get("events", []):
    et = e.get("event_type", "observation")
    events.append({
        "timestamp_mmss": e.get("start", "00:00"),
        # keep the span end so multi-frame events (near_miss / sop spans) survive to
        # the timeline instead of collapsing to a point — the frontend fires on start
        # and can show duration; scoring keeps the full overlap window.
        "timestamp_end_mmss": e.get("end", e.get("start", "00:00")),
        "severity": e.get("severity", "medium"),
        "event_type": et,
        "event_type_label": LABELS.get(et, et),
        "description": e.get("description_th") or e.get("description", ""),
    })

payload = {"camera_id": cam, "replace": True, "events": events}
Path(out).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"{len(events)} events -> {out}  (schema = /api/events/bulk, same as mock)\n")
print(f"{'TIME':<6} {'SEVERITY':<9} {'EVENT_TYPE':<20} DESCRIPTION (TH)")
print("-" * 90)
for ev in events:
    print(f"{ev['timestamp_mmss']:<6} {ev['severity']:<9} {ev['event_type']:<20} {ev['description'][:52]}")
