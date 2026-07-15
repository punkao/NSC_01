#!/usr/bin/env python3
"""Phase 5 — combine image-tier + video-tier events into one timeline, picking the
best source per event type (each tier's proven strength):
  - image tier  -> ppe_violation            (only the per-frame image pass sees PPE)
  - video tier  -> sop_violation, near_miss, unauthorized_person, hygiene_violation
                   (temporal context; better timing on person/hygiene)

Usage: python combine_tiers.py <image_events.json> <video_merged.json> <out.json>
"""
import json
import sys
from pathlib import Path

img_path = sys.argv[1] if len(sys.argv) > 1 else "ev2.json"
vid_path = sys.argv[2] if len(sys.argv) > 2 else "vid_merged.json"
out = sys.argv[3] if len(sys.argv) > 3 else "result_combined.json"

# image tier is now verified best for these (fine-grained, low FP); video tier only
# provides the temporal-motion events it alone can see.
IMAGE_TYPES = {"ppe_violation", "unauthorized_person", "hygiene_violation"}
VIDEO_TYPES = {"sop_violation", "near_miss"}


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8")).get("events", [])


def norm(e):
    return {
        "start": e.get("start"),
        "end": e.get("end", e.get("start")),
        "event_type": e.get("event_type"),
        "severity": e.get("severity", "medium"),
        "description_th": e.get("description_th") or e.get("description", ""),
    }


combined = [norm(e) for e in load(img_path) if e.get("event_type") in IMAGE_TYPES]
combined += [norm(e) for e in load(vid_path) if e.get("event_type") in VIDEO_TYPES]
combined.sort(key=lambda e: e["start"])

Path(out).write_text(json.dumps({"events": combined}, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"{len(combined)} combined events -> {out}\n")
for e in combined:
    src = "img" if e["event_type"] in IMAGE_TYPES else "vid"
    print(f"  [{src}] {e['start']}-{e['end']}  {e['event_type']:<20} {e['description_th'][:46]}")
