# VLM Video Understanding — วิธีทำให้แม่นโดยไม่เทรน detector (ตกผลึกจากหลายแหล่ง)

> ค้น 2026-07-14 · โจทย์: ดัน **VLM video understanding** ให้แม่น · **ห้ามเทรน YOLO** · หน้ากากไม่ใช่ requirement
> แหล่ง: NVIDIA VSS (production จริง), research 2025-2026, GitHub (Grounded-SAM, Set-of-Mark)

## 🎯 ข้อสรุปหลัก (สิ่งที่คนทำจริงใช้)
**ไม่ใช่ "VLM อย่างเดียว" และไม่ใช่ "YOLO เทรนเอง" — แต่คือ VLM + zero-shot detector เป็น "ตัวชี้" (ไม่ต้องเทรน).**
NVIDIA VSS (สถาปัตยกรรม production ที่ใช้ Cosmos Reason จริง) ทำแบบนี้เป๊ะ.

## เทคนิคที่ใช้ได้จริง (ทั้งหมด NO training)

### ⭐ 1. Zero-shot detector นำทาง VLM (Grounding DINO / Grounded-SAM) — คำตอบหลัก
- **Grounding DINO** = detector **open-vocabulary** สั่งด้วย **text** ("helmet", "gloves", "person", "bottle")
  → คืน bounding box **โดยไม่ต้องเทรนเลย** (zero-shot). = ตรงข้ามกับ YOLO ที่ต้อง label+train.
- **NVIDIA VSS ทำ:** Grounding DINO detect/track → **วาด box overlay ลงบนวิดีโอ** → ป้อนให้ Cosmos Reason
  → VLM reasoning บนภาพที่ "ถูกชี้" ให้แล้ว → **แม่นขึ้นมาก** (แก้จุดอ่อนของเล็ก เช่น หน้ากาก/ถุงมือ).
- **Grounded-SAM** = Grounding DINO (text→box) + SAM (box→mask) — ยังไม่ต้องเทรน.

### ⭐ 2. Set-of-Mark (SoM) prompting — ทำให้ VLM "ชี้จุด" แม่นขึ้นมาก
- วาง detector (zero-shot) หา region → **overlay ตัวเลข/กรอบ/mask** ลงบนภาพ → VLM grounding ดีขึ้นแบบก้าวกระโดด
  (Microsoft research; ใช้ได้กับ GPT-4V/LMM ทุกตัว). = ต่างจาก "fixed crop" ที่เราลองแล้วพัง (อันนี้ detect ชี้ให้ตรงจุด).

### ⭐ 3. Reasoning prompts (CoT + persona + adversarial self-verify) — เพิ่มความแม่น ไม่ต้องเทรน
- **Chain-of-Thought:** สั่ง VLM ไล่ดูทีละส่วน (หัว→มือ→หน้า) ก่อนตอบ ไม่ตัดสินทันที → ลด error.
  (Cosmos เป็น reasoning model อยู่แล้ว — ใช้ประโยชน์ได้เต็ม).
- **Persona scaffolding:** "คุณคือเจ้าหน้าที่ความปลอดภัย..." → เข้าถึง reasoning เฉพาะทาง.
- **Adversarial self-verification:** ให้ VLM สร้าง 2 สมมติฐาน (ละเมิด/ไม่ละเมิด) แล้วโต้แย้งตัวเอง → **ลดทั้ง
  false positive และ false negative** (paper construction safety ยืนยัน แม่นขึ้นโดยไม่ใช้ labeled data).

### 4. Event-trigger (detector flag → VLM รีวิวเฉพาะช่วงสำคัญ) — VSS "Event Reviewer"
- ไม่รัน VLM ทุกเฟรม. detector ถูก+เร็ว flag เหตุ → ส่งเฉพาะคลิปสั้นให้ VLM reasoning → ประหยัด+โฟกัส.

### 5. Temporal video understanding (สิ่งที่โจทย์อยากได้)
- **Chunk 10-30s + caption ขนาน** (VSS) → VLM เห็น motion (SOP/near-miss).
- **Temporal dedup + event reasoning** (Live-E2T): รวมเหตุซ้ำ + CoT.
- **Temporal state tracking** (= `ppe_tracker.py` ที่เราทำ): carry state ข้ามเฟรม.
- **StreamingVLM:** real-time video ต่อเนื่อง (window policy).

## 🔧 แผนปรับใช้กับ line-guard (ทั้งหมดไม่ต้องเทรน)
1. **เพิ่ม Grounding DINO (zero-shot) เป็นชั้นนำทาง:** สั่ง text detect `person / cap / gloves / bottle` →
   ได้ box → (a) crop/overlay region ป้อน Cosmos (Set-of-Mark) → PPE/คนแม่นขึ้น, (b) นับคน → unauthorized แม่นขึ้น.
2. **อัป prompt Cosmos เป็น reasoning:** CoT ไล่ทีละส่วน + persona safety-inspector + adversarial check.
3. **คง 2-tier + temporal tracker** (chunk video สำหรับ SOP/near-miss + per-frame + ppe_tracker).
4. **Event-trigger:** ใช้ Grounding DINO flag ช่วงมีคน/ของ แล้วค่อยเรียก Cosmos reasoning.
→ ยังเป็น **VLM-centric video understanding 100%**, detector แค่ "ชี้" (zero-shot ไม่เทรน).

## Sources
- NVIDIA — Integrate CV pipelines with GenAI reasoning (VSS + Grounding DINO + Cosmos): https://developer.nvidia.com/blog/how-to-integrate-computer-vision-pipelines-with-generative-ai-and-reasoning/
- NVIDIA VSS + Cosmos Reason (chunk+caption+detection overlay): https://nvidia-cosmos.github.io/cosmos-cookbook/recipes/inference/reason2/vss/inference.html
- Set-of-Mark Prompting (Microsoft, visual grounding): https://arxiv.org/abs/2310.11441 · https://github.com/microsoft/SoM
- Grounded-SAM (zero-shot detect+segment): https://blog.roboflow.com/enhance-image-annotation-with-grounding-dino-and-sam/
- Persona-scaffolded Adversarial CoT VLM (construction safety, no training): https://arxiv.org/pdf/2605.19869
- Live-E2T real-time threat monitoring (dedup + CoT): https://arxiv.org/pdf/2509.18571
- StreamingVLM real-time infinite video: https://www.emergentmind.com/papers/2510.09608
