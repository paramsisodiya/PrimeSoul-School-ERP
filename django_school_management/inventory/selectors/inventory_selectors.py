"""
PrimeSoul School ERP - Phase 16: Inventory & Asset Selectors
Tenant-scoped, optimized database queries and metric aggregations.
"""
from decimal import Decimal
from typing import Optional, Dict, Any, List
from django.db.models import Count, Sum, Q, F, DecimalField, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from django_school_management.tenants.models import School
from django_school_management.inventory.models import (
    InventoryCategory, UnitOfMeasure, Supplier, Store,
    InventoryItem, ItemStoreStock, StockMovement,
    PurchaseReceipt, StockIssue, StockReturn, StockTransfer, StockAdjustment,
    AssetCategory, Asset, AssetAssignment, AssetMaintenance
)


def get_inventory_dashboard_metrics(school: School) -> Dict[str, Any]:
    """
    Computes real, live database metrics for the Inventory & Asset Management overview dashboard.
    """
    # 1. Consumable Inventory Counts
    total_items = InventoryItem.objects.filter(school=school, is_active=True).count()
    total_stores = Store.objects.filter(school=school, is_active=True).count()
    total_suppliers = Supplier.objects.filter(school=school, is_active=True).count()

    # Aggregate item store stock
    stock_agg = ItemStoreStock.objects.filter(school=school).aggregate(
        total_quantity=Coalesce(Sum('quantity'), Value(Decimal('0.00'), output_field=DecimalField()))
    )
    total_stock_qty = stock_agg['total_quantity']

    # Items annotated with current total stock
    items_annotated = InventoryItem.objects.filter(school=school, is_active=True).annotate(
        current_stock=Coalesce(Sum('store_stocks__quantity'), Value(Decimal('0.00'), output_field=DecimalField()))
    )

    out_of_stock_count = items_annotated.filter(current_stock__lte=0).count()
    low_stock_count = items_annotated.filter(
        current_stock__gt=0,
        current_stock__lte=F('reorder_level')
    ).count()
    healthy_stock_count = items_annotated.filter(current_stock__gt=F('reorder_level')).count()

    # 2. Asset Counts & Status Breakdown
    asset_counts = Asset.objects.filter(school=school).aggregate(
        total_assets=Count('id'),
        available=Count('id', filter=Q(status=Asset.STATUS_AVAILABLE)),
        assigned=Count('id', filter=Q(status=Asset.STATUS_ASSIGNED)),
        in_repair=Count('id', filter=Q(status=Asset.STATUS_IN_REPAIR)),
        lost=Count('id', filter=Q(status=Asset.STATUS_LOST)),
        damaged=Count('id', filter=Q(status=Asset.STATUS_DAMAGED)),
        disposed=Count('id', filter=Q(status=Asset.STATUS_DISPOSED)),
        retired=Count('id', filter=Q(status=Asset.STATUS_RETIRED)),
        total_valuation=Coalesce(Sum('purchase_cost'), Value(Decimal('0.00'), output_field=DecimalField()))
    )

    lost_damaged_count = asset_counts['lost'] + asset_counts['damaged']
    retired_disposed_count = asset_counts['retired'] + asset_counts['disposed']

    # 3. Recent Activity Lists
    recent_movements = (
        StockMovement.objects.filter(school=school)
        .select_related('item', 'source_store', 'destination_store', 'performed_by', 'item__unit')
        .order_by('-timestamp')[:8]
    )

    recent_assignments = (
        AssetAssignment.objects.filter(school=school)
        .select_related('asset', 'assigned_to_employee', 'assigned_to_department', 'assigned_by')
        .order_by('-assigned_date', '-created')[:6]
    )

    pending_maintenance = (
        AssetMaintenance.objects.filter(
            school=school,
            status__in=[AssetMaintenance.STATUS_OPEN, AssetMaintenance.STATUS_IN_PROGRESS]
        )
        .select_related('asset', 'asset__category', 'created_by')
        .order_by('-start_date')[:6]
    )

    return {
        'total_items': total_items,
        'total_stores': total_stores,
        'total_suppliers': total_suppliers,
        'total_stock_qty': total_stock_qty,
        'low_stock_count': low_stock_count,
        'out_of_stock_count': out_of_stock_count,
        'healthy_stock_count': healthy_stock_count,
        'total_assets': asset_counts['total_assets'],
        'available_assets': asset_counts['available'],
        'assigned_assets': asset_counts['assigned'],
        'in_repair_assets': asset_counts['in_repair'],
        'lost_damaged_count': lost_damaged_count,
        'retired_disposed_count': retired_disposed_count,
        'total_valuation': asset_counts['total_valuation'],
        'recent_movements': recent_movements,
        'recent_assignments': recent_assignments,
        'pending_maintenance': pending_maintenance,
    }


def get_low_stock_items(school: School):
    """Returns items where current stock <= reorder level and > 0."""
    return (
        InventoryItem.objects.filter(school=school, is_active=True)
        .annotate(
            current_stock=Coalesce(Sum('store_stocks__quantity'), Value(Decimal('0.00'), output_field=DecimalField()))
        )
        .filter(current_stock__gt=0, current_stock__lte=F('reorder_level'))
        .select_related('category', 'unit')
        .order_by('name')
    )


def get_out_of_stock_items(school: School):
    """Returns items where current stock <= 0."""
    return (
        InventoryItem.objects.filter(school=school, is_active=True)
        .annotate(
            current_stock=Coalesce(Sum('store_stocks__quantity'), Value(Decimal('0.00'), output_field=DecimalField()))
        )
        .filter(current_stock__lte=0)
        .select_related('category', 'unit')
        .order_by('name')
    )


def get_store_stock_summary(school: School, store_id: Optional[int] = None):
    """Returns inventory stock breakdown per item and store."""
    qs = ItemStoreStock.objects.filter(school=school).select_related('item', 'item__category', 'item__unit', 'store')
    if store_id:
        qs = qs.filter(store_id=store_id)
    return qs.order_by('store__name', 'item__name')


def get_stock_movement_ledger(
    school: School,
    item_id: Optional[int] = None,
    store_id: Optional[int] = None,
    movement_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """Filtered stock movement ledger."""
    qs = StockMovement.objects.filter(school=school).select_related(
        'item', 'item__unit', 'source_store', 'destination_store', 'performed_by'
    )
    if item_id:
        qs = qs.filter(item_id=item_id)
    if store_id:
        qs = qs.filter(Q(source_store_id=store_id) | Q(destination_store_id=store_id))
    if movement_type:
        qs = qs.filter(movement_type=movement_type)
    if start_date:
        qs = qs.filter(timestamp__date__gte=start_date)
    if end_date:
        qs = qs.filter(timestamp__date__lte=end_date)
    return qs.order_by('-timestamp', '-created')


def get_asset_register(
    school: School,
    category_id: Optional[int] = None,
    status: Optional[str] = None,
    department_id: Optional[int] = None,
    employee_id: Optional[int] = None,
    search: Optional[str] = None
):
    """Filtered Fixed Asset Register."""
    qs = Asset.objects.filter(school=school).select_related(
        'category', 'supplier', 'department', 'assigned_employee'
    )
    if category_id:
        qs = qs.filter(category_id=category_id)
    if status:
        qs = qs.filter(status=status)
    if department_id:
        qs = qs.filter(department_id=department_id)
    if employee_id:
        qs = qs.filter(assigned_employee_id=employee_id)
    if search:
        search = search.strip()
        qs = qs.filter(
            Q(name__icontains=search) |
            Q(asset_tag__icontains=search) |
            Q(serial_number__icontains=search) |
            Q(model_number__icontains=search) |
            Q(current_location__icontains=search)
        )
    return qs.order_by('name', 'asset_tag')


def get_asset_detail_with_history(asset_id: int, school: School) -> Optional[Asset]:
    """Fetches asset with prefetched assignments and maintenance logs."""
    return (
        Asset.objects.filter(school=school, pk=asset_id)
        .select_related('category', 'supplier', 'department', 'assigned_employee')
        .prefetch_related(
            'assignment_history__assigned_to_employee',
            'assignment_history__assigned_to_department',
            'assignment_history__assigned_by',
            'maintenance_records__created_by'
        )
        .first()
    )


# Backward compatibility aliases
get_inventory_dashboard_kpis = get_inventory_dashboard_metrics


def get_inventory_items(school: School):
    """Returns all active inventory items for a school."""
    return (
        InventoryItem.objects.filter(school=school, is_active=True)
        .select_related('category', 'unit')
        .order_by('name')
    )

