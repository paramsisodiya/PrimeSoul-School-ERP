import io
import os
import logging
from decimal import Decimal
from django.conf import settings
from django.core.exceptions import PermissionDenied

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, KeepTogether
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.graphics.barcode.qr import QrCodeWidget
    from reportlab.graphics.shapes import Drawing
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

from django_school_management.examinations.models import StudentExamResult, StudentMark, ExamSubject

logger = logging.getLogger(__name__)

# Track registered font name
REGISTERED_FONT = 'Helvetica'
REGISTERED_FONT_BOLD = 'Helvetica-Bold'


def init_unicode_fonts():
    """
    Safely registers Unicode / Devanagari TTF fonts if available on the system or in settings.
    Falls back gracefully to Helvetica without throwing errors.
    """
    global REGISTERED_FONT, REGISTERED_FONT_BOLD
    candidate_paths = [
        getattr(settings, 'REPORT_CARD_UNICODE_FONT_PATH', None),
        os.path.join(getattr(settings, 'STATIC_ROOT', ''), 'fonts', 'NotoSans-Regular.ttf'),
        'C:/Windows/Fonts/Arial.ttf',
        '/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    ]
    for p in candidate_paths:
        if p and os.path.exists(p):
            try:
                font_name = 'CustomUnicodeFont'
                pdfmetrics.registerFont(TTFont(font_name, p))
                REGISTERED_FONT = font_name
                REGISTERED_FONT_BOLD = font_name
                logger.info("Registered Report Card Unicode Font from: %s", p)
                break
            except Exception as e:
                logger.debug("Failed registering candidate font %s: %s", p, e)


if REPORTLAB_AVAILABLE:
    init_unicode_fonts()


def render_report_card_pdf_bytes(result: StudentExamResult, verification_base_url: str = "http://127.0.0.1:8000") -> bytes:
    """
    Renders an official, tamper-evident Indian K-12 Student Report Card / Marksheet in PDF format.
    Includes school branding, student profile, subject breakdown, overall metrics, attendance, and verification QR code.
    """
    if not REPORTLAB_AVAILABLE:
        return b"%PDF-1.4 Mock Report Card File (ReportLab Not Available)"

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=32,
        bottomMargin=32
    )

    styles = getSampleStyleSheet()
    
    # Custom styles
    school_title_style = ParagraphStyle(
        'SchoolTitle',
        parent=styles['Heading1'],
        fontName=REGISTERED_FONT_BOLD,
        fontSize=16,
        leading=20,
        alignment=1, # Center
        textColor=colors.HexColor('#0F172A')
    )
    subtitle_style = ParagraphStyle(
        'Subtitle',
        parent=styles['Normal'],
        fontName=REGISTERED_FONT,
        fontSize=8.5,
        leading=11,
        alignment=1,
        textColor=colors.HexColor('#475569')
    )
    doc_header_style = ParagraphStyle(
        'DocHeader',
        parent=styles['Heading2'],
        fontName=REGISTERED_FONT_BOLD,
        fontSize=12,
        leading=15,
        alignment=1,
        textColor=colors.HexColor('#1D4ED8'),
        spaceAfter=6
    )
    cell_style = ParagraphStyle(
        'Cell',
        parent=styles['Normal'],
        fontName=REGISTERED_FONT,
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#1E293B')
    )
    cell_bold_style = ParagraphStyle(
        'CellBold',
        parent=styles['Normal'],
        fontName=REGISTERED_FONT_BOLD,
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#0F172A')
    )
    cell_center_style = ParagraphStyle(
        'CellCenter',
        parent=cell_style,
        alignment=1
    )
    cell_center_bold_style = ParagraphStyle(
        'CellCenterBold',
        parent=cell_bold_style,
        alignment=1
    )

    elements = []

    # 1. School Header
    school = result.school
    elements.append(Paragraph(f"<b>{school.name.upper()}</b>", school_title_style))
    school_sub = school.address or "Affiliated to CBSE / ICSE / State Board"
    elements.append(Paragraph(school_sub, subtitle_style))
    contact_parts = []
    if getattr(school, 'phone', None):
        contact_parts.append(f"Phone: {school.phone}")
    if getattr(school, 'email', None):
        contact_parts.append(f"Email: {school.email}")
    if contact_parts:
        elements.append(Paragraph(" | ".join(contact_parts), subtitle_style))
    elements.append(Spacer(1, 4))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#2563EB'), spaceAfter=8))

    # 2. Document Title
    exam = result.exam
    exam_title = f"OFFICIAL REPORT CARD — {exam.name.upper()} ({exam.academic_year.name})"
    elements.append(Paragraph(f"<b>{exam_title}</b>", doc_header_style))
    elements.append(Spacer(1, 4))

    # 3. Student Profile Info Table
    student = result.student
    enrollment = result.enrollment
    grade_name = exam.grade_level.name if exam.grade_level else "Class"
    sec_name = f" - Section {enrollment.section.name}" if (enrollment and enrollment.section) else (f" - Section {exam.section.name}" if exam.section else "")
    roll_no = getattr(student, 'roll_number', '') or (enrollment.roll_number if enrollment else "N/A")
    adm_no = getattr(student, 'admission_number', '') or str(student.id)
    student_name = f"{student.first_name} {student.last_name}".strip() if getattr(student, 'first_name', '') else getattr(student, 'name', 'Student')

    info_data = [
        [
            Paragraph(f"<b>Student Name:</b> {student_name}", cell_style),
            Paragraph(f"<b>Admission No:</b> {adm_no}", cell_style),
        ],
        [
            Paragraph(f"<b>Class & Section:</b> {grade_name}{sec_name}", cell_style),
            Paragraph(f"<b>Roll Number:</b> {roll_no}", cell_style),
        ],
        [
            Paragraph(f"<b>Academic Session:</b> {exam.academic_year.name}", cell_style),
            Paragraph(f"<b>Date of Evaluation:</b> {result.calculated_at.strftime('%d-%b-%Y') if result.calculated_at else 'N/A'}", cell_style),
        ]
    ]
    info_table = Table(info_data, colWidths=[260, 260])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
        ('PADDING', (0, 0), (-1, -1), 4),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 10))

    # 4. Subject-wise Marks Table
    exam_subjects = list(exam.subjects.filter(is_active=True).select_related('subject').order_by('sequence_order', 'subject__name'))
    marks_map = {m.exam_subject_id: m for m in StudentMark.objects.filter(exam=exam, student=student)}

    table_rows = [
        [
            Paragraph("<b>S.No.</b>", cell_center_bold_style),
            Paragraph("<b>Subject</b>", cell_bold_style),
            Paragraph("<b>Max Marks</b>", cell_center_bold_style),
            Paragraph("<b>Pass Marks</b>", cell_center_bold_style),
            Paragraph("<b>Marks Obtained</b>", cell_center_bold_style),
            Paragraph("<b>Grade</b>", cell_center_bold_style),
            Paragraph("<b>Status</b>", cell_center_bold_style),
        ]
    ]

    for idx, es in enumerate(exam_subjects, 1):
        mark_entry = marks_map.get(es.id)
        if mark_entry and mark_entry.status == StudentMark.STATUS_PRESENT:
            obtained_str = f"{mark_entry.marks_obtained:g}" if mark_entry.marks_obtained is not None else "0"
            grade_str = mark_entry.grade or "—"
            status_str = "PASSED" if mark_entry.is_passed else "FAILED"
            status_color = "#16A34A" if mark_entry.is_passed else "#DC2626"
        elif mark_entry and mark_entry.status == StudentMark.STATUS_ABSENT:
            obtained_str = "ABSENT"
            grade_str = "AB"
            status_str = "ABSENT"
            status_color = "#DC2626"
        else:
            obtained_str = "—"
            grade_str = "—"
            status_str = "PENDING"
            status_color = "#64748B"

        table_rows.append([
            Paragraph(str(idx), cell_center_style),
            Paragraph(es.subject.name, cell_style),
            Paragraph(f"{es.max_marks:g}", cell_center_style),
            Paragraph(f"{es.passing_marks:g}", cell_center_style),
            Paragraph(f"<b>{obtained_str}</b>", cell_center_style),
            Paragraph(grade_str, cell_center_bold_style),
            Paragraph(f"<font color='{status_color}'><b>{status_str}</b></font>", cell_center_style),
        ])

    # Total row
    tot_obtained_str = f"{result.total_marks_obtained:g}"
    tot_max_str = f"{result.total_max_marks:g}"
    table_rows.append([
        "",
        Paragraph("<b>GRAND TOTAL</b>", cell_bold_style),
        Paragraph(f"<b>{tot_max_str}</b>", cell_center_bold_style),
        "",
        Paragraph(f"<b>{tot_obtained_str}</b>", cell_center_bold_style),
        Paragraph(f"<b>{result.overall_grade}</b>", cell_center_bold_style),
        Paragraph(f"<b>{result.get_result_status_display()}</b>", cell_center_bold_style),
    ])

    marks_table = Table(table_rows, colWidths=[35, 175, 60, 60, 75, 55, 60])
    marks_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E2E8F0')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('PADDING', (0, 0), (-1, -1), 4),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#F1F5F9')),
    ]))
    elements.append(marks_table)
    elements.append(Spacer(1, 10))

    # 5. Performance Summary & Attendance Grid
    att_pct_str = f"{result.attendance_percentage}%" if result.attendance_percentage is not None else "N/A"
    rank_str = f"Class Rank #{result.class_rank}" if result.class_rank else "—"
    if result.section_rank:
        rank_str += f" | Section Rank #{result.section_rank}"

    summary_data = [
        [
            Paragraph(f"<b>Percentage:</b> {result.percentage:.2f}%", cell_style),
            Paragraph(f"<b>Overall Grade:</b> {result.overall_grade or '—'}", cell_style),
            Paragraph(f"<b>Result:</b> {result.get_result_status_display()}", cell_style),
        ],
        [
            Paragraph(f"<b>Total Working Days:</b> {result.attendance_working_days}", cell_style),
            Paragraph(f"<b>Days Present:</b> {result.attendance_present_days}", cell_style),
            Paragraph(f"<b>Attendance:</b> {att_pct_str}", cell_style),
        ],
        [
            Paragraph(f"<b>Standing / Rank:</b> {rank_str}", cell_style),
            Paragraph(f"<b>Subjects Passed:</b> {result.subjects_passed} / {len(exam_subjects)}", cell_style),
            Paragraph(f"<b>Verification Ref:</b> {result.verification_code}", cell_style),
        ]
    ]
    summary_table = Table(summary_data, colWidths=[173, 173, 174])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
        ('PADDING', (0, 0), (-1, -1), 4),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 12))

    # 6. Remarks and Verification Section (with QR Code)
    verify_url = f"{verification_base_url.rstrip('/')}/verify/result/{result.verification_code}/"
    qr_drawing = Drawing(65, 65)
    qr_widget = QrCodeWidget(verify_url)
    qr_widget.barWidth = 65
    qr_widget.barHeight = 65
    qr_widget.qrVersion = 1
    qr_drawing.add(qr_widget)

    verify_block = [
        [
            qr_drawing,
            Paragraph(
                f"<b>Tamper-Evident QR Verification</b><br/>"
                f"<font size='7' color='#64748B'>Scan with any smartphone camera to independently verify authenticity.</font><br/>"
                f"<font size='7' color='#2563EB'>{verify_url}</font><br/>"
                f"<font size='7' color='#64748B'>Official Digital Credential • PrimeSoul ERP Security Shield</font>",
                cell_style
            )
        ]
    ]
    verify_table = Table(verify_block, colWidths=[75, 445])
    verify_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F1F5F9')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('PADDING', (0, 0), (-1, -1), 4),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(verify_table)
    elements.append(Spacer(1, 20))

    # 7. Signature Areas
    sig_data = [
        [
            Paragraph("<b>Class Teacher</b><br/><br/><br/>_______________________", ParagraphStyle('Sig1', parent=cell_style, alignment=0)),
            Paragraph("<b>Exam Controller</b><br/><br/><br/>_______________________", ParagraphStyle('Sig2', parent=cell_style, alignment=1)),
            Paragraph("<b>Principal / Head of Institution</b><br/><br/><br/>_______________________", ParagraphStyle('Sig3', parent=cell_style, alignment=2)),
        ]
    ]
    sig_table = Table(sig_data, colWidths=[173, 173, 174])
    sig_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
        ('PADDING', (0, 0), (-1, -1), 2),
    ]))
    elements.append(sig_table)

    doc.build(elements)
    pdf_data = buffer.getvalue()
    buffer.close()
    return pdf_data
