# HANDOFF — ส่งต่องาน Real VLM Pipeline (CAM-A05)

> # 🛑 ไฟล์นี้ล้าสมัย (2026-07-14) — เริ่มที่ `RESUME_HERE.md` แทน
>
> ไฟล์นี้เขียนว่า *"มีเฉลยจริงแล้ว (definitive)"* — **เฉลยชุดนั้นผิด 32 จุด** และถูกแทนที่ด้วย `claude_gt_v4.json` แล้ว
> ตัวเลขในไฟล์นี้ (`gloves 100% · mask 12% · FP 0 · recall 71%`) **ผิดทั้งหมด**
> ของจริง: หมวก 100% · ถุงมือ 57% · หน้ากาก 80% · **รวม 82%** · FP 5 → ดู `MEASUREMENTS.md`
>
> ⚠️ การตัดสินใจในไฟล์นี้ที่ว่า *"หน้ากากไม่ใช่ requirement → Cosmos แข็งพอแล้ว"*
> **เกิดจากเฉลยที่พัง** — ความจริงหน้ากากทำได้ 80% และเป็นจุดแข็ง ไม่ใช่จุดที่ต้องตัดทิ้ง
>
> เก็บไว้เป็นประวัติเท่านั้น

---


> อ่านไฟล์นี้ก่อนเริ่ม แล้วอ่าน **`spike/WORKLOG.md`** เพื่อ context เต็ม (research → decision →
> ผลลัพธ์ทุก run). ไฟล์นี้คือ "resume ตรงนี้ได้เลย".

## ⭐ LATEST STATE (2026-07-14 ค่ำ — resume ตรงนี้)
**อ่าน:** `WORKLOG.md` (log เต็ม, entry ล่าสุดล่างสุด) · `VLM_VIDEO_PLAYBOOK.md` (ทิศทางล่าสุด) ·
`RESULTS_SUMMARY.md` · `claude_gt_report.txt` (Cosmos error map) · `RESEARCH_METHODS.md`

- **✅ มีเฉลยจริงแล้ว (definitive):** `claude_gt.json` — Claude อ่านทั้งคลิป high-res crop 74 เฟรม (per-hand).
  `diff_gt.py` → **Cosmos: cap 100% · gloves 100% · mask 12% (1/8) · FP 0 · recall รวม 71%.**
  → **จุดอ่อนเดียว = หน้ากาก** (ของเล็ก/ดึงลงคาง). วิธีวัดนี้ = เครื่องมือที่ trust ได้ (ใช้กับวิดีโอ 2 ได้).
- **🎯 DECISION ใหม่ (ผู้ใช้ยืนยัน):** **หน้ากากไม่ใช่ requirement จริง** → **Cosmos แข็งพอแล้ว** (cap+gloves 100%).
  และ **ยึดทาง VLM video understanding — ไม่เอา YOLO ที่ต้องเทรน.**
- **🔬 ทิศทางที่ตกผลึก (ดู `VLM_VIDEO_PLAYBOOK.md`):** วิธี production จริง (NVIDIA VSS) = **VLM + zero-shot
  detector "ตัวชี้" (Grounding DINO, ไม่ต้องเทรน)** + reasoning prompt (CoT + persona + adversarial self-verify)
  + Set-of-Mark overlay + temporal (chunk + `ppe_tracker`). ทุกอย่าง NO training, ยัง VLM-centric 100%.
- **👉 งานถัดไป (เลือก):** (a) prototype **Grounding DINO + Cosmos** บน cam_a05 (ต้อง GPU) ดูว่าแม่นขึ้นไหม ·
  (b) e2e integrate เข้า backend (mask ตัดทิ้งได้) · (c) วิดีโอที่ 2 (generalization ด้วย Claude-GT).
- **ทำไว้แล้ว:** `ppe_tracker.py` (LiveTracker) wire เข้า `live_demo.py` แล้ว (verify batch ผ่าน, ยังไม่ test live).
- **🔴 Vast ปิดแล้ว — เช่าใหม่** (RTX 4090/3090 24GB, template vLLM): อัป `spike/` + `serve_cosmos.sh` +
  วิดีโอ (`cam_a05_1080p.mp4` image / `cam_a05_720p.mp4` demo) + HF token ใน `/workspace/.hf_env` →
  `setsid bash /workspace/spike/serve_cosmos.sh > /workspace/vllm_cosmos.log 2>&1 &`.
- **วิธีสร้างเฉลย/วัด (ทำเองได้ ไม่ต้อง GPU):** ดูโค้ดใน `WORKLOG` — build crop-montage (PIL) → Claude อ่าน
  label → `claude_gt.json` → `diff_gt.py`. (crop หัว+มือ high-res = อ่าน mask/ถุงมือต่อมือได้).
- **Gotchas:** vLLM+4090 `gpu_util 0.90` (0.95 OOM) · video tier ≤480p (1080p OOM) · image tier 1080p ·
  `PYTHONIOENCODING=utf-8` (ไทย) · ffmpeg = imageio_ffmpeg · Cosmos ตอบใน `message.reasoning`.
- **⚠️ revoke HF token** (Falsity24) หลังจบ.

## รอบถัดไปเริ่มที่ไหน (อ่านก่อน)
- 👉 **แผน execution ละเอียด = `spike/WORKPLAN.md`** (ตัวหลัก มี env setup หลังเปลี่ยน user + Phase 0-7 +
  acceptance ทุก phase). **เริ่มที่ Phase 0 = เทสต์ SOP บนเฟรมนิ่ง (gate, ห้ามข้าม).**
- ทิศทางที่ล็อค: **VLM-only per-frame near-realtime** (PPE+คน+SOP, near-miss หยาบ) — เหตุผล+research อยู่ WORKLOG.
  (`PLAN_single_track.md` = ฉบับร่างเดิม, ถูกแทนด้วย WORKPLAN.md แล้ว)
- **เอกสารส่งทีม:** `spike/MODEL_HANDOFF_TO_TEAM.md` (สำหรับ integration/UI).
- **GPU:** ปิด vast พักได้ (การทดลองรอบนี้จบแล้ว). กลับมา serve ใหม่ด้วย `serve_cosmos.sh` (เซฟไว้ใน spike/
  แล้ว, **เปิด image+video** `--limit-mm-per-prompt '{"video":1,"image":2}'`):
  `setsid bash /workspace/spike/serve_cosmos.sh > /workspace/vllm_cosmos.log 2>&1 &` (ready ~130-260s).
- ถ้า instance ถูก destroy → อัป `serve_cosmos.sh` (ใน spike/) + วิดีโอ + สคริปต์กลับขึ้นเครื่องใหม่.

## TL;DR — ตอนนี้อยู่ตรงไหน
- **เป้า:** แทน event timeline ที่เป็น mock (ปั้นมือ) ด้วยผล VLM จริง ที่ตรวจ "เวลาไหนเกิดอะไร" เอง.
- **DoD ครบ 4/4 (🟢 DONE):** วิธีชนะ = **`Cosmos-Reason2-8B` + chunked 15s (v1 prompt) + `merge_events.py` 20s**.
  Recall(type) 75%, **Precision 62%**, near-miss @02:55 **DETECTED**, ไทยใช้ได้, near-realtime 1.16×.
- **คีย์ precision:** ไม่ได้มาจาก prompt — **post-hoc temporal merge** (รวม event ต่อเนื่องข้าม chunk เป็น
  span เดียว). ลอง suppress ใน prompt (v2/v3/v4) แล้ว **recall พังทุกครั้ง** (Cosmos เป็น binary — พอให้
  ทางออก "return []" มันเงียบหมด). **บทเรียน: แก้ precision ที่ post-processing ไม่ใช่ prompt.**
- **e2e สำเร็จ:** `cam_a05_ai_events.json` (8 events, merged) — schema เดียวกับ mock, POST `/api/events/bulk` ได้.
- **งานถัดไป = integrate เข้า backend** (ไม่ใช่ research/จูนอีกแล้ว). ดู §"งานถัดไป".
- **Trade-off ที่ค้าง:** timestamp หยาบลงจาก merge (sop 02:00–03:30 span เดียว); ppe recall ยัง 0/2.

## Environment / วิธีต่อ
- **Local repo:** `C:\Users\SaritpopRaktham\Desktop\P_kai\line-guard-smart-safe` (โฟลเดอร์ `spike/` มีทุกอย่าง).
- **Vast instance (ยังรันอยู่ — เสียเงินต่อเนื่อง):**
  ```
  ssh -p 53239 root@70.30.158.46
  ```
  (ใช้ SSH key บนเครื่องนี้ — ถ้า session ใหม่อยู่เครื่องเดียวกันจะต่อได้เลย)
- **vLLM ที่รันอยู่:** Cosmos-Reason2-8B, OpenAI API ที่ `http://localhost:18000/v1`,
  served-model-name = **`cosmos`**. Serve script: `/workspace/serve_cosmos.sh`.
- **ไฟล์บน remote:** `/workspace/spike/` (สคริปต์+วิดีโอ+ผล ครบ), วิดีโอ = `/workspace/spike/cam_a05.mp4`
  (720p 10MB, ย่อจาก 1080p แล้ว), token = `/workspace/.hf_env`.
- **GPU:** 1×RTX 3090 24GB **Ampere → ไม่มี FP8** (ใช้ BF16). max_model_len 16384, gpu_util 0.95.

## วิธีรัน (คำสั่งจริง บน remote)
```bash
ssh -p 53239 root@70.30.158.46
source /venv/main/bin/activate
cd /workspace/spike

# 1) chunked inference — arg: model, video, out, seg_seconds, [prompt_file]
#    (v1 prompt เดิม = default; อย่าใช้ v2/v3/v4 — ทำ recall พัง)
python chunk_infer.py cosmos /workspace/spike/cam_a05.mp4 result.json 15

# 2) MERGE (คีย์สู่ precision) — รวม event ต่อเนื่องข้าม chunk เป็น span เดียว, gap 20s
python merge_events.py result.json result_merged.json 20

# 3) ให้คะแนนเทียบเฉลย (ต้องได้ P≥60 R≥70 near-miss DETECTED)
python evaluate.py --pred result_merged.json

# 4) แปลงเป็น schema frontend (เหมือน mock) — ใช้ผล MERGED
python to_bulk_events.py result_merged.json cam_a05_ai_events.json CAM-A05
```

## Gotchas (บทเรียนที่เสียเวลามาแล้ว — อย่าพลาดซ้ำ)
1. **Cosmos ใส่คำตอบใน `message.reasoning`** (ไม่ใช่ `content`) — เป็น reasoning model. `chunk_infer.py`
   fallback `content → reasoning_content → reasoning` แล้ว.
2. **ไฟล์วิดีโอ/chunk ต้องอยู่ใต้ `/workspace`** — vLLM ตั้ง `--allowed-local-media-path /workspace`
   (เคยเขียนที่ /tmp แล้ว 400 ทุก request).
3. **KV cache จำกัด** — max_model_len เกิน 16384 จะ OOM. อย่าเพิ่ม.
4. **stop vLLM แล้ว EngineCore อาจค้าง** ยึด VRAM — เช็ค `fuser /dev/nvidia0`, kill PID ที่ค้าง.
5. **uplink ผู้ใช้ช้ามาก** (~39KB/s) — อย่าอัปไฟล์ใหญ่. วิดีโอย่อ 720p ด้วย
   imageio_ffmpeg (`C:\Users\...\Python314\...\imageio_ffmpeg\binaries\ffmpeg-*.exe`) แล้ว.
6. **Windows console แสดงไทยไม่ได้** (cp1252) — อย่า print ไทยตรงๆ ใน python บน local; เขียนลงไฟล์ UTF-8 แทน.

## Integration เข้า backend — สถานะ (increment 1 = DONE, code+unit test)
พอร์ต pipeline เข้า `backend/` แล้ว (ดู WORKLOG entry 2026-07-14):
- **ไฟล์ใหม่:** `backend/app/services/cosmos_events.py` (logic บริสุทธิ์) +
  `cosmos_runner.py` (chunk cv2 + เรียก vLLM + เขียน timeline Events/Alerts).
- **wire:** `POST /api/analyze/video` มี field `engine` = `qwen`(เดิม)/`cosmos`(ใหม่).
- **test:** `backend/tests/test_cosmos_events.py` → `python tests/test_cosmos_events.py` = **7/7 ผ่าน**
  (reproduce spike run 5: 21→8 events, near-miss@02:55 ยังอยู่).
- **prompt v1 ฝังใน `PROMPT_TEMPLATE`** ของ `cosmos_runner.py` (เติม SOP จาก DB). **ห้ามใช้ v2/v3/v4.**

### เหลือทำ (ตามลำดับ)
1. **[ต้องทำ] verify e2e จริง** (ยังไม่ได้ทำ — dev box ไม่มี backend deps/Postgres/GPU):
   - รัน vLLM Cosmos เป็น **local sidecar** ข้างๆ backend, `--allowed-local-media-path` ครอบ
     `COSMOS_CHUNK_DIR`. ตั้ง env `VLLM_BASE_URL`, `VLLM_MODEL=cosmos`.
   - `POST /api/analyze/video` (engine=cosmos, camera_id=CAM-A05, sop_id ของ CAM-A05) → เช็ค job done +
     `/api/events?camera_id=CAM-A05` ได้ timeline เดียวกับ mock + Event Timeline UI เด้งตามวิดีโอ.
   - เช็ก cv2 chunking (mp4v) ให้ vLLM decode ได้จริง (ถ้ามีปัญหา → สลับไป ffmpeg CLI แบบ `chunk_infer.py`).
2. **[optional] ppe recall (ยัง 0/2):** เติม "เช็ค PPE ของ worker แต่ละคน (มือ/หน้า/หัว)" ใน `PROMPT_TEMPLATE`
   — v4 เคยทำให้ ppe@03:30 โผล่ (พลาด GT 03:35 แค่ 1s). ระวัง destabilize → วัดด้วย `evaluate.py` ซ้ำก่อน.
3. **[optional] timestamp คมขึ้นสำหรับ near-miss:** fine pass crop 02:40–03:05 (fps สูง) แล้ว merge.
   ตอนนี้ near-miss เป็น span ~45s พอสำหรับ demo/alert.

## Open items / ต้องจัดการ
- ⚠️ **Revoke HF token** ที่เคยส่งในแชต (บัญชี Falsity24) → สร้างใหม่ที่ huggingface.co/settings/tokens.
- ⚠️ **Stop Vast instance** ถ้าจะเว้นช่วง (Cosmos กิน VRAM ~24GB, เสียเงินต่อเนื่อง). กลับมา serve ใหม่ด้วย
  `setsid bash /workspace/spike/serve_cosmos.sh > /workspace/vllm_cosmos.log 2>&1 &`.

## Ground truth (เฉลย) — 8 segments, span 01:13–03:38
sop_violation 01:13–02:03 · unauthorized 01:36–01:40 · hygiene 01:39 · **near_miss 02:55 (critical)** ·
ppe 02:59–03:00 + 03:35–03:38. อยู่ใน `ground_truth_cam_a05.json`.
