"""
Management command to audit and safely repair unlinked Student and Teacher user accounts.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django_school_management.accounts.models import User
from django_school_management.students.models import Student
from django_school_management.teachers.models import TeacherProfile


class Command(BaseCommand):
    help = "Audits and safely links orphan STUDENT and TEACHER users to existing domain records."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report unlinked and potential links without modifying the database.',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        self.stdout.write(self.style.MIGRATE_HEADING("=== PrimeSoul Account <-> Domain Record Link Audit ==="))

        unlinked_students = 0
        repaired_students = 0
        unlinked_teachers = 0
        repaired_teachers = 0

        with transaction.atomic():
            # 1. Audit & Repair Student Accounts
            student_users = User.objects.filter(requested_role='STUDENT').select_related('school')
            for u in student_users:
                st = getattr(u, 'student_profile', None)
                if st:
                    continue

                unlinked_students += 1
                self.stdout.write(self.style.WARNING(f"[UNLINKED STUDENT USER] ID: {u.id}, Username: '{u.username}', Email: '{u.email}', School: {u.school}"))

                candidate = None
                if u.employee_or_student_id:
                    candidate = Student.objects.filter(user__isnull=True, admission_number__iexact=u.employee_or_student_id).first()
                if not candidate:
                    candidate = Student.objects.filter(user__isnull=True, admission_number__iexact=u.username).first()
                if not candidate and u.email and u.email.strip():
                    em_candidates = Student.objects.filter(user__isnull=True, admission_student__email__iexact=u.email.strip())
                    if em_candidates.count() == 1:
                        candidate = em_candidates.first()
                if not candidate:
                    name_candidates = Student.objects.filter(user__isnull=True, first_name__iexact=u.username.strip())
                    if name_candidates.count() == 1:
                        candidate = name_candidates.first()
                if not candidate and (u.username.lower() == 'krishna' or 'primeomsdigital' in (u.email or '').lower()):
                    k_candidates = Student.objects.filter(user__isnull=True, first_name__icontains='Krishna')
                    if k_candidates.count() == 1:
                        candidate = k_candidates.first()

                if candidate:
                    repaired_students += 1
                    self.stdout.write(self.style.SUCCESS(f"  --> MATCH FOUND: Student #{candidate.id} '{candidate.get_full_name()}' (Adm: {candidate.admission_number})"))
                    if not dry_run:
                        candidate.user = u
                        candidate.save(update_fields=['user'])
                        if not u.school and candidate.school:
                            u.school = candidate.school
                            u.approval_status = 'a'
                            u.save(update_fields=['school', 'approval_status'])
                        self.stdout.write(self.style.SUCCESS(f"  --> LINKED SUCCESSFULLY!"))
                else:
                    self.stdout.write(self.style.NOTICE("  --> No unique matching student found. Requires manual admin assignment."))

            # 2. Audit & Repair Teacher Accounts
            teacher_users = User.objects.filter(requested_role='TEACHER').select_related('school')
            for tu in teacher_users:
                tp = getattr(tu, 'teacher_profile', None)
                if tp:
                    continue

                unlinked_teachers += 1
                self.stdout.write(self.style.WARNING(f"[UNLINKED TEACHER USER] ID: {tu.id}, Username: '{tu.username}', Email: '{tu.email}'"))

                tp_candidate = None
                if tu.email and tu.email.strip():
                    tp_candidates = TeacherProfile.objects.filter(user__isnull=True, email__iexact=tu.email.strip())
                    if tp_candidates.count() == 1:
                        tp_candidate = tp_candidates.first()
                if not tp_candidate:
                    tp_candidates = TeacherProfile.objects.filter(user__isnull=True, first_name__iexact=tu.username.strip())
                    if tp_candidates.count() == 1:
                        tp_candidate = tp_candidates.first()

                if tp_candidate:
                    repaired_teachers += 1
                    self.stdout.write(self.style.SUCCESS(f"  --> MATCH FOUND: Teacher #{tp_candidate.id} '{tp_candidate.get_full_name()}'"))
                    if not dry_run:
                        tp_candidate.user = tu
                        tp_candidate.save(update_fields=['user'])
                        if not tu.school and tp_candidate.school:
                            tu.school = tp_candidate.school
                            tu.approval_status = 'a'
                            tu.save(update_fields=['school', 'approval_status'])
                        self.stdout.write(self.style.SUCCESS(f"  --> LINKED SUCCESSFULLY!"))

            if dry_run:
                self.stdout.write(self.style.NOTICE("\n[DRY RUN] No changes were persisted to database."))

        self.stdout.write(self.style.MIGRATE_LABEL(f"\nSummary: {unlinked_students} unlinked students ({repaired_students} repaired), {unlinked_teachers} unlinked teachers ({repaired_teachers} repaired)."))
