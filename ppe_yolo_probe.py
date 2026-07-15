#!/usr/bin/env python3
"""Viability probe for a PRETRAINED PPE-YOLO (not trained by us) on CAM-A05 frames.

keremberke/yolov8m-protective-equipment-detection detects: glove, goggles, helmet,
mask, no_glove, no_goggles, no_helmet, no_mask, no_shoes, shoes — i.e. it has the
explicit worn/not-worn distinction VLM+GD both struggle with. The question: does a
model trained on (mostly construction) PPE transfer to this canning line (cloth cap,
cloth gloves, hygiene mask)?

Usage: python ppe_yolo_probe.py <frame.jpg> [...]
"""
import sys
import time

from huggingface_hub import hf_hub_download
from ultralytics import YOLO

REPO = "keremberke/yolov8m-protective-equipment-detection"
CONF = 0.20

t0 = time.time()
weights = hf_hub_download(REPO, "best.pt")
model = YOLO(weights)
print(f"loaded {REPO} in {time.time()-t0:.1f}s")
print("classes:", model.names)

for fp in sys.argv[1:]:
    t = time.time()
    r = model.predict(fp, conf=CONF, verbose=False)[0]
    dt = time.time() - t
    print(f"\n=== {fp}  infer {dt*1000:.0f}ms ===")
    names = r.names
    dets = sorted(
        [(names[int(c)], float(s), [round(float(x)) for x in b])
         for c, s, b in zip(r.boxes.cls, r.boxes.conf, r.boxes.xyxy)],
        key=lambda z: -z[1])
    if not dets:
        print("  (no detections)")
    for lab, score, box in dets:
        print(f"  {lab:<12} {score:.2f}  box={box}")
