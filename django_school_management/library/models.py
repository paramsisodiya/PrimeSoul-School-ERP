"""
PrimeSoul Library Management - Data Models
Complete school library system with catalog, members, issue/return, and fine management.
"""
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from model_utils.models import TimeStampedModel
from django_prometheus.models import ExportModelOperationsMixin


class Library(ExportModelOperationsMixin('library'), TimeStampedModel):
    """Library instance belonging to a school tenant."""
    school = models.ForeignKey(
        'tenants.School', on_delete=models.CASCADE, related_name='libraries'
    )
    name = models.CharField(max_length=200, help_text="Library name (e.g. Main Library, Junior Wing Library)")
    code = models.CharField(max_length=50, help_text="Short unique code")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    issue_limit_student = models.PositiveIntegerField(default=2, help_text="Max books a student can borrow")
    issue_limit_teacher = models.PositiveIntegerField(default=5, help_text="Max books a teacher can borrow")
    default_loan_days = models.PositiveIntegerField(default=14, help_text="Default loan period in days")
    fine_per_day = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('1.00'), help_text="Fine per overdue day (₹)")
    max_fine = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('100.00'), help_text="Maximum fine cap (₹)")
    grace_period_days = models.PositiveIntegerField(default=0, help_text="Grace days before fine starts")

    class Meta:
        unique_together = ('school', 'code')
        ordering = ['name']
        verbose_name = 'Library'
        verbose_name_plural = 'Libraries'

    def __str__(self):
        return f"{self.name} ({self.code})"


class BookCategory(ExportModelOperationsMixin('book_category'), TimeStampedModel):
    """Book category/genre classification."""
    school = models.ForeignKey(
        'tenants.School', on_delete=models.CASCADE, related_name='book_categories'
    )
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('school', 'code')
        ordering = ['name']
        verbose_name = 'Book Category'
        verbose_name_plural = 'Book Categories'

    def __str__(self):
        return self.name


class Author(ExportModelOperationsMixin('author'), TimeStampedModel):
    """Book author."""
    school = models.ForeignKey(
        'tenants.School', on_delete=models.CASCADE, related_name='authors'
    )
    name = models.CharField(max_length=200)
    bio = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Publisher(ExportModelOperationsMixin('publisher'), TimeStampedModel):
    """Book publisher."""
    school = models.ForeignKey(
        'tenants.School', on_delete=models.CASCADE, related_name='publishers'
    )
    name = models.CharField(max_length=200)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class LibraryShelf(ExportModelOperationsMixin('library_shelf'), TimeStampedModel):
    """Physical shelf/rack location within a library."""
    school = models.ForeignKey(
        'tenants.School', on_delete=models.CASCADE, related_name='library_shelves'
    )
    name = models.CharField(max_length=200, help_text="Shelf/rack name (e.g. Shelf A1, Rack 3)")
    code = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('school', 'code')
        ordering = ['code']
        verbose_name = 'Library Shelf'
        verbose_name_plural = 'Library Shelves'

    def __str__(self):
        return f"{self.name} ({self.code})"


class Book(ExportModelOperationsMixin('book'), TimeStampedModel):
    """Book title record (not individual copies)."""
    LANGUAGE_CHOICES = (
        ('EN', 'English'),
        ('HI', 'Hindi'),
        ('BN', 'Bengali'),
        ('TA', 'Tamil'),
        ('TE', 'Telugu'),
        ('MR', 'Marathi'),
        ('GU', 'Gujarati'),
        ('KN', 'Kannada'),
        ('ML', 'Malayalam'),
        ('PA', 'Punjabi'),
        ('UR', 'Urdu'),
        ('SA', 'Sanskrit'),
        ('OTHER', 'Other'),
    )

    school = models.ForeignKey(
        'tenants.School', on_delete=models.CASCADE, related_name='books'
    )
    title = models.CharField(max_length=500)
    subtitle = models.CharField(max_length=500, blank=True)
    isbn = models.CharField(max_length=20, blank=True, db_index=True, help_text="ISBN-10 or ISBN-13")
    category = models.ForeignKey(
        BookCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='books'
    )
    publisher = models.ForeignKey(
        Publisher, on_delete=models.SET_NULL, null=True, blank=True, related_name='books'
    )
    language = models.CharField(max_length=10, choices=LANGUAGE_CHOICES, default='EN')
    edition = models.CharField(max_length=100, blank=True)
    publication_year = models.PositiveIntegerField(null=True, blank=True)
    description = models.TextField(blank=True)
    cover_image = models.ImageField(upload_to='library/covers/', blank=True, null=True)
    authors = models.ManyToManyField('Author', through='BookAuthor', related_name='books', blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['title']

    def __str__(self):
        return self.title

    @property
    def total_copies(self):
        return self.copies.count()

    @property
    def available_copies(self):
        return self.copies.filter(status=BookCopy.STATUS_AVAILABLE).count()


class BookAuthor(models.Model):
    """Many-to-many relationship between Book and Author."""
    school = models.ForeignKey(
        'tenants.School', on_delete=models.CASCADE, related_name='book_authors'
    )
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='book_authors')
    author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name='book_authors')

    class Meta:
        unique_together = ('school', 'book', 'author')

    def __str__(self):
        return f"{self.book.title} — {self.author.name}"


class BookCopy(ExportModelOperationsMixin('book_copy'), TimeStampedModel):
    """Individual physical copy of a book."""
    STATUS_AVAILABLE = 'AVAILABLE'
    STATUS_ISSUED = 'ISSUED'
    STATUS_RESERVED = 'RESERVED'
    STATUS_LOST = 'LOST'
    STATUS_DAMAGED = 'DAMAGED'
    STATUS_DISCARDED = 'DISCARDED'

    STATUS_CHOICES = (
        (STATUS_AVAILABLE, 'Available'),
        (STATUS_ISSUED, 'Issued'),
        (STATUS_RESERVED, 'Reserved'),
        (STATUS_LOST, 'Lost'),
        (STATUS_DAMAGED, 'Damaged'),
        (STATUS_DISCARDED, 'Discarded'),
    )

    CONDITION_NEW = 'NEW'
    CONDITION_GOOD = 'GOOD'
    CONDITION_FAIR = 'FAIR'
    CONDITION_DAMAGED = 'DAMAGED'

    CONDITION_CHOICES = (
        (CONDITION_NEW, 'New'),
        (CONDITION_GOOD, 'Good'),
        (CONDITION_FAIR, 'Fair'),
        (CONDITION_DAMAGED, 'Damaged'),
    )

    school = models.ForeignKey(
        'tenants.School', on_delete=models.CASCADE, related_name='book_copies'
    )
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='copies')
    accession_number = models.CharField(max_length=50, db_index=True, help_text="Unique accession number within school")
    barcode = models.CharField(max_length=100, blank=True, db_index=True)
    shelf = models.ForeignKey(
        LibraryShelf, on_delete=models.SET_NULL, null=True, blank=True, related_name='copies'
    )
    purchase_date = models.DateField(null=True, blank=True)
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, default=CONDITION_NEW)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_AVAILABLE)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ('school', 'accession_number')
        ordering = ['accession_number']
        verbose_name = 'Book Copy'
        verbose_name_plural = 'Book Copies'

    def __str__(self):
        return f"{self.book.title} [{self.accession_number}]"


class LibraryMember(ExportModelOperationsMixin('library_member'), TimeStampedModel):
    """Library membership record linked to existing User/Student/Teacher."""
    TYPE_STUDENT = 'STUDENT'
    TYPE_TEACHER = 'TEACHER'
    TYPE_STAFF = 'STAFF'

    TYPE_CHOICES = (
        (TYPE_STUDENT, 'Student'),
        (TYPE_TEACHER, 'Teacher'),
        (TYPE_STAFF, 'Staff'),
    )

    school = models.ForeignKey(
        'tenants.School', on_delete=models.CASCADE, related_name='library_members'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='library_memberships'
    )
    student = models.ForeignKey(
        'students.Student', on_delete=models.SET_NULL, null=True, blank=True, related_name='library_memberships'
    )
    teacher = models.ForeignKey(
        'teachers.Teacher', on_delete=models.SET_NULL, null=True, blank=True, related_name='library_memberships'
    )
    member_code = models.CharField(max_length=50, db_index=True)
    member_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_STUDENT)
    is_active = models.BooleanField(default=True)
    joined_date = models.DateField(default=timezone.localdate)
    max_books_override = models.PositiveIntegerField(null=True, blank=True, help_text="Override default issue limit")

    class Meta:
        unique_together = ('school', 'member_code')
        ordering = ['member_code']

    def __str__(self):
        if self.student:
            return f"{self.student.name} ({self.member_code})"
        if self.teacher:
            return f"{self.teacher.name} ({self.member_code})"
        return f"Member {self.member_code}"

    def clean(self):
        """Validate tenant consistency."""
        if self.student and self.student.school_id and self.student.school_id != self.school_id:
            raise ValidationError("Student does not belong to this school.")
        if self.teacher and self.teacher.school_id and self.teacher.school_id != self.school_id:
            raise ValidationError("Teacher does not belong to this school.")

    def get_issue_limit(self, library):
        """Returns the effective issue limit for this member."""
        if self.max_books_override is not None:
            return self.max_books_override
        if self.member_type == self.TYPE_TEACHER:
            return library.issue_limit_teacher
        return library.issue_limit_student

    @property
    def current_issued_count(self):
        """Returns the number of books currently issued to this member."""
        return self.issues.filter(status='ISSUED').count()


class LibraryIssue(ExportModelOperationsMixin('library_issue'), TimeStampedModel):
    """Book issue/return transaction."""
    STATUS_ISSUED = 'ISSUED'
    STATUS_RETURNED = 'RETURNED'
    STATUS_OVERDUE = 'OVERDUE'
    STATUS_LOST = 'LOST'
    STATUS_DAMAGED = 'DAMAGED'

    STATUS_CHOICES = (
        (STATUS_ISSUED, 'Issued'),
        (STATUS_RETURNED, 'Returned'),
        (STATUS_OVERDUE, 'Overdue'),
        (STATUS_LOST, 'Lost'),
        (STATUS_DAMAGED, 'Damaged'),
    )

    school = models.ForeignKey(
        'tenants.School', on_delete=models.CASCADE, related_name='library_issues'
    )
    library = models.ForeignKey(
        Library, on_delete=models.CASCADE, related_name='issues'
    )
    member = models.ForeignKey(
        LibraryMember, on_delete=models.CASCADE, related_name='issues'
    )
    book_copy = models.ForeignKey(
        BookCopy, on_delete=models.CASCADE, related_name='issues'
    )
    issue_date = models.DateField(default=timezone.localdate)
    due_date = models.DateField()
    returned_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ISSUED)
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='library_issues_made'
    )
    returned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='library_returns_made'
    )
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ['-issue_date', '-created']

    def __str__(self):
        return f"{self.book_copy} → {self.member} ({self.status})"


class LibraryFine(ExportModelOperationsMixin('library_fine'), TimeStampedModel):
    """Fine record associated with a library issue."""
    school = models.ForeignKey(
        'tenants.School', on_delete=models.CASCADE, related_name='library_fines'
    )
    issue = models.OneToOneField(
        LibraryIssue, on_delete=models.CASCADE, related_name='fine'
    )
    calculated_fine = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    waived_fine = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    final_fine = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    waiver_reason = models.TextField(blank=True)
    waived_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='library_fines_waived'
    )
    paid = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created']

    def __str__(self):
        return f"Fine ₹{self.final_fine} for {self.issue}"
