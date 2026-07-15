#!/usr/bin/env python3
"""ไล่ผลโมเดลทั้งวิดีโอเทียบเฉลย (self-grade) — chronological.

เฉลย:
  ground_truth_cam_a05.json  = เฉลยเหตุการณ์ (คนทำมือ ทีละ ~2s -> ยุบเป็น segment)
  claude_gt.json             = เฉลย PPE ต่อเฟรม (Claude อ่าน crop high-res)
โมเดล: cam_a05_ai_events_final.json (timeline) + image_obs_sr.json / image_obs.json (PPE)
"""
import json

TOL = 6  # วินาที คลาด


def sec(v):
    p = str(v).split(":")
    return int(p[0]) * 60 + float(p[1]) if len(p) == 2 else float(p[0])


def mmss(s):
    s = int(s)
    return f"{s // 60:02d}:{s % 60:02d}"


TYPE_TH = {"sop_violation": "ข้ามขั้นตอน", "ppe_violation": "PPE", "near_miss": "Near-miss",
           "unauthorized_person": "คนนอก", "hygiene_violation": "ของแปลก"}

# ---- collapse GT เป็น segment ----
gt = json.load(open("ground_truth_cam_a05.json", encoding="utf-8"))["events"]
segs = []
for e in sorted(gt, key=lambda x: x["timestamp_sec"]):
    t = e["event_type"]
    s = e["timestamp_sec"]
    if segs and segs[-1]["t"] == t and s - segs[-1]["end"] <= 12:
        segs[-1]["end"] = s
        segs[-1]["n"] += 1
    else:
        segs.append({"t": t, "start": s, "end": s, "n": 1})

# ---- โมเดล ----
pred = json.load(open("cam_a05_ai_events_final.json", encoding="utf-8"))["events"]
P = [{"t": p["event_type"], "s": sec(p["timestamp_mmss"]),
      "e": sec(p.get("timestamp_end_mmss", p["timestamp_mmss"]))} for p in pred]


def overlap(a0, a1, b0, b1):
    return a0 - TOL <= b1 and b0 - TOL <= a1


print("=" * 68)
print("ไล่ตามวิดีโอ: เฉลย (GT) → โมเดลตรวจเจออะไร")
print("=" * 68)
tp_segs = 0
for sg in segs:
    hit = [p for p in P if p["t"] == sg["t"] and overlap(p["s"], p["e"], sg["start"], sg["end"])]
    ok = bool(hit)
    tp_segs += ok
    mark = "✅ เจอ " if ok else "❌ พลาด"
    print(f"  {mmss(sg['start'])}-{mmss(sg['end'])}  {TYPE_TH[sg['t']]:<12} (x{sg['n']:2d})  {mark}")

print("\n" + "=" * 68)
print("โมเดลเตือน แต่ไม่มีในเฉลย (FALSE ALARM)")
print("=" * 68)
fp = 0
for p in P:
    matched = any(p["t"] == sg["t"] and overlap(p["s"], p["e"], sg["start"], sg["end"]) for sg in segs)
    if not matched:
        fp += 1
        print(f"  {mmss(p['s'])}-{mmss(p['e'])}  {TYPE_TH.get(p['t'], p['t'])}  ← เตือนเกิน")
if not fp:
    print("  (ไม่มี)")

# ---- PPE per-item vs Claude-GT ----
print("\n" + "=" * 68)
print("PPE ต่อชิ้น (เทียบ claude_gt.json — เฉลยจริงต่อเฟรม)")
print("=" * 68)
claude = json.load(open("claude_gt.json", encoding="utf-8"))
base = {f["t"]: f["obs"] for f in json.load(open("image_obs.json", encoding="utf-8"))}
srobs = {f["t"]: f["obs"] for f in json.load(open("image_obs_sr.json", encoding="utf-8"))}


def ppe(item, obs, gated=False):
    caught = miss = fpx = 0
    for c in claude.values():
        t = c["t"]
        for w in ("1", "2"):
            cl = c["obs"].get(f"{w}|{item}", "on")
            co = obs.get(t, {}).get(f"{w}|{item}", "unknown")
            if gated and obs.get(t, {}).get(f"{w}|mask_facevis") != "yes":
                co = "on"
            if cl == "off" and co == "off":
                caught += 1
            elif cl == "off":
                miss += 1
            elif cl == "on" and co == "off":
                fpx += 1
    v = caught + miss
    return f"recall {caught}/{v}={caught/v*100 if v else 0:3.0f}%  false-alarm {fpx}"


print(f"  หมวก (cap)    : {ppe('cap', base)}")
print(f"  ถุงมือ (gloves): {ppe('gloves', base)}")
print(f"  หน้ากาก (mask) : {ppe('mask', srobs, gated=True)}   [SR+gate]")

print("\n" + "=" * 68)
print(f"สรุป: เหตุการณ์เจอ {tp_segs}/{len(segs)} ({tp_segs/len(segs)*100:.0f}%) · เตือนเกิน {fp} · โมเดลออก {len(P)} events")
print("=" * 68)
