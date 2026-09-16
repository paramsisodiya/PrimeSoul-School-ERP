"""
PrimeSoul School ERP - Phase 17: Reports Export Service
Generates Excel-compatible UTF-8 CSVs and branded institutional PDF reports.
"""
import io
import csv
from typing import List, Dict, Any, Optional
from django.http import HttpResponse
from django.utils import timezone

try:
    from reportlab.lib.pagesizes import letter, A4, landscape
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


def export_to_csv(filename: str, headers: List[str], rows: List[List[Any]]) -> HttpResponse:
    """
    Generates UTF-8 encoded CSV with BOM for seamless Indian Excel compatibility.
    """
    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}_{timestamp}.csv"'
    
    # Write UTF-8 BOM so Excel opens Hindi/currency symbols properly
    response.write('\ufeff')
    
    writer = csv.writer(response)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([str(cell) if cell is not None else '' for cell in row])
        
    return response


def export_to_pdf(
    school_name: str,
    report_title: str,
    headers: List[str],
    rows: List[List[Any]],
    filename: str,
    filters_summary: Optional[str] = None,
    is_landscape: bool = False
) -> HttpResponse:
    """
    Generates a clean, branded institutional PDF report.
    """
    if not REPORTLAB_AVAILABLE:
        # Fallback to plain text / mock pdf if reportlab isn't installed
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}.pdf"'
        response.write(b"%PDF-1.4 Mock Report File (ReportLab library not available)")
        return response

    buffer = io.BytesIO()
    pagesize = landscape(A4) if is_landscape else A4
    doc = SimpleDocTemplate(
        buffer,
        pagesize=pagesize,
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30
    )

    styles = getSampleStyleSheet()
    
    header_style = ParagraphStyle(
        'SchoolHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        textColor=colors.HexColor('#1E293B'),
        alignment=1
    )
    
    title_style = ParagraphStyle(
        'ReportTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=14,
        textColor=colors.HexColor('#4F46E5'),
        alignment=1
    )

    meta_style = ParagraphStyle(
        'MetaStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#64748B'),
        alignment=1
    )

    story = []
    
    # 1. School & Title
    story.append(Paragraph(school_name.upper(), header_style))
    story.append(Paragraph(report_title, title_style))
    timestamp_str = timezone.now().strftime("%d %B %Y, %I:%M %p")
    meta_text = f"Generated On: {timestamp_str}"
    if filters_summary:
        meta_text += f" | Filters: {filters_summary}"
    story.append(Paragraph(meta_text, meta_style))
    story.append(Spacer(1, 12))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#E2E8F0'), spaceAfter=10))

    # 2. Table Data
    table_data = [headers]
    for r in rows:
        row_cells = []
        for c in r:
            val_str = str(c) if c is not None else '-'
            # Shorten if extremely long
            if len(val_str) > 60:
                val_str = val_str[:57] + '...'
            row_cells.append(val_str)
        table_data.append(row_cells)

    col_count = len(headers)
    page_width = (pagesize[0] - 60)
    col_width = page_width / max(col_count, 1)

    t = Table(table_data, colWidths=[col_width] * col_count, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4F46E5')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('TOPPADDING', (0, 0), (-1, 0), 6),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
        ('TOPPADDING', (0, 1), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
    ]))
    story.append(t)

    # 3. Footer
    story.append(Spacer(1, 15))
    footer_style = ParagraphStyle(
        'FooterStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7,
        leading=9,
        textColor=colors.HexColor('#94A3B8'),
        alignment=1
    )
    story.append(Paragraph("PrimeSoul School ERP &copy; PrimeSoul Web Solutions &bull; Confidential Institutional Record", footer_style))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}_{timestamp}.pdf"'
    response.write(pdf_bytes)
    return response
