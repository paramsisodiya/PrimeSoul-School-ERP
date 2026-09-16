from django.urls import path
from . import views

app_name = 'library'

urlpatterns = [
    path('', views.library_dashboard, name='dashboard'),
    path('books/', views.book_list, name='books'),
    path('books/add/', views.book_create, name='book_create'),
    path('books/<int:pk>/', views.book_detail, name='book_detail'),
    path('books/<int:book_pk>/add-copy/', views.book_copy_create, name='book_copy_create'),
    path('members/', views.member_list, name='members'),
    path('issues/', views.issue_list, name='issues'),
    path('issues/new/', views.issue_book_view, name='issue_book'),
    path('issues/<int:issue_pk>/return/', views.return_book_view, name='return_book'),
    path('overdue/', views.overdue_list, name='overdue'),
    path('fines/', views.fines_list, name='fines'),
    path('my-library/', views.my_library, name='my_library'),
]
