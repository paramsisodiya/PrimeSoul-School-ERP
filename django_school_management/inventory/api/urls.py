"""
PrimeSoul School ERP - Phase 16: Inventory & Asset Management REST API URLs
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from django_school_management.inventory.api import views

app_name = 'inventory_api'

router = DefaultRouter()
router.register(r'categories', views.InventoryCategoryViewSet, basename='category')
router.register(r'units', views.UnitOfMeasureViewSet, basename='unit')
router.register(r'suppliers', views.SupplierViewSet, basename='supplier')
router.register(r'stores', views.StoreViewSet, basename='store')
router.register(r'items', views.InventoryItemViewSet, basename='item')
router.register(r'movements', views.StockMovementViewSet, basename='movement')
router.register(r'purchases', views.PurchaseReceiptViewSet, basename='purchase')
router.register(r'issues', views.StockIssueViewSet, basename='issue')
router.register(r'returns', views.StockReturnViewSet, basename='return')
router.register(r'transfers', views.StockTransferViewSet, basename='transfer')
router.register(r'adjustments', views.StockAdjustmentViewSet, basename='adjustment')
router.register(r'asset-categories', views.AssetCategoryViewSet, basename='asset_category')
router.register(r'assets', views.AssetViewSet, basename='asset')
router.register(r'maintenance', views.AssetMaintenanceViewSet, basename='maintenance')

urlpatterns = [
    path('dashboard/', views.InventoryDashboardAPIView.as_view(), name='dashboard'),
    path('', include(router.urls)),
]
