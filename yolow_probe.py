#!/usr/bin/env python3
"""Viability probe for YOLO-World (open-vocab detector) on CAM-A05 frames.

Same role as gd_probe.py but YOLO-World is real-time-fast — the point is to see if
it counts people / localizes PPE as well as Grounding DINO but quick enough for live.

Usage: python yolow_probe.py <frame.jpg> [...]
"""
import sys
import time

from ultralytics import YOLO

CLASSES = ["person", "hard hat", "glove", "bare hand", "face mask", "bottle"]
CONF = 0.20

t0 = time.time()
model = YOLO("yolov8s-world.pt")
model.set_classes(CLASSES)
print(f"loaded yolov8s-world in {time.time()-t0:.1f}s")

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
