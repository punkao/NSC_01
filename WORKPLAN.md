# WORKPLAN — Real-time VLM Safety Detection (แผนงานละเอียด)

> เขียน 2026-07-14 · ทีม model (kaopun) · **ใช้ต่อหลังเปลี่ยน user บนเครื่องนี้**
> เอกสารประกอบ: [`HANDOFF.md`](HANDOFF.md) · [`WORKLOG.md`](WORKLOG.md) (log + ผลทดลอง + research) ·
> [`MODEL_HANDOFF_TO_TEAM.md`](MODEL_HANDOFF_TO_TEAM.md) (ส่งทีม integration/UI)
> เอกสารนี้ = แผน execution ละเอียด (แทน `PLAN_single_track.md` เดิม ที่เป็นฉบับร่าง)

---

# ส่วน A — ต้องรู้ก่อนเริ่ม (Context + Environment)

## A1. สถานะปัจจุบัน (จบอะไรมาแล้ว)
- ✅ **POC พิสูจน์แล้วบน cam_a05 (1 วิดีโอ):** Cosmos-Reason2-8B (vLLM) อ่าน event จากวิดีโอจริงได้
- ✅ **จับได้ 5 ประเภท** — sop_violation, ppe_violation, near_miss, unauthorized_person, hygiene_violation
- ✅ **Track A (video chunked+merge):** recall 75%, precision 62%
- ✅ **Track B (image PPE pass):** PPE recall 2/2 (video track จับ PPE ไม่ได้ ต้องใช้ภาพนิ่ง 1080p)
- ✅ **รวม A+B:** recall 100%, precision 60% → [`result_combined.json`](result_combined.json), [`cam_a05_ai_events.json`](cam_a05_ai_events.json)
- ✅ **คำอธิบายไทยดี** (บอกใคร/อะไร/ทำไม) — จุดขายของ VLM
- ✅ **2-stage fine-localize:** เหตุที่เห็นชัด (คนเข้า/PPE) ปักวินาทีเป๊ะได้ ([`fine_localize.py`](fine_localize.py))
- ✅ **backend:** `engine=cosmos` ใน `/api/analyze/video` (unit test ผ่าน, e2e ยังไม่รัน)

## A2. ทิศทางที่ตัดสินแล้ว (Decision — LOCKED)
**ไป: VLM-only per-frame near-realtime** (ยิงเฟรมทุก ~1-2 วิ → VLM → เตือน ~1-3 วิ)
- **โฟกัส:** PPE + unauthorized_person + SOP · near_miss = หยาบ/optional (จับไม่แม่น)
- **เหตุผล (จาก research ใน WORKLOG):**
  - งานเรา = **compliance monitoring** → มาตรฐาน IEC 61508 ยอมรับหน่วง "หลายวินาที" (ไม่ต้อง ms)
  - VLM ต่อเฟรม ~1-5 วิ = **ผ่านเกณฑ์ realtime ของงานนี้จริง**
  - ถูกกว่า streaming-VLM/H100 สิบเท่า (รันบน 3090/A100 ได้)
  - ยังเป็น "VLM system" 100% (ตรงที่ปูงานไว้)
- **ไม่ไป:** streaming VLM (แพง, general model, PPE-res เสี่ยง) · YOLO-hybrid (เก็บไว้ตอน scale หลายกล้อง)
- **Deliverable เป้าหมาย:** `detect_frame(image) → [events]` endpoint (เร็ว+แม่นพอ) ให้เพื่อนเสียบ stream

## A3. Environment — ตั้งค่าหลังเปลี่ยน USER ⚠️ (ทำก่อนเริ่มงาน)
เมื่อ login เป็น user ใหม่บนเครื่องนี้ ต้องเตรียม:

- [ ] **Repo:** ปัจจุบันอยู่ `C:\Users\SaritpopRaktham\Desktop\P_kai\line-guard-smart-safe`
      → copy ไป user ใหม่ หรือชี้ path ให้ถูก (path จะเปลี่ยนตามชื่อ user)
- [ ] **Vast SSH key:** private key อยู่ `~/.ssh` ของ user เดิม → copy ไป `~/.ssh` ของ user ใหม่
      (ไม่งั้น `ssh -p 53239 root@70.30.158.46` จะไม่ผ่าน)
- [ ] **ffmpeg:** ใช้ imageio_ffmpeg → `pip install imageio-ffmpeg` แล้วหา path ด้วย
      `python -c "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())"`
- [ ] **Python deps (local scripts):** `pip install requests imageio-ffmpeg`
- [ ] **Console ไทย:** Windows cp1252 print ไทยไม่ได้ → รัน python ด้วย `PYTHONIOENCODING=utf-8`
- [ ] **⚠️ Revoke HF token เก่า** (บัญชี Falsity24 ที่เคยส่งในแชต) ที่ huggingface.co/settings/tokens
      → สร้างใหม่ ตั้งใน `/workspace/.hf_env` บน remote

## A4. Vast / GPU — connect + serve
```bash
ssh -p 53239 root@70.30.158.46          # (instance เดิม ถ้ายังไม่ destroy)
source /venv/main/bin/activate
# serve Cosmos (เปิดทั้ง image+video) — ready ~130-260s
setsid bash /workspace/spike/serve_cosmos.sh > /workspace/vllm_cosmos.log 2>&1 &
curl -s http://localhost:18000/v1/models   # เช็คว่า "cosmos" ขึ้น
```
- serve config: [`serve_cosmos.sh`](serve_cosmos.sh) (เซฟไว้ใน repo แล้ว — `--limit-mm-per-prompt '{"video":1,"image":2}'`)
- GPU: 1×RTX 3090 24GB (Ampere = ไม่มี FP8, ใช้ BF16), max_model_len 16384
- **ถ้า instance ถูก destroy:** เช่าใหม่ → อัป `serve_cosmos.sh` + วิดีโอ + สคริปต์จาก repo กลับขึ้น /workspace/spike

## A5. Gotchas (บทเรียนที่เสียเวลามาแล้ว)
1. Cosmos ใส่คำตอบใน `message.reasoning` (ไม่ใช่ content) → fallback `content→reasoning_content→reasoning`
2. ไฟล์ media ต้องอยู่ใต้ `/workspace` (vLLM `--allowed-local-media-path`) — image ส่ง base64 ได้ ข้ามข้อนี้
3. server เดิม image ปิด (`image:0`) → 400 · ตอนนี้เปิดแล้ว (`image:2`)
4. อย่าใช้ prompt v2/v3/v4 (ทำ recall พัง) — ใช้ v1 (`prompt_safety_temporal.txt`)
5. PPE ต้องภาพ **1080p** (720p มองไม่เห็นหมวก/ถุงมือ)
6. near-miss หา single-frame signature ไม่ได้ (fuzzy) — อย่าคาดหวัง localize

---

# ส่วน B — งานเป็น Phase (Execution)

## ภาพรวม + ลำดับ dependency
| Phase | งาน | Gate/ผ่านเมื่อ | Dependency |
|:---:|---|---|---|
| **0** | เทสต์ SOP บนเฟรมนิ่ง | SOP window fire, ปกติเงียบ | — (ทำก่อน) |
| **1** | combined per-frame prompt (PPE+คน+SOP) | ได้ raw ต่อเฟรมทั้งคลิป | 0 ผ่าน |
| **2** | debounce + ประกอบ event | event มี timestamp + persistence | 1 |
| **3** | วัด latency + เร่งความเร็ว | รู้ ว/เฟรม, หา config ที่ทัน 1x | 1 |
| **4** | near-miss หยาบ (optional) | near_miss span + needs_review | reuse |
| **5** | รวม + วัดผลทั้งคลิป | recall/precision รายงานได้ | 2,4 |
| **6** | ห่อเป็น `detect_frame` endpoint + backend | endpoint เรียกได้ | 2,3 |
| **7** | generalization (วิดีโอที่ 2) | รู้ว่า work ข้ามคลิปไหม | มีวิดีโอ 2 |

---

## Phase 0 — เทสต์ SOP บนเฟรมนิ่ง ⚠️ (GATE — ห้ามข้าม)
**เป้า:** พิสูจน์ว่า SOP ("หยิบ NG วางสายพานไม่ตรวจ") ตรวจจากภาพนิ่งเฟรมเดียวได้ไหม
**Tasks:**
- [ ] ดึงเฟรม 1080p ช่วง SOP จริง (01:13–02:03) + ช่วงปกติ (00:00–01:00, 02:10–02:40) ทุก ~3 วิ
      (ffmpeg pattern เหมือน `ppe_batch` — ดู A4)
- [ ] เขียน probe: prompt ถาม `{"sop_violation": bool, "worker", "note_th"}`
      "มีคนหยิบกระป๋องจากกล่อง NG/reject มาวางบนสายพานโดยไม่ตรวจด้วยสายตาไหม"
- [ ] รันเทียบ: SOP window ต้อง fire, ช่วงปกติต้องเงียบ
**Acceptance:** recall SOP window > 60% + false ในช่วงปกติ < ครึ่ง
**ถ้าไม่ผ่าน:** SOP ถอยไปใช้ Track A (video, Cosmos) → ระบบเป็น "image สำหรับ PPE/คน + video สำหรับ SOP"
**Risk:** สูงสุด — SOP เป็น procedural, เฟรมเดียวอาจไม่พอ

## Phase 1 — combined per-frame prompt (PPE + คน + SOP)
**เป้า:** prompt เดียว/เฟรม คืนทุกอย่าง
**Tasks:**
- [ ] ออกแบบ prompt คืน `{"workers":[{"id","cap","gloves","mask"}], "third_person":bool, "sop_ng":bool, "note_th"}`
- [ ] รันทั้งคลิปทุก ~3 วิ (base จาก `ppe_batch.py`)
- [ ] เช็คว่า prompt รวมแม่นไหม (เทียบกับรันแยกทีละคำถาม)
**Acceptance:** raw ต่อเฟรมครบ, แม่นไม่ต่ำกว่ารันแยกอย่างมีนัย
**Fallback:** ถ้ารวมแม่นตก → แยก 2-3 คำถาม/เฟรม (แลกความเร็ว)

## Phase 2 — debounce + ประกอบ event
**เป้า:** raw เฟรม → event มี timestamp
**Tasks:**
- [ ] debounce: PPE = same-worker+same-item ต่อเนื่อง ≥2 เฟรม / คน = ต่อเนื่อง / SOP = ต่อเนื่อง
      (ตัด flicker FP ที่เจอตอนทดลอง — ดู `ppe_analyze` ใน WORKLOG)
- [ ] แปลงเป็น event schema (start/end/type/severity/description/reason)
- [ ] (option) fine-localize 1 วิ ที่ onset ให้คม (`fine_localize.py`)
**Acceptance:** event มี span + คำอธิบาย, false เฟรมเดี่ยวถูกกรอง

## Phase 3 — วัด latency + เร่งความเร็ว
**เป้า:** ให้ทันวิดีโอ 1x (ต่อ 1 stream)
**Tasks:**
- [ ] วัดจริง: Cosmos ต่อเฟรมกี่วินาที (บน 3090 / ลอง A100)
- [ ] เร่ง: ตัด reasoning tokens (max_tokens สั้น), ลด resolution เท่าที่ PPE ยังเห็น
- [ ] **ถ้ายังช้า (>5 วิ):** ลอง VLM เล็กเร็ว (Apple FastVLM / Qwen2.5-VL-3B) สำหรับ tier PPE/คน,
      เก็บ Cosmos ไว้ SOP (ดู research WORKLOG)
**Acceptance:** PPE/คน หน่วง ≤ ~3 วิ ต่อเฟรมบน 1 stream

## Phase 4 — near-miss หยาบ (optional)
- [ ] reuse `chunk_infer.py` → กรองเอาเฉพาะ near_miss → merge span → ใส่ `needs_review=true`
**Acceptance:** near_miss span โผล่, mark ชัดว่าเชื่อได้น้อย

## Phase 5 — รวม + วัดผลทั้งคลิป
- [ ] merge image events + near-miss หยาบ (`merge_ab.py` ปรับ)
- [ ] `evaluate.py` วัด recall/precision (PPE+คน+SOP แยกจาก near_miss)
- [ ] `to_bulk_events.py` → JSON /api/events/bulk
**Acceptance:** รายงานตัวเลขได้, timeline ยิงเข้า UI ได้

## Phase 6 — ห่อเป็น endpoint + backend
- [ ] `POST /detect-frame` (รับภาพ base64 → คืน events JSON) — ฝั่งเราส่งมอบอันนี้
- [ ] อัปเดต `backend/app/services/cosmos_runner.py` + `cosmos_events.py` ให้เป็น per-frame
- [ ] เพิ่ม field `confidence` / `needs_review` ใน schema
- [ ] อัปเดต `MODEL_HANDOFF_TO_TEAM.md` (บอกเพื่อนวิธีเรียก endpoint จาก stream)
**Acceptance:** เพื่อนเรียก endpoint แล้วได้ events, e2e กับ vLLM sidecar ผ่าน

## Phase 7 — generalization (วิดีโอที่ 2)
- [ ] เอาวิดีโอที่ 2 (จริงยิ่งดี) รัน pipeline เดียวกัน
- [ ] ดู recall/precision เทียบ cam_a05 → รู้ว่า generalize ได้แค่ไหน
**Acceptance:** เข้าใจ variance ข้ามคลิป (gate จริงก่อนสัญญากับใคร)

---

# ส่วน C — Deliverables + Definition of Done

## Deliverables (ฝั่ง model)
- [ ] `detect_frame` endpoint (ภาพ → events, เร็วพอ realtime)
- [ ] pipeline per-frame (extract → prompt → debounce → events) เป็นโค้ดเดียว
- [ ] ผลวัด recall/precision (PPE/คน/SOP) บน cam_a05 + วิดีโอที่ 2
- [ ] อัปเดต backend + docs ส่งทีม

## Definition of Done (POC)
- [ ] อัปวิดีโอ → ได้ event PPE/คน/SOP near-realtime (~1-3 วิ) พร้อมคำอธิบายไทย
- [ ] Phase 0 ตัดสินแล้ว (SOP เฟรมเดียวได้/ไม่ได้)
- [ ] latency วัดจริงแล้ว, อยู่ในเกณฑ์ compliance (หลายวินาที)
- [ ] ทดสอบวิดีโอที่ 2 แล้ว (รู้ generalization)

---

# ส่วน D — Open decisions (ต้องเคาะ/ถามทีม)
1. **Phase 0 SOP** — ผ่านไหม (ตัดสิน "track เดียว" สมบูรณ์ไหม)
2. **วิดีโอที่ 2** — มี/หาได้ไหม (ความเสี่ยงใหญ่สุด = N=1)
3. **GPU** — 3090 พอไหม หรือขยับ A100 (เร็วขึ้น) · deploy หลายกล้อง = งบ GPU
4. **near-miss** — ยอมรับว่าหยาบ+ต้อง human review ได้ไหม
5. **streaming infra** — ใครทำ frame grabber + websocket (backend/frontend)

---

# ส่วน E — File map (spike/)
| ไฟล์ | ใช้ทำอะไร |
|---|---|
| `chunk_infer.py` | Track A video chunk inference |
| `merge_events.py` | รวม event ต่อเนื่อง (Track A) |
| `ppe_batch.py` + `ppe_batch_result.json` | Track B PPE image pass + ผล |
| `fine_localize.py` | 2-stage ปักวินาที (per-frame probe pattern) |
| `merge_ab.py` | รวม Track A + B |
| `evaluate.py` | ให้คะแนนเทียบเฉลย |
| `to_bulk_events.py` | แปลง → schema /api/events/bulk |
| `prompt_safety_temporal.txt` | prompt v1 (ใช้ตัวนี้) |
| `ground_truth_cam_a05.json` | เฉลย (= mock) |
| `cam_a05_ai_events.json` / `result_combined.json` | ผลรวมสุดท้าย |
| `serve_cosmos.sh` | คำสั่ง serve vLLM (image+video) |
| `cam_a05.mp4` | วิดีโอทดสอบ 1080p |

> เริ่มที่ **Phase 0** เสมอ. อ่าน `HANDOFF.md` + `WORKLOG.md` (research + ผลทดลอง) ประกอบ.
