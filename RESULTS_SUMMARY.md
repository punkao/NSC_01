# RESULTS SUMMARY — Real VLM Safety Detection (CAM-A05)

> Snapshot 2026-07-15 · ทีม model (kaopun) · รายละเอียดเต็ม = [`WORKLOG.md`](WORKLOG.md) ·
> แผน = [`WORKPLAN.md`](WORKPLAN.md)

## สถานะรวม: 🟢 PPE ถึงเพดาน no-train VLM แล้ว (วัดครบด้วย Claude-GT) — deliverable พร้อม, เหลือ polish live demo + ส่งทีม

## สิ่งที่ทำได้แล้ว
- **AI ตรวจ event จากวิดีโอเองครบ 5 ประเภท** (แทน mock ปั้นมือ): PPE, unauthorized_person, SOP,
  near_miss, hygiene/foreign_object — เป็นภาษาไทย, schema เดียวกับ mock (POST `/api/events/bulk` ได้).
- **โมเดล:** Cosmos-Reason2-8B (vLLM, BF16) บน RTX 3090/4090 24GB. ชนะ Qwen3-VL-8B ที่เทียบ.
- **Live demo (`live_demo.py`):** วิดีโอ + แจ้งเตือนสด จากโมเดล ณ วินาทีนั้น (ไม่ใช่ JSON). http://localhost:5000

## สถาปัตยกรรม 2-tier (พิสูจน์แล้วว่าจำเป็น)
| Tier | เหตุ | วิธี | latency |
|---|---|---|---|
| **Image** (per-frame 1080p) | PPE, คนนอก, foreign object | เฟรมเดียว → Cosmos | **~1.85s** (realtime) |
| **Video** (chunked 480p) | SOP, near_miss | หลายเฟรม → Cosmos | ~15–30s |

- **ทำไม 2-tier:** video ย่อภาพ→มองไม่เห็น PPE (0/2); image เฟรมเดียว→ตัดสิน SOP ไม่ได้ (Phase 0 gate FAIL).
- SOP/near-miss = motion → ต้อง temporal (เฟรมเดียวไม่พอ — พิสูจน์ด้วยภาพ: NG/WAIT/GOOD boxes แยกทิศทางไม่ได้).

## ตัวเลข — วัดด้วย Claude-GT (เฉลยจริง per-frame, trust ได้)
**Event timeline (`cam_a05_ai_events.json` = `_final`, 10 span events):** Recall(type) **100% (8/8)** · Precision **100% (10/10)** · near-miss **DETECTED**
- ⚠️ **precision นี้เป็นระดับ span/segment ไม่ใช่ต่อวินาที** — โมเดล over-detect sop ช่วง 02:15–03:30 (span ยุบไว้ + evaluate segment-overlap กลบ). ถ้าต้องการ granular ต่อวินาทีแบบ mock: reproduce แบบซื่อสัตย์ไม่ได้ (VLM detect ทุก 15s chunk ไม่ใช่ 2s) — ดู `expand_granular.py` + WORKLOG.
- deliverable = **span (incident windows)** เลือกแทน granular เพราะซื่อสัตย์กับความละเอียดจริง + เหมาะ alert/timeline (ไม่สแปม).

**PPE per-item (best config, no-train, on-prem):**
| item | recall | FP | วิธี |
|---|:---:|:---:|---|
| cap (หมวก) | **100%** | 0 | Cosmos full-frame |
| gloves (ถุงมือ) | **100%** | 4 | Cosmos full-frame |
| person / foreign | ✅ | ~0 | Cosmos full-frame |
| mask (หน้ากาก) | **62%** | 4 | SR-head (EDSR-4x) + face-visibility gate, **offline** |

## บทเรียน / เพดานที่พิสูจน์แล้ว (honest)
1. **mask = เพดาน no-train VLM (62%)** — mask ดึงลงคาง เล็ก/เกรน เกินกำลัง Cosmos-8B (มันบอกเอง face_visible=false แม้ SR).
   พิสูจน์ 3 เส้น: detector สำเร็จรูป transfer-fail · SoM crop พัง gloves · SR ได้ recall แต่ต้อง gate. เป๊ะ 100% ต้อง train/frontier (ขัด constraint).
2. **แก้ precision ที่ post-processing ไม่ใช่ prompt** · **วัดทุก item before/after** (SR ทำ mask ดีแต่เคยพัง gloves/FP ถ้าไม่ gate).
3. **SR หนักบน CPU (~3s/หัว)** → mask เป็น offline overlay ไม่ใช่ live per-frame.
4. **N=1** (วิดีโอเดียว) — เป็น demo คลิปเดียวโดยตั้งใจ (generalization out of scope).

## เหลือทำ
- Polish live demo (เอา timeline สะอาดเข้า · ลด latency person · mask overlay) → verify + อัดคลิป.
- teardown GPU + revoke HF token · อัป `MODEL_HANDOFF_TO_TEAM.md` ส่งทีม integration.

## Infra / วิธีรัน
- Vast: `ssh -p 44915 root@49.0.90.52` · Cosmos serve = `serve_cosmos.sh` (gpu_util 0.90, video+image).
- Live demo: tunnel `ssh -N -L 18000:localhost:18000 -p 44915 root@49.0.90.52` + `python live_demo.py`.
- Gotchas: Cosmos ตอบใน `message.reasoning` · media ใต้ `/workspace` · video tier ต้อง ≤480p (1080p OOM) ·
  console ไทยใช้ `PYTHONIOENCODING=utf-8`.
