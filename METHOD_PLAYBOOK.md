# METHOD PLAYBOOK — วิธีทำ VLM ตรวจ safety event จากวิดีโอ (ใช้ซ้ำกับคลิปใหม่ได้)

> เขียน 2026-07-14 · ทีม model · **จุดประสงค์: จดวิธีที่ใช้ได้ผลบน cam_a05 เพื่อเอาไปปรับใช้กับวิดีโออื่น**
> แยกให้ชัด: **[GENERAL]** = ใช้ได้ทุกคลิป · **[TUNE]** = ต้องปรับต่อคลิป
> รายละเอียด/หลักฐาน = `WORKLOG.md` · ตัวเลข = `RESULTS_SUMMARY.md`

---

## 1. สถาปัตยกรรม 2-tier [GENERAL]
โมเดลตัวเดียว (Cosmos-Reason2-8B บน vLLM) ป้อน input 2 แบบ เพราะตอบคนละคำถาม:

| Tier | Input | จับ | latency | ทำไม |
|---|---|---|---|---|
| **Image** | เฟรมนิ่ง 1080p (base64) | PPE, คนนอก, foreign object | ~2s/เฟรม | ของชิ้นเล็กต้องภาพคม |
| **Video** | คลิป chunked ≤480p | SOP, near-miss | ~15-30s | เหตุ = การเคลื่อนไหว/เวลา |

**หลักการเลือก tier:** เหตุแบบ "สภาพ ณ วินาที" (ใส่ PPE ไหม/มีคนแปลก) → image · เหตุแบบ "ลำดับ/การเคลื่อนไหว" (ข้ามขั้นตอน/มือเข้าเครื่อง) → video

---

## 2. เทคนิคหลัก (image tier) [GENERAL] — คือหัวใจที่ทำให้แม่น

### 2.1 Focused prompts — 1 เรื่อง 1 คำถาม (อย่ารวม!)
**บทเรียน:** ยัด PPE+คน+foreign ใน prompt เดียว → โมเดลโฟกัส PPE จน**พลาดคน/ของ**. แยกเป็น 3 prompts
(PPE / person / foreign) → จับครบ. (ดู `image_tier.py`)

### 2.2 Visibility-gate — ย้าย abstention มาไว้ในโค้ด (คีย์ลด PPE false-positive)
**ปัญหา:** โมเดลเดา "ไม่ใส่ PPE" ตอน**มองไม่เห็น** (มือบัง) — และ**ไม่เชื่อฟัง** คำสั่ง prompt "มองไม่เห็น→ถือว่าใส่"
(ยิง 5 votes ได้ 0/5 = systematic).
**วิธีแก้ที่เวิร์ก:** ให้โมเดลรายงาน `head_visible/hands_visible/face_visible` → **ตัดสินในโค้ด: เตือนเฉพาะ
(เห็นชัด AND ไม่ใส่)**. → FP แบบ occlusion หายทั้งคลิป.
**สิ่งที่ลองแล้วไม่เวิร์ก (อย่าเสียเวลาซ้ำ):** per-worker crop (❌), self-consistency vote (❌ เพราะ FP เป็น systematic).

### 2.3 Per-type debounce — ต้องเจอ ≥2 ครั้งใน window
กัน flicker FP. **gap ≤ 2×sample_step** (ทน 1 เฟรมกระพริบ) — สำคัญกับเหตุ transient (คนเดินผ่าน).

---

## 3. จูนเฉพาะ cam_a05 [TUNE] — ⚠️ ต้องทำใหม่ทุกคลิป
สิ่งพวกนี้ **overfit cam_a05** — คลิปใหม่ต้องปรับ:

| จูน | cam_a05 ตั้งไว้ | คลิปใหม่ต้อง |
|---|---|---|
| ตำแหน่งคน | worker1 ซ้าย / worker2 ขวา (fixed) | ดูใหม่ว่าใครอยู่ไหน / กี่คน |
| `PPE_ITEMS` | `cap,gloves` (ตัด mask ทิ้ง) | ดูว่าคลิปมีเหตุ PPE แบบไหน แล้วเปิด/ปิดตาม |
| Gloves hint | "มือถือผ้าแดง = ยังใส่ถุงมือ" | เปลี่ยนตาม confuser ของคลิป (สี/ของที่ถือ) |
| SOP definition | "หยิบจากกล่อง NG วางสายพาน" | นิยาม SOP ของ process นั้น |
| Ground truth | `ground_truth_cam_a05.json` | ทำเฉลยของคลิปใหม่ (หรือ verify ด้วยตา) |
| sample_step / debounce | 3s / ≥2 | ปรับตามความยาว/ความถี่เหตุ |

---

## 4. Recipe — เอาไปใช้กับวิดีโอใหม่ (step-by-step)
1. **เตรียม:** วิดีโอ (1080p สำหรับ image tier) + SOP + list ประเภทเหตุที่ต้องจับ
2. **ดูคลิป 5-10 เฟรม:** ระบุตำแหน่ง/จำนวนคน, PPE ที่ใส่, ของที่อาจสับสน (confuser)
3. **ตั้ง [TUNE]:** `PPE_ITEMS`, gloves/สี hint, worker positions, SOP prompt
4. **รัน image tier** (`image_tier.py`) → PPE/คน/foreign
5. **รัน video tier** (`chunk_infer.py` + merge) → SOP/near-miss
6. **⚠️ Verify ด้วยตา** (สำคัญ): spot-check เฟรมที่ flag — **mock/เฉลยมักไม่ครบ** (เจอ cam_a05 ผิด ≥3 จุด:
   PPE ต่อเนื่อง, near-miss ก้ำกึ่ง, w1 mask ลงไม่จด). อย่าเชื่อ precision เทียบ mock 100%
7. **จูน debounce/sampling** จนครบ+FP ต่ำ
8. **รวม 2 tier** → timeline เดียว → `/api/events/bulk`

---

## 5. ข้อจำกัดที่รู้ (honest) [GENERAL]
1. **occluded/มือขยับ ยัง noise** — visibility-gate แก้ "มองไม่เห็น" ได้ แต่ "เห็นแต่กำกวม" (มือถือของ) ยังพลาดบ้าง
2. **near-miss อ่อนสุด** — จับแบบเดา (over-flag) ไม่มี single-frame signature → ต้อง human review
3. **mask FP** จากหัวก้ม — ปิดไว้ ถ้าเปิดต้องจัดการ
4. **cost:** 3 prompts/เฟรม = แพงสำหรับ realtime หลายกล้อง (ทางเลือก: YOLO สำหรับ PPE — ดู RESEARCH_METHODS #4)
5. **N=1:** ยังไม่เคยเทสต์คลิปอื่น = generalization ยังไม่พิสูจน์ (ความเสี่ยงใหญ่สุด)

---

## 6. ผลบน cam_a05 (image tier, verify แล้ว)
5 events, GT 4/4, FP ~0:
- 01:36-42 คนนอกเข้า ✅ · 01:39-02:15 ขวดน้ำ ✅ (ขวดอยู่จริง) · 03:00-39 w2 ไม่สวมหมวก ✅ ·
  03:36-39 w2 ไม่สวมถุงมือ ✅ · 03:36-39 w1 ไม่สวมถุงมือ ⚠️ (borderline ปลายกะ)

## 7. ไฟล์ที่เกี่ยวข้อง
- `image_tier.py` — image tier (focused prompts + visibility-gate + debounce) ← **ตัวหลัก**
- `chunk_infer.py` + `merge_events.py` — video tier (SOP/near-miss)
- `live_demo.py` — demo สด (⚠️ ยังใช้ detector เก่า — ต้อง wire image_tier เข้าไป)
- `evaluate.py` / `ground_truth_cam_a05.json` — วัดผล
