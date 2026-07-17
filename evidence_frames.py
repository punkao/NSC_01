#!/usr/bin/env python3
"""เลือกเฟรมหลักฐานให้เหตุการณ์ -- และรายการที่ตรวจด้วยตาแล้วว่าต้องทับค่าเริ่มต้น

ปัญหาที่เจอ (พบโดยทีมส่วนหน้าเปิดดูของจริง ไม่ใช่จากการวัดของเราเอง):
  ค่าเริ่มต้นใช้ "เฟรมแรกของช่วง" เป็นหลักฐานเสมอ ทั้ง 11 เหตุการณ์
  - ใช้ได้กับเหตุแบบ "สถานะ" (ไม่สวมหมวก = เห็นได้ทุกเฟรมตลอดช่วง)
  - ใช้ไม่ได้กับเหตุแบบ "การกระทำ" ที่เกิดเป็นจังหวะกลางช่วง
    -> near-miss ชี้ไปเฟรม 02:45 ซึ่งไม่มีใครเอามือใกล้เครื่องเลย
       ทั้งที่เฉลยระบุว่าเหตุจริงอยู่ที่ 02:55

สำคัญ: การทับนี้ **ไม่แตะเวลา ช่วง ระดับความรุนแรง หรือการจับคู่กฎ**
เปลี่ยนแค่ "รูปที่เอาไปโชว์" ให้ตรงกับเหตุที่รายงาน จึงไม่กระทบตัวเลขความแม่นยำใด ๆ

Run: python evidence_frames.py            # ดูว่าจะเปลี่ยนอะไรบ้าง
     python evidence_frames.py --apply    # เขียนลง cam_a05_timeline.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

TIMELINE = Path("cam_a05_timeline.json")

# (ชนิดเหตุการณ์, เวลาเริ่ม) -> (วินาทีของเฟรมหลักฐาน, เหตุผลที่ตรวจด้วยตาแล้ว)
# ทุกรายการต้องเปิดภาพยืนยันก่อนใส่ -- ห้ามเดา และห้ามเลือกเฟรมเพราะ "ดูดraมาติกกว่า"
# เกณฑ์: เลือกเฟรมที่ "เห็นเหตุตามที่ description เขียนไว้" และอยู่ในช่วง t_start..t_end
OVERRIDE: dict[tuple[str, str], tuple[int, str]] = {
    ("near_miss", "02:45"): (
        175,
        "เฟรมเริ่มช่วง (02:45) ทั้งสองคนอยู่ที่ลัง ไม่มีมือใกล้เครื่องเลย. "
        "เฉลยที่คนทำระบุเหตุจริงที่ 02:55 = 'Person B ยื่นมือขวาไปที่ส่วนกลางของเครื่องจักร "
        "(ขณะสายพานยังเดิน)' และเปิดภาพ t0175 ยืนยันแล้วว่าเห็นชัด",
    ),
    ("unauthorized_person", "01:36"): (
        99,
        "ที่ 01:36 บุคคลภายนอกถูกผู้ปฏิบัติงานคนที่ 1 บังไว้เกือบมิด เห็นแค่ผมกับใบหน้าบางส่วน. "
        "ที่ 01:39 ยืนเต็มตัวกลางภาพ เห็นชัดเจน และยังอยู่ในช่วงเหตุการณ์ (96-102)",
    ),
}


def pick(event_type: str, mmss: str, t_start: int) -> tuple[int, str | None]:
    """คืน (วินาทีของเฟรมหลักฐาน, เหตุผลถ้าถูกทับ)"""
    hit = OVERRIDE.get((event_type, mmss))
    if hit:
        return hit[0], hit[1]
    return t_start, None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="เขียนผลลง JSON (ไม่ใส่ = แค่ดูว่าจะเปลี่ยนอะไร)")
    a = ap.parse_args()

    d = json.loads(TIMELINE.read_text(encoding="utf-8"))
    changed = 0
    for e in d["events"]:
        t_new, why = pick(e["type"], e["mmss"], int(e["t_start"]))
        old = e["evidence_frame"]
        new = f"t{t_new:04d}.jpg"
        if not (int(e["t_start"]) <= t_new <= int(e["t_end"])):
            raise SystemExit(f"เฟรม {new} อยู่นอกช่วงเหตุการณ์ {e['mmss']} -- ผิดแน่ ๆ")
        if old != new:
            changed += 1
            print(f"  {e['mmss']} {e['type']}")
            print(f"    {old} -> {new}")
            print(f"    เหตุผล: {why}")
            e["evidence_frame"] = new
            e["evidence_note"] = why          # เก็บเหตุผลไว้ในไฟล์ ให้ตรวจย้อนได้
        else:
            print(f"  {e['mmss']} {e['type']:<20} {old}  (ใช้เฟรมเริ่มช่วง ตรวจแล้วเห็นเหตุ)")

    print(f"\nเปลี่ยน {changed} จาก {len(d['events'])} เหตุการณ์")
    if a.apply:
        TIMELINE.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"เขียนลง {TIMELINE} แล้ว")
    else:
        print("(ยังไม่เขียนไฟล์ -- ใส่ --apply ถ้าจะเขียนจริง)")


if __name__ == "__main__":
    main()
