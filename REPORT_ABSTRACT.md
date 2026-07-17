# บทคัดย่อ

โครงงานนี้พัฒนา **SAFEVISION AI** ระบบตรวจจับเหตุการณ์ความปลอดภัยในสายการผลิตจากภาพกล้องวงจรปิด
โดยใช้ **แบบจำลองภาษาและภาพ (Vision-Language Model)** ซึ่งดูภาพแล้วอธิบายเหตุการณ์เป็นภาษาคนได้
ระบบตรวจจับการไม่สวมอุปกรณ์ป้องกันส่วนบุคคล เหตุเกือบเกิดอุบัติเหตุ บุคคลภายนอกเข้าพื้นที่
และการทำงานผิดขั้นตอน พร้อมจับคู่เข้ากับกฎความปลอดภัยและระบุระดับความรุนแรงโดยอัตโนมัติ

จุดต่างจากแนวทางที่ใช้กันทั่วไปคือ ระบบตรวจจับวัตถุแบบเดิมต้องเก็บภาพมาติดป้ายกำกับและฝึกสอน
แบบจำลองใหม่ทุกโรงงานและทุกมุมกล้อง แต่ **โครงงานนี้ไม่ฝึกสอนแบบจำลองเลยแม้แต่ครั้งเดียว
และไม่ใช้ชุดข้อมูลติดป้ายกำกับแม้แต่ภาพเดียว** การเพิ่มกฎความปลอดภัยใหม่ทำได้ด้วยการเพิ่ม
ข้อความในชุดคำสั่ง สถาปัตยกรรมแบ่งเป็นสองชั้น คือชั้นแจ้งเตือนที่ตอบสั้นเพื่อความเชื่อถือได้
และชั้นบรรยายที่เล่าเหตุการณ์เป็นภาษาคน ซึ่งเป็นการออกแบบที่มีผลการวัดรองรับ

ผลการทดสอบบนคลิปทดสอบความยาว 3 นาที 39 วินาที เทียบกับเฉลยที่จัดทำจากการเปิดภาพดูด้วยตา
ทีละเฟรม 74 จุดตรวจ พบว่า **ระบบตรวจจับการละเมิดได้ 46 จาก 56 จุด คิดเป็น 82%
โดยแจ้งผิดเพียง 5 จุด** แยกเป็นหมวก 100% หน้ากาก 80% และถุงมือ 57%
**ตรวจพบเหตุการณ์ครบ 11 รายการและจับคู่กฎความปลอดภัยได้ครบทุกรายการ**
รวมถึง **เหตุเกือบเกิดอุบัติเหตุซึ่งแบบจำลองที่นำมาเปรียบเทียบตรวจไม่พบ**
และทำงานได้ที่ 0.86 เท่าของความเร็ววิดีโอบนการ์ดจอสองใบ โดยขยายได้เชิงเส้น 1.82 เท่า

ข้อค้นพบเชิงวิชาการที่สำคัญคือ **แบบจำลองภาษาและภาพอ่านป้ายชื่อลังออกทุกป้าย
แต่จับคู่ป้ายเข้ากับลังผิดเมื่อลังสองใบอยู่ใกล้กัน** โดยลังที่ห่างกัน 251 พิกเซลถูกเรียกผิด 66%
ขณะที่ลังที่ห่างออกไป 1,053 พิกเซลไม่เคยถูกเรียกผิดเลย ซึ่งเป็นข้อจำกัดเชิงโครงสร้าง
ที่แก้ด้วยการปรับชุดคำสั่งไม่ได้ โครงงานจึงแก้ด้วยการ **ให้โปรแกรมกำหนดขอบเขตของคำถาม
แล้วให้แบบจำลองตอบเฉพาะสิ่งที่อยู่ในกรอบนั้น** ทำให้ความถูกต้องเพิ่มเป็น 8 จาก 8 การตรวจ

ข้อจำกัดของงานคือทดสอบบนวิดีโอเพียงคลิปเดียว และความแม่นยำในระดับปัจจุบันเหมาะกับ
การเป็นเครื่องมือช่วยคัดกรองให้เจ้าหน้าที่ตรวจสอบ มากกว่าการตัดสินโดยอัตโนมัติ

**คำสำคัญ:** แบบจำลองภาษาและภาพ · ความปลอดภัยในสายการผลิต · การตรวจจับเหตุการณ์จากวิดีโอ ·
อุปกรณ์ป้องกันส่วนบุคคล · เหตุเกือบเกิดอุบัติเหตุ · การเรียนรู้แบบไม่ต้องฝึกสอน · กล้องวงจรปิด

---

# Abstract

This project presents **SAFEVISION AI**, a safety event detection system for industrial production lines
that operates on standard CCTV footage using a **Vision-Language Model (VLM)** — a model that
interprets images and describes events in natural language. The system detects personal protective
equipment (PPE) violations, near-miss incidents, unauthorized personnel, and procedural deviations,
then automatically maps each detection to a safety rule and assigns a severity level.

The key distinction from conventional approaches is that object detection systems require collecting
and annotating images, then retraining a model for every factory and every camera angle.
**This project trains nothing and uses no labeled dataset whatsoever.** New safety rules are added
simply by extending the text prompt. The architecture is deliberately split into two tiers:
an alerting tier that answers short yes/no questions for reliability, and a narration tier that
describes events in natural language — a design choice supported by measurement rather than intuition.

Evaluated on a 3-minute 39-second test clip against a ground truth built by manual frame-by-frame
inspection at 74 checkpoints, **the system detected 46 of 56 violations (82%) with only 5 false
alarms** — 100% for hard hats, 80% for face masks, and 57% for gloves. It **identified all 11 safety
events and successfully mapped every one to a safety rule**, including **a near-miss incident that
the comparison model failed to detect**. It runs at 0.86× real-time video speed on two GPUs and
scales linearly at 1.82× when adding a second card.

The principal technical finding is that **the VLM reads every box label correctly yet mis-binds
labels to objects when two boxes are close together**: boxes 251 pixels apart were confused 66% of
the time, while a box 1,053 pixels away was never misidentified. This is a structural limitation
that prompt engineering cannot fix. The project addresses it by **letting code define the scope of
each question so the model only answers about what is inside a given crop**, raising accuracy to
8 out of 8 checks.

The main limitation is that evaluation was performed on a single video clip, and accuracy at the
current level positions the system as a screening aid for safety officers rather than an autonomous
decision maker.

**Keywords:** Vision-Language Model · Industrial Safety · Video Event Detection ·
Personal Protective Equipment (PPE) · Near-Miss Detection · Zero-Shot Learning · CCTV Analytics
