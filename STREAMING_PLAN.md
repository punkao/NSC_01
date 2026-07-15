# STREAMING SAFETY NARRATION — แผนระบบ (VLM เข้าใจ video → เล่า safety ต่อเนื่อง)

> เป้า (ตกผลึก 2026-07-15): **VLM เข้าใจวิดีโอ → เล่า safety เป็นช่วงๆ ทุก ~2-3 วิ (near-real-time)**
> ปรับใช้กับ safety อุตสาหกรรม (PPE / ของตก / อันตราย). **ไม่ offline · ไม่บังคับ binary** (= narrator ไม่ใช่ detector)

## วิเคราะห์: ทำไม framing นี้ + บทเรียนที่ใช้ออกแบบ
- **จุดแข็ง VLM = เข้าใจ+เล่า** (จัดการ ambiguity ด้วยภาษา) → เลิกบีบเป็น category binary (mask/SOP/ของตก เจอเพดานเพราะบังคับ binary)
- **บทเรียน crash:** narration ยาว + video → Cosmos ตาย (24GB) → **ต้องเก็บ output สั้น** (คีย์สำคัญ)
- **บทเรียน latency:** Cosmos reasoning ~5-15s/ครั้ง → real-time เป๊ะไม่ได้ → **near-real-time (เล่น 0.5x)**

## Architecture
```
วิดีโอ (0.5x) → ทุก ~3วิ: ส่ง window ~4วิ → Cosmos เล่าสั้นๆ ไทย (safety-focused, hedge ได้)
                                    ↓ (narration)
                          light tagger: ดึง tag PPE/ของตก/คน/อันตราย + เวลา
                                    ↓
                   UI: วิดีโอ + การ์ดเล่าต่อเนื่อง + tag chip (sync เวลา)
```

## Design decisions
| เรื่อง | เลือก | เหตุผล |
|---|---|---|
| cadence | ทุก 3วิ (video time) | ใกล้ "2-3วิ" ที่ขอ |
| window | 4-5วิ | มี context พอเล่า |
| **output** | **สั้น 1-2 ประโยค (~120 tokens)** | **กัน crash (บทเรียน)** |
| prompt | เปิด+safety ("เห็นอะไร+เสี่ยงอะไร สั้นๆ") | ปล่อยให้เข้าใจ ไม่บังคับ binary |
| tagger | keyword/pattern จาก narration | เร็ว, ดึง structure โดยไม่บีบ VLM |
| speed | near-real-time (0.5x) | Cosmos ช้า (reasoning) |

## Phases (ลงมือตามลำดับ — de-risk crash ก่อน)
- **P1. Narration probe** — Cosmos เล่า window 4วิ **สั้น** → verify **ไม่ crash** + คุณภาพคำเล่า ← gate สำคัญ
- **P2. Rolling pipeline** — สคริปต์ไล่วิดีโอทุก 3วิ → เก็บ narration ต่อ window เป็น timeline
- **P3. Light tagger** — ดึง PPE/ของตก/คน/อันตราย จากแต่ละคำเล่า
- **P4. Streaming UI** — live_demo variant: วิดีโอ + การ์ดเล่าต่อเนื่อง + tag
- **P5. Run + verify** — เล่นวิดีโอ ดู narration streaming จริง

## Risks
- crash → output สั้น (P1 gate) · GPU flaky → launch สะอาด (ไม่ pkill) · latency → 0.5x

---

## 📋 ผลลงมือ (2026-07-15)
- **P1 ✅ (แต่ pivot):** video mode narration **crash engine ซ้ำๆ** (ไม่ว่า output สั้น/ยาว) → **เปลี่ยนเป็น image mode (2 เฟรม/window)** = เสถียร (image_tier รัน 74 เฟรมไม่เคย crash) + เร็ว 4s + rich.
- **P2 ✅:** `rolling_narrate.py` — 36 windows (ทุก 6s) narrate ทั้งวิดีโอ, ไม่ crash → `narration_timeline.json`. narration ลื่น เข้าใจบริบท จับคนแปลกหน้า @01:36.
- **⚠️ finding สำคัญ:** open narration **hedge "ปลอดภัย/PPE ครบ" → พลาด violation** (03:00 หมวกออก, 02:52 near-miss). scrutinize prompt ช่วยบางส่วน (จับ mask@03:36) แต่ยังพลาด. **recall แย่กว่า structured pipeline.**
- **🎯 ตกผลึกสุดท้าย = HYBRID (รวม ไม่ใช่แทน):** narration ≠ ดีกว่า structured — คนละหน้าที่:
  **structured = CATCH เหตุการณ์ (recall 100%, จำเป็นเพราะ narration พลาด) · narration = UNDERSTAND บริบท (ที่ structured ขาด)**.
- **P4 ✅:** `live_demo_hybrid.py` (localhost:5001) — วิดีโอ + 2 ชั้น: CATCH (PPE/near-miss/คน/ของ ที่ VLM จับ) + UNDERSTAND (narration ต่อเนื่อง). precomputed = ไม่ต้อง GPU ดู.
- **สรุป:** งาน structured ที่ทำมา = ชั้น catch (ไม่เสียเปล่า) · narration = ชั้น understand (ที่ขาด) → **รวมกัน = "VLM เข้าใจ video เพื่อ safety" ที่สมบูรณ์**.
