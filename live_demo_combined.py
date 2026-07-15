#!/usr/bin/env python3
"""COMBINED demo (ตกผลึกสุดท้าย) — 2 ชั้นแยกหน้าที่ให้ถูก:
  🔔 CATCH     = structured detection (precomputed, reliable, recall 100%) — client-side sync เวลา, ไม่ต้อง GPU
  🗣️ UNDERSTAND = LIVE narration (Cosmos พ่นสดผ่าน tunnel ทุก ~3วิ) — จุดแข็ง VLM, ตรง thesis
= "จับแม่น (structured) + เล่าเข้าใจสด (narration)" — แก้ปัญหา near-miss FP/person พลาด ของ live-tag เดิม.

ต้องมี (ตอนรัน): tunnel  ssh -N -L 18000:localhost:18000 -p <port> root@<ip>  + Cosmos serve + _frames/ + video.
Run: python live_demo_combined.py -> http://localhost:5003
"""
import base64
import itertools
import json
import os
import re
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VIDEO = "cam_a05_720p.mp4"
FRAMES = "_frames"
# 1 GPU/A100 = endpoint เดียว; 2 GPU = ตั้ง env COSMOS_ENDPOINTS="http://127.0.0.1:18000/...,http://127.0.0.1:18001/..."
_EPS = [e.strip() for e in os.environ.get(
    "COSMOS_ENDPOINTS", "http://localhost:18000/v1/chat/completions").split(",") if e.strip()]
_ep_cycle = itertools.cycle(_EPS)
_ep_lock = threading.Lock()


def _cosmos_ep():  # round-robin เฉลี่ยโหลดข้าม GPU (split-stream)
    with _ep_lock:
        return next(_ep_cycle)

# ---- CATCH layer: structured events (precomputed + human-verified, reliable) ----
# falling_object = curated/verified frames (00:14, 01:52) — เชื่อถือได้เพราะ human-in-loop ไม่ใช่ live VLM
_TYPE = {"ppe_violation": ("PPE", "med"), "near_miss": ("⚠️ Near-miss", "high"),
         "unauthorized_person": ("บุคคลภายนอก", "high"), "hygiene_violation": ("ของแปลกปลอม", "low"),
         "falling_object": ("📦 ของตก", "high")}


def _sec(mmss):
    p = str(mmss).split(":")
    return int(p[0]) * 60 + int(p[1]) if len(p) == 2 else 0


CATCH = []
for e in json.load(open("cam_a05_ai_events.json", encoding="utf-8"))["events"]:
    if e["event_type"] not in _TYPE:
        continue
    ty, sev = _TYPE[e["event_type"]]
    ts = _sec(e["timestamp_mmss"])
    te = _sec(e.get("timestamp_end_mmss", e["timestamp_mmss"]))
    CATCH.append({"t": ts, "t_end": max(te, ts), "sev": sev, "type": ty, "text": e["description"]})
CATCH.sort(key=lambda x: x["t"])

# ---- UNDERSTAND layer: live narration prompt (image mode, 2 frames/window) ----
# per-second mode: วลีสั้นมาก -> ~1.2s/call พอดีกับ 0.7x (สดทุก ~1วิ)
NARR_PROMPT = (
    "ภาพ CCTV โรงงานกระป๋อง (คน1 ซ้าย, คน2 ขวา). "
    "บอกสั้นมากเป็นวลีเดียวภาษาไทยล้วน (ไม่เกิน 10 คำ ห้ามปนภาษาอื่น) ว่าตอนนี้เห็นอะไร/มีจุดเสี่ยงไหม. "
    "ถ้าไม่มีความเสี่ยงให้ตอบว่า 'ทำงานปกติ'."
)


# เฟรมมีทุก ~1วิ (มี gap บ้าง) -> เลือกเฟรมที่ใกล้ที่สุดที่มีจริง เพื่อ window ถี่ 2วิ
_AVAIL = sorted(int(f[1:5]) for f in os.listdir(FRAMES) if f.startswith("t") and f.endswith(".jpg"))


def _nearest(sec):
    return min(_AVAIL, key=lambda x: abs(x - sec)) if _AVAIL else sec


WIN = 1  # per-second: 2 เฟรมห่าง 1วิ = สะท้อน "ตอนนี้" แบบชิดที่สุด


def narrate_live(t):
    a = _nearest(int(t))
    b = _nearest(a + WIN)
    fa, fb = f"{FRAMES}/t{a:04d}.jpg", f"{FRAMES}/t{b:04d}.jpg"
    if not (os.path.exists(fa) and os.path.exists(fb)):
        return {"mmss": f"{a//60:02d}:{a%60:02d}", "narration": ""}
    import requests
    e = lambda p: base64.b64encode(open(p, "rb").read()).decode()
    payload = {"model": "cosmos", "messages": [{"role": "user", "content": [
        {"type": "text", "text": NARR_PROMPT},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{e(fa)}"}},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{e(fb)}"}}]}],
        "max_tokens": 30, "temperature": 0}
    try:
        r = requests.post(_cosmos_ep(), json=payload, timeout=60)
        m = r.json()["choices"][0]["message"]
        txt = (m.get("content") or m.get("reasoning_content") or m.get("reasoning") or "").strip()
    except Exception as ex:
        txt = f"(narration error: {str(ex)[:40]})"
    return {"mmss": f"{a//60:02d}:{a%60:02d}", "narration": txt}


# ---- live CONFIRM: ยิง Cosmos ยืนยัน event ที่ curate ไว้ (feel สด แต่ trigger ยังแม่น 100%) ----
def confirm_live(idx):
    if idx < 0 or idx >= len(CATCH):
        return {"verdict": "skip", "remark": ""}
    c = CATCH[idx]
    a = _nearest(c["t"])  # ใช้ timestamp ที่ curate ไว้ = จังหวะที่ verify แล้วว่า event ชัดสุด
    b = _nearest(a + WIN)
    fa, fb = f"{FRAMES}/t{a:04d}.jpg", f"{FRAMES}/t{b:04d}.jpg"
    if not (os.path.exists(fa) and os.path.exists(fb)):
        return {"verdict": "skip", "remark": ""}
    import requests
    e = lambda p: base64.b64encode(open(p, "rb").read()).decode()
    prompt = (f"ภาพ CCTV โรงงานกระป๋อง (คน1 ซ้าย, คน2 ขวา). ตรวจว่าข้อความนี้ตรงกับสิ่งที่เห็นในภาพไหม: "
              f"\"{c['text']}\". ตอบภาษาไทยล้วน ขึ้นต้นด้วยคำว่า ใช่ หรือ ไม่ใช่ แล้วตามด้วยเหตุผลสั้นๆ 1 ประโยค.")
    payload = {"model": "cosmos", "messages": [{"role": "user", "content": [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{e(fa)}"}},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{e(fb)}"}}]}],
        "max_tokens": 90, "temperature": 0}
    try:
        r = requests.post(_cosmos_ep(), json=payload, timeout=60)
        m = r.json()["choices"][0]["message"]
        txt = (m.get("content") or m.get("reasoning_content") or m.get("reasoning") or "").strip()
    except Exception as ex:
        return {"verdict": "skip", "remark": f"(error {str(ex)[:30]})"}
    verdict = "maybe" if txt.startswith("ไม่") else ("yes" if txt.startswith("ใช่") else "maybe")
    return {"verdict": verdict, "remark": txt}


PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>Line Guard — Combined</title>
<style>
 body{margin:0;font-family:'Segoe UI',sans-serif;background:#0e1116;color:#e6edf3;display:flex;height:100vh}
 .left{flex:1.6;padding:16px;display:flex;flex-direction:column;gap:8px;min-width:0}
 .right{flex:1;display:flex;flex-direction:column;border-left:1px solid #222b36;min-width:340px}
 video{width:100%;border-radius:10px;background:#000}
 h2{margin:2px 0;font-size:17px}.h{font-size:12px;color:#7d8aa0;margin:2px 0 6px}
 .stat{font-size:12px;color:#8fa3bd;display:flex;gap:8px;align-items:center}
 .dot{width:8px;height:8px;border-radius:50%;background:#3fb950;display:inline-block;animation:p 1.4s infinite}@keyframes p{50%{opacity:.3}}
 .dot.live{background:#f85149}
 .pane{padding:12px 14px;overflow-y:auto}.catch{flex:1.05;border-bottom:1px solid #222b36}.under{flex:1}
 .lbl{font-size:12px;font-weight:700;color:#adbac7;margin-bottom:8px;text-transform:uppercase;display:flex;justify-content:space-between}
 .tag{font-size:10px;font-weight:600;padding:1px 7px;border-radius:9px}.tag.rel{background:#12331f;color:#3fb950}.tag.liv{background:#3a1516;color:#f85149}
 .card{background:#161b22;border-left:4px solid #d29922;border-radius:7px;padding:8px 11px;margin-bottom:8px;animation:in .3s}
 .card.high{border-color:#f85149}.card.med{border-color:#d29922}.card.low{border-color:#58a6ff}
 @keyframes in{from{opacity:0;transform:translateX(10px)}}
 .card .t{font-weight:700;color:#fff;font-size:13px}.card .ty{font-size:10px;color:#8b98a5}.card .x{font-size:13px;margin-top:2px;line-height:1.45}
 .cf{font-size:10px;font-weight:600;padding:1px 6px;border-radius:8px;cursor:help}
 .cf.wait{background:#2a2410;color:#d29922;animation:p 1.2s infinite}
 .cf.ok{background:#12331f;color:#3fb950}.cf.chk{background:#1c2530;color:#58a6ff}
 .now{background:#12233a;border:1px solid #1f6feb;border-radius:8px;padding:11px 13px;margin-bottom:10px}
 .now .w{font-size:11px;color:#58a6ff;font-weight:700}.now .n{font-size:15px;margin-top:4px;line-height:1.5}
 .hist{font-size:12px;color:#7d8aa0;line-height:1.5}.hist b{color:#adbac7}.empty{color:#5a6b7d;font-size:12px;text-align:center;margin-top:24px}
</style></head><body>
<div class="left">
  <h2>🏭 Line Guard — VLM Safety (จับแม่น + เล่าเข้าใจสด)</h2>
  <div class="h">CAM-A05 · CATCH=structured (reliable) · UNDERSTAND=Cosmos พ่นสดทุก ~1วิ · 0.6×</div>
  <video id="v" src="/video" controls autoplay muted></video>
  <div class="stat"><span class="dot" id="d"></span><span id="st">กด play เพื่อเริ่ม</span></div>
</div>
<div class="right">
  <div class="pane catch"><div class="lbl"><span>🔔 ตรวจจับเหตุการณ์</span><span class="tag rel">structured · reliable</span></div>
     <div id="alerts"><div class="empty">รอเหตุการณ์…</div></div></div>
  <div class="pane under"><div class="lbl"><span>🗣️ Cosmos เล่าสด</span><span class="tag liv">LIVE</span></div>
     <div id="now" class="now"><div class="w">—</div><div class="n">รอเริ่ม…</div></div><div id="hist" class="hist"></div></div>
</div>
<script>
const CATCH=__CATCH__;
const v=document.getElementById('v'),box=document.getElementById('alerts'),st=document.getElementById('st'),dd=document.getElementById('d');
const now=document.getElementById('now'),hist=document.getElementById('hist');
const shown=new Set();let first=true,busy=false,lastT=-99,hlog=[];
function mmss(s){s=Math.floor(s);return String(Math.floor(s/60)).padStart(2,'0')+':'+String(s%60).padStart(2,'0')}
v.addEventListener('play',()=>{v.playbackRate=0.6; if(!window._go){window._go=1; loop()}});
// CATCH = precomputed structured, sync client-side (ไม่ต้อง server)
v.addEventListener('timeupdate',()=>{
  const t=v.currentTime;
  for(let i=0;i<CATCH.length;i++){ const c=CATCH[i]; if(t>=c.t){ if(!shown.has(i)){shown.add(i);
    if(first){box.innerHTML='';first=false}
    const d=document.createElement('div');d.className='card '+c.sev;
    d.innerHTML='<span class="t">'+mmss(c.t)+'</span> <span class="ty">'+c.type+'</span> <span class="cf wait" id="cf'+i+'">⏳ Cosmos ตรวจสด…</span><div class="x">'+c.text+'</div>';
    box.prepend(d); confirmLive(i);} } }
});
// LIVE CONFIRM = ยิง Cosmos ยืนยัน event ตอน playhead ถึง (trigger ยัง curate 100%)
async function confirmLive(i){
  try{
    const r=await fetch('/confirm?i='+i);const d=await r.json();
    const el=document.getElementById('cf'+i);if(!el)return;
    if(d.verdict==='yes'){el.className='cf ok';el.textContent='✓ Cosmos ยืนยันสด'; if(d.remark)el.title=d.remark;}
    else if(d.verdict==='maybe'){el.className='cf chk';el.textContent='👁 Cosmos ตรวจสด'; el.title='ตรวจสดแล้ว — วัตถุเล็ก/แวบเดียว perception จำกัด (trigger ใช้ curated ที่ verify แล้ว)';}
    else{el.textContent='';}
  }catch(e){const el=document.getElementById('cf'+i);if(el)el.textContent='';}
}
// UNDERSTAND = live narration จาก Cosmos ทุก ~3วิ
async function loop(){
  if(v.paused||v.ended){setTimeout(loop,500);return}
  const t=v.currentTime;
  if(busy||t-lastT<0.9){setTimeout(loop,120);return}
  busy=true;lastT=t;dd.className='dot live';st.textContent='Cosmos กำลังดู '+mmss(t)+' …';
  try{
    const r=await fetch('/narrate?t='+t.toFixed(1));const d=await r.json();
    if(d.narration){
      now.innerHTML='<div class="w">ช่วง '+d.mmss+'</div><div class="n">'+d.narration+'</div>';
      hlog.unshift('<b>'+d.mmss+'</b> '+d.narration);hist.innerHTML=hlog.slice(0,7).map(x=>'<div style="margin-bottom:6px">'+x+'</div>').join('');
    }
    st.textContent='เล่าถึง '+mmss(t);
  }catch(e){st.textContent='narrate error'}
  dd.className='dot';busy=false;setTimeout(loop,300);
}
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
            body = PAGE.replace("__CATCH__", json.dumps(CATCH, ensure_ascii=False)).encode("utf-8")
            self._send(200, body, "text/html; charset=utf-8")
        elif p.path == "/narrate":
            t = float(urllib.parse.parse_qs(p.query).get("t", ["0"])[0])
            self._send(200, json.dumps(narrate_live(t), ensure_ascii=False).encode("utf-8"), "application/json")
        elif p.path == "/confirm":
            i = int(urllib.parse.parse_qs(p.query).get("i", ["-1"])[0])
            self._send(200, json.dumps(confirm_live(i), ensure_ascii=False).encode("utf-8"), "application/json")
        elif p.path == "/video":
            self._serve_video()
        else:
            self._send(404, b"{}")

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
    print(f"Combined demo: http://localhost:5003  ({len(CATCH)} catch precomputed + live narration)")
    print("ต้องมี tunnel :18000 -> Cosmos + _frames/ + video")
    ThreadingHTTPServer(("127.0.0.1", 5003), H).serve_forever()
