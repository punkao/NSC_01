#!/usr/bin/env python3
"""สร้าง event หน้ากากใหม่จาก SR แบบไม่มี face-gate — แทนของเดิมที่มาจากคอนฟิกที่พิสูจน์แล้วว่าแย่

เหตุผล (ดู MEASUREMENTS.md ข้อ 2.4): face-gate ทิ้งคำตอบที่ถูกไป 19 จุด (80% -> 26%)
เพื่อกำจัด FP ที่เกิดจากเฉลยผิด -> event ที่ได้เลยมีช่องว่างปลอมกลางเหตุการณ์

debounce: ต้องเจอ >= 2 จุดติดกัน (ยอมขาดได้ 1 ช่วงสุ่ม = 6 วิ) — ตัด FP จุดเดี่ยวทิ้ง
** ไม่ขยาย gap ให้ span รวมกันเป็นก้อนเดียว ** เพราะนั่นคือการจูนให้ได้คำตอบที่เรารู้อยู่แล้ว
Run: python rebuild_mask_events.py
"""
import json

SR = "image_obs_sr.json"
OUT = "mask_events_sr.json"
GAP = 6          # วินาทีที่ยอมให้ขาดภายใน span เดียว (= พลาด 1 จุดสุ่ม)
MIN_POINTS = 2   # ต้องเจอซ้ำอย่างน้อย 2 จุด จึงยืนยัน (debounce)


def main() -> None:
    obs = {x["t"]: x["obs"] for x in json.load(open(SR, encoding="utf-8"))}
    events = []
    for w in ("1", "2"):
        det = sorted(t for t in obs if obs[t].get(f"{w}|mask") == "off")
        spans: list[list[int]] = []
        for t in det:
            if spans and t - spans[-1][-1] <= GAP:
                spans[-1].append(t)
            else:
                spans.append([t])
        for s in spans:
            if len(s) < MIN_POINTS:
                continue                      # จุดเดี่ยว = สัญญาณรบกวน ตัดทิ้ง
            events.append({
                "event_type": "ppe_violation", "severity": "medium",
                "worker": w, "item": "mask",
                "start_sec": s[0], "end_sec": s[-1],
                "description_th": f"ผู้ปฏิบัติงาน {w} ไม่สวมหน้ากาก",
                "detected_points": len(s),
                "method": "super-resolution (EDSR-4x) ไม่มี face-gate",
            })
    events.sort(key=lambda e: e["start_sec"])
    json.dump(events, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for e in events:
        a, b = e["start_sec"], e["end_sec"]
        print(f"  {a//60:02d}:{a%60:02d}-{b//60:02d}:{b%60:02d} ({b-a:3d}s, {e['detected_points']} จุด) {e['description_th']}")
    print(f"-> {OUT} ({len(events)} events)")


if __name__ == "__main__":
    main()
