#!/usr/bin/env python3
"""Diff Claude's ground truth (claude_gt.json) against Cosmos observations
(image_obs.json) on the 6 PPE keys, and report exactly where Cosmos is wrong.

Per (frame, item):
  claude=off, cosmos=off      -> caught      (correct violation)
  claude=off, cosmos=on       -> FN          (Cosmos missed a real violation)
  claude=off, cosmos=unknown  -> FN(abstain) (Cosmos abstained on a real violation)
  claude=on,  cosmos=off      -> FP          (Cosmos false alarm)
  else                        -> ok / abstain-benign
"""
import argparse
import json

# เฉลยที่ใช้ = v3 (ตรวจด้วยตาครบทุกเฟรม). v1 ผิด 29 จุด -> เก็บใน _archive/ เพื่ออ้างอิงเท่านั้น
# ดูเหตุผลใน MEASUREMENTS.md ข้อ 2.4
_ap = argparse.ArgumentParser()
_ap.add_argument("--gt", default="claude_gt_v3.json", help="ไฟล์เฉลย (ค่าเริ่มต้น = v3 ที่ตรวจแล้ว)")
_ap.add_argument("--obs", default="image_obs.json", help="ไฟล์คำตอบของโมเดล")
_args = _ap.parse_args()

claude = json.loads(open(_args.gt, encoding="utf-8").read())
cosmos = {f["t"]: f["obs"] for f in json.loads(open(_args.obs, encoding="utf-8").read())}
print(f"เฉลย: {_args.gt}  |  คำตอบโมเดล: {_args.obs}")
KEYS = ["1|cap", "1|gloves", "1|mask", "2|cap", "2|gloves", "2|mask"]
TH = {"1|cap": "w1 หมวก", "1|gloves": "w1 ถุงมือ", "1|mask": "w1 หน้ากาก",
      "2|cap": "w2 หมวก", "2|gloves": "w2 ถุงมือ", "2|mask": "w2 หน้ากาก"}


def mmss(s):
    return f"{s // 60:02d}:{s % 60:02d}"


caught, fn, fn_abstain, fp = [], [], [], []
for ts, c in sorted(claude.items(), key=lambda kv: kv[1]["t"]):
    t = c["t"]
    cos = cosmos.get(t, {})
    for k in KEYS:
        cl = c["obs"].get(k, "on")
        co = cos.get(k, "unknown")
        if cl == "off" and co == "off":
            caught.append((t, k))
        elif cl == "off" and co == "on":
            fn.append((t, k))
        elif cl == "off" and co == "unknown":
            fn_abstain.append((t, k))
        elif cl == "on" and co == "off":
            fp.append((t, k))

viol = len(caught) + len(fn) + len(fn_abstain)
print("=" * 60)
print("Claude GT vs Cosmos — PPE detection (74 frames, per item)")
print("=" * 60)
print(f"\nการละเมิด PPE จริง (Claude เห็น) ทั้งหมด: {viol} จุด")
print(f"  Cosmos จับได้         : {len(caught):2d}  ({len(caught)/viol:.0%})" if viol else "")
print(f"  Cosmos พลาด (บอกใส่อยู่): {len(fn):2d}  <- FALSE NEGATIVE")
print(f"  Cosmos ไม่ตัดสิน (unknown): {len(fn_abstain):2d}  <- พลาดเพราะมองไม่เห็น")
print(f"\nCosmos เตือนผิด (Claude เห็นว่าใส่อยู่): {len(fp)}  <- FALSE POSITIVE")

print("\n--- รายละเอียด: Cosmos พลาด (FN) ---")
for t, k in fn + fn_abstain:
    co = cosmos.get(t, {}).get(k, "unknown")
    print(f"  {mmss(t)}  {TH[k]:<14} จริง=ถอด  Cosmos='{co}'  <- พลาด")
if not (fn or fn_abstain):
    print("  (ไม่มี)")

print("\n--- รายละเอียด: Cosmos เตือนผิด (FP) ---")
for t, k in fp:
    print(f"  {mmss(t)}  {TH[k]:<14} จริง=ใส่อยู่  Cosmos='off'  <- เตือนผิด")
if not fp:
    print("  (ไม่มี)")

print("\n--- Cosmos จับถูก (caught) ---")
for t, k in caught:
    print(f"  {mmss(t)}  {TH[k]}")
