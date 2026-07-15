#!/usr/bin/env python3
"""Diagnostic: send ONE chunk to the served model, dump the full response shape."""
import json
import subprocess
import sys
from pathlib import Path

import requests

model = sys.argv[1] if len(sys.argv) > 1 else "cosmos"
start = sys.argv[2] if len(sys.argv) > 2 else "165"  # near-miss chunk ~02:45
SPK = "/workspace/spike"

prompt = Path(f"{SPK}/prompt_safety_temporal.txt").read_text(encoding="utf-8")
sop = Path(f"{SPK}/sop_cam_a05.txt").read_text(encoding="utf-8").strip()
prompt = prompt.replace("{SOP_CONTEXT}", sop)

chunk = f"{SPK}/_chunks/dbg.mp4"
subprocess.run(["ffmpeg", "-y", "-ss", start, "-t", "15", "-i", f"{SPK}/cam_a05.mp4",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "30", "-an", chunk],
               capture_output=True)

payload = {
    "model": model,
    "messages": [{"role": "user", "content": [
        {"type": "text", "text": prompt},
        {"type": "video_url", "video_url": {"url": "file://" + chunk}},
    ]}],
    "max_tokens": 3072,
    "temperature": 0,
}
r = requests.post("http://localhost:18000/v1/chat/completions", json=payload, timeout=300)
print("HTTP", r.status_code)
d = r.json()
ch = d["choices"][0]
msg = ch["message"]
print("finish_reason:", ch.get("finish_reason"))
print("usage:", d.get("usage"))
print("content len:", len(msg.get("content") or ""))
print("reasoning len:", len(msg.get("reasoning_content") or ""))
print("=== CONTENT ===")
print((msg.get("content") or "")[:1200])
print("=== REASONING (first 1500) ===")
print((msg.get("reasoning_content") or "")[:1500])
print("=== RAW CHOICE JSON (first 2500) ===")
print(json.dumps(ch, ensure_ascii=False)[:2500])
