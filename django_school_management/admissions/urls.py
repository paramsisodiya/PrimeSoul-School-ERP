from django.urls import path
from . import views

app_name = 'admissions'

urlpatterns = [
    # Dashboard & Config
    path('', views.admissions_dashboard, name='dashboard'),
    path('sessions/', views.session_list, name='session_list'),
    path('classes/', views.class_config_list, name='class_config_list'),

    # Enquiries
    path('enquiries/', views.enquiry_list, name='enquiry_list'),
    path('enquiries/<int:pk>/', views.enquiry_detail, name='enquiry_detail'),

    # Applications
    path('applications/', views.application_list, name='application_list'),
    path('applications/create/', views.application_create, name='application_create'),
    path('applications/<int:pk>/', views.application_detail, name='application_detail'),
    path('applications/<int:pk>/review/', views.application_review, name='application_review'),
    path('applications/<int:pk>/convert/', views.application_convert, name='application_convert'),

    # Sub-entities
    path('applications/<int:application_id>/documents/upload/', views.document_upload, name='document_upload'),
    path('documents/<int:pk>/verify/', views.document_verify, name='document_verify'),
    path('applications/<int:application_id>/interviews/schedule/', views.interview_schedule, name='interview_schedule'),
    path('applications/<int:application_id>/assessments/record/', views.assessment_record_view, name='assessment_record'),

    # Reports
    path('reports/', views.reports_view, name='reports'),

    # Public-Facing Workflows
    path('public/apply/', views.public_apply, name='public_apply'),
    path('public/status/', views.public_status, name='public_status'),
]
