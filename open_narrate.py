#!/usr/bin/env python3
"""ทดสอบสมมติฐาน "เราจำกัด VLM มากไป" — ปล่อยให้ Cosmos บรรยายอิสระ (ไม่บังคับ JSON/category)
เทียบกับ pipeline ที่ filter หนัก. ดูว่ามัน "เข้าใจ+อ่านได้เยอะ" แค่ไหนถ้าไม่จำกัด.

Run บน GPU box (Cosmos localhost:18000, คลิปใต้ /workspace)."""
import requests

URL = "http://localhost:18000/v1/chat/completions"
CLIP = "file:///workspace/narrate_clip.mp4"
PROMPT = (
    "คุณคือเจ้าหน้าที่ความปลอดภัยโรงงาน กำลังดูกล้อง CCTV สายการผลิตกระป๋อง (มีผู้ปฏิบัติงาน 2 คน). "
    "เล่าเป็นภาษาไทยแบบละเอียดและเป็นธรรมชาติว่า เห็นอะไรเกิดขึ้นบ้างในคลิปนี้ตามลำดับเวลา "
    "และชี้ประเด็นความปลอดภัยทุกอย่างที่สังเกตเห็น (PPE, ขั้นตอนการทำงาน, อันตราย, สิ่งผิดปกติ, อะไรก็ได้). "
    "ไม่ต้องจำกัดอยู่แค่หมวดตายตัว — เล่าให้ครบตามที่เข้าใจจริง ถ้าไม่แน่ใจก็บอกว่าไม่แน่ใจได้."
)
payload = {"model": "cosmos", "messages": [{"role": "user", "content": [
    {"type": "text", "text": PROMPT},
    {"type": "video_url", "video_url": {"url": CLIP}}]}],
    "max_tokens": 1200, "temperature": 0.3}
r = requests.post(URL, json=payload, timeout=240)
m = r.json()["choices"][0]["message"]
reply = m.get("content") or m.get("reasoning_content") or m.get("reasoning") or ""
print(reply)
