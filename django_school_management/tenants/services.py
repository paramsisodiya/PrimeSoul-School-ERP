"""
Tenant management and provisioning services for PrimeSoul School ERP.
Deterministic bridging between InstituteProfile onboarding and multi-tenant School models.
"""
from django.db import transaction
from django.utils.text import slugify
from django_school_management.tenants.models import School, Domain, Subscription


def sync_institute_to_school_tenant(institute, user=None) -> School:
    """
    Idempotently bridges and synchronizes an InstituteProfile with the corresponding
    tenants.School tenant, primary Domain, and active Subscription.

    If user is provided, associates user.school = school and persists it.
    """
    if not institute:
        return None

    with transaction.atomic():
        # 1. Determine a stable base slug
        base_slug = slugify(institute.name) if institute.name else 'school'
        if not base_slug:
            base_slug = 'school'

        # Look for existing school by user.school or by name/slug match
        school = None
        if user and getattr(user, 'school', None):
            school = user.school

        if not school:
            school = School.objects.filter(name=institute.name).first()

        if not school:
            school = School.objects.filter(slug=base_slug).first()

        # Country normalization
        country_str = 'India'
        if hasattr(institute.country, 'name') and institute.country.name:
            country_str = str(institute.country.name)
        elif hasattr(institute.country, 'code') and institute.country.code:
            country_str = str(institute.country.code)
        elif institute.country:
            country_str = str(institute.country)

        # 2. Get or create School tenant
        if not school:
            candidate_slug = base_slug
            counter = 1
            while School.objects.filter(slug=candidate_slug).exists() or School.objects.filter(subdomain=candidate_slug).exists():
                candidate_slug = f"{base_slug}-{counter}"
                counter += 1

            school = School.objects.create(
                name=institute.name,
                slug=candidate_slug,
                subdomain=candidate_slug,
                country=country_str,
                logo=institute.logo if institute.logo else None,
                is_active=True,
                onboarding_completed=bool(getattr(institute, 'onboarding_completed', False))
            )
        else:
            updated = False
            if bool(getattr(institute, 'onboarding_completed', False)) and not school.onboarding_completed:
                school.onboarding_completed = True
                updated = True
            if not school.is_active:
                school.is_active = True
                updated = True
            if institute.logo and (not school.logo or school.logo != institute.logo):
                school.logo = institute.logo
                updated = True
            if updated:
                school.save()

        # 3. Ensure primary Domain exists
        domain_name = f"{school.subdomain}.primesoul.local"
        Domain.objects.get_or_create(
            school=school,
            domain=domain_name,
            defaults={"is_primary": True, "is_verified": True}
        )

        # 4. Ensure active Subscription exists
        Subscription.objects.get_or_create(
            school=school,
            defaults={
                "plan_name": "Standard Plan",
                "status": "active",
                "max_students": 1000
            }
        )

        # 5. Link user to school if provided
        if user and user.is_authenticated:
            if user.school_id != school.id:
                user.school = school
                user.save(update_fields=['school'])

        return school
