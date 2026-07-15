"""Unit tests for the temporal PPE state machine (ppe_tracker.track). No GPU needed.
Proves: sustained removal fires, flicker filtered, occlusion carries state, span
closes on re-don, off detected without prior 'on', workers/items independent."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ppe_tracker import track  # noqa: E402


def _frames(seqs: dict) -> list[dict]:
    """seqs: {key: [obs,...]} -> list of {t, obs} frames (t = frame index seconds)."""
    n = max(len(v) for v in seqs.values())
    out = []
    for i in range(n):
        out.append({"t": i, "obs": {k: v[i] for k, v in seqs.items() if i < len(v)}})
    return out


def test_sustained_removal_fires():
    ev = track(_frames({"2|gloves": "on on off off off off".split()}), k=2)
    assert len(ev) == 1
    assert ev[0]["worker"] == "2" and ev[0]["item"] == "gloves"


def test_brief_flicker_filtered():
    # one stray "off" between "on"s must NOT create an event
    assert track(_frames({"1|mask": "on on off on on".split()}), k=2) == []


def test_occlusion_carries_state():
    # off, then hands hidden (unknown x3), then off again -> ONE span across the gap
    ev = track(_frames({"2|cap": "on on off off unknown unknown unknown off".split()}), k=2)
    assert len(ev) == 1 and ev[0]["end_sec"] == 7


def test_span_closes_on_redon():
    ev = track(_frames({"2|gloves": "on on off off on on".split()}), k=2)
    assert len(ev) == 1 and ev[0]["end_sec"] == 5


def test_off_without_prior_on():
    # bare hand seen from the start (no prior "on") still counts as a violation
    ev = track(_frames({"1|gloves": "unknown unknown off off".split()}), k=2)
    assert len(ev) == 1


def test_workers_and_items_independent():
    ev = track(_frames({"1|mask": "on on off off".split(),
                        "2|gloves": "on on on on".split()}), k=2)
    assert len(ev) == 1 and ev[0]["worker"] == "1" and ev[0]["item"] == "mask"


def test_mask_reenabled():
    # mask is a first-class item again (was dropped in the stateless version)
    ev = track(_frames({"1|mask": "on on off off off".split()}), k=2)
    assert len(ev) == 1 and ev[0]["item"] == "mask"


def _run():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests:
        t()
        print(f"  PASS {t.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    _run()
