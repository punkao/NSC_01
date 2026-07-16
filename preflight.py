#!/usr/bin/env python3
"""Preflight — ยืนยันว่ากำลังยิงใส่ Cosmos-Reason2-8B จริง ก่อนวัดผลทุกครั้ง.

ทำไมต้องมี: เครื่องเช่า (vast.ai template) ตั้ง env `VLLM_MODEL=Qwen/Qwen3.5-9B` ไว้ทั้งเครื่อง
สคริปต์ที่เขียนว่า os.getenv("VLLM_MODEL", "cosmos") จะหยิบค่านั้นไปใช้เงียบๆ
-> เสี่ยงวัด Qwen แล้วรายงานว่าเป็น Cosmos. เช็คด้วยตาไม่พอ ต้องให้โค้ดตรวจเอง

Run: python preflight.py --url http://127.0.0.1:18000/v1/chat/completions
"""
import argparse
import sys

import requests

EXPECT_ROOT = "nvidia/Cosmos-Reason2-8B"


def check(url: str) -> None:
    base = url.split("/v1/")[0]
    r = requests.get(f"{base}/v1/models", timeout=10).json()
    served = {m["id"]: m.get("root", "") for m in r["data"]}
    print(f"endpoint : {base}")
    print(f"served   : {served}")
    roots = [v for v in served.values()]
    if not any(EXPECT_ROOT in v for v in roots):
        sys.exit(f"❌ ไม่ใช่ Cosmos! root={roots} (ต้องการ {EXPECT_ROOT}) — หยุดก่อนวัด")
    for bad in ("VLLM_MODEL", "MODEL_NAME", "VLLM_ARGS"):
        import os
        v = os.getenv(bad)
        if v and "Qwen" in v:
            sys.exit(f"❌ env {bad}={v} จะทำให้สคริปต์ยิงผิดโมเดล — ต้อง unset ก่อน")
    print(f"✅ ยืนยัน: {EXPECT_ROOT}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:18000/v1/chat/completions")
    a = ap.parse_args()
    check(a.url)
