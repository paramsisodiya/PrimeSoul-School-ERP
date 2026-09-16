from django.urls import path
from . import views

app_name = 'fees'

urlpatterns = [
    path('', views.fee_dashboard_view, name='dashboard'),
    path('dashboard/', views.fee_dashboard_view, name='fee_dashboard'),
    path('heads/', views.fee_heads_view, name='fee_heads'),
    path('structures/', views.fee_structures_view, name='fee_structures'),
    path('student-fees/', views.student_fees_view, name='student_fees'),
    path('installments/', views.installments_view, name='installments'),
    path('concessions/', views.concessions_view, name='concessions'),
    path('invoices/', views.invoices_view, name='invoices'),
    path('payments/', views.payments_view, name='payments'),
    path('receipts/', views.receipts_view, name='receipts'),
    path('receipts/<int:pk>/modal/', views.receipt_modal_detail, name='receipt_modal_detail'),
    path('receipts/<int:pk>/pdf/', views.receipt_pdf_download_view, name='receipt_pdf'),
]

