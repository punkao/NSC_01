#!/usr/bin/env python3
"""F4: SOP step-skip — LLM (OpenRouter/Opus) อ่าน narration timeline เทียบ 7 ขั้นตอน SOP
บอกว่าทำครบ/ข้ามขั้นตอนไหน. เขียน sop_compliance{} กลับ cam_a05_timeline.json.
Text-only, offline, ยิง LLM ครั้งเดียว. อ่าน key จาก .env.

⚠️ ข้อจำกัด: เช็คได้เฉพาะขั้นตอนที่เห็นด้วยตา (หยิบ/วาง/เช็ด). ขั้นตอน 'ตรวจด้วยสายตา'
และ 'ตรวจด้วย AI' คนแค่มอง VLM แยกไม่ออก -> LLM จะตอบ 'unclear'.

Run: python analyze_sop.py
"""
import json
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

    system = ("คุณเป็นผู้ตรวจสอบ SOP (มาตรฐานการทำงาน) โรงงานกระป๋อง. "
              "อ่านลำดับเหตุการณ์จาก narration แล้วประเมินว่าแต่ละขั้นตอน SOP 'ทำจริง' 'ข้าม' หรือ 'ไม่ชัด'. "
              "ขั้นตอนที่เป็นการคิด/มองด้วยสายตา (เช่น ตรวจด้วยสายตา, ตรวจด้วย AI) มักตอบ unclear เพราะดูจากภาพไม่ออก. "
              "ตอบเป็น JSON อย่างเดียว ไม่มีข้อความอื่น.")
    user = (f"ขั้นตอน SOP มาตรฐาน:\n{steps_txt}\n\n"
            f"ลำดับเหตุการณ์จริงจากวิดีโอ (narration ตามเวลา):\n{tl_txt}\n\n"
            "ประเมินแต่ละขั้นตอน (1-7). "
            'ตอบ JSON: {"steps":[{"step":1,"status":"observed|skipped|unclear",'
            '"evidence_mmss":"01:34","confidence":"high|medium|low","note":"เหตุผลสั้นๆ"}],'
            '"summary":"สรุปภาพรวมว่าข้ามขั้นตอนไหนบ้าง 1-2 ประโยค"}')

    print(f"ยิง LLM (Opus) อ่าน {len(lines)} narration เทียบ 7 SOP steps ...")
    out = call_llm(env, system, user, max_tokens=2500)
    result = extract_json(out)

    steps = result.get("steps", [])
    observed = [s["step"] for s in steps if s.get("status") == "observed"]
    skipped = [s["step"] for s in steps if s.get("status") == "skipped"]
    unclear = [s["step"] for s in steps if s.get("status") == "unclear"]
    data["sop_compliance"] = {
        "steps_observed": observed, "steps_skipped": skipped, "steps_unclear": unclear,
        "detail": steps, "summary": result.get("summary", ""),
        "analyzed_by": env["OPENROUTER_MODEL"],
    }
    json.dump(data, open(TIMELINE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print(f"\nทำจริง: {observed} | ข้าม: {skipped} | ไม่ชัด: {unclear}")
    print(f"สรุป: {result.get('summary','')}\n")
    for s in steps:
        icon = {"observed": "✅", "skipped": "❌", "unclear": "❓"}.get(s.get("status"), "?")
        print(f"  {icon} step {s['step']} [{s.get('confidence','?')}] @ {s.get('evidence_mmss','-')} : {s.get('note','')[:55]}")
    print(f"\n-> เขียน sop_compliance กลับ {TIMELINE}")


if __name__ == "__main__":
    main()
