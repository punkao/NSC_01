#!/usr/bin/env python3
"""Phase 0 GATE — probe whether SOP violation is detectable from a SINGLE still frame.

Reads phase0_frames/manifest.json, sends each 1080p frame (base64) to Cosmos with a
focused SOP question, then scores:
  - recall  = % of SOP-window frames that fire (sop_violation=true)
  - false   = % of normal-window frames that wrongly fire
Acceptance (WORKPLAN Phase 0): recall > 60% AND false < 50%.

Usage: python sop_probe.py [frames_dir] [base_url]
"""
import base64
import json
import re
import sys
from pathlib import Path

import requests

FRAMES = sys.argv[1] if len(sys.argv) > 1 else "/workspace/spike/phase0_frames"
BASE = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:18000/v1"
MODEL = "cosmos"

PROMPT = (
    "You are a factory safety inspector looking at ONE still frame from a canning "
    "production line.\n"
    "SOP rule: a worker must VISUALLY INSPECT each can, and place only GOOD cans on "
    "the conveyor. NG / reject cans must go into the NG tray and must NEVER be put "
    "back onto the conveyor.\n\n"
    "Look at this frame. Does it show a worker taking a can from the NG/reject box, "
    "or placing a can onto the conveyor without inspecting it (an SOP violation)?\n"
    "Judge only from what is visible in THIS frame.\n\n"
    'Answer with JSON only: {"sop_violation": true or false, '
    '"worker": "who (e.g. worker 1/2)", "note_th": "<what you see, in Thai>"}'
)


def parse(reply: str) -> dict:
    m = re.search(r"\{.*\}", reply, re.DOTALL)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {}


def main() -> None:
    manifest = json.loads(Path(f"{FRAMES}/manifest.json").read_text())["frames"]
    results = []
    for fr in manifest:
        img = Path(f"{FRAMES}/{fr['file']}").read_bytes()
        b64 = base64.b64encode(img).decode()
        payload = {
            "model": MODEL,
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": PROMPT},
                {"type": "image_url",
                 "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            ]}],
            "max_tokens": 1024,
            "temperature": 0,
        }
        r = requests.post(f"{BASE}/chat/completions", json=payload, timeout=180)
        r.raise_for_status()
        msg = r.json()["choices"][0]["message"]
        reply = msg.get("content") or msg.get("reasoning_content") or msg.get("reasoning") or ""
        obj = parse(reply)
        fire = bool(obj.get("sop_violation"))
        results.append({**fr, "fire": fire, "note": obj.get("note_th", "")[:60]})
        tag = "SOP-WIN" if fr["window"] == "sop" else "normal "
        mark = "FIRE" if fire else "  -  "
        print(f"  [{tag}] {fr['sec']:>3}s  {mark}  {obj.get('note_th','')[:55]}")

    sop = [r for r in results if r["window"] == "sop"]
    norm = [r for r in results if r["window"] == "normal"]
    recall = sum(r["fire"] for r in sop) / len(sop) if sop else 0
    false = sum(r["fire"] for r in norm) / len(norm) if norm else 0
    print("\n=== PHASE 0 RESULT ===")
    print(f"  SOP-window recall : {recall:.0%}  ({sum(r['fire'] for r in sop)}/{len(sop)})")
    print(f"  normal false-fire : {false:.0%}  ({sum(r['fire'] for r in norm)}/{len(norm)})")
    ok = recall > 0.60 and false < 0.50
    print(f"  ACCEPTANCE (recall>60% & false<50%): {'PASS ✅' if ok else 'FAIL ❌'}")
    if not ok:
        print("  → ถ้า FAIL: SOP ถอยไปใช้ Track A (video/temporal) ตาม WORKPLAN")


if __name__ == "__main__":
    main()
