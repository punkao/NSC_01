#!/usr/bin/env python3
"""Remote inference runner (requests-based, no openai dep).
Usage: python infer.py <served_model> <video_path> <out_json>
Sends the whole video (server caps frames via --media-io-kwargs) with the safety
prompt, extracts the JSON event list, saves it in ground_truth-compatible shape.
"""
import json
import re
import sys
import time
from pathlib import Path

import requests

model = sys.argv[1] if len(sys.argv) > 1 else "qwen3vl"
video = sys.argv[2] if len(sys.argv) > 2 else "/workspace/spike/cam_a05.mp4"
out = sys.argv[3] if len(sys.argv) > 3 else "/workspace/spike/result_qwen.json"
base = sys.argv[4] if len(sys.argv) > 4 else "http://localhost:18000/v1"

SPK = "/workspace/spike"
prompt = Path(f"{SPK}/prompt_safety_temporal.txt").read_text(encoding="utf-8")
sop = Path(f"{SPK}/sop_cam_a05.txt").read_text(encoding="utf-8").strip()
prompt = prompt.replace("{SOP_CONTEXT}", sop)

payload = {
    "model": model,
    "messages": [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "video_url", "video_url": {"url": "file://" + video}},
            ],
        }
    ],
    "max_tokens": 4096,
    "temperature": 0,
}

t0 = time.time()
r = requests.post(f"{base}/chat/completions", json=payload, timeout=900)
dt = time.time() - t0
r.raise_for_status()
data = r.json()
reply = data["choices"][0]["message"]["content"] or ""

m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", reply, re.DOTALL)
cand = m.group(1) if m else reply[reply.find("{") : reply.rfind("}") + 1]
try:
    parsed = json.loads(cand)
except Exception as e:
    parsed = {"events": [], "_parse_error": str(e)}

events = parsed.get("events", [])
res = {
    "model": model,
    "video": video,
    "latency_sec": round(dt, 1),
    "events": events,
    "raw_reply": reply,
}
Path(out).write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")

n = len(events)
print(f"latency={dt:.1f}s  events={n}  usage={data.get('usage')}")
print("--- RAW REPLY (first 1800 chars) ---")
print(reply[:1800])
