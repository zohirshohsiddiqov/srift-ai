import os
import docx
from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from google import genai
from google.genai import types
import os

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

client = genai.Client(api_key=GEMINI_API_KEY)


def check_spelling_and_style(text: str) -> str:
    """Gemini API orqali matn sofligi va imlo xatolarini tahlil qilish."""
    prompt = (
        "Siz o'zbek tili mutaxassisisiz. Berilgan matnni tahlil qiling:\n"
        "1. Imlo va grammatik xatolarni tuzatib, to'g'ri variantini ko'rsating.\n"
        "2. Matndagi ajnabiy/jargon so'zlarni va ularning o'zbekcha muqobillarini ajratib ko'rsating.\n"
        "3. Matn sofligi va o'qishliylik darajasiga 100 ballik shkalada baho bering.\n\n"
        f"Matn:\n{text}"
    )

    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.2),
    )
    return response.text


def convert_to_new_alphabet(text: str) -> str:
    """Matnni Yangi O'zbek Alifbosiga (Ş, Ç, Ġ, Ō) o'girish va o'zgarishlarni tushuntirish."""
    prompt = (
        "Berilgan o'zbekcha matnni YANGI LOTIN ALIFBOSIGA (Ş ş, Ç ç, Ġ ġ, Ō ō harflari qo'llanilgan holda) "
        "to'g'ri va xatosiz o'girib bering. Javobda:\n"
        "1. 🔄 **Yangi alifbodagi matn:** (to'liq variant)\n"
        "2. 💡 **O'zgargan harflar va qoidalar:** (Aynan qaysi so'zlar yangi imloga ko'ra o'zgargani)\n\n"
        f"Matn:\n{text}"
    )

    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.1),
    )
    return response.text


def process_docx_file(input_path: str, output_path: str) -> None:
    """Word (.docx) hujjatdagi matnlarni yagona so'rov bilan yangi alifboga o'girish."""
    doc = docx.Document(input_path)
    paragraphs_to_process = [p for p in doc.paragraphs if p.text.strip()]

    if not paragraphs_to_process:
        doc.save(output_path)
        return

    # Barcha abzaslarni yagona matnga birlashtiramiz (API 429 limitidan o'tmaslik uchun)
    combined_text = "\n---PARAGRAPH_BREAK---\n".join([p.text for p in paragraphs_to_process])

    prompt = (
        "Quyidagi matn abzaslarga bo'lingan. Har bir abzasni YANGI O'ZBEK LOTIN ALIFBOSIGA (Ş, Ç, Ġ, Ō) o'girib ber.\n"
        "ABZASLAR ORASIDAGI '---PARAGRAPH_BREAK---' AJRATUVCHISINI O'ZGARTIRMA VA O'CHIRMA!\n\n"
        f"{combined_text}"
    )

    response = client.models.generate_content(
        model="gemini-3.6-flash", contents=prompt
    )

    translated_paragraphs = response.text.split("---PARAGRAPH_BREAK---")

    for p, translated_text in zip(paragraphs_to_process, translated_paragraphs):
        p.text = translated_text.strip()

    doc.save(output_path)


def process_txt_file(input_path: str, output_path: str) -> None:
    """TXT matnli faylni o'qib, yangi alifboda saqlash."""
    with open(input_path, "r", encoding="utf-8") as f:
        text = f.read()

    prompt = f"Ushbu matnni to'liq YANGI O'ZBEK LOTIN ALIFBOSIGA (Ş, Ç, Ġ, Ō) o'girib ber, ortiqcha izoh yozma:\n{text}"
    response = client.models.generate_content(
        model="gemini-3.6-flash", contents=prompt
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(response.text)


def process_pdf_file(input_path: str, output_path: str) -> None:
    """PDF fayldagi matnlarni ajratib, yangi alifboga o'girib saqlash."""
    reader = PdfReader(input_path)
    full_text = ""
    for page in reader.pages:
        extracted = page.extract_text()
        if extracted:
            full_text += extracted + "\n"

    prompt = f"Ushbu PDF matnini to'liqligicha YANGI O'ZBEK LOTIN ALIFBOSIGA (Ş, Ç, Ġ, Ō) o'girib ber, ortiqcha izoh yozma:\n{full_text}"
    response = client.models.generate_content(
        model="gemini-3.6-flash", contents=prompt
    )

    # Shrift o'rnatish
    font_path = "C:\\Windows\\Fonts\\arial.ttf"
    if os.path.exists(font_path):
        pdfmetrics.registerFont(TTFont('ArialUz', font_path))
        main_font = 'ArialUz'
    else:
        main_font = 'Helvetica'

    doc = SimpleDocTemplate(output_path, pagesize=A4)
    styles = getSampleStyleSheet()

    body_style = ParagraphStyle(
        'PdfBody',
        parent=styles['Normal'],
        fontName=main_font,
        fontSize=10,
        leading=14
    )

    story = [
        Paragraph("<b>YANGI ALIFBODAGI HUJJAT</b>", body_style),
        Spacer(1, 15),
        Paragraph(response.text.replace('\n', '<br/>'), body_style)
    ]
    doc.build(story)


def generate_infographic_pdf(output_path: str) -> None:
    """ReportLab orqali Yangi Alifbo PDF plakatini Unicode (Arial) bilan shakllantirish."""

    font_path = "C:\\Windows\\Fonts\\arial.ttf"
    font_bold_path = "C:\\Windows\\Fonts\\arialbd.ttf"

    if os.path.exists(font_path) and os.path.exists(font_bold_path):
        pdfmetrics.registerFont(TTFont('ArialUz', font_path))
        pdfmetrics.registerFont(TTFont('ArialUz-Bold', font_bold_path))
        main_font = 'ArialUz'
        bold_font = 'ArialUz-Bold'
    else:
        main_font = 'Helvetica'
        bold_font = 'Helvetica-Bold'

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30
    )
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontName=bold_font,
        fontSize=20,
        textColor=colors.HexColor('#0284c7'),
        alignment=1,
        spaceAfter=8
    )

    subtitle_style = ParagraphStyle(
        'SubTitleStyle',
        parent=styles['Normal'],
        fontName=main_font,
        fontSize=10,
        textColor=colors.HexColor('#0369a1'),
        alignment=1,
        spaceAfter=20
    )

    cell_style = ParagraphStyle(
        'CellStyle',
        parent=styles['Normal'],
        fontName=main_font,
        fontSize=10,
        leading=14
    )

    header_cell_style = ParagraphStyle(
        'HeaderCellStyle',
        parent=styles['Normal'],
        fontName=bold_font,
        fontSize=10,
        textColor=colors.white
    )

    story = []
    story.append(Paragraph("YANGI O'ZBEK ALIFBOSI QAIDALARI", title_style))
    story.append(Paragraph("Jonajon o'zbek tilim tanlovi maxsus qo'llanmasi | Raqamli Ekotizim", subtitle_style))
    story.append(Spacer(1, 10))

    data = [
        [
            Paragraph("Yangi Harf", header_cell_style),
            Paragraph("Eski Ko'rinishi", header_cell_style),
            Paragraph("Misollar (Yangi Imlo)", header_cell_style),
            Paragraph("Qoida Izohi", header_cell_style)
        ],
        [
            Paragraph("<b><font size='12' color='#0284c7'>Ş ş</font></b>", cell_style),
            Paragraph("Sh sh", cell_style),
            Paragraph("şahar, nişon, şadlik", cell_style),
            Paragraph("Pastida ilmog'i bor harf", cell_style)
        ],
        [
            Paragraph("<b><font size='12' color='#0284c7'>Ç ç</font></b>", cell_style),
            Paragraph("Ch ch", cell_style),
            Paragraph("çaqaloq, çoy, içimlik", cell_style),
            Paragraph("'Ch' uchun yaxlit harf", cell_style)
        ],
        [
            Paragraph("<b><font size='12' color='#0284c7'>Ġ ġ</font></b>", cell_style),
            Paragraph("G' g'", cell_style),
            Paragraph("baġir, ġallakor, daftarg'a", cell_style),
            Paragraph("Ustida nuqtasi bor harf", cell_style)
        ],
        [
            Paragraph("<b><font size='12' color='#0284c7'>Ō ō</font></b>", cell_style),
            Paragraph("O' o'", cell_style),
            Paragraph("ōzbek, ōqituvçi, ōrmon", cell_style),
            Paragraph("Ustida chizig'i bor harf", cell_style)
        ],
    ]

    table = Table(data, colWidths=[80, 100, 180, 170])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f172a')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    ]))

    story.append(table)
    story.append(Spacer(1, 25))

    info_title = ParagraphStyle(
        'InfoTitle',
        parent=styles['Heading2'],
        fontName=bold_font,
        fontSize=12,
        textColor=colors.HexColor('#0284c7'),
        spaceAfter=8
    )
    info_body = ParagraphStyle(
        'InfoBody',
        parent=styles['Normal'],
        fontName=main_font,
        fontSize=9.5,
        leading=15
    )

    story.append(Paragraph("💡 Asosiy Afzalliklar va Qulayliklar:", info_title))
    story.append(Paragraph(
        "• <b>Yaxlitlik:</b> Sh va Ch birikmalari o'rniga bitta belgi ishlatilishi matnni 10-15% ga qisqartiradi.<br/>"
        "• <b>Texnik qulaylik:</b> Tutuq belgilari bilan bog'liq dasturlash va qidiruv tizimidagi chalkashliklar to'liq bartaraf etiladi.<br/>"
        "• <b>Xalqaro standart:</b> Klaviatura va matnli ishlov berishda jahon standartlariga mos keladi.",
        info_body
    ))

    doc.build(story)