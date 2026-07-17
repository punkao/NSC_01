#!/usr/bin/env python3
"""ตรวจผลการระบุลัง (8/8) จากคำตอบที่บันทึกไว้ -- ไม่ต้องใช้ GPU

ทำไมต้องมี: เลข 8/8 ในรายงานเคยเป็นเลขลอย ไม่มีคำสั่งไหนพ่นออกมาได้
(และเคยเขียนผิดเป็น 7/7 มาแล้ว) สคริปต์นี้ทำให้ตรวจซ้ำได้เหมือนเลขอื่นในรายงาน

⚠️ กับดักที่ต้องระวัง -- เฟรมสองชุดคนละจังหวะกัน:
  _frames       แตกด้วย `ffmpeg -ss <t>`               -> ใช้กับเฉลย PPE
  _frames_full  แตกด้วย `ffmpeg -vf fps=1 -start_number 0` -> ใช้กับ ROI/คำบรรยาย
ที่ t=4 สองชุดนี้ต่างกันจนเป็นคนละเหตุการณ์ (_frames มืออยู่นอกลัง /
_frames_full มืออยู่ในลัง WAIT) เอามาเทียบข้ามชุดจะได้ 5/8 แล้วสรุปผิดว่าโมเดลแย่
roi_scan.py รันบน _frames_full -> เฉลยที่ใช้เทียบต้องมาจาก _frames_full ด้วย

Run: python verify_roi.py            # ตรวจ 8/8
     python verify_roi.py --dump     # + เขียนภาพหลักฐานให้ดูด้วยตา
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

SCAN = Path("roi_scan.json")
FRAMES = "_frames_full"  # ห้ามเปลี่ยนเป็น _frames -- ดูหมายเหตุด้านบน
ROI = {"WAIT": (170, 610, 555, 850), "NG": (60, 855, 485, 1075)}

# เฉลย: ไล่ดูด้วยตาบนเฟรม _frames_full (ชุดเดียวกับที่ roi_scan.py รัน)
# ยืนยันซ้ำ 2026-07-17 ด้วยการเปิดภาพครอบดูทีละจุด
CASES = [
    (4, {"WAIT": "yes", "NG": "no"}),    # มือคนที่ 1 อยู่ในลัง WAIT กำลังหยิบกระป๋อง · NG ว่าง
    (113, {"WAIT": "yes", "NG": "no"}),  # มือคนที่ 1 อยู่ในลัง WAIT ถือกระป๋อง
    (121, {"WAIT": "no", "NG": "no"}),   # มืออยู่เหนือลัง ไม่ได้ยื่นเข้าไปในลัง
    (207, {"WAIT": "no", "NG": "no"}),   # มืออยู่นอกลัง
]


def dump_evidence(scan: dict) -> None:
    """เขียนภาพครอบพร้อมคำตอบของแบบจำลอง เพื่อให้คนเปิดตรวจซ้ำได้"""
    from PIL import Image, ImageDraw

    out = Path("_audit_roi")
    out.mkdir(exist_ok=True)
    for t, _truth in CASES:
        im = Image.open(f"{FRAMES}/t{t:04d}.jpg").convert("RGB")
        d = ImageDraw.Draw(im)
        for box, r in ROI.items():
            ans = scan[str(t)][box]
            col = (255, 60, 60) if ans == "yes" else (0, 255, 0)
            d.rectangle(r, outline=col, width=6)
            d.text((r[0] + 8, r[1] + 8), f"{box}: {ans}", fill=col)
        im.crop((0, 560, 900, 1080)).save(out / f"t{t:04d}.png")
    print(f"เขียนภาพหลักฐานไว้ที่ {out}/")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", action="store_true", help="เขียนภาพหลักฐานให้ตรวจด้วยตา")
    a = ap.parse_args()

    scan = json.loads(SCAN.read_text(encoding="utf-8"))
    ok = tot = fp = fn = 0
    print(f"เฉลย: ไล่ดูด้วยตาบนเฟรม {FRAMES}  |  คำตอบแบบจำลอง: {SCAN}")
    print("=" * 62)
    for t, truth in CASES:
        got = scan.get(str(t), {})
        for box, exp in truth.items():
            g = got.get(box)
            hit = g == exp
            ok += hit
            tot += 1
            fp += exp == "no" and g == "yes"
            fn += exp == "yes" and g == "no"
            mark = "ถูก" if hit else "ผิด"
            print(f"  {t // 60}:{t % 60:02d}  {box:<5} เฉลย={exp:<3} แบบจำลอง={str(g):<4} {mark}")
    print("=" * 62)
    print(f"  ตรง {ok}/{tot}  ·  แจ้งผิด {fp}  ·  แจ้งขาด {fn}")
    print()
    print(f"  หมายเหตุ: ฐานเล็ก -- {len(CASES)} จุดเวลา × {len(ROI)} ลัง = {tot} การตรวจ")
    neg = sum(1 for _t, tr in CASES for v in tr.values() if v == "no")
    print(f"  และ {neg} ใน {tot} เป็นคำตอบ 'ไม่มีมือ' ซึ่งตอบถูกง่ายกว่า")
    print("  อ่านว่า 'ในจุดที่ตรวจแล้วยังไม่พบข้อผิดพลาด' ไม่ใช่ 'แม่นยำ 100%'")

    if a.dump:
        dump_evidence(scan)


if __name__ == "__main__":
    main()
