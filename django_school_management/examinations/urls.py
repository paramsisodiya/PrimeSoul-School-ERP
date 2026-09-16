from django.urls import path
from . import views

app_name = 'examinations'

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),

    # Sessions
    path('sessions/', views.session_list, name='session_list'),
    path('sessions/create/', views.session_create, name='session_create'),
    path('sessions/<int:pk>/edit/', views.session_edit, name='session_edit'),

    # Exams
    path('exams/', views.exam_list, name='exam_list'),
    path('exams/create/', views.exam_create, name='exam_create'),
    path('exams/<int:pk>/edit/', views.exam_edit, name='exam_edit'),
    path('exams/<int:exam_id>/subjects/', views.exam_subjects_config, name='exam_subjects'),
    path('exams/<int:exam_id>/subjects/<int:subject_id>/delete/', views.exam_subject_delete, name='exam_subject_delete'),

    # Grade Scales & Bands
    path('grades/', views.grade_scale_list, name='grade_scale_list'),
    path('grades/create/', views.grade_scale_create, name='grade_scale_create'),
    path('grades/<int:pk>/', views.grade_scale_detail, name='grade_scale_detail'),

    # Marks Entry & Correction
    path('marks/', views.marks_entry_view, name='marks_entry'),
    path('marks/<int:pk>/correct/', views.correct_student_mark_view, name='correct_mark'),

    # Results & Workflow Actions
    path('results/', views.results_list_view, name='results_list'),
    path('results/<int:exam_id>/calculate/', views.calculate_results_action, name='calculate_results'),
    path('results/<int:exam_id>/finalize/', views.finalize_results_action, name='finalize_results'),
    path('results/<int:exam_id>/publish/', views.publish_results_action, name='publish_results'),
    path('results/<int:exam_id>/lock/', views.lock_results_action, name='lock_results'),

    # Analytics & History
    path('results/class/', views.class_result_summary_view, name='class_summary_default'),
    path('results/class/<int:exam_id>/', views.class_result_summary_view, name='class_summary'),
    path('results/student/', views.student_result_profile_view, name='student_results_default'),
    path('results/student/<int:student_id>/', views.student_result_profile_view, name='student_results'),

    # Report Card & Marksheet PDF
    path('results/<int:pk>/report-card/', views.report_card_view, name='report_card'),
    path('results/<int:pk>/report-card/pdf/', views.report_card_pdf_view, name='report_card_pdf'),

    # Verification (Namespaced)
    path('verify/<str:verification_code>/', views.public_result_verification_view, name='public_verify_result'),

    # CSV Exports
    path('export/marks/<int:exam_id>/<int:subject_id>/', views.export_marks_csv, name='export_marks_csv'),
    path('export/results/<int:exam_id>/', views.export_results_csv, name='export_results_csv'),
]
