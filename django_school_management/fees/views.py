import datetime
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.db.models import Q, Sum, Count

from django_school_management.tenants.models import School
from django_school_management.academics.models import AcademicYear, GradeLevel, Section
from django_school_management.students.models import Student
from django_school_management.fees.models import (
    FeeHead, FeeStructure, FeeStructureItem, FeeConcession,
    StudentFeeAssignment, FeeInstallment, FeeInvoice, PaymentTransaction,
    FeeReceipt, FeeHeadCategory, FeeFrequency, ConcessionType,
    PaymentGateway, PaymentStatus, ChequeClearanceStatus, InvoiceStatus,
    InstallmentStatus
)
from django_school_management.fees.services.installment_service import generate_student_installments
from django_school_management.fees.services.invoice_service import create_fee_invoice, cancel_fee_invoice
from django_school_management.fees.services.payment_service import (
    record_offline_payment, process_cheque_clearance, process_cheque_bounce
)
from django_school_management.fees.services.receipt_service import (
    generate_fee_receipt, render_receipt_pdf_bytes, generate_receipt_qr_code_payload
)
from django_school_management.fees.selectors.dashboard_selectors import get_fee_dashboard_summary


def get_user_school(user):
    """Safely extracts tenant school for the current user."""
    if user.is_authenticated and hasattr(user, 'school') and user.school:
        return user.school
    # Fallback to active school in system if superuser
    if user.is_superuser:
        return School.objects.filter(is_active=True).first()
    return None


from django.core.exceptions import PermissionDenied

def user_has_fee_permission(user, allowed_roles):
    """Verifies user belongs to authorized role or is superuser."""
    if not user.is_authenticated:
        return False
    user_role = getattr(user, 'role', None) or getattr(user, 'requested_role', '')
    if user.is_superuser or user_role in ['admin', 'SCHOOL_ADMIN', 'PLATFORM_SUPER_ADMIN']:
        return True
    return user_role in allowed_roles


# ─────────────────────────────────────────────────────────────
# 1. FEE DASHBOARD
# ─────────────────────────────────────────────────────────────

@login_required
def fee_dashboard_view(request):
    if not user_has_fee_permission(request.user, ['SCHOOL_ADMIN', 'ACCOUNTANT', 'PRINCIPAL', 'RECEPTIONIST']):
        raise PermissionDenied("Access denied. Insufficient permissions.")

    school = get_user_school(request.user)
    if not school:
        messages.error(request, "No school tenant associated with your account.")
        return redirect('index_view')

    active_ay = AcademicYear.objects.filter(school=school, is_current=True).first() or AcademicYear.objects.filter(school=school).first()
    ay_id = request.GET.get('academic_year')
    if ay_id:
        selected_ay = AcademicYear.objects.filter(school=school, pk=ay_id).first() or active_ay
    else:
        selected_ay = active_ay

    summary = get_fee_dashboard_summary(school=school, academic_year=selected_ay)
    academic_years = AcademicYear.objects.filter(school=school)

    # Recent Transactions
    recent_payments = (
        PaymentTransaction.objects.filter(school=school)
        .select_related('student', 'invoice')
        .order_by('-created_at')[:8]
    )

    # Recent Invoices
    recent_invoices = (
        FeeInvoice.objects.filter(school=school)
        .select_related('student')
        .order_by('-created_at')[:6]
    )

    context = {
        "school": school,
        "selected_ay": selected_ay,
        "academic_years": academic_years,
        "summary": summary,
        "recent_payments": recent_payments,
        "recent_invoices": recent_invoices,
    }
    return render(request, "fees/dashboard.html", context)


# ─────────────────────────────────────────────────────────────
# 2. FEE HEADS
# ─────────────────────────────────────────────────────────────

@login_required
def fee_heads_view(request):
    school = get_user_school(request.user)
    if not school:
        messages.error(request, "No school tenant associated.")
        return redirect('index_view')

    if not user_has_fee_permission(request.user, ['SCHOOL_ADMIN', 'ACCOUNTANT', 'PRINCIPAL']):
        messages.error(request, "Access denied. Insufficient permissions.")
        return redirect('index_view')

    # Handle POST Actions (Create / Edit / Delete)
    if request.method == "POST":
        action = request.POST.get('action')
        if action == 'create':
            name = request.POST.get('name', '').strip()
            code = request.POST.get('code', '').strip().upper()
            category = request.POST.get('category', FeeHeadCategory.TUITION)
            is_recurring = request.POST.get('is_recurring') == '1'
            description = request.POST.get('description', '').strip()

            if not name or not code:
                messages.error(request, "Fee Head name and code are required.")
            elif FeeHead.objects.filter(school=school, code=code).exists():
                messages.error(request, f"Fee Head code '{code}' already exists.")
            else:
                FeeHead.objects.create(
                    school=school,
                    name=name,
                    code=code,
                    category=category,
                    is_recurring=is_recurring,
                    description=description,
                    is_active=True
                )
                messages.success(request, f"Fee Head '{name}' created successfully.")
            return redirect('fees:fee_heads')

        elif action == 'edit':
            head_id = request.POST.get('head_id')
            head = get_object_or_404(FeeHead, school=school, pk=head_id)
            head.name = request.POST.get('name', head.name).strip()
            head.category = request.POST.get('category', head.category)
            head.is_recurring = request.POST.get('is_recurring') == '1'
            head.description = request.POST.get('description', '').strip()
            head.is_active = request.POST.get('is_active') == '1'
            head.save()
            messages.success(request, f"Fee Head '{head.name}' updated successfully.")
            return redirect('fees:fee_heads')

        elif action == 'delete':
            head_id = request.POST.get('head_id')
            head = get_object_or_404(FeeHead, school=school, pk=head_id)
            head_name = head.name
            head.delete()
            messages.success(request, f"Fee Head '{head_name}' deleted.")
            return redirect('fees:fee_heads')

    # Filters & Search
    query = request.GET.get('q', '').strip()
    category_filter = request.GET.get('category', '')

    heads_qs = FeeHead.objects.filter(school=school)
    if query:
        heads_qs = heads_qs.filter(Q(name__icontains=query) | Q(code__icontains=query))
    if category_filter:
        heads_qs = heads_qs.filter(category=category_filter)

    paginator = Paginator(heads_qs.order_by('category', 'name'), 15)
    page_number = request.GET.get('page')
    fee_heads = paginator.get_page(page_number)

    context = {
        "school": school,
        "fee_heads": fee_heads,
        "categories": FeeHeadCategory.choices,
        "query": query,
        "category_filter": category_filter,
    }
    return render(request, "fees/fee_heads.html", context)


# ─────────────────────────────────────────────────────────────
# 3. FEE STRUCTURES
# ─────────────────────────────────────────────────────────────

@login_required
def fee_structures_view(request):
    school = get_user_school(request.user)
    if not school:
        messages.error(request, "No school tenant associated.")
        return redirect('index_view')

    if not user_has_fee_permission(request.user, ['SCHOOL_ADMIN', 'ACCOUNTANT', 'PRINCIPAL']):
        messages.error(request, "Access denied. Insufficient permissions.")
        return redirect('index_view')

    academic_years = AcademicYear.objects.filter(school=school)
    grade_levels = GradeLevel.objects.filter(school=school)
    fee_heads = FeeHead.objects.filter(school=school, is_active=True)

    if request.method == "POST":
        action = request.POST.get('action')
        if action == 'create':
            name = request.POST.get('name', '').strip()
            ay_id = request.POST.get('academic_year')
            gl_id = request.POST.get('grade_level')
            freq = request.POST.get('frequency', FeeFrequency.QUARTERLY)
            eff_from = request.POST.get('effective_from') or timezone.now().date()
            eff_to = request.POST.get('effective_to') or (timezone.now().date() + datetime.timedelta(days=365))

            ay = get_object_or_404(AcademicYear, school=school, pk=ay_id)
            gl = get_object_or_404(GradeLevel, school=school, pk=gl_id)

            structure = FeeStructure.objects.create(
                school=school,
                name=name,
                academic_year=ay,
                grade_level=gl,
                frequency=freq,
                effective_from=eff_from,
                effective_to=eff_to,
                is_active=True
            )

            # Create line items
            for fh in fee_heads:
                amount_str = request.POST.get(f'head_amount_{fh.id}', '').strip()
                if amount_str:
                    try:
                        amt = Decimal(amount_str)
                        if amt > 0:
                            FeeStructureItem.objects.create(
                                fee_structure=structure,
                                fee_head=fh,
                                amount=amt,
                                due_day=10
                            )
                    except Exception:
                        pass

            messages.success(request, f"Fee Structure '{name}' created with items.")
            return redirect('fees:fee_structures')

        elif action == 'delete':
            struct_id = request.POST.get('structure_id')
            structure = get_object_or_404(FeeStructure, school=school, pk=struct_id)
            structure.delete()
            messages.success(request, "Fee Structure removed.")
            return redirect('fees:fee_structures')

    # Filters
    ay_filter = request.GET.get('academic_year')
    gl_filter = request.GET.get('grade_level')

    structs_qs = FeeStructure.objects.filter(school=school).select_related('academic_year', 'grade_level').prefetch_related('items__fee_head')
    if ay_filter:
        structs_qs = structs_qs.filter(academic_year_id=ay_filter)
    if gl_filter:
        structs_qs = structs_qs.filter(grade_level_id=gl_filter)

    structures = structs_qs.order_by('grade_level__display_order', 'name')

    context = {
        "school": school,
        "structures": structures,
        "academic_years": academic_years,
        "grade_levels": grade_levels,
        "fee_heads": fee_heads,
        "frequencies": FeeFrequency.choices,
        "ay_filter": ay_filter,
        "gl_filter": gl_filter,
    }
    return render(request, "fees/fee_structures.html", context)


# ─────────────────────────────────────────────────────────────
# 4. STUDENT FEES ASSIGNMENT & BULK GENERATION
# ─────────────────────────────────────────────────────────────

@login_required
def student_fees_view(request):
    school = get_user_school(request.user)
    if not school:
        messages.error(request, "No school tenant associated.")
        return redirect('index_view')

    if not user_has_fee_permission(request.user, ['SCHOOL_ADMIN', 'ACCOUNTANT', 'PRINCIPAL']):
        messages.error(request, "Access denied. Insufficient permissions.")
        return redirect('index_view')

    academic_years = AcademicYear.objects.filter(school=school)
    grade_levels = GradeLevel.objects.filter(school=school)
    fee_structures = FeeStructure.objects.filter(school=school, is_active=True)
    concessions = FeeConcession.objects.filter(school=school, is_active=True, is_approved=True)

    if request.method == "POST":
        action = request.POST.get('action')
        if action in ['assign_and_generate', 'generate_installments']:
            assignment_id = request.POST.get('assignment_id')
            if assignment_id:
                assignment = get_object_or_404(StudentFeeAssignment, pk=assignment_id)
                student = assignment.student
                structure = assignment.fee_structure
                ay = assignment.academic_year
                concession = assignment.concession
                custom_conc = assignment.custom_concession_amount
            else:
                student_id = request.POST.get('student_id')
                structure_id = request.POST.get('fee_structure_id')
                ay_id = request.POST.get('academic_year_id')
                concession_id = request.POST.get('concession_id') or None
                custom_conc_str = request.POST.get('custom_concession', '0')

                student = get_object_or_404(Student, school=school, pk=student_id)
                structure = get_object_or_404(FeeStructure, school=school, pk=structure_id)
                ay = get_object_or_404(AcademicYear, school=school, pk=ay_id)
                concession = FeeConcession.objects.filter(school=school, pk=concession_id).first() if concession_id else None

                try:
                    custom_conc = Decimal(custom_conc_str or '0')
                except Exception:
                    custom_conc = Decimal('0.00')

                StudentFeeAssignment.objects.update_or_create(
                    student=student,
                    academic_year=ay,
                    fee_structure=structure,
                    defaults={
                        "concession": concession,
                        "custom_concession_amount": custom_conc,
                        "status": 'ACTIVE',
                    }
                )

            installments = generate_student_installments(
                student=student,
                fee_structure=structure,
                academic_year=ay,
                concession=concession,
                custom_concession=custom_conc,
                actor=request.user
            )

            messages.success(request, f"Generated {len(installments)} installments for {student.first_name} {student.last_name} ({structure.name}).")
            return redirect('fees:student_fees')

    query = request.GET.get('q', '').strip()
    gl_filter = request.GET.get('grade_level')

    students_qs = Student.objects.filter(school=school, is_active=True).select_related('grade_level', 'section', 'academic_year').prefetch_related('fee_assignments__fee_structure', 'fee_installments')
    if query:
        students_qs = students_qs.filter(
            Q(first_name__icontains=query) | Q(last_name__icontains=query) |
            Q(admission_number__icontains=query) | Q(roll_number__icontains=query)
        )
    if gl_filter:
        students_qs = students_qs.filter(grade_level_id=gl_filter)

    paginator = Paginator(students_qs.order_by('grade_level__display_order', 'roll_number', 'first_name'), 15)
    page_number = request.GET.get('page')
    students = paginator.get_page(page_number)

    context = {
        "school": school,
        "students": students,
        "academic_years": academic_years,
        "grade_levels": grade_levels,
        "fee_structures": fee_structures,
        "concessions": concessions,
        "query": query,
        "gl_filter": gl_filter,
    }
    return render(request, "fees/student_fees.html", context)


# ─────────────────────────────────────────────────────────────
# 5. INSTALLMENTS
# ─────────────────────────────────────────────────────────────

@login_required
def installments_view(request):
    school = get_user_school(request.user)
    if not school:
        messages.error(request, "No school tenant associated.")
        return redirect('index_view')

    installments_qs = FeeInstallment.objects.filter(student__school=school).select_related('student', 'academic_year', 'fee_structure')

    # RBAC Scoping
    if request.user.requested_role in ['STUDENT']:
        installments_qs = installments_qs.filter(student__user=request.user)
    elif request.user.requested_role in ['PARENT']:
        installments_qs = installments_qs.filter(student__guardian_relationships__guardian__user=request.user)

    status_filter = request.GET.get('status', '')
    query = request.GET.get('q', '').strip()

    if status_filter:
        installments_qs = installments_qs.filter(status=status_filter)
    if query:
        installments_qs = installments_qs.filter(
            Q(student__first_name__icontains=query) | Q(student__last_name__icontains=query) |
            Q(student__admission_number__icontains=query) | Q(installment_name__icontains=query)
        )

    paginator = Paginator(installments_qs.order_by('due_date', 'student__first_name'), 20)
    page_number = request.GET.get('page')
    installments = paginator.get_page(page_number)

    context = {
        "school": school,
        "installments": installments,
        "statuses": InstallmentStatus.choices,
        "status_filter": status_filter,
        "query": query,
    }
    return render(request, "fees/installments.html", context)


# ─────────────────────────────────────────────────────────────
# 6. CONCESSIONS & SCHOLARSHIPS
# ─────────────────────────────────────────────────────────────

@login_required
def concessions_view(request):
    school = get_user_school(request.user)
    if not school:
        messages.error(request, "No school tenant associated.")
        return redirect('index_view')

    if not user_has_fee_permission(request.user, ['SCHOOL_ADMIN', 'ACCOUNTANT', 'PRINCIPAL']):
        messages.error(request, "Access denied.")
        return redirect('index_view')

    fee_heads = FeeHead.objects.filter(school=school, is_active=True)

    if request.method == "POST":
        action = request.POST.get('action')
        if action == 'create':
            name = request.POST.get('name', '').strip()
            ctype = request.POST.get('concession_type', ConcessionType.PERCENTAGE)
            val = Decimal(request.POST.get('value', '0'))
            max_amt_str = request.POST.get('maximum_amount', '').strip()
            max_amt = Decimal(max_amt_str) if max_amt_str else None
            req_app = request.POST.get('approval_required') == '1'
            selected_heads = request.POST.getlist('applicable_heads')

            concession = FeeConcession.objects.create(
                school=school,
                name=name,
                concession_type=ctype,
                value=val,
                maximum_amount=max_amt,
                approval_required=req_app,
                is_approved=not req_app or request.user.requested_role in ['PRINCIPAL', 'SCHOOL_ADMIN', 'admin'],
                approved_by=request.user if (not req_app or request.user.requested_role in ['PRINCIPAL', 'SCHOOL_ADMIN', 'admin']) else None,
                is_active=True
            )
            if selected_heads:
                concession.applicable_fee_heads.set(selected_heads)

            messages.success(request, f"Concession policy '{name}' created.")
            return redirect('fees:concessions')

        elif action == 'approve':
            if not user_has_fee_permission(request.user, ['PRINCIPAL', 'SCHOOL_ADMIN', 'admin']):
                messages.error(request, "Only Principal or School Admin can approve concessions.")
            else:
                conc_id = request.POST.get('concession_id')
                concession = get_object_or_404(FeeConcession, school=school, pk=conc_id)
                concession.is_approved = True
                concession.approved_by = request.user
                concession.save(update_fields=['is_approved', 'approved_by', 'updated_at'])
                messages.success(request, f"Concession '{concession.name}' approved.")
            return redirect('fees:concessions')

    concessions = FeeConcession.objects.filter(school=school).prefetch_related('applicable_fee_heads', 'approved_by').order_by('-created_at')

    context = {
        "school": school,
        "concessions": concessions,
        "fee_heads": fee_heads,
        "types": ConcessionType.choices,
    }
    return render(request, "fees/concessions.html", context)


# ─────────────────────────────────────────────────────────────
# 7. INVOICES
# ─────────────────────────────────────────────────────────────

@login_required
def invoices_view(request):
    school = get_user_school(request.user)
    if not school:
        messages.error(request, "No school tenant associated.")
        return redirect('index_view')

    academic_years = AcademicYear.objects.filter(school=school)
    students = Student.objects.filter(school=school, is_active=True).select_related('grade_level', 'section')

    if request.method == "POST":
        action = request.POST.get('action')
        if action in ['create', 'create_invoice']:
            student_id = request.POST.get('student_id')
            ay_id = request.POST.get('academic_year_id')
            subtotal = Decimal(request.POST.get('subtotal', '0'))
            concession = Decimal(request.POST.get('concession', '0'))
            late_fee = Decimal(request.POST.get('late_fee', '0'))
            due_date_str = request.POST.get('due_date')
            due_date = datetime.date.fromisoformat(due_date_str) if due_date_str else None
            notes = request.POST.get('notes', '').strip()

            student = get_object_or_404(Student, school=school, pk=student_id)
            ay = get_object_or_404(AcademicYear, school=school, pk=ay_id)

            invoice = create_fee_invoice(
                school=school,
                student=student,
                academic_year=ay,
                subtotal=subtotal,
                concession=concession,
                late_fee=late_fee,
                due_date=due_date,
                notes=notes,
                actor=request.user,
                ip_address=request.META.get('REMOTE_ADDR')
            )
            student_full_name = f"{student.first_name} {student.last_name}".strip() if (hasattr(student, 'first_name') and student.first_name) else getattr(student, 'name', 'Student')
            messages.success(request, f"Invoice {invoice.invoice_number} created for {student_full_name} (₹{invoice.total}).")
            return redirect('fees:invoices')

        elif action == 'cancel':
            inv_id = request.POST.get('invoice_id')
            reason = request.POST.get('reason', 'Cancelled by accountant')
            invoice = get_object_or_404(FeeInvoice, school=school, pk=inv_id)
            try:
                cancel_fee_invoice(invoice, actor=request.user, reason=reason)
                messages.success(request, f"Invoice {invoice.invoice_number} cancelled.")
            except ValueError as e:
                messages.error(request, str(e))
            return redirect('fees:invoices')

    invoices_qs = FeeInvoice.objects.filter(school=school).select_related('student', 'academic_year')
    status_filter = request.GET.get('status', '')
    query = request.GET.get('q', '').strip()

    if status_filter:
        invoices_qs = invoices_qs.filter(status=status_filter)
    if query:
        invoices_qs = invoices_qs.filter(
            Q(invoice_number__icontains=query) | Q(student__first_name__icontains=query) |
            Q(student__last_name__icontains=query) | Q(student__admission_number__icontains=query)
        )

    paginator = Paginator(invoices_qs.order_by('-created_at'), 15)
    page_number = request.GET.get('page')
    invoices = paginator.get_page(page_number)

    context = {
        "school": school,
        "invoices": invoices,
        "academic_years": academic_years,
        "students": students,
        "statuses": InvoiceStatus.choices,
        "status_filter": status_filter,
        "query": query,
    }
    return render(request, "fees/invoices.html", context)


# ─────────────────────────────────────────────────────────────
# 8. PAYMENTS & CHEQUE MANAGEMENT
# ─────────────────────────────────────────────────────────────

@login_required
def payments_view(request):
    school = get_user_school(request.user)
    if not school:
        messages.error(request, "No school tenant associated.")
        return redirect('index_view')

    students = Student.objects.filter(school=school, is_active=True).select_related('grade_level')
    invoices = FeeInvoice.objects.filter(school=school).exclude(status=InvoiceStatus.PAID).select_related('student')

    if request.method == "POST":
        action = request.POST.get('action')
        if action in ['collect_offline', 'record_payment']:
            student_id = request.POST.get('student_id')
            invoice_id = request.POST.get('invoice_id') or None
            try:
                amount = Decimal(request.POST.get('amount', '0'))
            except Exception:
                messages.error(request, "Invalid payment amount format.")
                return redirect('fees:payments')

            if amount <= Decimal('0.00'):
                messages.error(request, "Payment amount must be greater than ₹0.00.")
                return redirect('fees:payments')

            gateway = request.POST.get('gateway') or request.POST.get('payment_gateway') or PaymentGateway.CASH
            method = request.POST.get('payment_method') or gateway
            transaction_id = request.POST.get('transaction_reference') or request.POST.get('transaction_id', '').strip() or None
            notes = request.POST.get('notes') or request.POST.get('remarks', '').strip()

            # Cheque specific
            cheque_no = request.POST.get('cheque_number', '').strip()
            bank_name = request.POST.get('bank_name', '').strip()
            chq_date_str = request.POST.get('cheque_date')
            chq_date = datetime.date.fromisoformat(chq_date_str) if chq_date_str else None
            default_chq_status = ChequeClearanceStatus.PENDING if gateway == PaymentGateway.CHEQUE else ChequeClearanceStatus.CLEARED
            initial_status = request.POST.get('clearance_status', default_chq_status)

            inv = FeeInvoice.objects.filter(school=school, pk=invoice_id).first() if invoice_id else None
            if inv and amount > inv.balance_amount:
                messages.error(request, f"Payment amount (₹{amount}) cannot exceed the outstanding invoice balance of ₹{inv.balance_amount}.")
                return redirect('fees:payments')

            if not student_id and inv:
                student = inv.student
            else:
                student = get_object_or_404(Student, school=school, pk=student_id)

            try:
                payment = record_offline_payment(
                    school=school,
                    student=student,
                    amount=amount,
                    gateway=gateway,
                    payment_method=method,
                    transaction_id=transaction_id,
                    invoice=inv,
                    collected_by=request.user,
                    notes=notes,
                    cheque_number=cheque_no,
                    bank_name=bank_name,
                    cheque_date=chq_date,
                    clearance_status=initial_status,
                    ip_address=request.META.get('REMOTE_ADDR')
                )
                if payment.status == PaymentStatus.SUCCESS:
                    receipt = generate_fee_receipt(payment, issued_by=request.user, ip_address=request.META.get('REMOTE_ADDR'))
                    messages.success(request, f"Payment of ₹{amount} recorded. Receipt {receipt.receipt_number} generated.")
                else:
                    messages.warning(request, f"Cheque payment of ₹{amount} recorded (Pending Clearance).")
            except ValueError as e:
                messages.error(request, str(e))

            return redirect('fees:payments')

        elif action == 'clear_cheque':
            pay_id = request.POST.get('payment_id') or request.POST.get('transaction_id')
            payment = get_object_or_404(PaymentTransaction, school=school, pk=pay_id)
            try:
                cleared = process_cheque_clearance(payment, actor=request.user, ip_address=request.META.get('REMOTE_ADDR'))
                receipt = generate_fee_receipt(cleared, issued_by=request.user, ip_address=request.META.get('REMOTE_ADDR'))
                messages.success(request, f"Cheque {cleared.cheque_number} cleared! Receipt {receipt.receipt_number} issued.")
            except ValueError as e:
                messages.error(request, str(e))
            return redirect('fees:payments')

        elif action == 'bounce_cheque':
            pay_id = request.POST.get('payment_id')
            reason = request.POST.get('bounce_reason', 'Insufficient Funds')
            payment = get_object_or_404(PaymentTransaction, school=school, pk=pay_id)
            try:
                bounced = process_cheque_bounce(payment, reason=reason, actor=request.user, ip_address=request.META.get('REMOTE_ADDR'))
                messages.error(request, f"Cheque {bounced.cheque_number} marked as BOUNCED. Allocations reversed.")
            except ValueError as e:
                messages.error(request, str(e))
            return redirect('fees:payments')

    payments_qs = PaymentTransaction.objects.filter(school=school).select_related('student', 'invoice', 'collected_by')
    gateway_filter = request.GET.get('gateway', '')
    status_filter = request.GET.get('status', '')
    query = request.GET.get('q', '').strip()

    if gateway_filter:
        payments_qs = payments_qs.filter(gateway=gateway_filter)
    if status_filter:
        payments_qs = payments_qs.filter(status=status_filter)
    if query:
        payments_qs = payments_qs.filter(
            Q(transaction_id__icontains=query) | Q(student__first_name__icontains=query) |
            Q(student__last_name__icontains=query) | Q(student__admission_number__icontains=query) |
            Q(cheque_number__icontains=query)
        )

    paginator = Paginator(payments_qs.order_by('-created_at'), 15)
    page_number = request.GET.get('page')
    payments = paginator.get_page(page_number)

    context = {
        "school": school,
        "payments": payments,
        "students": students,
        "invoices": invoices,
        "gateways": PaymentGateway.choices,
        "statuses": PaymentStatus.choices,
        "gateway_filter": gateway_filter,
        "status_filter": status_filter,
        "query": query,
    }
    return render(request, "fees/payments.html", context)


# ─────────────────────────────────────────────────────────────
# 9. RECEIPTS
# ─────────────────────────────────────────────────────────────

@login_required
def receipts_view(request):
    school = get_user_school(request.user)
    if not school:
        messages.error(request, "No school tenant associated.")
        return redirect('index_view')

    receipts_qs = FeeReceipt.objects.filter(school=school).select_related('student', 'payment', 'issued_by')

    # RBAC Scoping
    if request.user.requested_role in ['STUDENT']:
        receipts_qs = receipts_qs.filter(student__user=request.user)
    elif request.user.requested_role in ['PARENT']:
        receipts_qs = receipts_qs.filter(student__guardian_relationships__guardian__user=request.user)

    query = request.GET.get('q', '').strip()
    if query:
        receipts_qs = receipts_qs.filter(
            Q(receipt_number__icontains=query) | Q(student__first_name__icontains=query) |
            Q(student__last_name__icontains=query) | Q(student__admission_number__icontains=query)
        )

    paginator = Paginator(receipts_qs.order_by('-receipt_date', '-id'), 15)
    page_number = request.GET.get('page')
    receipts = paginator.get_page(page_number)

    context = {
        "school": school,
        "receipts": receipts,
        "query": query,
    }
    return render(request, "fees/receipts.html", context)


@login_required
def receipt_modal_detail(request, pk):
    """AJAX endpoint to render clean receipt detail with tamper-evident QR code."""
    school = get_user_school(request.user)
    receipt = get_object_or_404(FeeReceipt, school=school, pk=pk)
    student_name = f"{receipt.student.first_name} {receipt.student.last_name}".strip()
    qr_payload = receipt.qr_verification_code or generate_receipt_qr_code_payload(
        school=school,
        receipt_number=receipt.receipt_number,
        student_name=student_name,
        amount=receipt.amount
    )
    allocations = receipt.payment.allocations.select_related('installment').all() if receipt.payment else []

    data = {
        "receipt_number": receipt.receipt_number,
        "receipt_id": receipt.id,
        "issued_at": receipt.receipt_date.strftime("%d %b %Y"),
        "receipt_date": str(receipt.receipt_date),
        "student_name": student_name,
        "admission_number": getattr(receipt.student, 'admission_number', '') or receipt.student.roll_number,
        "grade": str(getattr(receipt.student, 'grade_level', '')),
        "section": str(getattr(receipt.student, 'section', '')),
        "roll_number": receipt.student.roll_number,
        "amount": str(receipt.amount),
        "amount_paid": str(receipt.amount),
        "gateway": receipt.payment.get_gateway_display() if (receipt.payment and hasattr(receipt.payment, 'get_gateway_display')) else receipt.payment_method,
        "payment_method": receipt.payment_method or (receipt.payment.gateway if receipt.payment else ""),
        "transaction_id": receipt.payment.transaction_id if receipt.payment else "",
        "cheque_number": receipt.payment.cheque_number if receipt.payment else "",
        "bank_name": receipt.payment.bank_name if receipt.payment else "",
        "issued_by": f"{receipt.issued_by.first_name} {receipt.issued_by.last_name}".strip() if receipt.issued_by else "Accounts Dept",
        "qr_payload": qr_payload,
        "allocations": [
            {
                "name": (alloc.installment.title if hasattr(alloc.installment, 'title') else getattr(alloc.installment, 'installment_name', 'Installment')) if alloc.installment else "Fee Allocation",
                "amount": str(alloc.allocated_amount)
            } for alloc in allocations
        ]
    }
    return JsonResponse(data)


@login_required
def receipt_pdf_download_view(request, pk):
    """Serves printable official Fee Receipt in PDF format."""
    school = get_user_school(request.user)
    receipt = get_object_or_404(FeeReceipt, school=school, pk=pk)
    pdf_bytes = render_receipt_pdf_bytes(receipt)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="receipt_{receipt.receipt_number}.pdf"'
    return response

