# เอกสารอ้างอิง

> ทุกรายการเปิดตรวจจากแหล่งต้นทางจริงก่อนอ้างอิง ไม่ได้เขียนจากความจำ
> แยกให้ชัดระหว่าง **บทความวิชาการ** กับ **model card / ซอฟต์แวร์** เพราะบางแบบจำลองที่ใช้
> ยังไม่มีบทความตีพิมพ์ของตัวเอง การอ้างจึงต้องระบุตามความเป็นจริง
>
> รายการนี้คัดเฉพาะสิ่งที่ **เป็นแกนของระบบ** หรือ **รองรับข้อความในรายงานโดยตรง**
> ส่วนไลบรารีและบริการพื้นฐานที่ไม่ใช่สาระของงาน (ไลบรารีประมวลผลภาพทั่วไป บริการเช่าเครื่อง
> แหล่งดาวน์โหลดน้ำหนัก ตัวกลางเรียก API) ระบุไว้ในบทที่ 5 หัวข้อ 5.3 แล้ว ไม่นำมาอ้างซ้ำที่นี่

## แบบจำลองและซอฟต์แวร์ที่เป็นแกนของระบบ

[1] NVIDIA. *Cosmos-Reason2-8B* [model card]. Hugging Face.
    https://huggingface.co/nvidia/Cosmos-Reason2-8B
    — **แบบจำลองหลักของโครงงานนี้** ใช้ในชั้น L2 (มองเห็น) ทั้งการตรวจอุปกรณ์ป้องกัน
    การบรรยายเหตุการณ์ และการระบุลัง · สัญญาอนุญาต NVIDIA Open Model License และเพิ่มเติม Apache-2.0
    *หมายเหตุ:* ณ วันที่จัดทำรายงาน **ยังไม่พบบทความวิชาการเฉพาะของ Cosmos-Reason2**
    เอกสารวิชาการที่ใกล้ที่สุดคือของรุ่นก่อนหน้าตามรายการ [2]

[2] NVIDIA. (2025). *Cosmos-Reason1: From Physical Common Sense To Embodied Reasoning.*
    arXiv:2503.15558. https://arxiv.org/abs/2503.15558
    — บทความของ**รุ่นก่อนหน้า** อธิบายแนวคิดตระกูล Cosmos-Reason คือการให้เหตุผลเชิงกายภาพ
    และการฝึกสี่ขั้น (vision pre-training → SFT → Physical AI SFT → reinforcement learning)
    **ไม่ใช่บทความของรุ่นที่ใช้จริง** แต่เป็นเอกสารวิชาการที่ใกล้ที่สุด ใช้อธิบายที่มาของสถาปัตยกรรม
    และเหตุผลที่เลือกแบบจำลองตระกูลนี้แทนแบบจำลองภาษาและภาพทั่วไป

[3] Anthropic. *Claude Opus* [เอกสารผลิตภัณฑ์]. https://www.anthropic.com/claude/opus
    · เอกสารสำหรับนักพัฒนา: https://platform.claude.com/docs
    — ใช้ในชั้น L4 (วิเคราะห์) สำหรับจับคู่เหตุการณ์เข้ากับกฎความปลอดภัย R1–R10
    ตัดสินระดับความรุนแรง และสรุปภาพรวมขั้นตอนการทำงาน
    รุ่นที่ใช้จริงคือ `anthropic/claude-opus-4.8` · บันทึกไว้ในไฟล์ผลลัพธ์ที่ฟิลด์
    `generated_by.safety_analysis.model` เพื่อให้ตรวจย้อนได้ว่าผลมาจากรุ่นใด

[4] vLLM Project. *vLLM* [ซอฟต์แวร์]. https://github.com/vllm-project/vllm
    — ระบบให้บริการแบบจำลองตามรายการ [1] (เวอร์ชัน 0.25.0) · สัญญาอนุญาต Apache-2.0
    เป็นตัวที่ทำให้แบ่งงานลงการ์ดจอสองใบแบบขนานได้ · แนวคิดเบื้องหลังตามรายการ [6]

[5] Siow, E. *edsr-base* [model card]. Hugging Face.
    https://huggingface.co/eugenesiow/edsr-base
    — **น้ำหนักแบบจำลองขยายภาพที่โครงงานนี้เรียกใช้จริง** (scale = 4) · สัญญาอนุญาต Apache-2.0
    ใช้ขยายภาพเฉพาะส่วนศีรษะก่อนส่งให้แบบจำลองตรวจหน้ากาก ซึ่งทำให้อัตราการตรวจพบ
    เพิ่มจาก 23% เป็น 80% (บทที่ 7 หัวข้อ 7.2) · วิธีการเบื้องหลังตามรายการ [7]

## ทฤษฎีและงานวิจัยที่รองรับข้อความในรายงาน

[6] Kwon, W., Li, Z., Zhuang, S., Sheng, Y., Zheng, L., Yu, C. H., Gonzalez, J. E.,
    Zhang, H., & Stoica, I. (2023). *Efficient Memory Management for Large Language Model
    Serving with PagedAttention.* In Proceedings of the 29th Symposium on Operating Systems
    Principles (SOSP '23). https://doi.org/10.1145/3600006.3613165
    arXiv:2309.06180. https://arxiv.org/abs/2309.06180
    — บทความต้นทางของ vLLM ตามรายการ [4] อธิบายกลไกการรวบคำขอที่เข้ามาพร้อมกันเป็นกลุ่ม
    เพื่อเพิ่มปริมาณงาน ซึ่งเป็น **เหตุผลเชิงระบบที่ทำให้คำตอบไม่คงที่แม้สั่งไม่ให้สุ่ม**
    ตามที่พบในบทที่ 7 หัวข้อ 7.8 และอธิบายไว้ในบทที่ 8 หัวข้อ 8.4

[7] Lim, B., Son, S., Kim, H., Nah, S., & Lee, K. M. (2017). *Enhanced Deep Residual Networks
    for Single Image Super-Resolution.* In IEEE Conference on Computer Vision and Pattern
    Recognition Workshops (CVPRW), pp. 1132–1140.
    https://openaccess.thecvf.com/content_cvpr_2017_workshops/w12/papers/Lim_Enhanced_Deep_Residual_CVPR_2017_paper.pdf
    — วิธีการขยายภาพด้วยแบบจำลอง (EDSR) ซึ่งเป็นเบื้องหลังของน้ำหนักตามรายการ [5]
    อธิบายว่าทำไมการขยายภาพแบบนี้จึงเพิ่มรายละเอียดได้ ต่างจากการยืดภาพธรรมดา

[8] Dosovitskiy, A., Beyer, L., Kolesnikov, A., Weissenborn, D., Zhai, X., Unterthiner, T.,
    Dehghani, M., Minderer, M., Heigold, G., Gelly, S., Uszkoreit, J., & Houlsby, N. (2021).
    *An Image is Worth 16x16 Words: Transformers for Image Recognition at Scale.*
    In International Conference on Learning Representations (ICLR 2021).
    arXiv:2010.11929. https://arxiv.org/abs/2010.11929
    — ที่มาของแนวคิด **หั่นภาพเป็นตาราง (patch) แล้วให้แบบจำลองอ่านเรียงกันเหมือนอ่านคำ**
    ซึ่งเป็นหลักการที่บทที่ 5 หัวข้อ 5.2.2 ใช้อธิบายว่าแบบจำลองไม่ได้ "ดูรูป" แบบที่คนดู
    *หมายเหตุ:* บทความต้นฉบับใช้ตารางขนาด 16×16 พิกเซล ส่วนแบบจำลองที่โครงงานนี้ใช้
    ใช้ตาราง 14×14 แล้วรวมแบบ 2×2 — ต่างกันที่ค่าพารามิเตอร์ แต่เป็นหลักการเดียวกัน

[9] Yuksekgonul, M., Bianchi, F., Kalluri, P., Jurafsky, D., & Zou, J. (2023).
    *When and why vision-language models behave like bags-of-words, and what to do about it?*
    In International Conference on Learning Representations (ICLR 2023).
    arXiv:2210.01936. https://arxiv.org/abs/2210.01936
    — เสนอชุดทดสอบ ARO (Attribution, Relation, Order) มากกว่า 50,000 กรณี และแสดงว่า
    แบบจำลองภาษาและภาพจำนวนมาก **เข้ารหัสภาพเสมือน "ถุงคำ"** คือรู้ว่ามีวัตถุอะไรและมีคุณสมบัติ
    อะไรอยู่ในภาพ แต่ **จับคู่ว่าคุณสมบัติไหนเป็นของวัตถุไหนไม่ได้**

    **เป็นงานที่อธิบายอาการที่พบในโครงงานนี้ได้ตรงที่สุด** — แบบจำลองอ่านป้าย NG/WAIT/GOOD
    ออกทุกป้าย แต่จับคู่ป้ายเข้ากับลังผิดเมื่อลังสองใบอยู่ใกล้กัน 251 พิกเซล (ผิด 66%)
    ขณะที่ลังที่อยู่ห่าง 1,053 พิกเซลไม่เคยผิดเลย ยืนยันว่าเป็น **ข้อจำกัดเชิงโครงสร้าง
    ที่มีรายงานในงานวิจัย ไม่ใช่ความผิดพลาดเฉพาะกรณีหรือปัญหาการอ่านป้าย**
    จึงเป็นเหตุผลรองรับการแก้ด้วยวิธีครอบภาพทีละลัง (บทที่ 7 หัวข้อ 7.4 · บทที่ 8 หัวข้อ 8.2)

## แบบจำลองที่นำมาเปรียบเทียบ

[10] Qwen Team, Alibaba. *Qwen3-VL-8B-Instruct* [model card]. Hugging Face.
     https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct
     — แบบจำลองที่นำมาเทียบตอนเลือกแบบจำลอง (บทที่ 7 หัวข้อ 7.6)
     ผลคือตรวจพบ 62% และ **ตรวจไม่พบเหตุเกือบเกิดอุบัติเหตุ** ขณะที่ Cosmos ตรวจพบ
     ซึ่งเป็นจุดชี้ขาดในการเลือกแบบจำลอง

## เทคนิคที่ทดลองแล้วไม่ได้ใช้ในผลงานสุดท้าย

รายงานกล่าวถึงเทคนิคสองรายการนี้ในบทที่ 5 หัวข้อ 5.3 และบทที่ 9 หัวข้อ 9.4
จึงต้องระบุแหล่งที่มาไว้ **แต่ไม่ได้ใช้ในผลงานที่ส่งมอบ**

[11] Yang, J., Zhang, H., Li, F., Zou, X., Li, C., & Gao, J. (2023). *Set-of-Mark Prompting
     Unleashes Extraordinary Visual Grounding in GPT-4V.* arXiv:2310.11441.
     https://arxiv.org/abs/2310.11441 · โค้ด: https://github.com/microsoft/SoM
     — วิธีติดหมายเลขบนภาพเพื่อช่วยให้แบบจำลองอ้างอิงตำแหน่งได้
     **ทดลองแล้วไม่ได้ใช้** เพราะช่วยเรื่องหน้ากากแต่ทำให้การตรวจถุงมือแย่ลง

[12] Cheng, T., Song, L., Ge, Y., Liu, W., Wang, X., & Shan, Y. (2024). *YOLO-World:
     Real-Time Open-Vocabulary Object Detection.* In IEEE/CVF Conference on Computer Vision
     and Pattern Recognition (CVPR 2024).
     https://openaccess.thecvf.com/content/CVPR2024/html/Cheng_YOLO-World_Real-Time_Open-Vocabulary_Object_Detection_CVPR_2024_paper.html
     — ตัวตรวจจับวัตถุแบบไม่ต้องเทรน **ทดลองแล้วไม่ได้ใช้** เพราะแบบจำลองตรวจอุปกรณ์ป้องกัน
     สำเร็จรูปย้ายมาใช้กับฉากนี้ไม่ได้ และการเทรนใหม่ขัดกับข้อจำกัดของโครงงาน
     ที่ไม่มีชุดข้อมูลติดป้ายกำกับ
