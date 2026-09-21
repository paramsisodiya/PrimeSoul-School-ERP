from typing import Any

from django.shortcuts import redirect

from django_school_management.accounts.constants import AccountURLConstants
from django_school_management.accounts.forms import CommonUserProfileForm, UserProfileSocialLinksFormSet, \
    ProfileCompleteForm
from django_school_management.accounts.models import User


class ProfileCompleteService:
    def __init__(self, request: Any, user: User, session_messages):
        self.request = request
        self.user = user
        self.session_messages = session_messages

    def _handle_user_profile_update(self) -> None:
        profile = getattr(self.user, 'profile', None)
        if not profile:
            from django_school_management.accounts.models import CommonUserProfile
            profile, _ = CommonUserProfile.objects.get_or_create(user=self.user)
            self.user.refresh_from_db()

        profile_edit_form = CommonUserProfileForm(
            self.request.POST,
            self.request.FILES,
            instance=profile
        )
        social_links_form = UserProfileSocialLinksFormSet(
            self.request.POST,
            instance=profile
        )
        if profile_edit_form.is_valid():
            profile_edit_form.save()

        if social_links_form.is_valid():
            social_links_form.save()

        self.session_messages.add_message(
            self.request,
            self.session_messages.SUCCESS,
            'Your profile has been saved.'
        )

    def _handle_handle_approval_submit(self) -> None:
        if getattr(self.user, 'is_superuser', False):
            # Superuser verification is permanent and cannot be demoted to pending
            if self.user.approval_status != 'a':
                self.user.approval_status = 'a'
                self.user.save(update_fields=['approval_status'])
            self.session_messages.add_message(
                self.request,
                self.session_messages.INFO,
                'Superuser account is already verified.'
            )
            return

        verification_form = ProfileCompleteForm(
            self.request.POST,
            instance=self.user
        )

        if verification_form.is_valid():
            verification_form.instance.approval_status = 'p'
            # approval status get's pending
            verification_form.save()
            self.user.approval_status = 'p'
            self.user.save()
            self.session_messages.add_message(
                self.request,
                self.session_messages.SUCCESS,
                'Your request has been sent and will be reviewed by your institute.'
            )

    def handle_profile_update(self):
        if 'user-profile-update-form' in self.request.POST:
            self._handle_user_profile_update()
        else:
            self._handle_handle_approval_submit()

        return redirect(AccountURLConstants.profile_complete)
