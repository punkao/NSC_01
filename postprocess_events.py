#!/usr/bin/env python3
"""Domain post-processing filter for CAM-A05 video-tier events.

Fixes the two documented false-alarm patterns WITHOUT touching the prompt
(WORKLOG lesson: fix precision at post-processing, not prompt — prompt suppression
kills recall). Insert this BEFORE merge_events.py in the pipeline:

    chunk_infer -> postprocess_events -> merge_events -> combine_tiers -> to_bulk

Two safety-domain rules:

  Rule A  near_miss integrity
    A real near_miss on this line = a hand entering / getting close to the moving
    belt or machine. Cosmos over-labels routine can-placement as near_miss, which
    produces CRITICAL false alarms (01:00, 01:38). Any near_miss whose text lacks
    hand + machine-contact evidence is RE-CLASSIFIED to sop_violation (it is a
    procedural lapse, not a physical near_miss). The genuine hand-in-belt events
    (02:45 / 03:00 / 03:30, "มือ...ถูกสายพาน cuốn เข้าไป") are kept as near_miss.

  Rule B  SOP source correctness
    Taking a can from the WAIT box is the CORRECT procedure; the violation is
    taking from the NG box. A sop_violation that describes taking from WAIT (and
    not NG) is normal work mislabeled and is DROPPED (removes the 00:00 baseline
    false alarm).

Pure logic — no GPU/network. Idempotent. Reversible (writes a new file).

Usage: python postprocess_events.py <in.json> <out.json>
"""
import json
import sys
from pathlib import Path

# A genuine near_miss needs BOTH a body part and a machine-contact cue.
HAND_CUES = ("มือ",)
MACHINE_CONTACT_CUES = ("สายพาน", "เครื่องจักร", "เครื่อง", "หนีบ", "cuốn", "ดึงเข้า", "ม้วน")


def _text(e: dict) -> str:
    return e.get("description_th") or e.get("description", "")


def is_physical_near_miss(text: str) -> bool:
    """True only when the text describes a hand near/into the belt or machine."""
    has_body = any(cue in text for cue in HAND_CUES)
    has_contact = any(cue in text for cue in MACHINE_CONTACT_CUES)
    return has_body and has_contact


def is_wait_box_normal(text: str) -> bool:
    """True when a sop_violation actually describes the CORRECT source (WAIT box).

    Box labels are written uppercase in the data ("กล่อง WAIT" / "กล่อง NG"), so
    match case-sensitively to avoid catching unrelated substrings.
    """
    return "WAIT" in text and "NG" not in text


def postprocess(events: list[dict]) -> tuple[list[dict], list[str]]:
    kept: list[dict] = []
    log: list[str] = []
    for e in events:
        et = e.get("event_type")
        text = _text(e)
        when = e.get("start", "??")

        if et == "near_miss" and not is_physical_near_miss(text):
            e = dict(e)
            e["event_type"] = "sop_violation"
            e["severity"] = "medium"
            e["_reclassified_from"] = "near_miss"
            log.append(f"  RECLASSIFY near_miss->sop  @{when}  (no hand+machine cue) : {text[:50]}")
            kept.append(e)
            continue

        if et == "sop_violation" and is_wait_box_normal(text):
            log.append(f"  DROP sop_violation         @{when}  (WAIT box = correct)  : {text[:50]}")
            continue

        kept.append(e)
    return kept, log


def main() -> None:
    inp = sys.argv[1] if len(sys.argv) > 1 else "result_cosmos_chunked.json"
    out = sys.argv[2] if len(sys.argv) > 2 else "result_pp.json"

    data = json.loads(Path(inp).read_text(encoding="utf-8"))
    events = data.get("events", [])
    kept, log = postprocess(events)

    data["events"] = kept
    data["method"] = data.get("method", "") + "+postproc(nearmiss_integrity,wait_box)"
    Path(out).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"{len(events)} events -> {len(kept)} kept  ({len(events) - len(kept)} dropped) -> {out}")
    print("\n".join(log) if log else "  (no changes)")


if __name__ == "__main__":
    main()
