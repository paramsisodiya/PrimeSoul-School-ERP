"""
PrimeSoul School ERP - Phase 16: Inventory & Asset Management URLs
"""
from django.urls import path
from django_school_management.inventory import views

app_name = 'inventory'

urlpatterns = [
    # Dashboard & Reports
    path('', views.inventory_dashboard, name='dashboard'),
    path('reports/', views.inventory_reports_overview, name='reports'),

    # Masters: Categories, Stores, Suppliers
    path('categories/', views.category_list, name='category_list'),
    path('stores/', views.store_list, name='store_list'),
    path('suppliers/', views.supplier_list, name='supplier_list'),

    # Items
    path('items/', views.item_list, name='item_list'),
    path('items/new/', views.item_create, name='item_create'),
    path('items/<int:item_id>/', views.item_detail, name='item_detail'),

    # Stock Transactions
    path('purchases/', views.purchase_list, name='purchase_list'),
    path('purchases/new/', views.purchase_create, name='purchase_create'),
    path('issues/', views.issue_list, name='issue_list'),
    path('issues/new/', views.issue_create, name='issue_create'),
    path('returns/', views.return_list, name='return_list'),
    path('returns/new/', views.return_create, name='return_create'),
    path('transfers/', views.transfer_list, name='transfer_list'),
    path('transfers/new/', views.transfer_create, name='transfer_create'),
    path('adjustments/', views.adjustment_list, name='adjustment_list'),
    path('adjustments/new/', views.adjustment_create, name='adjustment_create'),
    path('movements/', views.movement_ledger, name='movement_ledger'),

    # Asset Management
    path('asset-categories/', views.asset_category_list, name='asset_category_list'),
    path('assets/', views.asset_list, name='asset_list'),
    path('assets/new/', views.asset_create, name='asset_create'),
    path('assets/<int:asset_id>/', views.asset_detail, name='asset_detail'),
    path('assets/<int:asset_id>/assign/', views.asset_assign, name='asset_assign'),
    path('assets/<int:asset_id>/return/', views.asset_return, name='asset_return'),
    path('assets/<int:asset_id>/lifecycle/', views.asset_lifecycle_action, name='asset_lifecycle'),
    path('asset-assignments/', views.asset_assignment_list, name='asset_assignment_list'),

    # Asset Maintenance
    path('maintenance/', views.maintenance_list, name='maintenance_list'),
    path('maintenance/new/', views.maintenance_create, name='maintenance_create'),
    path('maintenance/new/<int:asset_id>/', views.maintenance_create, name='maintenance_create_for_asset'),
    path('maintenance/<int:record_id>/complete/', views.maintenance_complete, name='maintenance_complete'),
]
