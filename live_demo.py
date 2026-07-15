#!/usr/bin/env python3
"""Live demo (HYBRID) — video on the left, alerts on the right.

Two sources, combined into one timeline as the video plays at 0.5x:
  - LIVE from the model: PPE / unauthorized person / foreign object. As the browser
    plays, it sends the current frame time here; we run the image-tier detector
    (Cosmos via the SSH tunnel) and return alerts for that second.
  - OVERLAY (pre-computed): SOP / near-miss. These are VIDEO-tier events that need
    temporal/multi-frame context, so a single live frame cannot judge them — they
    are computed once (result_cosmos_merged.json) and shown when the video reaches
    their timestamp. near-miss is tagged "ควรตรวจสอบ" (the known low-confidence type).

Run:  python live_demo.py    then open  http://localhost:5000
(requires: SSH tunnel  ssh -N -L 18000:localhost:18000 -p <port> root@<ip>  running)
"""
import json
import os
import re
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Detection reuses the improved image-tier detector: 3 focused prompts (PPE / person
# / foreign) + visibility-gate + drop-mask + cloth hint. See image_tier.py and
# METHOD_PLAYBOOK.md for why each of those matters.
import threading

from image_tier import alerts_from_signals, analyze_frame
from ppe_tracker import ITEM_TH, LiveTracker

VIDEO_PLAY = "cam_a05_720p.mp4"      # smaller file served to the browser (smooth playback)

# PPE now uses the TEMPORAL tracker (stateful across frames) instead of the stateless
# per-frame gate: "not visible -> carry state" recovers removals the gate missed
# (mask/gloves off), and it consumes the full obs (incl. mask) so mask is back in play.
# person / foreign stay stateless (they have no removal/occlusion problem).
_tracker = LiveTracker(2)
_tlock = threading.Lock()
_last_t = [-1.0]


def detect(t: float) -> dict:
    """Detect events at video time t: PPE via the temporal LiveTracker (obs-based),
    person/foreign stateless. Returns alert cards for the page."""
    try:
        row = analyze_frame(int(round(t)))
    except Exception as e:
        return {"t": t, "alerts": [], "err": str(e)[:80]}
    # mask is NOT a requirement for this line and Cosmos is unreliable on it (small
    # object / pulled to chin -> 67% recall + FP both ways vs 100%/low-FP on cap+gloves,
    # verified against claude_gt.json). Drop it so the demo shows only trustworthy PPE.
    obs = {k: v for k, v in row.get("obs", {}).items() if not k.endswith("|mask")}
    with _tlock:
        if t < _last_t[0] - 1:                 # backward seek / replay -> reset temporal state
            _tracker.reset()
        _last_t[0] = t
        off = _tracker.update(obs)
    alerts = [{"sev": "medium", "type": "PPE",
               "text": f"ผู้ปฏิบัติงาน {k.split('|')[0]} ไม่สวม{ITEM_TH.get(k.split('|')[1], k.split('|')[1])}"}
              for k in sorted(off)]
    alerts += alerts_from_signals([s for s in row.get("sig", []) if not s.startswith("ppe|")])
    return {"t": t, "alerts": alerts}


def _load_precomputed() -> list[dict]:
    """SOP + near-miss are VIDEO-tier: they need temporal/multi-frame context, so a
    single live frame cannot judge them. They are pre-computed once and shown as the
    video reaches their timestamp. PPE / person / foreign stay LIVE from the model."""
    # SOP grounding อ่อน (verified โดยดูเฟรมจริง: ท่าหยิบกระป๋องปกติ vs violation แยกด้วยตายาก
    # โมเดลยิงจากท่าทางกว้างๆ + over-fire idle/ยืด span) -> ติดป้าย low-confidence
    label = {"sop_violation": ("low", "ข้ามขั้นตอน (SOP · AI ประเมิน ควรยืนยัน)"),
             "near_miss": ("high", "⚠️ Near-miss (ควรตรวจสอบ)"),
             # mask via SR is too slow (~3s) for the live per-frame path, so it is
             # shown as a precomputed overlay like SOP/near-miss (SR-head + face gate).
             "ppe_violation": ("medium", "😷 PPE — หน้ากาก"),
             "falling_object": ("high", "⚠️ ของตก (กระป๋องหล่น)")}
    out = []
    # Prefer the domain-cleaned video-tier events (near_miss integrity + WAIT-box
    # rule; see postprocess_events.py) so the demo does not fire the 01:00/01:38
    # near_miss false alarms. Fall back to the raw merged file if the clean one
    # is absent.
    src = "result_video_clean.json" if os.path.exists("result_video_clean.json") else "result_cosmos_merged.json"
    try:
        data = json.loads(open(src, encoding="utf-8").read())
    except Exception:
        return out
    for e in data.get("events", []):
        info = label.get(e.get("event_type"))
        if not info:
            continue
        sev, ty = info
        mm = str(e.get("start", "0:00")).split(":")
        sec = int(mm[0]) * 60 + int(mm[1]) if len(mm) == 2 else 0
        # skip the idle-baseline sop at 00:00 (line not running yet -> borderline FP)
        if e.get("event_type") == "sop_violation" and sec == 0:
            continue
        out.append({"t": sec, "sev": sev, "type": ty,
                    "text": e.get("description_th") or e.get("description", "")})
    return sorted(out, key=lambda x: x["t"])


PRECOMPUTED = _load_precomputed()


PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>Live Safety Demo</title>
<style>
 body{margin:0;font-family:'Segoe UI',sans-serif;background:#0f141b;color:#e8eef5;display:flex;height:100vh}
 .left{flex:2;padding:18px;display:flex;flex-direction:column;gap:10px}
 .right{flex:1;background:#141b24;border-left:1px solid #222d3a;padding:16px;overflow-y:auto;min-width:300px}
 video{width:100%;border-radius:10px;background:#000}
 h2{margin:4px 0;font-weight:600}
 .sub{color:#7c8ba0;font-size:13px;margin-bottom:8px}
 .stat{font-size:13px;color:#9fb3c8;display:flex;gap:14px;align-items:center}
 .dot{width:9px;height:9px;border-radius:50%;background:#39d98a;display:inline-block;animation:p 1.4s infinite}
 @keyframes p{50%{opacity:.3}}
 .card{background:#1b2530;border-left:4px solid #f5a524;border-radius:8px;padding:10px 12px;margin-bottom:9px;animation:in .3s}
 .card.high{border-color:#ff4d4f}.card.low{border-color:#5b8def}.card.medium{border-color:#f5a524}
 @keyframes in{from{opacity:0;transform:translateX(12px)}}
 .card .t{font-weight:700;color:#fff}.card .ty{font-size:11px;color:#9fb3c8;text-transform:uppercase;letter-spacing:.5px}
 .card .x{font-size:14px;margin-top:3px}
 .empty{color:#5a6b7d;font-size:13px;text-align:center;margin-top:40px}
</style></head><body>
<div class="left">
  <h2>🏭 Line Guard — Live AI Detection</h2>
  <div class="sub">CAM-A05 · <b>สด</b>: หมวก/ถุงมือ/คน/ของ (Cosmos ต่อเฟรม) · <b>คำนวณล่วงหน้า</b>: SOP/near-miss/หน้ากาก (temporal/SR) · 0.5×</div>
  <video id="v" src="/video" controls autoplay muted></video>
  <div class="stat"><span class="dot"></span><span id="st">พร้อม</span></div>
</div>
<div class="right">
  <h2>🔔 แจ้งเตือน</h2>
  <div class="sub">เด้งตามที่โมเดลตรวจเจอ ณ วินาทีนั้น</div>
  <div id="alerts"><div class="empty">รอเหตุการณ์…</div></div>
</div>
<script>
const v=document.getElementById('v'), box=document.getElementById('alerts'), st=document.getElementById('st');
const PRE = __PRECOMPUTED__;                 // SOP / near-miss (video tier) — shown at their time
const shown=new Set(); let busy=false, first=true; let lastKeys=new Set();
function mmss(s){s=Math.floor(s);return String(Math.floor(s/60)).padStart(2,'0')+':'+String(s%60).padStart(2,'0')}
function card(t,a){                          // show once per distinct event (no repeats)
  const key=a.type+'|'+a.text; if(shown.has(key))return; shown.add(key);
  if(first){box.innerHTML='';first=false}
  const c=document.createElement('div'); c.className='card '+a.sev;
  c.innerHTML='<span class="t">'+mmss(t)+'</span> <span class="ty">'+a.type+'</span><div class="x">'+a.text+'</div>';
  box.prepend(c);
}
async function loop(){
  if(v.paused||v.ended){setTimeout(loop,400);return}
  if(busy){setTimeout(loop,200);return}
  busy=true; const t=v.currentTime; st.textContent='กำลังวิเคราะห์เฟรม '+mmss(t)+' …';
  for(const p of PRE){ if(t>=p.t) card(p.t,p); }           // overlay video-tier events
  try{
    const r=await fetch('/detect?t='+t.toFixed(2)); const d=await r.json();
    st.textContent='ตรวจแล้วถึง '+mmss(t);
    const cur=new Set((d.alerts||[]).map(a=>a.type+'|'+a.text));
    for(const a of (d.alerts||[])){
      const key=a.type+'|'+a.text;
      // person/foreign จับแม่น -> เด้งทันที (แก้ 'เตือนช้า'); PPE รอเจอ 2 ครั้งติด (กัน flicker)
      if(a.type==='PPE' && !lastKeys.has(key))continue;
      card(t,a);
    }
    lastKeys=cur;
  }catch(e){st.textContent='error: '+e}
  busy=false; setTimeout(loop,250);
}
v.addEventListener('play',()=>{v.playbackRate=0.5; if(!window._started){window._started=1;loop()}});
</script></body></html>"""


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        p = urllib.parse.urlparse(self.path)
        if p.path == "/":
            body = PAGE.replace("__PRECOMPUTED__", json.dumps(PRECOMPUTED, ensure_ascii=False))
            self._send(200, body.encode("utf-8"), "text/html; charset=utf-8")
        elif p.path == "/video":
            self._serve_video()
        elif p.path == "/detect":
            t = float(urllib.parse.parse_qs(p.query).get("t", ["0"])[0])
            self._send(200, json.dumps(detect(t), ensure_ascii=False).encode("utf-8"))
        else:
            self._send(404, b"{}")

    def _serve_video(self):
        size = os.path.getsize(VIDEO_PLAY)
        rng = self.headers.get("Range")
        start, end = 0, size - 1
        if rng:
            m = re.search(r"bytes=(\d+)-(\d*)", rng)
            if m:
                start = int(m.group(1))
                end = int(m.group(2)) if m.group(2) else size - 1
        length = end - start + 1
        self.send_response(206 if rng else 200)
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Accept-Ranges", "bytes")
        if rng:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(length))
        self.end_headers()
        with open(VIDEO_PLAY, "rb") as f:
            f.seek(start)
            self.wfile.write(f.read(length))


if __name__ == "__main__":
    print("Live demo: http://localhost:5000  (Ctrl+C to stop)")
    ThreadingHTTPServer(("127.0.0.1", 5000), H).serve_forever()
