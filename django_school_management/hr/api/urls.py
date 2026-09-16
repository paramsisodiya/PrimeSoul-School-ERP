from django.urls import path
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'departments', views.DepartmentViewSet, basename='department')
router.register(r'designations', views.HRDesignationViewSet, basename='hr-designation')
router.register(r'employees', views.EmployeeViewSet, basename='employee')
router.register(r'documents', views.EmployeeDocumentViewSet, basename='employee-document')
router.register(r'leave-types', views.LeaveTypeViewSet, basename='leave-type')
router.register(r'leave-balances', views.LeaveBalanceViewSet, basename='leave-balance')
router.register(r'leave-requests', views.LeaveRequestViewSet, basename='leave-request')
router.register(r'attendance', views.EmployeeAttendanceViewSet, basename='employee-attendance')
router.register(r'salary-components', views.SalaryComponentViewSet, basename='salary-component')
router.register(r'salary-structures', views.EmployeeSalaryStructureViewSet, basename='salary-structure')
router.register(r'payroll-periods', views.PayrollPeriodViewSet, basename='payroll-period')
router.register(r'payroll-records', views.PayrollRecordViewSet, basename='payroll-record')

urlpatterns = [
    path('dashboard/', views.HRDashboardAPIView.as_view(), name='api_hr_dashboard'),
    path('my-profile/', views.MyEmployeeProfileAPIView.as_view(), name='api_my_profile'),
    path('my-leaves/', views.MyLeaveAPIView.as_view(), name='api_my_leaves'),
    path('my-payslips/', views.MyPayslipsAPIView.as_view(), name='api_my_payslips'),
    path('leave/apply/', views.ApplyLeaveAPIView.as_view(), name='api_leave_apply'),
    path('payroll/process/', views.ProcessPayrollAPIView.as_view(), name='api_payroll_process'),
] + router.urls
