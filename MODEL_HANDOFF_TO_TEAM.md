# สรุปฝั่ง Model → ส่งต่อทีม Integration / UI / Backend

> # 🛑 ไฟล์นี้ล้าสมัย — ห้ามใช้ตัวเลขในไฟล์นี้ (ตรวจสอบ 2026-07-17)
>
> ตัวเลขในไฟล์นี้วัดด้วย **เฉลยที่ภายหลังพบว่าผิด 32 จุด** จึงผิดแทบทุกตัว:
>
> | ไฟล์นี้เขียนว่า | ของจริง (วัดใหม่ 2026-07-17) |
> |---|---|
> | ถุงมือ 100% | **57%** (4/7) · FP 3 |
> | หน้ากาก 62% "เพดานของ VLM" | **80%** (28/35) — ไม่ใช่เพดาน แค่วัดผิด |
> | recall 100% · precision 91% | **recall รวม 82%** (46/56) · FP 5 |
>
> **ถ้าคุณคือทีม frontend/integration → อ่าน `INTEGRATION_FOR_FRONTEND.md` (โดยเฉพาะข้อ 10) และ `PROMPT_FOR_FRIEND_UPDATE.md` แทน**
> ตัวเลขที่ถูกต้องทั้งหมดอยู่ที่ `MEASUREMENTS.md` เท่านั้น
> เก็บไฟล์นี้ไว้เป็นประวัติเท่านั้น — เนื้อหาข้างล่างนี้คือสิ่งที่ **เคยเข้าใจผิด**

---


> เขียนโดยทีม model (kaopun) · อัปเดต 2026-07-15
> **ไฟล์นี้สำหรับเพื่อนที่ทำ frontend / backend / integration อ่าน** — ไม่ต้องรู้ลึกเรื่อง AI
> รายละเอียดเชิงลึกอยู่ใน `spike/WORKLOG.md` + `spike/HANDOFF.md` (สำหรับคนทำ model)

---

## TL;DR (อ่านแค่นี้ก็เข้าใจ 80%)

- เราทำ **AI ตรวจจับเหตุการณ์ความปลอดภัยจากวิดีโอ CCTV จริง** แทน event timeline ที่เคยเขียนมือ (mock)
- โมเดล = **NVIDIA Cosmos-Reason2-8B** (VLM) รันบน vLLM
- **Output = JSON event timeline หน้าตาเหมือน mock เป๊ะ** → ยิงเข้า `POST /api/events/bulk` ได้เลย ขับ Event Timeline UI ตัวเดิม
- ทดสอบบนคลิป **CAM-A05** (1 คลิป): จับเหตุได้ **ครบทุกประเภท (recall 100%)**, **precision 91%** (วัดด้วย Claude-GT เฉลยจริง)
- จับได้ **5 ประเภท**: `sop_violation`, `ppe_violation`, `near_miss`, `unauthorized_person`, `hygiene_violation`
- **PPE (per-item):** หมวก 100% · ถุงมือ 100% · **หน้ากาก 62%** (เพดาน VLM ไม่เทรน — หน้ากากดึงลงคางเล็ก/เกรน; ถ้าต้องเป๊ะ 100% ต้องใช้ detector เทรนเอง หรือ VLM ใหญ่/frontier)

---

## 1. สิ่งที่ฝั่ง Model ส่งมอบ (Output Contract) ← สำคัญสุดสำหรับ integration

Model ผลิต JSON แบบเดียวกับ mock ทุก field → POST เข้า endpoint เดิม:

```
POST /api/events/bulk
{
  "camera_id": "CAM-A05",
  "replace": true,                       // ลบ event เดิมของกล้องนี้ก่อน
  "events": [
    {
      "timestamp_mmss": "01:39",         // เวลาในวิดีโอ (นาที:วินาที)
      "severity": "medium",              // low | medium | high | critical
      "event_type": "hygiene_violation", // 1 ใน 5 ประเภทด้านล่าง
      "event_type_label": "วางของไม่เกี่ยวข้อง",
      "description": "ผู้ปฏิบัติงานวางขวดน้ำบนสายพาน"   // ไทย ใช้โชว์ได้เลย
    }
  ]
}
```

- ไฟล์ตัวอย่างจริง (ล่าสุด): **`spike/cam_a05_ai_events_final.json`** (11 events, ครบ 5 ประเภท + mask) — เอาไปยิงได้เลย
  (มี field เสริม `timestamp_end_mmss` = เวลาสิ้นสุด span; ไม่ใช้ก็ได้ UI เดิมอ่าน `timestamp_mmss` พอ)
- `event_type` มีได้แค่: `sop_violation` | `ppe_violation` | `near_miss` | `unauthorized_person` | `hygiene_violation`
- `severity`: `low` | `medium` | `high` | `critical` (near_miss = critical เสมอ)
- UI เดิม (Event Timeline) sync กับวิดีโอด้วย `video_offset_seconds` อยู่แล้ว → **ไม่ต้องแก้ UI**

---

## 2. Architecture: ทำไมมี "2 Track" (ต้องเข้าใจไว้)

โมเดล **ตัวเดียว** (Cosmos) แต่ป้อน input 2 แบบ เพราะตอบคนละคำถาม — **ไม่ใช่ 2 โมเดล, GPU ตัวเดียว**:

| | **Track A — วิดีโอ** | **Track B — รูปภาพ** |
|---|---|---|
| ป้อน | คลิป 15 วิ (ย่อ 720p, ~2fps) | ภาพนิ่งเต็ม (1080p) ทีละใบ |
| ตอบคำถาม | "เกิดอะไรตามเวลา" (การเคลื่อนไหว) | "ตอนนี้เห็นอะไร" (รายละเอียดคมชัด) |
| จับ | near_miss, SOP, คนเข้าพื้นที่, hygiene | **PPE (หมวก/ถุงมือ/mask)** |
| ทำไมแยก | เหตุพวกนี้ต้องเห็นการเคลื่อนไหว | PPE เป็นจุดเล็ก ต้องภาพคม — วิดีโอย่อ 720p มองไม่เห็น |

**ตอน analyze:** 2 track แยกกัน → **ตอน output:** รวมเป็น timeline เดียว (`merge_ab.py`) → integration เห็นแค่ JSON เดียว

> 💡 หมายเหตุถึงทีม: ใน `co-work.md` มีแผน service DINOv3 (Project 3) สำหรับ PPE/zone อยู่แล้ว —
> **นั่นคือที่ที่ถูกต้องสำหรับ PPE ตอน production** (detector เฉพาะทาง เร็ว+ถูกกว่า VLM). Track B (image
> PPE ด้วย Cosmos) ของเราเป็นแค่ "พิสูจน์ว่าทำได้" — production ควรย้าย PPE ไป DINOv3/detector

---

## 3. ผลลัพธ์จริง (คลิป CAM-A05) — ต้องรู้เพื่อออกแบบ UX

**Recall 100% (จับครบทุกเหตุ) · Precision 60% (เตือนถูก 6 ใน 10)**

| เหตุการณ์จริง | เวลา | จับได้? | เวลาแม่นแค่ไหน |
|---|:---:|:---:|---|
| SOP ข้ามขั้นตอน | 01:13–02:03 | ✅ | หยาบ (span กว้าง) |
| คนนอกเข้าพื้นที่ | 01:36–01:40 | ✅ | **เป๊ะ ±1 วิ** |
| วางของผิดที่ (ขวดน้ำ) | 01:39 | ✅ | **เป๊ะ** |
| near_miss มือเข้าเครื่อง | 02:55 | ⚠️ จับแบบเดา | ❌ ไม่แม่น + หาเฟรมยืนยันไม่ได้ |
| PPE ถอดหมวก/ถุงมือ | 02:59, 03:35 | ✅ (Track B) | ✅ ดี |

**เตือนผิด (false alarm) 4/10:** near_miss 2 อัน (ไม่มีจริง), sop 1 (ต้นคลิป), ppe 1 (หลงจังหวะ)

---

## 4. ข้อจำกัดที่ UI/Integration ต้องออกแบบรับมือ ⚠️

1. **มี false alarm ~40%** → UI ควรมีปุ่ม "ack / dismiss / ยืนยัน" อย่าโชว์ว่า AI ถูก 100%
2. **near_miss เชื่อไม่ได้** → เป็นเหตุ critical แต่โมเดลจับแบบเดา — **ต้องให้คนตรวจก่อนเสมอ** อย่า auto-escalate
3. **เวลา (timestamp):**
   - คนเข้า / PPE / ของวางผิดที่ → แม่นระดับวินาที (±1-2 วิ)
   - SOP / near_miss → หยาบ เป็น "ช่วง" (คลาดได้ 10 วิ, span ยาว)
4. **PPE ต้องมาจาก Track B** — ถ้าใช้แต่ Track A จะไม่มี PPE เลย

---

## 5. เรื่อง Deploy จริง (Backend/Infra ต้องรู้)

**โหมดที่ใช้ตอนนี้ = Offline batch** (วิเคราะห์ทั้งคลิปก่อน → เก็บ event → replay วิดีโอให้ event เด้ง)
→ **demo แบบเล่นวิดีโอที่อัดไว้ = ทำได้เลย** (เหมือน mock)

**ถ้าจะใช้กล้องสดจริง (live stream):**
| ต้องการ | ทำได้ไหม |
|---|:---:|
| แจ้งเตือน supervisor (~30 วิ โอเค) | ✅ ได้ (near-realtime, หน่วง ~26 วิ) |
| หยุดเครื่องทันทีกันมือหนีบ (<1 วิ) | ❌ ไม่ได้ (VLM ช้าเกิน — ต้องใช้ edge detector) |

- **1 GPU (RTX 3090) ≈ 1 กล้อง** near-realtime → หลายกล้อง = ต้องหลาย GPU (แพง)
- **Scale จริง → hybrid:** detector เล็กถูก (DINOv3/YOLO) ทำ PPE+คน แบบ real-time, เก็บ VLM ไว้ทำ reasoning (near-miss/SOP)

---

## 6. สถานะ Backend Integration (โค้ดอยู่ใน repo แล้ว)

- ✅ เขียน service ใหม่แล้ว: `backend/app/services/cosmos_runner.py` + `cosmos_events.py`
- ✅ ต่อ endpoint: `POST /api/analyze/video` เพิ่ม field `engine=cosmos` (ค่า default `qwen` = ของเดิม ไม่กระทบ)
- ✅ unit test ผ่าน: `backend/tests/test_cosmos_events.py` (7/7)
- ⏳ **ยังไม่ได้ทดสอบ e2e จริง** — ต้องมี vLLM sidecar + Postgres วางด้วยกัน (dev box ไม่มี)
- **สิ่งที่ integration ต้องเซ็ต:** รัน vLLM Cosmos เป็น local sidecar, เปิดทั้ง image+video
  (`--limit-mm-per-prompt '{"video":1,"image":2}'`, `--allowed-local-media-path`), ตั้ง env
  `VLLM_BASE_URL`, `VLLM_MODEL=cosmos`

---

## 7. Map ไฟล์ (ฝั่ง model, อยู่ใน `spike/`)

| ไฟล์ | คืออะไร |
|---|---|
| `cam_a05_ai_events.json` | **ผลสุดท้าย: timeline ครบ 5 ประเภท พร้อมยิง /api/events/bulk** |
| `chunk_infer.py` | Track A — หั่นวิดีโอเป็น chunk → เรียก VLM |
| `merge_events.py` | รวม event ต่อเนื่องใน Track A เป็น span (คีย์ precision) |
| `ppe_batch.py` (scratchpad) | Track B — PPE จากภาพนิ่ง |
| `fine_localize.py` | 2-stage: ปักวินาทีเป๊ะสำหรับเหตุที่เห็นชัด |
| `merge_ab.py` | รวม Track A + B เป็น timeline เดียว |
| `evaluate.py` | ให้คะแนนเทียบเฉลย (recall/precision) |
| `ground_truth_cam_a05.json` | เฉลย (= mock เดิม) |

---

## 8. คำถาม/สิ่งที่ทีมต้องตัดสินใจต่อ

1. **requirement เรื่องความเร็ว:** ต้องการ "แจ้งเตือนให้คนไปดู" (~30 วิ พอ) หรือ "ตอบสนองทันที" (<1 วิ)?
   → กำหนด architecture คนละทาง
2. **PPE production:** จะย้ายไป DINOv3 (Project 3) หรือคงใช้ Cosmos image pass?
3. **หลายกล้อง:** งบ GPU / จะทำ hybrid ไหม
4. **near_miss:** ยอมรับว่าต้อง human-in-the-loop ได้ไหม (โมเดลจับไม่แม่น)
5. **⚠️ ทุกตัวเลขมาจากคลิปเดียว (N=1)** — ต้องมีวิดีโอที่ 2 มาเทสต์ก่อนเชื่อว่า generalize ได้
