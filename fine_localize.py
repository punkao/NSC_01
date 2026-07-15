#!/usr/bin/env python3
"""Stage-2 fine localization — turn a coarse ~15s event window into second-accurate
onset/offset by scanning 1s-spaced full-res frames with a type-specific yes/no
question (image path -> base64, so it works cross-machine, no file:// needed).

Proven in spike (2026-07-14): unauthorized_person pinned to 01:35 entry / 01:42
exit; PPE cap/glove per-frame. near_miss does NOT localize (no crisp single-frame
signature — it is an inherently fuzzy judgment call), so this returns [] for it and
the coarse window should be kept instead.

Usage: python fine_localize.py <video> <event_type> <start_sec> <end_sec>
       event_type in: unauthorized_person | ppe_violation | hygiene_violation |
                      foreign_object | near_miss
"""
import base64
import json
import os
import re
import subprocess
import sys
import tempfile

import requests

BASE = os.getenv("VLLM_BASE_URL", "http://localhost:18000/v1")
MODEL = os.getenv("VLLM_MODEL", "cosmos")
FFMPEG = os.getenv("FFMPEG", "ffmpeg")
MIN_RUN = 2          # frames a condition must persist to count (debounce)
CLUSTER_GAP = 2      # seconds; merge flagged frames within this into one span

# Type-specific per-frame questions. Each asks for {"hit": bool, "note_th": str}.
PROMPTS = {
    "unauthorized_person":
        "You see ONE still frame of a can inspection line normally run by exactly "
        "TWO workers (labelled 1 and 2, white shirts). Is there an ADDITIONAL "
        "(third) person present in the work area? Answer ONLY JSON "
        '{"hit":true,"note_th":"<short Thai>"}.',
    "ppe_violation":
        "You see ONE still frame of a can line. Each worker in the area must wear a "
        "CAP, cloth GLOVES and a MASK. Is ANY worker clearly missing a cap, gloves "
        "or mask? Answer ONLY JSON {\"hit\":true,\"note_th\":\"<short Thai>\"}.",
    "hygiene_violation":
        "You see ONE still frame of a can line work area. Is there an unrelated "
        "personal item (water bottle, drink, phone) placed on the table/conveyor "
        "in the work area? Answer ONLY JSON {\"hit\":true,\"note_th\":\"<Thai>\"}.",
    "foreign_object":
        "You see ONE still frame of a can line. Is there any foreign object that "
        "does not belong on the conveyor/work area? Answer ONLY JSON "
        '{"hit":true,"note_th":"<short Thai>"}.',
    "near_miss":
        "You see ONE still frame of a can line with a moving conveyor. Is a "
        "worker's hand/arm reaching INTO or touching the moving belt / rollers / "
        "pinch-point (could be caught)? A hand holding a can above the belt is NOT "
        "this. Answer ONLY JSON {\"hit\":true,\"note_th\":\"<short Thai>\"}.",
}


def sec_to_mmss(s: int) -> str:
    return f"{s // 60:02d}:{s % 60:02d}"


def extract_frame(video: str, t: int, out: str) -> bool:
    subprocess.run([FFMPEG, "-nostdin", "-loglevel", "error", "-ss", str(t),
                    "-i", video, "-frames:v", "1", "-vf", "scale=1280:-2",
                    "-q:v", "3", out, "-y"], capture_output=True)
    return os.path.exists(out) and os.path.getsize(out) > 0


def probe(path: str, prompt: str) -> dict:
    b64 = base64.b64encode(open(path, "rb").read()).decode()
    payload = {"model": MODEL, "messages": [{"role": "user", "content": [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
    ]}], "max_tokens": 400, "temperature": 0}
    r = requests.post(f"{BASE}/chat/completions", json=payload, timeout=180)
    r.raise_for_status()
    m = r.json()["choices"][0]["message"]
    rep = m.get("content") or m.get("reasoning_content") or m.get("reasoning") or ""
    s, e = rep.find("{"), rep.rfind("}")
    try:
        return json.loads(rep[s:e + 1])
    except Exception:
        return {"hit": None, "note_th": rep[:80]}


def localize(video: str, event_type: str, start: int, end: int) -> list[dict]:
    prompt = PROMPTS.get(event_type)
    if not prompt:
        raise SystemExit(f"unknown event_type {event_type}; choose {list(PROMPTS)}")
    flagged: list[int] = []
    with tempfile.TemporaryDirectory() as td:
        for t in range(start, end + 1):
            fp = os.path.join(td, f"f_{t}.jpg")
            if not extract_frame(video, t, fp):
                continue
            res = probe(fp, prompt)
            hit = bool(res.get("hit"))
            print(f"  {sec_to_mmss(t)}  hit={hit}  {res.get('note_th', '')}")
            if hit:
                flagged.append(t)

    # cluster consecutive flagged seconds, keep runs that persist (>= MIN_RUN)
    spans, run = [], []
    for t in flagged:
        if run and t - run[-1] <= CLUSTER_GAP:
            run.append(t)
        else:
            if len(run) >= MIN_RUN:
                spans.append((run[0], run[-1]))
            run = [t]
    if len(run) >= MIN_RUN:
        spans.append((run[0], run[-1]))
    return [{"start": sec_to_mmss(a), "end": sec_to_mmss(b),
             "start_sec": a, "end_sec": b} for a, b in spans]


if __name__ == "__main__":
    video, etype = sys.argv[1], sys.argv[2]
    start, end = int(sys.argv[3]), int(sys.argv[4])
    spans = localize(video, etype, start, end)
    print(f"\n{etype} localized spans: {spans or 'NONE (keep coarse window)'}")
