#!/usr/bin/env python3
"""P2: rolling window narration — ไล่ทั้งวิดีโอทีละ window (2 เฟรม start+mid) ให้ Cosmos
เล่า safety สั้นๆ → narration timeline. image mode (เสถียร) + sequential (กัน engine ล้ม).

Run บน GPU box (frames ที่ /workspace/frames, Cosmos localhost). -> narration_timeline.json"""
import base64
import json
import os
import time

import requests

URL = "http://localhost:18000/v1/chat/completions"
FRAMES = "/workspace/frames"
STEP = 6      # window ทุก 6 วินาที
GAP = 3       # เฟรมที่ 2 ห่างจากเฟรมแรก 3 วินาที (ได้ temporal)
END = 216
PROMPT = (
    "ภาพ 2 เฟรมต่อเนื่อง (ห่างกัน ~3 วินาที) จากกล้อง CCTV สายการผลิตกระป๋อง (ผู้ปฏิบัติงาน 2 คน). "
    "เล่าสั้นๆ 1-2 ประโยคภาษาไทยว่าช่วงนี้เห็นอะไร และมีจุดเสี่ยงความปลอดภัยไหม "
    "(PPE หมวก/ถุงมือ/หน้ากาก, ของตก/หล่น, มือใกล้เครื่อง/สายพาน, คนแปลกหน้า). ถ้าปกติบอกสั้นๆ. ห้ามเกิน 2 ประโยค."
)


def b64(t):
    p = os.path.join(FRAMES, f"t{t:04d}.jpg")
    return base64.b64encode(open(p, "rb").read()).decode() if os.path.exists(p) else None


def narrate(t1, t2):
    a, b = b64(t1), b64(t2)
    if not a or not b:
        return None
    payload = {"model": "cosmos", "messages": [{"role": "user", "content": [
        {"type": "text", "text": PROMPT},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{a}"}},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b}"}}]}],
        "max_tokens": 160, "temperature": 0.2}
    for _ in range(2):  # retry once on transient error
        try:
            r = requests.post(URL, json=payload, timeout=120)
            j = r.json()
            if "choices" in j:
                m = j["choices"][0]["message"]
                return (m.get("content") or m.get("reasoning_content") or m.get("reasoning") or "").strip()
        except Exception:
            pass
        time.sleep(2)
    return None


def main():
    out = []
    t0 = time.time()
    for t in range(0, END, STEP):
        txt = narrate(t, t + GAP)
        mmss = f"{t // 60:02d}:{t % 60:02d}"
        out.append({"t": t, "mmss": mmss, "narration": txt or "(ไม่ได้ผล)"})
        print(f"  {mmss}  {txt or '(FAIL)'}")
        json.dump(out, open("narration_timeline.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n{len(out)} windows -> narration_timeline.json ({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()
