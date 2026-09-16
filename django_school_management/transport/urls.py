from django.urls import path
from . import views

app_name = 'transport'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('vehicles/', views.vehicles_view, name='vehicles'),
    path('vehicles/create/', views.vehicle_create_view, name='vehicle_create'),
    path('vehicles/<int:pk>/toggle/', views.vehicle_delete_view, name='vehicle_toggle'),
    path('routes/', views.routes_view, name='routes'),
    path('routes/create/', views.route_create_view, name='route_create'),
    path('routes/<int:pk>/', views.route_detail_view, name='route_detail'),
    path('routes/<int:route_id>/stops/create/', views.stop_create_view, name='stop_create'),
    path('stops/<int:pk>/delete/', views.stop_delete_view, name='stop_delete'),
    path('staff/', views.staff_view, name='staff'),
    path('staff/create/', views.staff_create_view, name='staff_create'),
    path('assignments/create/', views.assignment_create_view, name='assignment_create'),
    path('students/', views.students_view, name='students'),
    path('students/assign/', views.student_assign_view, name='student_assign'),
    path('students/<int:pk>/status/', views.student_status_toggle_view, name='student_status_toggle'),
    path('my-transport/', views.my_transport_view, name='my_transport'),
]
