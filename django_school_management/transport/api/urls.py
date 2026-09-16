from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    TransportVehicleViewSet, TransportStaffViewSet,
    TransportRouteViewSet, TransportStopViewSet,
    VehicleRouteAssignmentViewSet, StudentTransportAssignmentViewSet,
    TransportDashboardAPIView, MyTransportAPIView
)

router = DefaultRouter()
router.register(r'vehicles', TransportVehicleViewSet, basename='vehicle')
router.register(r'staff', TransportStaffViewSet, basename='staff')
router.register(r'routes', TransportRouteViewSet, basename='route')
router.register(r'stops', TransportStopViewSet, basename='stop')
router.register(r'assignments', VehicleRouteAssignmentViewSet, basename='assignment')
router.register(r'students', StudentTransportAssignmentViewSet, basename='student-assignment')

urlpatterns = [
    path('dashboard/', TransportDashboardAPIView.as_view(), name='dashboard'),
    path('my-transport/', MyTransportAPIView.as_view(), name='my_transport'),
    path('', include(router.urls)),
]
