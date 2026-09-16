from django.urls import path
from . import views

app_name = 'communication'

urlpatterns = [
    # Communication Management
    path('', views.communication_dashboard, name='dashboard'),
    path('announcements/', views.announcement_list, name='announcement_list'),
    path('announcements/create/', views.announcement_create, name='announcement_create'),
    path('announcements/<int:pk>/', views.announcement_detail, name='announcement_detail'),
    path('announcements/<int:pk>/edit/', views.announcement_edit, name='announcement_edit'),
    path('announcements/<int:pk>/publish/', views.announcement_publish, name='announcement_publish'),
    path('announcements/<int:pk>/archive/', views.announcement_archive, name='announcement_archive'),
    path('templates/', views.template_list, name='template_list'),
    path('delivery-logs/', views.delivery_logs_view, name='delivery_logs'),

    # In-App Notification Center
    path('notifications/', views.notification_center, name='notification_center'),
    path('notifications/<int:pk>/read/', views.notification_read, name='notification_read'),
    path('notifications/mark-all-read/', views.notification_mark_all_read, name='notification_mark_all_read'),
    path('preferences/', views.notification_preferences_view, name='notification_preferences'),
]
