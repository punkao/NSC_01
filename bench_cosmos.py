#!/usr/bin/env python3
"""Benchmark Cosmos narration — วัด latency / throughput / คุณภาพ ต่อ 1 GPU config.
รัน 1 ครั้งต่อ config (1gpu / 2gpu / a100) → เก็บ bench_results/<name>.json แยกไฟล์ เทียบทีหลัง.

ต้องมี: tunnel Cosmos (:18000 [+ :18001 ถ้า 2 GPU]) + _frames/ local.

ตัวอย่าง:
  # 1 GPU (หรือ A100 — โค้ดเดียวกัน แค่ endpoint เดียว)
  python bench_cosmos.py --name 1gpu --gpu "RTX 4090 x1"
  python bench_cosmos.py --name a100 --gpu "A100 80GB x1"
  # 2 GPU แยกสตรีม (2 endpoints)
  python bench_cosmos.py --name 2gpu --gpu "RTX 4090 x2" \
      --endpoints http://127.0.0.1:18000/v1/chat/completions,http://127.0.0.1:18001/v1/chat/completions
"""
import argparse
import base64
import datetime
import json
import os
import statistics
import time
from concurrent.futures import ThreadPoolExecutor

import requests

FRAMES = "_frames"
OUTDIR = "bench_results"
# prompt "ชัด 1-2 ประโยค" — ใช้ตัวเดียวกันทุก config เพื่อเทียบ apples-to-apples
CLEAR_PROMPT = (
    "ภาพ 2 เฟรมต่อเนื่อง กล้อง CCTV โรงงานกระป๋อง (คน1 ซ้าย คน2 ขวา). "
    "บรรยายภาษาไทยล้วน 1-2 ประโยคชัดเจน ว่าตอนนี้เห็นอะไร คนกำลังทำอะไร และมีจุดเสี่ยงความปลอดภัยไหม."
)

_AVAIL = sorted(int(f[1:5]) for f in os.listdir(FRAMES) if f.startswith("t") and f.endswith(".jpg"))


def _nearest(s):
    return min(_AVAIL, key=lambda x: abs(x - s))


def _b64(p):
    return base64.b64encode(open(p, "rb").read()).decode()


def one_call(ep, t, tokens):
    """ยิง Cosmos 1 ครั้ง (2 เฟรมห่าง 1วิ) คืน (latency, text, finish_reason)."""
    a = _nearest(int(t))
    b = _nearest(a + 1)
    fa, fb = f"{FRAMES}/t{a:04d}.jpg", f"{FRAMES}/t{b:04d}.jpg"
    payload = {"model": "cosmos", "messages": [{"role": "user", "content": [
        {"type": "text", "text": CLEAR_PROMPT},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{_b64(fa)}"}},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{_b64(fb)}"}}]}],
        "max_tokens": tokens, "temperature": 0}
    s = time.time()
    r = requests.post(ep, json=payload, timeout=120)
    dt = time.time() - s
    j = r.json()["choices"][0]
    m = j["message"]
    txt = (m.get("content") or m.get("reasoning_content") or m.get("reasoning") or "").strip()
    return dt, txt, j.get("finish_reason")


def measure(endpoints, tokens, n):
    """ยิง n ครั้งกระจายทั่ววิดีโอ, concurrency = จำนวน endpoint (จำลอง split-stream).
    คืน per-call latencies + effective wall (ไว้คิด throughput จริง)."""
    lo, hi = _AVAIL[0], _AVAIL[-1]
    ts = [lo + int((hi - lo) * k / max(n - 1, 1)) for k in range(n)]
    out = [None] * n

    def task(k):
        ep = endpoints[k % len(endpoints)]
        return k, one_call(ep, ts[k], tokens)

    wall0 = time.time()
    with ThreadPoolExecutor(max_workers=len(endpoints)) as ex:
        for k, res in ex.map(task, range(n)):
            out[k] = res
    wall = time.time() - wall0
    lats = [o[0] for o in out]
    samples = [{"t": ts[k], "mmss": f"{ts[k]//60:02d}:{ts[k]%60:02d}",
                "latency": round(out[k][0], 2), "finish": out[k][2], "text": out[k][1]}
               for k in range(min(n, 6))]
    return lats, wall, samples


def token_sweep(ep, sweep, per):
    """วัด latency ที่ token ต่างๆ (single endpoint) เพื่อ characterize L(N) ของ GPU นี้."""
    curve = {}
    lo, hi = _AVAIL[0], _AVAIL[-1]
    for mt in sweep:
        ls = [one_call(ep, lo + (hi - lo) * i // max(per - 1, 1), mt)[0] for i in range(per)]
        curve[mt] = round(statistics.median(ls), 2)
    return curve


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True, help="config id -> bench_results/<name>.json")
    ap.add_argument("--gpu", default="unknown", help="โน้ต GPU เช่น 'RTX 4090 x1'")
    ap.add_argument("--endpoints", default="http://127.0.0.1:18000/v1/chat/completions",
                    help="คั่นด้วย , (2 อันสำหรับ 2 GPU)")
    ap.add_argument("--tokens", type=int, default=90, help="ความชัด (default 90 = ~2 ประโยค)")
    ap.add_argument("--samples", type=int, default=20, help="จำนวน call วัด latency")
    ap.add_argument("--sweep", default="30,60,90,120", help="token sweep (ว่าง = ข้าม)")
    args = ap.parse_args()

    eps = [e.strip() for e in args.endpoints.split(",") if e.strip()]
    os.makedirs(OUTDIR, exist_ok=True)
    print(f"[{args.name}] {args.gpu} | endpoints={len(eps)} | tokens={args.tokens}")

    # warmup
    print("  warmup...")
    for _ in range(2):
        one_call(eps[0], _AVAIL[len(_AVAIL) // 2], args.tokens)

    print(f"  วัด latency ({args.samples} calls)...")
    lats, wall, samples = measure(eps, args.tokens, args.samples)
    L = statistics.median(lats)
    eff_interval = wall / args.samples  # narration ใหม่ออกทุกกี่วิ (throughput จริง)

    sweep = {}
    if args.sweep.strip():
        print("  token sweep...")
        sweep = token_sweep(eps[0], [int(x) for x in args.sweep.split(",")], 3)

    # derived: p_max = video speed สูงสุดที่ทำได้ ที่ cadence D วินาที (cap 1.0)
    p_max = {f"every_{d}s": round(min(1.0, d / eff_interval), 2) for d in (1, 2, 3)}

    result = {
        "name": args.name,
        "gpu": args.gpu,
        "n_endpoints": len(eps),
        "tokens": args.tokens,
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        "latency": {
            "median_s": round(L, 2),
            "mean_s": round(statistics.mean(lats), 2),
            "p90_s": round(sorted(lats)[int(len(lats) * 0.9)], 2),
            "min_s": round(min(lats), 2),
            "max_s": round(max(lats), 2),
            "all": [round(x, 2) for x in lats],
        },
        "effective_interval_s": round(eff_interval, 2),
        "throughput_per_s": round(1 / eff_interval, 2),
        "max_video_speed": p_max,
        "token_latency_curve": sweep,
        "sample_narrations": samples,
    }
    path = os.path.join(OUTDIR, f"{args.name}.json")
    json.dump(result, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print(f"\n  === {args.name} ({args.gpu}) ===")
    print(f"  latency median = {L:.2f}s (min {min(lats):.2f} / max {max(lats):.2f})")
    print(f"  effective interval = {eff_interval:.2f}s  (narration ใหม่ทุก ~{eff_interval:.2f}s)")
    print(f"  video speed สูงสุด: per-second={p_max['every_1s']}x  ทุก2วิ={p_max['every_2s']}x")
    if sweep:
        print(f"  token curve: {sweep}")
    print(f"  -> saved {path}")


if __name__ == "__main__":
    main()
