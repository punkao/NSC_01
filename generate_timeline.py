#!/usr/bin/env python3
"""สร้าง cam_a05_timeline.json — narration ต่อวินาทีทั้งวิดีโอ (สำหรับ demo offline).
รัน co-located บนเครื่อง GPU (hit localhost) เพื่อความเร็วเต็มที่ + ใช้ทั้ง 2 GPU ขนาน.

ตัวอย่าง (บนเครื่อง 2×4090):
  python generate_timeline.py \
    --endpoints http://localhost:18000/v1/chat/completions,http://localhost:18001/v1/chat/completions \
    --frames /workspace/frames --events cam_a05_ai_events.json --out cam_a05_timeline.json
"""
import argparse
import base64
import datetime
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor

import requests

PROMPT = (
    "ภาพ 2 เฟรมต่อเนื่อง กล้อง CCTV โรงงานกระป๋อง (คน1 ซ้าย คน2 ขวา). "
    "บรรยายภาษาไทยล้วน 1-2 ประโยคสั้นกระชับ จบประโยคให้สมบูรณ์ "
    "ว่าตอนนี้เห็นอะไร คนกำลังทำอะไร และมีจุดเสี่ยงความปลอดภัยไหม."
)


def _clean(txt, finish):
    txt = txt.strip()
    if finish == "length":
        i = txt.rfind(" ")
        if i > 40:
            txt = txt[:i].rstrip(" ,·") + " …"
    return txt
_TYPE_LABEL = {
    "ppe_violation": ("PPE", "medium"), "near_miss": ("Near-miss", "critical"),
    "unauthorized_person": ("บุคคลภายนอก", "high"), "hygiene_violation": ("ของแปลกปลอม", "low"),
    "falling_object": ("ของตก", "high"),
}


def _sec(mmss):
    p = str(mmss).split(":")
    return int(p[0]) * 60 + int(p[1]) if len(p) == 2 else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--endpoints", default="http://localhost:18000/v1/chat/completions")
    ap.add_argument("--frames", default="/workspace/frames")
    ap.add_argument("--events", default="cam_a05_ai_events.json")
    ap.add_argument("--out", default="cam_a05_timeline.json")
    ap.add_argument("--tokens", type=int, default=90)
    ap.add_argument("--step", type=int, default=1, help="ทุกกี่วินาที (1 = per-second)")
    args = ap.parse_args()

    eps = [e.strip() for e in args.endpoints.split(",") if e.strip()]
    avail = sorted(int(f[1:5]) for f in os.listdir(args.frames) if f.startswith("t") and f.endswith(".jpg"))
    nearest = lambda s: min(avail, key=lambda x: abs(x - s))
    b64 = lambda p: base64.b64encode(open(p, "rb").read()).decode()
    lo, hi = avail[0], avail[-1]
    points = list(range(lo, hi + 1, args.step))

    # round-robin endpoint ต่อ index (ใช้ 2 GPU ขนาน)
    def task(i):
        ep = eps[i % len(eps)]
        t = points[i]
        a = nearest(t)
        b = nearest(a + 1)
        fa, fb = f"{args.frames}/t{a:04d}.jpg", f"{args.frames}/t{b:04d}.jpg"
        payload = {"model": "cosmos", "messages": [{"role": "user", "content": [
            {"type": "text", "text": PROMPT},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64(fa)}"}},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64(fb)}"}}]}],
            "max_tokens": args.tokens, "temperature": 0}
        try:
            r = requests.post(ep, json=payload, timeout=90)
            ch = r.json()["choices"][0]
            m = ch["message"]
            txt = (m.get("content") or m.get("reasoning_content") or m.get("reasoning") or "").strip()
            txt = _clean(txt, ch.get("finish_reason"))
        except Exception as ex:
            txt = f"(error {str(ex)[:30]})"
        return i, {"t": t, "mmss": f"{t//60:02d}:{t%60:02d}", "narration": txt,
                   "evidence_frame": f"t{a:04d}.jpg"}

    print(f"generating {len(points)} narration points ({len(eps)} GPU) ...")
    timeline = [None] * len(points)
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=len(eps)) as ex:
        done = 0
        for i, entry in ex.map(task, range(len(points))):
            timeline[i] = entry
            done += 1
            if done % 20 == 0:
                print(f"  {done}/{len(points)}  ({time.time()-t0:.0f}s)")

    # CATCH events + evidence
    events = []
    if os.path.exists(args.events):
        for e in json.load(open(args.events, encoding="utf-8"))["events"]:
            ty = e["event_type"]
            label, sev = _TYPE_LABEL.get(ty, (ty, e.get("severity", "medium")))
            ts = _sec(e["timestamp_mmss"])
            events.append({
                "t_start": ts, "t_end": _sec(e.get("timestamp_end_mmss", e["timestamp_mmss"])),
                "mmss": e["timestamp_mmss"], "type": ty, "label": label,
                "severity": e.get("severity", sev), "description": e["description"],
                "evidence_frame": f"t{nearest(ts):04d}.jpg"})
        events.sort(key=lambda x: x["t_start"])

    out = {
        "camera_id": "CAM-A05",
        "video": "cam_a05_720p.mp4",
        "duration_sec": hi,
        "generated_by": {"model": "Cosmos-Reason2-8B", "tokens": args.tokens,
                         "step_sec": args.step, "gpu": len(eps),
                         "date": datetime.datetime.now().isoformat(timespec="seconds")},
        "timeline": timeline,
        "events": events,
    }
    json.dump(out, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\ndone in {time.time()-t0:.0f}s -> {args.out}  ({len(timeline)} narration + {len(events)} events)")


if __name__ == "__main__":
    main()
