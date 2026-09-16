from django.contrib import admin
from .models import (
    AdmissionSession, AdmissionClassConfig, AdmissionEnquiry,
    AdmissionApplication, AdmissionDocument, AdmissionInterview, AdmissionAssessment
)


class AdmissionClassConfigInline(admin.TabularInline):
    model = AdmissionClassConfig
    extra = 1


class AdmissionDocumentInline(admin.TabularInline):
    model = AdmissionDocument
    extra = 0
    readonly_fields = ('uploaded_at', 'verified_at', 'verified_by')


class AdmissionInterviewInline(admin.TabularInline):
    model = AdmissionInterview
    extra = 0


class AdmissionAssessmentInline(admin.TabularInline):
    model = AdmissionAssessment
    extra = 0


@admin.register(AdmissionSession)
class AdmissionSessionAdmin(admin.ModelAdmin):
    list_display = ('name', 'school', 'academic_year', 'status', 'application_start', 'application_end', 'active')
    list_filter = ('school', 'status', 'active')
    search_fields = ('name',)
    inlines = [AdmissionClassConfigInline]


@admin.register(AdmissionClassConfig)
class AdmissionClassConfigAdmin(admin.ModelAdmin):
    list_display = ('grade_level', 'admission_session', 'school', 'total_seats', 'reserved_seats', 'application_fee', 'active')
    list_filter = ('school', 'admission_session', 'active')


@admin.register(AdmissionEnquiry)
class AdmissionEnquiryAdmin(admin.ModelAdmin):
    list_display = ('enquiry_number', 'student_name', 'parent_name', 'mobile', 'school', 'interested_grade', 'source', 'status')
    list_filter = ('school', 'status', 'source')
    search_fields = ('enquiry_number', 'student_name', 'parent_name', 'mobile')


@admin.register(AdmissionApplication)
class AdmissionApplicationAdmin(admin.ModelAdmin):
    list_display = ('application_number', 'first_name', 'last_name', 'school', 'requested_grade', 'status', 'application_fee_status', 'admitted_student')
    list_filter = ('school', 'status', 'requested_grade', 'application_fee_status')
    search_fields = ('application_number', 'first_name', 'last_name', 'father_name', 'father_mobile')
    inlines = [AdmissionDocumentInline, AdmissionInterviewInline, AdmissionAssessmentInline]


@admin.register(AdmissionDocument)
class AdmissionDocumentAdmin(admin.ModelAdmin):
    list_display = ('application', 'document_type', 'title', 'school', 'status', 'uploaded_at', 'verified_by')
    list_filter = ('school', 'status', 'document_type')


@admin.register(AdmissionInterview)
class AdmissionInterviewAdmin(admin.ModelAdmin):
    list_display = ('application', 'scheduled_at', 'school', 'location', 'interviewer', 'status', 'score')
    list_filter = ('school', 'status')


@admin.register(AdmissionAssessment)
class AdmissionAssessmentAdmin(admin.ModelAdmin):
    list_display = ('application', 'subject', 'school', 'score', 'max_score', 'assessed_by')
    list_filter = ('school', 'subject')
