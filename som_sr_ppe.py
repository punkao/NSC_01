#!/usr/bin/env python3
"""Full-video SR-head PPE: super-res each worker's HEAD crop -> Cosmos -> cap + mask,
over all 74 frames. Gloves are intentionally NOT touched here (full-frame baseline is
their best method; crop hurt them) — this isolates SR's effect on cap/mask so a
regression elsewhere is impossible by construction.

Output: image_obs_sr.json with cap/mask per worker (merge gloves from baseline offline).
Run on the GPU box (Cosmos localhost:18000, detenv with super-image).
"""
import base64
import io
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor

import requests
from PIL import Image
from super_image import EdsrModel, ImageLoader

URL = "http://localhost:18000/v1/chat/completions"
FRAMES = os.getenv("FRAMES", "/workspace/frames")
HEAD = {"1": (330, 90, 820, 410), "2": (1090, 120, 1600, 450)}
PROMPT = (
    "Extreme close-up of ONE factory worker's head. Answer ONLY from what is clearly "
    'visible.\nJSON only: {"cap":true|false,"mask":true|false,"head_visible":true|false,'
    '"face_visible":true|false}\n'
    "cap = a cap/hat worn on the head. mask = a hygiene mask COVERING nose AND mouth "
    "(pulled to chin/neck = false). head_visible = top of head shown. face_visible = "
    "nose/mouth area clearly shown."
)
_sr = EdsrModel.from_pretrained("eugenesiow/edsr-base", scale=4)
_lock_i = [0]


def upscale(crop: Image.Image, tag: str) -> Image.Image:
    out = f"/tmp/_sr_{tag}.png"
    ImageLoader.save_image(_sr(ImageLoader.load_image(crop)), out)
    return Image.open(out).convert("RGB")


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
        h = ask(upscale(im.crop(HEAD[w]), f"{t}_{w}"))
        # report raw (ungated) cap/mask; the gate is evaluated separately offline
        obs[f"{w}|cap"] = "on" if h.get("cap") else "off"
        obs[f"{w}|mask"] = "on" if h.get("mask") else "off"
        obs[f"{w}|mask_facevis"] = "yes" if h.get("face_visible") else "no"
    return {"t": t, "obs": obs}


def main() -> None:
    ts = list(range(0, 220, 3))
    print(f"SR-head PPE: {len(ts)} frames (SR head crop -> cap/mask)...")
    with ThreadPoolExecutor(2) as ex:  # SR is CPU-heavy; keep Cosmos concurrency low
        rows = [r for r in ex.map(frame_obs, ts) if r]
    rows.sort(key=lambda r: r["t"])
    json.dump(rows, open("image_obs_sr.json", "w", encoding="utf-8"), ensure_ascii=False)
    print(f"saved image_obs_sr.json ({len(rows)} frames)")


if __name__ == "__main__":
    main()
