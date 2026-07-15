# RESEARCH — วิธีเพิ่มความแม่น PPE (ลด false positive)

> ค้น 2026-07-14 · โจทย์: VLM ถามภาพเต็มเฟรม → PPE false positive (เดา "ไม่มี" ตอน occlusion)
> สรุปจากงานวิจัยล่าสุด + วิธีที่ควรลองต่อ (เรียงตาม impact/effort)

## สาเหตุ FP (ยืนยันจากงานวิจัย)
- **FP ส่วนใหญ่มาจาก visual ambiguity** — occlusion, มุมกล้อง, แสง/เงา/สะท้อน (ตรงกับที่เราเจอ: มือลง→เดาไม่มีถุงมือ).
- **การป้อนภาพเต็มเฟรมให้ VLM = image-text alignment แย่** → VLM ต้อง localize + ตัดสินพร้อมกัน → พลาดง่าย.

## วิธีที่งานวิจัยใช้ (เรียงตามผลกับงานเรา)

### ⭐ 1. Object-guided / crop รายคน (ผลชัดสุด, effort กลาง) — Clip2Safety
- **วิธี:** detect คน/ของก่อน (YOLO-World) → **crop เฉพาะคน** → แล้วค่อยถาม VLM/CLIP บน crop.
- **ผล:** แม่นขึ้น **~16%** + เร็วขึ้น **200×** (เทียบ VQA ภาพเต็ม). crop แยกคน → alignment ดีขึ้น → FP ลด.
- **ปรับใช้กับเรา (ง่ายกว่าเปเปอร์):** กล้อง**นิ่ง** + คนอยู่ตำแหน่งคงที่ (worker1 ซ้าย, worker2 ขวา)
  → ใช้ **fixed crop** (ซ้าย/ขวา) ได้เลย **ไม่ต้องมี detector** → zoom เห็น หมวก/ถุงมือ ชัด → FP ลดมาก.
  **= วิธีที่คุ้มสุดที่ควรลองก่อน.**

### 2. Hybrid YOLO + VLM (best practice อุตสาหกรรม, effort สูง)
- **วิธี:** YOLO detect PPE (helmet/gloves/vest/mask) แม่น+เร็ว (mAP@0.5 ~88%) → VLM ทำ reasoning/context/SOP.
- **โมเดลสำเร็จรูป:** `keremberke/yolov8m-protective-equipment-detection` (HF), `yolov8n-ppe-6classes`,
  Roboflow PPE YOLO-11, Ultralytics Construction-PPE dataset.
- **⚠️ ข้อจำกัดกับเรา:** โมเดลพวกนี้เทรนกับ PPE ก่อสร้าง (หมวกแข็ง/เสื้อสะท้อนแสง) — ของเราเป็น
  **หมวกแก๊ป/ถุงมือผ้า/หน้ากากอนามัย** → อาจ match ไม่ดี → ต้อง **fine-tune** ด้วยภาพจากกล้องเราเอง.
  = ทางยาว (production จริง) แต่ต้องลงแรง label + train.

### 3. Reasoning + self-consistency (effort ต่ำ, ผลกลาง)
- **Reasoning:** Cosmos เป็น reasoning model อยู่แล้ว — สั่งให้ **ไล่ดูทีละส่วน** (หัว→มือ→หน้า) ก่อนตอบ
  ("double-thinking": bbox + chain-of-thought) → ลด FP + อธิบายได้.
- **Self-consistency:** ยิงซ้ำ 2-3 ครั้ง → vote เสียงข้างมาก (CISC = ถ่วงน้ำหนักด้วย confidence). ลด FP สุ่ม.
  แลกด้วย compute 2-3×.

### 4. Multi-frame temporal voting (ทำแล้ว — งานวิจัยยืนยัน)
- **"วิเคราะห์ ≥2 เฟรมก่อนตัดสิน → precision เพิ่ม"** = debounce ที่เราเพิ่งใส่ใน live demo. ถูกทางแล้ว.
  ปรับต่อได้: track คนข้ามเฟรม (ReID) + vote สถานะ PPE ต่อคน.

### 5. Abstention (ทำแล้ว)
- สั่ง "มองไม่เห็น→ถือว่าใส่" (ทำใน live_demo แล้ว) — ตรงกับ research เรื่อง uncertainty/abstention.

## แผนที่แนะนำ (เรียงลำดับ)
1. ~~fixed per-worker crop~~ — **❌ ทดสอบแล้ว 2026-07-14 ไม่เวิร์ก** (01:08 FP ยังอยู่ + 03:37 หลุด cap).
   ต้นตอไม่ใช่ framing → crop ไม่ช่วย. (ดู WORKLOG)
2. ~~self-consistency vote~~ — **❌ ทดสอบแล้ว ไม่เวิร์ก** (FP เป็น systematic 0/5 ไม่ใช่ random) → vote ไม่ช่วย.
3. **⭐ [ชนะ — ใช้ตัวนี้] visibility-gate** — ให้โมเดลรายงาน `head/hands/face_visible` แล้ว **ตัดสินในโค้ด:
   เตือนเฉพาะ (เห็นชัด AND ไม่ใส่)**. แก้ FP หลัก (01:08) ได้จริงโดยคงเหตุจริง (03:37). ย้าย abstention
   จาก prompt (โมเดลไม่เชื่อฟัง) มาไว้ในโค้ด. → **นี่คือสิ่งที่ควรเอาเข้า live_demo.**
4. **[ทางยาว/production] YOLO PPE fine-tuned** — เมื่อมี data + จะ deploy จริง (มือขยับ/บังยัง noise).
5. คง debounce (2 เฟรม) ไว้ (ฐาน).

## รอบถัดไป (ยังไม่ทำ): แก้ False-Negative — PPE ถอดแล้วไม่แจ้ง ⚠️
> ปัญหาที่เจอ 2026-07-14 ตอนดู demo: worker1 ถอด**หน้ากาก**ไม่แจ้ง · worker2 ถอด**ถุงมือ**ไม่แจ้ง (บ่อย) ·
> **หมวก**บางทีก็ไม่แจ้ง. = per-frame VLM ชนเพดาน (แลก FP↔FN). ต้องหาข้อมูลเพิ่มก่อนตัดสิน.

**สาเหตุที่ยืนยันแล้ว:** (1) mask ถูก**ตัดทิ้ง** (`PPE_ITEMS`) (2) gloves ถูก**กดด้วย knob กัน-FP**
(visibility-gate + cloth-hint + debounce) (3) VLM ตัดสิน PPE ชิ้นเล็ก/ขยับ/บัง ไม่แม่นโดยธรรมชาติ.

**เทคนิคที่ต้องไปหาข้อมูล (เรียงตามที่น่าจะคุ้ม):**
1. **⭐ YOLO-PPE fine-tune บนภาพกล้องเราเอง** — detector เฉพาะ presence/absence (helmet/glove/mask).
   *หาเพิ่ม:* base model ไหนดี (YOLOv8/v11-PPE), ต้อง label กี่ภาพสำหรับกล้องนิ่งตัวเดียว, มี pretrained ที่
   รวม cap แก๊ป/ถุงมือผ้า/mask ไหม (ส่วนใหญ่เป็น hardhat ก่อสร้าง = domain gap).
2. **Temporal PPE state tracking** — track สถานะ PPE ต่อคนข้ามเฟรม → แจ้งเมื่อ "worn→off ต่อเนื่อง".
   ลดทั้ง FP (flicker) และ FN (จับจังหวะถอด). กล้องนิ่ง+คนตำแหน่งคงที่ = ทำง่าย. *หาเพิ่ม:* state machine / ReID.
3. **VLM fine-tune (Cosmos LoRA)** — สอนให้รู้จัก PPE เฉพาะเรา. *หาเพิ่ม:* มีใครทำ LoRA VLM สำหรับ PPE ไหม,
   ต้องใช้ data เท่าไหร่, คุ้มกว่า YOLO ไหม (น่าจะไม่ — VLM ไม่เหมาะ small-object).
4. **Detection-assisted VLM (Set-of-Mark)** — detector หา head/hands → mark/crop → VLM ตัดสิน
   (ต่างจาก fixed-crop ที่ลองแล้วพัง). *หาเพิ่ม:* SoM prompting กับ Cosmos.
5. **แกะทุกเฟรม / sampling ถี่** — ช่วยเหตุสั้นเท่านั้น, แพง, ไม่แก้ต้นตอ. = ไม่ใช่ทางหลัก.
6. **rebalance knob เดิม (stopgap)** — เปิด mask กลับ + ตัด cloth-hint + debounce=1 → recall↑ แต่ FP↑.
   ใช้ชั่วคราวสำหรับ demo ได้ ไม่ใช่ทางจริง.

**คำถามวิจัยที่ต้องตอบก่อนเลือกทาง:** (a) YOLO-PPE fine-tune ใช้ effort/data เท่าไหร่จริง? (b) recall/precision
YOLO-PPE vs VLM บน PPE ต่างแค่ไหน? (c) temporal tracking ช่วย recall ได้เท่าไหร่โดยไม่ต้องเทรน?

## Sources
- Clip2Safety — Object-guided VLM PPE compliance: https://arxiv.org/html/2408.07146v1
- Real-time construction safety VLM+NLP: https://www.sciencedirect.com/science/article/abs/pii/S1474034625007827
- Hazard detection LLM/VLM: https://arxiv.org/pdf/2511.15720
- Self-Consistency reduces VLM hallucination: https://arxiv.org/abs/2509.23236
- YOLO26 vs YOLOv11 PPE: https://www.mdpi.com/2079-9292/15/6/1146
- Pretrained PPE YOLO: https://huggingface.co/keremberke/yolov8m-protective-equipment-detection
