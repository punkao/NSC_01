#!/usr/bin/env python3
"""Late fusion — เติม "ชื่อลังจริง" ลง narration โดยใช้ผลตรวจ ROI (ไม่ใช่การเดาของ VLM).

== ทำไมต้องทำแบบนี้ ==
SOP ต้องรู้ว่า "หยิบจากลังไหน" -> narration ต้องบอกชื่อลัง
แต่ Cosmos อ่านป้ายลังเองแล้วผิด 66% (146/220 จุด) -> ห้ามให้มันเรียกชื่อลังเอง (ดู FINDINGS_SOP.md)

== วิธี: แยกหน้าที่ แล้วค่อยประกอบ ==
  Cosmos  -> "คน1 หยิบกระป๋องจาก[ลังฝั่งซ้าย]"   = การกระทำ + ฝั่ง (สิ่งที่มันแม่น ไม่เคยผิด)
  ROI+โค้ด -> t=0: WAIT=true, NG=false            = ลังไหน (วัดจริง, validate 7/7)
  ประกอบ  -> "คน1 หยิบกระป๋องจากลัง WAIT"        = ถูกทั้งการกระทำและชื่อลัง

** นี่ไม่ใช่การยัดคำตอบ ** ชื่อลังมาจากการตรวจจับจริงของระบบ ไม่ใช่จากเฉลยที่มนุษย์รู้
   ถ้าวันหน้ามีคนหยิบจากลัง NG จริง ROI จะเห็น -> ระบบก็จะเขียนว่า "ลัง NG" เอง

== กฎ (ไม่ชัดห้ามเติม) ==
  ฝั่งขวา  -> มีลังเดียว = GOOD (จริงตาม layout) -> เติมได้เสมอ
  ฝั่งซ้าย  -> มี 2 ลัง (WAIT/NG) -> เติมเฉพาะเมื่อ ROI เห็นมือใน "ลังเดียว" เท่านั้น
             ถ้าเห็นทั้งคู่ (มือเอื้อมคร่อม) หรือไม่เห็นเลย -> คงคำกลางๆ "ลังฝั่งซ้าย" ไว้

เก็บ narration_vlm (คำพูดดิบของ Cosmos) ไว้ด้วยเสมอ -> ตรวจสอบย้อนหลังได้ว่าอะไรมาจากใคร
Run: python compose_narration.py     (ไม่ใช้ GPU)
"""
import argparse
import json

TIMELINE = "cam_a05_timeline.json"
LEFT, RIGHT = "ลังฝั่งซ้าย", "ลังฝั่งขวา"


def compose(narration: str, act: dict | None) -> tuple[str, str]:
    """คืน (ประโยคที่ประกอบแล้ว, ที่มาของชื่อลัง)."""
    out, src = narration, []
    if RIGHT in out:                       # ฝั่งขวามีลังเดียว -> GOOD แน่นอนตาม layout
        out = out.replace(RIGHT, "ลัง GOOD")
        src.append("GOOD:layout")
    if LEFT in out and act:
        hit = [b for b in ("WAIT", "NG") if act.get(b)]
        if len(hit) == 1:                  # ROI เห็นมือในลังเดียว -> ระบุได้
            out = out.replace(LEFT, f"ลัง {hit[0]}")
            src.append(f"{hit[0]}:roi")
        elif len(hit) == 2:                # มือคร่อม 2 ลัง -> ไม่ชัด ห้ามเดา
            src.append("left:ambiguous")
        else:
            src.append("left:no_hand")     # ไม่มีมือในลัง -> narration พูดลอยๆ ห้ามเติม
    return out, "+".join(src) if src else "none"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeline", default=TIMELINE)
    a = ap.parse_args()
    d = json.load(open(a.timeline, encoding="utf-8"))
    ba = d.get("box_activity", {})

    stats = {"WAIT": 0, "NG": 0, "GOOD": 0, "ambiguous": 0, "no_hand": 0}
    for e in d["timeline"]:
        raw = e.get("narration_vlm", e["narration"])   # rerun ได้ ไม่ทับของเดิม
        new, src = compose(raw, ba.get(str(e["t"])))
        e["narration_vlm"] = raw          # คำพูดดิบของ Cosmos (audit trail)
        e["narration"] = new              # ที่ demo เอาไปโชว์
        e["box_source"] = src
        for k in stats:
            if k in src:
                stats[k] += 1

    d["generated_by"]["narration_composition"] = {
        "method": "late fusion — Cosmos พูดการกระทำ/ฝั่ง, ROI ระบุชื่อลัง แล้วโค้ดประกอบ",
        "why": "Cosmos อ่านป้ายลังเองผิด 146/220 (66%) จาก attribute-binding -> ไม่ให้มันเรียกชื่อลัง",
        "rule": "เติมชื่อลังเฉพาะเมื่อ ROI เห็นมือใน 'ลังเดียว'; กำกวม/ไม่เห็นมือ -> คงคำว่า 'ลังฝั่งซ้าย'",
        "audit": "narration_vlm = คำพูดดิบของ Cosmos, box_source = ชื่อลังนี้มาจากไหน",
    }
    json.dump(d, open(a.timeline, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    n = len(d["timeline"])
    print(f"ประกอบ narration {n} จุด:")
    print(f"  เติม 'ลัง WAIT' (ROI ยืนยัน)  : {stats['WAIT']}")
    print(f"  เติม 'ลัง NG'   (ROI ยืนยัน)  : {stats['NG']}")
    print(f"  เติม 'ลัง GOOD' (layout)      : {stats['GOOD']}")
    print(f"  คงคำกลางๆ - มือคร่อม 2 ลัง    : {stats['ambiguous']}")
    print(f"  คงคำกลางๆ - ไม่เห็นมือในลัง   : {stats['no_hand']}")
    print("\nตัวอย่าง:")
    for t in (0, 4, 107, 140):
        e = next((x for x in d["timeline"] if x["t"] == t), None)
        if e:
            print(f"  {e['mmss']} [{e['box_source']}]")
            print(f"    Cosmos : {e['narration_vlm'][:74]}")
            print(f"    ประกอบ : {e['narration'][:74]}")
    print(f"\n-> เขียนกลับ {a.timeline} (narration=ประกอบแล้ว, narration_vlm=ดิบ)")


if __name__ == "__main__":
    main()
