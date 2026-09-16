from django.contrib import admin
from .models import (
    Library, BookCategory, Author, Publisher, LibraryShelf,
    Book, BookAuthor, BookCopy, LibraryMember, LibraryIssue, LibraryFine
)


@admin.register(Library)
class LibraryAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'school', 'issue_limit_student', 'issue_limit_teacher', 'is_active')
    list_filter = ('school', 'is_active')
    search_fields = ('name', 'code')


@admin.register(BookCategory)
class BookCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'school', 'is_active')
    list_filter = ('school', 'is_active')
    search_fields = ('name', 'code')


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ('name', 'school', 'is_active')
    list_filter = ('school', 'is_active')
    search_fields = ('name',)


@admin.register(Publisher)
class PublisherAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'email', 'school', 'is_active')
    list_filter = ('school', 'is_active')
    search_fields = ('name', 'email')


@admin.register(LibraryShelf)
class LibraryShelfAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'school', 'is_active')
    list_filter = ('school', 'is_active')


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ('title', 'isbn', 'category', 'publisher', 'school', 'is_active')
    list_filter = ('school', 'category', 'is_active')
    search_fields = ('title', 'isbn')


@admin.register(BookCopy)
class BookCopyAdmin(admin.ModelAdmin):
    list_display = ('accession_number', 'book', 'barcode', 'shelf', 'status', 'school')
    list_filter = ('school', 'status', 'condition')
    search_fields = ('accession_number', 'barcode', 'book__title')


@admin.register(LibraryMember)
class LibraryMemberAdmin(admin.ModelAdmin):
    list_display = ('member_code', 'member_type', 'student', 'teacher', 'school', 'is_active')
    list_filter = ('school', 'member_type', 'is_active')
    search_fields = ('member_code', 'student__user__first_name', 'teacher__user__first_name')


@admin.register(LibraryIssue)
class LibraryIssueAdmin(admin.ModelAdmin):
    list_display = ('book_copy', 'member', 'issue_date', 'due_date', 'returned_date', 'status', 'school')
    list_filter = ('school', 'status')
    search_fields = ('book_copy__accession_number', 'member__member_code')


@admin.register(LibraryFine)
class LibraryFineAdmin(admin.ModelAdmin):
    list_display = ('issue', 'calculated_fine', 'waived_fine', 'final_fine', 'paid', 'school')
    list_filter = ('school', 'paid')
