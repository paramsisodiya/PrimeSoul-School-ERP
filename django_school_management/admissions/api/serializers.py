from rest_framework import serializers
from django_school_management.admissions.models import (
    AdmissionSession, AdmissionClassConfig, AdmissionEnquiry,
    AdmissionApplication, AdmissionDocument, AdmissionInterview, AdmissionAssessment
)
from django_school_management.academics.models import GradeLevel, Section
from django_school_management.utils.india_localization import (
    is_valid_indian_mobile, clean_indian_mobile
)


class AdmissionSessionSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    academic_year_name = serializers.CharField(source='academic_year.name', read_only=True)

    class Meta:
        model = AdmissionSession
        fields = [
            'id', 'school', 'name', 'academic_year', 'academic_year_name',
            'application_start', 'application_end', 'admission_start', 'admission_end',
            'status', 'status_display', 'application_number_prefix', 'admission_number_prefix',
            'active', 'created'
        ]
        read_only_fields = ['school', 'created']


class AdmissionClassConfigSerializer(serializers.ModelSerializer):
    grade_name = serializers.CharField(source='grade_level.name', read_only=True)

    class Meta:
        model = AdmissionClassConfig
        fields = [
            'id', 'school', 'admission_session', 'grade_level', 'grade_name',
            'total_seats', 'reserved_seats', 'application_fee', 'active', 'created'
        ]
        read_only_fields = ['school', 'created']


class AdmissionEnquirySerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    source_display = serializers.CharField(source='get_source_display', read_only=True)
    grade_name = serializers.CharField(source='interested_grade.name', read_only=True)

    class Meta:
        model = AdmissionEnquiry
        fields = [
            'id', 'school', 'admission_session', 'enquiry_number',
            'student_name', 'parent_name', 'mobile', 'email',
            'interested_grade', 'grade_name', 'source', 'source_display',
            'notes', 'status', 'status_display', 'assigned_to', 'created'
        ]
        read_only_fields = ['school', 'enquiry_number', 'created']

    def validate_mobile(self, value):
        if not is_valid_indian_mobile(value):
            raise serializers.ValidationError("Please provide a valid 10-digit Indian mobile number.")
        return clean_indian_mobile(value)


class AdmissionDocumentSerializer(serializers.ModelSerializer):
    document_type_display = serializers.CharField(source='get_document_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = AdmissionDocument
        fields = [
            'id', 'school', 'application', 'document_type', 'document_type_display',
            'title', 'file', 'status', 'status_display', 'uploaded_at',
            'verified_at', 'verified_by', 'rejection_reason'
        ]
        read_only_fields = ['school', 'uploaded_at', 'verified_at', 'verified_by']


class AdmissionInterviewSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    interviewer_name = serializers.CharField(source='interviewer.get_full_name', read_only=True)

    class Meta:
        model = AdmissionInterview
        fields = [
            'id', 'school', 'application', 'scheduled_at', 'location',
            'interviewer', 'interviewer_name', 'status', 'status_display',
            'remarks', 'score', 'created'
        ]
        read_only_fields = ['school', 'created']


class AdmissionAssessmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdmissionAssessment
        fields = [
            'id', 'school', 'application', 'subject', 'max_score',
            'score', 'remarks', 'assessed_by', 'created'
        ]
        read_only_fields = ['school', 'created']


class AdmissionApplicationSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    fee_status_display = serializers.CharField(source='get_application_fee_status_display', read_only=True)
    grade_name = serializers.CharField(source='requested_grade.name', read_only=True)
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    documents = AdmissionDocumentSerializer(many=True, read_only=True)
    interviews = AdmissionInterviewSerializer(many=True, read_only=True)
    assessments = AdmissionAssessmentSerializer(many=True, read_only=True)

    class Meta:
        model = AdmissionApplication
        fields = [
            'id', 'school', 'admission_session', 'enquiry', 'application_number',
            'first_name', 'middle_name', 'last_name', 'full_name',
            'date_of_birth', 'gender', 'blood_group', 'nationality', 'category', 'aadhaar_number',
            'requested_grade', 'grade_name', 'requested_stream',
            'previous_school', 'previous_school_tc_number', 'previous_grade', 'previous_percentage',
            'father_name', 'father_mobile', 'father_email', 'father_occupation', 'father_aadhaar',
            'mother_name', 'mother_mobile', 'mother_email', 'mother_occupation', 'mother_aadhaar',
            'guardian_name', 'guardian_mobile', 'guardian_relation',
            'current_address', 'permanent_address', 'emergency_contact_name', 'emergency_contact_number',
            'status', 'status_display', 'application_fee_status', 'fee_status_display',
            'submitted_at', 'reviewed_at', 'reviewed_by', 'rejection_reason', 'remarks',
            'admitted_student', 'admitted_at', 'documents', 'interviews', 'assessments', 'created'
        ]
        read_only_fields = ['school', 'application_number', 'admitted_student', 'admitted_at', 'created', 'submitted_at', 'reviewed_at', 'reviewed_by']


class PublicAdmissionApplySerializer(serializers.ModelSerializer):
    """
    Serializer for public anonymous online applications.
    """
    class Meta:
        model = AdmissionApplication
        fields = [
            'first_name', 'middle_name', 'last_name',
            'date_of_birth', 'gender', 'blood_group', 'category', 'aadhaar_number',
            'requested_grade', 'previous_school', 'previous_grade', 'previous_percentage',
            'father_name', 'father_mobile', 'father_email', 'father_occupation',
            'mother_name', 'mother_mobile', 'mother_email',
            'current_address', 'emergency_contact_number'
        ]

    def validate_father_mobile(self, value):
        if not is_valid_indian_mobile(value):
            raise serializers.ValidationError("Please provide a valid 10-digit Indian mobile number.")
        return clean_indian_mobile(value)


class PublicAdmissionStatusSerializer(serializers.ModelSerializer):
    """
    Safe public application status representation without leaking internal database IDs.
    """
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    grade_name = serializers.CharField(source='requested_grade.name', read_only=True)
    session_name = serializers.CharField(source='admission_session.name', read_only=True)
    full_name = serializers.CharField(source='get_full_name', read_only=True)

    class Meta:
        model = AdmissionApplication
        fields = [
            'application_number', 'full_name', 'grade_name', 'session_name',
            'status', 'status_display', 'submitted_at', 'remarks'
        ]


class AdmissionConvertSerializer(serializers.Serializer):
    section_id = serializers.IntegerField(required=False, allow_null=True)
    roll_number = serializers.CharField(required=False, allow_blank=True)
