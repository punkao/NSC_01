#!/usr/bin/env python3
"""SOP Overview (ประมาณการ) — LLM (OpenRouter/Opus) อ่าน narration timeline แล้วสรุป 'ภาพรวม'
ว่ากระบวนการเป็นไปตาม SOP ไหม — แบบ 'ประมาณการ ไม่เป๊ะ' (ตามที่เพื่อนเสนอ: ดูภาพรวม ไม่ต้องเป๊ะทีละใบ).

ต่างจาก analyze_sop.py (deprecated): ไม่แจ้ง violation เป๊ะ (ที่พลาดเรื่องกล่อง) แต่ให้
ภาพรวม + บอกชัดว่าจุดไหน 'ประเมินไม่ได้' (แยกกล่อง/การตรวจ) = ซื่อสัตย์ ไม่แจ้งผิด.

Text-only, offline, ยิง LLM ครั้งเดียว, ไม่แตะ GPU. Run: python sop_overview.py
"""
import json

from analyze_safety import call_llm, extract_json, load_env

TIMELINE = "cam_a05_timeline.json"
STEPS = [
    "กระป๋องรอในลัง WAIT",
    "worker1 หยิบจาก WAIT + ตรวจด้วยสายตา ผิดปกติใส่ NG",
    "worker1 วางกระป๋องดีลงบน conveyor",
    "Conveyor ผ่านกล้อง + ตรวจด้วย AI",
    "worker2 หยิบออกจาก conveyor",
    "worker2 เช็ดกระป๋องครบทุกด้าน",
    "worker2 เก็บใส่ลัง GOOD",
]


def main():
    env = load_env()
    data = json.load(open(TIMELINE, encoding="utf-8"))

    lines, prev = [], ""
    for e in data["timeline"]:
        n = e["narration"].strip()
        if n and n != prev:
            lines.append(f'{e["mmss"]} {n}')
            prev = n
    tl = "\n".join(lines)
    steps_txt = "\n".join(f"{i+1}. {s}" for i, s in enumerate(STEPS))

    system = ("คุณเป็นผู้ช่วยประเมินภาพรวมการทำงานตาม SOP โรงงานกระป๋อง. "
              "ให้ดู 'ภาพรวมแบบประมาณการ' ว่ากระบวนการโดยรวมเป็นไปตามลำดับ SOP ไหม — ไม่ต้องเป๊ะทีละกระป๋อง. "
              "สำคัญ: อย่าฟันธง violation ที่ต้องแยกกล่อง NG/WAIT/GOOD หรือดูการ 'ตรวจด้วยสายตา' "
              "เพราะกล้อง VLM แยกกล่อง/อ่านความตั้งใจไม่ได้ — ให้ระบุว่าสิ่งเหล่านั้น 'ประเมินไม่ได้' อย่างตรงไปตรงมา. "
              "ตอบเป็น JSON อย่างเดียว.")
    user = (f"ขั้นตอน SOP:\n{steps_txt}\n\n"
            f"narration ตามเวลา (ภาพรวมทั้งคลิป):\n{tl}\n\n"
            "สรุปภาพรวมแบบประมาณการ. "
            'ตอบ JSON: {"overall":"สรุปภาพรวม 2-3 ประโยคว่ากระบวนการโดยรวมตามลำดับ SOP ไหม",'
            '"steps":[{"step":1,"assessment":"observed|partial|cannot_assess","note":"สั้นๆ"}],'
            '"cannot_verify":["สิ่งที่ VLM ประเมินไม่ได้ เช่น การแยกกล่อง NG/WAIT/GOOD, การตรวจด้วยสายตา"],'
            '"note_for_human":"จุดที่ควรให้คนตรวจซ้ำ"}')

    print("ยิง LLM (Opus) สรุปภาพรวม SOP (ประมาณการ) ...")
    result = extract_json(call_llm(env, system, user, max_tokens=1500))
    result["disclaimer"] = "ประมาณการจาก AI (VLM+LLM) — ไม่ใช่คำตัดสิน จุดที่ไม่ชัดควรให้คนตรวจ"
    result["by"] = env["OPENROUTER_MODEL"]
    data["sop_overview"] = result
    json.dump(data, open(TIMELINE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print(f"\n📋 ภาพรวม: {result.get('overall','')}\n")
    ic = {"observed": "✅", "partial": "🔶", "cannot_assess": "❓"}
    for s in result.get("steps", []):
        print(f"  {ic.get(s.get('assessment'),'?')} step {s['step']}: {s.get('note','')[:55]}")
    print(f"\n❓ ประเมินไม่ได้: {', '.join(result.get('cannot_verify',[]))}")
    print(f"👤 ควรให้คนตรวจ: {result.get('note_for_human','')}")
    print(f"\n-> เขียน sop_overview กลับ {TIMELINE}")


if __name__ == "__main__":
    main()
