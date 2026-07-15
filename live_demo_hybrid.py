#!/usr/bin/env python3
"""P4: Hybrid demo — 2 ชั้นรวมกัน (ตกผลึกสุดท้าย):
  ชั้น CATCH   = structured detection (PPE/near-miss/คน/ของ) ที่ VLM จับได้ครบ (reliable)
  ชั้น UNDERSTAND = rolling narration ที่ VLM เล่าบริบทต่อเนื่องทุก 6 วิ (เข้าใจ)
= "จับเหตุได้ + เล่าให้เข้าใจ" พร้อมกัน ตรงเป้า VLM video understanding for safety.

ทั้งคู่ precomputed -> เล่นได้เลยไม่ต้อง GPU. Run: python live_demo_hybrid.py -> http://localhost:5001
"""
import json
import os
import re
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VIDEO = "cam_a05_720p.mp4"


def _sec(mmss):
    p = str(mmss).split(":")
    return int(p[0]) * 60 + int(p[1]) if len(p) == 2 else 0


# ---- catch layer (VLM-detected structured events, ตัด falling_object ที่ VLM ตรวจไม่เจอ) ----
_TYPE = {"ppe_violation": ("PPE", "med"), "near_miss": ("⚠️ Near-miss", "high"),
         "unauthorized_person": ("บุคคลภายนอก", "high"), "hygiene_violation": ("ของแปลกปลอม", "low")}
CATCH = []
for e in json.load(open("cam_a05_ai_events.json", encoding="utf-8"))["events"]:
    if e["event_type"] == "falling_object":
        continue
    ty, sev = _TYPE.get(e["event_type"], (e["event_type"], "med"))
    CATCH.append({"t": _sec(e["timestamp_mmss"]), "sev": sev, "type": ty, "text": e["description"]})
CATCH.sort(key=lambda x: x["t"])

# ---- understand layer (rolling narration) ----
NARR = json.load(open("narration_timeline.json", encoding="utf-8"))

PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>Line Guard — VLM Safety Understanding</title>
<style>
 body{margin:0;font-family:'Segoe UI',sans-serif;background:#0e1116;color:#e6edf3;display:flex;height:100vh}
 .left{flex:1.6;padding:16px;display:flex;flex-direction:column;gap:8px;min-width:0}
 .right{flex:1;display:flex;flex-direction:column;border-left:1px solid #222b36;min-width:330px}
 video{width:100%;border-radius:10px;background:#000}
 h2{margin:2px 0;font-size:17px}.h{font-size:12px;color:#7d8aa0;margin:2px 0 6px}
 .stat{font-size:12px;color:#8fa3bd;display:flex;gap:8px;align-items:center}
 .dot{width:8px;height:8px;border-radius:50%;background:#3fb950;display:inline-block;animation:p 1.4s infinite}@keyframes p{50%{opacity:.3}}
 .pane{padding:12px 14px;overflow-y:auto}
 .catch{flex:1.05;border-bottom:1px solid #222b36}
 .under{flex:1}
 .lbl{font-size:12px;font-weight:700;letter-spacing:.4px;color:#adbac7;margin-bottom:8px;text-transform:uppercase}
 .card{background:#161b22;border-left:4px solid #d29922;border-radius:7px;padding:8px 11px;margin-bottom:8px;animation:in .3s}
 .card.high{border-color:#f85149}.card.low{border-color:#58a6ff}.card.med{border-color:#d29922}
 @keyframes in{from{opacity:0;transform:translateX(10px)}}
 .card .t{font-weight:700;color:#fff;font-size:13px}.card .ty{font-size:10px;color:#8b98a5;text-transform:uppercase}
 .card .x{font-size:13px;margin-top:2px;line-height:1.45}
 .now{background:#12233a;border:1px solid #1f6feb;border-radius:8px;padding:11px 13px;margin-bottom:10px}
 .now .w{font-size:11px;color:#58a6ff;font-weight:700}.now .n{font-size:15px;margin-top:4px;line-height:1.5}
 .hist{font-size:12px;color:#7d8aa0;line-height:1.5}.hist b{color:#adbac7}
 .empty{color:#5a6b7d;font-size:12px;text-align:center;margin-top:24px}
</style></head><body>
<div class="left">
  <h2>🏭 Line Guard — VLM เข้าใจวิดีโอเพื่อความปลอดภัย</h2>
  <div class="h">CAM-A05 · 2 ชั้น: <b>ตรวจจับ</b> (เหตุการณ์) + <b>เล่าเข้าใจ</b> (บริบทต่อเนื่อง) · 0.5×</div>
  <video id="v" src="/video" controls autoplay muted></video>
  <div class="stat"><span class="dot"></span><span id="st">เล่นเพื่อเริ่ม</span></div>
</div>
<div class="right">
  <div class="pane catch"><div class="lbl">🔔 ตรวจจับเหตุการณ์ (CATCH)</div>
     <div id="alerts"><div class="empty">รอเหตุการณ์…</div></div></div>
  <div class="pane under"><div class="lbl">🗣️ AI เล่าเหตุการณ์ (UNDERSTAND)</div>
     <div id="now" class="now"><div class="w">—</div><div class="n">รอเริ่ม…</div></div>
     <div id="hist" class="hist"></div></div>
</div>
<script>
const CATCH=__CATCH__, NARR=__NARR__;
const v=document.getElementById('v'),box=document.getElementById('alerts'),st=document.getElementById('st');
const now=document.getElementById('now'),hist=document.getElementById('hist');
const shown=new Set();let first=true,lastW=-1,hlog=[];
function mmss(s){s=Math.floor(s);return String(Math.floor(s/60)).padStart(2,'0')+':'+String(s%60).padStart(2,'0')}
v.addEventListener('play',()=>{v.playbackRate=0.5});
v.addEventListener('timeupdate',()=>{
  const t=v.currentTime; st.textContent='กำลังวิเคราะห์ '+mmss(t);
  for(const c of CATCH){ if(t>=c.t){ const k=c.type+c.text; if(!shown.has(k)){shown.add(k);
     if(first){box.innerHTML='';first=false}
     const d=document.createElement('div');d.className='card '+c.sev;
     d.innerHTML='<span class="t">'+mmss(c.t)+'</span> <span class="ty">'+c.type+'</span><div class="x">'+c.text+'</div>';
     box.prepend(d);} } }
  let cur=null; for(const n of NARR){ if(t>=n.t) cur=n; else break; }
  if(cur && cur.t!==lastW){ lastW=cur.t;
     now.innerHTML='<div class="w">ช่วง '+cur.mmss+'</div><div class="n">'+cur.narration+'</div>';
     hlog.unshift('<b>'+cur.mmss+'</b> '+cur.narration);
     hist.innerHTML=hlog.slice(0,8).map(x=>'<div style="margin-bottom:6px">'+x+'</div>').join(''); }
});
</script></body></html>"""


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        p = urllib.parse.urlparse(self.path)
        if p.path == "/":
            body = (PAGE.replace("__CATCH__", json.dumps(CATCH, ensure_ascii=False))
                        .replace("__NARR__", json.dumps(NARR, ensure_ascii=False))).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif p.path == "/video":
            self._serve_video()
        else:
            self.send_response(404)
            self.end_headers()

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
    print(f"Hybrid demo: http://localhost:5001  ({len(CATCH)} catch · {len(NARR)} narration windows)")
    ThreadingHTTPServer(("127.0.0.1", 5001), H).serve_forever()
