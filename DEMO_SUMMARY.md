# 📋 Line Guard VLM — สรุปสถานะ Demo (2026-07-16)

VLM (Cosmos-Reason2-8B) เข้าใจวิดีโอความปลอดภัยโรงงาน CAM-A05 — ไม่เทรน, ใช้ prompt + zero-shot.
ระบบ 2 ชั้น: **🔔 CATCH** (เหตุการณ์อันตราย, curate+verify, แม่น) + **🗣️ narration** (Cosmos บรรยาย per-second).

---

## 🎬 มี 3 Demo

| demo | ไฟล์ | port | narration | speed | GPU | ความเสี่ยง |
|---|---|---|---|---|---|---|
| **Offline** ⭐ | `live_demo_offline.py` | 5004 | อ่านจาก JSON | **1.0×** | 0 | **ไม่มี** |
| **Live buffer-ahead** | `live_demo_combined.py` | 5003 | Cosmos คิดสด | 0.5-0.8× | 2×4090 | ขึ้นกับเน็ต |
| Hybrid (precomputed) | `live_demo_hybrid.py` | 5001 | อ่านล่วงหน้า | — | 0 | ไม่มี |

### ⭐ ตัวโชว์หลัก = Offline (5004)
- per-second + **1.0× เต็มสปีด** + sync เป๊ะ + **ไม่ต้องเช่า GPU** = ปลอดภัยสุด เล่นที่ไหนก็ได้
- narration + CATCH + **รูปหลักฐาน** (คลิกดูได้) ครบ

### Live (5003) = ของพิสูจน์ "คิดสดจริง"
- **buffer-ahead:** 2 GPU คิดล่วงหน้า playhead → buffer → โชว์ตอนถึงเวลา = per-second + sync + ไม่มี lag (ดีเท่า offline แต่ Cosmos คิดสด)
- **speed ขึ้นกับ network ไป GPU:** co-located ~0.8× / laptop→tunnel host ไกล ~0.5×
- ปรับด้วย env `PLAYBACK_RATE`

---

## 🏆 ผล Benchmark GPU (ดู `BENCHMARK_RESULTS.md`)
- **2×4090 co-located** ทำ per-second ได้: 60tok→1.0×, 90tok→0.84× (คุ้มสุด)
- **A100-40GB ไม่คุ้ม** (เร็วกว่า 4090 แค่ ~1.2× เพราะงาน prefill-bound)
- **network RTT ของ tunnel ทำ latency เพี้ยน** → ต้องวัด co-located
- narration ~1.7s/call co-located, ~3s ผ่าน tunnel host ไกล (upload รูป 1MB)

---

## 🎯 คำแนะนำสำหรับวัน Demo
```
1. เล่นหลัก = Offline (5004)  → per-second 1.0× ลื่น ปลอดภัย ไม่ต้อง GPU
2. (ถ้าอยาก) โชว์ Live สั้นๆ 15วิ → พิสูจน์ Cosmos คิดสด
```
→ **ไม่ต้องเสี่ยงพึ่ง live per-second** เป็นตัวหลัก — offline ให้ผลดีกว่าและไม่มีทางพัง

---

## 📁 ไฟล์สำคัญ
| ไฟล์ | คือ |
|---|---|
| `cam_a05_timeline.json` | narration per-second ทั้งวิดีโอ (220 จุด) + 11 events + evidence — **ข้อมูล demo offline** |
| `cam_a05_ai_events.json` | CATCH events (curate) |
| `generate_timeline.py` | สร้าง timeline JSON (co-located 2 GPU, ~275s) |
| `bench_cosmos.py` / `bench_compare.py` | benchmark harness + เทียบผล |
| `serve_cosmos.sh` / `serve_cosmos_2gpu.sh` | serve Cosmos (1 / 2 GPU) |
| `INTEGRATION_FOR_FRONTEND.md` | คู่มือเชื่อม frontend + JSON schema |
| `BENCHMARK_RESULTS.md` | ผล benchmark ละเอียด |

## 🧠 Feature LLM (OpenRouter/Opus — analyze_*.py)
- ✅ **F5 Safety-rule + severity** (`analyze_safety.py`) — จับ event เข้ากฎ R1-R10 + ระดับ (10/11) **ใช้จริง**
- ✅ **SOP Overview** (`sop_overview.py`) — LLM สรุป 'ภาพรวมประมาณการ' ว่ากระบวนการตาม SOP ไหม + บอกจุดที่ 'ประเมินไม่ได้' (แยกกล่อง/ตรวจสายตา) อย่างซื่อสัตย์ → โชว์ใน demo เป็น panel (ไม่ฟันธง = ไม่ false alert) **ใช้จริง**
- ⚠️ **F4 SOP step-skip แบบเป๊ะ** (`analyze_sop.py`) — **EXPERIMENTAL ไม่ใช้** ติด data ceiling (VLM แยกกล่องไม่ออก) → ดู `FINDINGS_SOP.md`. ทางแก้ที่ใช้แทน = SOP Overview ข้างบน (ประมาณการ)

## ⏭️ Future work
- SOP-skip ให้ได้จริง = ต้องทำ ROI/box-grounding เพิ่ม (ดู `FINDINGS_SOP.md`)
- (option) ย่อรูป 1080p→640p ให้ live เร็วขึ้น ~0.7×
