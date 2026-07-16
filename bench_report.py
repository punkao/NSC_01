#!/usr/bin/env python3
"""วัดตัวเลขทั้งหมดที่รายงานบทที่ 5 ต้องใช้ — รัน co-located บนเครื่อง GPU เท่านั้น.

ทำไมต้องมีไฟล์นี้: ตัวเลข latency ในรายงานรอบก่อนวัดผ่าน SSH tunnel -> มีเวลาเครือข่ายปน
(ส่งภาพ ~1MB/คำขอ) ทำให้ตัวเลขสูงเกินจริง 2-3 เท่า. ไฟล์นี้วัดบนเครื่องเดียวกับโมเดล.

วัด 3 อย่าง:
  1. image-tier latency  : 1 เฟรม 1080p + 1 prompt (ที่รายงานเคลมว่า ~1.85 วิ)
  2. narration latency   : 2 เฟรม + prompt 150 token (ที่ใช้จริงใน deliverable)
  3. throughput          : ยิงขนานเท่าจำนวน GPU -> ช่วงเวลาระหว่างคำตอบ -> ความเร็ววิดีโอสูงสุด

Run: python bench_report.py --endpoints <ep0>[,<ep1>] --label 1gpu
"""
import argparse
import base64
import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor

import requests

FRAMES = "_frames_full"   # เฟรมทุก 1 วิ (narration ใช้ 2 เฟรมติดกัน)
IMG_PROMPT = ("You are a factory safety inspector viewing ONE still CCTV frame of a canning line. "
              "worker 1 (left), worker 2 (right). For EACH worker report whether head/hands are "
              'CLEARLY VISIBLE and whether cap/gloves are worn. JSON only: '
              '{"workers":[{"id":"1"|"2","head_visible":bool,"cap":bool,"hands_visible":bool,"gloves":bool}]}')
# ใช้ prompt ตัวจริงที่ deliverable ใช้ — ห้ามเขียนใหม่ ไม่งั้นวัดของที่ไม่ได้ส่ง
# (เคยพลาด: prompt ที่เขียนเองพ่น output ยาวกว่า 130 vs 102 token -> latency ต่างไป 20%)
from generate_timeline import BAN_BOX, PROMPT
NARR_PROMPT = PROMPT + BAN_BOX


def b64(p: str) -> str:
    return base64.b64encode(open(p, "rb").read()).decode()


def call(ep: str, prompt: str, frames: list[str], max_tok: int) -> tuple[float, int, int]:
    payload = {"model": "cosmos", "messages": [{"role": "user", "content":
        [{"type": "text", "text": prompt}] +
        [{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64(f)}"}} for f in frames]}],
        "max_tokens": max_tok, "temperature": 0}
    t0 = time.time()
    j = requests.post(ep, json=payload, timeout=120).json()
    dt = time.time() - t0
    u = j.get("usage", {})
    return dt, u.get("prompt_tokens", 0), u.get("completion_tokens", 0)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--endpoints", required=True)
    ap.add_argument("--label", required=True, help="เช่น 1gpu / 2gpu")
    ap.add_argument("--out", default="bench_report_results.json")
    a = ap.parse_args()
    eps = [e.strip() for e in a.endpoints.split(",") if e.strip()]
    ts = [10, 30, 50, 70, 90, 110, 130, 150, 170, 190]  # มีครบใน _frames_full (fps=1)

    for _ in range(2):                                   # warmup
        call(eps[0], NARR_PROMPT, [f"{FRAMES}/t0050.jpg"], 60)

    # 1) image-tier: 1 เฟรม 1 prompt
    r = [call(eps[0], IMG_PROMPT, [f"{FRAMES}/t{t:04d}.jpg"], 200) for t in ts[:6]]
    img_lat = statistics.median([x[0] for x in r])
    img_ptok = statistics.median([x[1] for x in r])

    # 2) narration: 2 เฟรม 150 token
    r = [call(eps[0], NARR_PROMPT, [f"{FRAMES}/t{t:04d}.jpg", f"{FRAMES}/t{t+1:04d}.jpg"], 150) for t in ts[:6]]
    nar_lat = statistics.median([x[0] for x in r])
    nar_ptok = statistics.median([x[1] for x in r])
    nar_ctok = statistics.median([x[2] for x in r])

    # 3) throughput: ยิงขนาน = จำนวน GPU (เหมือน demo จริง)
    def job(i: int):
        t = ts[i % len(ts)]
        return call(eps[i % len(eps)], NARR_PROMPT, [f"{FRAMES}/t{t:04d}.jpg", f"{FRAMES}/t{t+1:04d}.jpg"], 150)[0]
    n = 12
    w0 = time.time()
    with ThreadPoolExecutor(max_workers=len(eps)) as ex:
        list(ex.map(job, range(n)))
    interval = (time.time() - w0) / n

    res = {"label": a.label, "n_gpu": len(eps),
           "image_tier_latency_s": round(img_lat, 2), "image_tier_prompt_tokens": img_ptok,
           "narration_latency_s": round(nar_lat, 2), "narration_prompt_tokens": nar_ptok,
           "narration_output_tokens": nar_ctok, "prompt": "PROMPT+BAN_BOX (ตัวจริง)",
           "interval_s": round(interval, 2), "max_video_speed": round(min(1.0, 1 / interval), 2)}
    try:
        old = json.load(open(a.out))
    except Exception:
        old = {}
    old[a.label] = res
    json.dump(old, open(a.out, "w"), ensure_ascii=False, indent=1)
    print(f"\n=== {a.label} ({len(eps)} GPU, co-located) ===")
    print(f"  image-tier (1 เฟรม 1080p)  : {img_lat:.2f}s   (prompt {img_ptok} tokens)")
    print(f"  narration (2 เฟรม 150 tok) : {nar_lat:.2f}s   (prompt {nar_ptok} / out {nar_ctok} tokens)")
    print(f"  throughput (ยิงขนาน {len(eps)}) : interval {interval:.2f}s -> วิดีโอ {min(1.0,1/interval):.2f}x")
    print(f"  -> saved {a.out}")


if __name__ == "__main__":
    main()
