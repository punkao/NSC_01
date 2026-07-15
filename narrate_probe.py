#!/usr/bin/env python3
"""P1 (image-mode): narrate window ด้วย 2 เฟรม (start+end) แทน video — เพราะ video mode
crash engine ซ้ำๆ ส่วน image mode (image_tier) รัน 74 เฟรมไม่เคย crash = เสถียร.
2 เฟรม/window = ยังได้ temporal พอเล่าว่า "ช่วงนี้เกิดอะไร".

Usage: python narrate_probe.py <frameA.jpg> <frameB.jpg> [max_tokens]"""
import base64
import sys
import time

import requests

URL = "http://localhost:18000/v1/chat/completions"
fa, fb = sys.argv[1], sys.argv[2]
maxtok = int(sys.argv[3]) if len(sys.argv) > 3 else 160


def b64(p):
    return base64.b64encode(open(p, "rb").read()).decode()


PROMPT = (
    "ภาพ 2 เฟรมต่อเนื่อง (ห่างกันไม่กี่วินาที) จากกล้อง CCTV สายการผลิตกระป๋อง (ผู้ปฏิบัติงาน 2 คน). "
    "เล่าสั้นๆ 1-2 ประโยคภาษาไทยว่า ช่วงนี้เห็นอะไรเกิดขึ้น และมีจุดเสี่ยงความปลอดภัยไหม "
    "(PPE หมวก/ถุงมือ/หน้ากาก, ของตก/หล่น, มือใกล้เครื่อง/สายพาน, คนแปลกหน้า). "
    "ถ้าปกติก็บอกสั้นๆ. ห้ามเกิน 2 ประโยค."
)
payload = {"model": "cosmos", "messages": [{"role": "user", "content": [
    {"type": "text", "text": PROMPT},
    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64(fa)}"}},
    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64(fb)}"}}]}],
    "max_tokens": maxtok, "temperature": 0.2}
t = time.time()
r = requests.post(URL, json=payload, timeout=120)
dt = time.time() - t
j = r.json()
if "choices" not in j:
    print("STATUS", r.status_code, "->", str(j)[:200])
else:
    m = j["choices"][0]["message"]
    reply = m.get("content") or m.get("reasoning_content") or m.get("reasoning") or ""
    print(f"[{dt:.1f}s] {reply.strip()}")
