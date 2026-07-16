#!/usr/bin/env python3
"""SOP box-grounding — "ใครไปยุ่งกับลังไหน เมื่อไหร่" แบบที่เชื่อถือได้จริง.

== ปัญหาที่แก้ (ดู FINDINGS_SOP.md) ==
ถามภาพเต็มว่า "หยิบจากลังไหน" -> Cosmos ตอบผิด 146/220 จุด (66%) เพราะลัง WAIT/NG วางชิดกัน
251px (ฝั่ง GOOD ลังเดียว ห่าง 1053px -> ไม่เคยผิดเลย) = attribute-binding failure ของ VLM
ลองแก้ 4 วิธีแล้วไม่ผ่าน: layout-hint / สั่งห้ามเอ่ยชื่อลัง / ROI+yes-no ตรงๆ / บอกความรู้โดเมน

== วิธีที่ใช้แทน: เอางาน "ระบุลัง" ออกจากมือ VLM ==
  1. ROI (โค้ด) : กล้องนิ่ง ลังอยู่กับที่ -> crop ทีละลัง = "ลังไหน" มาจากโค้ด 100%
  2. VLM        : ตอบแค่ "มีมือในกรอบนี้ไหม" (งานง่ายสุด) -> validate แล้วตรง 7/7, FP=0
  -> ได้ข้อมูลที่เชื่อได้: "มือยุ่งกับลัง X ที่วินาที T"

== สิ่งที่ "ไม่" ทำ และเหตุผล (สำคัญ — เคยลองแล้วถอน) ==
เคยลองแยก "ใส่ลง" vs "หยิบออก" ด้วยการวัด %พื้นที่สว่างในลัง (นับกระป๋อง) -> ใช้ไม่ได้:
  ช่วง 1:56-2:03 กระป๋อง 4 ใบเท่าเดิมทั้งช่วง แต่ค่าแกว่ง 17.2% -> 7.7% (เงาคน/กล้องปรับแสง)
  = noise (8%) ใหญ่กว่า signal (3%) และค่าขัดแย้งกันเอง (4 ใบ ได้ค่าน้อยกว่า 0 ใบ)
  -> จึง "ไม่เดา" แต่ยกธงให้คนตรวจแทน = ซื่อสัตย์กว่าและยังมีประโยชน์
  (คลิปมีรอยตัดต่อจริงที่ ~2:17 ของในลังเปลี่ยนเพราะจัดฉากใหม่ ยิ่งทำให้นับของไม่ได้)

Input : roi_scan.json (จาก roi_scan.py บน GPU)
Output: เขียน box_activity / sop_events / sop_findings ลง cam_a05_timeline.json
Run   : python sop_roi.py        (ไม่ใช้ GPU)
"""
import argparse
import json

TIMELINE = "cam_a05_timeline.json"
SCAN = "roi_scan.json"
GAP = 2  # วินาทีห่างสุดที่ยังนับเป็นเหตุการณ์เดียวกัน

# ลังไหน = ใครควรยุ่ง + ยุ่งแล้วแปลว่าอะไร (ตาม SOP)
BOX_MEANING = {
    "WAIT": {"who": "คน1 (ซ้าย)", "expected": True,
             "note": "มือคน1 อยู่ในลัง WAIT = หยิบกระป๋องมาตรวจ (SOP ขั้น 2) — เป็นเรื่องปกติ",
             "needs_review": False},
    "NG": {"who": "คน1 (ซ้าย)", "expected": False,
           "note": "มีมือไปยุ่งกับลัง NG — อาจเป็นการใส่ของเสียลง (ถูก SOP) หรือหยิบกลับออกมา (ผิด R2) "
                   "ระบบแยกไม่ได้จากภาพ -> ให้คนตรวจยืนยันจากเฟรมหลักฐาน",
           "needs_review": True},
}


def episodes(seconds: list[int]) -> list[list[int]]:
    """รวมวินาทีที่ติดกันเป็นเหตุการณ์เดียว (มือยุ่ง 1 ครั้งกินหลายวินาที)."""
    out: list[list[int]] = []
    for t in sorted(seconds):
        if out and t - out[-1][-1] <= GAP:
            out[-1].append(t)
        else:
            out.append([t])
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan", default=SCAN)
    ap.add_argument("--timeline", default=TIMELINE)
    a = ap.parse_args()

    scan = json.load(open(a.scan))
    n = max(int(t) for t in scan) + 1
    mmss = lambda t: f"{t//60:02d}:{t%60:02d}"

    sop_events = []
    counts = {}
    for box, meaning in BOX_MEANING.items():
        eps = episodes([int(t) for t in scan if scan[t][box] == "yes"])
        counts[box] = len(eps)
        for ep in eps:
            sop_events.append({
                "t_start": ep[0], "t_end": ep[-1], "mmss": mmss(ep[0]),
                "box": box, "who": meaning["who"],
                "detected": "hand_interaction",   # นี่คือสิ่งที่ยืนยันได้จริง
                "note": meaning["note"],
                "needs_review": meaning["needs_review"],
                "evidence_frame": f"t{ep[0]:04d}.jpg",
            })
    sop_events.sort(key=lambda e: e["t_start"])
    review = [e for e in sop_events if e["needs_review"]]

    findings = {
        "wait_interactions": counts["WAIT"],
        "ng_interactions": counts["NG"],
        "ng_review_times": [e["mmss"] for e in review],
        "verified": ("ตรวจได้ว่า 'มือไปยุ่งกับลังไหน เมื่อไหร่' — ชื่อลังมาจาก ROI ที่โค้ดกำหนด "
                     "(กล้องนิ่ง ลังอยู่กับที่) ส่วน VLM ตอบแค่ 'มีมือไหม'"),
        "not_verified": ("แยกไม่ได้ว่า 'ใส่ลง' หรือ 'หยิบออก' — ลองวัดปริมาณของในลังด้วย pixel แล้ว "
                         "แต่เงาคน/กล้องปรับแสงทำให้ค่าแกว่งแรงกว่าสัญญาณจริง 3 เท่า (ถอนออก) "
                         "และคลิปมีรอยตัดต่อ (~02:17) ที่ของในลังเปลี่ยนเพราะจัดฉากใหม่"),
        "human_review_needed": len(review),
        "why_not_vlm_labels": ("ไม่ให้ VLM อ่านป้ายลังเอง เพราะวัดแล้วผิด 146/220 จุด (66%) "
                               "จาก attribute-binding: ลัง WAIT/NG ห่างกันแค่ 251px และเล็ก (4.5% ของภาพ) "
                               "ส่วนลัง GOOD ที่อยู่เดี่ยวห่าง 1053px โมเดลไม่เคยเรียกผิดเลย"),
        "validation": "จุดที่ระบบแจ้งมือในลัง NG ตรงกับการไล่ดูเฟรมด้วยคน 7/7 (false positive = 0)",
    }

    data = json.load(open(a.timeline, encoding="utf-8"))
    data["box_activity"] = {str(t): {"WAIT": scan[str(t)]["WAIT"] == "yes",
                                     "NG": scan[str(t)]["NG"] == "yes"} for t in range(n)}
    data["sop_events"] = sop_events
    data["sop_findings"] = findings
    json.dump(data, open(a.timeline, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print(f"มือยุ่งกับลัง WAIT : {counts['WAIT']} ครั้ง  (= หยิบมาตรวจ ตาม SOP ขั้น 2)")
    print(f"มือยุ่งกับลัง NG   : {counts['NG']} ครั้ง  -> ยกธงให้คนตรวจ")
    print(f"\nจุดที่ต้องให้คนดู ({len(review)} จุด, ดูรูปหลักฐาน 10 วิ จบ):")
    for e in review:
        print(f"  {e['mmss']}  ->  {e['evidence_frame']}")
    print(f"\n-> เขียน box_activity ({n} วิ) + sop_events ({len(sop_events)}) + sop_findings ลง {a.timeline}")


if __name__ == "__main__":
    main()
