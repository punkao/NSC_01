# 🏗️ Line Guard — Model Architecture (End-to-End)

ระบบเข้าใจวิดีโอความปลอดภัยโรงงานด้วย **VLM (Vision-Language Model)** — ไม่เทรนโมเดล ใช้ prompt + zero-shot
กล้อง CAM-A05 (สายการผลิตกระป๋อง). เอกสารนี้ = สถาปัตยกรรมฝั่ง model ตั้งแต่ input จนถึง output ทุกกระบวนการ.

---

## 0. ปรัชญาการออกแบบ (ทำไมแบ่งแบบนี้)

**หลักคิด:** แยก "จับแม่น" ออกจาก "เข้าใจลึก" เพราะมันคนละธรรมชาติ
- ตรวจจับเหตุการณ์ต้อง **เชื่อถือได้** (พลาดไม่ได้) → ใช้ชั้น curate + verify
- บรรยาย/เข้าใจบริบทต้อง **รวย** (เล่าได้) → ใช้ VLM พ่นสด
- วิเคราะห์เชิงเหตุผล (severity/SOP) ต้อง **reasoning** → ใช้ LLM (text)

→ ระบบมี **4 ชั้น** แยกหน้าที่กันชัด (ดูข้อ 2-5)

**ทำไม VLM ไม่ใช่ object detection:** object detection ต้อง fine-tune ทุกโรงงาน/ทุกกล้อง.
VLM + prompt = ปรับได้ทันทีผ่านคำสั่ง ไม่ต้องเทรนใหม่ (จุดขายหลัก).

---

## 1. FULL PIPELINE (ภาพรวมทั้งหมด)

```
 [1] INPUT: วิดีโอ CAM-A05 (~3.5 นาที, 720p)
        │
        ▼  extract เฟรม 1 เฟรม/วินาที
 [2] FRAMES: _frames/t0000.jpg … t0219.jpg (≈220 เฟรม)
        │
        ▼  หน้าต่าง 2 เฟรม/ครั้ง (IMAGE mode — video mode ทำ engine crash)
 ┌──────────────────────────────────────────────────────────┐
 │ [3] STAGE 1 — VLM PERCEPTION                              │
 │     Cosmos-Reason2-8B (vLLM บน GPU)                       │
 │     • prompt = บริบทฉาก + SOP + คำถามความปลอดภัย         │
 │     • คำตอบอยู่ใน field `reasoning`                       │
 │     ผลลัพธ์ 2 อย่าง ↓                                     │
 └──────────────────────────────────────────────────────────┘
        │                              │
        ▼ (บรรยายทุกวินาที)            ▼ (ตรวจพบเหตุการณ์)
 [4a] UNDERSTAND                 [4b] DETECTED EVENTS
      narration/sec                    │ human curate + verify
        │                              ▼
        │                       ┌──────────────────────┐
        │                       │ CATCH LAYER          │ recall 100%
        │                       │ structured events    │ + evidence frame
        │                       │ (เชื่อถือได้)         │
        │                       └──────────────────────┘
        │                              │
        └───────────────┬──────────────┘
                        ▼  รวมเป็นไฟล์เดียว
 [5] cam_a05_timeline.json  ◄── "contract" (frontend อ่านไฟล์นี้ไฟล์เดียว)
                        │
                        ▼  STAGE 4 — LLM ANALYSIS (OpenRouter/Opus, text-only, ไม่ใช้ GPU)
 ┌──────────────────────────────────────────────────────────┐
 │ [6a] F5: จับ event → safety rule (R1-R10) + severity      │
 │ [6b] SOP Overview: สรุปภาพรวมประมาณการ ว่าตาม SOP ไหม     │
 └──────────────────────────────────────────────────────────┘
                        │
                        ▼  เขียนกลับ (enrich)
 [7] cam_a05_timeline.json + rule_id/severity/category + sop_overview
                        │
             ┌──────────┴───────────┐
             ▼                       ▼
 [8a] LIVE demo (Cosmos สด)   [8b] OFFLINE demo (อ่าน JSON, 0 GPU)
        │                             │
        └──────────────┬──────────────┘
                       ▼
              [9] FRONTEND / Dashboard (เพื่อน)
```

---

## 2. STAGE 1 — VLM Perception (Cosmos-Reason2-8B)

**หน้าที่:** ดูภาพ → เข้าใจว่าเกิดอะไร (คนทำอะไร, ใส่ PPE ไหม, มีอันตรายไหม)

| ประเด็น | รายละเอียด |
|---|---|
| โมเดล | NVIDIA **Cosmos-Reason2-8B** (reasoning VLM) เสิร์ฟด้วย vLLM |
| โหมด | **IMAGE mode 2 เฟรม/window** — VIDEO mode ทำ vLLM engine crash (EngineDeadError) |
| Input ต่อครั้ง | 2 เฟรมต่อเนื่อง (base64) + prompt |
| คำตอบ | อยู่ใน field `reasoning` (ไม่ใช่ `content`) |
| latency | ~0.5-1.5s/call (วัดจริง, ไม่ใช่ 5-25s) |
| prompt | บอกบริบท (คน1 ซ้าย/คน2 ขวา, กล่อง WAIT/NG/GOOD) + สั่งบรรยายไทย + ถามจุดเสี่ยง |

**สิ่งที่ตรวจได้ (verified):**
| หมวด | ผล |
|---|---|
| หมวก (cap) | 100% / 0 FP |
| ถุงมือ (gloves) | 100% |
| หน้ากาก (mask) | 62% (ต้องใช้ super-resolution EDSR-4x — วัตถุเล็ก) |
| คนนอก / ของแปลกปลอม | ✅ |
| near-miss (มือใกล้สายพาน) | ✅ ตรวจได้ |
| ของตก | curate + verify เฟรม |

**เพดานที่รู้ตัว (honest ceilings):**
- **mask = perception ceiling** (วัตถุเล็ก → SR ช่วยได้ถึง 62%)
- **กล่อง NG/WAIT/GOOD = data ceiling** (กล่องเหมือนกัน มุมกดลง → VLM แยกไม่ออก → SOP-skip เป๊ะทำไม่ได้ ดู `FINDINGS_SOP.md`)
- **falling/near-miss = ambiguity** (วางกับหล่น แยกยาก)

---

## 3. STAGE 2 — CATCH Layer (structured events)

**หน้าที่:** เก็บ "เหตุการณ์อันตราย" ที่ **เชื่อถือได้** (recall 100%)

- มาจาก Cosmos detect → **human curate + verify เฟรมจริง** → นิ่ง (precompute)
- **ทำไม precompute:** เพื่อความแม่น (ไม่เอา detection แม่นๆ ไปเสี่ยงกับ live inference)
- แต่ละ event มี: เวลา, ประเภท, คำอธิบาย, **รูปหลักฐาน (evidence_frame)**
- ไฟล์ต้นทาง: `cam_a05_ai_events.json`

**events ที่มี (11):** ของตก(00:14,01:52) · คนนอก(01:36) · ของแปลกปลอม(01:39) · ไม่สวมหน้ากาก(02:12,03:33) · ถอดถุงมือ(02:12) · near-miss(02:45) · ไม่สวมหมวก(03:00) · ไม่สวมถุงมือ(03:36×2)

---

## 4. STAGE 3 — UNDERSTAND Layer (narration)

**หน้าที่:** บรรยายฉากทุกวินาที (บริบท — คนดูเข้าใจว่าเกิดอะไร)

- Cosmos พ่นบรรยายไทย 1-2 ประโยค/วินาที
- 2 โหมด:
  - **สด (live):** buffer-ahead 2 GPU คิดล่วงหน้า → โชว์ตอน playhead ถึง (per-second, sync)
  - **offline:** อัดไว้ใน JSON ล่วงหน้า → เล่น 1.0× ไม่ต้อง GPU

---

## 5. STAGE 4 — LLM Analysis (OpenRouter/Opus · text-only · ไม่ใช้ GPU)

**หน้าที่:** วิเคราะห์เชิงเหตุผลจาก text (severity + SOP) — แยก stage เพราะเป็น text ไม่ต้องแย่ง GPU

### 5.1 F5 — Safety rule + severity (`analyze_safety.py`)
- อ่าน events → จับคู่กับ **safety rulebook (R1-R10)** → ใส่ `rule_id` + `severity` + `category`
- ผล: 10/11 match (near-miss→R1 critical, ถอดถุงมือ→R4 high, คนนอก→R10 low ฯลฯ)
- **severity อิงกฎลูกค้าจริง ไม่ใช่เดา**

### 5.2 SOP Overview (`sop_overview.py`)
- อ่าน narration timeline → สรุป **"ภาพรวมประมาณการ"** ว่ากระบวนการตาม SOP ไหม
- ระบุชัดว่าจุดไหน **"ประเมินไม่ได้"** (แยกกล่อง/ตรวจสายตา) + จุดที่ควรให้คนตรวจ
- **ประมาณการ ไม่ฟันธง** → ไม่มี false alert (SOP-skip เป๊ะทำไม่ได้เพราะ box ceiling)

---

## 6. SAFETY RULEBOOK (R1-R10) — ใช้ใน F5

| ID | ระดับ | ประเภท | กฎ | VLM ทำได้? |
|---|---|---|---|---|
| R1 | 🔴 CRITICAL | Near-Miss | มือ/ร่างกายเข้าใกล้จุดหนีบสายพานขณะเดิน | ✅ |
| R2 | 🟠 HIGH | Unsafe Action | หยิบจากลัง NG กลับขึ้นสายพาน / ใส่ผิดลัง | ❌ (พึ่งกล่อง) |
| R3 | 🟠 HIGH | Unsafe Condition | กระป๋องหล่นบนสายพานที่กำลังเดิน | ✅ |
| R4 | 🟠 HIGH | Unsafe Action | ถอดหมวก/ถุงมือระหว่างปฏิบัติงาน | ✅ |
| R5 | 🟡 MEDIUM | Unsafe Action | ไม่สวม PPE (หมวก/ถุงมือ/หน้ากาก) ตั้งแต่เริ่ม | ✅ |
| R6 | 🟡 MEDIUM | Unsafe Action | หน้ากากไม่คลุมจมูกปาก | ✅ (mask 62%) |
| R7 | 🟡 MEDIUM | Unsafe Action | วางขึ้นสายพานโดยไม่ตรวจ (ข้ามขั้น 2) | ❌ (การคิด) |
| R8 | 🟡 MEDIUM | Unsafe Action | เก็บ GOOD โดยไม่เช็ด (ข้ามขั้น 6) | ⚠️ (พึ่งกล่อง) |
| R9 | 🟡 MEDIUM | Unsafe Condition | วางของไม่เกี่ยว (ขวดน้ำ/มือถือ) ในพื้นที่ | ✅ |
| R10 | 🔵 LOW | Unsafe Action | บุคคลอื่นเข้าพื้นที่ทำงาน | ✅ |

→ กฎที่ **ไม่พึ่งกล่อง (R1,R3,R4,R5,R6,R9,R10) = VLM ทำได้แม่น**; กฎที่ **พึ่งกล่อง/การคิด (R2,R7,R8) = ทำไม่ได้เป๊ะ** (ดู SOP Overview แทน)

---

## 7. SOP WORK STEPS (7 ขั้นตอน) — ใช้ใน SOP Overview

| ขั้น | การทำงาน | VLM เห็นได้? |
|---|---|---|
| 1 | กระป๋องรอในลัง WAIT | ❌ (แยกกล่อง) |
| 2 | worker1 หยิบจาก WAIT + **ตรวจด้วยสายตา** ผิดปกติใส่ NG | ❌ (กล่อง+การคิด) |
| 3 | worker1 วางกระป๋องดีลงบน conveyor | ✅ (เห็นการวาง) |
| 4 | Conveyor ผ่านกล้อง + **ตรวจด้วย AI** | ❌ (เครื่อง/AI) |
| 5 | worker2 หยิบออกจาก conveyor | ✅ (เห็นการหยิบ) |
| 6 | worker2 เช็ดกระป๋องครบทุกด้าน | ✅ (เห็นการเช็ด) |
| 7 | worker2 เก็บใส่ลัง GOOD | ⚠️ (พึ่งกล่อง GOOD) |

→ **ขั้นที่เป็นการกระทำ (3,5,6) VLM เห็นได้** → SOP Overview เลยประเมินได้แบบภาพรวม
→ **ขั้นที่พึ่งกล่อง/การคิด (1,2,4,7) ประเมินไม่ได้** → บอกตรงว่า "cannot_assess"

---

## 8. DATA CONTRACT — cam_a05_timeline.json

ไฟล์เดียวที่ frontend อ่าน (offline-first). โครงสร้าง:

```jsonc
{
  "camera_id": "CAM-A05", "video": "...", "duration_sec": 219,
  "timeline": [                              // ชั้น UNDERSTAND (narration/วินาที)
    {"t": 40, "mmss": "00:40", "narration": "...", "evidence_frame": "t0040.jpg"}
  ],
  "events": [                               // ชั้น CATCH + F5 (severity)
    {"t_start": 96, "mmss": "01:36", "type": "unauthorized_person",
     "rule_id": "R10", "severity": "low", "category": "Unsafe Action",
     "description": "...", "evidence_frame": "t0096.jpg"}
  ],
  "sop_overview": {                         // SOP Overview (ประมาณการ)
    "overall": "...", "steps": [...], "cannot_verify": [...],
    "note_for_human": "...", "disclaimer": "ประมาณการ ไม่ใช่คำตัดสิน"
  }
}
```

---

## 9. DEPLOYMENT — 2 โหมด

| | LIVE (co-located) | OFFLINE (JSON) |
|---|---|---|
| narration | Cosmos คิดสด (buffer-ahead 2 GPU) | อ่านจาก JSON |
| GPU ตอนโชว์ | ต้องมี (2×4090) | **0 (ฟรี)** |
| speed | 0.8-1.0× | 1.0× เป๊ะ |
| ความเสี่ยง | ขึ้นกับเน็ต/GPU | ไม่มี |
| ใช้เมื่อ | โชว์ "AI คิดสด" | demo ทั่วไป (แนะนำ) |

**สถาปัตยกรรมที่ถูก:** รัน demo บนเครื่อง GPU (co-located) แล้ว tunnel แค่หน้าเว็บ — ไม่ส่งรูปข้ามเน็ต (network RTT เป็นคอขวด ไม่ใช่ GPU)

---

## 10. สรุปการแบ่งหน้าที่ (4 ชั้น)

```
🔍 STAGE 1 VLM Perception  → เห็นภาพ เข้าใจฉาก           (GPU, Cosmos)
🔔 STAGE 2 CATCH           → จับเหตุการณ์แม่น (verify)    (precompute, reliable)
🗣️ STAGE 3 UNDERSTAND       → บรรยายทุกวินาที (บริบท)      (live/offline)
🧠 STAGE 4 LLM Analysis    → severity + SOP overview      (text, Opus, ไม่ใช้ GPU)
```

**เชื่อถือได้ (ship):** CATCH + narration + F5 severity + SOP Overview
**เป็น finding (ไม่ ship):** SOP-skip เป๊ะ (ติด box ceiling — `FINDINGS_SOP.md`)

---

## 11. ไฟล์ที่เกี่ยวข้อง (map กับสถาปัตยกรรม)

| Stage | ไฟล์ |
|---|---|
| 1 VLM serve | `serve_cosmos.sh` / `serve_cosmos_2gpu.sh` |
| 1 narration gen | `generate_timeline.py` (offline) / `live_demo_combined.py` (live) |
| 2 CATCH | `cam_a05_ai_events.json` |
| 4 F5 severity | `analyze_safety.py` |
| 4 SOP overview | `sop_overview.py` |
| 5/8 data + demo | `cam_a05_timeline.json` · `live_demo_offline.py` (:5004) · `live_demo_combined.py` (:5003) |
| eval | `evaluate.py` · `diff_gt.py` · `claude_gt.json` · `bench_*.py` |
| docs | `ARCHITECTURE.md`(นี้) · `INTEGRATION_FOR_FRONTEND.md` · `BENCHMARK_RESULTS.md` · `FINDINGS_SOP.md` · `DEMO_SUMMARY.md` |
