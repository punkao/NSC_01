# Vast.ai VLM Spike — "real model, real results"

Goal: prove a modern VLM can produce the **"what happened when"** event timeline
by itself (replacing the hand-written mock), and measure how close it gets to the
CAM-A05 answer key.

We have the answer key (`ground_truth_cam_a05.json`, 35 events → 8 segments,
span 01:13–03:38) so every run gets an objective score.

## Files
| File | What it is |
|------|-----------|
| `ground_truth_cam_a05.json` | The answer key (extracted from the mock bulk-import). |
| `prompt_safety_temporal.txt` | The VLM prompt — asks for JSON events with start/end + our taxonomy, Thai descriptions. |
| `sop_cam_a05.txt` | SOP context injected into the prompt. **Replace with the real SOP before the final run.** |
| `run_inference.py` | Sends the video to a vLLM server, saves structured JSON. Model-agnostic. |
| `evaluate.py` | Scores a result file against the answer key (recall / precision / near-miss). |

## What YOU need to bring
1. **The CAM-A05 video** — this is the ONLY missing piece. Per the DB it is
   "Mock Station.mp4", duration **3:39**, originally stored as
   `media/videos/69953788c36641b6b331e47888a8ecf3.mp4` (not committed — `media/`
   is gitignored). Put your copy at `spike/cam_a05.mp4`.
2. SOP is already filled in from the DB (`sop_cam_a05.txt`) — no action needed.

> Cross-check reference: the camera's `ai_summary` in `db/seed.sql` documents the
> same incident as 5 grouped events (EVT-001 near-miss @02:55 … EVT-005
> unauthorized entry @01:36–01:40, 39 total, 219s, 2 workers) — matches our
> collapsed ground-truth segments.

## Models under test (run both, same harness)
- **Primary:** `nvidia/Cosmos-Reason2-8B` (FP8) — best on smart-spaces/safety.
- **Fallback / Thai check:** `Qwen/Qwen3-VL-8B-Instruct`.

## Vast.ai runbook (one session, both models)

Pick an instance with a **24GB+ GPU** (e.g. RTX 4090 / A6000). Then:

```bash
# 0. deps
pip install "vllm>=0.11.0" openai

# 1. serve Cosmos-Reason2-8B (FP8) — OpenAI-compatible server on :8000
vllm serve nvidia/Cosmos-Reason2-8B \
    --allowed-local-media-path "$(pwd)" \
    --max-model-len 32768 \
    --media-io-kwargs '{"video": {"num_frames": -1}}' \
    --reasoning-parser qwen3 \
    --port 8000
# (wait for "Application startup complete")

# 2. in another shell — run inference + score
python run_inference.py --video cam_a05.mp4 \
    --model nvidia/Cosmos-Reason2-8B \
    --sop-file sop_cam_a05.txt --fps 4 \
    --out result_cosmos.json
python evaluate.py --pred result_cosmos.json

# 3. swap model: stop vLLM, then
vllm serve Qwen/Qwen3-VL-8B-Instruct \
    --allowed-local-media-path "$(pwd)" \
    --max-model-len 32768 \
    --media-io-kwargs '{"video": {"num_frames": -1}}' \
    --reasoning-parser qwen3 --port 8000

python run_inference.py --video cam_a05.mp4 \
    --model Qwen/Qwen3-VL-8B-Instruct \
    --sop-file sop_cam_a05.txt --fps 4 \
    --out result_qwen.json
python evaluate.py --pred result_qwen.json
```

## What we're deciding from the results
- **Detection quality:** recall on the 8 GT segments, esp. the **critical near-miss @ 02:55**.
- **Precision:** how many false events (noise) the model invents.
- **Thai quality:** eyeball `description_th` / `reason` in the result files.
- **FPS sensitivity:** if near-miss is missed, re-run at `--fps 8` (short event).
- Winner + settings feed into rewriting `backend/app/services/qwen_runner.py`
  to use this video-native + JSON + timestamp method instead of single-frame + keyword grep.

## Tuning knobs if results are weak
- `--fps 4 → 8` : catch sub-second events (near-miss).
- Raise `--max-model-len` if the video is long (256K context is available).
- Tighten the prompt's event definitions / few-shot examples.
- `evaluate.py --tolerance 4 → 6` : looser time matching if timestamps drift.
