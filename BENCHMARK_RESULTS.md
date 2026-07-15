# 📊 GPU Benchmark Results — Cosmos Narration (CAM-A05)

**เป้าหมาย:** หา GPU config ที่ให้ narration **ชัด + ถี่ (ใกล้ per-second) + วิดีโอเร็ว (ใกล้ 1.0×)** คุ้มสุดสำหรับ live.
**Baseline:** 90 tokens = 2 ประโยคไทยชัด. โมเดล Cosmos-Reason2-8B (image mode, 2 เฟรม/call, vLLM).

---

## ⚠️ บทเรียนสำคัญ: Network RTT ปนผล (ต้องวัด co-located)

รอบแรกวัดผ่าน **SSH tunnel** (demo บน laptop → Cosmos บน GPU remote). พบว่า **payload 1MB/call (2 รูป base64) upload ข้าม tunnel ช้ามาก** โดยเฉพาะ host ไกล:

| | ผ่าน tunnel | server-side (co-located) |
|---|---|---|
| 2×4090 @ 90tok (1 call) | ~4-5s | **1.65s** |
| ต่างกัน | — | ~3s = network RTT ล้วน |

**→ ตัวเลขที่เชื่อได้ = co-located เท่านั้น** (รัน benchmark บนเครื่อง GPU, hit localhost)

---

## ✅ ผลจริง (co-located, 2×4090 แยกสตรีม)

| tokens (ความชัด) | 1-call latency | effective interval | **per-second** | ทุก-2วิ |
|---|---|---|---|---|
| **60** (1-1.5 ประโยค) | 1.14s | **0.91s** | **1.0× เต็มสปีด** ✅ | 1.0× |
| **90** (2 ประโยคเต็ม) | 1.65s | **1.19s** | **0.84×** | 1.0× |

**สรุป:** 2×4090 (co-located) ทำ **per-second + ชัด + วิดีโอเต็มสปีด** ได้จริง
- 60 tokens → per-second ที่ 1.0× (เต็มสปีด)
- 90 tokens → per-second ที่ 0.84× (เกือบเต็ม, ชัดกว่า)

---

## 📉 ผลผ่าน tunnel (network-polluted — ไว้อ้างอิงเชิงเปรียบเทียบเท่านั้น)

| config | 1-call | interval | per-second | ทุก-2วิ | หมายเหตุ |
|---|---|---|---|---|---|
| RTX 3090 ×1 | 5.14s | 5.07s | 0.2× | 0.39× | budget, ช้าสุด |
| RTX 4090 ×1 | 3.14s | 3.46s | 0.29× | 0.58× | +network |
| A100-40GB ×1 | 2.78s | 2.97s | 0.34× | 0.67× | +network |
| RTX 4090 ×2 | 3.53s | 1.80s | 0.55× | 1.0× | +network |

*(ตัวเลขพวกนี้รวม network RTT → สูงกว่าความจริง; ใช้เทียบ relative คร่าวๆ)*

**ข้อสังเกตที่ยังจริง:** A100-40GB เร็วกว่า 4090 เดี่ยวแค่ ~1.2× (ไม่ใช่ 2-3×) เพราะงานนี้ prefill รูปหนัก = compute-bound (4090 fp16 สูงพอๆ A100) ส่วน bandwidth ของ A100 ช่วยแค่ decode ที่สั้น

---

## 🏆 Verdict (ไม่เข้าข้าง)

| เป้าหมาย | คำตอบ |
|---|---|
| **เก่งสุด** (per-second+ชัดเต็ม+เต็มสปีด single card) | H100 (~$2-3/ชม, overkill) |
| **คุ้มสุด สำหรับ live per-second** | 🏆 **2×4090 co-located** (~$0.70/ชม) |
| **ถูกสุด สำหรับ demo** | offline JSON generate จาก 1×4090 ครั้งเดียว (~$0.10) → เล่น 0 GPU |
| **ไม่คุ้ม / ตัดทิ้ง** | A100-40GB (แพงกว่า 4090 แต่เดี่ยวไม่ถึง per-second) |

## 🔧 สถาปัตยกรรม demo ที่ถูกต้อง
- **อย่า** รัน demo บน laptop แล้ว tunnel `:18000` (ส่งรูป 1MB/call ข้ามเน็ต = ช้า)
- **ให้** รัน `live_demo_combined.py` บนเครื่อง GPU (co-located) แล้ว tunnel แค่ `:5003` (หน้าเว็บเบา)
- หรือ **generate JSON offline** → demo เล่นจากไฟล์ 0 GPU (เร็ว 1.0× per-second เนียน)

## 🎯 คำแนะนำสุดท้าย
- **demo สด:** 2×4090 co-located, 60-90 tokens, per-second — ไม่ต้องแตะ A100/H100
- **demo ประหยัด:** generate `cam_a05_timeline.json` (per-second) → เล่น offline ฟรี
- per-second อาจไม่จำเป็นด้วยซ้ำ — "ทุก-2วิ + ชัดเต็ม + เต็มสปีด" ก็เนียนมากสำหรับ safety narration
