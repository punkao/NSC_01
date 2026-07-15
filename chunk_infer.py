#!/usr/bin/env python3
"""Chunked video inference — cut the video into fixed windows, analyze each with
dense frame sampling, then offset per-chunk timestamps back onto the full timeline.
This is the VSS-style method that lets a small-context VLM catch short events
(e.g. the near-miss) that whole-video coarse sampling misses.

Usage: python chunk_infer.py <served_model> <video> <out_json> [seg_seconds]
"""
import json
import math
import re
import subprocess
import sys
import time
from pathlib import Path

import requests

model = sys.argv[1] if len(sys.argv) > 1 else "qwen3vl"
video = sys.argv[2] if len(sys.argv) > 2 else "/workspace/spike/cam_a05.mp4"
out = sys.argv[3] if len(sys.argv) > 3 else "/workspace/spike/result_qwen_chunked.json"
seg = int(sys.argv[4]) if len(sys.argv) > 4 else 15
prompt_file = sys.argv[5] if len(sys.argv) > 5 else "prompt_safety_temporal.txt"
base = "http://localhost:18000/v1"
SPK = "/workspace/spike"


def duration(path: str) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True,
    )
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def mmss_to_sec(v) -> float:
    p = str(v).strip().split(":")
    try:
        return int(p[0]) * 60 + float(p[1]) if len(p) >= 2 else float(p[0])
    except ValueError:
        return 0.0


def sec_to_mmss(s: float) -> str:
    s = max(0, int(round(s)))
    return f"{s // 60:02d}:{s % 60:02d}"


prompt = Path(f"{SPK}/{prompt_file}").read_text(encoding="utf-8")
sop = Path(f"{SPK}/sop_cam_a05.txt").read_text(encoding="utf-8").strip()
prompt = prompt.replace("{SOP_CONTEXT}", sop)

dur = duration(video)
nchunks = math.ceil(dur / seg) if dur else 0
print(f"duration={dur:.1f}s  seg={seg}s  chunks={nchunks}  model={model}")

chunk_dir = f"{SPK}/_chunks"
Path(chunk_dir).mkdir(parents=True, exist_ok=True)
all_events = []
t0 = time.time()
for i in range(nchunks):
    start = i * seg
    chunk = f"{chunk_dir}/chunk_{i:03d}.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-ss", str(start), "-t", str(seg), "-i", video,
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "30", "-an", chunk],
        capture_output=True,
    )
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "video_url", "video_url": {"url": "file://" + chunk}},
        ]}],
        "max_tokens": 3072,
        "temperature": 0,
    }
    try:
        r = requests.post(f"{base}/chat/completions", json=payload, timeout=300)
        r.raise_for_status()
        msg = r.json()["choices"][0]["message"]
        # reasoning models (Cosmos) put the answer in reasoning/reasoning_content
        reply = msg.get("content") or msg.get("reasoning_content") or msg.get("reasoning") or ""
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", reply, re.DOTALL)
        cand = m.group(1) if m else reply[reply.find("{"): reply.rfind("}") + 1]
        evs = json.loads(cand).get("events", [])
    except Exception as e:
        evs = []
        print(f"  chunk {i:02d} error: {e}")
    for e in evs:
        e["start"] = sec_to_mmss(mmss_to_sec(e.get("start", "0:00")) + start)
        e["end"] = sec_to_mmss(mmss_to_sec(e.get("end", e.get("start", "0:00"))) + start)
        e["chunk"] = i
        all_events.append(e)
    print(f"  chunk {i:02d} [{sec_to_mmss(start)}-{sec_to_mmss(start + seg)}] -> {len(evs)} events")

dt = time.time() - t0
res = {"model": model, "video": video, "method": f"chunked_{seg}s",
       "latency_sec": round(dt, 1), "events": all_events}
Path(out).write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nTOTAL {len(all_events)} events in {dt:.0f}s -> {out}")
