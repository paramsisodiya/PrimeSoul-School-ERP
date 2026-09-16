"""
PrimeSoul School ERP - Production System Initialization Command
Executes required production system initialization without creating any demo records.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import connection
from django_school_management.accounts.roles import Role, ensure_system_roles_exist
from django_school_management.tenants.models import School

User = get_user_model()


class Command(BaseCommand):
    help = (
        "Initialize PrimeSoul School ERP production database with system roles and "
        "base configuration. Creates NO demo data, NO mock users, and NO demo schools."
    )

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("=" * 70))
        self.stdout.write(self.style.NOTICE("PRIMESOUL SCHOOL ERP - PRODUCTION SYSTEM INITIALIZATION"))
        self.stdout.write(self.style.NOTICE("=" * 70))

        # 1. Verify Database Connection
        self.stdout.write("[1/4] Verifying database connectivity...")
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
            row = cursor.fetchone()
            if not row or row[0] != 1:
                self.stderr.write(self.style.ERROR("Database connection failed."))
                return
        self.stdout.write(self.style.SUCCESS("  [OK] Database connection healthy."))

        # 2. Ensure System Roles & Groups
        self.stdout.write("[2/4] Ensuring 12 PrimeSoul system roles and Django groups exist...")
        ensure_system_roles_exist()
        self.stdout.write(self.style.SUCCESS(f"  [OK] Verified {len(Role.ALL_ROLES)} system roles/groups."))

        # 3. Audit Tenant & User Cleanliness
        self.stdout.write("[3/4] Checking tenant database state...")
        schools_count = School.objects.count()
        users_count = User.objects.count()
        demo_users = User.objects.filter(email__endswith="@primesoul.com").count()

        self.stdout.write(f"  - Active Schools in database: {schools_count}")
        self.stdout.write(f"  - Total User accounts: {users_count}")
        if demo_users > 0:
            self.stdout.write(self.style.WARNING(
                f"  ! Notice: {demo_users} development demo accounts exist in current local environment."
            ))
        else:
            self.stdout.write(self.style.SUCCESS("  [OK] Zero demo accounts in database."))

        # 4. Next Steps Guidance
        self.stdout.write("[4/4] Production Readiness Status:")
        self.stdout.write(self.style.SUCCESS("  [OK] Production foundation successfully initialized!"))
        self.stdout.write(self.style.NOTICE("\nNext Steps to Onboard First Real School:"))
        self.stdout.write("  1. Create Platform Super Admin:")
        self.stdout.write("     python manage.py createsuperuser")
        self.stdout.write("  2. Start Web / Celery Services:")
        self.stdout.write("     sudo systemctl start primesoul-gunicorn primesoul-celery primesoul-celery-beat")
        self.stdout.write("  3. Log in to Platform Admin and create the first customer School Tenant.")
        self.stdout.write("  4. Have School Administrator complete the 4-step onboarding wizard.")
        self.stdout.write(self.style.NOTICE("=" * 70))
