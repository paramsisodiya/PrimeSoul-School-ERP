"""
PrimeSoul School ERP - Phase 17: Reports REST API Views
Multi-tenant, RBAC-protected endpoints for executive intelligence and domain analytics.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from django.core.exceptions import PermissionDenied

from django_school_management.accounts.roles import Role, user_has_role
from django_school_management.tenants.models import School
from django_school_management.reports.selectors import report_selectors


def get_request_school(request):
    """Safely resolves school tenant from request."""
    if hasattr(request, 'tenant') and request.tenant:
        return request.tenant
    if hasattr(request, 'school') and request.school:
        return request.school
    if request.user.is_authenticated and getattr(request.user, 'school', None):
        return request.user.school
    return School.objects.first()


def _is_restricted_user(user):
    if user.is_superuser:
        return False
    return user_has_role(user, Role.PARENT, Role.STUDENT)


class ExecutiveDashboardAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if _is_restricted_user(request.user):
            return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        
        school = get_request_school(request)
        kpis = report_selectors.get_executive_dashboard_kpis(school)

        return Response({
            'student_stats': kpis['student_stats'],
            'attendance_today': kpis['attendance_today'],
            'academics': {
                'active_year': str(kpis['academics']['active_year']) if kpis['academics']['active_year'] else None,
                'total_classes': kpis['academics']['total_classes'],
                'total_sections': kpis['academics']['total_sections'],
                'total_teachers': kpis['academics']['total_teachers'],
            },
            'examination': {
                'total_exams': kpis['examination']['total_exams'],
                'published_exams': kpis['examination']['published_exams'],
                'avg_percentage': str(kpis['examination']['avg_percentage']),
                'pass_rate': str(kpis['examination']['pass_rate']),
            },
            'finance': {
                'total_invoiced': str(kpis['finance']['total_invoiced']),
                'total_paid': str(kpis['finance']['total_paid']),
                'total_due': str(kpis['finance']['total_due']),
                'overdue_invoices': kpis['finance']['overdue_invoices'],
                'collection_rate': str(kpis['finance']['collection_rate']),
            },
            'admissions': {
                'total_enquiries': kpis['admissions']['total_enquiries'],
                'total_apps': kpis['admissions']['total_apps'],
                'admitted': kpis['admissions']['admitted'],
                'conversion_rate': str(kpis['admissions']['conversion_rate']),
            },
            'transport': kpis['transport'],
            'library': kpis['library'],
            'hr': kpis['hr'],
            'inventory': kpis['inventory'],
        })


class FinanceReportsAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if _is_restricted_user(request.user):
            return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        
        school = get_request_school(request)
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        academic_year_id = request.query_params.get('academic_year')
        payment_method = request.query_params.get('payment_method')

        data = report_selectors.get_finance_reports(
            school=school,
            start_date=start_date,
            end_date=end_date,
            academic_year_id=int(academic_year_id) if academic_year_id else None,
            payment_method=payment_method
        )

        return Response({
            'totals': {
                'total_invoiced': str(data['totals']['total_invoiced']),
                'total_collected': str(data['totals']['total_collected']),
                'total_outstanding': str(data['totals']['total_outstanding']),
                'invoice_count': data['totals']['invoice_count'],
            },
            'total_invoiced': str(data['totals']['total_invoiced']),
            'total_collected': str(data['totals']['total_collected']),
            'total_outstanding': str(data['totals']['total_outstanding']),
            'invoice_count': data['totals']['invoice_count'],
            'method_breakdown': data['method_breakdown'],
        })


class HRReportsAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if _is_restricted_user(request.user):
            return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        
        school = get_request_school(request)
        data = report_selectors.get_hr_reports(school)

        return Response({
            'total_employees': data['total_employees'],
            'dept_headcounts': [{'department': d.name, 'count': d.employee_count} for d in data['dept_headcounts']],
            'employees_list': data['employees_list'],
        })


class AcademicsReportsAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if _is_restricted_user(request.user):
            return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        
        school = get_request_school(request)
        data = report_selectors.get_academic_reports(school)
        return Response({
            'total_enrollment': data['total_enrollment'],
            'class_strengths': data['class_strengths'],
        })


class AttendanceReportsAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if _is_restricted_user(request.user):
            return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        
        school = get_request_school(request)
        target_date = request.query_params.get('date')
        data = report_selectors.get_attendance_reports(school, date=target_date)
        return Response({
            'date': str(data['date']),
            'daily_summary': data['daily_summary'],
            'class_breakdown': data['class_breakdown'],
        })


class ExaminationReportsAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if _is_restricted_user(request.user):
            return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        
        school = get_request_school(request)
        exam_id = request.query_params.get('exam_id')
        data = report_selectors.get_examination_reports(school, exam_id=int(exam_id) if exam_id else None)
        return Response({
            'metrics': data['metrics'],
            'pass_percentage': str(data.get('pass_percentage', 0.0)),
        })


class AdmissionsReportsAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if _is_restricted_user(request.user):
            return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        
        school = get_request_school(request)
        session_id = request.query_params.get('session_id')
        data = report_selectors.get_admissions_reports(school, session_id=int(session_id) if session_id else None)
        return Response({
            'enquiry_count': data['enquiry_count'],
            'app_pipeline': data['app_pipeline'],
            'conversion_rate': str(data['conversion_rate']),
            'class_wise': data['class_wise'],
        })


class TransportReportsAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if _is_restricted_user(request.user):
            return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        
        school = get_request_school(request)
        data = report_selectors.get_transport_reports(school)
        return Response({
            'total_capacity': data['total_capacity'],
            'total_allocated': data['total_allocated'],
            'routes_summary': data['routes_summary'],
        })


class LibraryReportsAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if _is_restricted_user(request.user):
            return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        
        school = get_request_school(request)
        data = report_selectors.get_library_reports(school)
        return Response({
            'stats': data['stats'],
            'fines': {
                'total_fines': str(data['fines']['total_fines']),
                'collected_fines': str(data['fines']['collected_fines']),
                'pending_fines': str(data['fines']['pending_fines']),
            }
        })


class InventoryReportsAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if _is_restricted_user(request.user):
            return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        
        school = get_request_school(request)
        data = report_selectors.get_inventory_reports(school)
        return Response({
            'total_asset_valuation': str(data['total_asset_valuation']),
            'low_stock_count': data['low_stock_items'].count(),
            'out_of_stock_count': data['out_of_stock_items'].count(),
        })
