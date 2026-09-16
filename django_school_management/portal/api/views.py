"""
PrimeSoul Unified Portal - REST API Views
Secure, role-aware API endpoints for Parent, Student, and Teacher portals.
Enforces multi-tenant scoping and IDOR prevention on every request.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.exceptions import PermissionDenied, NotFound

from django_school_management.portal.permissions import (
    resolve_portal_school,
    get_parent_children,
    get_parent_selected_child,
    get_student_for_user,
    get_teacher_for_user,
    get_employee_for_user,
    IsPortalParent,
    IsPortalStudent,
    IsPortalTeacher,
)
from django_school_management.portal.selectors import portal_selectors
from django_school_management.portal.api.serializers import (
    PortalNoticeSerializer,
    PortalStudentSummarySerializer,
    PortalAttendanceRecordSerializer,
    PortalFeeInstallmentSerializer,
    PortalFeeInvoiceSerializer,
    PortalFeeReceiptSerializer,
    PortalExamResultSerializer,
    PortalTimetableEntrySerializer,
    PortalLeaveBalanceSerializer,
    PortalPayrollRecordSerializer,
)


# ─────────────────────────────────────────────────────────────
# 1. PARENT PORTAL API ENDPOINTS
# ─────────────────────────────────────────────────────────────

class ParentDashboardAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsPortalParent]

    def get(self, request):
        school = resolve_portal_school(request)
        student_id = request.query_params.get('student_id')
        child = get_parent_selected_child(request, school, student_id=student_id)
        data = portal_selectors.get_parent_portal_dashboard(request.user, school, child)

        return Response({
            'has_children': data['has_children'],
            'children_count': data['children_count'],
            'children': PortalStudentSummarySerializer(data['children'], many=True).data,
            'selected_child': PortalStudentSummarySerializer(data['selected_child']).data if data['selected_child'] else None,
            'attendance_percentage': data['attendance'].get('percentage', 0.0) if data.get('attendance') else 0.0,
            'total_outstanding_fees': str(data['fees'].get('total_outstanding', '0.00')) if data.get('fees') else '0.00',
            'latest_result': PortalExamResultSerializer(data['latest_result']['result']).data if data.get('latest_result') else None,
            'timetable_today_count': len(data.get('timetable_today', [])),
            'notices': PortalNoticeSerializer(data.get('notices', []), many=True).data,
        })


class ParentChildrenAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsPortalParent]

    def get(self, request):
        school = resolve_portal_school(request)
        children = get_parent_children(request.user, school)
        return Response(PortalStudentSummarySerializer(children, many=True).data)


class ParentChildDetailAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsPortalParent]

    def get(self, request, pk):
        school = resolve_portal_school(request)
        allowed = {c.id: c for c in get_parent_children(request.user, school)}
        if pk not in allowed:
            raise PermissionDenied("Unauthorized child access.")
        return Response(PortalStudentSummarySerializer(allowed[pk]).data)


class ParentAttendanceAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsPortalParent]

    def get(self, request):
        school = resolve_portal_school(request)
        student_id = request.query_params.get('student_id')
        child = get_parent_selected_child(request, school, student_id=student_id)
        if not child:
            return Response({'percentage': 0.0, 'records': []})

        att_data = portal_selectors.get_student_portal_attendance(child, school)
        return Response({
            'student_id': child.id,
            'student_name': child.name,
            'percentage': att_data['percentage'],
            'total_records': att_data['total_records'],
            'present_count': att_data['present_count'],
            'absent_count': att_data['absent_count'],
            'late_count': att_data['late_count'],
            'today_status': att_data['today_status'],
            'recent_records': PortalAttendanceRecordSerializer(att_data['recent_records'], many=True).data,
        })


class ParentFeesAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsPortalParent]

    def get(self, request):
        school = resolve_portal_school(request)
        student_id = request.query_params.get('student_id')
        child = get_parent_selected_child(request, school, student_id=student_id)
        if not child:
            return Response({'total_outstanding': '0.00', 'installments': []})

        fee_data = portal_selectors.get_student_portal_fees(child, school)
        return Response({
            'student_id': child.id,
            'total_payable': str(fee_data['total_payable']),
            'total_paid': str(fee_data['total_paid']),
            'total_outstanding': str(fee_data['total_outstanding']),
            'installments': PortalFeeInstallmentSerializer(fee_data['installments'], many=True).data,
            'invoices': PortalFeeInvoiceSerializer(fee_data['invoices'], many=True).data,
            'receipts': PortalFeeReceiptSerializer(fee_data['receipts'], many=True).data,
        })


class ParentResultsAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsPortalParent]

    def get(self, request):
        school = resolve_portal_school(request)
        student_id = request.query_params.get('student_id')
        child = get_parent_selected_child(request, school, student_id=student_id)
        if not child:
            return Response({'student_id': None, 'results': []})

        results = portal_selectors.get_student_portal_results(child, school)
        raw_results = [r['result'] for r in results]
        return Response({
            'student_id': child.id,
            'results': PortalExamResultSerializer(raw_results, many=True).data
        })


class ParentTimetableAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsPortalParent]

    def get(self, request):
        school = resolve_portal_school(request)
        student_id = request.query_params.get('student_id')
        child = get_parent_selected_child(request, school, student_id=student_id)
        if not child:
            return Response({'today_entries': []})

        tt_data = portal_selectors.get_student_portal_timetable(child, school)
        return Response({
            'student_id': child.id,
            'section_name': child.section.name if child.section else '',
            'today_entries': PortalTimetableEntrySerializer(tt_data['today_entries'], many=True).data,
        })


class ParentTransportAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsPortalParent]

    def get(self, request):
        school = resolve_portal_school(request)
        student_id = request.query_params.get('student_id')
        child = get_parent_selected_child(request, school, student_id=student_id)
        if not child:
            return Response(None)

        info = portal_selectors.get_student_portal_transport(child, school)
        if not info:
            return Response({'is_assigned': False})

        return Response({
            'is_assigned': True,
            'route_name': info['route'].name if info.get('route') else '',
            'pickup_stop': info['pickup_stop'].name if info.get('pickup_stop') else '',
            'drop_stop': info['drop_stop'].name if info.get('drop_stop') else '',
            'vehicle_number': info['vehicle'].registration_number if info.get('vehicle') else '',
            'driver_name': info.get('driver_name', ''),
            'driver_phone': info.get('driver_phone', ''),
        })


class ParentLibraryAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsPortalParent]

    def get(self, request):
        school = resolve_portal_school(request)
        student_id = request.query_params.get('student_id')
        child = get_parent_selected_child(request, school, student_id=student_id)
        if not child:
            return Response(None)

        lib_info = portal_selectors.get_student_portal_library(child, school)
        if not lib_info:
            return Response({'is_member': False})

        return Response({
            'is_member': True,
            'member_code': lib_info['member'].member_code,
            'active_loans_count': len(lib_info['active_issues']),
            'outstanding_fines': str(lib_info['outstanding_fines']),
        })


class ParentNoticesAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsPortalParent]

    def get(self, request):
        school = resolve_portal_school(request)
        notices = portal_selectors.get_portal_notices(school, request.user)
        return Response(PortalNoticeSerializer(notices, many=True).data)


# ─────────────────────────────────────────────────────────────
# 2. STUDENT PORTAL API ENDPOINTS
# ─────────────────────────────────────────────────────────────

class StudentDashboardAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsPortalStudent]

    def get(self, request):
        school = resolve_portal_school(request)
        student = get_student_for_user(request.user, school)
        if not student:
            raise NotFound("Student profile not found.")

        data = portal_selectors.get_student_portal_dashboard(student, school)
        return Response({
            'student': PortalStudentSummarySerializer(student).data,
            'attendance_percentage': data['attendance'].get('percentage', 0.0),
            'total_outstanding_fees': str(data['fees'].get('total_outstanding', '0.00')),
            'latest_result': PortalExamResultSerializer(data['latest_result']['result']).data if data.get('latest_result') else None,
            'today_timetable_count': len(data.get('timetable_today', [])),
            'notices': PortalNoticeSerializer(data.get('notices', []), many=True).data,
        })


class StudentProfileAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsPortalStudent]

    def get(self, request):
        school = resolve_portal_school(request)
        student = get_student_for_user(request.user, school)
        if not student:
            raise NotFound("Student profile not found.")
        return Response(PortalStudentSummarySerializer(student).data)


class StudentAttendanceAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsPortalStudent]

    def get(self, request):
        school = resolve_portal_school(request)
        student = get_student_for_user(request.user, school)
        if not student:
            raise NotFound("Student profile not found.")

        att_data = portal_selectors.get_student_portal_attendance(student, school)
        return Response({
            'percentage': att_data['percentage'],
            'total_records': att_data['total_records'],
            'present_count': att_data['present_count'],
            'absent_count': att_data['absent_count'],
            'today_status': att_data['today_status'],
            'recent_records': PortalAttendanceRecordSerializer(att_data['recent_records'], many=True).data,
        })


class StudentFeesAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsPortalStudent]

    def get(self, request):
        school = resolve_portal_school(request)
        student = get_student_for_user(request.user, school)
        if not student:
            raise NotFound("Student profile not found.")

        fee_data = portal_selectors.get_student_portal_fees(student, school)
        return Response({
            'total_payable': str(fee_data['total_payable']),
            'total_paid': str(fee_data['total_paid']),
            'total_outstanding': str(fee_data['total_outstanding']),
            'installments': PortalFeeInstallmentSerializer(fee_data['installments'], many=True).data,
            'invoices': PortalFeeInvoiceSerializer(fee_data['invoices'], many=True).data,
            'receipts': PortalFeeReceiptSerializer(fee_data['receipts'], many=True).data,
        })


class StudentResultsAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsPortalStudent]

    def get(self, request):
        school = resolve_portal_school(request)
        student = get_student_for_user(request.user, school)
        if not student:
            raise NotFound("Student profile not found.")

        results = portal_selectors.get_student_portal_results(student, school)
        raw_results = [r['result'] for r in results]
        return Response({
            'student_id': student.id,
            'results': PortalExamResultSerializer(raw_results, many=True).data
        })


class StudentTimetableAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsPortalStudent]

    def get(self, request):
        school = resolve_portal_school(request)
        student = get_student_for_user(request.user, school)
        if not student:
            raise NotFound("Student profile not found.")

        tt_data = portal_selectors.get_student_portal_timetable(student, school)
        return Response({
            'section_name': student.section.name if student.section else '',
            'today_entries': PortalTimetableEntrySerializer(tt_data['today_entries'], many=True).data,
        })


class StudentTransportAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsPortalStudent]

    def get(self, request):
        school = resolve_portal_school(request)
        student = get_student_for_user(request.user, school)
        if not student:
            raise NotFound("Student profile not found.")

        info = portal_selectors.get_student_portal_transport(student, school)
        if not info:
            return Response({'is_assigned': False})

        return Response({
            'is_assigned': True,
            'route_name': info['route'].name if info.get('route') else '',
            'pickup_stop': info['pickup_stop'].name if info.get('pickup_stop') else '',
            'drop_stop': info['drop_stop'].name if info.get('drop_stop') else '',
            'vehicle_number': info['vehicle'].registration_number if info.get('vehicle') else '',
            'driver_name': info.get('driver_name', ''),
        })


class StudentLibraryAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsPortalStudent]

    def get(self, request):
        school = resolve_portal_school(request)
        student = get_student_for_user(request.user, school)
        if not student:
            raise NotFound("Student profile not found.")

        lib_info = portal_selectors.get_student_portal_library(student, school)
        if not lib_info:
            return Response({'is_member': False})

        return Response({
            'is_member': True,
            'member_code': lib_info['member'].member_code,
            'active_loans_count': len(lib_info['active_issues']),
            'outstanding_fines': str(lib_info['outstanding_fines']),
        })


class StudentNoticesAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsPortalStudent]

    def get(self, request):
        school = resolve_portal_school(request)
        notices = portal_selectors.get_portal_notices(school, request.user)
        return Response(PortalNoticeSerializer(notices, many=True).data)


# ─────────────────────────────────────────────────────────────
# 3. TEACHER PORTAL API ENDPOINTS
# ─────────────────────────────────────────────────────────────

class TeacherDashboardAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsPortalTeacher]

    def get(self, request):
        school = resolve_portal_school(request)
        data = portal_selectors.get_teacher_portal_dashboard(request.user, school)
        assigned_classes = portal_selectors.get_teacher_assigned_classes(data.get('teacher'), school)

        return Response({
            'teacher_name': data['teacher'].name if data.get('teacher') else '',
            'assigned_classes_count': len(assigned_classes),
            'today_classes_count': len(data.get('today_schedule', [])),
            'pending_attendance_count': len([s for s in data.get('pending_attendance', []) if not s.get('is_marked')]),
            'leave_balances': PortalLeaveBalanceSerializer(data['leave_summary'].get('balances', []), many=True).data,
            'latest_payslip': PortalPayrollRecordSerializer(data['latest_payslip']).data if data.get('latest_payslip') else None,
            'notices': PortalNoticeSerializer(data.get('notices', []), many=True).data,
        })


class TeacherTimetableAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsPortalTeacher]

    def get(self, request):
        school = resolve_portal_school(request)
        teacher = get_teacher_for_user(request.user, school)
        if not teacher:
            raise NotFound("Teacher profile not found.")

        tt_data = portal_selectors.get_teacher_portal_timetable(teacher, school)
        matrix = tt_data.get('matrix', {})
        return Response({
            'total_entries': matrix.get('total_entries', 0) if matrix else 0,
            'working_days_count': len(matrix.get('working_days', [])) if matrix else 0,
        })


class TeacherClassesAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsPortalTeacher]

    def get(self, request):
        school = resolve_portal_school(request)
        teacher = get_teacher_for_user(request.user, school)
        if not teacher:
            raise NotFound("Teacher profile not found.")

        classes = portal_selectors.get_teacher_assigned_classes(teacher, school)
        res = []
        for c in classes:
            res.append({
                'grade': c['grade_level'].name if c['grade_level'] else '',
                'section': c['section'].name if c['section'] else '',
                'subject': c['subject'].name if c['subject'] else '',
                'student_count': c['student_count'],
            })
        return Response(res)


class TeacherStudentsAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsPortalTeacher]

    def get(self, request):
        school = resolve_portal_school(request)
        teacher = get_teacher_for_user(request.user, school)
        if not teacher:
            raise NotFound("Teacher profile not found.")

        section_id = request.query_params.get('section_id')
        roster = portal_selectors.get_teacher_assigned_students(teacher, school, section_id=section_id)
        return Response(roster)


class TeacherAttendanceAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsPortalTeacher]

    def get(self, request):
        school = resolve_portal_school(request)
        data = portal_selectors.get_teacher_portal_dashboard(request.user, school)
        pending = data.get('pending_attendance', [])
        res = []
        for p in pending:
            res.append({
                'section_id': p['section'].id,
                'section_name': f"{p['grade_level'].name} - {p['section'].name}",
                'is_marked': p['is_marked'],
                'records_count': p['records_count'],
            })
        return Response(res)


class TeacherLeaveAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsPortalTeacher]

    def get(self, request):
        school = resolve_portal_school(request)
        employee = get_employee_for_user(request.user, school)
        if not employee:
            raise NotFound("Employee profile not found.")

        summary = portal_selectors.get_teacher_portal_leaves(employee, school)
        return Response({
            'balances': PortalLeaveBalanceSerializer(summary.get('balances', []), many=True).data,
        })


class TeacherPayslipsAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsPortalTeacher]

    def get(self, request):
        school = resolve_portal_school(request)
        employee = get_employee_for_user(request.user, school)
        if not employee:
            raise NotFound("Employee profile not found.")

        payslips = portal_selectors.get_teacher_portal_payslips(employee, school)
        return Response(PortalPayrollRecordSerializer(payslips, many=True).data)


class TeacherNoticesAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsPortalTeacher]

    def get(self, request):
        school = resolve_portal_school(request)
        notices = portal_selectors.get_portal_notices(school, request.user)
        return Response(PortalNoticeSerializer(notices, many=True).data)
