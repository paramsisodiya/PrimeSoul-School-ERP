from django.urls import path
from . import views

app_name = 'timetable'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('setup/', views.setup_view, name='setup'),
    path('setup/day/<int:pk>/toggle/', views.working_day_toggle_view, name='working_day_toggle'),
    path('setup/slot/create/', views.time_slot_create_view, name='time_slot_create'),
    path('setup/slot/<int:pk>/delete/', views.time_slot_delete_view, name='time_slot_delete'),
    path('setup/room/create/', views.classroom_create_view, name='classroom_create'),
    path('setup/room/<int:pk>/delete/', views.classroom_delete_view, name='classroom_delete'),
    path('weekly/', views.weekly_view, name='weekly'),
    path('class/', views.class_timetable_view, name='class_timetable_default'),
    path('class/<int:section_id>/', views.class_timetable_view, name='class_timetable'),
    path('teacher/', views.teacher_timetable_view, name='teacher_timetable_default'),
    path('teacher/<int:teacher_id>/', views.teacher_timetable_view, name='teacher_timetable'),
    path('rooms/', views.rooms_view, name='rooms_default'),
    path('rooms/<int:room_id>/', views.rooms_view, name='rooms'),
    path('generate/', views.generate_view, name='generate'),
    path('entry/create/', views.entry_create_view, name='entry_create'),
    path('entry/<int:pk>/delete/', views.entry_delete_view, name='entry_delete'),
    path('clone/', views.clone_view, name='clone'),
    path('clear/', views.clear_view, name='clear'),
    path('export/csv/', views.export_csv_view, name='export_csv'),
    path('my-timetable/', views.my_timetable_view, name='my_timetable'),
]
