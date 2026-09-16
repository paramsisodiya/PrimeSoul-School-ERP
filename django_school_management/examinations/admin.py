from django.contrib import admin
from .models import (
    AssessmentType, GradeScale, GradeScaleBand,
    ExaminationSession, Exam, ExamSubject,
    StudentMark, StudentExamResult, MarksCorrectionLog
)


class GradeScaleBandInline(admin.TabularInline):
    model = GradeScaleBand
    extra = 1


@admin.register(AssessmentType)
class AssessmentTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'school', 'is_active')
    list_filter = ('school', 'is_active')
    search_fields = ('name', 'code')


@admin.register(GradeScale)
class GradeScaleAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'school', 'is_default')
    list_filter = ('school', 'is_default')
    search_fields = ('name', 'code')
    inlines = [GradeScaleBandInline]


@admin.register(ExaminationSession)
class ExaminationSessionAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'academic_year', 'school', 'start_date', 'end_date', 'status')
    list_filter = ('school', 'status', 'academic_year')
    search_fields = ('name', 'code')


class ExamSubjectInline(admin.TabularInline):
    model = ExamSubject
    extra = 1


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ('name', 'session', 'grade_level', 'section', 'academic_year', 'school', 'status')
    list_filter = ('school', 'status', 'session', 'grade_level')
    search_fields = ('name',)
    inlines = [ExamSubjectInline]


@admin.register(StudentMark)
class StudentMarkAdmin(admin.ModelAdmin):
    list_display = ('student', 'exam', 'exam_subject', 'status', 'marks_obtained', 'grade', 'is_passed')
    list_filter = ('school', 'exam', 'status', 'is_passed')
    search_fields = ('student__first_name', 'student__last_name', 'student__roll_number')


@admin.register(StudentExamResult)
class StudentExamResultAdmin(admin.ModelAdmin):
    list_display = ('student', 'exam', 'percentage', 'overall_grade', 'result_status', 'status', 'class_rank', 'verification_code')
    list_filter = ('school', 'exam', 'status', 'result_status')
    search_fields = ('student__first_name', 'student__last_name', 'verification_code')


@admin.register(MarksCorrectionLog)
class MarksCorrectionLogAdmin(admin.ModelAdmin):
    list_display = ('student', 'subject', 'exam', 'previous_marks', 'new_marks', 'corrected_by', 'corrected_at')
    list_filter = ('school', 'exam')
    search_fields = ('student__first_name', 'reason')
