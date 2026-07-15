#!/usr/bin/env python3
"""Set-of-Mark probe: does feeding Cosmos a ZOOMED head crop (instead of the full
1080p frame) fix the mask/cap blind spot?

Rationale: claude_gt.json was built by cropping head+hands high-res -> a frontier VLM
read PPE per-hand accurately. Cosmos on the FULL frame misses the small mask. This
tests the missing step: crop each worker's head (static camera -> fixed regions) and
ask Cosmos on the zoom. If Cosmos-on-crop gets mask right where Cosmos-on-frame failed,
Set-of-Mark fixes PPE on-prem (no model change).

Run on the GPU box (Cosmos at localhost:18000). Usage: python som_probe.py <frame.jpg> [...]
"""
import base64
import io
import json
import re
import sys

import requests
from PIL import Image

URL = "http://localhost:18000/v1/chat/completions"
# static camera: worker 1 left, worker 2 right. Head-region crops (x0,y0,x1,y1).
CROPS = {"w1": (330, 90, 820, 410), "w2": (1090, 120, 1600, 450)}
PROMPT = (
    "Extreme close-up of ONE factory worker's head and upper body. Answer ONLY from "
    "what is clearly visible in THIS crop.\n"
    'JSON only: {"cap":true|false,"mask":true|false,"face_visible":true|false}\n'
    "cap = a cap/hat worn on the head.\n"
    "mask = a hygiene face mask worn COVERING the nose AND mouth. A mask pulled down to "
    "the chin or hanging on the neck = false.\n"
    "face_visible = is the nose/mouth area clearly shown in this crop."
)


def ask(img: Image.Image) -> dict:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    b64 = base64.b64encode(buf.getvalue()).decode()
    payload = {"model": "cosmos", "messages": [{"role": "user", "content": [
        {"type": "text", "text": PROMPT},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}]}],
        "max_tokens": 500, "temperature": 0}
    r = requests.post(URL, json=payload, timeout=120)
    m = r.json()["choices"][0]["message"]
    reply = m.get("content") or m.get("reasoning_content") or m.get("reasoning") or ""
    mt = re.search(r"\{.*\}", reply, re.DOTALL)
    try:
        return json.loads(mt.group(0)) if mt else {"raw": reply[:100]}
    except (ValueError, TypeError):
        return {"raw": reply[:100]}


for fp in sys.argv[1:]:
    im = Image.open(fp).convert("RGB")
    print(f"\n=== {fp} ===")
    for w, box in CROPS.items():
        print(f"  {w} {box}: {ask(im.crop(box))}")
