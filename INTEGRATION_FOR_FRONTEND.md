# 🔌 Frontend Integration Guide — Line Guard VLM Safety (CAM-A05)

> อ่านไฟล์นี้ก่อนเริ่มเชื่อม frontend. เขียนให้ Claude ของเพื่อน (frontend dev) เข้าใจว่า model ฝั่งเราทำอะไร ส่งอะไรออกมา และต้องเชื่อมยังไง — จะได้ไม่ต้องไปไล่โค้ดทดลอง 80 ไฟล์.

---

## 1. โปรเจกต์นี้คืออะไร (ภาพรวม 30 วินาที)

- งานคือ **เอา VLM (NVIDIA Cosmos-Reason2-8B) มา "เข้าใจวิดีโอ" ความปลอดภัยในโรงงานกระป๋อง** (กล้อง CAM-A05, คลิปเดียว ~3.5 นาที)
- **ไม่มีการเทรนโมเดล** — ใช้ VLM zero-shot + prompt เท่านั้น
- ระบบมี **2 ชั้น แยกหน้าที่กันชัด**:
  | ชั้น | คืออะไร | เชื่อถือได้แค่ไหน |
  |---|---|---|
  | 🔔 **CATCH** (structured events) | เหตุการณ์อันตราย + ระดับความรุนแรง (precompute + verify แล้ว) | **แม่น 100% recall** |
  | 🗣️ **UNDERSTAND** (narration) | Cosmos บรรยายสดว่าเห็นอะไรทุก ~1-3 วิ | บริบท เข้าใจฉาก |

- **สำคัญมากสำหรับ frontend:** เป้าหมายสุดท้าย demo จะ **ดึงทุกอย่างจากไฟล์ JSON (offline)** ไม่ใช่ยิง GPU สด (เพราะเช่า GPU ทั้งวันแพง). GPU ใช้แค่ตอน "generate log ล่วงหน้า" เท่านั้น. → **frontend ควร build โดยอ่านจาก JSON schema ข้อ 3 เป็นหลัก.**

---

## 2. ของที่มี / ไม่มีในเรพо

**มี (ในเรพо):** โค้ด model ทั้งหมด, `cam_a05_ai_events.json` (CATCH events), demo server `live_demo_combined.py`

**ไม่มี (gitignore ไว้ — ขอไฟล์จากทีม model แยก):**
- `cam_a05_720p.mp4` — วิดีโอ demo
- `_frames/` — เฟรมทุก 1 วินาที (`t0000.jpg`..`t0219.jpg`) ใช้ทำ evidence snapshot

---

## 3. 🎯 JSON Schema กลาง (สัญญา contract — build frontend ตามนี้)

ทีม model จะ generate ไฟล์นี้ให้ (`cam_a05_timeline.json`). Frontend อ่านไฟล์นี้ไฟล์เดียวจบ ไม่ต้องต่อ GPU:

```jsonc
{
  "camera_id": "CAM-A05",
  "video": "cam_a05_720p.mp4",
  "duration_sec": 219,
  "generated_by": { "model": "Cosmos-Reason2-8B", "config": "1gpu-sweetspot", "date": "2026-07-16" },

  // --- SOP อ้างอิง (มาจากหน้า frontend ของเพื่อน: work steps + safety rules) ---
  "sop": {
    "steps": [
      { "id": 1, "text": "กระป๋องรอเข้าตรวจสอบ วางในลัง WAIT" },
      { "id": 2, "text": "worker1 หยิบจาก WAIT ตรวจด้วยตา ผิดปกติใส่ NG" },
      { "id": 6, "text": "worker2 เช็ดกระป๋องครบทุกด้าน" }
      /* ... 7 ขั้นตอน */
    ],
    "safety_rules": [
      { "id": "R1", "severity": "CRITICAL", "category": "Near-Miss", "text": "มือ/ร่างกายเข้าใกล้จุดหนีบสายพานขณะเดิน" },
      { "id": "R4", "severity": "HIGH", "category": "Unsafe Action", "text": "ถอดหมวก/ถุงมือระหว่างปฏิบัติงาน" }
      /* ... map 1:1 กับตาราง Safety Rules ในหน้าเพื่อน */
    ]
  },

  // --- ชั้น UNDERSTAND: narration ต่อวินาที (เล่นตามเวลา video) ---
  "timeline": [
    { "t": 40, "mmss": "00:40", "narration": "คนซ้ายจัดกระป๋อง NG คนขวาจัดกระป๋อง GOOD", "evidence_frame": "t0040.jpg" }
    /* ทุก ~1-3 วิ */
  ],

  // --- ชั้น CATCH: เหตุการณ์อันตราย + จับคู่ safety rule + severity + หลักฐาน ---
  "events": [
    {
      "t_start": 96, "t_end": 102, "mmss": "01:36",
      "type": "unauthorized_person",
      "rule_id": "R10", "severity": "LOW", "category": "Unsafe Action",
      "description": "บุคคลภายนอก (ผู้หญิงไม่ใส่ PPE) เข้าพื้นที่",
      "evidence_frame": "t0096.jpg",          // ← feature: แคปภาพ ณ เวลานั้น (รูปที่ 2)
      "live_confirm": { "verdict": "maybe", "remark": "..." }
    }
  ],

  // --- ผลตรวจ SOP: ข้ามขั้นตอนไหม (feature รูปที่ 1) ---
  "sop_compliance": {
    "steps_observed": [1,2,3,4,5,7],
    "steps_skipped": [6],
    "detail": [
      { "step": 6, "status": "skipped", "confidence": "medium",
        "note": "ไม่พบการเช็ดกระป๋องครบทุกด้านก่อนใส่ GOOD", "evidence_t": null }
    ]
  }
}
```

**กฎการใช้:**
- `timeline[]` → เล่นตาม `video.currentTime` (หา entry ที่ `t <= currentTime` ล่าสุด)
- `events[]` → แสดง alert เมื่อ `currentTime >= t_start`; `severity` มาจาก safety rule (สี CRITICAL/HIGH/MEDIUM/LOW)
- `evidence_frame` → `<img src="/frames/t0096.jpg">` เปิดดูภาพจริงตอนเกิดเหตุ
- `sop_compliance` → แสดง checklist ว่า step ไหนทำ/ข้าม

---

## 4. ระหว่างที่ JSON ยังไม่เสร็จ — โหมด LIVE (dev/ทดสอบเท่านั้น)

`live_demo_combined.py` (localhost:5003) มี endpoint สดให้ลอง (ต้องต่อ GPU + tunnel :18000):

| endpoint | คืน |
|---|---|
| `GET /narrate?t=<sec>` | `{ mmss, narration }` |
| `GET /confirm?i=<event_index>` | `{ verdict, remark }` |
| `GET /video` | สตรีมวิดีโอ (HTTP range) |

> **frontend dev ไม่ต้องมี GPU ก็ทำงานได้** — mock 2 endpoint นี้ด้วยข้อความ dummy ไปก่อน แล้วสลับมาอ่าน `cam_a05_timeline.json` ตอน model ส่ง log จริง.

---

## 5. Do / Don't

✅ **DO**
- build frontend อ่าน `cam_a05_timeline.json` เป็นหลัก (offline-first)
- ใช้ `severity` จาก safety rule กำหนดสี/ความสำคัญ
- แยก 2 ชั้นในหน้า UI: CATCH (alert เชื่อถือได้) กับ narration (บริบท)

❌ **DON'T**
- อย่า assume ว่า narration สด = แม่น (มันคือ "เข้าใจฉาก" ไม่ใช่ detection ที่ verify)
- อย่า hardcode timestamp — อ่านจาก JSON
- อย่าเรียก GPU ตอน demo จริง (แพง) — ใช้ JSON

---

## 6. Roadmap ฝั่ง model (กำลังทำ — เพื่อน build UI รอ field เหล่านี้ได้เลย)
1. narration sweet-spot (1 GPU) → เติม `timeline[]`
2. เปรียบเทียบ 2 GPU / A100 → เลือก config generate log ที่ดีสุด
3. **SOP step-skip** (LLM อ่าน timeline เทียบ steps) → เติม `sop_compliance`
4. **Safety-rule + severity** (LLM จับคู่ narration กับ rule) → เติม `severity`/`rule_id` ใน `events[]`
5. **Evidence snapshot** → เติม `evidence_frame` ทุก event

> field ทั้งหมดอยู่ใน schema ข้อ 3 แล้ว — เพื่อน build UI รองรับไว้ได้เลย ค่าจะทยอยเติมเข้ามา
