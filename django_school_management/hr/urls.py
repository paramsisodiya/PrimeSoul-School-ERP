from django.urls import path
from . import views

app_name = 'hr'

urlpatterns = [
    path('', views.hr_dashboard, name='dashboard'),
    path('employees/', views.employee_list, name='employees'),
    path('employees/add/', views.employee_create, name='employee_create'),
    path('employees/<int:pk>/', views.employee_detail, name='employee_detail'),
    path('employees/<int:pk>/edit/', views.employee_edit, name='employee_edit'),
    path('departments/', views.department_list, name='departments'),
    path('designations/', views.designation_list, name='designations'),
    path('attendance/', views.attendance_view, name='attendance'),
    path('leaves/', views.leave_list, name='leaves'),
    path('leaves/apply/', views.leave_apply, name='leave_apply'),
    path('leaves/<int:pk>/<str:action>/', views.leave_action, name='leave_action'),
    path('salary-structures/', views.salary_structures_list, name='salary_structures'),
    path('payroll-periods/', views.payroll_periods_list, name='payroll_periods'),
    path('payroll-periods/<int:period_pk>/process/', views.payroll_process_view, name='payroll_process'),
    path('payroll-periods/<int:period_pk>/lock/', views.payroll_lock_view, name='payroll_lock'),
    path('payslips/<int:record_pk>/', views.payslip_detail, name='payslip_detail'),
    path('my-hr/', views.my_hr, name='my_hr'),
]
