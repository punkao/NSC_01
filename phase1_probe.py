#!/usr/bin/env python3
"""Phase 1 — combined per-frame image probe (image tier: PPE + person + foreign_object).
SOP/near-miss are handled by the video track, not here (Phase 0 gate).

Extracts 1080p frames from the video on the remote (ffmpeg), sends each as base64
to Cosmos with ONE combined prompt, saves raw per-frame results.

Usage: python phase1_probe.py <video> <out_json> [interval_sec] [start_sec] [end_sec]
"""
import base64
import json
import re
import subprocess
import sys
from pathlib import Path

import requests

video = sys.argv[1] if len(sys.argv) > 1 else "/workspace/spike/cam_a05_1080p.mp4"
out = sys.argv[2] if len(sys.argv) > 2 else "/workspace/spike/phase1_raw.json"
interval = float(sys.argv[3]) if len(sys.argv) > 3 else 3.0
start = float(sys.argv[4]) if len(sys.argv) > 4 else 0.0
end = float(sys.argv[5]) if len(sys.argv) > 5 else 219.0
BASE = "http://localhost:18000/v1"
MODEL = "cosmos"
FRAMEDIR = "/workspace/spike/_p1frames"

PROMPT = (
    "You are a factory safety inspector viewing ONE still CCTV frame of a canning "
    "line. Two workers normally operate the line: worker 1 on the LEFT (near the NG "
    "and WAIT boxes), worker 2 on the RIGHT (near the GOOD box).\n"
    "Report ONLY what is visible in THIS frame. Answer with JSON only, no other text:\n"
    "{\n"
    '  "person_count": <int, total people visible>,\n'
    '  "workers": [{"id": "1" or "2", "cap": true/false, "gloves": true/false, "mask": true/false}],\n'
    '  "extra_person": true/false,\n'
    '  "foreign_object": true/false,\n'
    '  "note_th": "<one short Thai sentence: missing PPE / outsider / foreign object>"\n'
    "}\n"
    "PPE: report cap/gloves/mask as what you actually see worn on each worker. "
    "extra_person = a third person who is NOT worker 1 or 2 (visitor/outsider). "
    "foreign_object = an unrelated item in the work area (drink bottle, phone, personal belongings)."
)


def parse(reply: str) -> dict:
    m = re.search(r"\{.*\}", reply, re.DOTALL)
    try:
        return json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        return {}


def probe(path: str) -> dict:
    b64 = base64.b64encode(Path(path).read_bytes()).decode()
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": PROMPT},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
        ]}],
        "max_tokens": 1024,
        "temperature": 0,
    }
    r = requests.post(f"{BASE}/chat/completions", json=payload, timeout=180)
    r.raise_for_status()
    msg = r.json()["choices"][0]["message"]
    reply = msg.get("content") or msg.get("reasoning_content") or msg.get("reasoning") or ""
    return parse(reply)


def mmss(s: float) -> str:
    s = int(s)
    return f"{s//60:02d}:{s%60:02d}"


def main() -> None:
    Path(FRAMEDIR).mkdir(parents=True, exist_ok=True)
    results = []
    t = start
    print(f"{'TIME':<6} {'ppl':<3} {'PPE(cap/glv/msk per worker)':<34} {'extra':<6} {'foreign':<8} note")
    print("-" * 110)
    while t <= end:
        fp = f"{FRAMEDIR}/f_{int(t):04d}.jpg"
        subprocess.run(["ffmpeg", "-y", "-ss", str(t), "-i", video,
                        "-frames:v", "1", "-q:v", "2", fp], capture_output=True)
        obj = probe(fp)
        obj["sec"] = t
        results.append(obj)
        ppe = " ".join(
            f"w{w.get('id','?')}:{int(bool(w.get('cap')))}{int(bool(w.get('gloves')))}{int(bool(w.get('mask')))}"
            for w in (obj.get("workers") or [])
        )
        print(f"{mmss(t):<6} {str(obj.get('person_count','?')):<3} {ppe:<34} "
              f"{str(obj.get('extra_person','?')):<6} {str(obj.get('foreign_object','?')):<8} "
              f"{(obj.get('note_th','') or '')[:40]}")
        t += interval

    Path(out).write_text(json.dumps({"video": video, "interval": interval, "frames": results},
                                    ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{len(results)} frames -> {out}")


if __name__ == "__main__":
    main()
