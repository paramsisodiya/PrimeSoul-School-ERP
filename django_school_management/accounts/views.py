import datetime
from decimal import Decimal
from django.utils import timezone
from rolepermissions.roles import assign_role
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test, login_required
from django.contrib.auth.mixins import UserPassesTestMixin
from django.views.generic import ListView
from django.views.generic.edit import UpdateView
from django.urls import reverse

from django_school_management.academics.models import Department
from django_school_management.institute.models import InstituteProfile
from django_school_management.students.models import Student
from django_school_management.teachers.models import Teacher
from .constants import ProfileApprovalStatusEnum, AccountURLConstants
from .forms import (
    ProfileCompleteForm,
    ApprovalProfileUpdateForm,
    UserChangeFormDashboard, UserCreateFormDashboard
)
from django_school_management.mixins.no_permission import LoginRequiredNoPermissionMixin
from .models import CustomGroup, User
from .forms import (CommonUserProfileForm,
    UserProfileSocialLinksFormSet
)
from .services.common import profile_not_approved, map_profile_approval_status_message
from permission_handlers.administrative import (
    user_is_admin_or_su,
)
from permission_handlers.basic import user_is_verified, can_access_dashboard
from .services.profile_complete import ProfileCompleteService


@login_required(login_url='account_login')
def profile_complete(request):
    ctx = {}
    user = User.objects.get(pk=request.user.pk)

    if profile_not_approved(request.user):
        messages.add_message(
            request,
            messages.INFO,
            map_profile_approval_status_message(request.user.approval_status)
        )
    else:
        profile = getattr(user, 'profile', None)
        if not profile:
            from .models import CommonUserProfile
            profile, _ = CommonUserProfile.objects.get_or_create(user=user)
        profile_edit_form = CommonUserProfileForm(
            instance=profile
        )
        social_links_form = UserProfileSocialLinksFormSet(
            instance=profile
        )
        ctx.update({
            'profile_edit_form': profile_edit_form,
            'social_links_form': social_links_form
        })

    if request.method == 'POST':
        profile_service = ProfileCompleteService(request, user, messages)
        profile_service.handle_profile_update()

    user_permissions = user.user_permissions.all()
    ctx.update({
        'verification_form': ProfileCompleteForm(instance=user),
        'user_perms': user_permissions if user_permissions else None,
    })
    return render(request, 'account/profile_complete.html', ctx)


@login_required(login_url=AccountURLConstants.permission_error)
@user_passes_test(
    can_access_dashboard,
    login_url=AccountURLConstants.profile_complete
)
def dashboard(request):
    institute = getattr(request.user, 'institute', None)
    if not institute:
        active = InstituteProfile.objects.filter(active=True).first()
        if active:
            request.user.institute = active
            request.user.save(update_fields=['institute'])
            institute = active

    is_admin = request.user.is_superuser or request.user.requested_role == 'admin'

    if request.GET.get('skip_onboarding'):
        request.session['skip_onboarding'] = True

    skipped = request.session.get('skip_onboarding', False)

    if is_admin and not skipped:
        school = getattr(request.user, 'school', None)
        if not school:
            if not institute:
                return redirect('institute:onboarding_step1')
            if not institute.onboarding_completed:
                next_step = institute.onboarding_step
                if next_step == 2:
                    return redirect('institute:onboarding_step2')
                elif next_step == 3:
                    return redirect('institute:onboarding_step3')

    from django_school_management.tenants.models import School
    from django_school_management.academics.models import GradeLevel, AcademicYear
    from django_school_management.teachers.models import TeacherProfile
    from django_school_management.fees.models import PaymentTransaction, PaymentStatus, FeeInvoice
    from django_school_management.fees.selectors.dashboard_selectors import get_fee_dashboard_summary
    from django.db.models import Sum

    school = getattr(request.user, 'school', None)
    if not school:
        school = School.objects.filter(is_active=True).first()
        if not school:
            inst = getattr(request.user, 'institute', None) or InstituteProfile.objects.filter(active=True).first()
            if inst:
                from django_school_management.tenants.services import sync_institute_to_school_tenant
                school = sync_institute_to_school_tenant(inst, user=request.user)
        elif request.user.is_authenticated and request.user.school_id != school.id:
            request.user.school = school
            request.user.save(update_fields=['school'])

    if school:
        total_students = Student.objects.filter(school=school, is_active=True).count()
        total_teachers = TeacherProfile.objects.filter(school=school, is_active=True).count()
        if total_teachers == 0:
            total_teachers = Teacher.objects.filter(school=school).count()
        total_grades = GradeLevel.objects.filter(school=school).count()
        active_ay = AcademicYear.objects.filter(school=school, is_current=True).first()
        fee_summary = get_fee_dashboard_summary(school=school, academic_year=active_ay)

        now = timezone.now()
        monthly_collected = (
            PaymentTransaction.objects.filter(
                school=school,
                status=PaymentStatus.SUCCESS,
                created_at__month=now.month,
                created_at__year=now.year
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        )

        recent_payments = (
            PaymentTransaction.objects.filter(school=school)
            .select_related('student', 'invoice')
            .order_by('-created_at')[:5]
        )

        from django_school_management.attendance.models import AttendanceRecord
        today_date = timezone.localdate()
        today_records = AttendanceRecord.objects.filter(school=school, attendance_date=today_date)
        total_att = today_records.count()
        if total_att > 0:
            present_att = today_records.filter(status__in=['PRESENT', 'LATE', 'HALF_DAY']).count()
            today_attendance_rate = f"{(present_att / total_att) * 100:.1f}%"
        else:
            today_attendance_rate = "0.0%" if total_students > 0 else "N/A"
    else:
        total_students = Student.objects.count()
        total_teachers = Teacher.objects.count()
        total_grades = Department.objects.count()
        active_ay = None
        fee_summary = {
            'total_expected_amount': '0.00',
            'total_collected_amount': '0.00',
            'total_pending_balance': '0.00',
            'total_overdue_balance': '0.00',
        }
        monthly_collected = Decimal('0.00')
        recent_payments = []
        today_attendance_rate = "N/A"

    context = {
        'school': school,
        'active_academic_year': active_ay,
        'total_students': total_students,
        'total_teachers': total_teachers,
        'total_departments': total_grades or Department.objects.count(),
        'total_grades': total_grades,
        'fee_summary': fee_summary,
        'monthly_collected': monthly_collected,
        'recent_payments': recent_payments,
        'today_attendance_rate': today_attendance_rate,
    }
    return render(request, 'dashboard.html', context)


@login_required(login_url=AccountURLConstants.permission_error)
@user_passes_test(user_is_admin_or_su, login_url=AccountURLConstants.permission_error)
def user_approval(request, pk, approved):
    """ Approve or decline approval request based on parameter `approved`.
    approved=0 means decline, 1 means approve.
    """
    user = User.objects.get(pk=pk)
    requested_role = user.requested_role

    if approved:
        assign_role(user, requested_role)
        if requested_role == 'admin':
            user.is_staff = True
        user.approval_status = 'a'
        if request.user.institute and not user.institute:
            user.institute = request.user.institute
        user.save()
        messages.add_message(
            request,
            messages.SUCCESS,
            f'{user}\'s account has been approved.'
        )
    else:
        messages.add_message(
            request,
            messages.SUCCESS,
            f'{user}\'s request for {requested_role} has been declined.'
        )
    return redirect(AccountURLConstants.user_requests)


@login_required(login_url=AccountURLConstants.permission_error)
@user_passes_test(user_is_admin_or_su, login_url=AccountURLConstants.permission_error)
def user_approval_with_modification(request, pk):
    user = User.objects.get(pk=pk)
    form = ApprovalProfileUpdateForm()
    if request.method == 'POST':
        requested_role = request.POST.get('requested_role')
        assign_role(user, requested_role)
        if requested_role == 'admin':
            user.is_staff = True
        user.approval_status = 'a'
        if request.user.institute and not user.institute:
            user.institute = request.user.institute
        user.save()
        messages.add_message(
            request,
            messages.SUCCESS,
            f'{user}\'s account has been approved.'
        )
        return redirect(AccountURLConstants.user_requests)
    ctx = {
        'form': form,
    }
    return render(request, 'account/modify_approval.html', ctx)


@login_required(login_url=AccountURLConstants.permission_error)
@user_passes_test(user_is_admin_or_su, login_url=AccountURLConstants.permission_error)
def add_user_view(request):
    context = dict()
    if request.method == 'POST':
        user_form = UserCreateFormDashboard(request.POST)
        if user_form.is_valid():
            user_form.save()
            return redirect(AccountURLConstants.all_accounts)
        else:
            context['user_form'] = user_form
            return render(request, 'academics/add_user.html', context)
    else:
        user_form = UserCreateFormDashboard()
        context['user_form'] = user_form
        return render(request, 'academics/add_user.html', context)


class AccountListView(LoginRequiredNoPermissionMixin, UserPassesTestMixin, ListView):
    model = User
    queryset = User.objects.exclude(is_superuser=True)
    template_name = 'account/dashboard/accounts_list.html'
    context_object_name = 'accounts'

    def test_func(self):
        user =  self.request.user
        return user_is_verified(user)


class GroupListView(LoginRequiredNoPermissionMixin, UserPassesTestMixin, ListView):
    model = CustomGroup
    template_name = 'academics/group_list.html'
    context_object_name = 'groups'

    def test_func(self):
        user =  self.request.user
        return user_is_verified(user)


class UserRequestsListView(UserPassesTestMixin, ListView):
    queryset = User.objects.exclude(approval_status=ProfileApprovalStatusEnum.approved.value)
    template_name = 'account/user_requests.html'
    context_object_name = 'users'

    def test_func(self):
        user =  self.request.user
        return user_is_admin_or_su(user)

user_requests_list = UserRequestsListView.as_view()


from django.views.decorators.http import require_POST
from django.contrib.auth.mixins import LoginRequiredMixin


@login_required
@require_POST
def profile_picture_upload(request):
    """
    Handles profile pic uploads coming through ajax.
    Requires authenticated user.
    """
    image = request.FILES.get('profile-picture')
    if not image:
        return JsonResponse({'status': 'error', 'message': 'No image provided'}, status=400)
    try:
        if not hasattr(request.user, 'profile') or not request.user.profile:
            from .models import CommonUserProfile
            CommonUserProfile.objects.create(user=request.user)
        request.user.profile.profile_picture = image
        request.user.profile.save()
        return JsonResponse({
            'status': 'ok',
            'imgUrl': request.user.profile.profile_picture.url,
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


class UserUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    form_class = UserChangeFormDashboard
    queryset = User.objects.all()
    template_name = 'account/dashboard/update_user.html'

    def test_func(self):
        user = self.request.user
        target_user = self.get_object()
        # Users can update themselves, or school admins can update users in their school
        if user.pk == target_user.pk or user.is_superuser or user_is_admin_or_su(user):
            return True
        return False

    def get_success_url(self):
        return reverse(
            'articles:author_profile',
            args=[self.object.username,])