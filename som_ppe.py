#!/usr/bin/env python3
"""Set-of-Mark PPE — the local, no-train attempt at precise PPE.

Instead of asking Cosmos about PPE on the full 1080p frame (small items lost), crop
each worker's HEAD (cap / mask) and HANDS (gloves) high-res and ask Cosmos per crop,
with a visibility gate applied in CODE (not visible -> "unknown", never guess worn).
Static camera => fixed crop regions (worker 1 left, worker 2 right).

Produces image_obs_som.json (same schema as image_obs.json) so diff_gt.py / ppe_tracker
work unchanged. Run on the GPU box (Cosmos at localhost:18000).

Usage: python som_ppe.py            # full video (frames in FRAMES dir)
"""
import base64
import io
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor

import requests
from PIL import Image

URL = "http://localhost:18000/v1/chat/completions"
FRAMES = os.getenv("FRAMES", "/workspace/frames")
STEP = 3

# static-camera crop regions (x0, y0, x1, y1)
HEAD = {"1": (330, 90, 820, 410), "2": (1090, 120, 1600, 450)}
HANDS = {"1": (360, 430, 820, 790), "2": (1120, 420, 1560, 780)}

HEAD_PROMPT = (
    "Extreme close-up of ONE factory worker's head. Answer ONLY from what is clearly "
    'visible.\nJSON only: {"cap":true|false,"mask":true|false,"head_visible":true|false,'
    '"face_visible":true|false}\n'
    "cap = a cap/hat worn on the head. mask = a hygiene mask COVERING nose AND mouth "
    "(pulled down to chin/neck = false). head_visible = is the top of the head shown. "
    "face_visible = is the nose/mouth area clearly shown."
)
HANDS_PROMPT = (
    "Extreme close-up of a factory worker's hands at a conveyor. Answer ONLY from what "
    'is clearly visible.\nJSON only: {"gloves":true|false,"hands_visible":true|false}\n'
    "gloves = cloth/rubber gloves on the hands (a hand holding a cloth still counts as "
    "gloved). Set gloves=false ONLY for a clearly BARE hand (visible skin). "
    "hands_visible = is at least one hand clearly in view."
)


def ask(img: Image.Image, prompt: str) -> dict:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    b64 = base64.b64encode(buf.getvalue()).decode()
    payload = {"model": "cosmos", "messages": [{"role": "user", "content": [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}]}],
        "max_tokens": 500, "temperature": 0}
    r = requests.post(URL, json=payload, timeout=120)
    m = r.json()["choices"][0]["message"]
    reply = m.get("content") or m.get("reasoning_content") or m.get("reasoning") or ""
    mt = re.search(r"\{.*\}", reply, re.DOTALL)
    try:
        return json.loads(mt.group(0)) if mt else {}
    except (ValueError, TypeError):
        return {}


def frame_obs(t: int) -> dict | None:
    fp = os.path.join(FRAMES, f"t{t:04d}.jpg")
    if not os.path.exists(fp):
        return None
    im = Image.open(fp).convert("RGB")
    obs: dict[str, str] = {}
    for w in ("1", "2"):
        h = ask(im.crop(HEAD[w]), HEAD_PROMPT)
        # cap: gate on head visibility; mask: gate on face visibility (never guess worn)
        obs[f"{w}|cap"] = ("unknown" if not h.get("head_visible")
                           else "on" if h.get("cap") else "off")
        obs[f"{w}|mask"] = ("unknown" if not h.get("face_visible")
                            else "on" if h.get("mask") else "off")
        g = ask(im.crop(HANDS[w]), HANDS_PROMPT)
        obs[f"{w}|gloves"] = ("unknown" if not g.get("hands_visible")
                              else "on" if g.get("gloves") else "off")
    return {"t": t, "obs": obs}


def main() -> None:
    ts = list(range(0, 220, STEP))
    print(f"SoM PPE: {len(ts)} frames x 4 crops (head+hands per worker)...")
    with ThreadPoolExecutor(3) as ex:
        rows = [r for r in ex.map(frame_obs, ts) if r]
    rows.sort(key=lambda r: r["t"])
    json.dump(rows, open("image_obs_som.json", "w", encoding="utf-8"), ensure_ascii=False)
    print(f"saved image_obs_som.json ({len(rows)} frames)")


if __name__ == "__main__":
    main()
