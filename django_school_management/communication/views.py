from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.views.decorators.http import require_POST
from django.http import JsonResponse, HttpResponseRedirect
from django.urls import reverse
from django.utils import timezone

from django_school_management.tenants.models import School
from django_school_management.communication.models import (
    Announcement, AnnouncementTarget, AnnouncementCategory,
    Notification, NotificationTemplate, NotificationDeliveryLog, NotificationPreference
)
from django_school_management.communication.forms import (
    AnnouncementForm, NotificationTemplateForm, NotificationPreferenceForm
)
from django_school_management.communication.selectors.communication_selectors import (
    get_communication_dashboard_metrics,
    get_user_notifications,
    get_user_unread_count,
    get_announcement_delivery_summary,
    get_active_announcements_for_user
)
from django_school_management.communication.services.notification_service import (
    publish_announcement,
    mark_notification_as_read,
    mark_all_notifications_read
)


def resolve_school(request) -> School:
    """Helper to resolve current tenant school."""
    if hasattr(request, 'tenant') and request.tenant:
        return request.tenant
    if hasattr(request, 'school') and request.school:
        return request.school
    if request.user.is_authenticated and getattr(request.user, 'school', None):
        return request.user.school
    return School.objects.first()


# ---------------------------------------------------------------------------
# Staff / Administration Communication Views
# ---------------------------------------------------------------------------

@login_required
def communication_dashboard(request):
    """
    Staff communication dashboard displaying announcement overview and metrics.
    """
    school = resolve_school(request)
    metrics = get_communication_dashboard_metrics(school)
    recent_announcements = Announcement.objects.filter(school=school).order_by('-created')[:5]
    recent_logs = NotificationDeliveryLog.objects.filter(
        notification__school=school
    ).select_related('notification').order_by('-attempted_at')[:8]

    context = {
        'school': school,
        'metrics': metrics,
        'recent_announcements': recent_announcements,
        'recent_logs': recent_logs,
    }
    return render(request, 'communication/dashboard.html', context)


@login_required
def announcement_list(request):
    """
    List and filter announcements within the school tenant.
    """
    school = resolve_school(request)
    qs = Announcement.objects.filter(school=school).select_related('category', 'created_by').prefetch_related('targets')

    status_filter = request.GET.get('status')
    priority_filter = request.GET.get('priority')
    search_q = request.GET.get('q')

    if status_filter:
        qs = qs.filter(status=status_filter)
    if priority_filter:
        qs = qs.filter(priority=priority_filter)
    if search_q:
        qs = qs.filter(title__icontains=search_q)

    qs = qs.order_by('-created')

    context = {
        'school': school,
        'announcements': qs,
        'status_filter': status_filter,
        'priority_filter': priority_filter,
        'search_q': search_q,
    }
    return render(request, 'communication/announcements.html', context)


@login_required
def announcement_create(request):
    """
    Create a new announcement with targeted audience configuration.
    """
    school = resolve_school(request)

    if request.method == 'POST':
        form = AnnouncementForm(request.POST, request.FILES, school=school)
        if form.is_valid():
            announcement = form.save(commit=False)
            announcement.school = school
            announcement.created_by = request.user
            announcement.save()

            # Create target record
            target_type = form.cleaned_data.get('target_type')
            grade_level = form.cleaned_data.get('grade_level')
            section = form.cleaned_data.get('section')

            AnnouncementTarget.objects.create(
                announcement=announcement,
                target_type=target_type,
                grade_level=grade_level,
                section=section
            )

            # If published directly, trigger dispatch
            if announcement.status == Announcement.STATUS_PUBLISHED:
                notif_count = publish_announcement(announcement, published_by=request.user)
                messages.success(request, f"Announcement published! {notif_count} notification(s) dispatched.")
            else:
                messages.success(request, f"Announcement '{announcement.title}' saved as {announcement.get_status_display()}.")

            return redirect('communication:announcement_detail', pk=announcement.pk)
    else:
        form = AnnouncementForm(school=school)

    context = {
        'school': school,
        'form': form,
        'is_edit': False,
    }
    return render(request, 'communication/announcement_form.html', context)


@login_required
def announcement_detail(request, pk):
    """
    View announcement details, target recipients, and dispatch summary.
    """
    school = resolve_school(request)
    announcement = get_object_or_404(Announcement, pk=pk, school=school)
    delivery_summary = get_announcement_delivery_summary(announcement)
    logs = NotificationDeliveryLog.objects.filter(
        notification__announcement=announcement
    ).select_related('notification__recipient_user').order_by('-attempted_at')[:20]

    context = {
        'school': school,
        'announcement': announcement,
        'delivery_summary': delivery_summary,
        'logs': logs,
    }
    return render(request, 'communication/announcement_detail.html', context)


@login_required
def announcement_edit(request, pk):
    """
    Edit existing announcement.
    """
    school = resolve_school(request)
    announcement = get_object_or_404(Announcement, pk=pk, school=school)

    if request.method == 'POST':
        form = AnnouncementForm(request.POST, request.FILES, instance=announcement, school=school)
        if form.is_valid():
            announcement = form.save()
            messages.success(request, f"Announcement '{announcement.title}' updated successfully.")
            return redirect('communication:announcement_detail', pk=announcement.pk)
    else:
        form = AnnouncementForm(instance=announcement, school=school)

    context = {
        'school': school,
        'announcement': announcement,
        'form': form,
        'is_edit': True,
    }
    return render(request, 'communication/announcement_form.html', context)


@login_required
@require_POST
def announcement_publish(request, pk):
    """
    Publishes a draft or scheduled announcement immediately.
    """
    school = resolve_school(request)
    announcement = get_object_or_404(Announcement, pk=pk, school=school)

    notif_count = publish_announcement(announcement, published_by=request.user)
    messages.success(request, f"Announcement published! Dispatched {notif_count} notification(s).")
    return redirect('communication:announcement_detail', pk=announcement.pk)


@login_required
@require_POST
def announcement_archive(request, pk):
    """
    Archives an announcement.
    """
    school = resolve_school(request)
    announcement = get_object_or_404(Announcement, pk=pk, school=school)
    announcement.status = Announcement.STATUS_ARCHIVED
    announcement.save(update_fields=['status'])
    messages.info(request, f"Announcement '{announcement.title}' archived.")
    return redirect('communication:announcement_list')


@login_required
def template_list(request):
    """
    Manage notification message templates.
    """
    school = resolve_school(request)
    templates = NotificationTemplate.objects.filter(school=school)

    if request.method == 'POST':
        form = NotificationTemplateForm(request.POST)
        if form.is_valid():
            tmpl = form.save(commit=False)
            tmpl.school = school
            tmpl.created_by = request.user
            tmpl.save()
            messages.success(request, f"Template '{tmpl.name}' created.")
            return redirect('communication:template_list')
    else:
        form = NotificationTemplateForm()

    context = {
        'school': school,
        'templates': templates,
        'form': form,
    }
    return render(request, 'communication/templates.html', context)


@login_required
def delivery_logs_view(request):
    """
    View global communication delivery logs for audit and tracking.
    """
    school = resolve_school(request)
    logs = NotificationDeliveryLog.objects.filter(
        notification__school=school
    ).select_related('notification__recipient_user', 'notification__announcement').order_by('-attempted_at')[:100]

    context = {
        'school': school,
        'logs': logs,
    }
    return render(request, 'communication/delivery_logs.html', context)


# ---------------------------------------------------------------------------
# In-App Notification Center (For All Authenticated Users)
# ---------------------------------------------------------------------------

@login_required
def notification_center(request):
    """
    In-app notification center displaying user's personal notifications.
    """
    school = resolve_school(request)
    unread_only = request.GET.get('unread') == '1'
    category_filter = request.GET.get('type')

    notifications = get_user_notifications(
        user=request.user,
        school=school,
        unread_only=unread_only,
        notification_type=category_filter
    )
    unread_count = get_user_unread_count(request.user, school)

    context = {
        'school': school,
        'notifications': notifications,
        'unread_count': unread_count,
        'unread_only': unread_only,
        'category_filter': category_filter,
    }
    return render(request, 'notifications/notification_center.html', context)


@login_required
def notification_read(request, pk):
    """
    Marks a notification as read and redirects to relevant entity or back.
    """
    notification = get_object_or_404(Notification, pk=pk, recipient_user=request.user)
    mark_notification_as_read(notification, request.user)

    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('format') == 'json':
        return JsonResponse({'status': 'success', 'notification_id': pk, 'is_read': True})

    if notification.announcement:
        return redirect('communication:announcement_detail', pk=notification.announcement.pk)

    return redirect('communication:notification_center')


@login_required
@require_POST
def notification_mark_all_read(request):
    """
    Marks all notifications for the current user as read.
    """
    school = resolve_school(request)
    count = mark_all_notifications_read(request.user, school)

    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('format') == 'json':
        return JsonResponse({'status': 'success', 'marked_read': count})

    messages.success(request, f"Marked {count} notification(s) as read.")
    return redirect('communication:notification_center')


@login_required
def notification_preferences_view(request):
    """
    Manage personal notification preferences.
    """
    school = resolve_school(request)
    pref, _ = NotificationPreference.objects.get_or_create(school=school, user=request.user)

    if request.method == 'POST':
        form = NotificationPreferenceForm(request.POST, instance=pref)
        if form.is_valid():
            form.save()
            messages.success(request, "Notification preferences updated successfully.")
            return redirect('communication:notification_preferences')
    else:
        form = NotificationPreferenceForm(instance=pref)

    context = {
        'school': school,
        'form': form,
        'pref': pref,
    }
    return render(request, 'notifications/preferences.html', context)
