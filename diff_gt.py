#!/usr/bin/env python3
"""Diff เฉลย (claude_gt_v4.json) กับคำตอบของ Cosmos แล้วบอกว่าผิดตรงไหนบ้าง

ค่าเริ่มต้น = **คอนฟิกที่ส่งมอบจริง** คือ หมวก/ถุงมือ จากเฟรมเต็ม (image_obs.json)
+ หน้ากาก จาก super-resolution (image_obs_sr.json) -> ได้ 46/56 (82%), FP 5 ตรงกับ MEASUREMENTS.md

  ก่อนหน้านี้สคริปต์นี้อ่าน --obs ไฟล์เดียว ซึ่งใช้หน้ากากจากเฟรมเต็ม -> ได้ 26/56 (46%)
  เป็นคนละคอนฟิกกับที่รายงาน ทำให้คำสั่งใน MEASUREMENTS.md §7 ทำซ้ำเลขในรายงานไม่ได้
  ใช้ --no-sr ถ้าต้องการผลแบบเฟรมเต็มล้วน (ตัวเลขเปรียบเทียบใน §2.3)

Per (frame, item):
  claude=off, cosmos=off      -> caught      (จับการละเมิดได้ถูก)
  claude=off, cosmos=on       -> FN          (พลาดการละเมิดจริง)
  claude=off, cosmos=unknown  -> FN(abstain) (ไม่ตัดสินทั้งที่มีการละเมิด)
  claude=on,  cosmos=off      -> FP          (เตือนผิด)
"""
import argparse
import json
from pathlib import Path

# เฉลยที่ใช้ = v4 (ตรวจด้วยตาครบทุกเฟรม ทุกรายการ). v1 ผิด 32 จุด -> อยู่ใน _archive/
# ดูเหตุผลใน MEASUREMENTS.md ข้อ 2.4
_ap = argparse.ArgumentParser()
_ap.add_argument("--gt", default="claude_gt_v4.json", help="ไฟล์เฉลย (ค่าเริ่มต้น = v4 ที่ตรวจแล้ว)")
_ap.add_argument("--obs", default="image_obs.json", help="คำตอบโมเดลจากเฟรมเต็ม (หมวก/ถุงมือ)")
_ap.add_argument("--mask-obs", default="image_obs_sr.json", help="คำตอบหน้ากากจาก super-resolution")
_ap.add_argument("--no-sr", action="store_true", help="ใช้หน้ากากจากเฟรมเต็มแทน SR")
_args = _ap.parse_args()

claude = json.loads(open(_args.gt, encoding="utf-8").read())
cosmos = {f["t"]: dict(f["obs"]) for f in json.loads(open(_args.obs, encoding="utf-8").read())}

# ทับเฉพาะคีย์หน้ากากด้วยผลจาก SR = คอนฟิกที่ส่งมอบ
mask_src = "เฟรมเต็ม (--no-sr)"
if not _args.no_sr:
    if not Path(_args.mask_obs).exists():
        raise SystemExit(
            f"ไม่พบ {_args.mask_obs} ซึ่งจำเป็นสำหรับคอนฟิกที่ส่งมอบ\n"
            f"สร้างด้วย: python3 som_sr_ppe.py   (หรือใช้ --no-sr ถ้าตั้งใจวัดแบบเฟรมเต็มล้วน)"
        )
    sr = {f["t"]: f["obs"] for f in json.loads(open(_args.mask_obs, encoding="utf-8").read())}
    for t, obs in sr.items():
        for k, v in obs.items():
            if k.endswith("|mask") and t in cosmos:
                cosmos[t][k] = v
    mask_src = _args.mask_obs

print(f"เฉลย: {_args.gt}  |  หมวก/ถุงมือ: {_args.obs}  |  หน้ากาก: {mask_src}")
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

# ---- แยกรายรายการ = ตัวเลขที่อ้างในรายงาน (MEASUREMENTS.md §2.5) ----
ITEMS = {"cap": "หมวก", "gloves": "ถุงมือ", "mask": "หน้ากาก"}
print("\n" + "=" * 60)
print("แยกรายรายการ (ตัวเลขชุดนี้คือที่อ้างใน MEASUREMENTS.md §2.5)")
print("=" * 60)
print(f"  {'รายการ':<10} {'จับได้/ละเมิดจริง':>18}  {'recall':>7}  {'FP':>3}")
for item, th in ITEMS.items():
    c = sum(1 for _, k in caught if k.endswith(item))
    v = sum(1 for _, k in caught + fn + fn_abstain if k.endswith(item))
    f = sum(1 for _, k in fp if k.endswith(item))
    print(f"  {th:<10} {f'{c}/{v}':>18}  {c/v:>6.0%}  {f:>3}" if v else f"  {th:<10} {'—':>18}")
print(f"  {'-'*44}")
print(f"  {'รวม':<10} {f'{len(caught)}/{viol}':>18}  {len(caught)/viol:>6.0%}  {len(fp):>3}")

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
