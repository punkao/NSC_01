#!/usr/bin/env python3
"""ทดสอบ: ถ้าบอก 'layout กล่องคงที่' ใน prompt -> Cosmos ระบุกล่อง (WAIT/NG/GOOD) ถูกขึ้นไหม?
เป้า: กู้ box accuracy เพื่อให้ approach 'narration -> LLM -> SOP-skip' ใช้ได้จริง.

รันบนเครื่อง GPU (co-located) หรือผ่าน tunnel :18000. ต้องมี Cosmos serve + _frames/.
Run: python test_box_layout.py   (หรือ --url http://127.0.0.1:18000/...)

เฉลยจากเฟรมจริง (ผม verify แล้ว):
  01:53 (t0113) worker1 หยิบจาก WAIT   ← เดิม narration บอกผิดเป็น NG
  03:27 (t0207) worker1 หยิบจาก WAIT   ← เดิม narration บอกผิดเป็น NG
"""
import argparse
import base64
import os

import requests

FRAMES = "_frames"
# layout คงที่ (จากทุกเฟรม): WAIT=หน้าซ้าย, NG=ซ้ายสุด/ล่างซ้าย, GOOD=ขวา
LAYOUT = ("ผังกล่องคงที่ในภาพนี้ (จำไว้): "
          "ลัง WAIT อยู่ 'หน้า-ซ้าย' (ใกล้ล่างซ้ายของภาพ ติดป้าย WAIT), "
          "ลัง NG อยู่ 'ซ้ายสุด/มุมล่างซ้าย' (ติดป้าย NG ห่างออกไปทางซ้าย), "
          "ลัง GOOD อยู่ 'ขวา' (ติดป้าย GOOD). สายพานลำเลียงอยู่กลางภาพ.")

# เฟรมที่จะทดสอบ + เฉลย (ที่ verify จากภาพ)
CASES = [
    (113, "01:53", "WAIT"),
    (207, "03:27", "WAIT"),
    (4, "00:04", "?"),      # ช่วงเริ่ม worker1 คัดของ
    (121, "02:01", "?"),
    (132, "02:12", "?"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:18000/v1/chat/completions")
    args = ap.parse_args()

    avail = sorted(int(f[1:5]) for f in os.listdir(FRAMES) if f.startswith("t") and f.endswith(".jpg"))
    nearest = lambda s: min(avail, key=lambda x: abs(x - s))
    b64 = lambda p: base64.b64encode(open(p, "rb").read()).decode()

    prompt = (LAYOUT + " "
              "คำถาม: คน1 (ซ้าย) กำลังเอามือ 'หยิบ/ล้วง' กระป๋องจากลังไหน? "
              "ตอบชื่อลังเดียว: WAIT หรือ NG หรือ GOOD หรือ 'ไม่ได้หยิบจากลัง' "
              "แล้วบอกเหตุผลสั้นๆ 1 ประโยค (อ้างตำแหน่งมือเทียบ layout).")

    print("=== ทดสอบ box accuracy ด้วย layout-hint ===\n")
    correct = 0
    total = 0
    for t, mmss, truth in CASES:
        a = nearest(t)
        b = nearest(a + 1)
        payload = {"model": "cosmos", "messages": [{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64(f'{FRAMES}/t{a:04d}.jpg')}"}},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64(f'{FRAMES}/t{b:04d}.jpg')}"}}]}],
            "max_tokens": 120, "temperature": 0}
        try:
            r = requests.post(args.url, json=payload, timeout=60)
            m = r.json()["choices"][0]["message"]
            ans = (m.get("content") or m.get("reasoning_content") or m.get("reasoning") or "").strip()
        except Exception as ex:
            ans = f"(error {ex})"
        # เดา box ที่ Cosmos ตอบ
        said = next((box for box in ("WAIT", "NG", "GOOD") if box in ans), "?")
        mark = ""
        if truth != "?":
            total += 1
            ok = said == truth
            correct += ok
            mark = "✅ ถูก" if ok else f"❌ ผิด (ควรเป็น {truth})"
        print(f"{mmss} (เฉลย={truth}) -> Cosmos ว่า '{said}' {mark}")
        print(f"     {ans[:110]}\n")
    if total:
        print(f"=== สรุป: ถูก {correct}/{total} เคสที่มีเฉลย ===")
        print("ถ้าถูกทั้ง 2 (01:53, 03:27 = WAIT) -> layout-hint กู้ box accuracy ได้ = approach เพื่อนใช้ได้จริง")
        print("ถ้ายังผิด -> box grounding ต้องใช้ ROI/crop (งานเพิ่ม)")


if __name__ == "__main__":
    main()
