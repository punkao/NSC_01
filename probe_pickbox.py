#!/usr/bin/env python3
"""Pass-2 (แยกจาก narration): ถามเจาะจง 'คน1 หยิบกระป๋องจากลังไหน' ทุกวินาที.

ทำไมแยก pass: งาน narration แบบเล่าอิสระ โมเดลพ่นชื่อลังมั่ว (verify แล้ว 146/220 ผิด)
แต่พอ 'ถามเจาะจง + ให้ผังลัง' มันตอบถูก 3/3 ในเคสที่ verify -> เอามาทำเป็น field แยก
ผลไปเติม timeline เป็น pick_box เพื่อให้ SOP ประเมินขั้นที่ต้องรู้ลังได้

เฉลยระดับคลิป (เจ้าของวิดีโอยืนยัน): คน1 หยิบจากลัง WAIT เสมอ
-> ถ้าโมเดลตอบ NG บ่อย = ยังมั่ว, ถ้าตอบ WAIT เกือบหมด = ใช้ได้
"""
import argparse
import base64
import json
import time
from concurrent.futures import ThreadPoolExecutor

import requests

from test_box_layout import LAYOUT

Q = (LAYOUT + " คำถาม: ในภาพนี้ 'คน1 (คนซ้าย)' กำลังหยิบ/ล้วงกระป๋องจากลังไหน? "
     "ตอบสั้นที่สุดคำเดียว: WAIT หรือ NG หรือ GOOD หรือ NONE (ถ้าไม่ได้หยิบจากลังใดเลย)")


def parse(txt: str) -> str:
    t = txt.upper()
    for k in ("NONE", "ไม่ได้หยิบ"):
        if k in t or k in txt:
            return "NONE"
    pos = {b: t.find(b) for b in ("WAIT", "NG", "GOOD") if t.find(b) >= 0}
    return min(pos, key=pos.get) if pos else "?"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--endpoints", required=True)
    ap.add_argument("--frames", default="/workspace/frames")
    ap.add_argument("--out", default="pickbox.json")
    a = ap.parse_args()
    eps = [e.strip() for e in a.endpoints.split(",") if e.strip()]
    b64 = lambda p: base64.b64encode(open(p, "rb").read()).decode()
    pts = list(range(0, 219))

    def task(i: int):
        t = pts[i]
        pl = {"model": "cosmos", "messages": [{"role": "user", "content": [
            {"type": "text", "text": Q},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64(f'{a.frames}/t{t:04d}.jpg')}"}},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64(f'{a.frames}/t{t+1:04d}.jpg')}"}}]}],
            "max_tokens": 30, "temperature": 0}
        try:
            m = requests.post(eps[i % len(eps)], json=pl, timeout=90).json()["choices"][0]["message"]
            txt = (m.get("content") or m.get("reasoning") or m.get("reasoning_content") or "").strip()
            return i, {"t": t, "box": parse(txt), "raw": txt[:40]}
        except Exception as ex:
            return i, {"t": t, "box": "?", "raw": str(ex)[:30]}

    res = [None] * len(pts)
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=len(eps)) as ex:
        for i, r in ex.map(task, range(len(pts))):
            res[i] = r
    json.dump(res, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    from collections import Counter
    c = Counter(r["box"] for r in res)
    print(f"\ndone {len(res)} จุด ใน {time.time()-t0:.0f}s")
    print("การกระจายคำตอบ:", dict(c))
    print("\nเฉลย: คน1 หยิบจาก WAIT เสมอ -> NG ควรน้อยมาก/ไม่มี")
    for t in (4, 113, 121, 207):
        r = next(x for x in res if x["t"] == t)
        print(f"  t{t:04d}: {r['box']}")


if __name__ == "__main__":
    main()
