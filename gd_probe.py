#!/usr/bin/env python3
"""Viability probe for Grounding DINO (zero-shot detector) on CAM-A05 CCTV frames.

Goal: before building a GD->VLM pointer pipeline, check whether GD can even localize
the safety-relevant objects (person / hard hat / glove / bare hand / mask / bottle) on
this grainy factory footage. Runs on CPU (no VRAM contention with Cosmos).

Usage: python gd_probe.py <frame.jpg> [<frame.jpg> ...]
"""
import sys
import time

import torch
from PIL import Image
from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor

MODEL_ID = "IDEA-Research/grounding-dino-tiny"
LABELS = ["person", "hard hat", "glove", "bare hand", "face mask", "bottle"]
BOX_THR, TEXT_THR = 0.25, 0.20

t0 = time.time()
proc = AutoProcessor.from_pretrained(MODEL_ID)
model = AutoModelForZeroShotObjectDetection.from_pretrained(MODEL_ID).to("cpu").eval()
print(f"loaded {MODEL_ID} on cpu in {time.time()-t0:.1f}s")
text = ". ".join(LABELS) + "."


def detect(fp: str) -> None:
    img = Image.open(fp).convert("RGB")
    inputs = proc(images=img, text=text, return_tensors="pt")
    t = time.time()
    with torch.no_grad():
        out = model(**inputs)
    sizes = [img.size[::-1]]
    try:  # transformers 5.x signature
        res = proc.post_process_grounded_object_detection(
            out, threshold=BOX_THR, text_threshold=TEXT_THR, target_sizes=sizes)[0]
    except TypeError:  # older signature
        res = proc.post_process_grounded_object_detection(
            out, inputs.input_ids, box_threshold=BOX_THR, text_threshold=TEXT_THR,
            target_sizes=sizes)[0]
    labels = res.get("text_labels", res.get("labels"))
    print(f"\n=== {fp}  ({img.size[0]}x{img.size[1]})  infer {time.time()-t:.1f}s ===")
    if not len(res["scores"]):
        print("  (no detections)")
    for lab, score, box in sorted(zip(labels, res["scores"], res["boxes"]),
                                  key=lambda z: -float(z[1])):
        b = [round(float(x)) for x in box.tolist()]
        print(f"  {str(lab):<12} {float(score):.2f}  box={b}")


for f in sys.argv[1:]:
    detect(f)
