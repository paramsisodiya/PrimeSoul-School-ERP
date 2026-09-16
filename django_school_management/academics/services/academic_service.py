"""
PrimeSoul ERP Academic Management - Core Business Services
Handles validation, transaction-wrapped mutations, and audit logging for Academic entities.
"""
from typing import Optional, List
from django.db import transaction
from django.core.exceptions import ValidationError
from django_school_management.core.audit import log_academic_event
from django_school_management.academics.models import (
    AcademicYear, GradeLevel, Section, Subject,
    SubjectAssignment, StudentEnrollment, ClassTeacherAssignment
)
from django_school_management.students.models import Student
from django_school_management.teachers.models import Teacher


def set_current_academic_year(school, year_id: int, actor=None) -> AcademicYear:
    """
    Sets a specific academic year as active/current for the given school tenant.
    Deactivates all other academic years for the same school in a transaction.
    """
    with transaction.atomic():
        year = AcademicYear.objects.get(pk=year_id, school=school)
        AcademicYear.objects.filter(school=school, is_current=True).exclude(pk=year.pk).update(is_current=False)
        year.is_current = True
        year.status = AcademicYear.STATUS_ACTIVE
        year.save()

        # Update all active students' current academic year pointer
        Student.objects.filter(school=school, is_active=True).update(academic_year=year)

        log_academic_event(
            actor=actor,
            school=school,
            action='SET_CURRENT_ACADEMIC_YEAR',
            resource='AcademicYear',
            resource_id=str(year.pk),
            details={'name': year.name, 'start_date': str(year.start_date), 'end_date': str(year.end_date)}
        )
        return year


def create_or_update_grade_level(
    school,
    name: str,
    code: str,
    board: str = 'CBSE',
    stream_applicable: bool = False,
    display_order: int = 0,
    is_active: bool = True,
    actor=None,
    grade_id: Optional[int] = None
) -> GradeLevel:
    """
    Creates or updates a Class / GradeLevel with tenant validation.
    """
    with transaction.atomic():
        if grade_id:
            grade = GradeLevel.objects.get(pk=grade_id, school=school)
            grade.name = name
            grade.code = code
            grade.board = board
            grade.stream_applicable = stream_applicable
            grade.display_order = display_order
            grade.is_active = is_active
            grade.save()
            action = 'UPDATE_GRADE_LEVEL'
        else:
            grade = GradeLevel.objects.create(
                school=school,
                name=name,
                code=code,
                board=board,
                stream_applicable=stream_applicable,
                display_order=display_order,
                is_active=is_active,
                created_by=actor
            )
            action = 'CREATE_GRADE_LEVEL'

        log_academic_event(
            actor=actor,
            school=school,
            action=action,
            resource='GradeLevel',
            resource_id=str(grade.pk),
            details={'name': grade.name, 'code': grade.code, 'board': grade.board, 'order': grade.display_order}
        )
        return grade


def create_or_update_section(
    school,
    grade_level: GradeLevel,
    name: str,
    academic_year: Optional[AcademicYear] = None,
    class_teacher: Optional[Teacher] = None,
    room_number: str = '',
    max_capacity: int = 40,
    is_active: bool = True,
    actor=None,
    section_id: Optional[int] = None
) -> Section:
    """
    Creates or updates a Section under a GradeLevel and AcademicYear.
    Enforces tenant scoping on class teacher and grade level.
    """
    if grade_level.school != school:
        raise ValidationError("Grade Level does not belong to this school tenant.")

    if class_teacher and class_teacher.school and class_teacher.school != school:
        raise ValidationError("Class Teacher does not belong to this school tenant.")

    if academic_year and academic_year.school != school:
        raise ValidationError("Academic Year does not belong to this school tenant.")

    with transaction.atomic():
        if section_id:
            section = Section.objects.get(pk=section_id, school=school)
            old_teacher = section.class_teacher
            section.grade_level = grade_level
            section.name = name
            section.academic_year = academic_year
            section.class_teacher = class_teacher
            section.room_number = room_number
            section.max_capacity = max_capacity
            section.is_active = is_active
            section.save()
            action = 'UPDATE_SECTION'

            # Log class teacher change if teacher changed
            if class_teacher and class_teacher != old_teacher and academic_year:
                ClassTeacherAssignment.objects.create(
                    school=school,
                    academic_year=academic_year,
                    section=section,
                    teacher=class_teacher,
                    is_active=True,
                    created_by=actor
                )
        else:
            section = Section.objects.create(
                school=school,
                grade_level=grade_level,
                name=name,
                academic_year=academic_year,
                class_teacher=class_teacher,
                room_number=room_number,
                max_capacity=max_capacity,
                is_active=is_active,
                created_by=actor
            )
            action = 'CREATE_SECTION'

            if class_teacher and academic_year:
                ClassTeacherAssignment.objects.create(
                    school=school,
                    academic_year=academic_year,
                    section=section,
                    teacher=class_teacher,
                    is_active=True,
                    created_by=actor
                )

        log_academic_event(
            actor=actor,
            school=school,
            action=action,
            resource='Section',
            resource_id=str(section.pk),
            details={
                'grade': grade_level.name,
                'name': section.name,
                'capacity': section.max_capacity,
                'teacher': class_teacher.name if class_teacher else None
            }
        )
        return section


def assign_class_teacher(
    section: Section,
    teacher: Teacher,
    academic_year: Optional[AcademicYear] = None,
    actor=None
) -> ClassTeacherAssignment:
    """
    Assigns an active teacher as Class Teacher for a section.
    """
    if teacher.school and section.school and teacher.school != section.school:
        raise ValidationError("Teacher and Section belong to different schools.")

    with transaction.atomic():
        section.class_teacher = teacher
        section.save(update_fields=['class_teacher'])

        year = academic_year or section.academic_year or AcademicYear.objects.filter(school=section.school, is_current=True).first()
        if not year:
            raise ValidationError("No current or designated academic year found for class teacher assignment.")

        # Deactivate previous active class teacher assignments for this section and year
        ClassTeacherAssignment.objects.filter(
            section=section, academic_year=year, is_active=True
        ).update(is_active=False)

        cta = ClassTeacherAssignment.objects.create(
            school=section.school,
            academic_year=year,
            section=section,
            teacher=teacher,
            is_active=True,
            created_by=actor
        )

        log_academic_event(
            actor=actor,
            school=section.school,
            action='ASSIGN_CLASS_TEACHER',
            resource='ClassTeacherAssignment',
            resource_id=str(cta.pk),
            details={'section': section.name, 'grade': section.grade_level.name, 'teacher': teacher.name, 'year': year.name}
        )
        return cta


def create_or_update_subject(
    school,
    name: str,
    code: str,
    subject_type: str = 'CORE',
    max_marks: int = 100,
    passing_marks: int = 33,
    is_active: bool = True,
    theory_marks: int = 80,
    practical_marks: int = 20,
    actor=None,
    subject_id: Optional[int] = None
) -> Subject:
    """
    Creates or updates a Subject.
    """
    with transaction.atomic():
        if subject_id:
            sub = Subject.objects.get(pk=subject_id, school=school)
            sub.name = name
            sub.code = code
            sub.subject_type = subject_type
            sub.max_marks = max_marks
            sub.passing_marks = passing_marks
            sub.is_active = is_active
            sub.theory_marks = theory_marks
            sub.practical_marks = practical_marks
            sub.save()
            action = 'UPDATE_SUBJECT'
        else:
            sub = Subject.objects.create(
                school=school,
                name=name,
                code=code,
                subject_type=subject_type,
                max_marks=max_marks,
                passing_marks=passing_marks,
                is_active=is_active,
                theory_marks=theory_marks,
                practical_marks=practical_marks,
                created_by=actor
            )
            action = 'CREATE_SUBJECT'

        log_academic_event(
            actor=actor,
            school=school,
            action=action,
            resource='Subject',
            resource_id=str(sub.pk),
            details={'name': sub.name, 'code': sub.code, 'type': sub.subject_type}
        )
        return sub


def assign_subject_to_teacher(
    school,
    academic_year: AcademicYear,
    grade_level: GradeLevel,
    subject: Subject,
    section: Optional[Section] = None,
    teacher: Optional[Teacher] = None,
    periods_per_week: int = 5,
    actor=None,
    assignment_id: Optional[int] = None
) -> SubjectAssignment:
    """
    Assigns a subject and teacher to a class/section for an academic year.
    Prevents duplicate assignments.
    """
    if academic_year.school != school or grade_level.school != school or subject.school != school:
        raise ValidationError("Academic year, class, or subject does not belong to this school.")

    if section and section.school != school:
        raise ValidationError("Section does not belong to this school.")

    if teacher and teacher.school and teacher.school != school:
        raise ValidationError("Teacher does not belong to this school.")

    # Check for duplicate
    duplicate_qs = SubjectAssignment.objects.filter(
        school=school,
        academic_year=academic_year,
        grade_level=grade_level,
        section=section,
        subject=subject
    )
    if assignment_id:
        duplicate_qs = duplicate_qs.exclude(pk=assignment_id)

    if duplicate_qs.exists():
        sec_label = f" - Section {section.name}" if section else ""
        raise ValidationError(f"Subject '{subject.name}' is already assigned to {grade_level.name}{sec_label} for {academic_year.name}.")

    with transaction.atomic():
        if assignment_id:
            assign = SubjectAssignment.objects.get(pk=assignment_id, school=school)
            assign.academic_year = academic_year
            assign.grade_level = grade_level
            assign.section = section
            assign.subject = subject
            assign.teacher = teacher
            assign.periods_per_week = periods_per_week
            assign.save()
            action = 'UPDATE_SUBJECT_ASSIGNMENT'
        else:
            assign = SubjectAssignment.objects.create(
                school=school,
                academic_year=academic_year,
                grade_level=grade_level,
                section=section,
                subject=subject,
                teacher=teacher,
                periods_per_week=periods_per_week,
                created_by=actor
            )
            action = 'CREATE_SUBJECT_ASSIGNMENT'

        log_academic_event(
            actor=actor,
            school=school,
            action=action,
            resource='SubjectAssignment',
            resource_id=str(assign.pk),
            details={
                'year': academic_year.name,
                'grade': grade_level.name,
                'section': section.name if section else 'All',
                'subject': subject.name,
                'teacher': teacher.name if teacher else 'Unassigned'
            }
        )
        return assign


def enroll_student(
    school,
    student: Student,
    academic_year: AcademicYear,
    grade_level: GradeLevel,
    section: Optional[Section] = None,
    roll_number: Optional[str] = None,
    status: str = StudentEnrollment.STATUS_ACTIVE,
    notes: str = '',
    allow_update: bool = True,
    actor=None
) -> StudentEnrollment:
    """
    Enrolls a student in a specific class and section for an academic year.
    Ensures student belongs to same school and roll numbers are unique per section.
    """
    if student.school != school or academic_year.school != school or grade_level.school != school:
        raise ValidationError("Student, Academic Year, or Grade Level does not belong to this school.")

    if section and section.grade_level != grade_level:
        raise ValidationError(f"Section {section.name} does not belong to {grade_level.name}.")

    if not allow_update and StudentEnrollment.objects.filter(school=school, student=student, academic_year=academic_year).exists():
        raise ValidationError(f"Student {student.name} is already enrolled in academic year {academic_year.name}.")

    # Check roll number uniqueness within section + academic year
    if section and roll_number:
        if StudentEnrollment.objects.filter(
            academic_year=academic_year,
            section=section,
            roll_number=roll_number,
            status=StudentEnrollment.STATUS_ACTIVE
        ).exclude(student=student).exists():
            raise ValidationError(f"Roll number {roll_number} is already taken in {grade_level.name} - {section.name} for {academic_year.name}.")

    with transaction.atomic():
        enrollment, created = StudentEnrollment.objects.update_or_create(
            school=school,
            student=student,
            academic_year=academic_year,
            defaults={
                'grade_level': grade_level,
                'section': section,
                'roll_number': roll_number,
                'status': status,
                'notes': notes,
                'created_by': actor
            }
        )

        log_academic_event(
            actor=actor,
            school=school,
            action='ENROLL_STUDENT' if created else 'UPDATE_ENROLLMENT',
            resource='StudentEnrollment',
            resource_id=str(enrollment.pk),
            details={
                'student': student.name,
                'year': academic_year.name,
                'grade': grade_level.name,
                'section': section.name if section else None,
                'roll_number': roll_number,
                'status': status
            }
        )
        return enrollment
