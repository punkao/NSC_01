# เอกสารอ้างอิง

> ทุกรายการเปิดตรวจจากแหล่งต้นทางจริงก่อนอ้างอิง ไม่ได้เขียนจากความจำ
> แยกให้ชัดระหว่าง **บทความวิชาการ** กับ **model card / ซอฟต์แวร์** เพราะบางแบบจำลองที่ใช้
> ยังไม่มีบทความตีพิมพ์ของตัวเอง การอ้างจึงต้องระบุตามความเป็นจริง

## แบบจำลองที่ใช้ในผลงาน

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
    **ไม่ใช่บทความของรุ่นที่ใช้จริง** แต่ใช้อธิบายที่มาของสถาปัตยกรรมและเหตุผลที่เลือกตระกูลนี้

[3] Anthropic. *Claude Opus* [เอกสารผลิตภัณฑ์]. https://www.anthropic.com/claude/opus
    · เอกสารสำหรับนักพัฒนา: https://platform.claude.com/docs
    — ใช้ในชั้น L4 (วิเคราะห์) สำหรับจับคู่เหตุการณ์เข้ากับกฎความปลอดภัย R1–R10
    และสรุปภาพรวมขั้นตอนการทำงาน · รุ่นที่ใช้จริงคือ `anthropic/claude-opus-4.8`
    เรียกผ่านบริการตามรายการ [4] · บันทึกไว้ในไฟล์ผลลัพธ์ที่ฟิลด์ `generated_by.safety_analysis.model`
    เพื่อให้ตรวจย้อนได้ว่าผลมาจากรุ่นใด

[4] OpenRouter. *OpenRouter API* [บริการ]. https://openrouter.ai
    — บริการตัวกลางสำหรับเรียกแบบจำลองภาษาในรายการ [3] · เป็นบริการเชิงพาณิชย์

## แบบจำลองที่นำมาเปรียบเทียบ

[5] Qwen Team, Alibaba. *Qwen3-VL-8B-Instruct* [model card]. Hugging Face.
    https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct
    — แบบจำลองที่นำมาเทียบตอนเลือกแบบจำลอง (บทที่ 7 หัวข้อ 7.6)
    ผลคือตรวจพบ 62% และ **ตรวจไม่พบเหตุเกือบเกิดอุบัติเหตุ** ขณะที่ Cosmos ตรวจพบ
    ซึ่งเป็นจุดชี้ขาดในการเลือก

[6] Qwen Team. (2025). *Qwen3 Technical Report.* arXiv:2505.09388.
    https://arxiv.org/abs/2505.09388
    — เอกสารเทคนิคหลักที่ model card ตามรายการ [5] อ้างถึง

## ทฤษฎีและเทคนิคที่ใช้อธิบายการทำงาน

[7] Dosovitskiy, A., Beyer, L., Kolesnikov, A., Weissenborn, D., Zhai, X., Unterthiner, T.,
    Dehghani, M., Minderer, M., Heigold, G., Gelly, S., Uszkoreit, J., & Houlsby, N. (2021).
    *An Image is Worth 16x16 Words: Transformers for Image Recognition at Scale.*
    In International Conference on Learning Representations (ICLR 2021).
    arXiv:2010.11929. https://arxiv.org/abs/2010.11929
    — ที่มาของแนวคิด **หั่นภาพเป็นตาราง (patch) แล้วให้แบบจำลองอ่านเรียงกันเหมือนอ่านคำ**
    ซึ่งเป็นหลักการที่หัวข้อ 5.2.2 ใช้อธิบายว่าแบบจำลองไม่ได้ "ดูรูป" แบบที่คนดู
    *หมายเหตุ:* บทความต้นฉบับใช้ตารางขนาด 16×16 พิกเซล ส่วนแบบจำลองที่โครงงานนี้ใช้
    ใช้ตาราง 14×14 แล้วรวมแบบ 2×2 — ต่างกันที่ค่าพารามิเตอร์ แต่เป็นหลักการเดียวกัน

[8] Kwon, W., Li, Z., Zhuang, S., Sheng, Y., Zheng, L., Yu, C. H., Gonzalez, J. E.,
    Zhang, H., & Stoica, I. (2023). *Efficient Memory Management for Large Language Model
    Serving with PagedAttention.* In Proceedings of the 29th Symposium on Operating Systems
    Principles (SOSP '23). https://doi.org/10.1145/3600006.3613165
    arXiv:2309.06180. https://arxiv.org/abs/2309.06180
    — ที่มาของ vLLM ซึ่งใช้ให้บริการแบบจำลองในโครงงานนี้ (เวอร์ชัน 0.25.0)
    บทความนี้อธิบายกลไกการรวบคำขอเป็นกลุ่มเพื่อเพิ่มปริมาณงาน ซึ่งเป็น**เหตุผลเชิงระบบ
    ที่ทำให้คำตอบไม่คงที่แม้สั่งไม่ให้สุ่ม** ตามที่พบในบทที่ 7 หัวข้อ 7.8 และบทที่ 8 หัวข้อ 8.4

[9] Lim, B., Son, S., Kim, H., Nah, S., & Lee, K. M. (2017). *Enhanced Deep Residual Networks
    for Single Image Super-Resolution.* In IEEE Conference on Computer Vision and Pattern
    Recognition Workshops (CVPRW), pp. 1132–1140.
    https://openaccess.thecvf.com/content_cvpr_2017_workshops/w12/papers/Lim_Enhanced_Deep_Residual_CVPR_2017_paper.pdf
    — EDSR ซึ่งใช้ขยายภาพศีรษะ 4 เท่าก่อนส่งให้แบบจำลองตรวจหน้ากาก
    เป็นกลไกที่ทำให้อัตราการตรวจพบหน้ากากเพิ่มจาก 23% เป็น 80% (บทที่ 7 หัวข้อ 7.2)

[10] Siow, E. *edsr-base* [model card]. Hugging Face.
     https://huggingface.co/eugenesiow/edsr-base
     — **น้ำหนักแบบจำลอง EDSR ชุดที่โครงงานนี้เรียกใช้จริง** (scale = 4) · สัญญาอนุญาต Apache-2.0
     เรียกผ่านไลบรารีตามรายการ [11]

[11] Siow, E. *super-image* [ไลบรารีซอฟต์แวร์]. https://github.com/eugenesiow/super-image
     — ไลบรารีที่ห่อหุ้มแบบจำลองขยายภาพตามรายการ [10] ให้เรียกใช้ได้ · สัญญาอนุญาต Apache-2.0

## งานวิจัยที่รองรับข้อค้นพบเรื่องการจับคู่ป้ายกับวัตถุ

[12] Yuksekgonul, M., Bianchi, F., Kalluri, P., Jurafsky, D., & Zou, J. (2023).
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
     จึงเป็นเหตุผลรองรับการแก้ด้วยวิธีครอบภาพทีละลาง (บทที่ 7 หัวข้อ 7.4 · บทที่ 8 หัวข้อ 8.2)

## เทคนิคที่ทดลองแล้วไม่ได้ใช้ในผลงานสุดท้าย

การบันทึกสิ่งที่ทดลองแล้วไม่ผ่าน มีประโยชน์เท่ากับการบันทึกสิ่งที่ใช้ เพราะช่วยให้ผู้พัฒนาต่อ
ไม่ต้องเสียเวลาลองซ้ำ (รายละเอียดผลการทดลองอยู่ในบทที่ 9 หัวข้อ 9.4)

[13] Yang, J., Zhang, H., Li, F., Zou, X., Li, C., & Gao, J. (2023). *Set-of-Mark Prompting
     Unleashes Extraordinary Visual Grounding in GPT-4V.* arXiv:2310.11441.
     https://arxiv.org/abs/2310.11441 · โค้ด: https://github.com/microsoft/SoM
     — วิธีติดหมายเลขบนภาพเพื่อช่วยให้แบบจำลองอ้างอิงตำแหน่งได้
     **ทดลองแล้วไม่ได้ใช้** เพราะช่วยเรื่องหน้ากากแต่ทำให้การตรวจถุงมือแย่ลง

[14] Liu, S., Zeng, Z., Ren, T., Li, F., Zhang, H., Yang, J., Li, C., Yang, J., Su, H.,
     Zhu, J., & Zhang, L. (2023). *Grounding DINO: Marrying DINO with Grounded Pre-Training
     for Open-Set Object Detection.* arXiv:2303.05499. https://arxiv.org/abs/2303.05499
     — ตัวตรวจจับวัตถุแบบไม่ต้องเทรนที่รับคำสั่งเป็นข้อความ
     **ทดลองใช้ชี้ตำแหน่งวัตถุแล้วไม่ได้ใช้ในผลงานสุดท้าย**

[15] Cheng, T., Song, L., Ge, Y., Liu, W., Wang, X., & Shan, Y. (2024). *YOLO-World:
     Real-Time Open-Vocabulary Object Detection.* In IEEE/CVF Conference on Computer Vision
     and Pattern Recognition (CVPR 2024).
     https://openaccess.thecvf.com/content/CVPR2024/html/Cheng_YOLO-World_Real-Time_Open-Vocabulary_Object_Detection_CVPR_2024_paper.html
     — **ทดลองแล้วไม่ได้ใช้** เพราะแบบจำลองตรวจอุปกรณ์ป้องกันสำเร็จรูปย้ายมาใช้กับฉากนี้ไม่ได้
     และการเทรนใหม่ขัดกับข้อจำกัดของโครงงานที่ไม่มีชุดข้อมูลติดป้ายกำกับ

## ซอฟต์แวร์และเครื่องมือพื้นฐาน

[16] vLLM Project. *vLLM* [ซอฟต์แวร์]. https://github.com/vllm-project/vllm
     — ระบบให้บริการแบบจำลอง (เวอร์ชัน 0.25.0) · สัญญาอนุญาต Apache-2.0 · แนวคิดเบื้องหลังตามรายการ [8]

[17] PyTorch Foundation. *PyTorch* [ซอฟต์แวร์]. https://github.com/pytorch/pytorch
     — รากฐานการคำนวณของ vLLM (เวอร์ชัน 2.11.0+cu130) · สัญญาอนุญาตแบบ BSD

[18] FFmpeg. *FFmpeg* [ซอฟต์แวร์]. https://ffmpeg.org
     — ใช้ตัดเฟรมจากวิดีโอ · **หมายเหตุสำคัญ:** โครงงานนี้ใช้สองวิธีตัดเฟรมที่ให้ผลต่างกัน
     คือ `-ss <t>` (สำหรับเฉลยอุปกรณ์ป้องกัน) และ `-vf fps=1 -start_number 0`
     (สำหรับคำบรรยายและการระบุลัง) ซึ่งได้เฟรมคนละจังหวะกัน และเคยเป็นสาเหตุให้สรุปผลผิด
     (บทที่ 8 หัวข้อ 8.6)

[19] Python Imaging Library (Pillow). *Pillow* [ซอฟต์แวร์]. https://python-pillow.org
     — ใช้ครอบภาพ ขยายภาพ และประกอบภาพสำหรับตรวจสอบเฉลย

[20] Ultralytics. *Ultralytics YOLO* [ซอฟต์แวร์]. https://github.com/ultralytics/ultralytics
     — ใช้ทดลองตัวตรวจจับอุปกรณ์ป้องกันสำเร็จรูปตามรายการ [15] · **ไม่ได้ใช้ในผลงานสุดท้าย**

[21] Vast.ai. *Vast.ai* [บริการ]. https://vast.ai
     — บริการเช่าเครื่องที่มีการ์ดจอรายชั่วโมง ใช้รันและวัดผลทั้งหมด
     ข้อควรระวังที่พบจากการใช้บริการนี้อยู่ในบทที่ 8 หัวข้อ 8.5

[22] Hugging Face. *Hugging Face Hub* [บริการ]. https://huggingface.co
     — แหล่งดาวน์โหลดน้ำหนักแบบจำลองตามรายการ [1], [5] และ [10]
