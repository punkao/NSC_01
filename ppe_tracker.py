#!/usr/bin/env python3
"""
Temporal PPE state tracking — the fix for the false-negatives we hit with the
stateless per-frame gate (worker removes mask/gloves but no alert; see WORKLOG
2026-07-14).

Per (worker, item) we keep a STATE (on / off / unknown) instead of judging each
frame independently. The key differences from the old visibility-gate:

  1. "not visible" -> CARRY the last known state (do NOT assume worn). So if a
     worker was seen with gloves OFF and then their hands are briefly occluded, the
     state stays OFF and keeps alerting — this is what recovers the missed removals.
  2. A state change needs K consecutive confident observations, so a tilted-head
     one-frame false "off" is filtered (this is why we can re-enable mask).

Input: a list of per-frame observations, each
    {"t": <sec>, "obs": {"1|cap": "on"|"off"|"unknown", "2|gloves": ..., ...}}
Output: ppe_violation events (one span per continuous OFF period per worker+item).

Pure logic — no GPU/network. Feed it the raw obs saved by image_tier.py.
"""
from __future__ import annotations

ITEM_TH = {"cap": "หมวก", "gloves": "ถุงมือ", "mask": "หน้ากาก"}


def track(frames: list[dict], k: int = 2) -> list[dict]:
    """Run the state machine over per-frame observations; return OFF-span events.

    k = consecutive confident observations required to switch state (debounce).
    """
    frames = sorted(frames, key=lambda f: f["t"])
    keys = sorted({key for f in frames for key in f.get("obs", {})})

    state: dict[str, str] = {key: "unknown" for key in keys}
    pend_val: dict[str, str | None] = {key: None for key in keys}
    pend_cnt: dict[str, int] = {key: 0 for key in keys}
    open_off: dict[str, int] = {}          # key -> start_t of current OFF span
    events: list[dict] = []

    def switch(key: str, new: str, t: int) -> None:
        prev = state[key]
        state[key] = new
        if new == "off" and prev != "off":
            open_off[key] = t                       # OFF span starts
        elif new == "on" and key in open_off:
            events.append(_event(key, open_off.pop(key), t))   # OFF span ends

    for f in frames:
        t = f["t"]
        for key in keys:
            o = f.get("obs", {}).get(key, "unknown")
            if o == "unknown":
                continue                            # carry state + pending (bridge occlusion)
            if o == state[key]:
                pend_val[key], pend_cnt[key] = None, 0   # observation confirms state
                continue
            if o == pend_val[key]:
                pend_cnt[key] += 1
            else:
                pend_val[key], pend_cnt[key] = o, 1
            if pend_cnt[key] >= k:
                switch(key, o, t)
                pend_val[key], pend_cnt[key] = None, 0

    last_t = frames[-1]["t"] if frames else 0
    for key, start in open_off.items():             # OFF spans still open at end
        events.append(_event(key, start, last_t))
    return sorted(events, key=lambda e: e["start_sec"])


def _event(key: str, start: int, end: int) -> dict:
    wid, item = key.split("|")
    return {"event_type": "ppe_violation", "severity": "medium",
            "worker": wid, "item": item,
            "start_sec": start, "end_sec": end,
            "description_th": f"ผู้ปฏิบัติงาน {wid} ไม่สวม{ITEM_TH.get(item, item)}"}


class LiveTracker:
    """Streaming version of `track()` for the live demo — feed one frame's obs at a
    time (forward in time), get back the set of items currently OFF (confirmed).

    Same rules as track(): 'unknown' carries state (bridges occlusion); a state
    change needs k consecutive confident observations. Use reset() when the video
    is seeked backward / replayed (temporal state assumes forward time).
    """

    def __init__(self, k: int = 2) -> None:
        self.k = k
        self.state: dict[str, str] = {}
        self.pend_val: dict[str, str | None] = {}
        self.pend_cnt: dict[str, int] = {}

    def reset(self) -> None:
        self.state.clear()
        self.pend_val.clear()
        self.pend_cnt.clear()

    def update(self, obs: dict[str, str]) -> set[str]:
        for key, o in obs.items():
            if key not in self.state:
                self.state[key], self.pend_val[key], self.pend_cnt[key] = "unknown", None, 0
            if o == "unknown" or o == self.state[key]:
                if o == self.state[key]:
                    self.pend_val[key], self.pend_cnt[key] = None, 0
                continue
            if o == self.pend_val[key]:
                self.pend_cnt[key] += 1
            else:
                self.pend_val[key], self.pend_cnt[key] = o, 1
            if self.pend_cnt[key] >= self.k:
                self.state[key], self.pend_val[key], self.pend_cnt[key] = o, None, 0
        return {key for key, s in self.state.items() if s == "off"}


def _mmss(s: int) -> str:
    return f"{s // 60:02d}:{s % 60:02d}"


if __name__ == "__main__":
    import json
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else "image_obs.json"
    k = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    frames = json.loads(open(path, encoding="utf-8").read())
    for e in track(frames, k):
        print(f"  {_mmss(e['start_sec'])}-{_mmss(e['end_sec'])}  {e['description_th']}")
