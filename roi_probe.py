#!/usr/bin/env python3
"""ROI grounding — ถาม Cosmos ทีละลัง (crop) ว่า 'มีมือหยิบในลังนี้ไหม'.

ต่างจากเดิม: ไม่ให้โมเดลอ่านป้ายเอง (bind ผิด verify แล้ว 146/220 จุด)
ชื่อลังมาจาก 'เรา crop กรอบไหน' = โค้ดกำหนด 100% -> โมเดลทำแค่ perception ง่ายๆ
กล้องนิ่ง + ลังอยู่กับที่ -> ROI คงที่ทั้งคลิป (ตรวจด้วยตาแล้ว)
"""
import base64
import io

import requests
from PIL import Image

# ROI คงที่บนภาพ 1920x1080 (verify ด้วยตาแล้ว: แต่ละกรอบมีลังเดียว ไม่ทับกัน)
ROI = {"WAIT": (170, 610, 555, 850), "NG": (60, 855, 485, 1075), "GOOD": (1060, 740, 1740, 1080)}
Q = ("ภาพนี้คือลังใส่กระป๋องในโรงงาน (2 เฟรมต่อเนื่อง ซูมเฉพาะลังนี้). "
     "คำถาม: เห็น 'มือคน' (สวมถุงมือสีขาว) ยื่นเข้ามาในลังนี้ หรือกำลังจับ/หยิบ/วางกระป๋องในลังนี้ หรือไม่? "
     "คิดสั้นๆ แล้วลงท้ายด้วยบรรทัดสุดท้ายว่า 'คำตอบ: ใช่' หรือ 'คำตอบ: ไม่ใช่' เท่านั้น")
UPSCALE = 2  # crop เล็ก -> ขยายช่วยให้ perception ชัดขึ้น


def _b64(img: Image.Image) -> str:
    b = io.BytesIO()
    img.save(b, format="JPEG", quality=92)
    return base64.b64encode(b.getvalue()).decode()


def probe(url: str, frames_dir: str, t: int, box: str) -> str:
    """ถามว่า ลัง `box` ณ วินาที t มีมือมายุ่งไหม -> 'ใช่'/'ไม่ใช่'."""
    r = ROI[box]
    imgs = []
    for s in (t, t + 1):
        c = Image.open(f"{frames_dir}/t{s:04d}.jpg").crop(r)
        imgs.append(c.resize((c.width * UPSCALE, c.height * UPSCALE), Image.LANCZOS))
    payload = {"model": "cosmos", "messages": [{"role": "user", "content":
        [{"type": "text", "text": Q}] +
        [{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{_b64(i)}"}} for i in imgs]}],
        "max_tokens": 200, "temperature": 0}
    m = requests.post(url, json=payload, timeout=90).json()["choices"][0]["message"]
    txt = (m.get("content") or m.get("reasoning_content") or m.get("reasoning") or "").strip()
    # โมเดล reasoning: คำตอบอยู่ท้าย -> อ่านจากท้ายมาหน้า (ไม่ใช่ startswith)
    tail = txt[txt.rfind("คำตอบ"):] if "คำตอบ" in txt else txt[-40:]
    if "ไม่ใช่" in tail:
        return "ไม่ใช่"
    if "ใช่" in tail:
        return "ใช่"
    return f"?({txt[-30:]})"


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:18000/v1/chat/completions")
    ap.add_argument("--frames", default="/workspace/frames")
    a = ap.parse_args()
    # เฉลย verify ด้วยตา: (t, mmss, {ลัง: มีมือไหม})
    CASES = [
        (4, "00:04", {"WAIT": "ไม่ใช่", "NG": "ไม่ใช่"}),
        (113, "01:53", {"WAIT": "ใช่", "NG": "ไม่ใช่"}),
        (121, "02:01", {"WAIT": "ใช่", "NG": "ไม่ใช่"}),
        (207, "03:27", {"WAIT": "ใช่", "NG": "ไม่ใช่"}),
    ]
    ok = tot = 0
    for t, mmss, truth in CASES:
        out = []
        for box, exp in truth.items():
            got = probe(a.url, a.frames, t, box)
            hit = got == exp
            ok += hit
            tot += 1
            out.append(f"{box}={got}{'✅' if hit else f'❌(ควร {exp})'}")
        print(f"  {mmss}  " + "  ".join(out))
    print(f"\n=== ROI probe: ถูก {ok}/{tot} ===")
