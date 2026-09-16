from django.http import HttpResponse, HttpResponseNotFound
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import ListView
from django.views.generic import UpdateView
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied

from .models import Teacher, Designation
from .forms import TeacherForm, TeacherDesignationForm
from permission_handlers.administrative import (
    user_editor_admin_or_su,
    user_is_admin_or_su,
    user_is_teacher_or_administrative,
)
from permission_handlers.basic import user_is_teacher, user_is_verified
from django_school_management.mixins.no_permission import LoginRequiredNoPermissionMixin
from django_school_management.mixins.institute import get_user_institute


@user_passes_test(user_is_teacher_or_administrative)
def teachers_view(request):
    """
    :param request:
    :return: list of teachers to logged in user, login form instead.
    """
    institute = get_user_institute(request.user)
    teachers = Teacher.objects.filter(institute=institute) if institute else Teacher.objects.all()
    context = {'teachers': teachers}
    return render(request, 'teachers/teacher_list.html', context)


# TODO: Reduce duplicate queries.
@user_passes_test(user_is_admin_or_su)
def add_teacher_view(request):
    """
    :param request:
    :return: teacher add form
    """
    if request.method == 'POST':
        form = TeacherForm(request.POST, request.FILES)
        if form.is_valid():
            teacher = form.save(commit=False)
            teacher.institute = get_user_institute(request.user)
            teacher.created_by = request.user
            teacher.save()
            form.save_m2m()
            return redirect('teachers:all_teacher')
        context = {'form': form}
        return render(request, 'teachers/add_teacher.html', context)
    form = TeacherForm()
    context = {'form': form}
    return render(request, 'teachers/add_teacher.html', context)


@user_passes_test(user_is_verified)
def teacher_detail_view(request, pk):
    teacher = get_object_or_404(Teacher, pk=pk)
    context = {'teacher': teacher}
    return render(request, 'teachers/teacher_detail.html', context)


class teacher_update_view(LoginRequiredNoPermissionMixin, UserPassesTestMixin, UpdateView):
    model = Teacher
    fields = '__all__'
    template_name = 'teachers/update_teacher.html'

    def test_func(self):
        user = self.request.user
        return user_editor_admin_or_su(user)

    def get_success_url(self):
        teacher_id = self.kwargs['pk']
        return reverse_lazy('teachers:teacher_details', kwargs={'pk': teacher_id})


from django.views.decorators.http import require_POST
from django_school_management.accounts.permissions import school_admin_required


@require_POST
@user_passes_test(user_is_admin_or_su)
def teacher_delete_view(request, pk):
    """
    Safely delete a teacher record via POST only.
    Validates tenant ownership before deletion.
    """
    teacher = get_object_or_404(Teacher, pk=pk)
    tenant = getattr(request, 'tenant', None) or getattr(request.user, 'school', None)
    if tenant and not request.user.is_superuser:
        if teacher.school and teacher.school != tenant:
            raise PermissionDenied("Cannot delete teacher from another school.")
    teacher.delete()
    return redirect('teachers:all_teacher')



@user_passes_test(user_is_admin_or_su)
def create_designation(request):
    if request.method == 'POST':
        form = TeacherDesignationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('teachers:designations')
    else:
        form = TeacherDesignationForm()
    context = {'form': form}
    return render(request, 'teachers/designation_create.html', context)


class designation_list_view(LoginRequiredNoPermissionMixin, UserPassesTestMixin, ListView):
    model = Designation
    template_name = 'teachers/designation_list.html'

    def test_func(self):
        user = self.request.user
        return user_is_verified(user)


@user_passes_test(user_is_teacher)
def teacher_my_portal(request, teacher_id: str):
    if request.user.employee_or_student_id != teacher_id:
        return HttpResponseNotFound("Page not found!")

    ctx = dict()
    return render(request, "teachers/my-portal.html", ctx)


@user_passes_test(user_is_admin_or_su)
def import_teachers_csv_view(request):
    """
    Handles CSV bulk import for teachers and faculty with validation.
    """
    from django_school_management.core.services.csv_import_service import TeacherCSVImporter
    school = getattr(request, 'school', None) or getattr(request.user, 'school', None)

    if request.method == "POST" and request.FILES.get("csv_file"):
        csv_file = request.FILES["csv_file"]
        if not csv_file.name.endswith(".csv"):
            messages.error(request, "Please upload a valid .csv file.")
            return redirect("teachers:import_teachers_csv")

        try:
            content = csv_file.read().decode("utf-8-sig")
            dry_run = request.POST.get("dry_run") == "1"
            result = TeacherCSVImporter.import_csv(school=school, file_content=content, dry_run=dry_run)
            
            if result.errors:
                messages.error(request, f"Import validation found {len(result.errors)} errors. No records were modified.")
            elif result.duplicates:
                messages.warning(request, f"Found {len(result.duplicates)} duplicates.")
            
            if result.imported_rows > 0:
                messages.success(request, f"Successfully imported {result.imported_rows} faculty members!")
                return redirect("teachers:all_teacher")

            context = {
                "result": result.to_dict(),
                "dry_run": dry_run,
                "school": school,
            }
            return render(request, "teachers/import_teachers_csv.html", context)
        except Exception as exc:
            messages.error(request, f"Error processing CSV file: {str(exc)}")

    return render(request, "teachers/import_teachers_csv.html", {"school": school})


@user_passes_test(user_is_admin_or_su)
def download_sample_teachers_csv_view(request):
    """
    Returns downloadable sample CSV template for teachers import.
    """
    from django_school_management.core.services.csv_import_service import TeacherCSVImporter
    sample = TeacherCSVImporter.get_sample_csv()
    response = HttpResponse(sample, content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="teachers_import_sample.csv"'
    return response