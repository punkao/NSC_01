#!/usr/bin/env python3
"""F4: SOP step-skip — LLM (OpenRouter/Opus) อ่าน narration timeline เทียบ 7 ขั้นตอน SOP
บอกว่าทำครบ/ข้ามขั้นตอนไหน. เขียน sop_compliance{} กลับ cam_a05_timeline.json.
Text-only, offline, ยิง LLM ครั้งเดียว. อ่าน key จาก .env.

⚠️ ข้อจำกัด: เช็คได้เฉพาะขั้นตอนที่เห็นด้วยตา (หยิบ/วาง/เช็ด). ขั้นตอน 'ตรวจด้วยสายตา'
และ 'ตรวจด้วย AI' คนแค่มอง VLM แยกไม่ออก -> LLM จะตอบ 'unclear'.

Run: python analyze_sop.py
"""
import json
import os
import re

import requests

from analyze_safety import call_llm, extract_json, load_env

TIMELINE = "cam_a05_timeline.json"

# 7 ขั้นตอน SOP (จากหน้า Work Steps ของเพื่อน)
STEPS = [
    "กระป๋องรอเข้ากระบวนการตรวจสอบคุณภาพ วางอยู่ในลัง WAIT",
    "worker1 หยิบกระป๋องจากลัง WAIT และตรวจสอบด้วยสายตา หากพบผิดปกติให้หยิบออกใส่ลัง NG",
    "worker1 วางกระป๋องที่สภาพดีลงบน conveyor (สายพาน)",
    "Conveyor เลื่อนกระป๋องผ่านกล้องเพื่อถ่ายรูปและตรวจสอบด้วย AI",
    "worker2 หยิบกระป๋องออกจาก conveyor",
    "worker2 เช็ดกระป๋องให้ครบทุกด้าน",
    "worker2 เก็บใส่ลัง GOOD เพื่อส่งกระบวนการถัดไป",
]


def main():
    env = load_env()
    data = json.load(open(TIMELINE, encoding="utf-8"))

    # ย่อ timeline: ตัด narration ที่ซ้ำติดกัน (ลด token, คงลำดับเวลา)
    lines, prev = [], ""
    for e in data["timeline"]:
        n = e["narration"].strip()
        if n and n != prev:
            lines.append(f'{e["mmss"]} {n}')
            prev = n
    tl_txt = "\n".join(lines)
    steps_txt = "\n".join(f"ขั้นตอนที่ {i+1}: {s}" for i, s in enumerate(STEPS))

    # กฎการทำผิดกระบวนการ (ข้าม/ย้อน/ผิดลัง) — โยงกับ safety rulebook
    VIOL_RULES = ("R2 [HIGH] หยิบกระป๋องจาก 'ลัง NG (ของเสีย)' แล้ว 'วางกลับขึ้นสายพาน' — "
                  "⚠️ เข้มงวด: นับเป็น R2 เฉพาะเมื่อ narration บอกชัดว่า 'หยิบจาก NG แล้ววาง/นำขึ้นสายพาน' ในประโยคเดียวกัน. "
                  "การแค่หยิบ/จับ/จัดเรียงกระป๋องในกล่อง NG เฉยๆ = งานคัดของเสียปกติ ไม่ใช่ violation ห้ามนับ.\n"
                  "R7 [MEDIUM] วางกระป๋องขึ้นสายพานโดยไม่ตรวจสอบด้วยสายตา (ข้ามขั้นตอน 2)\n"
                  "R8 [MEDIUM] เก็บกระป๋องเข้าลัง GOOD โดยไม่เช็ดให้ครบทุกด้าน (ข้ามขั้นตอน 6)")
    system = ("คุณเป็นผู้ตรวจสอบ SOP (มาตรฐานการทำงาน) โรงงานกระป๋อง. "
              "อ่านลำดับเหตุการณ์จาก narration แล้วทำ 2 อย่าง: "
              "(1) ประเมินว่าแต่ละขั้นตอน SOP 'ทำจริง/ข้าม/ไม่ชัด'. "
              "(2) หา 'การทำผิดกระบวนการ' ตามกฎที่ให้ — โดยเฉพาะการหยิบของจากลัง NG กลับขึ้นสายพาน (R2), "
              "วางขึ้นสายพานโดยไม่ตรวจ (R7), เก็บ GOOD โดยไม่เช็ด (R8) — ระบุเวลา (mmss) ที่เกิดขึ้น. "
              "ขั้นตอนที่เป็นการคิด/มองด้วยสายตา มักตอบ unclear เพราะดูจากภาพไม่ออก. "
              "ตอบเป็น JSON อย่างเดียว ไม่มีข้อความอื่น.")
    user = (f"ขั้นตอน SOP มาตรฐาน:\n{steps_txt}\n\n"
            f"กฎการทำผิดกระบวนการที่ต้องจับ:\n{VIOL_RULES}\n\n"
            f"ลำดับเหตุการณ์จริงจากวิดีโอ (narration ตามเวลา):\n{tl_txt}\n\n"
            "ประเมิน 7 ขั้นตอน + หาการทำผิดกระบวนการทุกครั้งที่พบใน narration. "
            'ตอบ JSON: {"steps":[{"step":1,"status":"observed|skipped|unclear","evidence_mmss":"01:34","confidence":"high|medium|low","note":"..."}],'
            '"violations":[{"mmss":"01:53","rule_id":"R2","severity":"high","description":"หยิบกระป๋องจากลัง NG กลับขึ้นสายพาน"}],'
            '"summary":"สรุป 1-2 ประโยค"}')

    print(f"ยิง LLM (Opus) อ่าน {len(lines)} narration เทียบ 7 SOP steps ...")
    out = call_llm(env, system, user, max_tokens=2500)
    result = extract_json(out)

    steps = result.get("steps", [])
    violations = result.get("violations", [])
    observed = [s["step"] for s in steps if s.get("status") == "observed"]
    skipped = [s["step"] for s in steps if s.get("status") == "skipped"]
    unclear = [s["step"] for s in steps if s.get("status") == "unclear"]
    data["sop_compliance"] = {
        "steps_observed": observed, "steps_skipped": skipped, "steps_unclear": unclear,
        "detail": steps, "process_violations": violations,
        "summary": result.get("summary", ""), "analyzed_by": env["OPENROUTER_MODEL"],
    }

    # ใส่ process violations เข้า events[] (dedupe ตาม type+mmss) ให้ demo โชว์เป็น alert
    avail = sorted(int(f[1:5]) for f in os.listdir("_frames") if f.startswith("t") and f.endswith(".jpg")) \
        if os.path.isdir("_frames") else []
    nearest = (lambda s: min(avail, key=lambda x: abs(x - s))) if avail else (lambda s: s)

    def _sec(m):
        p = str(m).split(":")
        return int(p[0]) * 60 + int(p[1]) if len(p) == 2 else 0

    # idempotent: ลบ sop_violation เก่าออกก่อน (รันซ้ำได้ ไม่สะสม)
    data["events"] = [e for e in data["events"] if e.get("type") != "sop_violation"]
    added = 0
    for v in violations:
        ts = _sec(v.get("mmss", "00:00"))
        data["events"].append({
            "t_start": ts, "t_end": ts, "mmss": v.get("mmss"),
            "type": "sop_violation", "label": "⛔ ผิดขั้นตอน",
            "severity": v.get("severity", "high"), "category": "Unsafe Action",
            "rule_id": v.get("rule_id"), "description": v.get("description", ""),
            "evidence_frame": f"t{nearest(ts):04d}.jpg"})
        added += 1
    data["events"].sort(key=lambda e: e["t_start"])
    json.dump(data, open(TIMELINE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print(f"\nทำจริง: {observed} | ข้าม: {skipped} | ไม่ชัด: {unclear}")
    print(f"สรุป: {result.get('summary','')}\n")
    for s in steps:
        icon = {"observed": "✅", "skipped": "❌", "unclear": "❓"}.get(s.get("status"), "?")
        print(f"  {icon} step {s['step']} [{s.get('confidence','?')}] @ {s.get('evidence_mmss','-')} : {s.get('note','')[:55]}")
    print(f"\n⛔ ทำผิดกระบวนการ (จับได้ {len(violations)}, เพิ่มเป็น alert {added}):")
    for v in violations:
        print(f"  {v.get('mmss')} | {v.get('rule_id')} [{v.get('severity')}] : {v.get('description','')[:55]}")
    print(f"\n-> เขียนกลับ {TIMELINE}")


if __name__ == "__main__":
    main()
