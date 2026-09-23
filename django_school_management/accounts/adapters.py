"""
PrimeSoul Role-Aware Allauth Account Adapter.
Controls post-login and post-signup redirects based on user role and onboarding status.
"""
from allauth.account.adapter import DefaultAccountAdapter
from django.shortcuts import resolve_url
from django.conf import settings

from django_school_management.accounts.constants import ProfileApprovalStatusEnum


class AccountAdapter(DefaultAccountAdapter):
    """
    Directs authenticated users to their corresponding dashboard or self-service portal:
    - Platform Super Admin (Fresh / no school) -> Onboarding (/institute/onboarding/)
    - School Admin / Staff / Administrative roles -> Admin ERP Dashboard (/dashboard/)
    - Student -> Student Portal (/portal/student/)
    - Parent -> Parent Portal (/portal/parent/)
    - Teacher -> Teacher Portal (/portal/teacher/)
    - Unapproved Users -> Profile Verification (/account/)
    """

    def get_login_redirect_url(self, request):
        user = request.user
        if not user or not user.is_authenticated:
            return resolve_url(settings.LOGIN_REDIRECT_URL)

        # 1. Platform Super Admin onboarding check
        if user.is_superuser:
            school = getattr(user, 'school', None)
            institute = getattr(user, 'institute', None)
            if not school and not institute:
                return resolve_url('institute:onboarding_step1')
            return resolve_url('index_view')

        # 2. Unapproved user -> Profile completion / verification page
        if user.approval_status not in ['a', 'approved', ProfileApprovalStatusEnum.approved.value]:
            return resolve_url('account:profile_complete')

        # 3. Canonical Role-based routing for portals
        from django_school_management.accounts.roles import get_user_portal, PortalType

        portal = get_user_portal(user)
        if portal == PortalType.STUDENT_PORTAL:
            return resolve_url('portal:student_dashboard')
        elif portal == PortalType.TEACHER_PORTAL:
            return resolve_url('portal:teacher_dashboard')

        # 4. School Admin and staff roles -> Admin ERP dashboard
        return resolve_url('index_view')
