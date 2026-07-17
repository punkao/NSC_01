# 🗂️ ไฟล์ข้อมูล — อันไหนคือของจริง

> อัปเดต 2026-07-17 · **ตัวเลขทุกตัวในรายงานต้องมาจาก `MEASUREMENTS.md` เท่านั้น**
> ไฟล์เก่าที่ถูกแทนที่แล้วอยู่ใน `_archive/` (มี README อธิบายว่าทำไมไม่ใช้)

---

## ✅ ไฟล์ที่ใช้จริง (root)

### ผลงานที่ส่งมอบ
| ไฟล์ | คืออะไร | สร้างโดย |
|---|---|---|
| **`cam_a05_timeline.json`** | **ผลงานหลัก** — 220 คำบรรยาย + 11 เหตุการณ์ + ระดับความรุนแรง + SOP ระดับลัง | `generate_timeline.py` → `compose_narration.py` → `analyze_safety.py` → `sop_roi.py` |
| `cam_a05_ai_events.json` | เหตุการณ์อันตราย 11 รายการ (ต้นทางของชั้น CATCH) | curate + ตรวจสอบด้วยคน |

### เฉลยและผลวัด
| ไฟล์ | คืออะไร | หมายเหตุ |
|---|---|---|
| **`claude_gt_v4.json`** | **เฉลยที่ใช้จริง** — 74 จุดตรวจ พบการละเมิด **56 จุด** | ไล่ดูด้วยตาครบทุกเฟรม · การแก้ทุกจุดบันทึกในฟิลด์ `corrected` · **v3 ถูกแทนที่แล้ว** (ตรวจถุงมือจากภาพเล็กเกินไป จึงตกไป 3 จุด) |
| `image_obs.json` | คำตอบโมเดลรายเฟรม (หมวก/ถุงมือ/หน้ากาก จากเฟรมเต็ม) | รันใหม่ 2026-07-16 · ทำซ้ำได้ด้วย `image_tier.py` |
| `image_obs_sr.json` | คำตอบโมเดลสำหรับหน้ากาก (super-resolution) | ใช้คู่กับ `image_obs.json` |
| `image_events.json` | เหตุการณ์ที่ image tier ตรวจได้ | ผลพลอยได้จาก `image_tier.py` |
| `roi_scan.json` | มือยุ่งกับลัง WAIT/NG ทุกวินาที | `roi_scan.py` (ต้องใช้ GPU, 67 วินาที) |
| `bench_report_results.json` | เวลาตอบสนอง + throughput (1 GPU / 2 GPU) | `bench_report.py` |
| `env_report.json` | สเปกเครื่องและเวอร์ชันซอฟต์แวร์ที่ใช้วัด | `collect_env.py` |

---

## 🛑 เอกสารที่ล้าสมัย — ติดป้ายเตือนไว้แล้ว ห้ามอ้างตัวเลข

ไฟล์เหล่านี้เขียนก่อนพบว่าเฉลยผิด 32 จุด **ตัวเลขข้างในผิดแทบทุกตัว** (เช่น ถุงมือ 100%, หน้ากาก 62% "เพดาน", รวม 71%)
ยังเก็บไว้เป็นประวัติ แต่ **ทุกไฟล์มีป้ายเตือนที่หัวไฟล์แล้ว**

| ไฟล์ | ปัญหา | ใช้อะไรแทน |
|---|---|---|
| `MODEL_HANDOFF_TO_TEAM.md` | **อันตรายสุด** — จ่าหน้าว่าสำหรับทีม frontend อ่าน แต่ตัวเลขผิดหมด | `INTEGRATION_FOR_FRONTEND.md` §10 · `PROMPT_FOR_FRIEND_UPDATE.md` |
| `HANDOFF.md` | เขียนว่า "เฉลย definitive" ทั้งที่เฉลยนั้นผิด · ตัดสินใจตัดหน้ากากทิ้งเพราะเฉลยพัง | `RESUME_HERE.md` |
| `PROMPT_FOR_FRIEND.md` | ฉบับก่อนแก้เรื่องระบุลัง + ก่อนแก้เฉลย | `PROMPT_FOR_FRIEND_UPDATE.md` |
| `WORKLOG.md` | บันทึกตามเวลา — entry เก่าคือสิ่งที่เชื่อ ณ วันนั้น ไม่ใช่ข้อสรุป | `MEASUREMENTS.md` |

---

## 📄 เอกสารที่ต้องอ่านก่อน

| ไฟล์ | อ่านเมื่อ |
|---|---|
| **`RESUME_HERE.md`** | **เริ่มงานใหม่** — งานค้าง + สิ่งที่ห้ามลืม |
| **`MEASUREMENTS.md`** | **ต้องการตัวเลขใด ๆ** — มีทั้งผล วิธีวัด และคำสั่งทำซ้ำ |
| `REPORT_SECTION5.md` | รายงานบทที่ 5 (ต้นฉบับ) |
| `INTEGRATION_FOR_FRONTEND.md` | เชื่อมหน้าเว็บ / ส่งงานให้ทีม frontend |
| `DEMO_SUMMARY.md` | เตรียมสาธิต + เช็คลิสต์ก่อนโชว์สด |
| `_archive/README.md` | สงสัยว่าไฟล์เก่าอันไหนคืออะไร ทำไมไม่ใช้ |

---

## 🔁 ลำดับการรันใหม่ทั้งหมด (ถ้าเปลี่ยนวิดีโอ)

```bash
# --- ต้องมี GPU (รัน co-located บนเครื่อง GPU เท่านั้น) ---
python3 preflight.py                      # ยืนยันว่าเสิร์ฟ Cosmos-Reason2-8B จริง (กัน env ของเครื่องเช่า)
python3 image_tier.py                     # PPE 74 เฟรม        -> image_obs.json      (~121 วิ)
python3 som_sr_ppe.py                     # หน้ากาก + SR       -> image_obs_sr.json
python3 roi_scan.py --endpoints <ep0>,<ep1>   # ROI ระบุลัง     -> roi_scan.json       (~67 วิ)
python3 generate_timeline.py --no-box-names --endpoints <ep0>,<ep1>   # คำบรรยาย 220 จุด (~311 วิ)
python3 bench_report.py --endpoints <ep0>[,<ep1>] --label 1gpu|2gpu   # วัดความเร็ว

# --- ไม่ต้องใช้ GPU ---
python sop_roi.py                         # ROI -> box_activity / sop_events
python compose_narration.py               # เติมชื่อลังจาก ROI ลงคำบรรยาย
python analyze_safety.py                  # จับคู่กฎ R1-R10 + ระดับความรุนแรง (OpenRouter)
python sop_overview.py                    # สรุปภาพรวม SOP (OpenRouter)
python diff_gt.py                         # เทียบเฉลย -> recall/FP ต่อรายการ (= เลขในรายงาน)
```

> `python diff_gt.py` เฉย ๆ = **คอนฟิกที่ส่งมอบ** (หมวก/ถุงมือ จาก `image_obs.json` + หน้ากาก จาก `image_obs_sr.json`)
> ต้องได้ **46/56 (82%) · FP 5** · ถ้าได้ 46% แปลว่า `image_obs_sr.json` หาย ให้รัน `som_sr_ppe.py` ใหม่

> ⚠️ **ข้อควรระวังที่เจ็บมาแล้ว**
> - เฟรมสำหรับ **PPE** ต้องแตกด้วย `ffmpeg -ss <t>` (ตามที่ `image_tier.py` ทำเอง) เพราะเฉลยอิงชุดนี้
> - เฟรมสำหรับ **คำบรรยาย/ROI** ต้องแตกด้วย `ffmpeg -vf fps=1 -start_number 0` จากไฟล์ **1080p**
> - สองวิธีนี้ให้เฟรมคนละจังหวะ (ต่างกันเสี้ยววินาที) — **ห้ามสลับกัน**

---

## 🧹 ไฟล์เก่าอยู่ที่ไหน

| โฟลเดอร์ | มีอะไร |
|---|---|
| `_archive/ground_truth/` | เฉลยรุ่นเก่า (v1 ผิด 29 จุด, v2 แก้ไม่ครบ) |
| `_archive/superseded_eval/` | ผลวัดจากคอนฟิกที่เลิกใช้ (รวม `image_obs_prev.json` ที่เป็นต้นตอเลข "71% / FP=0") |
| `_archive/old_pipeline/` | ผลจากสถาปัตยกรรมรุ่นวิดีโอ (เลิกใช้เพราะ vLLM ล่ม + มองไม่เห็น PPE) |
| `_archive/intermediate/` | timeline ระหว่างทาง (รวมรุ่นที่บอกชื่อลังผิด 146/220 จุด) |
