"""
PrimeSoul School ERP - Phase 17: Reports REST Serializers
"""
from rest_framework import serializers


class ExecutiveDashboardSerializer(serializers.Serializer):
    student_stats = serializers.DictField()
    attendance_today = serializers.DictField()
    academics = serializers.DictField()
    examination = serializers.DictField()
    finance = serializers.DictField()
    admissions = serializers.DictField()
    transport = serializers.DictField()
    library = serializers.DictField()
    hr = serializers.DictField()
    inventory = serializers.DictField()


class FinanceReportSerializer(serializers.Serializer):
    totals = serializers.DictField()
    method_breakdown = serializers.ListField()


class AcademicReportSerializer(serializers.Serializer):
    total_enrollment = serializers.IntegerField()
    class_strengths = serializers.ListField()


class AttendanceReportSerializer(serializers.Serializer):
    date = serializers.CharField()
    daily_summary = serializers.DictField()
    class_breakdown = serializers.ListField()


class ExaminationReportSerializer(serializers.Serializer):
    metrics = serializers.DictField()
    pass_percentage = serializers.DecimalField(max_digits=5, decimal_places=2)


class AdmissionsReportSerializer(serializers.Serializer):
    enquiry_count = serializers.IntegerField()
    app_pipeline = serializers.DictField()
    conversion_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    class_wise = serializers.ListField()
