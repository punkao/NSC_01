#!/usr/bin/env python3
"""Phase 0 — extract 1080p frames from SOP window + normal windows (local).
Uploads tiny JPGs (not the 344MB video) so we can probe SOP per-frame on the remote.
"""
import json
import os
import subprocess

FF = r"C:\Users\SaritpopRaktham\AppData\Roaming\Python\Python314\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
VIDEO = "cam_a05.mp4"          # 1080p original
OUT = "phase0_frames"
os.makedirs(OUT, exist_ok=True)

plan = []
# SOP window 01:13–02:03 (73–123s) every 5s — ควร fire
for t in range(73, 124, 5):
    plan.append((t, "sop"))
# normal A 00:00–01:00 every 10s — ควรเงียบ
for t in range(0, 61, 10):
    plan.append((t, "normal"))
# normal B 02:10–02:40 (130–160s) every 6s — ควรเงียบ
for t in range(130, 161, 6):
    plan.append((t, "normal"))

manifest = []
for t, label in plan:
    fn = f"f_{t:03d}.jpg"
    subprocess.run([FF, "-y", "-ss", str(t), "-i", VIDEO,
                    "-frames:v", "1", "-q:v", "2", os.path.join(OUT, fn)],
                   capture_output=True)
    manifest.append({"file": fn, "sec": t, "window": label})

json.dump({"frames": manifest}, open(os.path.join(OUT, "manifest.json"), "w"), indent=2)
sz = sum(os.path.getsize(os.path.join(OUT, m["file"]))
         for m in manifest if os.path.exists(os.path.join(OUT, m["file"])))
n_sop = sum(1 for m in manifest if m["window"] == "sop")
n_norm = sum(1 for m in manifest if m["window"] == "normal")
print(f"{len(manifest)} frames ({n_sop} sop, {n_norm} normal) -> {OUT}  total {sz/1e6:.1f} MB")
