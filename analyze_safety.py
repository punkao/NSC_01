#!/usr/bin/env python3
"""F5: Safety-rule + severity — LLM (OpenRouter/Opus) จับ event เข้า safety rulebook + ใส่ระดับความรุนแรง.
อ่าน cam_a05_timeline.json -> เติม rule_id/severity/category ให้ events[] -> เขียนกลับไฟล์เดิม.
Text-only, offline, ยิง LLM ครั้งเดียว (ไม่แตะ GPU). อ่าน key จาก .env.

Run: python analyze_safety.py
"""
import json
import os
import re

import requests

# ---- safety rulebook (ตรงกับตาราง Safety Rules ในหน้า frontend ของเพื่อน) ----
RULES = [
    {"id": "R1", "severity": "critical", "category": "Near-Miss",
     "text": "มือ/ร่างกายเข้าใกล้จุดหนีบของสายพานขณะสายพานกำลังเดิน"},
    {"id": "R2", "severity": "high", "category": "Unsafe Action",
     "text": "หยิบกระป๋องจากลัง NG (ของเสีย) กลับขึ้นสายพาน หรือใส่กระป๋องผิดลัง"},
    {"id": "R3", "severity": "high", "category": "Unsafe Condition",
     "text": "กระป๋องหล่นบนสายพานที่กำลังเดิน"},
    {"id": "R4", "severity": "high", "category": "Unsafe Action",
     "text": "ถอดหมวกหรือถุงมือออกระหว่างปฏิบัติงาน (เครื่อง/สายพานยังทำงาน)"},
    {"id": "R5", "severity": "medium", "category": "Unsafe Action",
     "text": "ไม่สวมอุปกรณ์ PPE (หมวก/ถุงมือทั้งสองข้าง/หน้ากาก) ตั้งแต่เริ่มงาน"},
    {"id": "R6", "severity": "medium", "category": "Unsafe Action",
     "text": "หน้ากากอนามัยไม่คลุมจมูกและปาก (ดึงลงใต้คาง)"},
    {"id": "R7", "severity": "medium", "category": "Unsafe Action",
     "text": "วางกระป๋องขึ้นสายพานโดยไม่ตรวจสอบด้วยสายตา (ข้ามขั้นตอนที่ 2)"},
    {"id": "R8", "severity": "medium", "category": "Unsafe Action",
     "text": "เก็บกระป๋องเข้าลัง GOOD โดยไม่เช็ดให้ครบทุกด้าน (ข้ามขั้นตอนที่ 6)"},
    {"id": "R9", "severity": "medium", "category": "Unsafe Condition",
     "text": "วางของที่ไม่เกี่ยวข้องกับงาน (ขวดน้ำ/โทรศัพท์/ของส่วนตัว) ในพื้นที่ทำงาน"},
    {"id": "R10", "severity": "low", "category": "Unsafe Action",
     "text": "บุคคลอื่นที่ไม่ใช่ผู้ปฏิบัติงานประจำสถานีเข้าพื้นที่ทำงาน"},
]
TIMELINE = "cam_a05_timeline.json"


def load_env(path=".env"):
    env = {}
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def call_llm(env, system, user, max_tokens=2000):
    r = requests.post(env["OPENROUTER_BASE_URL"] + "/chat/completions",
                      headers={"Authorization": "Bearer " + env["OPENROUTER_API_KEY"],
                               "Content-Type": "application/json",
                               "HTTP-Referer": env.get("OPENROUTER_SITE_URL", ""),
                               "X-Title": env.get("OPENROUTER_APP_NAME", "")},
                      json={"model": env["OPENROUTER_MODEL"],
                            "messages": [{"role": "system", "content": system},
                                         {"role": "user", "content": user}],
                            "max_tokens": max_tokens, "temperature": 0},
                      timeout=120)
    j = r.json()
    if "error" in j:
        raise RuntimeError(j["error"])
    return j["choices"][0]["message"]["content"]


def extract_json(txt):
    m = re.search(r"```(?:json)?\s*(.*?)```", txt, re.S)
    if m:
        txt = m.group(1)
    m = re.search(r"(\[.*\]|\{.*\})", txt, re.S)
    return json.loads(m.group(1)) if m else json.loads(txt)


def main():
    env = load_env()
    data = json.load(open(TIMELINE, encoding="utf-8"))
    events = data["events"]

    rules_txt = "\n".join(f'{r["id"]} [{r["severity"].upper()} · {r["category"]}] {r["text"]}' for r in RULES)
    ev_txt = "\n".join(f'{i}. เวลา {e["mmss"]} | {e["type"]} | {e["description"]}' for i, e in enumerate(events))

    system = ("คุณเป็นผู้เชี่ยวชาญความปลอดภัยโรงงาน. งานคือจับคู่ 'เหตุการณ์ที่ตรวจพบ' แต่ละอัน "
              "เข้ากับ 'กฎความปลอดภัย' ที่ตรงที่สุด แล้วกำหนดระดับความรุนแรงตามกฎนั้น. "
              "ตอบเป็น JSON array อย่างเดียว ไม่มีข้อความอื่น.")
    user = (f"กฎความปลอดภัย (rulebook):\n{rules_txt}\n\n"
            f"เหตุการณ์ที่ตรวจพบ:\n{ev_txt}\n\n"
            "สำหรับแต่ละเหตุการณ์ (ตาม index) จับคู่กับกฎที่ตรงที่สุด. "
            "ถ้าไม่ตรงกฎไหนเลยให้ rule_id เป็น null. "
            'ตอบ JSON array: [{"i":0,"rule_id":"R10","severity":"low","category":"Unsafe Action","reason":"เหตุผลสั้นๆ"}]')

    print(f"ยิง LLM (Opus) จับคู่ {len(events)} events เข้า rulebook ...")
    out = call_llm(env, system, user)
    mapping = {m["i"]: m for m in extract_json(out)}

    matched = 0
    for i, e in enumerate(events):
        m = mapping.get(i)
        if not m:
            continue
        e["rule_id"] = m.get("rule_id")
        if m.get("rule_id"):
            matched += 1
            e["severity"] = m.get("severity", e.get("severity"))
            e["category"] = m.get("category")
            e["rule_reason"] = m.get("reason", "")
    data["generated_by"]["safety_analysis"] = {"model": env["OPENROUTER_MODEL"], "matched": matched}
    json.dump(data, open(TIMELINE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print(f"\nจับคู่สำเร็จ {matched}/{len(events)} events -> เขียนกลับ {TIMELINE}")
    for i, e in enumerate(events):
        rid = e.get("rule_id") or "-"
        sev = e.get("severity", "?")
        print(f"  {e['mmss']} | {rid} [{sev}] | {e['description'][:45]}")


if __name__ == "__main__":
    main()
