#!/bin/bash
source /venv/main/bin/activate
source /workspace/.hf_env
exec vllm serve nvidia/Cosmos-Reason2-8B \
  --host 127.0.0.1 --port 18000 \
  --served-model-name cosmos \
  --download-dir /workspace/models \
  --max-model-len 16384 \
  --gpu-memory-utilization 0.95 \
  --limit-mm-per-prompt '{"video":1,"image":2}' \
  --allowed-local-media-path /workspace \
  --reasoning-parser qwen3 \
  --media-io-kwargs '{"video": {"num_frames": 32}}'
