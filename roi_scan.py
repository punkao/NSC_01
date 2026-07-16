#!/usr/bin/env python3
"""สแกน ROI grounding ทั้งคลิป: ถามทีละลัง (crop) ว่า 'มีมือยุ่งกับกระป๋องในลังนี้ไหม'.

ชื่อลัง = มาจาก ROI ที่โค้ดนิยาม (ไม่ใช่โมเดลอ่านป้าย) -> ตัดปัญหา attribute-binding ทิ้ง
กล้องนิ่ง + ลังอยู่กับที่ -> ROI คงที่ (ตรวจด้วยตาแล้วทั้ง 220 เฟรม)
"""
import argparse
import base64
import io
import json
import time
from concurrent.futures import ThreadPoolExecutor

import requests
from PIL import Image

ROI = {"WAIT": (170, 610, 555, 850), "NG": (60, 855, 485, 1075)}
UPSCALE = 2
Q = ("ภาพนี้คือลังใส่กระป๋องในโรงงาน (2 เฟรมต่อเนื่อง ซูมเฉพาะลังนี้). "
     "คำถาม: เห็น 'มือคน' (สวมถุงมือสีขาว) ยื่นเข้ามาในลังนี้ หรือกำลังจับ/หยิบ/วางกระป๋องในลังนี้ หรือไม่? "
     "คิดสั้นๆ แล้วลงท้ายด้วยบรรทัดสุดท้ายว่า 'คำตอบ: ใช่' หรือ 'คำตอบ: ไม่ใช่' เท่านั้น")


def _b64(img: Image.Image) -> str:
    b = io.BytesIO()
    img.save(b, format="JPEG", quality=92)
    return base64.b64encode(b.getvalue()).decode()


def parse(txt: str) -> str:
    tail = txt[txt.rfind("คำตอบ"):] if "คำตอบ" in txt else txt[-40:]
    if "ไม่ใช่" in tail:
        return "no"
    if "ใช่" in tail:
        return "yes"
    return "?"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--endpoints", required=True)
    ap.add_argument("--frames", default="/workspace/frames")
    ap.add_argument("--out", default="roi_scan.json")
    a = ap.parse_args()
    eps = [e.strip() for e in a.endpoints.split(",") if e.strip()]
    jobs = [(t, box) for t in range(0, 219) for box in ("WAIT", "NG")]

    def task(i: int):
        t, box = jobs[i]
        r = ROI[box]
        imgs = []
        for s in (t, t + 1):
            c = Image.open(f"{a.frames}/t{s:04d}.jpg").crop(r)
            imgs.append(c.resize((c.width * UPSCALE, c.height * UPSCALE), Image.LANCZOS))
        pl = {"model": "cosmos", "messages": [{"role": "user", "content":
            [{"type": "text", "text": Q}] +
            [{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{_b64(im)}"}} for im in imgs]}],
            "max_tokens": 200, "temperature": 0}
        try:
            m = requests.post(eps[i % len(eps)], json=pl, timeout=90).json()["choices"][0]["message"]
            txt = (m.get("content") or m.get("reasoning") or m.get("reasoning_content") or "").strip()
            return i, parse(txt)
        except Exception:
            return i, "?"

    res = [None] * len(jobs)
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=len(eps)) as ex:
        done = 0
        for i, v in ex.map(task, range(len(jobs))):
            res[i] = v
            done += 1
            if done % 100 == 0:
                print(f"  {done}/{len(jobs)} ({time.time()-t0:.0f}s)")

    out = {}
    for (t, box), v in zip(jobs, res):
        out.setdefault(str(t), {})[box] = v
    json.dump(out, open(a.out, "w"), indent=0)
    from collections import Counter
    for box in ("WAIT", "NG"):
        c = Counter(out[k][box] for k in out)
        print(f"{box}: {dict(c)}")
    print(f"done {len(jobs)} calls in {time.time()-t0:.0f}s -> {a.out}")


if __name__ == "__main__":
    main()
