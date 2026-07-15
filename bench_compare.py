#!/usr/bin/env python3
"""เทียบผล benchmark ทุก config — โหลด bench_results/*.json มาวางเทียบกัน.
รันหลังเก็บครบ (1gpu / 2gpu / a100):  python bench_compare.py
"""
import glob
import json
import os

OUTDIR = "bench_results"

ORDER = {"1gpu": 0, "2gpu": 1, "a100": 2, "h100": 3}


def load():
    rows = []
    for p in glob.glob(os.path.join(OUTDIR, "*.json")):
        try:
            rows.append(json.load(open(p, encoding="utf-8")))
        except Exception as e:
            print(f"skip {p}: {e}")
    return sorted(rows, key=lambda r: ORDER.get(r.get("name", ""), 99))


def main():
    rows = load()
    if not rows:
        print("ยังไม่มีผล — รัน bench_cosmos.py ก่อน (bench_results/ ว่าง)")
        return

    print("\n================= BENCHMARK COMPARISON (tokens ต้องเท่ากันถึงเทียบได้) =================\n")
    h = f"{'config':<8} {'gpu':<16} {'tok':>4} {'L median':>9} {'interval':>9} {'per-sec':>8} {'ทุก2วิ':>8}"
    print(h)
    print("-" * len(h))
    toks = set()
    for r in rows:
        toks.add(r["tokens"])
        v = r["max_video_speed"]
        print(f"{r['name']:<8} {r['gpu']:<16} {r['tokens']:>4} "
              f"{r['latency']['median_s']:>8}s {r['effective_interval_s']:>8}s "
              f"{v['every_1s']:>7}x {v['every_2s']:>7}x")

    if len(toks) > 1:
        print(f"\n⚠️  tokens ไม่เท่ากัน {sorted(toks)} — เทียบตรงๆ ไม่ได้ ควร rerun ให้ token เท่ากัน")

    # winner = video speed สูงสุด ที่ per-second (ชัด+ถี่+เร็ว)
    best = max(rows, key=lambda r: (r["max_video_speed"]["every_1s"], -r["effective_interval_s"]))
    print(f"\n🏆 per-second ชัด+ถี่+เร็วสุด: {best['name']} ({best['gpu']}) "
          f"-> วิดีโอ {best['max_video_speed']['every_1s']}x")

    print("\n--- token latency curve (ต่อ config) ---")
    for r in rows:
        if r.get("token_latency_curve"):
            print(f"  {r['name']:<8}: {r['token_latency_curve']}")

    print("\n--- ตัวอย่าง narration (คุณภาพ) ---")
    for r in rows:
        s = r.get("sample_narrations", [])
        if s:
            print(f"\n  [{r['name']}] {s[0]['mmss']} ({s[0]['latency']}s): {s[0]['text'][:70]}")


if __name__ == "__main__":
    main()
