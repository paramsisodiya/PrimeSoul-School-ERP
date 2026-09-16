from django.urls import path
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'libraries', views.LibraryViewSet, basename='library')
router.register(r'categories', views.BookCategoryViewSet, basename='book-category')
router.register(r'authors', views.AuthorViewSet, basename='author')
router.register(r'publishers', views.PublisherViewSet, basename='publisher')
router.register(r'shelves', views.LibraryShelfViewSet, basename='shelf')
router.register(r'books', views.BookViewSet, basename='book')
router.register(r'copies', views.BookCopyViewSet, basename='book-copy')
router.register(r'members', views.LibraryMemberViewSet, basename='member')
router.register(r'issues', views.LibraryIssueViewSet, basename='issue')

urlpatterns = router.urls + [
    path('issue/', views.IssueBookAPIView.as_view(), name='api-issue-book'),
    path('return/', views.ReturnBookAPIView.as_view(), name='api-return-book'),
    path('dashboard/', views.LibraryDashboardAPIView.as_view(), name='api-library-dashboard'),
    path('my-library/', views.MyLibraryAPIView.as_view(), name='api-my-library'),
]
