#!/usr/bin/env python3
"""
Run a video through a vLLM-served VLM (Cosmos-Reason2 or Qwen3-VL) and save the
structured JSON event list.

Works against any OpenAI-compatible vLLM server. Example serve commands are in
spike/README.md.

Usage:
    python run_inference.py \
        --video ../media/videos/cam_a05.mp4 \
        --model nvidia/Cosmos-Reason2-8B \
        --prompt-file prompt_safety_temporal.txt \
        --sop-file sop_cam_a05.txt \
        --fps 4 \
        --out result_cosmos.json

The result JSON is written in the same shape as ground_truth so evaluate.py can
score it directly.
"""
import argparse
import json
import re
import sys
from pathlib import Path

try:
    from openai import OpenAI
except ImportError:
    sys.exit("pip install openai  (>=1.0)  — required to talk to the vLLM server")


def load_prompt(prompt_file: str, sop_file: str | None) -> str:
    prompt = Path(prompt_file).read_text(encoding="utf-8")
    sop = Path(sop_file).read_text(encoding="utf-8").strip() if sop_file else ""
    return prompt.replace("{SOP_CONTEXT}", sop or "No SOP provided.")


def extract_json(text: str) -> dict:
    """Pull the JSON object out of the model reply (tolerates ```json fences and
    leading reasoning text)."""
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else None
    if candidate is None:
        # fall back to the first '{' ... last '}'
        start, end = text.find("{"), text.rfind("}")
        candidate = text[start : end + 1] if start != -1 and end != -1 else "{}"
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as exc:
        print(f"[warn] could not parse JSON: {exc}", file=sys.stderr)
        return {"events": [], "_raw": text}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--prompt-file", default="prompt_safety_temporal.txt")
    ap.add_argument("--sop-file", default=None)
    ap.add_argument("--fps", type=float, default=4.0)
    ap.add_argument("--base-url", default="http://localhost:8000/v1")
    ap.add_argument("--api-key", default="token-abc123")
    ap.add_argument("--max-tokens", type=int, default=4096)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    video_path = Path(args.video).resolve()
    if not video_path.exists():
        sys.exit(f"video not found: {video_path}")

    prompt = load_prompt(args.prompt_file, args.sop_file)
    client = OpenAI(base_url=args.base_url, api_key=args.api_key)

    print(f"[info] model={args.model} fps={args.fps} video={video_path.name}")
    resp = client.chat.completions.create(
        model=args.model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "video_url",
                        "video_url": {"url": f"file://{video_path}"},
                    },
                ],
            }
        ],
        max_tokens=args.max_tokens,
        temperature=0.0,
        extra_body={"mm_processor_kwargs": {"fps": args.fps}},
    )

    msg = resp.choices[0].message
    reasoning = getattr(msg, "reasoning_content", None)
    reply = msg.content or ""
    parsed = extract_json(reply)

    result = {
        "model": args.model,
        "fps": args.fps,
        "video": video_path.name,
        "events": parsed.get("events", []),
        "raw_reply": reply,
        "reasoning": reasoning,
    }
    Path(args.out).write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[done] {len(result['events'])} events -> {args.out}")


if __name__ == "__main__":
    main()
