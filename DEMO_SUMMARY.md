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

## 🚨 เช็คลิสต์ก่อนโชว์สด (ห้ามลืม — เคยพลาดมาแล้ว)

### 1. demo สด ต้องพูดตรงกับ JSON offline
**เคยพลาด:** แก้แต่ JSON offline แต่ demo สด (5003) ยังใช้ prompt เก่า → **สดพ่น "หยิบจาก NG" (ผิด) ขณะที่ offline ไม่มีชื่อลัง** = 2 โหมดพูดคนละเรื่อง ถ้ากรรมการสลับดูจะจับได้ทันที

**กันพลาดแล้วด้วยโค้ด** — `live_demo_combined.py` import จาก `generate_timeline.py` โดยตรง:
```python
from generate_timeline import BAN_BOX, PROMPT, _strip_box_names   # single source of truth
NARR_PROMPT = PROMPT + BAN_BOX
```
→ **แก้ prompt ที่เดียว ทั้ง 2 โหมดเปลี่ยนตาม** (ห้ามแยก prompt กลับไปเป็นคนละก๊อปปี้เด็ดขาด)

**ตรวจก่อนโชว์ 10 วินาที:**
```bash
grep -c "BAN_BOX\|_strip_box_names" live_demo_combined.py   # ต้องได้ >= 4
```
จุดที่ต้องผ่านตัวกรองทั้งหมด: `narrate_live` **และ** `confirm_live` (จุดหลังนี้เกือบลืม — มันก็พ่นชื่อลังได้)

### 2. โฟลเดอร์เฟรมต้องถูกชุด
demo ต้องชี้ `_frames_full` (220 เฟรม) — **ห้ามใช้ `_frames` เก่า** (มี 175/220 + sub-second phase ไม่ตรง → รูปหลักฐานโชว์ผิดจังหวะ)
```bash
ls _frames_full | wc -l    # ต้องได้ 220
```

### 3. ห้ามพูดเกินข้อมูล (ถ้ากรรมการถามเรื่องลัง)
| พูดได้ ✅ | ห้ามพูด ❌ |
|---|---|
| "ระบบตรวจได้ว่ามีมือยุ่งกับลัง NG 4 ครั้ง" | "ระบบเห็นว่าเขาหยิบออกจาก NG" |
| "VLM ระบุชื่อลังไม่ได้ เราเลยให้โค้ดทำแทน (ROI)" | "Cosmos อ่านป้ายลังได้" |

---

## ⚡ prompt กันชื่อลัง ทำให้ช้าลงไหม? — **ไม่ (วัดแล้ว)**

| | prompt เก่า | prompt ใหม่ (+BAN_BOX +กรอง) |
|---|---|---|
| latency median | 2.62s | **2.25s** |
| output tokens | 112 | 102 |
| prompt tokens | 4187 | 4264 (**+77**) |

**paired test n=12 (สลับ A/B): −0.51s (−18.6%), 95%CI [−0.90, −0.13] = เร็วขึ้นอย่างมีนัยสำคัญ**

เหตุผล: prompt เพิ่มแค่ **+77 tokens** จากที่**ภาพกินไป 4187 tokens อยู่แล้ว** (+1.8% prefill = แทบไม่มีผล) ส่วน output **สั้นลง 10 tokens** → decode น้อยลง → เร็วขึ้น. regex กรอง = **0.0094 ms** (0.0004% ของ latency)

> 📌 **บทเรียนการวัด:** ครั้งแรกวัดแบบรัน A ทั้งชุดก่อนแล้วค่อย B → ได้ "ช้าลง 13.8%" (ผิด เพราะ drift ปน) พอวัดแบบ **paired สลับ A/B ทีละเฟรม** ผลกลับด้านเป็น "เร็วขึ้น" → **ต้องวัดแบบ paired เสมอ**

---

## 🎬 ความเร็ว demo สด หลังใส่ ROI (วัดจริง 2×4090 co-located)

วัดแบบเดียวกับที่ demo ใช้ (buffer-ahead ยิงขนาน NEP=2), 12 วินาทีวิดีโอ, สลับลำดับ A/B/B/A กัน drift:

| config | interval | **เล่นได้สูงสุด** |
|---|---|---|
| narration อย่างเดียว (ไม่มี ROI) | 1.02s/วิ | **0.98×** |
| **narration + ROI** (ที่ใช้จริง) | 1.22s/วิ | **0.82×** |
| ต่างกัน | **+0.20s/วิ** | **−19.7%** |

**ทำไมเพิ่มแค่ 20%:** ROI 2 call = 0.54s งาน GPU เทียบกับ narration 2.25s (+24% งาน) และ ROI เบามาก
(crop เล็ก → **916 prompt tokens** เทียบ narration **4,264**) พอกระจายบน 2 GPU ขนาน → interval เพิ่มแค่ 0.20s

### ✅ สรุปสำหรับวัน demo: **ไม่ต้องแก้อะไร**
- **ตัวโชว์หลัก = Offline (5004) → 1.0× เต็ม ไม่กระทบเลย** (ROI ทำไว้ล่วงหน้าใน JSON แล้ว)
- **Live (5003) = 0.82×** เอาไว้พิสูจน์ 15 วิว่า "คิดสดจริง" — ตาดูแทบไม่ออก และยังดีกว่าเกณฑ์เดิมที่รับได้ (0.84×)

### ถ้าวันหน้าอยากให้ live เร็วขึ้น (ไม่ต้องทำตอนนี้)
| ทาง | ได้ | เสีย |
|---|---|---|
| probe แค่ลัง NG (ตัด WAIT ออก) | ~0.90× | ไม่รู้ว่าหยิบจาก WAIT (แต่ WAIT = พฤติกรรมปกติอยู่แล้ว) |
| probe ROI ทุก 2 วิ | ~0.90× | ชื่อลังอัปเดตทุก 2 วิ |
| ลดขนาดเฟรม narration 1080p→720p | ยังไม่วัด | ป้าย/หน้ากากอาจมองยากขึ้น |

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
