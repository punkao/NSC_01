# 📊 Benchmark: 1 GPU vs 2 GPU vs A100

เป้าหมาย: หา config ที่ให้ **บรรยายชัด (90 tokens) + ถี่สุด + วิดีโอเร็วสุด (ใกล้ 1.0×)** สำหรับ **live**.
รันทีละ config เก็บ log แยกไฟล์ → เทียบทีหลัง. Baseline = **90 tokens** ทุก config (ต้องเท่ากันถึงเทียบได้).

## ผลลัพธ์เก็บที่
`bench_results/<name>.json` — 1 ไฟล์ต่อ config (1gpu / 2gpu / a100)

---

## ▶️ Phase 1 — 1×4090 (baseline)
```bash
# 1. serve Cosmos (การ์ดเดียว) บน remote — setsid bash serve_cosmos.sh (image mode, gpu-util 0.90)
# 2. tunnel จากเครื่อง local:
ssh -N -L 18000:localhost:18000 -p <port> root@<ip>
# 3. รัน benchmark (local, ใน spike/):
python bench_cosmos.py --name 1gpu --gpu "RTX 4090 x1"
```

## ▶️ Phase 2 — 2×4090 (แยกสตรีม)
```bash
# 1. เช่า 2×4090 -> upload frames + serve 2 instance:
setsid bash serve_cosmos_2gpu.sh          # GPU0->:18000  GPU1->:18001
# 2. tunnel ทั้ง 2 พอร์ต:
ssh -N -L 18000:localhost:18000 -L 18001:localhost:18001 -p <port> root@<ip>
# 3. benchmark 2 endpoints:
python bench_cosmos.py --name 2gpu --gpu "RTX 4090 x2" \
    --endpoints http://127.0.0.1:18000/v1/chat/completions,http://127.0.0.1:18001/v1/chat/completions
```

## ▶️ Phase 3 — A100 (โค้ดเดิม endpoint เดียว)
```bash
# 1. เช่า A100 -> serve_cosmos.sh (เหมือน 1 GPU) -> tunnel :18000
# 2. benchmark:
python bench_cosmos.py --name a100 --gpu "A100 80GB x1"
```

---

## 📈 เทียบผล (หลังเก็บครบ)
```bash
python bench_compare.py
```
แสดงตาราง: latency median · effective interval · video speed@per-second · @ทุก2วิ · ตัวอย่าง narration + บอกตัวชนะ

## รันจริงด้วยตัวชนะ (live)
- **1 GPU / A100:** `python live_demo_combined.py` (endpoint เดียว default)
- **2 GPU:** ตั้ง env ก่อนรัน demo ให้ round-robin 2 การ์ด:
  ```bash
  COSMOS_ENDPOINTS="http://127.0.0.1:18000/v1/chat/completions,http://127.0.0.1:18001/v1/chat/completions" python live_demo_combined.py
  ```
- ผลลัพธ์ live ของตัวชนะ = อัดลง JSON ได้ = offline byproduct

## หมายเหตุ
- Windows: prefix `PYTHONIOENCODING=utf-8 PYTHONUTF8=1` กันภาษาไทย error
- ใช้ `127.0.0.1` ไม่ใช่ `localhost` (localhost มี IPv6 delay ~2s บน Windows python-requests)
- ปรับความชัด: `--tokens 60` (สั้นลง เร็วขึ้น) หรือ `--tokens 120` (ยาวขึ้น) — **แต่ต้องใช้เลขเดียวกันทุก config**
