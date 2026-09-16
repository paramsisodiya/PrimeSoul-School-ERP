"""
PrimeSoul School ERP - Phase 17: Advanced Reports & Analytics Selectors
Pure aggregation layer querying live domain models with multi-tenant scoping.
"""
from decimal import Decimal
from typing import Optional, Dict, Any, List
from django.db import models
from django.db.models import Count, Sum, Avg, Max, Min, Q, F, DecimalField, Value, Case, When, IntegerField
from django.db.models.functions import Coalesce
from django.utils import timezone

from django_school_management.tenants.models import School
from django_school_management.students.models import Student
from django_school_management.academics.models import AcademicYear, GradeLevel, Section, SubjectAssignment
from django_school_management.attendance.models import AttendanceRecord
from django_school_management.examinations.models import Exam, StudentExamResult, StudentMark
from django_school_management.fees.models import FeeInvoice, FeeReceipt, PaymentTransaction, InvoiceStatus
from django_school_management.admissions.models import AdmissionSession, AdmissionEnquiry, AdmissionApplication
from django_school_management.transport.models import (
    TransportVehicle, TransportRoute, StudentTransportAssignment, VehicleRouteAssignment
)
from django_school_management.library.models import Book, BookCopy, LibraryIssue, LibraryFine
from django_school_management.hr.models import Employee, Department, PayrollPeriod, EmployeeAttendance, HRDesignation
from django_school_management.inventory.models import (
    InventoryItem, ItemStoreStock, StockMovement,
    Asset, AssetAssignment, AssetMaintenance, Store
)


# ==============================================================================
# 1. SCHOOL EXECUTIVE DASHBOARD (ALL 9 DOMAINS)
# ==============================================================================

def get_executive_dashboard_kpis(school: School) -> Dict[str, Any]:
    """
    Computes high-level KPIs across all ERP functional modules for Principal & Admin.
    Zero fake metrics; all live DB aggregations.
    """
    today = timezone.now().date()

    # 1. Students & Enrollment
    student_stats = Student.objects.filter(school=school).aggregate(
        total_students=Count('id'),
        active_students=Count('id', filter=Q(is_active=True)),
        male_count=Count('id', filter=Q(gender='M', is_active=True)),
        female_count=Count('id', filter=Q(gender='F', is_active=True)),
    )

    # 2. Attendance Today
    att_today_agg = AttendanceRecord.objects.filter(school=school, attendance_date=today).aggregate(
        total_marked=Count('id'),
        present=Count('id', filter=Q(status=AttendanceRecord.STATUS_PRESENT)),
        absent=Count('id', filter=Q(status=AttendanceRecord.STATUS_ABSENT)),
        late=Count('id', filter=Q(status=AttendanceRecord.STATUS_LATE)),
        half_day=Count('id', filter=Q(status=AttendanceRecord.STATUS_HALF_DAY)),
    )
    total_marked = att_today_agg['total_marked'] or 0
    present_count = (att_today_agg['present'] or 0) + (att_today_agg['late'] or 0)
    attendance_pct = round((present_count / total_marked * 100), 1) if total_marked > 0 else Decimal('0.0')

    # 3. Academics
    active_year = (
        AcademicYear.objects.filter(school=school, is_current=True).first()
        or AcademicYear.objects.filter(school=school, status=AcademicYear.STATUS_ACTIVE).first()
    )
    total_classes = GradeLevel.objects.filter(school=school, is_active=True).count()
    total_sections = Section.objects.filter(school=school, is_active=True).count()
    total_teachers = Employee.objects.filter(school=school, status=Employee.STATUS_ACTIVE, designation__category=HRDesignation.CATEGORY_TEACHING).count()
    if total_teachers == 0:
        total_teachers = Employee.objects.filter(school=school, status=Employee.STATUS_ACTIVE).count()

    # 4. Examination
    exam_stats = Exam.objects.filter(school=school).aggregate(
        total_exams=Count('id'),
        published_exams=Count('id', filter=Q(status='PUBLISHED')),
    )
    exam_results_agg = StudentExamResult.objects.filter(school=school).aggregate(
        avg_percentage=Avg('percentage'),
        total_results=Count('id'),
        passed_count=Count('id', filter=Q(result_status=StudentExamResult.RESULT_PASSED)),
    )
    exam_pass_rate = (
        round((exam_results_agg['passed_count'] / exam_results_agg['total_results'] * 100), 1)
        if exam_results_agg['total_results'] and exam_results_agg['total_results'] > 0
        else Decimal('0.0')
    )

    # 5. Finance
    finance_stats = FeeInvoice.objects.filter(school=school).aggregate(
        total_invoiced=Coalesce(Sum('total'), Value(Decimal('0.00'), output_field=DecimalField())),
        total_paid=Coalesce(Sum('paid_amount'), Value(Decimal('0.00'), output_field=DecimalField())),
        total_due=Coalesce(Sum('balance_amount'), Value(Decimal('0.00'), output_field=DecimalField())),
        overdue_invoices=Count('id', filter=Q(status=InvoiceStatus.OVERDUE)),
    )
    invoiced = finance_stats['total_invoiced']
    paid = finance_stats['total_paid']
    collection_rate = round((paid / invoiced * 100), 1) if invoiced > Decimal('0.00') else Decimal('0.0')

    # 6. Admissions
    active_session = AdmissionSession.objects.filter(school=school, active=True).first()
    adm_qs = AdmissionApplication.objects.filter(school=school)
    enq_qs = AdmissionEnquiry.objects.filter(school=school)
    if active_session:
        adm_qs = adm_qs.filter(admission_session=active_session)
        enq_qs = enq_qs.filter(admission_session=active_session)

    adm_stats = adm_qs.aggregate(
        total_apps=Count('id'),
        admitted=Count('id', filter=Q(status=AdmissionApplication.STATUS_ADMITTED)),
        approved=Count('id', filter=Q(status=AdmissionApplication.STATUS_APPROVED)),
    )
    total_enquiries = enq_qs.count()
    admission_conv_rate = (
        round((adm_stats['admitted'] / adm_stats['total_apps'] * 100), 1)
        if adm_stats['total_apps'] > 0
        else Decimal('0.0')
    )

    # 7. Transport
    transport_stats = {
        'total_vehicles': TransportVehicle.objects.filter(school=school, is_active=True).count(),
        'total_routes': TransportRoute.objects.filter(school=school, is_active=True).count(),
        'allocated_students': StudentTransportAssignment.objects.filter(school=school, transport_status=StudentTransportAssignment.STATUS_ACTIVE).count(),
    }

    # 8. Library
    library_stats = {
        'total_books': Book.objects.filter(school=school, is_active=True).count(),
        'total_copies': BookCopy.objects.filter(school=school).count(),
        'active_issues': LibraryIssue.objects.filter(school=school, status=LibraryIssue.STATUS_ISSUED).count(),
        'overdue_books': LibraryIssue.objects.filter(school=school, status=LibraryIssue.STATUS_OVERDUE).count(),
    }

    # 9. HR
    hr_stats = {
        'total_employees': Employee.objects.filter(school=school, status=Employee.STATUS_ACTIVE).count(),
        'present_today': EmployeeAttendance.objects.filter(school=school, attendance_date=today, status=EmployeeAttendance.STATUS_PRESENT).count(),
    }

    # 10. Inventory & Assets
    items_annotated = InventoryItem.objects.filter(school=school, is_active=True).annotate(
        current_stock=Coalesce(Sum('store_stocks__quantity'), Value(Decimal('0.00'), output_field=DecimalField()))
    )
    inv_stats = {
        'total_items': items_annotated.count(),
        'low_stock_count': items_annotated.filter(current_stock__gt=0, current_stock__lte=F('reorder_level')).count(),
        'out_of_stock_count': items_annotated.filter(current_stock__lte=0).count(),
        'total_assets': Asset.objects.filter(school=school).count(),
        'assigned_assets': Asset.objects.filter(school=school, status=Asset.STATUS_ASSIGNED).count(),
        'in_repair_assets': Asset.objects.filter(school=school, status=Asset.STATUS_IN_REPAIR).count(),
    }

    return {
        'student_stats': student_stats,
        'attendance_today': {
            'total_marked': total_marked,
            'present': present_count,
            'absent': att_today_agg['absent'] or 0,
            'attendance_pct': attendance_pct,
        },
        'academics': {
            'active_year': active_year,
            'total_classes': total_classes,
            'total_sections': total_sections,
            'total_teachers': total_teachers,
        },
        'examination': {
            'total_exams': exam_stats['total_exams'],
            'published_exams': exam_stats['published_exams'],
            'avg_percentage': round(exam_results_agg['avg_percentage'] or Decimal('0.0'), 1),
            'pass_rate': exam_pass_rate,
        },
        'finance': {
            'total_invoiced': invoiced,
            'total_paid': paid,
            'total_due': finance_stats['total_due'],
            'overdue_invoices': finance_stats['overdue_invoices'],
            'collection_rate': collection_rate,
        },
        'admissions': {
            'active_session': active_session,
            'total_enquiries': total_enquiries,
            'total_apps': adm_stats['total_apps'],
            'admitted': adm_stats['admitted'],
            'conversion_rate': admission_conv_rate,
        },
        'transport': transport_stats,
        'library': library_stats,
        'hr': hr_stats,
        'inventory': inv_stats,
    }


# ==============================================================================
# 2. FINANCE REPORTS
# ==============================================================================

def get_finance_reports(
    school: School,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    academic_year_id: Optional[int] = None,
    grade_id: Optional[int] = None,
    payment_method: Optional[str] = None,
    status: Optional[str] = None
) -> Dict[str, Any]:
    """Computes detailed fee collections, dues, and transaction registers."""
    invoices_qs = FeeInvoice.objects.filter(school=school).select_related('student', 'academic_year')
    receipts_qs = FeeReceipt.objects.filter(school=school).select_related('student', 'issued_by')

    if academic_year_id:
        invoices_qs = invoices_qs.filter(academic_year_id=academic_year_id)
    if start_date:
        receipts_qs = receipts_qs.filter(receipt_date__gte=start_date)
        invoices_qs = invoices_qs.filter(invoice_date__gte=start_date)
    if end_date:
        receipts_qs = receipts_qs.filter(receipt_date__lte=end_date)
        invoices_qs = invoices_qs.filter(invoice_date__lte=end_date)
    if payment_method:
        receipts_qs = receipts_qs.filter(payment_method=payment_method)
    if status:
        invoices_qs = invoices_qs.filter(status=status)

    totals = invoices_qs.aggregate(
        total_invoiced=Coalesce(Sum('total'), Value(Decimal('0.00'), output_field=DecimalField())),
        total_collected=Coalesce(Sum('paid_amount'), Value(Decimal('0.00'), output_field=DecimalField())),
        total_outstanding=Coalesce(Sum('balance_amount'), Value(Decimal('0.00'), output_field=DecimalField())),
        invoice_count=Count('id')
    )

    # Collection by payment method
    method_breakdown = receipts_qs.values('payment_method').annotate(
        total_amount=Coalesce(Sum('amount'), Value(Decimal('0.00'), output_field=DecimalField())),
        count=Count('id')
    ).order_by('-total_amount')

    # Recent receipts
    receipts_list = receipts_qs.order_by('-receipt_date', '-created_at')[:50]

    return {
        'totals': totals,
        'method_breakdown': list(method_breakdown),
        'receipts_list': receipts_list,
        'invoices_list': invoices_qs.order_by('-invoice_date')[:50],
    }


# ==============================================================================
# 3. ACADEMIC & ENROLLMENT REPORTS
# ==============================================================================

def get_academic_reports(school: School, academic_year_id: Optional[int] = None) -> Dict[str, Any]:
    """Class strength, section enrollment, and teacher allocations."""
    grades = GradeLevel.objects.filter(school=school, is_active=True).prefetch_related('sections')
    
    class_strengths = []
    total_enrollment = 0

    for grade in grades:
        grade_students = Student.objects.filter(school=school, grade_level=grade, is_active=True).count()
        total_enrollment += grade_students
        sections_data = []
        for sec in grade.sections.filter(is_active=True):
            sec_students = Student.objects.filter(school=school, grade_level=grade, section=sec, is_active=True).count()
            sections_data.append({
                'section_id': sec.id,
                'name': sec.name,
                'student_count': sec_students
            })
        class_strengths.append({
            'grade_id': grade.id,
            'name': grade.name,
            'total_students': grade_students,
            'sections': sections_data
        })

    teacher_allocations = (
        SubjectAssignment.objects.filter(school=school, is_active=True)
        .select_related('teacher', 'subject', 'grade_level', 'section')
        .order_by('grade_level__display_order')
    )

    return {
        'total_enrollment': total_enrollment,
        'class_strengths': class_strengths,
        'teacher_allocations': teacher_allocations[:50],
    }


# ==============================================================================
# 4. ATTENDANCE REPORTS
# ==============================================================================

def get_attendance_reports(
    school: School,
    date: Optional[str] = None,
    grade_id: Optional[int] = None,
    section_id: Optional[int] = None
) -> Dict[str, Any]:
    """Daily attendance summary and low attendance student register."""
    if not date:
        date = timezone.now().date()

    att_qs = AttendanceRecord.objects.filter(school=school, attendance_date=date).select_related(
        'student', 'grade_level', 'section'
    )
    if grade_id:
        att_qs = att_qs.filter(grade_level_id=grade_id)
    if section_id:
        att_qs = att_qs.filter(section_id=section_id)

    daily_summary = att_qs.aggregate(
        total=Count('id'),
        present=Count('id', filter=Q(status=AttendanceRecord.STATUS_PRESENT)),
        absent=Count('id', filter=Q(status=AttendanceRecord.STATUS_ABSENT)),
        late=Count('id', filter=Q(status=AttendanceRecord.STATUS_LATE)),
        half_day=Count('id', filter=Q(status=AttendanceRecord.STATUS_HALF_DAY)),
    )

    # Class-wise attendance breakdown
    class_breakdown = (
        att_qs.values('grade_level__name', 'section__name')
        .annotate(
            total=Count('id'),
            present=Count('id', filter=Q(status=AttendanceRecord.STATUS_PRESENT)),
            absent=Count('id', filter=Q(status=AttendanceRecord.STATUS_ABSENT)),
        )
        .order_by('grade_level__name', 'section__name')
    )

    return {
        'date': date,
        'daily_summary': daily_summary,
        'class_breakdown': list(class_breakdown),
        'attendance_records': att_qs.order_by('grade_level__name', 'student__first_name')[:50],
    }


# ==============================================================================
# 5. EXAMINATION REPORTS
# ==============================================================================

def get_examination_reports(school: School, exam_id: Optional[int] = None) -> Dict[str, Any]:
    """Examination performance, pass rate, and subject-wise averages."""
    exams = Exam.objects.filter(school=school).order_by('-start_date')
    selected_exam = Exam.objects.filter(school=school, pk=exam_id).first() if exam_id else exams.first()

    if not selected_exam:
        return {'exams': exams, 'selected_exam': None, 'metrics': {}}

    results_qs = StudentExamResult.objects.filter(exam=selected_exam).select_related('student', 'exam__grade_level', 'exam__section')
    metrics = results_qs.aggregate(
        total_students=Count('id'),
        passed_count=Count('id', filter=Q(result_status=StudentExamResult.RESULT_PASSED)),
        failed_count=Count('id', filter=Q(result_status=StudentExamResult.RESULT_FAILED)),
        avg_percentage=Avg('percentage'),
        highest_percentage=Max('percentage'),
        lowest_percentage=Min('percentage'),
    )

    pass_percentage = (
        round((metrics['passed_count'] / metrics['total_students'] * 100), 1)
        if metrics['total_students'] and metrics['total_students'] > 0
        else Decimal('0.0')
    )

    top_performers = results_qs.order_by('-percentage')[:10]

    return {
        'exams': exams,
        'selected_exam': selected_exam,
        'metrics': metrics,
        'pass_percentage': pass_percentage,
        'top_performers': top_performers,
        'results_list': results_qs.order_by('class_rank', '-percentage')[:50],
    }


# ==============================================================================
# 6. ADMISSIONS ANALYTICS & FUNNEL
# ==============================================================================

def get_admissions_reports(school: School, session_id: Optional[int] = None) -> Dict[str, Any]:
    """Admission funnel: Enquiries -> Applications -> Review -> Interview -> Admitted."""
    sessions = AdmissionSession.objects.filter(school=school).order_by('-created')
    session = AdmissionSession.objects.filter(school=school, pk=session_id).first() if session_id else sessions.first()

    enq_qs = AdmissionEnquiry.objects.filter(school=school)
    apps_qs = AdmissionApplication.objects.filter(school=school)

    if session:
        enq_qs = enq_qs.filter(admission_session=session)
        apps_qs = apps_qs.filter(admission_session=session)

    enquiry_count = enq_qs.count()
    app_pipeline = apps_qs.aggregate(
        total_applications=Count('id'),
        submitted=Count('id', filter=Q(status=AdmissionApplication.STATUS_SUBMITTED)),
        under_review=Count('id', filter=Q(status=AdmissionApplication.STATUS_UNDER_REVIEW)),
        shortlisted=Count('id', filter=Q(status=AdmissionApplication.STATUS_SHORTLISTED)),
        interview=Count('id', filter=Q(status=AdmissionApplication.STATUS_INTERVIEW)),
        approved=Count('id', filter=Q(status=AdmissionApplication.STATUS_APPROVED)),
        admitted=Count('id', filter=Q(status=AdmissionApplication.STATUS_ADMITTED)),
    )

    total_apps = app_pipeline['total_applications']
    admitted = app_pipeline['admitted']
    conversion_rate = round((admitted / total_apps * 100), 1) if total_apps > 0 else Decimal('0.0')

    # Class-wise applications
    class_wise = (
        apps_qs.values('requested_grade__name')
        .annotate(
            total=Count('id'),
            admitted=Count('id', filter=Q(status=AdmissionApplication.STATUS_ADMITTED))
        )
        .order_by('requested_grade__name')
    )

    return {
        'sessions': sessions,
        'selected_session': session,
        'enquiry_count': enquiry_count,
        'app_pipeline': app_pipeline,
        'conversion_rate': conversion_rate,
        'class_wise': list(class_wise),
    }


# ==============================================================================
# 7. TRANSPORT REPORTS
# ==============================================================================

def get_transport_reports(school: School) -> Dict[str, Any]:
    """Vehicle utilization, route capacity, and allocated student rosters."""
    vehicles = TransportVehicle.objects.filter(school=school, is_active=True)
    routes = TransportRoute.objects.filter(school=school, is_active=True).prefetch_related('vehicle_assignments', 'student_transport_assignments')

    routes_summary = []
    total_capacity = 0
    total_allocated = 0

    for r in routes:
        allocated_count = r.student_transport_assignments.filter(transport_status=StudentTransportAssignment.STATUS_ACTIVE).count()
        total_allocated += allocated_count
        assignment = r.vehicle_assignments.filter(is_active=True).select_related('vehicle', 'driver').first()
        cap = assignment.vehicle.capacity if assignment and assignment.vehicle else 0
        total_capacity += cap
        utilization = round((allocated_count / cap * 100), 1) if cap > 0 else Decimal('0.0')
        routes_summary.append({
            'route_id': r.id,
            'name': r.name,
            'vehicle': assignment.vehicle.vehicle_number if assignment and assignment.vehicle else "Unassigned",
            'capacity': cap,
            'allocated': allocated_count,
            'utilization': utilization
        })

    return {
        'vehicles': vehicles,
        'routes_summary': routes_summary,
        'total_capacity': total_capacity,
        'total_allocated': total_allocated,
    }


# ==============================================================================
# 8. LIBRARY REPORTS
# ==============================================================================

def get_library_reports(school: School) -> Dict[str, Any]:
    """Circulation summary, currently issued books, overdue books, and fine collections."""
    issues_qs = LibraryIssue.objects.filter(school=school).select_related('book_copy__book', 'member')
    stats = issues_qs.aggregate(
        total_loans=Count('id'),
        active_issued=Count('id', filter=Q(status=LibraryIssue.STATUS_ISSUED)),
        returned=Count('id', filter=Q(status=LibraryIssue.STATUS_RETURNED)),
        overdue=Count('id', filter=Q(status=LibraryIssue.STATUS_OVERDUE)),
        lost=Count('id', filter=Q(status=LibraryIssue.STATUS_LOST)),
    )

    fines_agg = LibraryFine.objects.filter(school=school).aggregate(
        total_fines=Coalesce(Sum('final_fine'), Value(Decimal('0.00'), output_field=DecimalField())),
        collected_fines=Coalesce(Sum('final_fine', filter=Q(paid=True)), Value(Decimal('0.00'), output_field=DecimalField())),
        pending_fines=Coalesce(Sum('final_fine', filter=Q(paid=False)), Value(Decimal('0.00'), output_field=DecimalField())),
    )

    overdue_list = issues_qs.filter(status=LibraryIssue.STATUS_OVERDUE).order_by('due_date')[:30]

    return {
        'stats': stats,
        'fines': fines_agg,
        'overdue_list': overdue_list,
    }


# ==============================================================================
# 9. HR & PAYROLL REPORTS (PII MASKED)
# ==============================================================================

def get_hr_reports(school: School) -> Dict[str, Any]:
    """
    Department headcount, employee role breakdown, payroll expenditures.
    Enforces sensitive data masking (Bank account numbers & PAN are masked).
    """
    dept_headcounts = (
        Department.objects.filter(school=school)
        .annotate(employee_count=Count('employees', filter=Q(employees__status=Employee.STATUS_ACTIVE)))
        .order_by('-employee_count')
    )

    employees_qs = Employee.objects.filter(school=school, status=Employee.STATUS_ACTIVE).select_related('department', 'designation')

    # Masked employee list for reporting
    safe_employees = []
    for emp in employees_qs[:50]:
        pan_raw = getattr(emp, 'pan_number', '') or ''
        pan_masked = f"{pan_raw[:2]}******{pan_raw[-2:]}" if len(pan_raw) >= 4 else "******"
        
        bank_raw = getattr(emp, 'bank_account_number', '') or ''
        bank_masked = f"******{bank_raw[-4:]}" if len(bank_raw) >= 4 else "******"

        safe_employees.append({
            'employee_id': emp.employee_code,
            'full_name': emp.full_name,
            'department': emp.department.name if emp.department else "Unassigned",
            'designation': emp.designation.name if emp.designation else "Staff",
            'role_type': emp.designation.get_category_display() if emp.designation else "Staff",
            'pan_masked': pan_masked,
            'bank_masked': bank_masked,
            'joining_date': getattr(emp, 'joining_date', None),
        })

    # Payroll period expenditure
    payroll_periods = PayrollPeriod.objects.filter(school=school).order_by('-year', '-month')[:12]

    return {
        'total_employees': employees_qs.count(),
        'dept_headcounts': dept_headcounts,
        'employees_list': safe_employees,
        'payroll_periods': payroll_periods,
    }


# ==============================================================================
# 10. INVENTORY REPORTS
# ==============================================================================

def get_inventory_reports(
    school: School,
    report_type: str = 'current_stock',
    category_id: Optional[int] = None,
    store_id: Optional[int] = None
) -> Dict[str, Any]:
    """Inventory balances, low stock audits, asset register, and maintenance logs."""
    items_qs = InventoryItem.objects.filter(school=school, is_active=True).select_related('category', 'unit')
    assets_qs = Asset.objects.filter(school=school).select_related('category', 'assigned_employee', 'department')
    maint_qs = AssetMaintenance.objects.filter(asset__school=school).select_related('asset', 'created_by')

    if category_id:
        items_qs = items_qs.filter(category_id=category_id)
        assets_qs = assets_qs.filter(category_id=category_id)

    items_annotated = items_qs.annotate(
        current_stock=Coalesce(Sum('store_stocks__quantity'), Value(Decimal('0.00'), output_field=DecimalField()))
    )

    total_valuation = assets_qs.aggregate(
        total=Coalesce(Sum('purchase_cost'), Value(Decimal('0.00'), output_field=DecimalField()))
    )['total']

    return {
        'report_type': report_type,
        'items': items_annotated[:50],
        'low_stock_items': items_annotated.filter(current_stock__gt=0, current_stock__lte=F('reorder_level')),
        'out_of_stock_items': items_annotated.filter(current_stock__lte=0),
        'assets': assets_qs[:50],
        'total_asset_valuation': total_valuation,
        'maintenance_records': maint_qs.order_by('-start_date')[:50],
    }
