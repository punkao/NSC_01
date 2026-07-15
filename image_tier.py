#!/usr/bin/env python3
"""
Image-tier safety detection — the real-time per-frame layer.

Detects PPE (per-worker, visibility-gated), unauthorized person, and foreign object
from single high-res frames. Each concern uses its OWN focused prompt: cramming all
three into one prompt dilutes the model's attention and misses the transient events
(verified 2026-07-14 — the combined prompt missed person+bottle that dedicated
prompts catch continuously). See spike/WORKLOG.md + RESEARCH_METHODS.md.

Key idea for PPE precision — VISIBILITY GATE: the model does NOT reliably follow a
text "assume worn if you can't see it" instruction, so we make it report whether
each body part is visible, and apply the abstention in CODE: flag a missing item
only when the part is clearly visible AND the item is absent.

Usage:
    python image_tier.py                 # full video -> events + GT check
    (requires SSH tunnel: ssh -N -L 18000:localhost:18000 -p <port> root@<ip>)
"""
from __future__ import annotations

import base64
import json
import os
import re
import subprocess
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

import requests

# ---- config -------------------------------------------------------------------
FFMPEG = os.getenv("FFMPEG", r"C:\Users\SaritpopRaktham\AppData\Roaming\Python\Python314"
                             r"\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe")
VIDEO = os.getenv("VIDEO", r"C:\Users\SaritpopRaktham\Desktop\P_kai\line-guard-smart-safe"
                           r"\spike\cam_a05_1080p.mp4")
MODEL_URL = os.getenv("VLLM_URL", "http://localhost:18000/v1/chat/completions")
MODEL = os.getenv("VLLM_MODEL", "cosmos")
SAMPLE_STEP = int(os.getenv("SAMPLE_STEP", "3"))       # seconds between frames
DEBOUNCE_MIN = 2                                        # detections needed to confirm
# Which PPE items to flag. mask is disabled: this scenario has no mask violations in
# the ground truth and tilted-head frames produce false positives. Re-enable when a
# use case needs it (with stronger evidence handling).
PPE_ITEMS = tuple(os.getenv("PPE_ITEMS", "cap,gloves").split(","))
FRAME_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_frames")
os.makedirs(FRAME_DIR, exist_ok=True)

# ---- focused prompts (one concern each) ---------------------------------------
PPE_PROMPT = (
    "You are a factory safety inspector viewing ONE still CCTV frame of a canning line. "
    "worker 1 (left, near NG/WAIT boxes), worker 2 (right, near GOOD box). For EACH worker, "
    "for head/hands/face report BOTH whether the part is CLEARLY VISIBLE and whether the PPE "
    "item is worn. JSON only:\n"
    '{"workers":[{"id":"1"|"2","head_visible":bool,"cap":bool,"hands_visible":bool,'
    '"gloves":bool,"face_visible":bool,"mask":bool}]}\n'
    "Strict visibility: hands lowered/behind the machine/out of frame -> hands_visible=false; "
    "head not clearly shown -> head_visible=false; face turned away -> face_visible=false.\n"
    "Gloves note: a worker wearing white cloth gloves is common. A hand that is HOLDING or "
    "WIPING with a cloth/rag (e.g. a red cleaning cloth) is still gloved -> gloves=true. Set "
    "gloves=false ONLY when you clearly see a BARE hand (visible skin, no glove)."
)
PERSON_PROMPT = (
    "You see ONE still CCTV frame of a can inspection line run by exactly TWO workers "
    "(worker 1 left, worker 2 right, white shirts). Is there an ADDITIONAL third person in "
    'the work area? JSON only: {"third_person":bool,"note_th":"<short>"}'
)
FOREIGN_PROMPT = (
    "You see ONE still CCTV frame of a can inspection line work area. Is there an unrelated "
    "personal item (water/drink BOTTLE, cup, phone) placed on the table or conveyor (NOT the "
    'cans, boxes, cloth, or machine)? JSON only: {"foreign_object":bool,"note_th":"<short>"}'
)

PPE_LABEL = {"cap": "หมวก", "gloves": "ถุงมือ", "mask": "หน้ากาก"}


# ---- model I/O ----------------------------------------------------------------
def _extract(t: int) -> str:
    fp = os.path.join(FRAME_DIR, f"t{t:04d}.jpg")
    if not os.path.exists(fp):
        subprocess.run([FFMPEG, "-nostdin", "-loglevel", "error", "-ss", str(t), "-i", VIDEO,
                        "-frames:v", "1", "-q:v", "3", fp], capture_output=True)
    return fp


def _ask(fp: str, prompt: str) -> dict:
    b64 = base64.b64encode(open(fp, "rb").read()).decode()
    payload = {"model": MODEL, "messages": [{"role": "user", "content": [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}]}],
        "max_tokens": 700, "temperature": 0}
    r = requests.post(MODEL_URL, json=payload, timeout=90)
    msg = r.json()["choices"][0]["message"]
    reply = msg.get("content") or msg.get("reasoning_content") or msg.get("reasoning") or ""
    m = re.search(r"\{.*\}", reply, re.DOTALL)
    try:
        return json.loads(m.group(0)) if m else {}
    except (ValueError, TypeError):
        return {}


def analyze_frame(t: int) -> dict:
    """Run the 3 focused prompts on frame t IN PARALLEL (keeps latency ~1 call, not 3)
    and return the set of visibility-gated signals."""
    fp = _extract(t)
    with ThreadPoolExecutor(3) as ex:
        f_ppe = ex.submit(_ask, fp, PPE_PROMPT)
        f_person = ex.submit(_ask, fp, PERSON_PROMPT)
        f_foreign = ex.submit(_ask, fp, FOREIGN_PROMPT)
        ppe, person, foreign = f_ppe.result(), f_person.result(), f_foreign.result()

    sig: set[str] = set()
    obs: dict[str, str] = {}   # raw per-worker/item state for the temporal tracker
    for w in ppe.get("workers", []):
        wid = str(w.get("id"))
        if wid not in ("1", "2"):
            continue
        for item, vkey in (("cap", "head_visible"), ("gloves", "hands_visible"),
                           ("mask", "face_visible")):
            # obs keeps ALL items (incl. mask) so the tracker can re-enable them;
            # sig applies the current stateless gate (PPE_ITEMS) for live_demo compat
            obs[f"{wid}|{item}"] = ("unknown" if not w.get(vkey)
                                    else "on" if w.get(item) else "off")
            if item in PPE_ITEMS and w.get(vkey) and not w.get(item):
                sig.add(f"ppe|{wid}|{item}")
    if person.get("third_person"):
        sig.add("unauthorized_person")
    if foreign.get("foreign_object"):
        sig.add("foreign_object")
    return {"t": t, "sig": sorted(sig), "obs": obs}


_ALERT_TYPE = {"ppe_violation": "PPE", "unauthorized_person": "บุคคลภายนอก",
               "hygiene_violation": "ของแปลกปลอม"}


def alerts_from_signals(sigs) -> list[dict]:
    """Convert per-frame visibility-gated signals into alert cards for the live demo."""
    out = []
    for s in sorted(set(sigs)):
        e = _event(s, 0, 0)
        out.append({"sev": e["severity"], "type": _ALERT_TYPE.get(e["event_type"], e["event_type"]),
                    "text": e["description_th"]})
    return out


# ---- debounce + event assembly ------------------------------------------------
def debounce(rows: list[dict], step: int = SAMPLE_STEP, minlen: int = DEBOUNCE_MIN) -> list[dict]:
    """Confirm a signal only if it appears >=minlen times within a rolling window
    (gap <= 2*step tolerates one flaky missed frame). Returns event spans."""
    hits: dict[str, list[int]] = defaultdict(list)
    for r in rows:
        for s in r["sig"]:
            hits[s].append(r["t"])
    gap = 2 * step + 1
    events = []
    for s, times in hits.items():
        run = []
        for t in sorted(times):
            if run and t - run[-1] <= gap:
                run.append(t)
            else:
                if len(run) >= minlen:
                    events.append(_event(s, run[0], run[-1]))
                run = [t]
        if len(run) >= minlen:
            events.append(_event(s, run[0], run[-1]))
    return sorted(events, key=lambda e: e["start_sec"])


def _event(sig: str, s: int, e: int) -> dict:
    if sig.startswith("ppe|"):
        _, wid, item = sig.split("|")
        etype, desc = "ppe_violation", f"ผู้ปฏิบัติงาน {wid} ไม่สวม{PPE_LABEL[item]}"
        sev = "medium"
    elif sig == "unauthorized_person":
        etype, desc, sev = "unauthorized_person", "บุคคลภายนอกเข้ามาในพื้นที่ทำงาน", "high"
    else:
        etype, desc, sev = "hygiene_violation", "มีของแปลกปลอม (ขวดน้ำ) ในพื้นที่ทำงาน", "low"
    return {"start_sec": s, "end_sec": e, "event_type": etype, "severity": sev,
            "description_th": desc, "_sig": sig}


def _mmss(s: int) -> str:
    return f"{s // 60:02d}:{s % 60:02d}"


# ---- main: full-video run + GT check ------------------------------------------
def main() -> None:
    ts = list(range(0, 220, SAMPLE_STEP))
    print(f"sampling {len(ts)} frames every {SAMPLE_STEP}s (3 prompts each)...")
    with ThreadPoolExecutor(3) as ex:  # 3 outer x 3 inner = ~9 concurrent requests
        rows = sorted(ex.map(analyze_frame, ts), key=lambda r: r["t"])
    json.dump(rows, open(os.path.join(FRAME_DIR, "rows.json"), "w"), ensure_ascii=False)

    # raw observations for the temporal tracker (keeps ALL items incl. mask)
    obs_frames = [{"t": r["t"], "obs": r.get("obs", {})} for r in rows]
    json.dump(obs_frames, open("image_obs.json", "w", encoding="utf-8"), ensure_ascii=False)

    events = debounce(rows)
    for e in events:                                    # add mm:ss for downstream tools
        e["start"], e["end"] = _mmss(e["start_sec"]), _mmss(e["end_sec"])
    json.dump({"events": events}, open("image_events.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("\n===== EVENTS ===== (saved -> image_events.json)")
    for e in events:
        print(f"  {e['start']}-{e['end']}  {e['event_type']:<20} {e['description_th']}")

    # ground-truth check (image-tier detectable events)
    gt = [("unauthorized_person", 96, 100), ("hygiene_violation", 99, 106),
          ("ppe_violation", 179, 180), ("ppe_violation", 215, 218)]
    print("\n===== GT CHECK =====")
    for typ, gs, ge in gt:
        ok = any(e["event_type"] == typ and e["start_sec"] - 6 <= ge and gs - 6 <= e["end_sec"]
                 for e in events)
        print(f"  [{'OK ' if ok else 'MISS'}] {typ} @ {_mmss(gs)}")

    # NEW: temporal-tracked PPE (state machine) — catches removals the stateless gate
    # misses (mask/gloves off) and re-enables mask. Compare against the gate above.
    from ppe_tracker import track as _track
    print("\n===== PPE (temporal tracker — includes mask) =====")
    for e in _track(obs_frames, k=2):
        print(f"  {_mmss(e['start_sec'])}-{_mmss(e['end_sec'])}  {e['description_th']}")


if __name__ == "__main__":
    main()
