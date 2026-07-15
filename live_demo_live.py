#!/usr/bin/env python3
"""LIVE hybrid — Cosmos พ่นสดตอนวิดีโอเล่น (ไม่ precomputed).
วิดีโอเล่น (0.5x) -> ทุก ~3วิ ส่ง 2 เฟรมปัจจุบันให้ Cosmos (ผ่าน tunnel :18000) ->
Cosmos เล่าสิ่งที่เห็น + tagger ดึง catch flag จากคำเล่า -> เด้งขึ้นจอสด.

ต้องมี: tunnel  ssh -N -L 18000:localhost:18000 -p <port> root@<ip>  รันอยู่ + Cosmos serve.
Run: python live_demo_live.py -> http://localhost:5002 (เปิดในเบราว์เซอร์)."""
import base64
import json
import os
import re
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VIDEO = "cam_a05_720p.mp4"
FRAMES = "_frames"
COSMOS = "http://localhost:18000/v1/chat/completions"
PROMPT = (
    "ภาพ 2 เฟรมต่อเนื่อง (~3วิ) กล้อง CCTV โรงงานกระป๋อง (คน1 ซ้าย, คน2 ขวา). ตรวจทีละจุดก่อนสรุป: "
    "แต่ละคนสวมหมวก/ถุงมือ/หน้ากากครบไหม (ใครถอด?), มีมือใกล้สายพาน/เครื่องไหม, มีของหล่น/คนแปลกหน้าไหม. "
    "แล้วเล่าสั้นๆ 1-2 ประโยคภาษาไทย เน้นจุดเสี่ยงถ้ามี."
)


def _tag(text):
    """ดึง catch flag จากคำเล่า (positive phrases + negation guard เฉพาะจุด)."""
    t = text
    out = []
    # ใช้เฉพาะคำ "บรรยายเชิงบวก" ที่โผล่ตอนมีคนจริง (ผู้หญิง=คนที่ 3 ในคลิป) — เลี่ยง "คนแปลกหน้า"
    # ที่ปนทั้งบวก/ลบ (negation ไทยสลับลำดับได้ -> false positive)
    if any(k in t for k in ("ผู้หญิง", "บุคคลที่สาม", "คนที่สาม")):
        out.append(("บุคคลภายนอก", "high"))
    if any(k in t for k in ("ถอดหน้ากาก", "ไม่สวมหน้ากาก", "ถอดหมวก", "ไม่สวมหมวก",
                            "ถอดถุงมือ", "ไม่สวมถุงมือ", "ดึงหน้ากาก", "หน้ากากออก")):
        out.append(("PPE — ถอดอุปกรณ์", "med"))
    if (re.search(r"มือ[^.]{0,22}(ใกล้|เข้าใกล้|มากเกินไป)[^.]{0,18}(สายพาน|เครื่อง)", t) or "หนีบ" in t):
        if not re.search(r"(ไม่มี|ไม่พบ)[^.]{0,12}มือ[^.]{0,22}(ใกล้|สายพาน)", t):
            out.append(("⚠️ Near-miss — มือใกล้เครื่อง", "high"))
    if re.search(r"กระป๋อง[^.]{0,12}(หล่น|ตกลง|หลุดจากมือ)", t) and not re.search(r"ไม่มี[^.]{0,16}(หล่น|ตก)", t):
        out.append(("ของตก", "high"))
    return out


def narrate(t):
    a = (int(t) // 3) * 3
    b = min(a + 3, 216)
    fa, fb = f"{FRAMES}/t{a:04d}.jpg", f"{FRAMES}/t{b:04d}.jpg"
    if not (os.path.exists(fa) and os.path.exists(fb)):
        return {"t": t, "narration": "", "catches": []}
    import requests
    b64 = lambda p: base64.b64encode(open(p, "rb").read()).decode()
    payload = {"model": "cosmos", "messages": [{"role": "user", "content": [
        {"type": "text", "text": PROMPT},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64(fa)}"}},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64(fb)}"}}]}],
        "max_tokens": 180, "temperature": 0}
    try:
        r = requests.post(COSMOS, json=payload, timeout=60)
        m = r.json()["choices"][0]["message"]
        txt = (m.get("content") or m.get("reasoning_content") or m.get("reasoning") or "").strip()
    except Exception as e:
        return {"t": t, "narration": f"(error: {str(e)[:50]})", "catches": []}
    return {"t": t, "mmss": f"{a//60:02d}:{a%60:02d}", "narration": txt,
            "catches": [{"type": ty, "sev": sev} for ty, sev in _tag(txt)]}


PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>Line Guard — LIVE</title>
<style>
 body{margin:0;font-family:'Segoe UI',sans-serif;background:#0e1116;color:#e6edf3;display:flex;height:100vh}
 .left{flex:1.6;padding:16px;display:flex;flex-direction:column;gap:8px;min-width:0}
 .right{flex:1;display:flex;flex-direction:column;border-left:1px solid #222b36;min-width:330px}
 video{width:100%;border-radius:10px;background:#000}
 h2{margin:2px 0;font-size:17px}.h{font-size:12px;color:#7d8aa0;margin:2px 0 6px}
 .stat{font-size:12px;color:#8fa3bd;display:flex;gap:8px;align-items:center}
 .dot{width:8px;height:8px;border-radius:50%;background:#f85149;display:inline-block;animation:p 1s infinite}@keyframes p{50%{opacity:.3}}
 .pane{padding:12px 14px;overflow-y:auto}.catch{flex:1.05;border-bottom:1px solid #222b36}.under{flex:1}
 .lbl{font-size:12px;font-weight:700;color:#adbac7;margin-bottom:8px;text-transform:uppercase}
 .card{background:#161b22;border-left:4px solid #d29922;border-radius:7px;padding:8px 11px;margin-bottom:8px;animation:in .3s}
 .card.high{border-color:#f85149}.card.med{border-color:#d29922}
 @keyframes in{from{opacity:0;transform:translateX(10px)}}
 .card .t{font-weight:700;color:#fff;font-size:13px}.card .ty{font-size:10px;color:#8b98a5}
 .now{background:#12233a;border:1px solid #1f6feb;border-radius:8px;padding:11px 13px;margin-bottom:10px}
 .now .w{font-size:11px;color:#58a6ff;font-weight:700}.now .n{font-size:15px;margin-top:4px;line-height:1.5}
 .hist{font-size:12px;color:#7d8aa0;line-height:1.5}.hist b{color:#adbac7}.empty{color:#5a6b7d;font-size:12px;text-align:center;margin-top:24px}
</style></head><body>
<div class="left">
  <h2>🔴 Line Guard — LIVE (Cosmos ดูสด)</h2>
  <div class="h">CAM-A05 · Cosmos วิเคราะห์ <b>สดตอนเล่น</b> ทุก ~3วิ · 0.5×</div>
  <video id="v" src="/video" controls autoplay muted></video>
  <div class="stat"><span class="dot"></span><span id="st">กด play เพื่อเริ่ม</span></div>
</div>
<div class="right">
  <div class="pane catch"><div class="lbl">🔔 ตรวจจับ (จากคำเล่าสด)</div><div id="alerts"><div class="empty">รอ…</div></div></div>
  <div class="pane under"><div class="lbl">🗣️ Cosmos เล่าสด</div>
     <div id="now" class="now"><div class="w">—</div><div class="n">รอเริ่ม…</div></div><div id="hist" class="hist"></div></div>
</div>
<script>
const v=document.getElementById('v'),box=document.getElementById('alerts'),st=document.getElementById('st');
const now=document.getElementById('now'),hist=document.getElementById('hist');
const shown=new Set();let first=true,busy=false,hlog=[],lastT=-99;
function mmss(s){s=Math.floor(s);return String(Math.floor(s/60)).padStart(2,'0')+':'+String(s%60).padStart(2,'0')}
v.addEventListener('play',()=>{v.playbackRate=0.5; if(!window._go){window._go=1; loop()}});
async function loop(){
  if(v.paused||v.ended){setTimeout(loop,500);return}
  const t=v.currentTime;
  if(busy || t-lastT<2.6){setTimeout(loop,300);return}
  busy=true;lastT=t;st.textContent='Cosmos กำลังดูช่วง '+mmss(t)+' …';
  try{
    const r=await fetch('/narrate?t='+t.toFixed(1));const d=await r.json();
    if(d.narration){
      now.innerHTML='<div class="w">ช่วง '+(d.mmss||mmss(t))+'</div><div class="n">'+d.narration+'</div>';
      hlog.unshift('<b>'+(d.mmss||mmss(t))+'</b> '+d.narration);hist.innerHTML=hlog.slice(0,8).map(x=>'<div style="margin-bottom:6px">'+x+'</div>').join('');
      for(const c of (d.catches||[])){const k=c.type; if(!shown.has(k+d.mmss)){shown.add(k+d.mmss);
        if(first){box.innerHTML='';first=false}
        const el=document.createElement('div');el.className='card '+c.sev;
        el.innerHTML='<span class="t">'+(d.mmss||mmss(t))+'</span> <span class="ty">'+c.type+'</span>';box.prepend(el);}}
    }
    st.textContent='วิเคราะห์ถึง '+mmss(t);
  }catch(e){st.textContent='error: '+e}
  busy=false;setTimeout(loop,300);
}
</script></body></html>"""


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        p = urllib.parse.urlparse(self.path)
        if p.path == "/":
            self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
        elif p.path == "/narrate":
            t = float(urllib.parse.parse_qs(p.query).get("t", ["0"])[0])
            self._send(200, json.dumps(narrate(t), ensure_ascii=False).encode("utf-8"), "application/json")
        elif p.path == "/video":
            self._serve_video()
        else:
            self._send(404, b"{}")

    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

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
    print("LIVE demo: http://localhost:5002  (ต้องมี tunnel :18000 -> Cosmos)")
    ThreadingHTTPServer(("127.0.0.1", 5002), H).serve_forever()
