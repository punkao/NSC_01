#!/usr/bin/env python3
"""Phase 1 (RESEARCH_NEXT): Set-of-Mark grounding for SOP.

จุดอ่อนที่ verify แล้ว: Cosmos เดา SOP จากท่าทางกว้างๆ แยก "หยิบ NG (violation)" กับ "งานปกติ" ไม่ได้.
วิธี (SoM, no-train, VLM ยัง reason): กล้องนิ่ง -> วาดกรอบ+ป้ายกล่อง NG/WAIT/GOOD ตำแหน่งคงที่ลงเฟรม +
prompt เชิงพื้นที่ ให้ Cosmos บอก "หยิบจากกล่องไหน" ก่อนตัดสิน violation.

เทสต์: t=30 (ปกติ ควร violation=false), t=78/t=120 (violation ควร source_box=NG).
Run บน GPU box (Cosmos localhost:18000, detenv มี PIL). Usage: python som_sop_probe.py <frame> [...]
"""
import base64
import io
import json
import os
import re
import sys

import requests
from PIL import Image, ImageDraw

URL = "http://localhost:18000/v1/chat/completions"
# กล่องตำแหน่งคงที่ (กล้องนิ่ง), 1920x1080: (x0,y0,x1,y1,label,color)
BOXES = [
    (55, 840, 380, 1060, "NG", (255, 60, 60)),
    (180, 620, 520, 815, "WAIT", (255, 190, 0)),
    (1040, 790, 1530, 1060, "GOOD", (60, 200, 90)),
]
PROMPT = (
    "CCTV of a canning inspection line (static camera). Boxes are OUTLINED and LABELED in the "
    "image: NG (rejected cans), WAIT (cans awaiting inspection), GOOD (passed cans).\n"
    "Correct procedure: worker 1 (left) takes a can from WAIT, inspects it by eye; good -> conveyor, "
    "defective -> NG. VIOLATION = taking a can FROM the NG box and putting it on the conveyor "
    "(re-introducing a rejected can), OR placing on the conveyor with no visual inspection.\n"
    "Look at worker 1's hands. Reason step by step then answer JSON only:\n"
    '{"source_box":"NG"|"WAIT"|"none","placing_on_belt":true|false,"violation":true|false,"why":"<short thai>"}'
)


def draw(im: Image.Image) -> Image.Image:
    im = im.copy()
    d = ImageDraw.Draw(im)
    for x0, y0, x1, y1, lab, col in BOXES:
        d.rectangle([x0, y0, x1, y1], outline=col, width=6)
        d.rectangle([x0, y0 - 34, x0 + 90, y0], fill=col)
        d.text((x0 + 6, y0 - 30), lab, fill=(0, 0, 0))
    return im


def ask(im: Image.Image) -> dict:
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=92)
    b64 = base64.b64encode(buf.getvalue()).decode()
    payload = {"model": "cosmos", "messages": [{"role": "user", "content": [
        {"type": "text", "text": PROMPT},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}]}],
        "max_tokens": 600, "temperature": 0}
    r = requests.post(URL, json=payload, timeout=120)
    m = r.json()["choices"][0]["message"]
    reply = m.get("content") or m.get("reasoning_content") or m.get("reasoning") or ""
    mt = re.search(r"\{.*\}", reply, re.DOTALL)
    try:
        return json.loads(mt.group(0)) if mt else {"raw": reply[:120]}
    except (ValueError, TypeError):
        return {"raw": reply[:120]}


for fp in sys.argv[1:]:
    im = Image.open(fp).convert("RGB")
    print(f"\n=== {os.path.basename(fp)} ===")
    print("  ", ask(draw(im)))
