"""
PrimeSoul Library - Modern ERP Forms
"""
from django import forms
from django_school_management.library.models import (
    Library, BookCategory, Author, Publisher, LibraryShelf,
    Book, BookCopy, LibraryMember, LibraryIssue, LibraryFine
)
from django_school_management.students.models import Student
from django_school_management.teachers.models import TeacherProfile


class LibraryForm(forms.ModelForm):
    class Meta:
        model = Library
        fields = [
            'name', 'code', 'description', 'issue_limit_student',
            'issue_limit_teacher', 'default_loan_days', 'fine_per_day', 'max_fine', 'is_active'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Main Campus Library'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'LIB-01'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'issue_limit_student': forms.NumberInput(attrs={'class': 'form-control'}),
            'issue_limit_teacher': forms.NumberInput(attrs={'class': 'form-control'}),
            'default_loan_days': forms.NumberInput(attrs={'class': 'form-control'}),
            'fine_per_day': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.50'}),
            'max_fine': forms.NumberInput(attrs={'class': 'form-control', 'step': '1.00'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class BookCategoryForm(forms.ModelForm):
    class Meta:
        model = BookCategory
        fields = ['name', 'code', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Science & Tech'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. SCI'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class AuthorForm(forms.ModelForm):
    class Meta:
        model = Author
        fields = ['name', 'bio', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Dr. A.P.J. Abdul Kalam'}),
            'bio': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class PublisherForm(forms.ModelForm):
    class Meta:
        model = Publisher
        fields = ['name', 'address', 'phone', 'email', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Oxford University Press'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class LibraryShelfForm(forms.ModelForm):
    class Meta:
        model = LibraryShelf
        fields = ['name', 'code', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Shelf A-1'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'SH-A1'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class BookForm(forms.ModelForm):
    authors = forms.ModelMultipleChoiceField(
        queryset=Author.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'form-control select2'})
    )

    class Meta:
        model = Book
        fields = [
            'title', 'subtitle', 'isbn', 'category', 'publisher',
            'language', 'edition', 'publication_year', 'description', 'is_active'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Title'}),
            'subtitle': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Subtitle (Optional)'}),
            'isbn': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ISBN-10 / ISBN-13'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'publisher': forms.Select(attrs={'class': 'form-control'}),
            'language': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'English / Hindi'}),
            'edition': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 3rd Edition'}),
            'publication_year': forms.NumberInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        if school:
            self.fields['category'].queryset = BookCategory.objects.filter(school=school, is_active=True)
            self.fields['publisher'].queryset = Publisher.objects.filter(school=school, is_active=True)
            self.fields['authors'].queryset = Author.objects.filter(school=school, is_active=True)


class BookCopyForm(forms.ModelForm):
    class Meta:
        model = BookCopy
        fields = [
            'book', 'accession_number', 'barcode', 'shelf',
            'purchase_date', 'purchase_price', 'condition', 'status', 'notes'
        ]
        widgets = {
            'book': forms.Select(attrs={'class': 'form-control'}),
            'accession_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. ACC-1001'}),
            'barcode': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. BC1001'}),
            'shelf': forms.Select(attrs={'class': 'form-control'}),
            'purchase_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'purchase_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'condition': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        if school:
            self.fields['book'].queryset = Book.objects.filter(school=school, is_active=True)
            self.fields['shelf'].queryset = LibraryShelf.objects.filter(school=school, is_active=True)


class LibraryMemberForm(forms.ModelForm):
    class Meta:
        model = LibraryMember
        fields = ['member_code', 'member_type', 'student', 'teacher', 'max_books_override', 'is_active']
        widgets = {
            'member_code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. MEM-001'}),
            'member_type': forms.Select(attrs={'class': 'form-control'}),
            'student': forms.Select(attrs={'class': 'form-control'}),
            'teacher': forms.Select(attrs={'class': 'form-control'}),
            'max_books_override': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Leave blank for default'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        if school:
            self.fields['student'].queryset = Student.objects.filter(school=school, is_active=True)
            self.fields['teacher'].queryset = TeacherProfile.objects.filter(school=school, is_active=True)


class IssueBookForm(forms.Form):
    library = forms.ModelChoiceField(queryset=Library.objects.none(), widget=forms.Select(attrs={'class': 'form-control'}))
    member = forms.ModelChoiceField(queryset=LibraryMember.objects.none(), widget=forms.Select(attrs={'class': 'form-control'}))
    accession_number = forms.CharField(max_length=50, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter Accession / Barcode'}))
    loan_days = forms.IntegerField(required=False, widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Leave empty for default'}))
    remarks = forms.CharField(required=False, widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}))

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        if school:
            self.fields['library'].queryset = Library.objects.filter(school=school, is_active=True)
            self.fields['member'].queryset = LibraryMember.objects.filter(school=school, is_active=True)


class ReturnBookForm(forms.Form):
    waive_fine = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    waiver_reason = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Reason if waiving fine'}))
    remarks = forms.CharField(required=False, widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}))
