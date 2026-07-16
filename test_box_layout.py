#!/usr/bin/env python3
"""ทดสอบ: layout-hint ที่อธิบาย 'ผังลัง' ช่วยให้ Cosmos ระบุลัง (WAIT/NG/GOOD) ถูกขึ้นไหม?

ปัญหาที่พบ (verify จากเฟรมจริงแล้ว): narration 146/220 จุด (66%) บอกว่าคน1 หยิบจาก "NG"
ทั้งที่ความจริงหยิบจาก "WAIT" — Cosmos จับป้าย NG ผิดลัง (attribute-binding error)
เพราะฝั่งซ้ายมี 2 ลังชิดกัน (WAIT บน / NG ล่าง) ส่วนฝั่งขวามีลังเดียว (GOOD) เลยไม่พลาด

สมมติฐาน: ถ้าบอก 'ผังลัง' ให้ชัด (โดยเฉพาะ cue กล่อง Double A สีน้ำเงินใต้ลัง NG)
          -> Cosmos bind ป้ายถูกลัง -> narration ระบุลังถูก -> regenerate timeline ได้

ระเบียบวิธี: hint อธิบาย 'ตำแหน่งลัง' เท่านั้น ไม่บอกว่า "คน1 หยิบจากลังไหน"
(ไม่งั้นเป็นการเฉลยคำตอบ = วัดอะไรไม่ได้). วัดแบบ A/B: ไม่มี hint vs มี hint.

รันบนเครื่อง GPU (co-located) หรือผ่าน tunnel :18000. ต้องมี Cosmos serve + _frames/.
Run: python test_box_layout.py [--url http://127.0.0.1:18000/v1/chat/completions]

เฉลย (verify จากเฟรมจริงด้วยตา):
  00:04 (t0004) มือคน1 อยู่ที่สายพาน ไม่ได้แตะลัง + ลัง NG ว่างเปล่า -> "ไม่ได้หยิบจากลัง"
  01:53 (t0113) มือคน1 อยู่ในลัง WAIT -> WAIT
  02:01 (t0121) มือคน1 อยู่ที่ขอบลัง WAIT -> WAIT
  03:27 (t0207) มือคน1 อยู่ในลัง WAIT -> WAIT
"""
import argparse
import base64
import os

import requests

FRAMES = "_frames"

# ผังลังคงที่ทั้งคลิป (สรุปจากการดูเฟรมจริง) — cue เด่น = กล่อง Double A สีน้ำเงินใต้ลัง NG
LAYOUT = (
    "ผังลังในภาพนี้คงที่ตลอดคลิป จำให้แม่น: "
    "ฝั่งซ้ายมี 2 ลังวางเรียงในแนวลึก ห้ามสับสนกัน — "
    "(ก) ลัง 'WAIT' = ลังกระดาษสีน้ำตาล อยู่ 'บน/ไกลจากกล้องกว่า' ติดกับโต๊ะขาวและสายพาน ป้าย WAIT อยู่ระดับกลางภาพ; "
    "(ข) ลัง 'NG' = ลังที่อยู่ 'ล่างสุด ใกล้กล้องที่สุด' ที่มุมล่างซ้ายของภาพ วางอยู่บน 'กล่องกระดาษสีน้ำเงิน (Double A)' "
    "และป้าย NG อยู่ที่ขอบล่างสุดของภาพ. "
    "ฝั่งขวามีลังเดียวคือลัง 'GOOD'. "
    "กฎสำคัญ: ป้าย 'NG' เป็นของลังล่างสุดที่วางบนกล่องสีน้ำเงินเท่านั้น — "
    "ถ้ามือคนอยู่ในลังซ้ายที่ติดโต๊ะขาว (เหนือกล่องน้ำเงิน) ลังนั้นคือ WAIT ไม่ใช่ NG."
)

QUESTION = (
    "คำถาม: ตอนนี้ 'มือของคน1 (คนซ้าย)' อยู่ในลังไหน หรือกำลังหยิบ/ล้วงกระป๋องจากลังไหน? "
    "ตอบเลือก 1 อย่างเท่านั้น: WAIT / NG / GOOD / ไม่ได้หยิบจากลัง "
    "แล้วบอกเหตุผลสั้น 1 ประโยค (อ้างตำแหน่งมือ เช่น อยู่เหนือกล่องน้ำเงินหรือไม่)."
)

# (วินาที, mmss, เฉลยที่ verify แล้ว)
CASES = [
    (4, "00:04", "ไม่ได้หยิบจากลัง"),
    (113, "01:53", "WAIT"),
    (121, "02:01", "WAIT"),
    (207, "03:27", "WAIT"),
]


def parse_answer(ans: str) -> str:
    """ดึงคำตอบลังจากข้อความ — เช็ค 'ไม่ได้หยิบ' ก่อน แล้วดูว่าเอ่ยลังไหนก่อน (ตำแหน่งแรกสุด)."""
    if "ไม่ได้หยิบ" in ans or "ไม่ได้ล้วง" in ans:
        return "ไม่ได้หยิบจากลัง"
    pos = {b: ans.find(b) for b in ("WAIT", "NG", "GOOD") if ans.find(b) >= 0}
    return min(pos, key=pos.get) if pos else "?"


def ask(url: str, prompt: str, fa: str, fb: str) -> str:
    b64 = lambda p: base64.b64encode(open(p, "rb").read()).decode()
    payload = {"model": "cosmos", "messages": [{"role": "user", "content": [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64(fa)}"}},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64(fb)}"}}]}],
        "max_tokens": 150, "temperature": 0}
    r = requests.post(url, json=payload, timeout=90)
    m = r.json()["choices"][0]["message"]
    return (m.get("content") or m.get("reasoning_content") or m.get("reasoning") or "").strip()


def run(url: str, label: str, prompt: str, avail: list[int]) -> int:
    nearest = lambda s: min(avail, key=lambda x: abs(x - s))
    print(f"\n===== {label} =====")
    correct = 0
    for t, mmss, truth in CASES:
        a = nearest(t)
        b = nearest(a + 1)
        try:
            ans = ask(url, prompt, f"{FRAMES}/t{a:04d}.jpg", f"{FRAMES}/t{b:04d}.jpg")
        except Exception as ex:
            ans = f"(error {ex})"
        said = parse_answer(ans)
        ok = said == truth
        correct += ok
        print(f"  {mmss} เฉลย={truth:18s} -> ตอบ '{said}'  {'✅' if ok else '❌'}")
        print(f"       {ans[:100]}")
    print(f"  --> {label}: ถูก {correct}/{len(CASES)}")
    return correct


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:18000/v1/chat/completions")
    args = ap.parse_args()

    avail = sorted(int(f[1:5]) for f in os.listdir(FRAMES) if f.startswith("t") and f.endswith(".jpg"))

    # A/B: ไม่มี hint (baseline) vs มี hint -> วัดว่า hint ช่วยจริงไหม
    base = run(args.url, "A) ไม่มี hint (baseline)", QUESTION, avail)
    hint = run(args.url, "B) มี layout-hint", LAYOUT + " " + QUESTION, avail)

    n = len(CASES)
    print(f"\n{'='*46}\nสรุป: baseline {base}/{n}  ->  layout-hint {hint}/{n}")
    if hint >= n - 1 and hint > base:
        print("✅ hint ช่วยได้จริง -> regenerate timeline ด้วย prompt ที่มี LAYOUT")
        print("   รัน: python generate_timeline.py --layout-hint --endpoints <ep0>,<ep1> ...")
    elif hint > base:
        print("🔶 hint ช่วยบางส่วน -> ดีขึ้นแต่ยังพลาด, ชั่งใจว่าจะ regenerate ไหม")
    else:
        print("❌ hint ไม่ช่วย -> ยืนยัน box-grounding ceiling จริง")
        print("   -> ทางเลือก: neutralize ชื่อลังใน narration หรือทำ ROI/crop grounding")


if __name__ == "__main__":
    main()
