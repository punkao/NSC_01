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
- `cam_a05_720p.mp4` — วิดีโอ demo (เล่นในหน้าเว็บ)
- `cam_a05_1080p.mp4` — วิดีโอต้นทางสำหรับ**แตกเฟรม**
- `_frames_full/` — เฟรมทุก 1 วินาที (`t0000.jpg`..`t0219.jpg`) ใช้ทำ evidence snapshot

### ⚠️ แตกเฟรมต้องใช้คำสั่งนี้เป๊ะๆ (ห้ามเปลี่ยน)

```bash
ffmpeg -i cam_a05_1080p.mp4 -vf fps=1 -start_number 0 -q:v 2 _frames_full/t%04d.jpg
```

**ทำไมต้องเป๊ะ** (เจ็บมาแล้ว 2 รอบ):
- **`-start_number 0`** — ถ้าไม่ใส่ ffmpeg เริ่มที่ `t0001` → **ทุกอย่างเลื่อน 1 วินาที** ทั้งไฟล์
- **ต้องใช้ `cam_a05_1080p.mp4`** ไม่ใช่ `720p` — timeline ทั้งหมด generate จากเฟรม 1080p
- **อย่าใช้โฟลเดอร์ `_frames/` เก่า** — มีแค่ 175/220 เฟรม และ sub-second phase ไม่ตรง → `evidence_frame` จะโชว์ภาพผิดจังหวะ

เช็คว่าถูก: `ls _frames_full | wc -l` ต้องได้ **220** และมี `t0000.jpg` ถึง `t0219.jpg`

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
  // ⚠️ narration "ไม่มีชื่อลัง" โดยตั้งใจ — VLM ระบุลังผิด 66% (ดูข้อ 9) ใช้ box_activity แทน
  "timeline": [
    { "t": 40, "mmss": "00:40", "narration": "คน1 ซ้าย ถือกระป๋องจากลังฝั่งซ้ายมาตรวจ ...", "evidence_frame": "t0040.jpg" }
    /* ครบทุก 1 วิ: 220 จุด */
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

  // --- SOP: ภาพรวมประมาณการจาก LLM (ไม่ฟันธง) ---
  "sop_overview": { "overall": "...", "steps": [{ "step": 1, "assessment": "observed|partial|cannot_assess", "note": "..." }],
                    "cannot_verify": ["..."], "note_for_human": "...", "disclaimer": "ประมาณการ ไม่ใช่คำตัดสิน" },

  // --- SOP ระดับลัง: ของจริงที่ verify แล้ว (ดูข้อ 9 ก่อนใช้!) ---
  "box_activity": { "113": { "WAIT": true, "NG": false } },
  "sop_events":   [ /* ดูข้อ 9.2 */ ],
  "sop_findings": { /* ดูข้อ 9.2 */ }
}
```

> ❌ **`sop_compliance` ถูกยกเลิกแล้ว** (เวอร์ชันเก่าที่ฟันธง step-skip) — ติด data ceiling เรื่องแยกลัง
> ✅ ใช้ **`sop_overview`** (ภาพรวมประมาณการ) + **`sop_events`/`box_activity`** (ของจริงที่ verify แล้ว) แทน

**กฎการใช้:**
- `timeline[]` → เล่นตาม `video.currentTime` (หา entry ที่ `t <= currentTime` ล่าสุด)
- `events[]` → แสดง alert เมื่อ `currentTime >= t_start`; `severity` มาจาก safety rule (สี CRITICAL/HIGH/MEDIUM/LOW)
- `evidence_frame` → `<img src="/frames/t0096.jpg">` เปิดดูภาพจริงตอนเกิดเหตุ
- `sop_overview` → panel สรุปภาพรวม (ต้องขึ้น disclaimer ว่าเป็น "ประมาณการ")
- `sop_events` + `box_activity` → timeline การยุ่งกับลัง + ปุ่ม "ให้คนตรวจสอบ" (ดูข้อ 9)

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
- ใช้ `box_activity`/`sop_events` เมื่อต้องพูดถึง "ลัง" — **อย่าไปดึงชื่อลังจาก narration** (ไม่มี และไม่ควรมี)

❌ **DON'T**
- อย่า assume ว่า narration สด = แม่น (มันคือ "เข้าใจฉาก" ไม่ใช่ detection ที่ verify)
- อย่า hardcode timestamp — อ่านจาก JSON
- อย่าเรียก GPU ตอน demo จริง (แพง) — ใช้ JSON
- **อย่าเคลมว่า "หยิบออกจาก NG"** จาก `sop_events` — ระบบรู้แค่ "มีมือมายุ่ง" (ดูข้อ 9.3)

---

## 6. Roadmap ฝั่ง model (กำลังทำ — เพื่อน build UI รอ field เหล่านี้ได้เลย)
1. narration sweet-spot (1 GPU) → เติม `timeline[]`
2. เปรียบเทียบ 2 GPU / A100 → เลือก config generate log ที่ดีสุด
3. ~~SOP step-skip (ฟันธง)~~ → **ยกเลิก** (VLM แยกลังไม่ได้) แทนด้วย `sop_overview` + `sop_events` ✅
4. **Safety-rule + severity** (LLM จับคู่ event กับ rule) → `rule_id`/`severity` ✅ **เสร็จ (11/11)**
5. **Evidence snapshot** → `evidence_frame` ทุก event ✅ **เสร็จ**
6. **ROI box-grounding** → `box_activity`/`sop_events`/`sop_findings` ✅ **เสร็จ (ดูข้อ 9)**

> ✅ **ทุก field พร้อมใช้แล้ว** — `cam_a05_timeline.json` มีครบ: 220 narration + 11 events + sop_overview + box_activity + 32 sop_events

---

## 9. 🆕 ข้อมูล SOP ระดับ "ลัง" (box_activity / sop_events / sop_findings)

> เพิ่มใหม่ล่าสุด — **นี่คือส่วนที่ทำให้ SOP ตรวจได้จริง** อ่านให้จบก่อนทำ UI ส่วนนี้

### 9.1 ทำไมต้องมี (และทำไม narration ไม่บอกชื่อลัง)

**Cosmos ระบุชื่อลังไม่ได้** — วัดแล้ว **ผิด 146/220 จุด (66%)**:
- ลัง `WAIT` กับ `NG` วางชิดกัน **251 px** และเล็ก (4.5% ของภาพ) → โมเดล**จับป้ายผิดลัง** (attribute-binding failure)
- ลัง `GOOD` อยู่เดี่ยวห่าง **1053 px** → **ไม่เคยเรียกผิดเลย** ← พิสูจน์ว่าไม่ใช่ "อ่านป้ายไม่ออก" แต่คือ "จับคู่ผิด"
- แก้ด้วย prompt hint / สั่งห้าม / บอกความรู้โดเมน → **ไม่ผ่านทุกวิธี**

**→ จึงออกแบบใหม่: เอางาน "ระบุลัง" ออกจาก VLM**
| ชั้น | ใครทำ | ทำอะไร |
|---|---|---|
| ระบุลัง | **โค้ด** (ROI คงที่ กล้องนิ่ง) | crop ทีละลัง → "ลังไหน" มาจากโค้ด **100%** |
| ตรวจมือ | **VLM** | ตอบแค่ "มีมือในกรอบนี้ไหม" → **validate แล้วตรง 7/7, false positive = 0** |

**ผลลัพธ์:** `narration` **ไม่มีชื่อลัง** (ตั้งใจ — เพราะ VLM เชื่อไม่ได้) แต่ข้อมูลลังที่**เชื่อได้**อยู่ใน `box_activity` / `sop_events` แทน

### 9.2 Schema

```jsonc
"box_activity": {            // มือยุ่งกับลังไหนบ้าง ทุกวินาที (ใช้ทำ timeline bar ได้)
  "113": { "WAIT": true, "NG": false }
},
"sop_events": [              // รวมเป็นเหตุการณ์
  { "t_start": 106, "t_end": 107, "mmss": "01:46",
    "box": "NG", "who": "คน1 (ซ้าย)",
    "detected": "hand_interaction",   // <- สิ่งที่ยืนยันได้จริง (ไม่ใช่ pick/place)
    "needs_review": true,             // <- ลัง NG = ต้องให้คนตรวจ
    "note": "...", "evidence_frame": "t0106.jpg" }
],
"sop_findings": {
  "wait_interactions": 28,    // คน1 หยิบจากลัง WAIT 28 ครั้ง = SOP ขั้น 2 ทำงานปกติ
  "ng_interactions": 4,
  "ng_review_times": ["00:10","01:46","03:04","03:28"],
  "human_review_needed": 4,
  "verified": "...", "not_verified": "...", "validation": "..."
}
```

### 9.3 ⚠️ กฎการทำ UI (ห้ามเคลมเกินข้อมูล)

| ทำได้ ✅ | ห้ามทำ ❌ |
|---|---|
| "มีมือยุ่งกับลัง NG ที่ 01:46" | "หยิบกระป๋องออกจากลัง NG" |
| "คน1 หยิบจากลัง WAIT 28 ครั้ง" | "ตรวจครบ 28/28 ใบ" |
| ปุ่ม **"ให้คนตรวจสอบ"** + โชว์ `evidence_frame` | ขึ้น alert R2 อัตโนมัติ |

**เหตุผล:** ระบบ**แยกไม่ได้**ว่า "ใส่ลง" หรือ "หยิบออก" — เคยลองวัดปริมาณของในลังด้วย pixel แล้ว **ถอนออก** เพราะเงาคน/กล้องปรับแสงทำค่าแกว่งแรงกว่าสัญญาณจริง 3 เท่า (ช่วง 1:56-2:03 กระป๋อง 4 ใบเท่าเดิม แต่ค่าเหวี่ยง 17%→7.7%) และ**คลิปมีรอยตัดต่อ** (~02:17 ลัง WAIT ว่าง→เต็ม 11 ใบ ใน 1 วิ) → ของในลังเปลี่ยนเพราะจัดฉาก ไม่ใช่เพราะคนหยิบ

### 9.4 💡 คุณค่าที่ขายได้ (เขียนในสไลด์ได้เลย)

> **ระบบไม่ตัดสินแทนคน — ระบบย่อวิดีโอ 3.5 นาที เหลือ 4 จุดที่ต้องดู**
> หัวหน้างานกดดู 4 รูป จบใน 10 วินาที แทนการนั่งดูทั้งคลิป
> = **AI คัดกรอง → คนตัดสิน** (แนวทางที่ระบบความปลอดภัยจริงใช้)
