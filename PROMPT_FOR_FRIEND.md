# 📨 Prompt สำหรับเพื่อน (copy วางใส่ Claude Code)

> # 🛑 ฉบับเก่า — ใช้ `PROMPT_FOR_FRIEND_UPDATE.md` แทน
>
> ฉบับนี้เขียนก่อนแก้เรื่องระบุลังผิด และก่อนแก้เฉลย ตัวเลข/เวลา event ไม่ตรงกับ `cam_a05_timeline.json` ปัจจุบัน

---


> เพื่อน: clone repo นี้ เปิดด้วย Claude Code แล้ว **วาง prompt ข้างล่างนี้ทั้งก้อน** ให้ Claude อ่าน

---

```
คุณกำลังทำงานฝั่ง FRONTEND ของโปรเจกต์ "Line Guard" — ระบบ VLM ตรวจความปลอดภัยในโรงงาน (กล้อง CAM-A05)
ทีม model (อีกคน) ทำฝั่ง AI เสร็จแล้ว ส่งข้อมูล + demo ให้ งานของคุณคือเชื่อม frontend ให้แสดงผลจากข้อมูลนี้

## อ่าน 3 ไฟล์นี้ก่อนเริ่ม (สำคัญมาก):
1. spike/INTEGRATION_FOR_FRONTEND.md  — คู่มือเชื่อม + JSON schema (contract หลัก)
2. spike/DEMO_SUMMARY.md              — ภาพรวมระบบ + demo ที่มี
3. spike/cam_a05_timeline.json        — ข้อมูลจริงที่ frontend ต้องอ่าน (narration + events)

## สิ่งที่ต้องเข้าใจ
- ระบบมี 2 ชั้น: 🔔 CATCH (เหตุการณ์อันตราย เชื่อถือได้) + 🗣️ narration (Cosmos บรรยายทุกวินาที)
- demo หลักเป็นแบบ OFFLINE = อ่านจาก cam_a05_timeline.json ไฟล์เดียว (ไม่ต้องต่อ GPU)
- โครงสร้าง JSON:
    timeline[]  = { t, mmss, narration, evidence_frame }   ← narration ต่อวินาที (sync ตาม video.currentTime)
    events[]    = { t_start, t_end, mmss, type, label, severity, description, evidence_frame }  ← alert + ระดับความรุนแรง
- severity มี 4 ระดับ (critical/high/medium/low) ใช้กำหนดสี alert
- evidence_frame = ชื่อไฟล์รูป (เช่น "t0096.jpg") = ภาพหลักฐาน ณ เวลาเกิดเหตุ

## งานที่ต้องทำ
เชื่อม frontend (ที่มีอยู่แล้ว — หน้า SOP/safety rules) ให้:
1. เล่นวิดีโอ CAM-A05
2. แสดง narration timeline sync ตามเวลาวิดีโอ (หา entry ที่ t <= currentTime ล่าสุด)
3. แสดง alert เมื่อ currentTime >= t_start พร้อมสี severity + รูป evidence_frame
4. (ถ้ามี GPU/tunnel) รองรับโหมด live: GET /narrate?t=X และ /confirm?i=X — แต่ dev ใช้ offline JSON ก่อนได้

## ข้อควรรู้
- ไฟล์ media (video .mp4, _frames/) ไม่อยู่ใน git (ใหญ่เกิน) — ขอจากทีม model แยก
- ตัวอย่าง demo ที่รันได้: spike/live_demo_offline.py (localhost:5004) — ดูเป็นแนวทาง UI ได้
- อย่า assume narration = detection แม่น (มันคือ "เข้าใจฉาก" ส่วน CATCH คือชั้นที่ verify แล้ว)

เริ่มจากอ่าน 3 ไฟล์ข้างบน แล้วสรุปให้ฟังก่อนว่าเข้าใจ schema + งานยังไง ค่อยลงมือเชื่อม
```

---

## หมายเหตุถึงเพื่อน (นอก prompt)
- repo: https://github.com/punkao/NSC_01.git
- ขอไฟล์ `cam_a05_720p.mp4` + โฟลเดอร์ `_frames/` จากทีม model (ไม่ได้อยู่ใน git)
- อยากลองเห็นหน้าตา demo ก่อน → รัน `python spike/live_demo_offline.py` เปิด localhost:5004
