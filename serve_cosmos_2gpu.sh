#!/bin/bash
# 2 GPU แยกสตรีม: Cosmos 2 instance อิสระ (GPU0->:18000, GPU1->:18001)
# ใช้กับ bench --endpoints http://127.0.0.1:18000/...,http://127.0.0.1:18001/...
# หมายเหตุ: แต่ละ instance กิน ~22GB -> ต้องการ 2 การ์ด 24GB
source /venv/main/bin/activate
source /workspace/.hf_env

start() {  # $1=gpu_id  $2=port  $3=logfile
  CUDA_VISIBLE_DEVICES=$1 setsid vllm serve nvidia/Cosmos-Reason2-8B \
    --host 127.0.0.1 --port $2 \
    --served-model-name cosmos \
    --download-dir /workspace/models \
    --max-model-len 16384 \
    --gpu-memory-utilization 0.90 \
    --limit-mm-per-prompt '{"video":1,"image":2}' \
    --allowed-local-media-path /workspace \
    --reasoning-parser qwen3 \
    --media-io-kwargs '{"video": {"num_frames": 32}}' \
    > "$3" 2>&1 < /dev/null &
  disown
}

start 0 18000 /workspace/vllm0.log
start 1 18001 /workspace/vllm1.log
echo "launched 2 instances: GPU0->:18000  GPU1->:18001 (โหลด model ~1-2 นาที)"
echo "เช็คพร้อม: curl -s localhost:18000/v1/models ; curl -s localhost:18001/v1/models"
