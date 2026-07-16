#!/usr/bin/env python3
"""OFFLINE demo — เล่นจาก cam_a05_timeline.json (0 GPU, วิดีโอเต็มสปีด 1.0×).
narration per-second + CATCH events + evidence snapshot ทั้งหมด sync ฝั่ง browser.
Run: python live_demo_offline.py -> http://localhost:5004
ต้องมี: cam_a05_timeline.json + cam_a05_720p.mp4 + _frames/
"""
import json
import os
import re
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VIDEO = "cam_a05_720p.mp4"
FRAMES = "_frames"
TIMELINE = "cam_a05_timeline.json"

DATA = json.load(open(TIMELINE, encoding="utf-8"))
_SEV = {"critical": "high", "high": "high", "medium": "med", "low": "low"}
for e in DATA["events"]:
    e["sev"] = _SEV.get(e.get("severity", "medium"), "med")

PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>Line Guard — Offline</title>
<style>
 body{margin:0;font-family:'Segoe UI',sans-serif;background:#0e1116;color:#e6edf3;display:flex;height:100vh}
 .left{flex:1.6;padding:16px;display:flex;flex-direction:column;gap:8px;min-width:0}
 .right{flex:1;display:flex;flex-direction:column;border-left:1px solid #222b36;min-width:360px}
 video{width:100%;border-radius:10px;background:#000}
 h2{margin:2px 0;font-size:17px}.h{font-size:12px;color:#7d8aa0;margin:2px 0 6px}
 .stat{font-size:12px;color:#8fa3bd;display:flex;gap:8px;align-items:center}
 .dot{width:8px;height:8px;border-radius:50%;background:#3fb950;display:inline-block;animation:p 1.4s infinite}@keyframes p{50%{opacity:.3}}
 .pane{padding:12px 14px;overflow-y:auto}.catch{flex:1.05;border-bottom:1px solid #222b36}.under{flex:1}
 .lbl{font-size:12px;font-weight:700;color:#adbac7;margin-bottom:8px;text-transform:uppercase;display:flex;justify-content:space-between}
 .tag{font-size:10px;font-weight:600;padding:1px 7px;border-radius:9px}.tag.rel{background:#12331f;color:#3fb950}.tag.off{background:#1c2530;color:#58a6ff}
 .card{background:#161b22;border-left:4px solid #d29922;border-radius:7px;padding:8px 11px;margin-bottom:8px;animation:in .3s;display:flex;gap:10px}
 .card.high{border-color:#f85149}.card.med{border-color:#d29922}.card.low{border-color:#58a6ff}
 @keyframes in{from{opacity:0;transform:translateX(10px)}}
 .card img{width:88px;height:50px;object-fit:cover;border-radius:4px;flex-shrink:0;cursor:pointer}
 .card .t{font-weight:700;color:#fff;font-size:13px}.card .ty{font-size:10px;color:#8b98a5}.card .x{font-size:12px;margin-top:2px;line-height:1.4}
 .now{background:#12233a;border:1px solid #1f6feb;border-radius:8px;padding:11px 13px;margin-bottom:10px}
 .now .w{font-size:11px;color:#58a6ff;font-weight:700}.now .n{font-size:15px;margin-top:4px;line-height:1.5}
 .hist{font-size:12px;color:#7d8aa0;line-height:1.5}.hist b{color:#adbac7}.empty{color:#5a6b7d;font-size:12px;text-align:center;margin-top:24px}
</style></head><body>
<div class="left">
  <h2>🏭 Line Guard — VLM Safety (Offline · เต็มสปีด 1.0×)</h2>
  <div class="h">CAM-A05 · narration per-second · CATCH + evidence + safety-rule severity (LLM Opus)</div>
  <video id="v" src="/video" controls autoplay muted></video>
  <div class="stat"><span class="dot" id="d"></span><span id="st">กด play เพื่อเริ่ม</span></div>
</div>
<div class="right">
  <div class="pane catch"><div class="lbl"><span>🔔 ตรวจจับเหตุการณ์</span><span class="tag rel">structured · reliable</span></div>
     <div id="alerts"><div class="empty">รอเหตุการณ์…</div></div></div>
  <div class="pane under"><div class="lbl"><span>🗣️ Cosmos บรรยาย</span><span class="tag off">per-second · offline</span></div>
     <div id="now" class="now"><div class="w">—</div><div class="n">รอเริ่ม…</div></div><div id="hist" class="hist"></div></div>
</div>
<script>
const TL=__TIMELINE__, EV=__EVENTS__;
const v=document.getElementById('v'),box=document.getElementById('alerts'),st=document.getElementById('st');
const now=document.getElementById('now'),hist=document.getElementById('hist');
const shown=new Set();let first=true,lastIdx=-1,hlog=[];
function mmss(s){s=Math.floor(s);return String(Math.floor(s/60)).padStart(2,'0')+':'+String(s%60).padStart(2,'0')}
v.addEventListener('timeupdate',()=>{
  const t=v.currentTime;
  // CATCH events
  for(const c of EV){ if(t>=c.t_start){ const k=c.type+c.description; if(!shown.has(k)){shown.add(k);
    if(first){box.innerHTML='';first=false}
    const d=document.createElement('div');d.className='card '+c.sev;
    d.innerHTML='<img src="/frames/'+c.evidence_frame+'" onclick="window.open(this.src)">'
      +'<div><span class="t">'+c.mmss+'</span> <span class="ty">'+c.label+' · '+(c.severity||'').toUpperCase()+(c.rule_id?' · '+c.rule_id:'')+(c.category?' · '+c.category:'')+'</span>'
      +'<div class="x">'+c.description+'</div></div>';
    box.prepend(d);} } }
  // narration per-second (หา entry ล่าสุดที่ t<=currentTime)
  let idx=-1;
  for(let i=0;i<TL.length;i++){ if(TL[i].t<=t) idx=i; else break; }
  if(idx>=0 && idx!==lastIdx){ lastIdx=idx; const e=TL[idx];
    now.innerHTML='<div class="w">'+e.mmss+'</div><div class="n">'+e.narration+'</div>';
    const _h=document.createElement('div');_h.style.marginBottom='6px';
    _h.innerHTML='<b>'+e.mmss+'</b> '+e.narration; hist.prepend(_h);  // เก็บครบ เลื่อนอ่านได้
    st.textContent='บรรยายถึง '+mmss(t);
  }
});
</script></body></html>"""


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        p = urllib.parse.urlparse(self.path)
        if p.path == "/":
            body = (PAGE.replace("__TIMELINE__", json.dumps(DATA["timeline"], ensure_ascii=False))
                        .replace("__EVENTS__", json.dumps(DATA["events"], ensure_ascii=False))).encode("utf-8")
            self._send(200, body, "text/html; charset=utf-8")
        elif p.path == "/video":
            self._serve_video()
        elif p.path.startswith("/frames/"):
            self._serve_frame(os.path.basename(p.path))
        else:
            self._send(404, b"{}", "application/json")

    def _serve_frame(self, name):
        path = os.path.join(FRAMES, name)
        if not (re.match(r"^t\d{4}\.jpg$", name) and os.path.exists(path)):
            self._send(404, b"", "image/jpeg")
            return
        self._send(200, open(path, "rb").read(), "image/jpeg")

    def _serve_video(self):
        size = os.path.getsize(VIDEO)
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
        with open(VIDEO, "rb") as f:
            f.seek(start)
            self.wfile.write(f.read(length))


if __name__ == "__main__":
    print(f"Offline demo: http://localhost:5004  ({len(DATA['timeline'])} narration + {len(DATA['events'])} events, 0 GPU)")
    ThreadingHTTPServer(("127.0.0.1", 5004), H).serve_forever()
