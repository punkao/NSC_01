# แผนถัดไป: ยุบเป็น Image-Primary Track (PPE + SOP) + near-miss หยาบ

> ⚠️ **ฉบับร่างเดิม — ถูกแทนด้วย `WORKPLAN.md` (ละเอียดกว่า + env setup + acceptance)** ใช้ WORKPLAN.md แทน
> วางแผน 2026-07-14 · ทีม model · อ่าน `MODEL_HANDOFF_TO_TEAM.md` + `WORKLOG.md` ก่อนเพื่อ context

## เป้าหมาย
ยุบจาก 2 track เหลือ **track หลักเดียว (image-based)** โฟกัส **PPE + SOP** (ได้ timestamp วินาทีเป๊ะ),
คง **near-miss ไว้แบบหยาบ** (reuse ของเดิม, mark ว่าเชื่อได้น้อย). เป็นระบบ "compliance monitor".

## Architecture ใหม่
```
วิดีโอ ─┬─► [PRIMARY: Image track]  ยิงเฟรมทุก ~3 วิ (1080p)
        │      └─ prompt ต่อเฟรม: PPE (หมวก/ถุงมือ/mask ต่อคน) + SOP (หยิบ NG วางสายพาน)
        │      └─ debounce (ต่อเนื่อง ≥2 เฟรม) → PPE + SOP events   [วินาทีเป๊ะ]
        │
        └─► [SECONDARY: near-miss หยาบ]  reuse chunk_infer เดิม → เก็บเฉพาะ near_miss
               └─ mark needs_review=true (เชื่อได้น้อย)
                                          │
                          รวม ─────────────┴──► timeline เดียว → /api/events/bulk
```

## แผนเป็น Phase (มี decision gate)

### Phase 0 ⚠️ — เทสต์ SOP บนเฟรมนิ่ง (หัวใจ / ความเสี่ยงสูงสุด)
- ยิงเฟรมช่วง SOP จริง (01:13–02:03) + ช่วงปกติ (00:00–01:00, 02:10–02:40)
- prompt: "มีคนหยิบกระป๋องจากกล่อง NG/reject มาวางบนสายพานไหม (ไม่ใช่จากกล่อง WAIT / ไม่ตรวจด้วยสายตา)"
- **เกณฑ์ผ่าน:** SOP window ต้อง fire, ช่วงปกติต้องเงียบ
- **ถ้าผ่าน → Phase 1. ถ้าไม่ผ่าน → SOP ถอยไปอยู่ video track (fallback)** = image สำหรับ PPE + video สำหรับ SOP/near-miss

### Phase 1 — combined prompt (PPE + SOP)
- prompt เดียวคืน `{workers:[{cap,gloves,mask}], sop_ng: bool, note_th}`
- รันทั้งคลิปทุก 3 วิ (~73 เฟรม)
- **fallback:** ถ้า prompt รวมแม่นตก → แยกเป็น 2 คำถาม/เฟรม

### Phase 2 — debounce + ประกอบ event
- PPE: ต่อเนื่อง same-worker+same-item ≥2 เฟรม (ตัด flicker FP ที่เจอตอนทดลอง)
- SOP: ต่อเนื่อง ≥2 เฟรม → span
- option: fine-localize 1 วิ ที่ onset ให้คม (ใช้ `fine_localize.py`)

### Phase 3 — near-miss หยาบ
- reuse `chunk_infer.py` เดิม → กรองเอาเฉพาะ `near_miss` → merge เป็น span → ใส่ `needs_review=true`
- ไม่ต้องทำใหม่ (ของเดิมมีอยู่แล้ว)

### Phase 4 — รวม + วัดผล
- merge image-track events + near-miss หยาบ → timeline เดียว
- `evaluate.py` วัด recall/precision (PPE+SOP แยกดูจาก near_miss)

### Phase 5 — productionize
- เขียนเป็น pipeline เดียวแทน 2-track split
- อัปเดต `backend/app/services/cosmos_runner.py` + `cosmos_events.py`
- เพิ่ม field `confidence` / `needs_review` ใน event schema (ให้ UI โชว์ near_miss ต่างจากเหตุมั่นใจ)
- อัปเดต `MODEL_HANDOFF_TO_TEAM.md`

### Phase 6 — generalization
- หา **วิดีโอที่ 2** เทสต์ว่า work ข้ามคลิปไหม (gate จริงก่อน deploy — ตอนนี้ N=1)

## Decision points (ต้องเทสต์ ไม่เดา)
1. **SOP เฟรมเดียว work ไหม** (Phase 0) — ถ้าไม่ → SOP คงอยู่ video track
2. **prompt รวม vs แยก** (Phase 1) — เริ่มรวม (ถูก/เร็ว) ตกค่อยแยก
3. **sampling 3 วิ** — ปรับได้ (ถี่ = แม่นขึ้น แต่คอมพิวต์เพิ่ม)

## ต้นทุน (ประมาณ)
- Image track: ~73 เฟรม × ~1-2 วิ ≈ 2-3 นาที/คลิป
- near-miss หยาบ (reuse): ~2 นาที
- รวม ~5 นาที/คลิป (offline batch)

## Schema ที่จะเพิ่ม
```json
{ "timestamp_mmss":"03:35", "event_type":"ppe_violation", "severity":"medium",
  "description":"...", "confidence":"high|low", "needs_review": false }
```
near_miss → `needs_review:true`

## ต้องการจากทีม
1. **วิดีโอที่ 2** (Phase 6)
2. **GPU/vLLM** — Phase 0-4 ต้องใช้ (ตอนพักได้ปิด vast, กลับมา serve ใหม่ตามคำสั่งใน HANDOFF)

## หมายเหตุ senior
Phase 0 คือหัวใจ — ถ้า SOP บนเฟรมเดียวไม่ผ่าน แผน "track เดียว" จะไม่สมบูรณ์ (PPE ได้แน่ SOP อาจต้องพึ่ง
video). เลยต้องเทสต์ก่อนลงแรงสร้าง. **อย่าเริ่ม Phase 1 ก่อนผ่าน Phase 0.**
```
