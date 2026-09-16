"""
PrimeSoul Library - DRF Serializers
"""
from rest_framework import serializers
from django_school_management.library.models import (
    Library, BookCategory, Author, Publisher, LibraryShelf,
    Book, BookAuthor, BookCopy, LibraryMember, LibraryIssue, LibraryFine
)


class LibrarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Library
        fields = '__all__'
        read_only_fields = ('school',)


class BookCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = BookCategory
        fields = '__all__'
        read_only_fields = ('school',)


class AuthorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Author
        fields = '__all__'
        read_only_fields = ('school',)


class PublisherSerializer(serializers.ModelSerializer):
    class Meta:
        model = Publisher
        fields = '__all__'
        read_only_fields = ('school',)


class LibraryShelfSerializer(serializers.ModelSerializer):
    class Meta:
        model = LibraryShelf
        fields = '__all__'
        read_only_fields = ('school',)


class BookSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True, default='')
    publisher_name = serializers.CharField(source='publisher.name', read_only=True, default='')
    total_copies = serializers.IntegerField(read_only=True)
    available_copies = serializers.IntegerField(read_only=True)

    class Meta:
        model = Book
        fields = '__all__'
        read_only_fields = ('school',)


class BookCopySerializer(serializers.ModelSerializer):
    book_title = serializers.CharField(source='book.title', read_only=True)
    shelf_name = serializers.CharField(source='shelf.name', read_only=True, default='')

    class Meta:
        model = BookCopy
        fields = '__all__'
        read_only_fields = ('school',)


class LibraryMemberSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = LibraryMember
        fields = '__all__'
        read_only_fields = ('school',)

    def get_display_name(self, obj):
        if obj.student:
            return obj.student.name
        if obj.teacher:
            return obj.teacher.name
        return f"Member {obj.member_code}"


class LibraryIssueSerializer(serializers.ModelSerializer):
    member_name = serializers.SerializerMethodField()
    book_title = serializers.CharField(source='book_copy.book.title', read_only=True)
    accession_number = serializers.CharField(source='book_copy.accession_number', read_only=True)

    class Meta:
        model = LibraryIssue
        fields = '__all__'
        read_only_fields = ('school',)

    def get_member_name(self, obj):
        return str(obj.member)


class LibraryFineSerializer(serializers.ModelSerializer):
    class Meta:
        model = LibraryFine
        fields = '__all__'
        read_only_fields = ('school',)


class IssueBookRequestSerializer(serializers.Serializer):
    library_id = serializers.IntegerField()
    member_id = serializers.IntegerField()
    book_copy_id = serializers.IntegerField(required=False)
    accession_number = serializers.CharField(required=False)
    loan_days = serializers.IntegerField(required=False)
    issue_date = serializers.DateField(required=False)
    due_date = serializers.DateField(required=False)
    remarks = serializers.CharField(required=False, allow_blank=True)


class ReturnBookRequestSerializer(serializers.Serializer):
    issue_id = serializers.IntegerField()
    return_date = serializers.DateField(required=False)
    waive_fine = serializers.BooleanField(required=False, default=False)
    waiver_reason = serializers.CharField(required=False, allow_blank=True)
    remarks = serializers.CharField(required=False, allow_blank=True)
