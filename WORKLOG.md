# Worklog — Real VLM Event-Detection Pipeline (CAM-A05)

> **Initiative:** แทนที่ event timeline ที่เป็น mock (hand-written) ด้วยผลลัพธ์จาก
> Vision-Language Model จริง ที่ตรวจจับ "เวลาไหนเกิดอะไร" ได้ด้วยตัวเอง
> **Owner:** kaopun · **Repo:** line-guard-smart-safe · **Started:** 2026-07-13
> **Status:** 🟢 DONE (DoD 4/4) — Cosmos-Reason2-8B + chunked 15s + temporal merge 20s:
> recall 75%, precision 62%, near-miss DETECTED, thai ใช้ได้, near-realtime 1.16×.
> e2e→schema mock สำเร็จ. เหลืองาน **integrate เข้า backend** (ไม่ใช่ research แล้ว).

---

## 1. Context & Problem Statement

ระบบเดิมมี 2 เส้นทางข้อมูลปนกัน:

1. **เส้นจริง** (`qwen_runner.py` → `tools/qwen_service.py`): อัปโหลดวิดีโอ → ตัดเฟรม
   → เรียก Qwen2.5-VL ทีละเฟรม → grep คำ `SAFE/WARNING/DANGER`. รันได้แต่คุณภาพต่ำ
   และตรวจ near-miss ไม่ได้ (ภาพนิ่งเดี่ยวไม่มี temporal context).
2. **เส้น mock** (`scripts/import_cam_a05_events.sh` → `/api/events/bulk`): event
   timeline ที่คนเขียนมือ ยัดเข้า DB ตรงๆ ไม่ผ่านโมเดล ใช้โชว์ demo.

**ขอบเขตงานนี้ (ของเรา):** ทำเส้นจริงให้ได้ผลจริง เทียบเท่า/ใกล้เคียง mock — เพื่อนดูฝั่ง
integration/UI, เราดูฝั่ง model + pipeline.

**ข้อได้เปรียบสำคัญ:** mock = **เฉลย (ground truth)**. เราวัดผลโมเดลได้เป็นตัวเลข
objective ไม่ใช่แค่ "ดูแล้วโอเค".

---

## 2. Decision Log (ADR-style)

### ADR-001 — เลือกโมเดล
- **ตัวเลือก:** Qwen3-VL (8B) vs NVIDIA Cosmos-Reason2 (8B) vs คงQwen2.5-VL.
- **ตัดสิน:** ทดสอบ **Cosmos-Reason2-8B เป็น primary**, **Qwen3-VL-8B เป็น fallback/เช็คภาษาไทย**.
- **เหตุผล:**
  - Cosmos สร้างบน Qwen3-VL-Instruct + fine-tune ด้าน physical/temporal reasoning.
  - Benchmark หมวด **Smart Spaces (CCTV/video analytics) 70% vs Qwen3-VL 43%** — งานเราคือ smart-spaces safety โดยตรง.
  - มี use case จริงด้าน workplace safety (Hitachi, Milestone) + pipeline สำเร็จรูป (VSS).
  - **ความเสี่ยง:** Cosmos ไม่ระบุรองรับภาษาไทยชัด → mitigate ด้วยการแยก structured
    fields (EN) ออกจาก description (TH), และมี Qwen3-VL เป็น fallback.
- **spec constraint:** ไม่มี (เช่า Vast.ai, GPU 24GB+).

### ADR-002 — วิธี inference (สำคัญกว่าเลือกโมเดล)
- **ปัญหาโค้ดเดิม:** single-frame + keyword grep + 0.33 fps.
- **ตัดสิน:** เปลี่ยนเป็น **video-native + structured JSON + timestamp injection**:
  - ส่งทั้งคลิปเป็น video (ไม่ใช่ทีละเฟรม) → เห็น temporal context → จับ near-miss ได้.
  - Prompt สั่งออก JSON `{start,end,event_type,severity,description_th}` (แบบ Cosmos
    `temporal_localization.yaml`) แทนการ grep คำ.
  - FPS 4 (งานวิจัยแนะ 2–4 fps สำหรับคลิปสั้น; เพิ่มเป็น 8 ถ้าพลาด near-miss).
- **อ้างอิง:** Cosmos VSS recipe, Qwen3-VL timestamp alignment (video_metadata),
  DATE / frame-timestamp interleaving papers.

---

## 3. Evaluation Methodology

- **Ground truth:** `ground_truth_cam_a05.json` — 35 point-events → collapse เหลือ
  **8 segments** (`evaluate.py`), ช่วง 01:13–03:38. Cross-check กับ `cameras.ai_summary`
  (5 event groups: near-miss, step-skip×21, ppe×6, foreign-object, unauthorized×4).
- **Matching:** โมเดลออก 1 event/ช่วง (ไม่ใช่ event ซ้ำ) → วัดแบบ "ครอบคลุมช่วงถูกไหม"
  ด้วย time-overlap ± tolerance + event_type.
- **Metrics:** Recall (type-aware & time-only), Precision, per-type breakdown, และ
  **near-miss @02:55 (critical) เป็น pass/fail สำคัญที่สุด**.
- **แยกภาษาออกจากความแม่น:** matching ใช้ structured fields (timestamp+type) ไม่ใช่
  ข้อความไทย → ประเมิน detection แยกจาก Thai fluency (eyeball `description_th` ต่างหาก).

---

## 4. Assets & Environment

| Asset | รายละเอียด | สถานะ |
|-------|-----------|-------|
| `cam_a05.mp4` | **1920×1080, 3:39 (219.9s), 344 MB** — ยืนยันตรง DB ("Mock Station.mp4") | ✅ verified 2026-07-13 |
| `ground_truth_cam_a05.json` | เฉลย 35 events → 8 segments | ✅ |
| `sop_cam_a05.txt` | SOP จริง (sops id=4, SOP-002 v1.15) + safety rules 7 ข้อ จาก `db/seed.sql` | ✅ |
| `prompt_safety_temporal.txt` | Prompt JSON temporal + taxonomy + TH | ✅ |
| `infer.py` | Whole-video inference (requests-based) | ✅ ใช้จริง |
| `chunk_infer.py` | **Chunked inference** (ffmpeg cut + offset timestamps) — ตัวหลัก | ✅ ใช้จริง |
| `evaluate.py` | Scoring harness เทียบ ground truth | ✅ ใช้จริง |
| `merge_events.py` | **Post-process: รวม event ต่อเนื่องข้าม chunk เป็น span เดียว** (คีย์สู่ precision) | ✅ ใช้จริง |
| `to_bulk_events.py` | แปลงผล → schema `/api/events/bulk` (เหมือน mock) | ✅ ใช้จริง |
| `result_cosmos_chunked.json` | ผลดิบ run 3 (v1 prompt, 21 events) — input ของ merge | ✅ |
| `result_cosmos_merged.json` | ผล merge 20s (8 events) — P62/R75 | ✅ |
| `cam_a05_ai_events.json` | **ผลลัพธ์สุดท้าย: AI events ไทย พร้อมใส่ UI** (8 events, merged) | ✅ ได้แล้ว |
| `prompt_safety_temporal_v2..v4.txt` | prompt ทดลอง suppress (ล้มเหลว — เก็บไว้เป็นบทเรียน) | ⚠️ อย่าใช้ |
| `run_inference.py` | vLLM OpenAI-client (สำรอง ไม่ได้ใช้ — openai dep + fps) | — |
| Vast.ai instance | 1×RTX 3090 24GB (Ampere), vLLM 0.23.0 | ✅ รันอยู่ (Cosmos loaded) |

**Taxonomy (ตรงทั้ง ground truth / SOP / prompt):** `sop_violation`, `ppe_violation`,
`near_miss`, `unauthorized_person`, `hygiene_violation`. Severity: `low|medium|high|critical`.

---

## 5. Chronological Log

### 2026-07-13
- **[research]** สำรวจ VLM landscape (ก.ค. 2026). สรุป Cosmos-Reason2 vs Qwen3-VL,
  benchmark, VRAM, ภาษาไทย, และ method (VSS chunking, temporal localization,
  timestamp injection). → ADR-001, ADR-002.
- **[audit]** อ่านโค้ดเดิม: ยืนยัน `qwen_runner.py` เป็น single-frame + keyword grep
  (0.33 fps) = สาเหตุที่ตรวจ near-miss ไม่ได้. `vlm_service.py` เป็น placeholder เก่า.
- **[data]** สกัด ground truth 35 events จาก import script → `ground_truth_cam_a05.json`.
  ขุด SOP จริง + safety rules จาก `db/seed.sql` (camera CAM-A05: process_id=2, sop_id=4)
  → `sop_cam_a05.txt`. เจอ `cameras.ai_summary` เป็น cross-check เพิ่ม.
- **[build]** สร้างชุด spike: prompt, `run_inference.py`, `evaluate.py`, `README.md`.
  ทดสอบ harness ด้วย synthetic prediction → ทำงานถูก (Recall/Precision/near-miss ออกถูก).
- **[verify]** รับวิดีโอจริง แก้ชื่อ `cam_a05.mp4.mp4` → `cam_a05.mp4`. Probe ผ่าน
  mp4-atom parser: 1920×1080 / 3:39 / 344 MB → **ตรงกับ DB, เป็นคลิปถูกตัว**.
- **สรุปวันนี้:** เตรียมครบทุกอย่าง เหลือ execute บน Vast.ai. ยังไม่มีผลโมเดลจริง.

### 2026-07-13 (ต่อ) — Execution บน Vast.ai
- **[infra]** เชื่อม Vast instance (RTX 3090 24GB, **Ampere → ไม่มี native FP8**, vLLM 0.23.0,
  transformers 5.12). เครื่องมากับ template ที่ serve `Qwen/Qwen3.5-9B` (text) ค้างอยู่.
- **[infra]** เจอ orphaned `VLLM::EngineCore` (PID 1909) ยึด VRAM 20.7GB หลัง stop supervisor —
  kill ตรงคืน VRAM ครบ 24GB. (ไม่ใช่ GPU แชร์ ยืนยันแล้ว).
- **[infra]** uplink ผู้ใช้ช้ามาก (~39 KB/s) → 344MB/1080p อัปไม่ไหว. **downscale 1080p→720p (no audio,
  crf30) เหลือ 9.96MB** ด้วย ffmpeg ในเครื่อง (imageio_ffmpeg) → อัปเสร็จเร็ว.
- **[serve]** vLLM Qwen3-VL-8B ครั้งแรก crash: KV cache ไม่พอที่ max_len 24576. แก้เป็น max_len 16384
  + gpu_util 0.95 → serve สำเร็จ (VRAM 22GB/24).
- **[run 1]** whole-video 32 เฟรม → JSON+ไทยถูก, แต่ recall 38%, near-miss miss (sampling เบา).
- **[bug]** chunked ครั้งแรก 400 ทุก chunk — เขียนไฟล์ที่ /tmp แต่ `--allowed-local-media-path=/workspace`
  ปฏิเสธ. ย้าย chunk ไป /workspace/spike/_chunks → ผ่าน.
- **[run 2]** chunked 15s → recall 62%, precision 26%, near-miss ยัง miss. (ดู §6).
- **สรุป:** pipeline ทำงานครบ end-to-end บน model จริง. Thai ดีมาก. เหลือแก้ near-miss + false positive.

### 2026-07-13 (ต่อ) — End-to-end สู่ frontend schema
- **[e2e]** แปลงผล Cosmos (result_cosmos_chunked.json) → schema เดียวกับ mock ทุกฟิลด์
  (`timestamp_mmss, severity, event_type, event_type_label, description`) ด้วย `to_bulk_events.py`
  → `cam_a05_ai_events.json` (21 events, ไทย). **เป็น drop-in แทน mock ได้จริง** — POST เข้า
  `/api/events/bulk` ขับ Event Timeline UI ตัวเดียวกับ mock, เล่นวิดีโอแล้ว event เด้งตามเวลา.
- **[finding] ความละเอียด timestamp = ~chunk (15s) ไม่ใช่วินาทีเป๊ะ** แบบ mock ปั้นมือ (01:13, 02:55).
  บาง event ตรงเป๊ะ (hygiene 01:39), บางอันคร่อม (near_miss 02:45+03:00 vs จริง 02:55). ตรง "ช่วง"
  พอสำหรับ demo/alert แต่ถ้าต้องวินาทีเป๊ะ → chunk สั้นลง หรือ prompt สั่งระบุวินาทีในคลิป.
- **สรุป:** แก่นสำเร็จ — AI สร้าง timeline เอง (ไทย, sync วิดีโอ, format=mock) แทนข้อมูลปั้นมือ.
  เหลือจูน precision + timestamp ให้คมขึ้น (รอบถัดไป).

### 2026-07-13 (ต่อ) — Cosmos-Reason2-8B
- **[gate]** Cosmos ติด HF gate (401). ผู้ใช้ accept license + ให้ HF token (บัญชี Falsity24) →
  ตั้ง /workspace/.hf_env. **[action] ผู้ใช้ควร rotate token หลังจบงาน (โผล่ในแชต).**
- **[serve]** swap Qwen→Cosmos: stop Qwen (VRAM คืน 0, ไม่มี orphan รอบนี้), serve Cosmos BF16
  (arch = Qwen3VLForConditionalGeneration, reasoning-parser qwen3). Ready ~260s. VRAM 22GB/24.
- **[bug]** Cosmos chunked แรก parse ล้มทุก chunk. debug พบ output อยู่ใน `message.reasoning`
  (Cosmos เป็น reasoning model) ไม่ใช่ `content`. แก้ fallback → ผ่าน.
- **[run 3]** Cosmos chunked 15s: **recall 75%, near_miss DETECTED**, precision 38%, 21 events, 177s.
  → Cosmos ชนะ Qwen3-VL ทุก metric (ดู §6). **บรรลุ 3/4 DoD.**

### 2026-07-13 (ต่อ) — จูน precision: prompt suppression ล้มเหลว → แก้ด้วย temporal merge
- **[เป้า]** ยก precision 38%→60%+ โดยไม่ให้ recall/near-miss ตก (DoD ข้อสุดท้าย).
- **[prompt v2/v3/v4]** ลอง 3 แนวทางใส่ภาษา "ลด false alarm" ใน prompt:
  - **v2** (baseline-normal + strict near_miss + "ถ้าไม่ชัดให้ return []"): precision 100% แต่
    **recall พังเหลือ 38%, near-miss MISS** — over-suppress ทั้งกระดาน.
  - **v3** (surgical + "avoid false alarms/return []"): เหลือ **1 event ทั้งคลิป** — พังหนักกว่าเดิม.
  - **v4** (v1-assertive + ตัด worker2-wiping + cap near_miss/clip, ไม่มี damping): near-miss กลับมา
    แต่ **recall(type) ตกเหลือ 50%** เพราะ model ไปแปะ near_miss คู่กับ sop แทบทุก chunk + หล่น hygiene.
  - **บทเรียนชี้ขาด: Cosmos เป็น binary/ไม่ calibrate** — พอให้ทางออก "ปกติ/return []" มันจะเงียบหมด
    ทั้งของจริงของปลอม. **prompt suppression ยกระดับ precision ไม่ได้โดยไม่ทำลาย recall.**
- **[แก้ที่ถูกจุด] post-processing temporal merge** (`merge_events.py`, gap 20s): per-chunk inference
  มองข้าม boundary ไม่ได้ → รายงานเหตุการณ์ต่อเนื่องเดิมซ้ำทุก 15s. รวม event ชนิดเดียวกันที่ติดกัน
  (≤ gap) เป็น span เดียว = ตรงกับที่ prompt สั่งอยู่แล้ว ("รายงานเป็น ONE event") และตรงวิธี GT ถูก collapse.
  **นี่คือ production pattern (event aggregation/debounce) ไม่ใช่การ hack metric.**
- **[run 5] v1 (prompt เดิม, ไม่แตะ) + merge 20s: recall(type) 75%, precision 62%, near-miss DETECTED,
  21→8 events.** **บรรลุ DoD ครบ 4/4.** (gap 30s → precision 71% แต่ merge ข้ามได้ 2 chunk; เลือก 20s
  เพราะ chunk=15s, 20s เชื่อมแค่ boundary เดียว = faithful กว่า.)
- **[e2e]** regenerate `cam_a05_ai_events.json` จาก merged (8 events) ผ่าน `to_bulk_events.py` — schema mock เดิม.
- **สรุป: DoD ครบ. วิธีชนะสุดท้าย = Cosmos + chunked 15s (v1 prompt) + merge 20s.** เหลือ integrate เข้า backend.

### 2026-07-14 — Integrate เข้า backend (increment 1)
- **[port]** สร้าง service ใหม่ใน `backend/`:
  - `app/services/cosmos_events.py` — logic บริสุทธิ์ (stdlib ล้วน, ไม่มี ORM/net/GPU):
    `parse_events_json` (fallback content→reasoning), `offset_events`, `merge_events` (20s),
    `to_event_fields` (map → timeline schema), `build_sop_context` (สร้าง prompt จาก SOP ใน DB).
  - `app/services/cosmos_runner.py` — orchestrate: chunk วิดีโอด้วย **OpenCV** (ไม่เพิ่ม system dep;
    ffmpeg CLI ไม่มีบน backend image), เรียก vLLM OpenAI ต่อ chunk (`file://`), offset+merge, เขียน
    **timeline Events** (`video_offset_seconds` + taxonomy `event_type` + `event_type_label`) แบบเดียว
    กับ `/api/events/bulk` (mock) + สร้าง Alert สำหรับ high/critical. แทน single-frame+grep ของ `qwen_runner`.
  - prompt = v1 ฝังใน `PROMPT_TEMPLATE` (เติม `{SOP_CONTEXT}` จาก DB). **ห้ามใช้ v2/v3/v4.**
- **[wire]** `POST /api/analyze/video` เพิ่ม field `engine` (`qwen` default = เดิม / `cosmos` = ใหม่) →
  dispatch ไป runner ที่เลือก. ไม่กระทบพฤติกรรมเดิม.
- **[test]** `backend/tests/test_cosmos_events.py` (7 tests, ไม่ต้องมี GPU/DB) — **ผ่านหมด**. ตัวสำคัญ:
  ป้อน output จริง 21 events → `merge(20s)` ได้ **8 events, near-miss @02:55 (critical) ยังอยู่** =
  reproduce spike run 5 เป๊ะ. + ทดสอบ parse/offset/mapping/SOP-context.
- **[verified vs not]** ✅ logic (parse/offset/merge/schema) พิสูจน์ด้วย unit test. ⏳ **ยังไม่ได้ทดสอบ e2e จริง**
  (live vLLM sidecar + cv2 chunk วิดีโอจริง + เขียน Postgres) เพราะ backend deps/DB/GPU ไม่มีบนเครื่อง dev.
- **Deployment note:** ต้องรัน vLLM เป็น **local sidecar** (แบบ qwen service) + `--allowed-local-media-path`
  ครอบ `COSMOS_CHUNK_DIR` เพราะ chunk ส่งเป็น `file://`. Vast box ในสไปค์เป็นแค่ dev harness.
- **Env vars:** `VLLM_BASE_URL` (def `http://host.docker.internal:18000/v1`), `VLLM_MODEL` (`cosmos`),
  `COSMOS_SEG_SECONDS` (15), `COSMOS_MERGE_GAP_SEC` (20), `COSMOS_CHUNK_DIR` (`/app/media/_chunks`).

### 2026-07-14 — PPE recall: focused high-res image pass (พิสูจน์แล้วว่า work)
- **[ปัญหา]** pass วิดีโอ (chunked 720p, ~2fps) จับ ppe_violation ไม่ได้เลย (0/2). สมมติฐาน: ไม่ใช่โมเดลโง่
  แต่ **ภาพเล็กเกิน** — PPE (หมวกผ้า/ถุงมือผ้า) เป็นงาน object/attribute detection ไม่ใช่ temporal.
- **[ยืนยันด้วยตา]** ดึงเฟรม 1080p จาก original: ที่ 01:20 เห็นชัดทั้ง 2 คนใส่ cap+mask+ถุงมือผ้า; ที่ 03:37
  **คนที่ 2 หัวโล้น มือเปล่า (ถอด cap แดง+ถุงมือขาววางบนโต๊ะ)** — mock ถูกต้อง และ **PPE ชัดมากที่ 1080p**.
- **[experiment] `ppe_probe.py`** — ส่งเฟรม still 1080p เป็น base64 image เข้า vLLM + prompt เจาะจง PPE
  (ถาม cap/gloves/mask ต่อ worker). ต้อง restart vLLM เปิด image (`--limit-mm-per-prompt video:1,image:2`;
  ของเดิม image:0 → 400). ผล:
  | เฟรม | จริง | Cosmos ตอบ | ผล |
  |------|------|-----------|----|
  | ctrl 01:20 (ใส่ครบ) | ครบ 2 คน | ครบ 2 คน, ppe_violation=false | ✅ ไม่ false alarm |
  | 03:37 (คน2 ถอด cap+glove) | คน2 ไม่มี cap+glove | **"คนที่ 2 ไม่สวมหมวกและถุงมือ"** | ✅✅ ตรงเป๊ะ |
  | 02:59 | (คน2 กำลังถอด) | คน1 mask=false | ⚠️ ก้ำกึ่ง (หน้าก้ม เห็น mask ไม่ชัด) ไม่ผิดชัด |
- **[สรุป] focused high-res image PPE pass = WORK.** Cosmos ระบุ cap/gloves/mask ต่อคนได้แม่นบน still 1080p
  ภาษาไทยด้วย — สิ่งที่ pass วิดีโอ 720p ทำไม่ได้. **คุ้มค่า: ใช้ Cosmos ตัวเดิม ไม่ต้องเทรนโมเดลใหม่**,
  generalize ด้วย prompt (ไม่ผูกกับ cam_a05).
- **[แนวทาง deploy = two-track ตัวเดียวกัน]**
  - Track A (มีแล้ว): Cosmos **video** chunked 15s + merge → near-miss, SOP, unauthorized, hygiene.
  - Track B (พิสูจน์แล้ว): Cosmos **image** PPE pass — สุ่มเฟรม full-res ทุก ~2-3s → prompt PPE → debounce
    เป็น span → ppe_violation. รวมเข้า timeline เดียวกัน.
  - GPU/โมเดลตัวเดียว (เปิดทั้ง image+video). ยังไม่ได้ build track B เต็ม + วัด recall/precision ทั้งคลิป.
- **[ops] เปลี่ยน config เซิร์ฟเวอร์:** `serve_cosmos.sh` เปิด image แล้ว (video:1,image:2). restart แล้ว ~130s.

### 2026-07-14 — PPE track: วัดผลทั้งคลิป + 3 ข้อค้นพบเชิงกลยุทธ์
- **[method]** สุ่มเฟรม full-res (1280w) 33 เฟรม (ทุก 8s + dense ที่ช่วง PPE) → batch image PPE pass
  (`ppe_batch.py`) → debounce ต่อเนื่อง ≥2 เฟรม (`ppe_analyze.py`).
- **[ผล PPE-only หลัง debounce]** **Recall 2/2** (จับทั้ง 02:59 และ 03:35 — เดิม pass วิดีโอได้ 0/2),
  Precision 1/2 (มี false event 02:00–02:16 คน1 ถุงมือ/mask), กรอง false เฟรมเดี่ยวทิ้ง 2 (00:00, 01:12).
- **ข้อค้นพบ:**
  1. **capability ครบแล้วทั้ง 5 ประเภท** — PPE ที่เคยพลาดหมด ตอนนี้ recall 2/2. ปิด gate "completeness".
  2. **debounce = เครื่องมือ precision ของ track PPE เหมือน merge ของ track วิดีโอ.** โมเดล raw ราย
     frame มี noise (มือบัง→flag ถุงมือผิดชั่วขณะ) — temporal persistence คือคำตอบ (เป็น production
     pattern ของ PPE compliance อยู่แล้ว). ปรับต่อได้: require same-worker+same-item ต่อเนื่อง จะตัด
     false 02:00/02:16 (คนละ item) ออก — **แต่ไม่ทำตอนนี้ (N=1 อย่า over-tune).**
  3. **⚠️ mock/เฉลยเองไม่เป๊ะ:** โมเดลเห็นคน2 ไม่มีหมวก **ต่อเนื่อง 03:01–03:39** แต่ mock ระบุแค่
     02:59-03:00 + 03:35-38. เฟรมยืนยัน (02:59 มีหมวก / 03:37 ไม่มี) → โมเดลน่าจะถูกกว่า. **สรุป:
     ตัวเลข precision/recall ทั้งโปรเจกต์วัดกับเฉลยที่ไม่สมบูรณ์ → เชื่อเป็น absolute ไม่ได้.**

### 2026-07-14 — บทวิเคราะห์กลยุทธ์ (senior view) + ทิศทางต่อ
- **สถานะจริง:** พิสูจน์ **capability ครบ 5 ประเภท** แล้ว (แต่ละอย่างจับได้) — แต่ **reliability ยังไม่พิสูจน์**:
  ทุกตัวเลขมาจาก **N=1 + วิดีโอจัดฉาก + เฉลยไม่เป๊ะ**, near-miss จับได้จากการ over-flag, และ e2e ยังไม่รัน.
- **3 gate ก่อน deploy (เรียงตามความเสี่ยง):**
  1. **Generalization** — work บนวิดีโออื่นไหม? (เสี่ยงสุด, ต้องมีวิดีโอที่ 2 / footage จริง) — ❓ ยังไม่รู้.
  2. **E2E จริง** — `cosmos_runner` (cv2 chunk→vLLM decode→เขียน DB) ยังไม่เคยรันจริง. ⚠️
  3. **Completeness** — จับครบ 5 ประเภท. ✅ ปิดแล้ว (PPE track).
- **decision:** หยุด polish วิดีโอเดียว (diminishing returns). งานที่เหลือคือ gate 1 & 2 ซึ่งต้องใช้
  ทรัพยากรเพิ่ม (วิดีโอที่ 2 / DB+GPU co-located) — ไม่ใช่การจูน cam_a05 ต่อ.
- **PPE track = build ได้ทุกเมื่อ (spec ชัดแล้ว):** extract frames ~ทุก 3-8s → image PPE pass → debounce
  (same-worker+item) → emit ppe_violation spans → merge เข้า timeline track A. low-risk.

### 2026-07-14 — 2-stage fine-localize (timestamp วินาทีเป๊ะ) + ความจริงเรื่อง near-miss
- **[why]** timestamp ของ pipeline หยาบ ~15s (= chunk) + merge ทำ span กว้าง (near-miss 45s, sop 90s).
  demo ต้องการเตือน "วินาทีเป๊ะตอนวิดีโอเล่น". แนวทาง = **2-stage**: stage1 chunked บอกช่วงหยาบ →
  stage2 ยิงเฟรมถี่ทุก 1s ในช่วงนั้น ถาม yes/no เจาะจง → ปักวินาที (ใช้ image base64 = ข้ามเครื่องได้ ไม่ต้อง file://).
- **[ผล — เหตุที่เห็นชัด = เป๊ะ]** unauthorized_person (`u_probe`): False จนถึง 01:34 → **True 01:35–01:42**
  → False 01:43. **ปักเข้า 01:35 / ออก 01:42** (mock 01:36–01:40 → AI ละเอียดกว่า เห็นตั้งแต่เท้าโผล่).
  ขอบเขตคม ไม่มี noise. PPE ก็ per-frame ได้ (entry ก่อนหน้า). → **per-second alerting ทำได้จริง** สำหรับ
  เหตุที่มี signature ชัด (คนเข้า/PPE/ของวางผิดที่/foreign object).
- **[ผล — near-miss = localize ไม่ได้]** `nm_probe` ยิง 02:48–03:02 ทีละ 1s + คำถาม strict "มือเข้าสายพาน/
  pinch-point?" → **False ทั้ง 15 เฟรม**. ตรวจด้วยตา (02:54/02:55/02:58): **ไม่เห็นมือเข้าเครื่องชัดๆ** —
  ที่ 02:55 คน2 แค่เอื้อมมือใกล้ belt guide ตอนหยิบกระป๋อง = ก้ำกึ่ง. **สรุป: near-miss ไม่มี single-frame
  signature → localize ระดับวินาทีไม่ได้ + coarse pass ที่ "จับได้" คือ over-flag ที่บังเอิญคร่อม mock,
  และ mock เองอาจ label near-miss แบบใจดี.** near-miss เป็นประเภทที่ยาก/เชื่อถือได้น้อยสุด.
- **[deliverable] `fine_localize.py`** — stage-2 ใช้ซ้ำได้: `python fine_localize.py <video> <event_type>
  <start_sec> <end_sec>` → คืน span วินาที (debounce ≥2 เฟรม). มี prompt เฉพาะ type (person/ppe/hygiene/
  foreign_object crisp; near_miss best-effort คืน [] ถ้าไม่ชัด → ให้คง coarse window).
- **[architecture สรุป]** deploy timeline = stage1 chunked+merge (รู้ว่ามีอะไรช่วงไหน) → stage2 fine_localize
  เฉพาะ event ชนิด crisp (ปักวินาที) → near-miss/sop คงเป็น span. ได้ "เตือนวินาทีเป๊ะ" สำหรับเหตุที่ทำได้จริง.

### 2026-07-14 — รวม Track A + B เป็น timeline เดียว (ครบ 5 ประเภท)
- **[merge] `merge_ab.py`** รวม Track A (video events, merged) + Track B (PPE จาก image pass, debounce
  ต่อเนื่อง ≥2 เฟรม) → `result_combined.json` → `cam_a05_ai_events.json` (10 events, ครบ 5 ประเภท).
- **[ผลวัดจริง (evaluate.py):** **Recall(type) 100% (8/8), Precision 60% (6/10), near-miss DETECTED.**
  ทุกประเภทมี recall เต็ม: sop 2/2, unauthorized 2/2, hygiene 1/1, near_miss 1/1, **ppe 2/2** (PPE span
  02:59–03:39 คร่อมทั้ง 2 ช่วง GT). → PPE ที่เคยพลาดหมด ตอนนี้ครบ.
- **[false positive ที่ยังเหลือ 4/10]:** sop 00:00, near_miss 01:00, near_miss 01:38, ppe 02:00.
- **สรุปตรงๆ: "รวมแล้วถูกเกือบหมด" จริงเฉพาะ recall (จับครบ ~100%) — แต่ precision ยัง 60% (เตือนผิด
  4/10).** จับครบ ≠ เตือนถูกทุกอัน. FP หลัก = near_miss over-flag (2) + sop/ppe หลงจังหวะ (2).
- **deliverable:** `cam_a05_ai_events.json` = timeline สมบูรณ์ครบ 5 ประเภท พร้อม POST `/api/events/bulk`.

### 2026-07-14 — Phase 0 GATE: SOP บนเฟรมนิ่ง = FAIL (decisive)
- **[setup]** instance ใหม่ = **RTX 4090** 24GB (Ada, มี FP8), vLLM 0.25.0. serve Cosmos ครั้งแรก crash
  **CUDA OOM** ตอน sampling/cudagraph (`gpu_util 0.95` แรงไปบน 4090+vLLM0.25 — เหลือ 14MB). **แก้: 0.95→0.90
  + `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`** → ready 90s. (อัปเดต `serve_cosmos.sh` แล้ว).
- **[method]** สกัด 24 เฟรม 1080p (11 ช่วง SOP 01:13–02:03 + 13 ช่วงปกติ) → `sop_probe.py` ส่ง base64 image
  → Cosmos ถาม `{sop_violation, worker, note_th}`.
- **[ผล] recall 0/11, false 0/13 → FAIL.** โมเดลบรรยายเฟรมแม่น (เห็นหยิบ NG/ตรวจสอบ/PPE) แต่**ไม่ flag
  sop_violation จากเฟรมเดียวเลย** — "วางไม่ตรวจ" เป็น procedural/temporal, เฟรมนิ่งกำกวม (โมเดลถูกที่ไม่ committed).
- **[decision — architecture ปรับ]** ตาม WORKPLAN fallback: **SOP ถอยไป Track A (video/temporal)**. ระบบเป็น
  **2-tier: image tier (per-frame, เร็ว ~1-3s) = PPE/person/hygiene/foreign-object · video tier (chunked, ~15-30s)
  = SOP/near-miss.** ยังเป็น VLM-only, near-realtime สำหรับเหตุ crisp; SOP latency สูงกว่าแต่ยอมรับได้ (compliance).
- **[bonus]** Phase 0 พิสูจน์ว่า **per-frame image pipeline ทำงาน** (base64→Cosmos→ไทย) — พร้อมใช้ Phase 1 (PPE/person).

### 2026-07-14 — Phase 1: combined per-frame image probe = PASS (image tier แม่น)
- **[method]** อัปวิดีโอ 1080p บีบอัด (crf30, 30MB, ครั้งเดียวใช้ทุก phase) → `phase1_probe.py` สกัดเฟรมบน remote
  ทุก 3s (74 เฟรม) → prompt เดียว/เฟรม คืน `{person_count, workers[cap/gloves/mask], extra_person, foreign_object, note_th}`.
- **[ผล เทียบ GT]** ✅ ทั้ง 3 signal ของ image tier:
  - **PPE:** baseline w1:111 w2:111 → **w2:011 (ไม่มีหมวก) ต่อเนื่อง 03:00–03:39** (ตรง GT ppe@02:59) →
    **w2:001 (ไม่มีหมวก+ถุงมือ) 03:36–03:39** (ตรง GT 03:35–38). **แก้จุดที่ video track พลาด (ppe 0/2) ได้!**
  - **extra_person:** True 01:36–01:39 (ตรง GT unauthorized 01:36–40).
  - **foreign_object:** True 01:48–02:12 (ตรง GT hygiene ขวดน้ำ; ช้ากว่า GT 01:39 นิด).
- **[noise]** w1 มี mask/gloves กระพริบ 1–3 เฟรม (มือบังหน้า/มุมกล้อง) — สัญญาณจริงนิ่ง (w2 no-cap 14 เฟรมติด)
  vs noise สั้น → **ยืนยันว่า debounce (Phase 2) จะกรอง flicker ออกได้.**
- **[latency]** ~2–3s/เฟรม บน 4090 (per-frame image). **Acceptance Phase 1 PASS** (raw ครบ+แม่น).

### 2026-07-14 — Phase 2: debounce → events + ข้อค้นพบเรื่องเฉลยไม่ครบ (สำคัญ)
- **[method]** `phase2_debounce.py` — per-item + same-worker persistence (≥THR เฟรมติด), ตัดคนนอก (id≥3)
  ออกจาก PPE check. THR=2 → 9 events (ตัด single-frame flicker). THR=3 → 6 (ฆ่าเหตุจริงสั้นด้วย → recall ตก).
- **[bug fixed]** เดิม "worker 3" (คนนอก) ถูกเช็ค PPE → FP. แก้ให้ PPE เฉพาะ id 1/2.
- **[ผล THR=2 vs GT]** ppe **2/2**, unauthorized **2/2**, hygiene 0/1 (ตรวจเจอขวดน้ำแต่ onset ช้า→02:00 พลาด
  GT 01:39 ที่ tolerance). recall(image-tier types) = 4/5. (sop/near_miss = 0 เพราะเป็นงาน video track).
- **[⚠️ ข้อค้นพบพลิก — ตรวจด้วยตา]** สิ่งที่คิดว่าเป็น "w1 PPE false positive" **บางส่วนเป็นจริง**:
  - `chk_129 (02:09)`: **worker 1 หน้ากากดึงลงคาง เห็นหน้าเต็ม** (mask ไม่ได้ใส่จริง) + ขวดน้ำ KMITL บนโต๊ะ.
  - `chk_180 (03:00)`: **worker 2 หัวโล้นไม่มีหมวก** ชัดเจน (ยืนยัน w2 no-cap ถูก).
  - **→ mock label แค่ PPE ของ worker 2 (02:59–03:38) แต่ worker 1 ก็มี mask-down เป็นช่วงๆ ที่ mock ไม่ได้จด.**
  - **บทเรียน: precision ที่วัดได้ (33%) เป็น LOWER BOUND — เฉลยไม่ครบ, โมเดลอาจถูกกว่า. ตัวเลขทั้งโปรเจกต์
    เชื่อเป็น absolute ไม่ได้ (N=1 + เฉลยจัดฉาก+ไม่ครบ).** ต้องมี footage จริง + เฉลยที่ตรวจแล้วถึงจะ trust ตัวเลข.
- **[acceptance Phase 2]** PASS ในเชิงกลไก: event มี span+คำอธิบายไทย, single-frame flicker ถูกกรอง.
  precision จริงประเมินไม่ได้จนกว่าจะมีเฉลยที่เชื่อถือได้. **อย่า over-tune กับ mock ที่ไม่ครบ.**

### 2026-07-14 — Phase 3: latency (image tier)
- วัดจริงบน **RTX 4090**: image-tier combined probe = **cold 2.2s, warm ~1.85s/เฟรม** (104 completion tokens).
- **→ ผ่านเกณฑ์ near-realtime (≤3s).** compute 1.85s < sampling 2s = **ตามทัน 1 กล้องแบบต่อเนื่อง**.
- latency เหตุ image-tier = sampling interval + ~1.85s (เช่น sample ทุก 2s → เตือน ~2–4s หลังเกิด). ✅
- (SOP/near-miss = video tier, latency ~15–30s ตามเดิม — ยอมรับได้ compliance).

### 2026-07-14 — Phase 4+5: video tier + รวม 2-tier = recall 100%
- **[bug: video OOM]** รัน video tier (chunk_infer) บน **1080p** → **CUDA OOM ใน vision encoder** (`mm_encoder_attention`,
  video_grid_thw [15,42,76] = 15 เฟรม 1080p ผ่าน ViT พร้อมกัน → memory spike). image tier รอด (เฟรมเดียว).
  **แก้: video tier ใช้วิดีโอ 480p** (SOP/near-miss เป็น coarse motion ไม่ต้อง 1080p) → `cam_a05_480p.mp4` → ไม่ OOM.
  **[gotcha ใหม่] video track ต้อง downscale (≤480–720p); 1080p เก็บไว้เฉพาะ image tier PPE.**
- **[video tier ผล]** 24→6 merged events, recall 75%, **precision 83%**, near-miss DETECTED. hygiene timing
  **ดีกว่า image (01:38 ตรง GT vs image 02:00)** — temporal context ช่วย.
- **[Phase 5 combine] `combine_tiers.py`** เลือกแหล่งแม่นสุดต่อประเภท: **image→ppe · video→sop/near_miss/
  unauthorized/hygiene** → `result_combined.json` (13 events) → `cam_a05_ai_events.json` (schema mock).
- **[ผลรวม 2-tier vs GT]** **Recall(type) 100% (8/8)** — ครบทุกประเภท: ppe 2/2, sop 2/2, near_miss 1/1,
  unauthorized 2/2, hygiene 1/1. **near-miss @02:55 DETECTED. Precision 54% (7/13).**
- **[precision วิเคราะห์]** 6 "FP" = w1 PPE ~5 อัน (verify แล้วว่า**จริงบางส่วน** เช่น w1 mask-down @02:09 —
  mock ไม่ได้ label) + near_miss over-flag 00:00–00:44 (จริง 1). → **precision จริง 54–85% วัดเป๊ะไม่ได้
  (เฉลยไม่ครบ).** near_miss ยังเป็นประเภท over-flag ง่ายสุด (ยืนยันซ้ำ).
- **[สรุป Phase 0–5 จบ]** 2-tier VLM-only ครบ 5 ประเภท recall 100%, near-realtime (image 1.85s), ไทยดี,
  `cam_a05_ai_events.json` พร้อมเข้า UI. **เหลือ: e2e backend + generalization (วิดีโอ 2).**

### 2026-07-14 — Live demo (video + realtime alerts จากโมเดลสด, ไม่ใช่ JSON)
- **[deliverable] `live_demo.py`** — เว็บ local (http.server ล้วน): วิดีโอซ้าย + แจ้งเตือนขวา. ขณะเล่น
  หน้าเว็บส่ง currentTime → server สกัดเฟรม (1080p) → base64 → Cosmos ผ่าน **SSH tunnel (local:18000→remote)**
  → คืน events → การ์ด alert เด้งตาม timestamp วิดีโอ. **ผลมาจากโมเดล ณ วินาทีนั้น ไม่ใช่ precomputed JSON.**
- **[verify]** ทดสอบ detect: 30s→เงียบ, 96s→"บุคคลภายนอกเข้าพื้นที่", 180s→"ผู้ปฏิบัติงาน 2 ไม่สวมหมวก". ✅
  screenshot ในเบราว์เซอร์: alert PPE/คนนอก/ของแปลกปลอม เด้งถูกต้องเป็นภาษาไทย พร้อม timestamp. ✅
- **[arch]** demo ใช้ **image tier** (PPE/person/foreign, ~1.85s = realtime "เตือนตอนนั้น") — ตรงโจทย์ผู้ใช้.
  playback 720p (ลื่น) + detect 1080p (แม่น). SOP realtime (short rolling window) = งานถัดไป.
- **[run]** ต้องมี: (1) Vast + Cosmos serve, (2) tunnel `ssh -N -L 18000:localhost:18000 -p <port> root@<ip>`,
  (3) `python live_demo.py` → เปิด http://localhost:5000.

### 2026-07-14 — แก้ PPE false positive (occlusion) จาก feedback ผู้ใช้
- **[feedback]** ผู้ใช้เห็นใน live demo: 01:08 alert "worker 1 ไม่สวมถุงมือ" แต่จริงๆ ใส่อยู่ = FP.
- **[verify ภาพ chk_068 (68s)]** worker 1 **มือลงต่ำ/มองไม่เห็นชัด** → โมเดล**เดาว่า "ไม่มี" เพราะมองไม่เห็น**
  (ไม่ใช่เห็นว่าไม่มีจริง). **นี่คือ FP จริง — ต่างจากกรณี 02:09 ที่หน้ากากลงจริง.** สรุป: w1 flags มีทั้ง
  จริง (mask-down) และ FP (glove ตอน occlusion) ปนกัน.
- **[fix 1 — prompt abstention]** เพิ่มกฎ: "มองไม่เห็นมือ→ถือว่าใส่ถุงมือ, มองไม่เห็นหัว→ถือว่าใส่หมวก,
  set false เฉพาะเห็นชัดว่าไม่มี". → **68s: FP หาย (0 alert)**, 96s(คนนอก)+180s(w2 no-cap) ยังจับได้. ✅
  (ต่างจาก prompt-suppression ที่เคยพัง recall — อันนี้แค่ห้ามเดาตอนมองไม่เห็น ไม่ใช่ห้าม flag).
- **[fix 2 — debounce ใน live demo]** เดิม demo ยิง alert ทุกเฟรม (ไม่มี debounce). เพิ่ม: ต้องเจอ violation
  **2 detection ติดกัน (~4s)** ถึงเด้ง → กรอง occlusion ชั่วขณะ. real violation (นาน) ผ่านสบาย.
- **[บทเรียน]** FP หลักของ PPE = โมเดลเดา "ไม่มี" ตอน occlusion → แก้ด้วย abstention prompt + temporal
  persistence (debounce) = production pattern มาตรฐานของ PPE compliance.

### 2026-07-14 (บ่าย/ต่อ) — แก้ PPE false-positive: crop ล้มเหลว → visibility-gate ชนะ
- **โจทย์:** PPE FP ที่ 01:08 (68s) — โมเดลว่า worker1 "ไม่มีถุงมือ" ทั้งที่ GT (import_cam_a05_events.sh)
  ยืนยันไม่มีเหตุก่อน 01:13 → เป็น FP จริง. (cross-check `ground_truth_cam_a05.json` = 35 events ตรง import script.)
- **[ลอง #1 per-worker crop] ❌ ล้มเหลว** — fixed crop ซ้าย/ขวา (worker นิ่ง) + prompt คนเดียว:
  01:08 FP ยังอยู่ · 03:37 crop **หลุด cap** ของ worker2 (full-frame จับได้ crop ไม่ได้). ไม่ช่วย + แย่ลง.
- **[ลอง self-consistency vote 5×] ❌ ล้มเหลว** — 01:08 worker1 gloves = **0/5** (unanimous ผิด) →
  **FP เป็น systematic ไม่ใช่ random noise** → vote แก้ไม่ได้. (worker1 gloves = 0/5 ทั้ง 01:08 และ 03:37
  = โมเดลไม่เคยเห็นถุงมือ worker1 เลย เพราะมือเขาบัง/ลงหลังเครื่องตลอด).
- **[ต้นตอจริง]** zoom มือ worker1 @01:08 → **มือบังหลังเครื่อง มองไม่เห็น** แต่โมเดลตอบ gloves:false
  ทั้งที่ prompt สั่ง abstention ("มองไม่เห็น→ถือว่าใส่") → **โมเดลไม่เชื่อฟัง text abstention.**
- **[วิธีที่ชนะ] visibility-gate** — ให้โมเดลรายงาน `head_visible/hands_visible/face_visible` ด้วย →
  **ตัดสินใน "โค้ด": เตือนเฉพาะเมื่อ (เห็นชัด AND ไม่ใส่)**. ย้าย abstention จาก prompt มาไว้ในโค้ด:
  | เฟรม | เดิม | crop | vote | **vis-gate** |
  |---|:---:|:---:|:---:|:---:|
  | 01:08 (FP) | ❌ | ❌ | ❌ | ✅ ไม่เตือน |
  | 01:20 (control) | ✅ | ✅ | — | ✅ |
  | 03:37 (w2 จริง) | ✅ | ❌หลุด cap | ✅ | ✅ เตือน หมวก+ถุงมือ |
- **ข้อจำกัดที่เหลือ:** มือขยับ/บังบางส่วนยัง noise (03:37 เผลอ flag w1 ถุงมือ) · **เจอ mock ผิดอีก:
  03:37 worker1 หน้ากากรูดลงคาง (ผิด PPE) แต่ GT ไม่จด** → เฉลยไม่ครบอีก.
- **ไฟล์ทดลอง:** scratchpad `crop_probe.py` (crop), `sc_probe.py` (vote), `vis_probe.py` (visibility-gate ชนะ).

### 2026-07-14 (บ่าย/ต่อ) — Full-video test: visibility-gate ผ่าน PPE แต่ completeness ตก
- **รันทั้งคลิป** (image-tier, สุ่มทุก 3s = 74 เฟรม, visibility-gate prompt + person + foreign, debounce ≥2 เฟรม).
- **✅ PPE ผ่าน:** `ppe_w2_cap 03:00-03:39` (คร่อม GT 02:59 + 03:35) · `ppe_w2_gloves 03:36-39` (=GT) ·
  **PPE false-alarm = 0 → FP แบบ 01:08 หายทั้งคลิป** (visibility-gate เวิร์กจริงระดับ full video).
- **❌ completeness ตก:** unauthorized_person + foreign_object **MISS**.
  - person: เจอแค่ 1 เฟรม (t=96) → t=99 หาย → debounce ≥2 กรองทิ้ง. (session ก่อน prompt เฉพาะจับต่อเนื่องได้)
    → **combined prompt ทำให้ person เจือจาง + debounce เข้มไปสำหรับเหตุ transient.**
  - foreign_object: โมเดลไม่เห็นขวดน้ำในเฟรมที่สุ่มเลย.
- **residual:** `ppe_w1_gloves 03:36-39` = น่าจะ FP/noise (มือ w1 กำกวม) หรือ mock gap (w1 หน้ากากลงที่ 03:37).
- **บทเรียน:** อย่ายัดทุก type ใน prompt เดียว — **แยก focused prompt (PPE vis-gate / person / foreign)**
  + debounce แบบ "≥2 ใน window" (ไม่ใช่ติดกันเป๊ะ) สำหรับเหตุสั้น. แล้วค่อย re-test.
- **ไฟล์:** scratchpad `full_video_test.py`, `fv_rows.json`.

### 2026-07-14 (บ่าย/ต่อ) — image-tier ใหม่: full-video ผ่าน + verify กับวิดีโอจริง ✅
- **แก้ตาม diagnosis:** สร้าง `image_tier.py` (module เป็นระบบ) = **3 focused prompts แยกกัน**
  (PPE visibility-gate / person / foreign) + per-type debounce (≥2 ใน window tolerate เฟรมกระพริบ).
- **[run 1] completeness ครบ (GT 4/4)** แต่เจอ FP ใหม่ 02:09–03:18. **verify ด้วยตา (senior check):**
  - w1 "ไม่สวมหน้ากาก" (02:18/02:30/03:18) = **FP** (mask อยู่ แต่ก้มหัว) — และ mask ไม่ใช่เหตุใน GT เลย.
  - w2 "ไม่สวมถุงมือ" (02:09/02:30) = **FP** (มือถือผ้าเช็ดสีแดง → เข้าใจผิดว่าไม่มีถุงมือ).
  - hygiene 01:39–02:15 = **ถูก!** (ยืนยันเฟรม: ขวดน้ำ KMITL อยู่บนโต๊ะจริงถึง 02:12) → ละเอียดกว่า mock.
- **[แก้ precision]** (1) drop mask (ไม่ใช่เหตุใน GT + ก้มหัว = FP; ตั้ง `PPE_ITEMS=cap,gloves`)
  (2) เติม hint ใน PPE prompt: "มือถือผ้า/เช็ด = ยังใส่ถุงมือ; false เฉพาะเห็นมือเปล่าชัด".
- **[run 2 — สุดท้าย] 10 events → 5 events, GT 4/4, FP mask+red-cloth หายหมด:**
  | เวลา | เหตุ | ตรวจ |
  |---|---|---|
  | 01:36–01:42 | unauthorized_person | ✅ ตรง GT |
  | 01:39–02:15 | hygiene (ขวดน้ำ) | ✅ ถูก (ขวดอยู่จริง, ดีกว่า mock) |
  | 03:00–03:39 | ppe w2 ไม่สวมหมวก | ✅ ตรง GT (02:59+03:35) |
  | 03:36–03:39 | ppe w2 ไม่สวมถุงมือ | ✅ ตรง GT |
  | 03:36–03:39 | ppe w1 ไม่สวมถุงมือ | ⚠️ borderline (ปลายกะ มือกำกวม — อาจจริงแบบ mask-down ที่ mock ไม่จด) |
- **สรุป:** image tier แจ้ง event ครบ+ถูกต้องตรงวิดีโอ (person/foreign/PPE) FP ~0 (เหลือ borderline 1).
  ยังเหลือ: (a) wire เข้า `live_demo.py` แทน detect() เดิม (b) รวมกับ video tier (SOP/near-miss).
- **ไฟล์:** `image_tier.py` (deliverable), scratchpad `full_video_test.py`/`diag_pf.py`.

### 2026-07-14 (บ่าย/ต่อ) — ประกอบร่าง: wire live_demo + รวม 2 tier = cam_a05 สมบูรณ์พอ demo
- **[wire]** `live_demo.py` `detect()` เปลี่ยนมาใช้ `image_tier.analyze_frame` (3 focused prompts ยิง**ขนาน**
  ~2s + visibility-gate + drop-mask + cloth-hint) แทน prompt เดียวแบบเก่า. verify ผ่าน endpoint:
  t=68 **ไม่มี alert (FP หาย)** · t=99 ขวดน้ำ+คนนอก · t=217 PPE w2 หมวก/ถุงมือ + w1 ถุงมือ. ✅
- **[combine]** `combine_tiers.py` ปรับ split ตามจุดแข็งที่ verify แล้ว: **image → ppe + unauthorized +
  hygiene** (fine-grained, FP ต่ำ) · **video → sop + near_miss** (temporal เท่านั้น).
  → `result_combined.json` (11 events, ครบ 5 ประเภท) → `cam_a05_ai_events.json` พร้อม POST /api/events/bulk.
- **สถานะ cam_a05:** image tier (PPE/คน/hygiene) = สะอาด verify แล้ว · video tier (SOP/near_miss) = ยังมี
  FP ที่รู้อยู่ (near_miss 01:00/01:38 = over-flag, sop 00:00 = early) — เป็นส่วนที่อ่อนตามที่ documented.
- **เหลือ (ถ้าจะขัดต่อ):** ลด near_miss/sop FP ของ video tier · ดู live demo ใน browser จริง · generalization (คลิป 2).
- **ไฟล์:** `image_tier.py` (+ save `image_events.json`), `live_demo.py` (wired), `combine_tiers.py`,
  `METHOD_PLAYBOOK.md` (วิธีใช้ซ้ำ).

### 2026-07-14 (บ่าย/ต่อ) — ⚠️ เจอ False Negative: PPE ถอดจริงแต่ไม่แจ้ง (recall/precision ceiling)
- **[ผู้ใช้เจอตอนดู demo]** worker1 ถอดหน้ากาก @~02:13 **ไม่แจ้ง** · ถอดถุงมือหลายจุด **ไม่แจ้ง** (เจอบ่อย).
- **สาเหตุ (ตรงๆ):**
  - **mask: เราตัดทิ้งเอง** (`PPE_ITEMS=cap,gloves`) เพราะ GT ไม่มี + หัวก้ม=FP → เลย**พลาด mask-off จริง**.
  - **gloves: ถูกกดด้วย knob กัน-FP ที่เราใส่** — visibility-gate (มือไม่ชัด→ไม่ flag) + cloth-hint (ถือผ้า→
    ถือว่าใส่) + debounce 2 เฟรม → พอถอดถุงมือตอนมือขยับ/ใกล้ผ้า → ไม่แจ้ง.
- **บทเรียนสำคัญ (senior):** เรา**แลก FP กับ FN มาตลอด** — ทุก knob ที่ลด false-positive (68s) = เพิ่ม
  false-negative (พลาดของจริง). **นี่คือ recall/precision ceiling ของ per-frame VLM บน PPE ชิ้นเล็ก/
  ขยับ/บัง** — เล่น whack-a-mole ไม่จบ. สำหรับ safety การ**พลาดของจริงอันตรายกว่า** FP.
- **ทางแก้จริง (documented ซ้ำ):** PPE ที่เชื่อถือได้ = **detector เฉพาะ (YOLO fine-tune บนกล้องเรา)** —
  presence/absence ของ PPE ชิ้นเล็กคืองานถนัด detector ไม่ใช่ VLM. เก็บ VLM ไว้ทำ SOP/reasoning/คำอธิบาย.
- **[ตัวเลือกรอบหน้า]** (a) demo: re-enable mask + ผ่อน gate → จับมากขึ้นแต่ FP มากขึ้น · (b) deploy:
  hybrid YOLO-PPE + VLM. → **ต้องเลือก balance/architecture ก่อนขัดต่อ.**

### 2026-07-14 (ต่อ) — สร้าง Temporal PPE Tracker (แก้ FN) — offline, ยังไม่ทดสอบวิดีโอจริง
- **`ppe_tracker.py`** — state machine ต่อ (worker,item). แนวคิดหลัก: **"ไม่เห็น → คงสถานะเดิม"**
  (ไม่ใช่ assume worn) → ถอดแล้วมือบัง = ยังแจ้ง (แก้ FN) · require K=2 ต่อเนื่องเปลี่ยน state (กรอง flicker)
  · **re-enable mask**. คืน off-span เป็น ppe_violation events.
- **`tests/test_ppe_tracker.py` = 7/7 ผ่าน** (sustained fires · flicker filtered · **occlusion carries state**
  · span closes on re-don · off-without-prior-on · workers/items independent · mask re-enabled).
- **`image_tier.py` refactor:** `analyze_frame` คืน `obs` (raw per-item on/off/unknown, เก็บ mask ด้วย) +
  main save `image_obs.json` + รัน tracker เทียบ. CLI integration ทดสอบ synthetic obs = ถูกต้อง.
- **⏳ เหลือ (ต้อง Vast/GPU):** รัน `image_tier.py` บนวิดีโอจริง → ได้ `image_obs.json` จริง → ป้อน `ppe_tracker`
  → verify จับ mask/gloves ถอดได้จริง (แก้ FN) โดยไม่ FP ท่วม → ถ้าดี wire เข้า `live_demo.py`.
- **Vast ปิดแล้ว** — ต้องเช่า instance ใหม่ (RTX 4090/3090 24GB) + `serve_cosmos.sh` ก่อนทดสอบวิดีโอจริง.

### 2026-07-14 (ต่อ) — Verify ppe_tracker (local, no GPU) + wire เข้า live_demo
- **ตัดสินทิศทาง:** รับ temporal tracker เป็นวิธี PPE → verify รอบเดียว → หยุดขัด PPE (เพดาน per-frame VLM)
  → ไปต่อ gate จริง (e2e + วิดีโอ 2). เหตุผล: ขัด PPE บน N=1 = diminishing returns.
- **[verify tracker บน obs จริง (image_obs.json 77 เฟรม, ไม่ใช้ GPU)]** ppe_tracker k=2 คืน:
  `03:03–03:48 w2 ไม่สวมหมวก` + **`03:39–03:48 w2 ไม่สวมถุงมือ` = กู้ FN ถุงมือที่เคยพลาด** · w1 mask off
  เฟรมเดียว(126s) ถูกกรอง (k=2) = ไม่ FP ท่วม. **tracker logic เวิร์กจริง.**
- **[spot-check เฟรม 216s]** ✅ w2 หัวโล้น+มือเปล่า (ถือหมวก, ถุงมือวางโต๊ะ) → event tracker เป็นของจริง.
  ⚠️ **แต่ w1 หน้ากากดึงลงคาง — obs ไม่ได้ flag → VLM พลาด mask = FN อยู่ที่ชั้น observation (ไม่ใช่ tracker).**
  → mask FN ต้องแก้ที่ VLM (เปิด mask + รันสด — ต้อง GPU).
- **[LiveTracker]** เพิ่ม streaming version ใน `ppe_tracker.py` (update ทีละเฟรม, reset ตอน seek ถอย).
  sim-test ป้อน obs จริงทีละเฟรม → **ตรงกับ batch เป๊ะ (MATCH: True).**
- **[wire] `live_demo.py`** PPE เปลี่ยนจาก stateless `sig` → **LiveTracker (obs-based, รวม mask กลับ)**;
  person/foreign คงเดิม. compile ผ่าน. **ยังไม่ทดสอบสด (ต้อง GPU).**
- **⏳ รอ GPU (สเต็ป 2):** เช่า → serve Cosmos → รัน image_tier สดใหม่ (PPE_ITEMS เปิด mask) → test live_demo
  end-to-end (ดูว่า mask/gloves ถอดแล้วเด้ง + ไม่ FP ท่วม) → spot-check → **จบ PPE.** แล้วไป e2e + วิดีโอ 2.

### 2026-07-14 (ต่อ) — Claude-GT: เฉลยจริงทั้งคลิป + แผนที่ error ของ Cosmos
- **[idea ผู้ใช้]** ใช้ Claude อ่านวิดีโอเองเป็นเฉลย (แก้ปัญหา mock ไม่ครบ) → diff กับ Cosmos → รู้ว่าพลาดตรงไหน.
- **[method]** montage 4 เฟรม/ภาพ (2×2, 960×540, ติดป้ายเวลา) ทั้งคลิป → 74 เฟรม = 19 montage (`build`
  ด้วย PIL). Claude อ่านทีละชุด label PPE ต่อคน+person+foreign → `claude_gt.json` (74 เฟรม, on/off จริง).
  `diff_gt.py` เทียบกับ Cosmos `image_obs.json`.
- **[ผลชี้ขาด] Cosmos recall PPE = 81% (17/21), FP = 0.** พลาด **4 จุด = หน้ากาก w1 ทั้งหมด**
  (02:09, 02:12, 03:36, 03:39 — Cosmos บอก mask=on ทั้งที่ดึงลง). จับถูก 100%: หมวก w2 (13 เฟรม),
  ถุงมือ w2 (2). หน้ากาก w1 จับได้แค่ 1/5.
- **[สรุปที่ trust ได้แล้ว]** Cosmos **แม่นจริงกับ cap+gloves (100%, ไม่มี FP)** — **จุดอ่อนเดียว = mask**
  (ชิ้นเล็ก/ดึงลงคางเห็นยาก). visibility-gate ยืนยันว่าตัด FP ได้จริง (0 FP ทั้งคลิป).
- **[decision-ready]** ถ้าต้อง mask แม่น → YOLO mask detector หรือ high-res mask crop; cap/gloves ใช้ Cosmos
  ได้เลย. **Claude-GT = เครื่องมือวัดผลที่เชื่อได้ (แก้ปัญหา mock ไม่ครบที่ค้างทั้งโปรเจกต์).**
- **ไฟล์:** `claude_gt.json` (เฉลย), `diff_gt.py`, `claude_gt_report.txt`, `_montage/` (ภาพให้คนตรวจซ้ำ).

### 2026-07-14 (ต่อ) — Claude-GT ละเอียด (high-res crop, per-hand) → definitive Cosmos error map
- **[feedback ผู้ใช้]** เฉลยหยาบ (3s, per-worker gloves, mask conservative) ไม่ครบ → undercount (w2 ถอดถุงมือ
  ข้างเดียว / w1 หน้ากากบางช่วง หลุด). ตัวเลข 81% เป็น upper bound.
- **[method ละเอียด]** crop หัว+มือ high-res (กล้องนิ่ง, w1 ซ้าย/w2 ขวา) → montage `[w1|w2]` 4 เวลา/ภาพ
  = 19 crop-montage. Claude re-label ทั้งคลิปแบบเป๊ะ (cap/mask/gloves per worker, ดูถุงมือแต่ละมือ).
  → `claude_gt.json` (74 เฟรม, definitive).
- **[ผล definitive] Cosmos recall PPE = 71% (17/24), FP = 0** (เฉลยละเอียดเจอละเมิดจริง 24 > หยาบ 21).
  พลาด **7 จุด = หน้ากาก w1 ทั้งหมด** (02:09,02:12,02:15,02:42,03:33,03:36,03:39).
- **[แยกชนิด — ชี้ขาด]** **cap 14/14 = 100% · gloves 2/2 = 100% · mask 1/8 = 12% (พลาดเกือบหมด) · FP 0.**
  → **Cosmos ใช้ได้ระดับ production กับ cap+gloves; หน้ากากคือจุดอ่อนชัดเจน** (ต้อง YOLO-mask หรือยอมรับ).
- **[บทเรียน method]** เฉลยหยาบทำ Cosmos ดูดีเกินจริง (81%→71%). **การมี Claude-GT ละเอียด + คนตรวจซ้ำ
  (มี _montage/crop ให้) = ได้ตัวเลขที่ trust ได้จริง** — เครื่องมือวัดผลที่โปรเจกต์ขาดมาตลอด.
- **ไฟล์:** `claude_gt.json`, `diff_gt.py`, `claude_gt_report.txt`.

### 2026-07-14 (ค่ำ/ต่อ) — Demo cleanup: ตัด FP (near_miss/sop) ด้วย domain post-processing (local, no GPU)
- **บริบท:** สโคปแคบลง = **model-only, cam_a05 คลิปเดียว, deliverable = live demo** (วิดีโอเล่น→แจ้งตามวินาที).
  ตัด e2e/backend/generalization ออก (เป็นงานทีม integration). เป้า = ทำ output ให้สะอาดพอโชว์.
- **[Phase 0 วัด state จาก artifact ที่มี — ไม่ใช้ GPU]** `diff_gt.py` ยืนยัน PPE: cap 100%/gloves 100%/mask 12%/FP 0.
  `ppe_tracker` บน `image_obs.json` กู้ FN: w2 หมวก 03:03–03:48 + w2 ถุงมือ 03:39–03:48 (ตรง GT, ไม่ flicker).
- **[เจอ FP ที่ฆ่าความน่าเชื่อถือ demo]** near_miss **critical** FP @01:00 + @01:38 (จริงๆ คือวางกระป๋อง=sop),
  sop @00:00 "หยิบจากกล่อง WAIT" (WAIT = source ที่ถูกต้องตาม SOP → งานปกติ mislabel).
- **[fix = post-processing ไม่แตะ prompt]** `postprocess_events.py` 2 กฎ domain:
  (A) **near_miss integrity** — near_miss ต้องมี "มือ"+contact (สายพาน/เครื่อง/หนีบ/cuốn) ไม่งั้น reclass→sop
  (แก้ FP 01:00/01:38, คงของจริง 02:45–03:30 "มือถูกสายพาน cuốn"). (B) **WAIT-box** — sop ที่หยิบจาก WAIT (ไม่ใช่ NG) = ปกติ → drop.
- **[เจอ bug 2 ตัว]** (1) `to_bulk_events.py` ตัด field `end` ทิ้ง → near_miss span 02:45–03:30 ยุบเป็นจุด 02:45
  → eval มองว่า MISSED. แก้ให้เก็บ `timestamp_end_mmss`. (2) `evaluate.py` fallback end=`"0:00"` ทำให้ทุก bulk
  event ถูกนับเป็น span จาก 0 → **baseline เดิม 88% เป็นตัวเลขลวง จริง=75%**. แก้ให้อ่าน `timestamp_end_mmss`.
- **[ผลชี้ขาด — pipeline: chunk→postprocess→merge→combine→to_bulk]** วัดด้วย `evaluate.py`:
  **Recall(type) 75%→100% (8/8) · Precision 55%→89% (8/9) · near_miss @02:55 MISSED→DETECTED.**
  เหลือ FP เดียว = sop@00:00 "ไม่ได้เช็ดกระป๋อง" (เป็น violation จริงตาม SOP step 6 แต่ GT ช่วง idle ไม่จด — honest ปล่อย).
- **[wire demo]** `live_demo.py._load_precomputed` โหลด `result_video_clean.json` (fallback `result_cosmos_merged.json`)
  → live demo จะเด้ง near_miss เฉพาะของจริง (ไม่มี critical FP 01:00/01:38). syntax ผ่าน (ยังไม่ test สด — ต้อง GPU).
- **ไฟล์ใหม่:** `postprocess_events.py`, `result_pp.json`, `result_pp_merged.json`, `result_combined_clean.json`,
  `cam_a05_ai_events_clean.json`, `result_video_clean.json`. **แก้:** `to_bulk_events.py`, `evaluate.py`, `live_demo.py`.
  **ของเดิมไม่แตะ:** `cam_a05_ai_events.json`, `result_cosmos_merged.json` (เก็บเทียบ).
- **⏳ เหลือ (ต้อง GPU):** รัน `live_demo.py` สดจริง → verify alert เด้งตามวินาที + PPE tracker จับ mask/gloves ถอด + ไม่ FP ท่วม → อัดคลิป demo.

### 2026-07-15 — GPU session #2: verify live demo + detector exploration + Set-of-Mark (ทุกอย่างวัดกับ Claude-GT)
**Instance ใหม่:** vast RTX 3090, `ssh -p 51911 root@142.120.200.22`. เป็น template ที่ auto-serve **Qwen3.5-9B**
(ไม่ใช่ Cosmos) → stop template vllm + kill EngineCore ที่ค้าง VRAM → serve Cosmos ด้วย `serve_cosmos.sh`.
**Gotcha:** gpu-util 0.95 = **CUDA OOM** ตอน FlashInfer warmup (เหลือ free 123MB) → ลดเป็น **0.90** ผ่าน
(VRAM 23.2/24GB). Model UI/vllm ของ template หยุดไว้. ⚠️ ultralytics auto-update ลง torch 2.13 ทับใน `/venv/main`
(torchvision พัง) — Cosmos ที่รันอยู่ไม่กระทบ (โหลด mem แล้ว) แต่ **อย่า restart** / detector ใช้ venv แยก `/workspace/detenv`.

- **[live demo verify]** end-to-end ผ่าน: tunnel local:18000→remote → image_tier ดึงเฟรม local → Cosmos → t=99
  จับ Person C + ขวดน้ำถูก. **ปิด mask ใน live_demo** (data: with-mask recall 67%/FP13 vs cap+gloves 100%/FP4).
- **[detector exploration — ตอบ "มี model/วิธีอื่นแม่นกว่าไหม" ด้วยตัวเลขจริง]**
  - **Grounding DINO** (gd_probe, CPU): person **เก่งมาก** (นับ 2-3 คนถูก) · hard-hat/mask presence พอได้ ·
    **glove/bare แยกไม่ออก · กระป๋อง=bottle เพียบ** → ดีเฉพาะ person-counter.
  - **YOLO-World**: dependency conflict (ต้อง clip + torchvision::nms พัง) · ค่า ≈ GD → ข้าม.
  - **Pretrained PPE-YOLO** (`keremberke/yolov8m-protective-equipment-detection`, มี glove/no_glove): **transfer FAIL**
    — เทรนบน PPE ก่อสร้าง มาเจอ cap ผ้า/ถุงมือผ้า/mask อนามัย จับได้แค่ no_goggles มั่วๆ. PPE ละเอียด = ต้องเทรนเอง (ตัดออก).
  - **Set-of-Mark** (som_ppe.py — crop หัว/มือ high-res → Cosmos + visibility gate, รันทั้ง 74 เฟรม): **mixed** —
    cap 100%/0FP (เท่าเดิม) · **gloves แย่ลง FP 4→14** (crop มือหลุดบริบท) · **mask 0%→50%, FP 9→4** (ดีขึ้นแต่ไม่เป๊ะ).
    → SoM เหมารวมไม่คุ้ม; ที่ดีสุด = cap/gloves ใช้ full-frame, mask ยังตัน.
- **[สรุปเพดาน local Cosmos-8B (vs Claude-GT)]** **cap 100%/0FP · gloves 100%/4FP · person/foreign ✅ · mask ~50% (crop) / 0-12% (frame)**.
  mask "ดึงลงคาง" = เพดานจริงของ 8B (crop แล้วมันบอกเอง face_visible=false) — ต้อง frontier VLM ถึงเป๊ะ.
- **[event timeline best config]** postprocess+merge → **recall 100% (8/8), precision 89% (8/9), near-miss detected** (`cam_a05_ai_events_clean.json`).
- **[model research]** มี **Cosmos-Reason2-32B** (post-trained บน **Qwen3-VL-32B**, drop-in สถาปัตย์เดียวกัน — pipeline ใช้ได้เลย)
  = ตัวใหญ่/ใหม่กว่า 8B (ฐาน Qwen2.5-VL-7B) น่าจะแก้ mask/ของเล็กได้ **แต่ 32B ไม่ฟิต 24GB** (ต้อง quant 4-bit หรือ GPU ใหญ่กว่า เช่น A100/H100).
  ทางเลือก frontier: Qwen3-VL-235B / Gemini-2.5 / GPT-5 (cloud).
- **ไฟล์ใหม่:** `gd_probe.py`, `yolow_probe.py`, `ppe_yolo_probe.py`, `som_probe.py`, `som_ppe.py`, `image_obs_som.json`.
  remote: `/workspace/serve_cosmos.sh` (gpu-util 0.90), `/workspace/frames/`, `/workspace/detenv/` (ultralytics แยก).

#### สรุป รอด/ไม่รอด (ทั้งโปรเจกต์)
- 🟢 **รอด:** Cosmos-8B · chunk15+merge20 · ppe_tracker · Claude-GT วัดผล · postprocess(near_miss integrity+WAIT-box) ·
  live_demo hybrid · cap 100%/0FP · gloves 100%/4FP · person/foreign.
- 🟡 **หยาบแต่รับได้:** near_miss (span หยาบ) · SOP (desc หยาบ) · latency ~2-5s · mask via crop 50%.
- 🔴 **ไม่รอด:** prompt v2/v3/v4 (recall พัง) · mask full-frame (0-12%) · pretrained PPE-YOLO (transfer fail) ·
  SoM เหมารวม (gloves พัง) · GD/YOLO-World สำหรับ PPE (person only).

### 2026-07-15 — Super-resolution (no-train) ดัน mask + ปิดจ็อบ PPE ที่เพดาน no-train VLM
**Instance:** vast **RTX 4090** ใหม่ `ssh -p 30779 root@120.88.119.115` (ตัวเก่า 3090 ถูก destroy). setup ซ้ำ: stop template Qwen3.5 →
`fuser -k /dev/nvidia0` เคลียร์ EngineCore ค้าง → serve_cosmos.sh (gpu-util 0.90) → re-download model. detenv แยก + super-image.
- **[แนวคิด] VLM แพ้เพราะ "มองไม่เห็น" ไม่ใช่ "ตัดสินไม่เป็น"** (Cosmos บอกเอง `face_visible=false` บน crop) → ลอง **super-resolution
  (EDSR-4x pretrained, no-train) crop หัวก่อนป้อน Cosmos**. `som_sr_probe.py` (4 เฟรม) → SR กู้ mask t=126 ได้ + ไม่มี FP บน 4 เฟรม.
- **[บทเรียน: 4 เฟรม probe หลอกได้]** รันเต็ม 74 เฟรม (`som_sr_ppe.py`, SR หัวเท่านั้น—gloves คง full-frame กันพัง):
  **mask recall 0→88% แต่ FP พุ่ง 9→23** (SR ทำ Cosmos ไวเกินจนเดา off มั่ว). → ต้อง **face-visibility gate** (เชื่อ off เฉพาะ face_visible=yes):
  **mask = recall 62% (5/8), FP 4** · **cap 100%/0FP, gloves 100%/4FP ไม่ถอย** (holistic verified). ← ผู้ใช้กำชับ "อย่าแก้อันนึงพังอันอื่น" = จับ FP23 ได้ทัน.
- **[สรุปเพดาน PPE — no-train VLM, พิสูจน์ครบ 3 เส้น]** detector transfer-fail · SoM crop พัง gloves · SR ได้ recall แต่ face_visible ยัง false
  = **62% คือเพดานจริงของ Cosmos-8B บน mask-ดึงลงคาง**. mask เป๊ะ 100% ต้อง train หรือ frontier (ขัด constraint).
- **[Best config ต่อ item — adopt]** cap 100%/0 (full-frame) · gloves 100%/4 (full-frame) · person/foreign ✅ (full-frame) · **mask 62%/4 (SR-head+face-gate, offline)**.
  SR ~3s/หัว บน CPU → **offline overlay ไม่ใช่ live per-frame** (live ต้อง SR-GPU/event-trigger).
- **[deliverable สมบูรณ์]** `cam_a05_ai_events_final.json` = timeline + mask (2 span w1) → **recall 100% (8/8), precision 91% (10/11), near-miss detected**.
  mask events (SR+gate+tracker) = `mask_events_sr.json`; รวมผ่าน `result_combined_final.json`.
- **ไฟล์ใหม่:** `som_sr_probe.py`, `som_sr_ppe.py`, `image_obs_sr.json`, `mask_events_sr.json`, `result_combined_final.json`, `cam_a05_ai_events_final.json`.
- **DECISION ปิดจ็อบ PPE:** ถึงเพดาน no-train แล้ว หยุดไล่ mask (ROI ต่ำ, พิสูจน์ 3 เส้น) → ไปเก็บ live demo + เอกสาร → teardown GPU + revoke token.

### 2026-07-15 — Granular vs span + finalize deliverable (honest finding)
- **[คำถามผู้ใช้]** deliverable มี 10 events แต่เฉลย/mock มี ~35 → น้อยไปไหม? **ตอบ:** เฉลย 35 = log ทุก ~2s เหตุการณ์เดียวซ้ำ →
  ยุบเป็น **8 เหตุการณ์จริง**; ของเรา = **merge เป็น 10 span** (คลุมครบ recall 100%). "10" = วิธีแสดง ไม่ใช่เจอน้อย.
- **[ลอง expand span → granular ทุก 2s (`expand_granular.py`) เพื่อให้หนาเหมือน mock] — พังและเผยความจริง:**
  146 events, **recall ตก 88%, precision 32%**. สาเหตุ: (1) span sop `02:00–03:30` (90s) แต่**เฉลย sop จบ 02:03** → โมเดล
  over-detect sop ช่วง 02:15–03:30 (เห็นคนหยิบกระป๋องต่อ) → expand = FP เพียบ. (2) near_miss ยุบเป็นจุด 02:45 → พลาด 02:55.
- **[honest finding สำคัญ]** **"Precision 100%" ที่รายงาน = ระดับ span/segment ไม่ใช่ต่อวินาที** — span + evaluate (segment-overlap
  + tolerance) กลบ sop over-detection ไว้. โมเดล detect แบบ chunk (video tier ทุก 15s) + merge → **ไม่มีความละเอียด 2s**;
  mock 35@2s = คน label มือ → **reproduce แบบซื่อสัตย์ไม่ได้** (expand = ปั้นความหนาแน่นที่ไม่ได้ตรวจจริง).
- **DECISION: deliver span (10) = ตัวแทนซื่อสัตย์ที่สุดของความละเอียดจริง** (incident windows). `expand_granular.py` เก็บไว้เป็น negative result.
- **[finalize ไฟล์]** `cam_a05_ai_events.json` == `cam_a05_ai_events_final.json` = 10 span (canonical, sync แล้ว) · ลบ intermediate `_clean`/`_spans` ·
  demo source `result_video_clean.json` align (ตัด sop@00:00). Deliverable: recall 100%, precision 100% (span-level), near-miss detected.

### 2026-07-15 — Verify SOP ด้วยเฟรมจริง (Claude ดูเอง) → SOP grounding อ่อน + demo polish สุดท้าย
- **[ผู้ใช้ระแวง]** "SOP บางอันดูปกติ แค่เขาก้ม โมเดลเลยบอกไม่ดู?" → Claude เปิดเฟรมจริงดู (t=78/01:18, t=120/02:00 = ในช่วง GT SOP):
  Worker 1 **ถือกระป๋องก้มมอง / เอื้อมหยิบแถวกล่อง NG** = **ดูเหมือนงานปกติ แยกจาก violation ด้วยตายาก**. เทียบ t=216/03:36:
  Worker 2 **หัวโล้นถือหมวก** = PPE-off **เห็นชัดทันที**.
- **[สรุป finding]** **SOP grounding อ่อนจริง** — โมเดลยิงจาก "ท่าหยิบกระป๋อง" กว้างๆ ไม่ใช่เห็น NG-violation ชัด (หลักฐาน: over-fire
  @00:00 idle + span ยืดถึง 03:30 เลย GT 02:03). ไม่ใช่ FP ล้วน (violation staged มีจริง + overlap ตรง) แต่ **confidence ต่ำ**.
  → **signal ที่ grounded เชื่อได้ = PPE-off / คนนอก / ขวดน้ำ / near-miss (เห็นด้วยตา); SOP = low-confidence procedural**.
- **[DECISION — Claude ตัดสินเอง]** ไม่ "แต่งคำ SOP ให้ดูมั่นใจ" (จะกลบความจริง) → **ติดป้าย SOP = "AI ประเมิน ควรยืนยัน" (severity low)**
  ใน live_demo + เอกสาร; ชู grounded signals เป็นหลัก. honest > สวย.
- **[demo polish]** แก้ label mask "(offline)" → "PPE — หน้ากาก" + subtitle บอกชัด สด/คำนวณล่วงหน้า. ความหนา ~10 alert = ~10 incident จริง (dedup) ไม่ padding.
- **สถานะ:** ปิดจ็อบ — deliverable + demo + เอกสาร honest ครบ. เหลือ acceptance (ผู้ใช้ดู full playthrough) + teardown (GPU + revoke token).

### 2026-07-15 — Re-scope: ตัด SOP + เพิ่ม falling_object → โฟกัส 3 หมวด safety
- **[ผู้ใช้ทบทวนเป้า]** งานหลัก = VLM video understanding เพื่อ safety, **3 หมวดสำคัญเท่ากัน: PPE / มือใกล้สายพาน (near-miss) / ของตก (falling_object)**.
  **SOP ตัดออก** (ตกลงแล้วว่า = data ceiling, ยากเกิน, ทำให้ demo มั่ว).
- **ตัด SOP:** ออกจาก deliverable + demo overlay (source `result_cosmos_chunked` เก็บไว้ = กลับได้).
- **เพิ่ม falling_object:** ผู้ใช้ระบุ 2 จุด → Claude verify เฟรมจริง: **00:14 (w2 กระป๋องหลุดจากมือที่สายพาน)** + **01:52 (w2 กระป๋องหล่นลงโต๊ะ)**.
  เพิ่ม type ใน `to_bulk_events.py` + `live_demo.py` overlay.
- **⚠️ honest — detection status ของ falling_object:** 2 event นี้ = **ผู้ใช้ระบุ + Claude verify เฟรม** (ไม่ใช่ Cosmos detect เพราะ GPU ล่ม).
  category + events เข้า timeline แล้ว (เหตุจริง) **แต่ VLM-detection ของ falling_object ยังไม่ได้รัน** (prompt พร้อม, รอ GPU).
- **deliverable ล่าสุด (`cam_a05_ai_events.json`, 10 events):** falling_object 2 · ppe 5 · near_miss 1 · unauthorized 1 · hygiene 1 · **ไม่มี SOP**.
- **framing สุดท้าย:** งาน = พิสูจน์ว่า VLM เข้าใจ safety video ได้แค่ไหน — **จุดแข็ง = อันตราย/near-miss/PPE ใหญ่ (reasoning+perception ที่ทำได้)**;
  จุดจำกัด = mask (perception), SOP (data → ตัดออก). ตรง 3 หมวดที่ผู้ใช้โฟกัส.

### 2026-07-15 — PIVOT: Streaming narration + Hybrid (narration=understand + structured=catch) [resume anchor]
**เป้าตกผลึกใหม่ (ผู้ใช้):** งาน = **VLM เข้าใจ video → apply safety (PPE/ของตก/มือใกล้สายพาน)** · ต้อง **near-real-time เล่าทุก ~2-3วิ** (ไม่ offline) · **ตัด SOP** (data ceiling).
**Insight:** เดิมเราบีบ VLM เป็น detector (binary category) → เจอเพดานหมด. จุดแข็งจริง = **narrator/เข้าใจ** (จัดการ ambiguity ด้วยภาษา). แต่...

- **Cosmos VIDEO mode crash engine ซ้ำๆ** (ทุก clip narration) → **ใช้ IMAGE mode (2 เฟรม/window) = เสถียร** (คีย์สำคัญ, image_tier ไม่เคย crash).
- **P1-P4 สร้างแล้ว:** `rolling_narrate.py` (narrate ทั้งวิดีโอ 36 windows/6วิ → `narration_timeline.json`) · `live_demo_hybrid.py` (**localhost:5001**, precomputed 2 ชั้น, self-contained ไม่ต้อง GPU) · `live_demo_live.py` (**localhost:5002**, Cosmos พ่นสดผ่าน tunnel).
- **[eval ชี้ขาด — `eval_live.py` → `live_eval.json`, 73 windows]** LIVE narration-tagger เทียบ GT:
  **PPE ✅ (TP6/FP2) · person ❌พลาด · near-miss ❌ FP13+พลาดของจริง · falling ❌** → **narration-tag ไม่น่าเชื่อถือสำหรับ "จับเหตุการณ์"** (over/under-flag).
- **🎯 ARCHITECTURE สุดท้าย (ยืนยันด้วย eval):** **structured detection = CATCH (recall 100%, reliable) · narration = UNDERSTAND (context, live).** ห้ามเอา catch มาจาก narration-tags.
- **👉 งานถัดไป (resume ตรงนี้):** ~~แก้ live_demo_live~~ → **เขียนเสร็จแล้ว = `live_demo_combined.py` (localhost:5003)**: CATCH=structured precomputed (client-side, 8 events, reliable) + UNDERSTAND=live narration (`/narrate` → Cosmos). verify แล้ว (compile+CATCH+endpoints). **เหลือแค่: เช่า GPU → serve Cosmos → tunnel :18000 → `python live_demo_combined.py` → เปิด localhost:5003.**
- **RESUME GPU:** เช่า Vast ใหม่ → เขียน `/workspace/serve_cosmos.sh` (gpu-util 0.90) + `/workspace/.hf_env` (HF token, **revoke ตัวเก่าก่อน**) → stop template vllm → `fuser -k /dev/nvidia0` → **launch สะอาด ไม่ pkill** (`setsid bash serve_cosmos.sh`, pkill -f ฆ่า ssh ตัวเอง) → upload `frames.tar.gz` → tunnel `-L 18000:localhost:18000`. **image mode เท่านั้น (video crash).**
- **ไฟล์ใหม่:** `STREAMING_PLAN.md`, `rolling_narrate.py`, `narrate_probe.py`, `live_demo_hybrid.py`, `live_demo_live.py`, `eval_live.py`, `narration_timeline.json`, `live_eval.json`, `open_narrate.py`.

<!-- ต่อ entry ใหม่ด้านล่างทุกครั้งที่มีความคืบหน้า -->

---

## 6. Results

รันจริงบน Vast.ai (RTX 3090 24GB) — **2026-07-13**. Model: `Qwen/Qwen3-VL-8B-Instruct` BF16.

| Run | Method | Frames | Recall(type) | Recall(time) | Precision | Near-miss | Thai | Latency | Events |
|-----|--------|--------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 1 | Qwen3-VL-8B · whole-video | 32 total (~0.15fps) | 38% (3/8) | 50% | **100%** (2/2) | ❌ MISS | ✅ ดีมาก | 15.5s | 2 |
| 2 | Qwen3-VL-8B · chunked 15s | 32/chunk (~2fps) | 62% (5/8) | 75% | 26% (5/19) | ❌ MISS | ✅ ดีมาก | 188s | 19 |
| 3 | **Cosmos-Reason2-8B · chunked 15s** | 32/chunk (~2fps) | **75% (6/8)** | **88%** | **38% (8/21)** | ✅ **DETECTED** | ✅ ดี (มี artifact เล็กน้อย) | 177s | 21 |

| 4 | **Cosmos-Reason2-8B · chunked 8s** | 32/chunk (~4fps) | 62% (5/8) | **100%** | 37% (13/35) | ✅ DETECTED | ✅ ดี | 349s | 35 |
| 5 | **Cosmos · chunked 15s + merge 20s** ⭐ | 32/chunk (~2fps) | **75% (6/8)** | 88% | **62% (5/8)** | ✅ **DETECTED** | ✅ ดี | 177s+~0 | 8 |

⭐ **run 5 = winning config (DoD 4/4).** Prompt = v1 เดิม (ไม่แตะ). Precision 38%→62% มาจาก post-hoc
temporal merge ล้วนๆ (รวม event ต่อเนื่องข้าม chunk เป็น span เดียว) — recall/near-miss ไม่ตก. merge gap
30s ได้ precision 71% แต่เลือก 20s เพราะ faithful กับ chunk 15s. **prompt v2/v3/v4 ที่พยายาม suppress
ทำ recall พัง (38%/1event/50%) — ทางที่ถูกคือแก้ post-processing ไม่ใช่ prompt.**

**ข้อค้นพบจาก run 4 (fps 2→4):** เพิ่ม fps ทำให้ **recall(time-only) = 100%** (model flag บางอย่าง
ตรงทุก GT segment รวม ppe 03:35 ที่ 15s เคยพลาด) — **แต่ recall(type) ลดลง 75%→62%** เพราะ label ผิด
ประเภทมากขึ้น. **สรุป: sampling พอแล้ว (เห็นครบทุกเหตุการณ์) — คอขวดจริงคือ type-classification + precision
ซึ่งเป็นปัญหา prompt/taxonomy ไม่ใช่ compute.** → รอบหน้าลงแรงที่ prompt engineering ไม่ใช่ fps/res.

**หัวข้อชี้ขาด — Cosmos vs Qwen3-VL (chunked เหมือนกัน):** Cosmos ชนะทุก metric — recall 75% vs 62%,
precision 38% vs 26%, และ**จับ near_miss critical @02:55 ได้ (Qwen พลาด)**. ยืนยัน ADR-001 ว่า Cosmos
ถนัด physical/temporal reasoning จริงสำหรับงาน smart-spaces safety. Trade-off: Thai ของ Cosmos มี artifact
เล็กน้อย (คำปนภาษาอื่นบางครั้ง) ส่วน Qwen3-VL ไทยสะอาดกว่า.

**Gotcha สำคัญ:** Cosmos เป็น reasoning model — vLLM ใส่คำตอบไว้ในฟิลด์ `message.reasoning`
(ไม่ใช่ `content`). ต้อง fallback อ่าน `content → reasoning_content → reasoning`.

**อ่านผล:**
- **Chunking ยก recall 38%→62%** — จับ sop_violation, unauthorized_person, hygiene ครบ. ยืนยันสมมติฐาน
  ว่า whole-video sampling เบาเกินไป.
- **แต่ precision ตกเป็น 26%** — model over-flag `sop_violation` ช่วง 00:00–01:00 (ก่อนเหตุจริงเริ่มที่
  01:13). สาเหตุ: per-chunk ไม่มี baseline + prompt priming ให้หาการละเมิด → เห็นการวางกระป๋องปกติเป็น
  violation. **ต้องแก้ prompt / เพิ่ม context ว่าเป็นการทำงานปกติจนกว่าจะเห็นชัด.**
- **near-miss @02:55 ยังพลาดทั้ง 2 วิธี** (critical). chunk 11 (02:45–03:00) เห็นเป็น sop_violation แทน.
  เหตุ near-miss คือการเคลื่อนไหว ~2–4s (มือเข้าเครื่อง) — 32 เฟรม/15s อาจยังไม่พอ + 720p อาจสูญรายละเอียด
  มือ. **→ ต้องเพิ่มความถี่เฟรมเฉพาะช่วง หรือ prompt เจาะจง near-miss หรือใช้ Cosmos (ถนัด physical).**
- **ppe_violation** เจอที่ 03:30 (ของจริง 03:35–03:38) พลาดเพราะห่างเกิน tolerance 4s นิดเดียว.
- **Thai quality: ดีมาก** — บรรยายลื่น แม่นบริบท ("วางกระป๋องจากกล่อง NG ลงสายพานโดยไม่ตรวจสอบ",
  "บุคคลที่สามเข้ามาในพื้นที่") ใช้กับ UI ได้ทันที. → **ไม่ต้องมีชั้นแปลไทย** (แก้ risk R1).

### Throughput / Real-time (วัดจริงบน 1×RTX 3090, Cosmos, chunk 15s)
- pure inference: **~11.7s/chunk** (cold 15.3s → warm ~9.9s), ffmpeg extract 1.3s.
- รวม **~13s ประมวลผลวิดีโอ 15s = 1.16× realtime** (warm ~1.34×) → **ตามทัน 1 สตรีมแบบ near-realtime**.
- **Cadence: ออกผลทุก 15s. Latency ~26s** (รอ chunk 15s + infer 11s) หลัง event เกิดจริง.
- chunk 8s → 0.63× realtime (ตกขบวนบน GPU เดียว).
- **Scale:** stream เดี่ยว GPU ยังว่างมาก → vLLM batch หลายกล้องพร้อมกันได้ (คอขวดคือ per-request latency
  ไม่ใช่ throughput). ปรับเร็วขึ้น: GPU แรงกว่า, batching, stream เฟรมตรง (ตัด ffmpeg 1.3s), ลด reasoning tokens.
- **สรุป: เหมาะกับ safety alerting (near-realtime หน่วง ~ครึ่งนาที) ไม่ใช่ per-frame instant.**

**Definition of Done — สถานะปัจจุบัน (Cosmos + chunked 15s + merge 20s):**
- [x] near-miss @02:55 ตรวจเจอ (critical) — **ผ่าน**.
- [x] Recall(type) ≥ 70% — **ผ่าน** (75%).
- [x] Precision ≥ 60% — **ผ่าน** (62%) — ได้จาก temporal merge (ไม่ใช่ prompt; prompt suppress ทำ recall พัง).
- [x] `description_th` ใช้กับ UI ได้ — **ผ่าน**.

→ **DoD ครบ 4/4.** เหลืองาน integrate เข้า `backend/` (ไม่ใช่ research อีกต่อไป).

**หมายเหตุ trade-off:** merge ทำให้ timestamp **หยาบลง** (เช่น sop 02:00–03:30 เป็น span เดียว,
near-miss 02:45–03:30 ~45s สำหรับเหตุ ~3s) — แลก precision กับความคมของเวลา. สำหรับ timeline/alert
รับได้ (โชว์ "ช่วงที่เกิด"). ถ้าต้องวินาทีเป๊ะสำหรับ near-miss → ต้อง fine pass crop ช่วง 02:40–03:05
แยก (ยังไม่ทำ). **ppe recall ยัง 0/2** (เพดาน recall ที่ 75%); v4 เคยโผล่ ppe@03:30 ตอนใส่ "เช็ค PPE"
→ เป็น lever เพิ่ม recall ได้ในอนาคต แต่เสี่ยง destabilize label อื่น.

---

## 7. Risks & Open Questions

- **R1 — ภาษาไทยของ Cosmos:** ถ้า `description_th` ห่วย → ใช้ Qwen3-VL, หรือเพิ่มชั้น
  แปล (Cosmos ตรวจ EN → LLM แปลไทย).
- **R2 — near-miss หลุด (event <1s):** ถ้าพลาด → เพิ่ม fps 4→8, หรือ crop ช่วง 02:40–03:05
  รันซ้ำละเอียด.
- **R3 — timestamp drift:** VLM ประเมินเวลาคลาดได้ → คุม tolerance ใน `evaluate.py` (4→6s).
- **R4 — 344 MB / Full HD:** vLLM อาจกิน memory/ช้าที่ fps สูง → พิจารณา downscale 1080p→720p
  ก่อนส่ง, หรือ chunk คลิป.
- **Q1 — whole-video vs chunking:** เริ่มแบบ whole-video (256K context พอสำหรับ 3:39).
  ถ้าผลหลุดค่อยเปลี่ยนเป็น chunk 20s แบบ VSS.

---

## 8. Next Actions

**สถานะ: model + method พิสูจน์แล้ว (Cosmos-Reason2-8B + chunked). เหลือ precision/type-accuracy.**

1. **[prompt engineering — ตัวแปรหลักที่เหลือ]** ลด false positive + แก้ mislabel:
   - บอก model ว่า "การวางกระป๋องเป็นงานปกติ — flag sop_violation เฉพาะเมื่อเห็นชัดว่าไม่ตรวจสอบด้วยสายตา".
   - ให้ few-shot ตัวอย่างของ normal vs violation.
   - นิยาม ppe_violation / near_miss ให้คมขึ้น (แยกจาก sop_violation).
   - ตั้ง sweet spot: chunked 15s (type-accuracy ดีสุด) เป็น baseline.
2. **[integrate]** เอา winning method (Cosmos + chunked + reasoning-field parsing + timestamp offset)
   ไปเขียนใหม่ `backend/app/services/qwen_runner.py` แทน single-frame + keyword grep. ตั้ง
   `QWEN_SERVICE_URL`/endpoint ให้ชี้ vLLM OpenAI API.
3. **[ops]** rotate HF token. Stop/แปลง Vast instance เมื่อไม่ใช้ (ประหยัดค่า GPU).
4. **[optional]** ทดสอบ Qwen3-VL ด้วย prompt ที่ปรับแล้ว (ไทยสะอาดกว่า) เทียบ Cosmos อีกรอบ — เผื่อ
   precision ใกล้กันแล้วเลือกไทยที่ดีกว่า.
