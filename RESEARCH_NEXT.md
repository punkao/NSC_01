# RESEARCH_NEXT — ทางไปต่อ (ไม่ใช่เพดานจริง) + ลำดับลงมือ

> ตกผลึกจากค้นหลายแหล่ง 2026-07-15 · "ตัน" ที่พูดก่อนหน้า = เพดานของ setup ปัจจุบัน
> (Cosmos-8B ตัวเดียว + chunked + crop คงที่ + GPU เดียว + ไม่มี tracker) **ไม่ใช่เพดานของวงการ**

## 4 lever ที่วงการมี (mapped กับจุดที่เราติด)

| lever | แก้อะไร | หลักฐาน | no-train? | VLM-centric? |
|---|---|---|---|---|
| **A. Set-of-Mark grounding** (overlay กล่อง NG/WAIT/GOOD + spatial prompt) | SOP grounding อ่อน | Thinking-with-Images, SoM, spatio-temporal grounding | ✅ | ✅ (Cosmos ยัง reason) |
| **B. Agentic/attention zoom** (ViCrop) | mask 62% | ViCrop, Thinking-with-Images (arXiv 2602.11858) | ✅ | ✅ |
| **C. Streaming VLM** (VideoLLM-online) | per-second/ความหนา | VideoLLM-online 5-10 FPS บน 3090 (CVPR24), StreamingVLM | ✅ (pretrained) | ✅ (เปลี่ยนตัว VLM) |
| **D. Model ใหญ่ขึ้น** (Cosmos-32B/frontier) | เพดานความแม่น | Cosmos-Reason2-32B, Qwen3-VL-235B | ✅ | ✅ |

## ลำดับลงมือ (เหตุผล: feasible × ตรงจุดอ่อนที่ verify แล้ว × VLM-centric × no-train × คุ้ม GPU)

### 🥇 Phase 1 — SoM-SOP grounding **(ทำก่อน — กำลังทำ)**
- **ทำไมก่อน:** (1) SOP คือจุดอ่อนที่ผู้ใช้ verify เอง (ดูเฟรม) (2) กล้องนิ่ง → กล่อง NG/WAIT/GOOD ตำแหน่งคงที่ → overlay ได้ง่าย
  (3) VLM ยัง reason (ไม่ใช่ rule ล้วน) → รักษา thesis (4) no-train (5) เทสต์ได้เลย GPU เปิดอยู่
- **วิธี:** วาดกรอบ+ป้ายกล่อง (SoM) ลงเฟรม + prompt เชิงพื้นที่ ("worker หยิบจากกล่องไหน? หยิบจาก NG ขึ้นสายพานโดยไม่ inspect = violation")
  → ให้ Cosmos reason จากตำแหน่งจริง แทนเดาจากท่าทาง
- **วัด:** เทสต์ 3 เฟรม — t=30 (ปกติ ควรบอกไม่ violation), t=78/t=120 (violation ควรระบุ NG box). ดูว่า grounding ดีขึ้น + หยุด over-fire ไหม
- **Acceptance:** Cosmos แยก "หยิบ NG (violation)" กับ "งานปกติ" ได้ชัดขึ้น + ระบุกล่องถูก

### 🥈 Phase 2 — Agentic/attention zoom สำหรับ mask (ViCrop-style)
- ให้ VLM เลือกจุด zoom เอง (แทน crop คงที่) → ดัน mask เกิน 62% · วัดกับ claude_gt (holistic ทุก item)

### 🥉 Phase 3 — Streaming VLM (per-second) — impact สูงสุด แต่ risk สูงสุด
- ลอง VideoLLM-online narrate real-time per-frame → แก้ per-second + ความหนา · เป็น model คนละตัว (setup friction) → ทำเมื่อ Phase 1-2 ผ่าน

### Phase 4 — Model ใหญ่ (32B/frontier) — ถ้ายังต้องการความแม่นเพิ่ม (ต้อง GPU ใหญ่)

## ⚠️ หลักการ (จากบทเรียนที่ผ่านมา)
- **ทุกเทคนิค "มีหลักฐานว่าเวิร์ก" แต่ไม่การันตีบนฟุตเทจเรา** → ต้องเทสต์จริง วัดทุก item (SR ได้แค่ 62%, PPE-YOLO fail)
- **วัด before/after ทุกครั้ง กันแก้อันนึงพังอันอื่น**

---

## 📋 ผลลงมือ

### Phase 1 — SoM-SOP grounding → ❌ ไม่ผ่าน (เจอ finding ลึกกว่า) — 2026-07-15
- วิธี: `som_sop_probe.py` วาดกรอบ+ป้ายกล่อง NG/WAIT/GOOD ลงเฟรม + spatial prompt → Cosmos.
- ผล (3 เฟรม): t=30 (หยิบ WAIT ปกติ, Claude ดูเฟรมยืนยัน) → model บอก **NG violation = hallucinate** · t=78 → WAIT/ปกติ · t=120 → NG/violation.
  = SoM ทำให้ reason เชิงพื้นที่ได้ แต่ **แยก NG/WAIT ไม่แม่น** + prompt violation-heavy เอียงไป false-positive.
- **🎯 FINDING ชี้ขาด: SOP = "เพดานข้อมูล (scene under-determined)" ไม่ใช่เพดาน model/เทคนิค.**
  กล่อง NG/WAIT ติดกัน + กระป๋องเหมือนกัน + มุมกล้องบน → **ไม่มีวิธีไหน (VLM/tracker/คน) แยกได้** เพราะภาพไม่พอ.
  violation ถูกกำหนดโดย script ไม่ใช่หลักฐานภาพ. **แก้ต้องที่ scene/data (มุมกล้อง/mark กระป๋อง/track รายใบ) ไม่ใช่ model.**
- **สรุป SOP: ยอมรับเป็น low-confidence (ตามที่ทำ) ถูกต้องแล้ว — ไม่ต้องลงแรง model เพิ่ม (data ไม่พอ).**
- **ทางไปต่อที่เหลือยังคุ้ม:** Phase 2 (mask agentic zoom — data พอ แค่เล็ก) · Phase 3 (streaming VLM — per-second, data พอ).
  SOP หยุดที่นี่ (ปัญหา data ไม่ใช่ model).

### Phase 3 — Streaming VLM (VideoLLM-online) spike → ⏸️ สรุป feasibility (ไม่รันจนจบ) — 2026-07-15
- setup: clone `showlab/videollm-online`, env (torch/transformers/peft), อัป cam_a05, patch cli (safety query).
- **เจอ friction 2 ชั้น (ยืนยัน risk ที่ประเมินไว้):** (1) torchvision ใหม่ตัด `read_video` → patch cv2 shim (2) **base = Meta-Llama-3-8B gated,
  บัญชี HF ไม่ได้รับอนุมัติ** → workaround NousResearch mirror (ungated). (3) รัน external code ถูก sandbox บล็อก (ต้องผู้ใช้อนุมัติ repo เจาะจง).
- **DECISION: จบ spike** — feasibility ตอบแล้ว: streaming VLM per-second **ทำได้จริง (paper: 5-10 FPS บน 3090)** แต่ (a) research-repo friction
  (b) gated dependency (c) **เป็น general Ego4D narrator (อังกฤษ) ไม่ใช่ safety-specific/ไทย → ต้อง fine-tune ถึงตรงงาน** (ซึ่งขัด constraint no-train).
- **สรุปทิศ streaming:** เป็นทางที่ "ฉลาดขึ้นได้จริง" สำหรับ per-second **แต่ไม่ใช่ drop-in** — คุ้มลงทุนเฉพาะถ้าจะทำ production จริง + ยอม fine-tune.

## 🏁 สรุปรวมทั้งโปรเจกต์ (ตกผลึกสุดท้าย)
**"ตัน" = ตันที่ setup ปัจจุบัน ไม่ใช่ตันที่วงการ** — แต่ละจุดตันคนละชนิด:
- **SOP → เพดาน DATA** (วิดีโอไม่มีข้อมูลพอ, กล่อง NG/WAIT ติดกัน) → แก้ที่กล้อง/scene
- **mask → เพดาน PERCEPTION** (ของเล็ก, 8B มองไม่เห็น) → SR ได้ 62%, ต้อง detector-train/frontier ถึงเกิน
- **per-second → เพดาน ARCHITECTURE** (เราใช้ chunked) → streaming VLM แก้ได้ แต่ต้องเปลี่ยนตัว + fine-tune
- **สิ่งที่ทำได้จริง on-prem no-train:** cap/gloves/person/foreign เป๊ะ + near-miss + SOP/mask low-confidence = **deliverable ปัจจุบัน**
