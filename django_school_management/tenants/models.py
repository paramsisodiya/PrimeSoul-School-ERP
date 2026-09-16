from django.db import models
from django.utils.text import slugify
from .managers import TenantManager


class School(models.Model):
    """
    Core Tenant model representing an Indian School or Educational Campus.
    All student, faculty, academic, and financial data is partitioned by School.
    """
    BOARD_CHOICES = (
        ('CBSE', 'Central Board of Secondary Education (CBSE)'),
        ('ICSE', 'Council for the Indian School Certificate Examinations (ICSE/ISC)'),
        ('STATE', 'State Board of Secondary Education'),
        ('IB', 'International Baccalaureate (IB)'),
        ('CAMBRIDGE', 'Cambridge Assessment International Education (IGCSE)'),
        ('OTHER', 'Other / Independent Board'),
    )

    name = models.CharField(max_length=255, help_text="Full legal name of the school / institution")
    slug = models.SlugField(max_length=100, unique=True, db_index=True, help_text="URL-safe unique identifier")
    subdomain = models.CharField(max_length=100, unique=True, db_index=True, help_text="Subdomain prefix (e.g. dpsdelhi)")
    custom_domain = models.CharField(max_length=255, blank=True, null=True, unique=True, help_text="Optional custom domain (e.g. dpsdelhi.edu.in)")

    logo = models.ImageField(upload_to='tenants/logos/', blank=True, null=True)
    favicon = models.ImageField(upload_to='tenants/favicons/', blank=True, null=True)

    # Statutory Indian School Identifiers
    board = models.CharField(max_length=50, choices=BOARD_CHOICES, default='CBSE')
    affiliation_number = models.CharField(max_length=100, blank=True, help_text="CBSE / ICSE / State Board Affiliation Number")
    school_code = models.CharField(max_length=50, blank=True, help_text="Official Board School Code")
    udise_code = models.CharField(max_length=50, blank=True, help_text="Unified District Information System for Education (UDISE+) Code")
    recognition_number = models.CharField(max_length=100, blank=True, help_text="State Department Recognition / Registration Number")

    # Address & Location
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    pincode = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, default='India')

    # Regional & Localization Defaults
    timezone = models.CharField(max_length=50, default='Asia/Kolkata')
    currency = models.CharField(max_length=10, default='INR')

    # SaaS Status
    is_active = models.BooleanField(default=True, help_text="Enables or disables access for this entire school tenant")
    onboarding_completed = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'School'
        verbose_name_plural = 'Schools'

    def __str__(self):
        return f"{self.name} ({self.subdomain})"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.subdomain or self.name)
        if not self.subdomain:
            self.subdomain = self.slug
        super().save(*args, **kwargs)


class Domain(models.Model):
    """
    Custom domain and subdomain mappings for multi-tenant routing.
    """
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='domains')
    domain = models.CharField(max_length=255, unique=True, db_index=True)
    is_primary = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-is_primary', 'domain']

    def __str__(self):
        return f"{self.domain} -> {self.school.name}"


class Subscription(models.Model):
    """
    Tracks commercial SaaS subscription tiers for school tenants.
    """
    STATUS_CHOICES = (
        ('trial', 'Trial'),
        ('active', 'Active'),
        ('past_due', 'Past Due'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    )

    school = models.OneToOneField(School, on_delete=models.CASCADE, related_name='subscription')
    plan_name = models.CharField(max_length=100, default='Standard Plan')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    max_students = models.PositiveIntegerField(default=1000)
    start_date = models.DateField(auto_now_add=True)
    end_date = models.DateField(blank=True, null=True)

    def __str__(self):
        return f"{self.school.name} - {self.plan_name} ({self.get_status_display()})"


class TenantModel(models.Model):
    """
    Abstract base model for all tenant-partitioned entities in PrimeSoul ERP.
    Guarantees that child models are strictly scoped to a specific School tenant.
    """
    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE,
        db_index=True,
        related_name="%(app_label)s_%(class)s_set",
        help_text="Tenant school that owns this record"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True
