#!/usr/bin/env python3
"""เช็คตัว LIVE (narration+tagger) อย่างเป็นระบบ — รันทุก 3วิ ทั้งวิดีโอ เก็บ narration+catches
เพื่อเทียบว่า "พลาดอะไร เวลาไหน" เทียบ GT. Run บน GPU box (Cosmos + /workspace/frames)."""
import base64
import json
import os
import re

import requests

URL = "http://localhost:18000/v1/chat/completions"
FR = "/workspace/frames"
PROMPT = (
    "ภาพ 2 เฟรมต่อเนื่อง (~3วิ) กล้อง CCTV โรงงานกระป๋อง (คน1 ซ้าย, คน2 ขวา). ตรวจทีละจุดก่อนสรุป: "
    "แต่ละคนสวมหมวก/ถุงมือ/หน้ากากครบไหม (ใครถอด?), มีมือใกล้สายพาน/เครื่องไหม, มีของหล่น/คนแปลกหน้าไหม. "
    "แล้วเล่าสั้นๆ 1-2 ประโยคภาษาไทย เน้นจุดเสี่ยงถ้ามี."
)


def tag(t):
    out = []
    if any(k in t for k in ("ผู้หญิง", "บุคคลที่สาม", "คนที่สาม")):
        out.append("person")
    if any(k in t for k in ("ถอดหน้ากาก", "ไม่สวมหน้ากาก", "ถอดหมวก", "ไม่สวมหมวก",
                            "ถอดถุงมือ", "ไม่สวมถุงมือ", "ดึงหน้ากาก", "หน้ากากออก")):
        out.append("ppe")
    if (re.search(r"มือ[^.]{0,22}(ใกล้|เข้าใกล้|มากเกินไป)[^.]{0,18}(สายพาน|เครื่อง)", t) or "หนีบ" in t):
        if not re.search(r"(ไม่มี|ไม่พบ)[^.]{0,12}มือ[^.]{0,22}(ใกล้|สายพาน)", t):
            out.append("nearmiss")
    if re.search(r"กระป๋อง[^.]{0,12}(หล่น|ตกลง|หลุดจากมือ)", t) and not re.search(r"ไม่มี[^.]{0,16}(หล่น|ตก)", t):
        out.append("falling")
    return out


def narrate(a, b):
    fa, fb = f"{FR}/t{a:04d}.jpg", f"{FR}/t{b:04d}.jpg"
    if not (os.path.exists(fa) and os.path.exists(fb)):
        return None
    e = lambda p: base64.b64encode(open(p, "rb").read()).decode()
    pl = {"model": "cosmos", "messages": [{"role": "user", "content": [
        {"type": "text", "text": PROMPT},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{e(fa)}"}},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{e(fb)}"}}]}],
        "max_tokens": 180, "temperature": 0}
    for _ in range(2):
        try:
            r = requests.post(URL, json=pl, timeout=90)
            j = r.json()
            if "choices" in j:
                m = j["choices"][0]["message"]
                return (m.get("content") or m.get("reasoning_content") or m.get("reasoning") or "").strip()
        except Exception:
            pass
    return None


out = []
for a in range(0, 217, 3):
    txt = narrate(a, min(a + 3, 216)) or ""
    tags = tag(txt)
    out.append({"t": a, "mmss": f"{a//60:02d}:{a%60:02d}", "tags": tags, "narration": txt})
    if tags:
        print(f"  {a//60:02d}:{a%60:02d}  {tags}  {txt[:60]}")
    json.dump(out, open("live_eval.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"\n{len(out)} windows -> live_eval.json")
