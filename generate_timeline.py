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
import re
import time
from concurrent.futures import ThreadPoolExecutor

import requests

from test_box_layout import LAYOUT  # ผังลังตัวเดียวกับที่ A/B ทดสอบ (single source of truth)

PROMPT = (
    "ภาพ 2 เฟรมต่อเนื่อง กล้อง CCTV โรงงานกระป๋อง (คน1 ซ้าย คน2 ขวา). "
    "บรรยายภาษาไทยล้วน 1-2 ประโยคสั้นกระชับ จบประโยคให้สมบูรณ์ "
    "ว่าตอนนี้เห็นอะไร คนกำลังทำอะไร และมีจุดเสี่ยงความปลอดภัยไหม."
)

# กันมั่ว: ถ้าไม่ชัดว่าลังไหน ให้เรียกกลางๆ ดีกว่าเดาผิด (เดิมพลาด 146/220 จุด = บอก NG ทั้งที่เป็น WAIT)
NO_GUESS = " ถ้าไม่เห็นป้ายลังชัดเจน ห้ามเดาชื่อลัง ให้เรียกว่า 'ลังฝั่งซ้าย' หรือ 'ลังฝั่งขวา' แทน."

# ห้ามเอ่ยชื่อลังเลย — ใช้คู่กับ _strip_box_names() เพราะ prompt อย่างเดียวยัง 'หลุด' (วัดแล้ว 1/4 เคส)
BAN_BOX = (" กฎเด็ดขาด: ห้ามใช้คำว่า NG, WAIT, GOOD หรือเอ่ยชื่อ/ป้ายของลังใดๆ ในคำบรรยาย "
           "ให้เรียกว่า 'ลังฝั่งซ้าย' หรือ 'ลังฝั่งขวา' เท่านั้น.")

# ผังจริง: NG+WAIT อยู่ฝั่งซ้าย, GOOD อยู่ฝั่งขวา -> map ชื่อลัง (ที่เชื่อไม่ได้) เป็น 'ฝั่ง' (ที่เชื่อได้)
_SIDE = {"NG": "ซ้าย", "WAIT": "ซ้าย", "GOOD": "ขวา"}
_BOX_RE = re.compile(r"(?:(?:กล่อง|ลัง)(?:กระดาษ)?(?:สี\S+?)?\s*)?(?:ที่)?(?:มี)?ป้าย\s*['\"‘’“”]?(NG|WAIT|GOOD)['\"‘’“”]?"
                     r"|(?:กล่อง|ลัง)\s*['\"‘’“”]?(NG|WAIT|GOOD)['\"‘’“”]?"
                     r"|['\"‘’“”]?\b(NG|WAIT|GOOD)\b['\"‘’“”]?")


def _strip_box_names(txt: str) -> str:
    """ลบชื่อลังออกจาก narration แบบ deterministic — โมเดลระบุลังผิด (verify แล้ว) จึงห้ามยืนยันชื่อลัง.
    แทนด้วย 'ลังฝั่งซ้าย/ขวา' ซึ่งเป็นข้อมูลที่ VLM ระบุถูก (คน1=ซ้าย, คน2=ขวา, GOOD=ขวาลังเดียว)."""
    def sub(m: re.Match) -> str:
        box = m.group(1) or m.group(2) or m.group(3)
        return f"ลังฝั่ง{_SIDE[box]}"
    out = _BOX_RE.sub(sub, txt)
    return re.sub(r"\s{2,}", " ", out).strip()


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
    ap.add_argument("--tokens", type=int, default=150)  # ตรงกับ live_demo_combined.py (จบประโยคสวย ไม่ตัดคำ)
    ap.add_argument("--step", type=int, default=1, help="ทุกกี่วินาที (1 = per-second)")
    ap.add_argument("--layout-hint", action="store_true",
                    help="ใส่ผังลัง (WAIT/NG/GOOD) + กันเดา ลงหัว prompt — ใช้เมื่อ test_box_layout.py ผ่าน")
    ap.add_argument("--no-box-names", action="store_true",
                    help="ห้ามเอ่ยชื่อลัง + กรองซ้ำแบบ deterministic (แนะนำ: prompt อย่างเดียวยังหลุด)")
    args = ap.parse_args()

    if args.no_box_names:
        prompt = PROMPT + BAN_BOX
    elif args.layout_hint:
        prompt = LAYOUT + " " + PROMPT + NO_GUESS
    else:
        prompt = PROMPT

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
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64(fa)}"}},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64(fb)}"}}]}],
            "max_tokens": args.tokens, "temperature": 0}
        try:
            r = requests.post(ep, json=payload, timeout=90)
            ch = r.json()["choices"][0]
            m = ch["message"]
            txt = (m.get("content") or m.get("reasoning_content") or m.get("reasoning") or "").strip()
            txt = _clean(txt, ch.get("finish_reason"))
            if args.no_box_names:
                txt = _strip_box_names(txt)  # กันหลุด: prompt เชื่อ 100% ไม่ได้
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
                         "layout_hint": args.layout_hint, "no_box_names": args.no_box_names,
                         "date": datetime.datetime.now().isoformat(timespec="seconds")},
        "timeline": timeline,
        "events": events,
    }
    json.dump(out, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\ndone in {time.time()-t0:.0f}s -> {args.out}  ({len(timeline)} narration + {len(events)} events)")


if __name__ == "__main__":
    main()
