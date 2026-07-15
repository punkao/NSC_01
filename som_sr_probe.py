#!/usr/bin/env python3
"""Super-resolution probe: does upscaling the head crop before Cosmos fix the mask
blind spot (Cosmos said face_visible=false on plain crops)?

Careful design (per holistic rule): test BOTH mask-off frames (should now be caught)
AND mask-on frames (must NOT gain false positives), and print cap alongside mask so a
regression on cap is visible. Compares plain-crop vs SR-crop side by side.

Run on the GPU box (Cosmos at localhost:18000). Usage: python som_sr_probe.py <frame> [...]
"""
import base64
import io
import json
import re
import sys

import requests
from PIL import Image
from super_image import EdsrModel, ImageLoader

URL = "http://localhost:18000/v1/chat/completions"
HEAD = {"1": (330, 90, 820, 410), "2": (1090, 120, 1600, 450)}
PROMPT = (
    "Extreme close-up of ONE factory worker's head. Answer ONLY from what is clearly "
    'visible.\nJSON only: {"cap":true|false,"mask":true|false,"face_visible":true|false}\n'
    "cap = a cap/hat worn on the head. mask = a hygiene mask COVERING nose AND mouth "
    "(pulled down to chin/neck = false). face_visible = is the nose/mouth area clearly shown."
)

_sr = EdsrModel.from_pretrained("eugenesiow/edsr-base", scale=4)


def upscale(crop: Image.Image) -> Image.Image:
    preds = _sr(ImageLoader.load_image(crop))
    ImageLoader.save_image(preds, "/tmp/_sr.png")
    return Image.open("/tmp/_sr.png").convert("RGB")


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
        return json.loads(mt.group(0)) if mt else {"raw": reply[:60]}
    except (ValueError, TypeError):
        return {"raw": reply[:60]}


for fp in sys.argv[1:]:
    im = Image.open(fp).convert("RGB")
    print(f"\n=== {fp} ===")
    for w, box in HEAD.items():
        crop = im.crop(box)
        print(f"  w{w} plain : {ask(crop)}")
        print(f"  w{w} SR-4x : {ask(upscale(crop))}")
