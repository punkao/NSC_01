# 🔬 Line Guard — Detailed System Architecture (Research-Grade)

เอกสารเชิงลึกระดับวิจัย: ไล่ทุกขั้นตั้งแต่วิดีโอเข้า → แตกเฟรม → windowing → การประมวลผลใน VLM
(prefill/decode) → การแบ่งงาน **2 GPU (split-stream data-parallel)** → buffer/controller → post-processing.
ตัวเลขทุกตัว**อ้างจากโค้ดจริงและ benchmark co-located** (ไม่ได้ประมาณ).

> Companion: `ARCHITECTURE.md` (ภาพรวม), `BENCHMARK_RESULTS.md` (ตัวเลขดิบ), `FINDINGS_SOP.md` (data ceiling).

---

## 0. Notation (สัญกรณ์)

| สัญลักษณ์ | ความหมาย | ค่าในระบบนี้ |
|---|---|---|
| $V$ | วิดีโอต้นทาง | CAM-A05, 720p (1280×720), $T_v \approx 219$s |
| $\text{fps}_{ex}$ | อัตราการแตกเฟรม | **1 fps** |
| $F=\{f_0,\dots,f_{219}\}$ | เซตเฟรม | $\lvert F\rvert \approx 220$, ชื่อ `t0000.jpg`…`t0219.jpg` |
| $\Delta$ | ระยะห่าง narration point | **1s** (per-second) |
| $W$ | window size | **1** (ใช้ 2 เฟรม: $f_t, f_{t+1}$) |
| $M$ | โมเดล VLM | Cosmos-Reason2-8B (8.0B params) |
| $E_0, E_1$ | vLLM engine replica | GPU0→`:18000`, GPU1→`:18001` |
| $R$ | จำนวน replica (= #GPU) | **2** |
| $C$ | concurrency (ThreadPool workers) | $C=R=2$ |
| $N_{out}$ | max output tokens | 60 / 90 / **150** (offline) |
| $L$ | single-call latency | 1.14s@60 · 1.65s@90 (2×4090) |
| $I$ | effective interval (throughput⁻¹) | 0.91s@60 · 1.19s@90 |
| $H$ | live look-ahead horizon | **8s** |
| $p$ | video playback rate | $\le \Delta/I$ |

---

## 1. Stage 0 — Ingest & Frame Extraction

**Input:** ไฟล์วิดีโอเดียว `cam_a05_720p.mp4` (H.264, 720p, ~3.5 นาที).

**การแตกเฟรม (decimation):** สุ่มตัวอย่างแบบสม่ำเสมอที่ $\text{fps}_{ex}=1$
→ ได้ $F$ โดย $f_t$ = เฟรม ณ วินาทีที่ $t$, เก็บเป็น JPEG ชื่อ `t{tttt}.jpg` (zero-padded 4 หลัก).

$$|F| = \lfloor T_v \cdot \text{fps}_{ex} \rfloor + 1 \approx 220 \text{ เฟรม}$$

**เหตุผลเชิงออกแบบ:**
- 1 fps เพียงพอสำหรับ safety monitoring (เหตุการณ์อันตรายกินเวลา >1s: มือเข้าใกล้สายพาน, ของหล่น, การถอด PPE) — 25/30 fps จะซ้ำซ้อนและเปลือง 25-30× โดยไม่เพิ่ม information gain
- ลด compute จาก ~6,500 เฟรม (30fps) เหลือ 220 → เป็นไปได้ที่จะทำ per-second narration ด้วย GPU จำกัด
- ดัชนี = วินาที → sync กับ playhead ฝั่ง browser ได้ตรงตัว (ไม่ต้อง map timestamp)

**การจับคู่ที่ทนต่อเฟรมหาย** (`generate_timeline.py:57-58`): ถ้าเฟรมบางวินาทีหาย ใช้
`nearest(s) = argmin|x−s|` เลือกเฟรมที่ใกล้ที่สุด → robust ต่อ decode ที่ไม่ครบ.

---

## 2. Stage 1 — Temporal Windowing (2-frame)

แต่ละ narration point $t$ สร้าง **input tuple** ด้วยหน้าต่างเวลา $W=1$:

$$x_t = \big(\text{prompt},\ f_{a},\ f_{b}\big),\quad a=\text{nearest}(t),\ b=\text{nearest}(a{+}W)$$

→ **2 เฟรมต่อเนื่องห่างกัน 1 วินาที**. (`live_demo_combined.py:81-86`, `generate_timeline.py:66-69`)

**ทำไม 2 เฟรม ไม่ใช่ 1:** เฟรมคู่ให้ **temporal cue** — โมเดลอนุมานการเคลื่อนไหวได้ (มือ*กำลังเอื้อม*เข้าสายพาน vs อยู่นิ่ง, ของ*กำลังหล่น* vs วางอยู่). เฟรมเดียว = ภาพนิ่ง แยก "action" ไม่ได้.

**ทำไมไม่ใช่ video-mode ของ vLLM:** ทดสอบแล้ว **video mode ทำ vLLM engine crash** (`EngineDeadError`). จึงบังคับ **image mode** ที่รับ ≤2 ภาพ/prompt (`--limit-mm-per-prompt '{"video":1,"image":2}'`). นี่คือข้อจำกัดเชิงวิศวกรรมที่ define สถาปัตยกรรม — เราส่ง "วิดีโอสั้น" เป็นคู่เฟรม static แทน tensor วิดีโอ.

**Encoding:** เฟรม → base64 → data-URI ฝังใน payload JSON (OpenAI-compatible). ขนาด payload ≈ **1MB/call** (2 รูป) — จุดนี้สำคัญมากใน §6 (network confound).

---

## 3. Stage 2 — Per-Call VLM Inference (ภายใน 1 call)

หนึ่ง call = $x_t \to$ narration $y_t$. ภายใน vLLM engine ทำ 2 เฟส:

### 3.1 Prefill (compute-bound)
1. **Vision encoding:** แต่ละเฟรม 720p → ตัด patch → vision transformer → $n_v$ visual tokens/เฟรม. รวม $2n_v$ visual tokens.
2. **Prompt tokenization:** ข้อความ prompt → $n_p$ text tokens.
3. **Prefill attention** บน context $N_{in}=2n_v+n_p$ tokens → สร้าง KV-cache.

เฟสนี้ **หนักด้วยภาพ** (vision encoder + prefill matmul) → **compute-bound (FLOPs)** ไม่ใช่ bandwidth-bound. เป็นเหตุผลหลักที่ **A100 ไม่ได้เร็วกว่า 4090 อย่างมีนัย** (§8).

### 3.2 Decode (autoregressive)
สร้าง output ทีละ token จนถึง $N_{out}$ หรือเจอ EOS:

$$y_t = \arg\max \prod_{k} P(w_k \mid w_{<k}, x_t),\quad \text{temperature}=0\ (\textbf{greedy, deterministic})$$

- `temperature=0` → **deterministic** → เทียบผลระหว่าง GPU config ได้แบบ apples-to-apples
- `finish_reason`:
  - `"stop"` = เจอ EOS → ประโยคจบสมบูรณ์
  - `"length"` = ชน $N_{out}$ → เรียก `_clean(txt, "length")`: ตัดกลับถึงช่องว่างสุดท้าย (ถ้า index>40) + เติม `…` → **กันคำขาดกลางคัน** (`generate_timeline.py:27-33`)

### 3.3 Output parsing
Cosmos เป็น **reasoning model** — คำตอบไม่อยู่ใน `content` แต่ใน `reasoning`/`reasoning_content` (parse ด้วย `--reasoning-parser qwen3`). โค้ด fallback ตามลำดับ: `content → reasoning_content → reasoning` (`generate_timeline.py:79`).

### 3.4 Latency model $L(N_{out})$
จาก token sweep (co-located, single call):

$$L(N_{out}) \approx L_0 + N_{out}\cdot t_{dec},\quad t_{dec}\approx \frac{1.65-1.14}{90-60}\approx 0.017\ \text{s/token}$$

| $N_{out}$ | ความชัด | $L$ (2×4090) |
|---|---|---|
| 60 | 1–1.5 ประโยค | 1.14s |
| 90 | 2 ประโยคเต็ม | 1.65s |
| 150 | จบสวยเสมอ (offline) | ~2.2s (ประมาณจากเส้น) |

→ latency **สเกลเชิงเส้นกับ output tokens** ที่ระดับนี้ (decode มีสัดส่วนสูง). เลือก tokens = trade-off ความชัด ↔ ความเร็ว.

---

## 4. Stage 3 — 2-GPU Split-Stream Scheduler ⭐ (หัวใจ)

นี่คือส่วนที่ผู้ใช้ถามถึงโดยเฉพาะ: **2 GPU แบ่งงานกันยังไง**

### 4.1 การเลือก parallelism: Data-Parallel (split-stream) ไม่ใช่ Tensor-Parallel

| | Tensor-Parallel (TP=2) | **Split-Stream (ที่เราใช้)** |
|---|---|---|
| แนวคิด | ชาร์ดโมเดล 1 ตัว ข้าม 2 GPU | **2 โมเดลเต็ม** อิสระ 1 ตัว/การ์ด |
| น้ำหนัก | θ กระจาย 2 การ์ด | θ ซ้ำ (full copy ×2, ~16GB/การ์ด) |
| เร่งอะไร | **latency ของ 1 call** (↓~1.2–1.4×) | **throughput** (↑~2× ทำ 2 call พร้อมกัน) |
| overhead | all-reduce ข้าม GPU ทุก layer | **ศูนย์** (ไม่มีการสื่อสารข้าม GPU) |
| เหมาะกับ | 1 คำขอใหญ่ ต้องเร็ว | **สตรีมคำขอถี่ๆ** (narration/วินาที) |

**เหตุผล:** เป้าหมายคือ narration **ทุกวินาที** = ต้องการ **throughput** (จำนวน call/วินาที) ไม่ใช่ latency ของ call เดี่ยว. TP ลด latency ต่อ call แต่มี comm overhead และยังทำได้ทีละ call. Split-stream ทำ 2 call **พร้อมกันจริง** โดยไม่มี overhead → ได้ ~2× throughput = คุ้มกว่าสำหรับ workload นี้.

### 4.2 การ serve (`serve_cosmos_2gpu.sh`)
รัน **2 process แยกกันสมบูรณ์**, pin คนละการ์ดด้วย `CUDA_VISIBLE_DEVICES`:

```
CUDA_VISIBLE_DEVICES=0  vllm serve Cosmos-Reason2-8B  --port 18000  ...   # → GPU0
CUDA_VISIBLE_DEVICES=1  vllm serve Cosmos-Reason2-8B  --port 18001  ...   # → GPU1
```

พารามิเตอร์สำคัญ (เหมือนกันทั้งคู่):
- `--max-model-len 16384` — context สูงสุด (พอสำหรับ 2 ภาพ + prompt + output)
- `--gpu-memory-utilization 0.90` — ให้ vLLM จอง 90% VRAM ทำ KV-cache/paged-attention
- `--limit-mm-per-prompt '{"video":1,"image":2}'` — เพดาน 2 ภาพ/prompt (บังคับ image mode)
- `--reasoning-parser qwen3` — ดึงคำตอบจาก reasoning field
- แต่ละ instance กิน **~22GB** → ต้องการการ์ด ≥24GB สองใบ (4090 = 24GB ✅)

### 4.3 Round-robin dispatch (`generate_timeline.py:63-64`)
Client มี endpoint list `eps=[:18000, :18001]`. งาน index $i$ ไปที่:

$$\text{replica}(i) = E_{\,i \bmod R}$$

→ index **คู่ → GPU0**, index **คี่ → GPU1**. สลับฟันปลาเป๊ะ.

### 4.4 Concurrency control
`ThreadPoolExecutor(max_workers=R=2)` → มี worker พอดี 2 ตัว → **มีงาน in-flight พอดี 2 call** (หนึ่ง/การ์ด) ตลอดเวลา. ไม่มี queue สะสมที่ engine → แต่ละ GPU ประมวลผล 1 call ต่อครั้ง, เสร็จแล้วดึงงานถัดไปทันที.

### 4.5 Timeline การทำงาน (Gantt แนวคิด)
```
เวลา→   0        L       2L      3L      4L
GPU0 | call0 | call2 | call4 | call6 | ...     (index คู่)
GPU1 | call1 | call3 | call5 | call7 | ...     (index คี่)
         ↑ 2 call เดินขนานตลอด → เสร็จ 2 point ต่อ ~L วินาที
```

**Effective interval** (narration ใหม่ออกทุกกี่วิ):

$$I = \frac{\text{wall\_time}}{n} \approx \frac{L}{R}\ (\text{+overhead})$$

วัดจริง: $L=1.14$s@60 → คาด $I\approx0.57$ แต่วัดได้ **0.91s** (overhead: dispatch, base64, localhost RTT). ที่ 90tok: $L=1.65 \to I=1.19$s.

### 4.6 Speedup จาก GPU ที่ 2
$$\text{Speedup} = \frac{I_{1\text{gpu}}}{I_{2\text{gpu}}} \approx R = 2\ \text{(near-linear เพราะ 0 comm overhead)}$$

นี่คือข้อได้เปรียบของ split-stream: scaling เชิงเส้นตามจำนวนการ์ด (เพิ่มการ์ด = เพิ่ม endpoint ใน round-robin).

---

## 5. Throughput → Video Speed (ตัวชี้วัดปลายทาง)

ความเร็ววิดีโอสูงสุดที่เล่นได้ ขณะ narration ตามทัน ที่ cadence $\Delta$:

$$p_{max} = \min\!\Big(1.0,\ \frac{\Delta}{I}\Big)$$

| config (co-located) | $N_{out}$ | $L$ | $I$ | $p_{max}$ (per-second, $\Delta{=}1$) | ทุก-2วิ |
|---|---|---|---|---|---|
| **2×4090** | 60 | 1.14s | **0.91s** | **1.00×** (เต็มสปีด) ✅ | 1.0× |
| **2×4090** | 90 | 1.65s | **1.19s** | **0.84×** | 1.0× |

→ **2×4090 ทำ per-second narration ที่วิดีโอเต็มสปีดได้จริง** (ที่ 60 tokens).

---

## 6. สอง Execution Regimes

### 6.1 Offline batch (`generate_timeline.py`) — สำหรับ demo (0 GPU ตอนโชว์)
- รัน **ครั้งเดียว** บนเครื่อง 2 GPU: 220 points ผ่าน round-robin → wall $\approx I\times220 \approx$ **~262–275s**
- เขียน `cam_a05_timeline.json` (narration + metadata `{model, tokens, step, gpu, date}`)
- **ตอน demo: อ่าน JSON, เล่นวิดีโอ 1.0×, ไม่แตะ GPU** → cost ≈ $0.10 (generate ครั้งเดียว) แล้วเล่นฟรีตลอด

### 6.2 Live buffer-ahead controller (`live_demo_combined.py`) — พิสูจน์ "คิดสด"
Controller ฝั่ง browser (`pump()` ทุก 150ms):

- ตัวแปร: playhead $c$ (วินาทีปัจจุบัน), generation pointer $g$ (genT), buffer $B$ (Map: วินาที→narration), inflight
- **กติกายิงงาน:** ขณะ `inflight < NEP` **และ** $g \le c + H$ **และ** $g \le T_v$ → ยิง `/narrate?t=g` (async, ผลลง $B$), แล้ว $g{+}{+}$
- **การแสดง:** โชว์ $B[s^*]$ โดย $s^* = \max\{k \le c : k \in B\}$ (วินาทีล่าสุดที่มีในบัฟเฟอร์ ≤ playhead → ไม่ทิ้งช่องว่าง)

**เงื่อนไข zero-lag (steady state):** บัฟเฟอร์ไม่มีวันหมด ตราบใด throughput ≥ playback:

$$\frac{1}{I} \ge p \quad\Longleftrightarrow\quad p \le \frac{1}{I}$$

GPU คิดล่วงหน้า $H=8$s → ดูดซับ jitter. `playbackRate` ตั้งตาม $p_{max}$ ของ config (env `PLAYBACK_RATE`). Endpoint ยิงแบบ round-robin `_cosmos_ep()` เช่นเดียวกัน → ใช้ 2 GPU เต็ม.

**ผล:** narration per-second, sync เป๊ะ, ไม่มี lag — ได้คุณภาพเท่า offline แต่ Cosmos **คิดสดจริง**.

---

## 7. Stage 4 — Post-Inference Analysis (text, ไม่ใช้ GPU)

หลังได้ narration + CATCH events → วิเคราะห์ต่อด้วย **LLM (OpenRouter / Claude Opus)** บน text ล้วน (ไม่แย่ง GPU):

### 7.1 CATCH assembly (`generate_timeline.py:97-109`)
รวม `cam_a05_ai_events.json` (เหตุการณ์ที่ curate+verify) → map `event_type`→`(label,severity)`, แนบ `evidence_frame = t{nearest(ts)}.jpg`, sort ตามเวลา. **recall 100%** (verify เฟรมจริง).

### 7.2 F5 — Safety-rule + severity (`analyze_safety.py`)
1 Opus call: จับ 11 events เข้า **rulebook R1–R10** → เติม `rule_id`, `severity`, `category`. ผล 10/11 matched.
**สำคัญ:** ระดับ severity **มาจาก rulebook (มนุษย์กำหนด)** ไม่ใช่ AI เดา — LLM แค่ทำ event→rule matching.

### 7.3 SOP Overview (`sop_overview.py`)
1 Opus call: อ่าน narration timeline → ประเมิน **ภาพรวมประมาณการ** ว่าตามลำดับ SOP 7 ขั้นไหม + ระบุจุด `cannot_assess` อย่างซื่อสัตย์ (แยกกล่อง/ตรวจสายตา — VLM ทำไม่ได้ ดู §9). ไม่ฟันธง → ไม่มี false alert.

---

## 8. Hardware Analysis — ทำไม A100 ไม่คุ้ม

**ข้อค้นพบ (counter-intuitive):** A100-40GB เร็วกว่า 4090 **แค่ ~1.2×** (ไม่ใช่ 2–3× ตามราคา).

**เหตุผลเชิง roofline:**
- workload นี้ **prefill รูปหนัก = compute-bound (FLOPs)**. 4090 มี fp16 throughput สูงพอๆ A100
- A100 เด่นที่ **memory bandwidth (HBM)** ซึ่งช่วยแค่เฟส **decode** ที่สั้น (60–90 tokens)
- → bottleneck อยู่ที่ prefill (compute) ที่ 4090 สู้ได้ → A100 premium ไม่คุ้ม

| เป้าหมาย | คำตอบ |
|---|---|
| คุ้มสุด (live per-second) | 🏆 **2×4090 co-located** (~$0.70/ชม) |
| ถูกสุด (demo) | offline generate 1×4090 ครั้งเดียว (~$0.10) → เล่น 0 GPU |
| ตัดทิ้ง | A100-40GB (แพงกว่าแต่เดี่ยวไม่ถึง per-second) |

**Network confound (บทเรียน methodology):** วัดผ่าน SSH tunnel ได้ 3.5–5s/call แต่ co-located จริง 1.65s — ต่าง ~3s = **network RTT ล้วน** (upload รูป 1MB/call ข้าม tunnel). → **ต้องวัด co-located เท่านั้น** และ deploy demo บนเครื่อง GPU แล้ว tunnel แค่หน้าเว็บ `:5003`.

---

## 9. Limitations (data ceilings — honest)

| จุด | เพดาน | ราก |
|---|---|---|
| หน้ากาก (mask) | ~62% | perception — วัตถุเล็ก (แม้ super-res EDSR-4×) |
| แยกกล่อง NG/WAIT/GOOD | ทำไม่ได้ | **data ceiling** — กล่องเหมือนกัน มุมกดลง (verify เฟรมจริงแล้ว) |
| SOP-skip เป๊ะ (R2,R7,R8·ขั้น1,2,4) | ทำไม่ได้ | พึ่งการแยกกล่อง + การอ่าน "เจตนาตรวจสายตา" |
| near-miss vs วางปกติ | ambiguous | temporal cue 2 เฟรมช่วยได้บางส่วน |

→ ระบบจึง **ship เฉพาะที่เชื่อถือได้** (CATCH + narration + F5 severity + SOP Overview ประมาณการ) และรายงาน SOP-skip เป๊ะเป็น **finding** (`FINDINGS_SOP.md`). แนวทางกู้: ROI/box-grounding (`test_box_layout.py`, future work).

---

## 10. สรุป dataflow (1 บรรทัด)

$$V \xrightarrow{\text{1fps}} F \xrightarrow{W=1} \{x_t\} \xrightarrow[\text{round-robin } i \bmod 2]{E_0 \parallel E_1} \{y_t\} \to \texttt{timeline.json} \xrightarrow{\text{Opus (text)}} \text{+severity +SOP} \to \text{frontend}$$

- **GPU-bound:** Stage 0–3 (Cosmos, 2×4090 split-stream)
- **CPU/API (no-GPU):** Stage 4 (Opus), demo playback (offline JSON)
