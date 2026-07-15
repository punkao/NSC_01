#!/usr/bin/env python3
"""Formal VLM detection of falling-object (can dropped) — Cosmos video mode.

ส่งคลิปสั้นรอบจังหวะที่ผู้ใช้ระบุ (00:14 สายพาน, 01:52 โต๊ะ) ให้ Cosmos ดูแบบ VIDEO
(เห็น motion การหล่น ไม่ใช่เฟรมนิ่ง) แล้วถามว่ามีกระป๋องหล่น/หลุดจากมือไหม.
= ปิด gap "falling_object ยังไม่ได้ VLM-detect" ให้เป็น detection จริง.

Run บน GPU box (Cosmos localhost:18000, คลิปใต้ /workspace). Usage: python falling_detect.py
"""
import json
import re

import requests

URL = "http://localhost:18000/v1/chat/completions"
CLIPS = {
    "00:14 (สายพาน)": "file:///workspace/drop1_belt.mp4",
    "01:52 (โต๊ะ)": "file:///workspace/drop2_table.mp4",
}
PROMPT = (
    "Short CCTV clip of a canning inspection line (2 workers). Watch the MOTION carefully. "
    "SAFETY QUESTION: does a worker DROP or FUMBLE a can — a can slipping/falling from the hand "
    "onto the conveyor, table, or floor at any moment in this clip?\n"
    'Answer JSON only: {"can_dropped": true|false, "where": "conveyor"|"table"|"floor"|"none", '
    '"description_th": "<สั้นๆ ว่าเกิดอะไร>"}'
)


def ask(video_url: str) -> dict:
    payload = {"model": "cosmos", "messages": [{"role": "user", "content": [
        {"type": "text", "text": PROMPT},
        {"type": "video_url", "video_url": {"url": video_url}}]}],
        "max_tokens": 600, "temperature": 0}
    r = requests.post(URL, json=payload, timeout=180)
    m = r.json()["choices"][0]["message"]
    reply = m.get("content") or m.get("reasoning_content") or m.get("reasoning") or ""
    mt = re.search(r"\{.*\}", reply, re.DOTALL)
    try:
        return json.loads(mt.group(0)) if mt else {"raw": reply[:150]}
    except (ValueError, TypeError):
        return {"raw": reply[:150]}


for label, url in CLIPS.items():
    print(f"\n=== {label} ===")
    print("  ", ask(url))
