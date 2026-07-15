#!/usr/bin/env python3
"""Batch PPE pass over full-res still frames (ts_<sec>.jpg). Outputs JSON list
[{t, ppe_violation, workers, note}] to ppe_batch_result.json. Run on the GPU box."""
import base64
import glob
import json
import os
import re
import sys

import requests

BASE = "http://localhost:18000/v1"
MODEL = "cosmos"
PROMPT = (
    "You are a factory safety inspector looking at ONE still image of a can "
    "inspection line. There are up to 2 workers (they may be labelled 1 and 2). "
    "Required PPE for each worker in the work area: a CAP/HAT on the head, cloth "
    "GLOVES on the hands, and a hygiene MASK. For EACH visible worker, look "
    "carefully at their head, hands and face and state whether each item is worn. "
    "Return ONLY JSON, no prose:\n"
    '{"workers":[{"id":1,"cap":true,"gloves":true,"mask":true}],'
    '"ppe_violation":false,"note_th":"<short Thai note>"}\n'
    "Set ppe_violation=true if ANY worker in the area is missing a cap, gloves, or "
    "mask. Judge only from what is clearly visible."
)


def probe(path: str) -> dict:
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    payload = {"model": MODEL, "messages": [{"role": "user", "content": [
        {"type": "text", "text": PROMPT},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
    ]}], "max_tokens": 1024, "temperature": 0}
    r = requests.post(f"{BASE}/chat/completions", json=payload, timeout=180)
    r.raise_for_status()
    msg = r.json()["choices"][0]["message"]
    reply = (msg.get("content") or msg.get("reasoning_content")
             or msg.get("reasoning") or "")
    s, e = reply.find("{"), reply.rfind("}")
    try:
        return json.loads(reply[s:e + 1])
    except Exception:
        return {"parse_error": reply[:200]}


def main():
    frames = sorted(glob.glob(os.path.join(sys.argv[1] if len(sys.argv) > 1 else ".",
                                           "ts_*.jpg")))
    out = []
    for p in frames:
        t = int(re.search(r"ts_(\d+)", os.path.basename(p)).group(1))
        try:
            res = probe(p)
        except Exception as exc:
            res = {"error": str(exc)}
        rec = {"t": t, "ppe_violation": res.get("ppe_violation"),
               "workers": res.get("workers"), "note": res.get("note_th", ""),
               "raw": res if ("error" in res or "parse_error" in res) else None}
        out.append(rec)
        mm = f"{t//60:02d}:{t%60:02d}"
        print(f"  {mm}  ppe_violation={res.get('ppe_violation')}  {res.get('note_th','')}")
    json.dump(out, open("ppe_batch_result.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"\n{len(out)} frames -> ppe_batch_result.json")


if __name__ == "__main__":
    main()
