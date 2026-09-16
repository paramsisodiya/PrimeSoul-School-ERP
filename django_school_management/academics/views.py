import csv, io

from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic.edit import CreateView, UpdateView
from django.views.generic import ListView, TemplateView
from django.urls import reverse_lazy
from django.db.models import Count, Q

from .constants import AcademicsURLConstants
from .models import (Semester, Department,
                     AcademicSession, Subject, Batch)
from .forms import SemesterForm, DepartmentForm, AcademicSessionForm, SubjectForm, SubjectFormCurriculumAware, BatchForm, BatchFormWithLabel, BulkSemesterForm
from permission_handlers.administrative import (
    user_is_admin_su_editor_or_ac_officer,
    user_editor_admin_or_su,
    user_is_teacher_or_administrative,
)
from permission_handlers.basic import user_is_verified
from ..mixins.created_by import CreatedByMixin
from ..mixins.institute import get_user_institute, InstituteAutoSetMixin


class AcademicSetupHubView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Hub page for academic setup: links to all setup areas and optional checklist."""
    template_name = 'academics/setup_hub.html'

    def test_func(self):
        return user_is_admin_su_editor_or_ac_officer(self.request.user)

    def get_context_data(self, **kwargs):
        try:
            from django_school_management.result.models import SubjectGroup
            subject_group_model = SubjectGroup
        except (ImportError, ModuleNotFoundError):
            subject_group_model = None
        institute = get_user_institute(self.request.user)
        ctx = super().get_context_data(**kwargs)
        ctx['institute'] = institute
        # Subresources for display on hub (limited counts)
        ctx['academic_sessions'] = AcademicSession.objects.order_by('-year')[:10]
        ctx['current_session_id'] = institute.current_session_id if institute else None
        dept_qs = Department.objects.filter(institute=institute) if institute else Department.objects.all()
        ctx['departments'] = dept_qs.order_by('name')[:12]
        ctx['semesters'] = Semester.objects.order_by('number')[:12]
        ctx['batches'] = Batch.objects.select_related('department', 'year').order_by('-year__year', 'department__name', 'number')[:12]
        ctx['subjects'] = Subject.objects.order_by('name')[:12]
        if subject_group_model:
            ctx['subject_groups'] = subject_group_model.objects.select_related(
                'department', 'semester'
            ).order_by('department__name', 'semester__number')[:12]
            ctx['has_subject_groups'] = subject_group_model.objects.exists()
        else:
            ctx['subject_groups'] = []
            ctx['has_subject_groups'] = False
        # Checklist flags
        ctx['has_sessions'] = AcademicSession.objects.exists()
        ctx['has_departments'] = dept_qs.exists()
        ctx['has_semesters'] = Semester.objects.exists()
        ctx['has_batches'] = Batch.objects.exists()
        ctx['has_subjects'] = Subject.objects.exists()
        return ctx


academic_setup_hub = AcademicSetupHubView.as_view()


@user_passes_test(user_is_admin_su_editor_or_ac_officer)
def semesters(request):
    """
    Shows semester list and
    contains semester create form
    """
    # TODO: Allow multiple semester creation together. (1,3,4,5) like this format.
    all_sems = Semester.objects.all()
    if request.method == 'POST':
        form = SemesterForm(request.POST)
        if form.is_valid():
            semster = form.save(commit=False)
            semster.created_by = request.user
            semster.save()
            return redirect(AcademicsURLConstants.all_semester)
    form = SemesterForm()
    ctx = {
        'all_sems': all_sems,
        'form': form,
    }
    return render(request, 'academics/all_semester.html', ctx)


@user_passes_test(user_is_admin_su_editor_or_ac_officer)
def academic_session(request):
    """
    Responsible for academic session list view
    and academic session create view.
    """
    institute = get_user_institute(request.user)
    if request.method == 'POST':
        form = AcademicSessionForm(request.POST)
        if form.is_valid():
            ac_session = form.save(commit=False)
            ac_session.created_by = request.user
            ac_session.save()
            return redirect(AcademicsURLConstants.academic_sessions)
    else:
        form = AcademicSessionForm()
    all_academic_session = AcademicSession.objects.all()
    ctx = {
        'form': form,
        'academic_sessions': all_academic_session,
        'institute': institute,
        'current_session': institute.current_session if institute else None,
    }
    return render(request, 'academics/academic_sessions.html', ctx)


@user_passes_test(user_is_admin_su_editor_or_ac_officer)
def set_academic_session_current(request, pk):
    """Set the given academic session as the institute's current session."""
    session = get_object_or_404(AcademicSession, pk=pk)
    institute = get_user_institute(request.user)
    if institute:
        institute.current_session = session
        institute.save(update_fields=['current_session'])
        messages.success(request, f'Current session set to {session}.')
    return redirect(AcademicsURLConstants.academic_sessions)


@user_passes_test(user_is_verified)
def departments(request):
    """
    Responsible for department list view
    and department create view.
    """
    institute = get_user_institute(request.user)
    if request.method == 'POST':
        form = DepartmentForm(request.POST, request.FILES)
        if form.is_valid():
            dept = form.save(commit=False)
            dept.created_by = request.user
            dept.institute = institute
            dept.save()
            return redirect(AcademicsURLConstants.departments)
    else:
        form = DepartmentForm()
    all_department = Department.objects.filter(institute=institute) if institute else Department.objects.all()
    ctx = {
        'form': form,
        'departments': all_department,
    }
    return render(request, 'academics/departments.html', ctx)


@user_passes_test(user_editor_admin_or_su)
def delete_semester(request, pk):
    obj = get_object_or_404(Semester, pk=pk)
    obj.delete()
    return redirect(AcademicsURLConstants.all_semester)


class UpdateDepartment(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Department
    form_class = DepartmentForm
    template_name = 'academics/update_department.html'
    success_url = reverse_lazy(AcademicsURLConstants.departments)

    def test_func(self):
        user = self.request.user
        return user_editor_admin_or_su(user)

    def form_valid(self, form):
        return super().form_valid(form)


@user_passes_test(user_editor_admin_or_su)
def delete_department(request, pk):
    obj = get_object_or_404(Department, pk=pk)
    obj.delete()
    return redirect(AcademicsURLConstants.departments)


@user_passes_test(user_is_teacher_or_administrative)
def upload_subjects_csv(request):
    template = 'result/add_subject_csv.html'
    prompt = {
        'order': 'Subject name, Subject Code'
    }
    if request.method == 'GET':
        return render(request, template, prompt)

    csv_file = request.FILES['file']
    if not csv_file.name.endswith('.csv'):
        messages.error(request, 'Please, upload a CSV file.')
    try:
        data_set = csv_file.read().decode('UTF-8')
        io_string = io.StringIO(data_set)
        next(io_string)
        # TODO: upload data for foreignkey also, and
        # create object for foreignkey if no data found.
        for column in csv.reader(io_string, delimiter=',', quotechar='|'):
            _, created = Subject.objects.update_or_create(
                name=column[0],
                subject_code=column[1]
            )
    except:
        pass
    context = {}
    return render(request, template, context)


class CreateDepartmentView(LoginRequiredMixin, UserPassesTestMixin, InstituteAutoSetMixin, CreateView):
    form_class = DepartmentForm
    success_url = reverse_lazy(AcademicsURLConstants.departments)
    template_name = 'academics/create_department.html'

    def test_func(self):
        user = self.request.user
        return user_editor_admin_or_su(user)

create_department = CreateDepartmentView.as_view()


class CreateSemesterView(LoginRequiredMixin, UserPassesTestMixin, CreateView, CreatedByMixin):
    form_class = SemesterForm
    success_url = reverse_lazy(AcademicsURLConstants.all_semester)
    template_name = 'academics/create_semester.html'

    def test_func(self):
        user = self.request.user
        return user_editor_admin_or_su(user)

create_semester = CreateSemesterView.as_view()


@user_passes_test(user_is_admin_su_editor_or_ac_officer)
def create_semesters_bulk(request):
    """Create multiple semesters at once (e.g. 1-6 or 1,2,3,4)."""
    institute = get_user_institute(request.user)
    sem_label = institute.semester_label if institute else 'Semester'
    if request.method == 'POST':
        form = BulkSemesterForm(request.POST)
        if form.is_valid():
            numbers = form.cleaned_data['numbers']
            for n in numbers:
                Semester.objects.create(number=n, created_by=request.user)
            messages.success(request, f'Created {len(numbers)} {sem_label}(s).')
            return redirect(AcademicsURLConstants.all_semester)
    else:
        form = BulkSemesterForm()
    ctx = {'form': form}
    return render(request, 'academics/create_semesters_bulk.html', ctx)


class CreateAcademicSession(LoginRequiredMixin, UserPassesTestMixin, CreateView, CreatedByMixin):
    form_class = AcademicSessionForm
    success_url = reverse_lazy(AcademicsURLConstants.academic_sessions)
    template_name = 'academics/create_academic_semester.html'

    def test_func(self):
        user = self.request.user
        return user_is_admin_su_editor_or_ac_officer(user)

    def get_initial(self):
        from datetime import date
        initial = super().get_initial()
        next_year = date.today().year + 1
        initial['year'] = next_year
        return initial

create_academic_semester = CreateAcademicSession.as_view()


class SubjectListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Subject
    context_object_name = 'subjects'
    template_name = 'academics/subject_list.html'

    def get_queryset(self):
        qs = Subject.objects.select_related('instructor', 'subject_template').order_by('name')
        q = self.request.GET.get('q', '').strip()
        if q:
            try:
                code = int(q)
                qs = qs.filter(Q(name__icontains=q) | Q(subject_code=code))
            except ValueError:
                qs = qs.filter(name__icontains=q)
        return qs

    def test_func(self):
        user = self.request.user
        return user_is_teacher_or_administrative(user)

subject_list = SubjectListView.as_view()


class CreateSubjectView(LoginRequiredMixin, UserPassesTestMixin, CreateView, CreatedByMixin):
    form_class = SubjectFormCurriculumAware
    template_name = 'academics/create_subject.html'
    success_url = reverse_lazy(AcademicsURLConstants.subject_list)

    def test_func(self):
        user = self.request.user
        return user_is_teacher_or_administrative(user)

    def get_initial(self):
        initial = super().get_initial()
        template_id = self.request.GET.get('template')
        if not template_id:
            return initial
        try:
            from django_school_management.curriculum.models import SubjectTemplate
            template = SubjectTemplate.objects.get(pk=int(template_id))
        except (ValueError, SubjectTemplate.DoesNotExist):
            return initial
        initial['subject_template'] = template.pk
        initial['name'] = template.name[:50]
        initial['theory_marks'] = template.default_theory_marks
        initial['practical_marks'] = template.default_practical_marks
        # Suggest unique subject_code: 10000+template.pk if free, else next available
        base_code = 10000 + template.pk
        if not Subject.objects.filter(subject_code=base_code).exists():
            initial['subject_code'] = base_code
        else:
            from django.db.models import Max
            max_code = Subject.objects.aggregate(m=Max('subject_code'))['m'] or 0
            initial['subject_code'] = max_code + 1
        return initial

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        try:
            from django_school_management.curriculum.models import SubjectTemplate
            ctx['subject_templates'] = SubjectTemplate.objects.order_by('name')
        except Exception:
            ctx['subject_templates'] = []
        return ctx

create_subject = CreateSubjectView.as_view()


class CreateBatchView(LoginRequiredMixin, UserPassesTestMixin, CreateView, CreatedByMixin):
    model = Batch
    form_class = BatchFormWithLabel
    template_name = 'academics/create_batch.html'
    success_url = reverse_lazy(AcademicsURLConstants.batch_list)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        institute = get_user_institute(self.request.user)
        if institute and getattr(institute, 'current_session', None):
            initial['year'] = institute.current_session
        return initial

    def test_func(self):
        user = self.request.user
        return user_is_teacher_or_administrative(user)

create_batch_view = CreateBatchView.as_view()


class BatchListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Batch
    context_object_name = 'batches'
    template_name = 'academics/batch_list.html'

    def get_queryset(self):
        return Batch.objects.select_related('department', 'year').annotate(
            student_count=Count('students')
        )

    def test_func(self):
        user = self.request.user
        return user_is_teacher_or_administrative(user)

batch_list_view = BatchListView.as_view()


# ── Subject Update / Delete ──────────────────────────────

class UpdateSubjectView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Subject
    form_class = SubjectFormCurriculumAware
    template_name = 'academics/update_subject.html'
    success_url = reverse_lazy(AcademicsURLConstants.subject_list)

    def test_func(self):
        return user_is_teacher_or_administrative(self.request.user)

update_subject = UpdateSubjectView.as_view()


@user_passes_test(user_is_teacher_or_administrative)
def delete_subject(request, pk):
    obj = get_object_or_404(Subject, pk=pk)
    obj.delete()
    messages.success(request, "Subject deleted.")
    return redirect(AcademicsURLConstants.subject_list)


# ── Academic Session Update / Delete ─────────────────────

class UpdateAcademicSessionView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = AcademicSession
    form_class = AcademicSessionForm
    template_name = 'academics/update_academic_session.html'
    success_url = reverse_lazy(AcademicsURLConstants.academic_sessions)

    def test_func(self):
        return user_is_admin_su_editor_or_ac_officer(self.request.user)

update_academic_session = UpdateAcademicSessionView.as_view()


@user_passes_test(user_is_admin_su_editor_or_ac_officer)
def delete_academic_session(request, pk):
    obj = get_object_or_404(AcademicSession, pk=pk)
    obj.delete()
    messages.success(request, "Academic session deleted.")
    return redirect(AcademicsURLConstants.academic_sessions)


# ── Batch Update / Delete ────────────────────────────────

class UpdateBatchView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Batch
    form_class = BatchFormWithLabel
    template_name = 'academics/update_batch.html'
    success_url = reverse_lazy(AcademicsURLConstants.batch_list)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def test_func(self):
        return user_is_teacher_or_administrative(self.request.user)

update_batch = UpdateBatchView.as_view()


@user_passes_test(user_is_teacher_or_administrative)
def delete_batch(request, pk):
    obj = get_object_or_404(Batch, pk=pk)
    obj.delete()
    messages.success(request, "Batch deleted.")
    return redirect(AcademicsURLConstants.batch_list)


# ── Semester Update ──────────────────────────────────────

class UpdateSemesterView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Semester
    form_class = SemesterForm
    template_name = 'academics/update_semester.html'
    success_url = reverse_lazy(AcademicsURLConstants.all_semester)

    def test_func(self):
        return user_editor_admin_or_su(self.request.user)

update_semester = UpdateSemesterView.as_view()


# ─────────────────────────────────────────────────────────────
# Phase 5 — Modern PrimeSoul K-12 Academic Views
# ─────────────────────────────────────────────────────────────

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.core.exceptions import PermissionDenied
from django_school_management.tenants.models import School
from django_school_management.students.models import Student
from django_school_management.teachers.models import Teacher
from .models import (
    AcademicYear, GradeLevel, Section, Subject,
    SubjectAssignment, StudentEnrollment, ClassTeacherAssignment
)
from .services import academic_service, promotion_service
from .selectors import academic_selectors
from .forms import (
    AcademicYearForm, GradeLevelForm, SectionForm,
    SubjectModernForm, SubjectAssignmentForm, StudentEnrollmentForm
)


def get_user_school(user):
    """Safely extracts tenant school for the current user."""
    if user.is_authenticated and hasattr(user, 'school') and user.school:
        return user.school
    if user.is_superuser:
        return School.objects.filter(is_active=True).first()
    return None


def user_has_academic_permission(user, allowed_roles):
    """Checks whether user has required role or is superuser."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    user_role = getattr(user, 'requested_role', '') or getattr(user, 'role', '')
    if user_role in ['PLATFORM_SUPER_ADMIN', 'SCHOOL_ADMIN', 'admin']:
        return True
    return user_role in allowed_roles


@login_required
def academic_dashboard_view(request):
    """
    Command Center Dashboard for PrimeSoul Academic Management.
    """
    if not user_has_academic_permission(request.user, ['SCHOOL_ADMIN', 'PRINCIPAL', 'VICE_PRINCIPAL', 'ACADEMIC_COORDINATOR', 'TEACHER']):
        raise PermissionDenied("You do not have permission to view the Academic Dashboard.")

    school = get_user_school(request.user)
    if not school:
        messages.error(request, "No active school tenant context found.")
        return redirect('index_view')

    metrics = academic_selectors.get_academic_dashboard_metrics(school)
    context = {
        'school': school,
        **metrics,
    }
    return render(request, 'academics/dashboard.html', context)


@login_required
def academic_years_view(request):
    """
    List, filter, create, edit, and set current academic session.
    """
    if not user_has_academic_permission(request.user, ['SCHOOL_ADMIN', 'PRINCIPAL']):
        raise PermissionDenied("You do not have permission to manage academic years.")

    school = get_user_school(request.user)
    if not school:
        return redirect('index_view')

    if request.method == 'POST':
        action = request.POST.get('action')
        try:
            if action == 'set_current':
                year_id = int(request.POST.get('year_id'))
                academic_service.set_current_academic_year(school, year_id, actor=request.user)
                messages.success(request, "Active academic year updated successfully.")
            elif action == 'create':
                form = AcademicYearForm(request.POST)
                if form.is_valid():
                    year = form.save(commit=False)
                    year.school = school
                    year.created_by = request.user
                    year.save()
                    messages.success(request, f"Academic Year {year.name} created successfully.")
                else:
                    for field, errs in form.errors.items():
                        messages.error(request, f"{field}: {errs[0]}")
            elif action == 'edit':
                year_id = int(request.POST.get('year_id'))
                year = get_object_or_404(AcademicYear, pk=year_id, school=school)
                form = AcademicYearForm(request.POST, instance=year)
                if form.is_valid():
                    form.save()
                    messages.success(request, f"Academic Year {year.name} updated successfully.")
                else:
                    for field, errs in form.errors.items():
                        messages.error(request, f"{field}: {errs[0]}")
        except Exception as e:
            messages.error(request, f"Error processing academic year: {str(e)}")
        return redirect('academics:academic_years')

    query = request.GET.get('q', '')
    status_filter = request.GET.get('status', '')
    years_qs = academic_selectors.get_academic_years_list(school, query=query, status_filter=status_filter)

    paginator = Paginator(years_qs, 15)
    page_number = request.GET.get('page')
    years_page = paginator.get_page(page_number)

    form = AcademicYearForm()
    context = {
        'school': school,
        'years': years_page,
        'form': form,
        'query': query,
        'status_filter': status_filter,
        'statuses': AcademicYear.STATUS_CHOICES,
    }
    return render(request, 'academics/years.html', context)


@login_required
def classes_view(request):
    """
    List, create, update, and activate/deactivate Grade Levels.
    """
    if not user_has_academic_permission(request.user, ['SCHOOL_ADMIN', 'PRINCIPAL', 'ACADEMIC_COORDINATOR']):
        raise PermissionDenied("You do not have permission to manage classes.")

    school = get_user_school(request.user)
    if not school:
        return redirect('index_view')

    if request.method == 'POST':
        action = request.POST.get('action')
        try:
            if action == 'create':
                form = GradeLevelForm(request.POST)
                if form.is_valid():
                    grade = form.save(commit=False)
                    grade.school = school
                    grade.created_by = request.user
                    grade.save()
                    messages.success(request, f"Class {grade.name} created successfully.")
                else:
                    for field, errs in form.errors.items():
                        messages.error(request, f"{field}: {errs[0]}")
            elif action == 'edit':
                grade_id = int(request.POST.get('grade_id'))
                grade = get_object_or_404(GradeLevel, pk=grade_id, school=school)
                form = GradeLevelForm(request.POST, instance=grade)
                if form.is_valid():
                    form.save()
                    messages.success(request, f"Class {grade.name} updated successfully.")
                else:
                    for field, errs in form.errors.items():
                        messages.error(request, f"{field}: {errs[0]}")
            elif action == 'toggle_active':
                grade_id = int(request.POST.get('grade_id'))
                grade = get_object_or_404(GradeLevel, pk=grade_id, school=school)
                grade.is_active = not grade.is_active
                grade.save(update_fields=['is_active'])
                status_str = "activated" if grade.is_active else "deactivated"
                messages.success(request, f"Class {grade.name} has been {status_str}.")
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
        return redirect('academics:classes')

    query = request.GET.get('q', '')
    board_filter = request.GET.get('board', '')
    classes_qs = academic_selectors.get_classes_list(school, query=query, board_filter=board_filter)

    paginator = Paginator(classes_qs, 20)
    classes_page = paginator.get_page(request.GET.get('page'))

    form = GradeLevelForm()
    context = {
        'school': school,
        'classes': classes_page,
        'form': form,
        'query': query,
        'board_filter': board_filter,
    }
    return render(request, 'academics/classes.html', context)


@login_required
def sections_view(request):
    """
    List, create, update, and assign class teacher to Sections.
    """
    if not user_has_academic_permission(request.user, ['SCHOOL_ADMIN', 'PRINCIPAL', 'ACADEMIC_COORDINATOR']):
        raise PermissionDenied("You do not have permission to manage sections.")

    school = get_user_school(request.user)
    if not school:
        return redirect('index_view')

    current_year = AcademicYear.objects.filter(school=school, is_current=True).first()

    if request.method == 'POST':
        action = request.POST.get('action')
        try:
            if action == 'create':
                form = SectionForm(request.POST, school=school)
                if form.is_valid():
                    sec = form.save(commit=False)
                    sec.school = school
                    sec.created_by = request.user
                    if not sec.academic_year and current_year:
                        sec.academic_year = current_year
                    sec.save()
                    if sec.class_teacher and sec.academic_year:
                        ClassTeacherAssignment.objects.create(
                            school=school,
                            academic_year=sec.academic_year,
                            section=sec,
                            teacher=sec.class_teacher,
                            is_active=True,
                            created_by=request.user
                        )
                    messages.success(request, f"Section {sec.grade_level.name} - {sec.name} created successfully.")
                else:
                    for field, errs in form.errors.items():
                        messages.error(request, f"{field}: {errs[0]}")
            elif action == 'edit':
                section_id = int(request.POST.get('section_id'))
                sec = get_object_or_404(Section, pk=section_id, school=school)
                old_teacher = sec.class_teacher
                form = SectionForm(request.POST, instance=sec, school=school)
                if form.is_valid():
                    form.save()
                    if sec.class_teacher and sec.class_teacher != old_teacher:
                        academic_service.assign_class_teacher(sec, sec.class_teacher, sec.academic_year, actor=request.user)
                    messages.success(request, f"Section {sec.grade_level.name} - {sec.name} updated successfully.")
                else:
                    for field, errs in form.errors.items():
                        messages.error(request, f"{field}: {errs[0]}")
            elif action == 'toggle_active':
                section_id = int(request.POST.get('section_id'))
                sec = get_object_or_404(Section, pk=section_id, school=school)
                sec.is_active = not sec.is_active
                sec.save(update_fields=['is_active'])
                status_str = "activated" if sec.is_active else "deactivated"
                messages.success(request, f"Section {sec.name} has been {status_str}.")
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
        return redirect('academics:sections')

    grade_filter = request.GET.get('grade')
    grade_id = int(grade_filter) if grade_filter and grade_filter.isdigit() else None
    sections_qs = academic_selectors.get_sections_list(school, year=current_year, grade_id=grade_id)

    paginator = Paginator(sections_qs, 20)
    sections_page = paginator.get_page(request.GET.get('page'))

    form = SectionForm(school=school)
    grades = GradeLevel.objects.filter(school=school, is_active=True)
    teachers = Teacher.objects.filter(school=school)
    years = AcademicYear.objects.filter(school=school)

    context = {
        'school': school,
        'sections': sections_page,
        'form': form,
        'grades': grades,
        'teachers': teachers,
        'years': years,
        'current_year': current_year,
        'grade_filter': grade_id,
    }
    return render(request, 'academics/sections.html', context)


@login_required
def subjects_view(request):
    """
    List, search, filter, and manage Subjects.
    """
    if not user_has_academic_permission(request.user, ['SCHOOL_ADMIN', 'PRINCIPAL', 'ACADEMIC_COORDINATOR', 'TEACHER']):
        raise PermissionDenied("You do not have permission to view subjects.")

    school = get_user_school(request.user)
    if not school:
        return redirect('index_view')

    if request.method == 'POST':
        action = request.POST.get('action')
        try:
            if action == 'create':
                form = SubjectModernForm(request.POST, school=school)
                if form.is_valid():
                    sub = form.save(commit=False)
                    sub.school = school
                    sub.created_by = request.user
                    sub.save()
                    messages.success(request, f"Subject '{sub.name}' created successfully.")
                else:
                    for field, errs in form.errors.items():
                        messages.error(request, f"{field}: {errs[0]}")
            elif action == 'edit':
                sub_id = int(request.POST.get('subject_id'))
                sub = get_object_or_404(Subject, pk=sub_id, school=school)
                form = SubjectModernForm(request.POST, instance=sub, school=school)
                if form.is_valid():
                    form.save()
                    messages.success(request, f"Subject '{sub.name}' updated successfully.")
                else:
                    for field, errs in form.errors.items():
                        messages.error(request, f"{field}: {errs[0]}")
            elif action == 'toggle_active':
                sub_id = int(request.POST.get('subject_id'))
                sub = get_object_or_404(Subject, pk=sub_id, school=school)
                sub.is_active = not sub.is_active
                sub.save(update_fields=['is_active'])
                status_str = "activated" if sub.is_active else "deactivated"
                messages.success(request, f"Subject {sub.name} has been {status_str}.")
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
        return redirect('academics:subjects_directory')

    query = request.GET.get('q', '')
    type_filter = request.GET.get('type', '')
    subjects_qs = academic_selectors.get_subjects_list(school, query=query, type_filter=type_filter)

    paginator = Paginator(subjects_qs, 20)
    subjects_page = paginator.get_page(request.GET.get('page'))

    form = SubjectModernForm(school=school)
    teachers = Teacher.objects.filter(school=school)

    context = {
        'school': school,
        'subjects': subjects_page,
        'form': form,
        'teachers': teachers,
        'query': query,
        'type_filter': type_filter,
        'types': Subject.SUBJECT_TYPE_CHOICES,
    }
    return render(request, 'academics/subjects.html', context)


@login_required
def assignments_view(request):
    """
    List and assign Subjects to Classes/Sections and Teachers.
    """
    if not user_has_academic_permission(request.user, ['SCHOOL_ADMIN', 'PRINCIPAL', 'ACADEMIC_COORDINATOR', 'TEACHER']):
        raise PermissionDenied("You do not have permission to view subject assignments.")

    school = get_user_school(request.user)
    if not school:
        return redirect('index_view')

    current_year = AcademicYear.objects.filter(school=school, is_current=True).first()

    if request.method == 'POST':
        action = request.POST.get('action')
        try:
            if action == 'create':
                form = SubjectAssignmentForm(request.POST, school=school)
                if form.is_valid():
                    academic_year = form.cleaned_data['academic_year']
                    grade_level = form.cleaned_data['grade_level']
                    section = form.cleaned_data.get('section')
                    subject = form.cleaned_data['subject']
                    teacher = form.cleaned_data.get('teacher')
                    periods = form.cleaned_data.get('periods_per_week', 5)

                    academic_service.assign_subject_to_teacher(
                        school=school,
                        academic_year=academic_year,
                        grade_level=grade_level,
                        subject=subject,
                        section=section,
                        teacher=teacher,
                        periods_per_week=periods,
                        actor=request.user
                    )
                    messages.success(request, f"Subject '{subject.name}' successfully assigned.")
                else:
                    for field, errs in form.errors.items():
                        messages.error(request, f"{field}: {errs[0]}")
            elif action == 'delete':
                assignment_id = int(request.POST.get('assignment_id'))
                assign = get_object_or_404(SubjectAssignment, pk=assignment_id, school=school)
                assign.delete()
                messages.success(request, "Subject assignment removed.")
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
        return redirect('academics:assignments')

    year_filter = request.GET.get('year')
    year_obj = AcademicYear.objects.filter(pk=year_filter, school=school).first() if year_filter else current_year
    grade_filter = request.GET.get('grade')
    grade_id = int(grade_filter) if grade_filter and grade_filter.isdigit() else None

    assignments_qs = academic_selectors.get_subject_assignments_list(school, year=year_obj, grade_id=grade_id)
    paginator = Paginator(assignments_qs, 25)
    assignments_page = paginator.get_page(request.GET.get('page'))

    form = SubjectAssignmentForm(school=school)
    years = AcademicYear.objects.filter(school=school)
    grades = GradeLevel.objects.filter(school=school, is_active=True)
    subjects = Subject.objects.filter(school=school, is_active=True)
    teachers = Teacher.objects.filter(school=school)

    context = {
        'school': school,
        'assignments': assignments_page,
        'form': form,
        'years': years,
        'grades': grades,
        'subjects': subjects,
        'teachers': teachers,
        'current_year': current_year,
        'selected_year': year_obj,
        'grade_filter': grade_id,
    }
    return render(request, 'academics/assignments.html', context)


@login_required
def enrollments_view(request):
    """
    Student Enrollment Registry: List, enroll, change section, and view history.
    """
    if not user_has_academic_permission(request.user, ['SCHOOL_ADMIN', 'PRINCIPAL', 'ACADEMIC_COORDINATOR', 'RECEPTIONIST']):
        raise PermissionDenied("You do not have permission to manage enrollments.")

    school = get_user_school(request.user)
    if not school:
        return redirect('index_view')

    current_year = AcademicYear.objects.filter(school=school, is_current=True).first()

    if request.method == 'POST':
        action = request.POST.get('action')
        try:
            if action == 'enroll':
                form = StudentEnrollmentForm(request.POST, school=school)
                if form.is_valid():
                    enrollment = form.save(commit=False)
                    enrollment.school = school
                    enrollment.created_by = request.user
                    enrollment.save()
                    messages.success(request, f"Student '{enrollment.student.name}' enrolled in {enrollment.grade_level.name}.")
                else:
                    for field, errs in form.errors.items():
                        messages.error(request, f"{field}: {errs[0]}")
            elif action == 'change_section':
                enrollment_id = int(request.POST.get('enrollment_id'))
                section_id = request.POST.get('section_id')
                enrollment = get_object_or_404(StudentEnrollment, pk=enrollment_id, school=school)
                sec_obj = Section.objects.filter(pk=section_id, school=school).first() if section_id else None
                enrollment.section = sec_obj
                enrollment.save(update_fields=['section'])
                # Sync student pointer
                if enrollment.academic_year and enrollment.academic_year.is_current:
                    enrollment.student.section = sec_obj
                    enrollment.student.save(update_fields=['section'])
                messages.success(request, f"Section updated for {enrollment.student.name}.")
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
        return redirect('academics:enrollments')

    year_filter = request.GET.get('year')
    year_obj = AcademicYear.objects.filter(pk=year_filter, school=school).first() if year_filter else current_year
    grade_filter = request.GET.get('grade')
    grade_id = int(grade_filter) if grade_filter and grade_filter.isdigit() else None
    section_filter = request.GET.get('section')
    section_id = int(section_filter) if section_filter and section_filter.isdigit() else None
    status_filter = request.GET.get('status')
    query = request.GET.get('q', '')

    enrollments_qs = academic_selectors.get_student_enrollments_list(
        school, year=year_obj, grade_id=grade_id, section_id=section_id,
        status_filter=status_filter, query=query
    )
    paginator = Paginator(enrollments_qs, 25)
    enrollments_page = paginator.get_page(request.GET.get('page'))

    form = StudentEnrollmentForm(school=school)
    years = AcademicYear.objects.filter(school=school)
    grades = GradeLevel.objects.filter(school=school, is_active=True)
    sections = Section.objects.filter(school=school, is_active=True)
    students = Student.objects.filter(school=school, is_active=True)

    context = {
        'school': school,
        'enrollments': enrollments_page,
        'form': form,
        'years': years,
        'grades': grades,
        'sections': sections,
        'students': students,
        'current_year': current_year,
        'selected_year': year_obj,
        'grade_filter': grade_id,
        'section_filter': section_id,
        'status_filter': status_filter,
        'query': query,
        'statuses': StudentEnrollment.ENROLLMENT_STATUS_CHOICES,
    }
    return render(request, 'academics/enrollments.html', context)


@login_required
def promotions_view(request):
    """
    Controlled student promotion desk across academic years and classes.
    """
    if not user_has_academic_permission(request.user, ['SCHOOL_ADMIN', 'PRINCIPAL']):
        raise PermissionDenied("You do not have permission to execute student promotions.")

    school = get_user_school(request.user)
    if not school:
        return redirect('index_view')

    current_year = AcademicYear.objects.filter(school=school, is_current=True).first()

    if request.method == 'POST':
        try:
            source_year_id = int(request.POST.get('source_year'))
            target_year_id = int(request.POST.get('target_year'))
            source_grade_id = int(request.POST.get('source_grade'))
            target_grade_id = int(request.POST.get('target_grade'))
            source_section_id = request.POST.get('source_section')
            target_section_id = request.POST.get('target_section')
            student_ids = request.POST.getlist('student_ids')

            source_year = get_object_or_404(AcademicYear, pk=source_year_id, school=school)
            target_year = get_object_or_404(AcademicYear, pk=target_year_id, school=school)
            source_grade = get_object_or_404(GradeLevel, pk=source_grade_id, school=school)
            target_grade = get_object_or_404(GradeLevel, pk=target_grade_id, school=school)

            source_section = Section.objects.filter(pk=source_section_id, school=school).first() if source_section_id else None
            target_section = Section.objects.filter(pk=target_section_id, school=school).first() if target_section_id else None
            st_ids = [int(sid) for sid in student_ids if sid.isdigit()] if student_ids else None

            result = promotion_service.execute_promotion(
                school=school,
                source_year=source_year,
                target_year=target_year,
                source_grade=source_grade,
                target_grade=target_grade,
                source_section=source_section,
                target_section=target_section,
                student_ids=st_ids,
                actor=request.user
            )

            messages.success(
                request,
                f"Successfully promoted {result['promoted_count']} student(s) to {target_grade.name} ({target_year.name})."
            )
            if result['skipped_count'] > 0:
                messages.warning(request, f"{result['skipped_count']} student(s) were skipped because they were already enrolled.")
        except Exception as e:
            messages.error(request, f"Promotion execution failed: {str(e)}")
        return redirect('academics:promotions')

    source_year_id = request.GET.get('source_year')
    source_grade_id = request.GET.get('source_grade')
    source_section_id = request.GET.get('source_section')

    candidate_students = []
    if source_year_id and source_grade_id:
        c_qs = StudentEnrollment.objects.filter(
            school=school,
            academic_year_id=source_year_id,
            grade_level_id=source_grade_id,
            status=StudentEnrollment.STATUS_ACTIVE
        ).select_related('student', 'section')
        if source_section_id:
            c_qs = c_qs.filter(section_id=source_section_id)
        candidate_students = list(c_qs)

    years = AcademicYear.objects.filter(school=school).order_by('-start_date')
    grades = GradeLevel.objects.filter(school=school, is_active=True)
    sections = Section.objects.filter(school=school, is_active=True)

    context = {
        'school': school,
        'years': years,
        'grades': grades,
        'sections': sections,
        'current_year': current_year,
        'source_year_id': int(source_year_id) if source_year_id and source_year_id.isdigit() else (current_year.pk if current_year else None),
        'source_grade_id': int(source_grade_id) if source_grade_id and source_grade_id.isdigit() else None,
        'source_section_id': int(source_section_id) if source_section_id and source_section_id.isdigit() else None,
        'candidate_students': candidate_students,
    }
    return render(request, 'academics/promotions.html', context)

