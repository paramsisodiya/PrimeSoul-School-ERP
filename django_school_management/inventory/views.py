"""
PrimeSoul School ERP - Phase 16: Inventory & Asset Management UI Views
Tenant-scoped, RBAC-protected views for complete stock, procurement,
issue, return, transfer, adjustment, asset registers, and maintenance.
"""
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from django.urls import reverse
from django.utils import timezone

from django_school_management.accounts.roles import Role, user_has_role
from django_school_management.tenants.models import School
from django_school_management.inventory.models import (
    InventoryCategory, UnitOfMeasure, Supplier, Store,
    InventoryItem, ItemStoreStock, StockMovement,
    PurchaseReceipt, PurchaseReceiptItem, StockIssue,
    StockReturn, StockTransfer, StockAdjustment,
    AssetCategory, Asset, AssetAssignment, AssetMaintenance
)
from django_school_management.inventory.forms import (
    InventoryCategoryForm, UnitOfMeasureForm, SupplierForm, StoreForm,
    InventoryItemForm, PurchaseReceiptForm, StockIssueForm,
    StockReturnForm, StockTransferForm, StockAdjustmentForm,
    AssetCategoryForm, AssetForm, AssetAssignmentForm,
    AssetReturnForm, AssetMaintenanceForm, AssetMaintenanceCompleteForm,
    AssetLifecycleForm
)
from django_school_management.inventory.services import inventory_service
from django_school_management.inventory.selectors import inventory_selectors


def _resolve_school(request) -> School:
    """Safely extracts tenant School from request context or user attributes."""
    if hasattr(request, 'tenant') and request.tenant:
        return request.tenant
    if hasattr(request, 'school') and request.school:
        return request.school
    if request.user.is_authenticated:
        user_school = getattr(request.user, 'school', None)
        if user_school:
            return user_school
    return School.objects.filter(is_active=True).first()


def _check_inventory_access(user, allow_read_only=False):
    """Verifies RBAC permissions for Inventory module."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    
    admin_roles = [
        Role.PLATFORM_SUPER_ADMIN,
        Role.SCHOOL_ADMIN,
        Role.PRINCIPAL,
        Role.VICE_PRINCIPAL,
        Role.ACCOUNTANT
    ]
    if user_has_role(user, *admin_roles):
        return True
        
    if allow_read_only and user_has_role(user, Role.TEACHER, Role.ACADEMIC_COORDINATOR, Role.LIBRARIAN, Role.TRANSPORT_MANAGER, Role.RECEPTIONIST):
        return True
        
    return False


# ==============================================================================
# DASHBOARD & REPORTS
# ==============================================================================

@login_required
def inventory_dashboard(request):
    """
    Overview of Inventory & Assets: KPIs, low-stock alerts, asset status breakdown.
    """
    if not _check_inventory_access(request.user, allow_read_only=True):
        raise PermissionDenied("Access restricted to authorized institutional staff.")

    school = _resolve_school(request)
    metrics = inventory_selectors.get_inventory_dashboard_metrics(school)

    context = {
        'school': school,
        'metrics': metrics,
        'is_admin': _check_inventory_access(request.user, allow_read_only=False),
    }
    return render(request, 'inventory/dashboard.html', context)


@login_required
def inventory_reports_overview(request):
    """Inventory & Asset analytical reports overview."""
    if not _check_inventory_access(request.user, allow_read_only=False):
        raise PermissionDenied("Access restricted to administrative staff.")
    school = _resolve_school(request)
    metrics = inventory_selectors.get_inventory_dashboard_metrics(school)
    return render(request, 'inventory/reports.html', {'school': school, 'metrics': metrics})


# ==============================================================================
# INVENTORY MASTER DATA
# ==============================================================================

@login_required
def category_list(request):
    if not _check_inventory_access(request.user, allow_read_only=False):
        raise PermissionDenied("Permission denied.")
    school = _resolve_school(request)
    categories = InventoryCategory.objects.filter(school=school).select_related('parent')

    if request.method == 'POST':
        form = InventoryCategoryForm(request.POST, school=school)
        if form.is_valid():
            cat = form.save(commit=False)
            cat.school = school
            cat.save()
            messages.success(request, f"Category '{cat.name}' saved successfully.")
            return redirect('inventory:category_list')
    else:
        form = InventoryCategoryForm(school=school)

    return render(request, 'inventory/categories.html', {
        'school': school,
        'categories': categories,
        'form': form
    })


@login_required
def store_list(request):
    if not _check_inventory_access(request.user, allow_read_only=False):
        raise PermissionDenied("Permission denied.")
    school = _resolve_school(request)
    stores = Store.objects.filter(school=school).select_related('manager')

    if request.method == 'POST':
        form = StoreForm(request.POST, school=school)
        if form.is_valid():
            st = form.save(commit=False)
            st.school = school
            st.save()
            messages.success(request, f"Store '{st.name}' [{st.code}] saved.")
            return redirect('inventory:store_list')
    else:
        form = StoreForm(school=school)

    return render(request, 'inventory/stores.html', {
        'school': school,
        'stores': stores,
        'form': form
    })


@login_required
def supplier_list(request):
    if not _check_inventory_access(request.user, allow_read_only=False):
        raise PermissionDenied("Permission denied.")
    school = _resolve_school(request)
    suppliers = Supplier.objects.filter(school=school)

    if request.method == 'POST':
        form = SupplierForm(request.POST)
        if form.is_valid():
            sup = form.save(commit=False)
            sup.school = school
            sup.save()
            messages.success(request, f"Vendor '{sup.name}' registered.")
            return redirect('inventory:supplier_list')
    else:
        form = SupplierForm()

    return render(request, 'inventory/suppliers.html', {
        'school': school,
        'suppliers': suppliers,
        'form': form
    })


@login_required
def item_list(request):
    if not _check_inventory_access(request.user, allow_read_only=True):
        raise PermissionDenied("Permission denied.")
    school = _resolve_school(request)
    category_id = request.GET.get('category')
    stock_status = request.GET.get('stock_status')
    search = request.GET.get('search', '').strip()

    items = InventoryItem.objects.filter(school=school).select_related('category', 'unit')
    if category_id:
        items = items.filter(category_id=category_id)
    if search:
        items = items.filter(name__icontains=search) | items.filter(sku__icontains=search)

    categories = InventoryCategory.objects.filter(school=school, is_active=True)
    
    paginator = Paginator(items, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'inventory/items.html', {
        'school': school,
        'page_obj': page_obj,
        'categories': categories,
        'selected_category': category_id,
        'search': search,
        'is_admin': _check_inventory_access(request.user, allow_read_only=False),
    })


@login_required
def item_create(request):
    if not _check_inventory_access(request.user, allow_read_only=False):
        raise PermissionDenied("Permission denied.")
    school = _resolve_school(request)

    if request.method == 'POST':
        form = InventoryItemForm(request.POST, school=school)
        if form.is_valid():
            item = form.save(commit=False)
            item.school = school
            if not item.sku:
                item.sku = inventory_service.generate_sku(school, item.category)
            item.save()
            messages.success(request, f"Item '{item.name}' ({item.sku}) created.")
            return redirect('inventory:item_detail', item_id=item.pk)
    else:
        form = InventoryItemForm(school=school)

    return render(request, 'inventory/item_form.html', {'school': school, 'form': form, 'title': 'Add New Inventory Item'})


@login_required
def item_detail(request, item_id):
    if not _check_inventory_access(request.user, allow_read_only=True):
        raise PermissionDenied("Permission denied.")
    school = _resolve_school(request)
    item = get_object_or_404(InventoryItem, school=school, pk=item_id)
    store_stocks = item.store_stocks.select_related('store').all()
    movements = item.stock_movements.select_related('source_store', 'destination_store', 'performed_by').order_by('-timestamp')[:20]

    return render(request, 'inventory/item_detail.html', {
        'school': school,
        'item': item,
        'store_stocks': store_stocks,
        'movements': movements,
        'is_admin': _check_inventory_access(request.user, allow_read_only=False),
    })


# ==============================================================================
# TRANSACTIONS & MOVEMENTS (GRN, ISSUE, RETURN, TRANSFER, ADJUSTMENT)
# ==============================================================================

@login_required
def purchase_list(request):
    if not _check_inventory_access(request.user, allow_read_only=False):
        raise PermissionDenied("Permission denied.")
    school = _resolve_school(request)
    purchases = PurchaseReceipt.objects.filter(school=school).select_related('supplier', 'store', 'received_by').prefetch_related('items__item')

    return render(request, 'inventory/purchases.html', {'school': school, 'purchases': purchases})


@login_required
def purchase_create(request):
    if not _check_inventory_access(request.user, allow_read_only=False):
        raise PermissionDenied("Permission denied.")
    school = _resolve_school(request)

    if request.method == 'POST':
        form = PurchaseReceiptForm(request.POST, school=school)
        item_ids = request.POST.getlist('item_id[]')
        quantities = request.POST.getlist('quantity[]')
        unit_costs = request.POST.getlist('unit_cost[]')

        if form.is_valid():
            if not item_ids:
                messages.error(request, "At least one line item is required for a goods receipt.")
            else:
                line_items_data = []
                for i in range(len(item_ids)):
                    if item_ids[i] and quantities[i]:
                        line_items_data.append({
                            'item_id': int(item_ids[i]),
                            'quantity': Decimal(quantities[i]),
                            'unit_cost': Decimal(unit_costs[i] or '0.00'),
                        })
                
                try:
                    receipt = inventory_service.receive_purchase_receipt(
                        school=school,
                        supplier=form.cleaned_data['supplier'],
                        store=form.cleaned_data['store'],
                        line_items_data=line_items_data,
                        receipt_number=form.cleaned_data.get('receipt_number'),
                        purchase_date=form.cleaned_data.get('purchase_date'),
                        received_by=request.user,
                        notes=form.cleaned_data.get('notes', '')
                    )
                    messages.success(request, f"Goods Receipt '{receipt.receipt_number}' recorded and stock added.")
                    return redirect('inventory:purchase_list')
                except ValidationError as e:
                    messages.error(request, str(e.message if hasattr(e, 'message') else e))
    else:
        form = PurchaseReceiptForm(school=school)

    items = InventoryItem.objects.filter(school=school, is_active=True)
    return render(request, 'inventory/purchase_form.html', {'school': school, 'form': form, 'items': items})


@login_required
def issue_list(request):
    if not _check_inventory_access(request.user, allow_read_only=False):
        raise PermissionDenied("Permission denied.")
    school = _resolve_school(request)
    issues = StockIssue.objects.filter(school=school).select_related(
        'item', 'store', 'recipient_employee', 'recipient_department', 'issued_by'
    )
    return render(request, 'inventory/issues.html', {'school': school, 'issues': issues})


@login_required
def issue_create(request):
    if not _check_inventory_access(request.user, allow_read_only=False):
        raise PermissionDenied("Permission denied.")
    school = _resolve_school(request)

    if request.method == 'POST':
        form = StockIssueForm(request.POST, school=school)
        if form.is_valid():
            try:
                issue = inventory_service.issue_stock(
                    school=school,
                    item=form.cleaned_data['item'],
                    store=form.cleaned_data['store'],
                    quantity=form.cleaned_data['quantity'],
                    recipient_type=form.cleaned_data['recipient_type'],
                    purpose=form.cleaned_data['purpose'],
                    recipient_employee=form.cleaned_data.get('recipient_employee'),
                    recipient_department=form.cleaned_data.get('recipient_department'),
                    recipient_name=form.cleaned_data.get('recipient_name', ''),
                    issue_date=form.cleaned_data.get('issue_date'),
                    issued_by=request.user,
                    notes=form.cleaned_data.get('notes', '')
                )
                messages.success(request, f"Stock issued successfully. Stock updated.")
                return redirect('inventory:issue_list')
            except ValidationError as e:
                messages.error(request, str(e.message if hasattr(e, 'message') else e))
    else:
        form = StockIssueForm(school=school)

    return render(request, 'inventory/issue_form.html', {'school': school, 'form': form})


@login_required
def return_list(request):
    if not _check_inventory_access(request.user, allow_read_only=False):
        raise PermissionDenied("Permission denied.")
    school = _resolve_school(request)
    returns = StockReturn.objects.filter(school=school).select_related('item', 'store', 'received_by', 'stock_issue')
    return render(request, 'inventory/returns.html', {'school': school, 'returns': returns})


@login_required
def return_create(request):
    if not _check_inventory_access(request.user, allow_read_only=False):
        raise PermissionDenied("Permission denied.")
    school = _resolve_school(request)

    if request.method == 'POST':
        form = StockReturnForm(request.POST, school=school)
        if form.is_valid():
            try:
                ret = inventory_service.return_stock(
                    school=school,
                    item=form.cleaned_data['item'],
                    store=form.cleaned_data['store'],
                    quantity=form.cleaned_data['quantity'],
                    stock_issue=form.cleaned_data.get('stock_issue'),
                    reason=form.cleaned_data.get('reason', ''),
                    condition=form.cleaned_data.get('condition', 'Good'),
                    return_date=form.cleaned_data.get('return_date'),
                    received_by=request.user,
                    notes=form.cleaned_data.get('notes', '')
                )
                messages.success(request, f"Stock return logged. Stock restored.")
                return redirect('inventory:return_list')
            except ValidationError as e:
                messages.error(request, str(e.message if hasattr(e, 'message') else e))
    else:
        form = StockReturnForm(school=school)

    return render(request, 'inventory/return_form.html', {'school': school, 'form': form})


@login_required
def transfer_list(request):
    if not _check_inventory_access(request.user, allow_read_only=False):
        raise PermissionDenied("Permission denied.")
    school = _resolve_school(request)
    transfers = StockTransfer.objects.filter(school=school).select_related(
        'item', 'source_store', 'destination_store', 'transferred_by'
    )
    return render(request, 'inventory/transfers.html', {'school': school, 'transfers': transfers})


@login_required
def transfer_create(request):
    if not _check_inventory_access(request.user, allow_read_only=False):
        raise PermissionDenied("Permission denied.")
    school = _resolve_school(request)

    if request.method == 'POST':
        form = StockTransferForm(request.POST, school=school)
        if form.is_valid():
            try:
                transfer = inventory_service.transfer_stock(
                    school=school,
                    item=form.cleaned_data['item'],
                    source_store=form.cleaned_data['source_store'],
                    destination_store=form.cleaned_data['destination_store'],
                    quantity=form.cleaned_data['quantity'],
                    reference_number=form.cleaned_data.get('reference_number', ''),
                    transfer_date=form.cleaned_data.get('transfer_date'),
                    transferred_by=request.user,
                    notes=form.cleaned_data.get('notes', '')
                )
                messages.success(request, f"Stock transfer completed between stores.")
                return redirect('inventory:transfer_list')
            except ValidationError as e:
                messages.error(request, str(e.message if hasattr(e, 'message') else e))
    else:
        form = StockTransferForm(school=school)

    return render(request, 'inventory/transfer_form.html', {'school': school, 'form': form})


@login_required
def adjustment_list(request):
    if not _check_inventory_access(request.user, allow_read_only=False):
        raise PermissionDenied("Permission denied.")
    school = _resolve_school(request)
    adjustments = StockAdjustment.objects.filter(school=school).select_related('item', 'store', 'performed_by')
    return render(request, 'inventory/adjustments.html', {'school': school, 'adjustments': adjustments})


@login_required
def adjustment_create(request):
    if not _check_inventory_access(request.user, allow_read_only=False):
        raise PermissionDenied("Permission denied.")
    school = _resolve_school(request)

    if request.method == 'POST':
        form = StockAdjustmentForm(request.POST, school=school)
        if form.is_valid():
            try:
                adj = inventory_service.adjust_stock(
                    school=school,
                    item=form.cleaned_data['item'],
                    store=form.cleaned_data['store'],
                    new_quantity=form.cleaned_data['new_quantity'],
                    reason=form.cleaned_data['reason'],
                    adjustment_date=form.cleaned_data.get('adjustment_date'),
                    performed_by=request.user
                )
                messages.success(request, f"Stock count adjusted. New balance: {adj.new_quantity}")
                return redirect('inventory:adjustment_list')
            except ValidationError as e:
                messages.error(request, str(e.message if hasattr(e, 'message') else e))
    else:
        form = StockAdjustmentForm(school=school)

    return render(request, 'inventory/adjustment_form.html', {'school': school, 'form': form})


@login_required
def movement_ledger(request):
    if not _check_inventory_access(request.user, allow_read_only=False):
        raise PermissionDenied("Permission denied.")
    school = _resolve_school(request)

    item_id = request.GET.get('item')
    store_id = request.GET.get('store')
    movement_type = request.GET.get('movement_type')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    movements_qs = inventory_selectors.get_stock_movement_ledger(
        school=school,
        item_id=int(item_id) if item_id else None,
        store_id=int(store_id) if store_id else None,
        movement_type=movement_type if movement_type else None,
        start_date=start_date if start_date else None,
        end_date=end_date if end_date else None
    )

    paginator = Paginator(movements_qs, 30)
    page_obj = paginator.get_page(request.GET.get('page'))

    items = InventoryItem.objects.filter(school=school, is_active=True)
    stores = Store.objects.filter(school=school, is_active=True)

    return render(request, 'inventory/movements.html', {
        'school': school,
        'page_obj': page_obj,
        'items': items,
        'stores': stores,
        'movement_types': StockMovement.MOVEMENT_TYPE_CHOICES,
        'selected_item': item_id,
        'selected_store': store_id,
        'selected_type': movement_type,
        'start_date': start_date,
        'end_date': end_date,
    })


# ==============================================================================
# ASSET MANAGEMENT (REGISTER, ASSIGNMENT, MAINTENANCE, LIFECYCLE)
# ==============================================================================

@login_required
def asset_category_list(request):
    if not _check_inventory_access(request.user, allow_read_only=False):
        raise PermissionDenied("Permission denied.")
    school = _resolve_school(request)
    categories = AssetCategory.objects.filter(school=school)

    if request.method == 'POST':
        form = AssetCategoryForm(request.POST)
        if form.is_valid():
            cat = form.save(commit=False)
            cat.school = school
            cat.save()
            messages.success(request, f"Asset Category '{cat.name}' saved.")
            return redirect('inventory:asset_category_list')
    else:
        form = AssetCategoryForm()

    return render(request, 'inventory/asset_categories.html', {
        'school': school,
        'categories': categories,
        'form': form
    })


@login_required
def asset_list(request):
    if not _check_inventory_access(request.user, allow_read_only=True):
        raise PermissionDenied("Permission denied.")
    school = _resolve_school(request)

    category_id = request.GET.get('category')
    status = request.GET.get('status')
    department_id = request.GET.get('department')
    search = request.GET.get('search')

    assets_qs = inventory_selectors.get_asset_register(
        school=school,
        category_id=int(category_id) if category_id else None,
        status=status if status else None,
        department_id=int(department_id) if department_id else None,
        search=search
    )

    paginator = Paginator(assets_qs, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    categories = AssetCategory.objects.filter(school=school, is_active=True)

    return render(request, 'inventory/assets.html', {
        'school': school,
        'page_obj': page_obj,
        'categories': categories,
        'statuses': Asset.STATUS_CHOICES,
        'selected_category': category_id,
        'selected_status': status,
        'search': search or '',
        'is_admin': _check_inventory_access(request.user, allow_read_only=False),
    })


@login_required
def asset_create(request):
    if not _check_inventory_access(request.user, allow_read_only=False):
        raise PermissionDenied("Permission denied.")
    school = _resolve_school(request)

    if request.method == 'POST':
        form = AssetForm(request.POST, school=school)
        if form.is_valid():
            asset = form.save(commit=False)
            asset.school = school
            if not asset.asset_tag:
                asset.asset_tag = inventory_service.generate_asset_tag(school, asset.category)
            asset.save()
            messages.success(request, f"Asset '{asset.name}' [{asset.asset_tag}] registered.")
            return redirect('inventory:asset_detail', asset_id=asset.pk)
    else:
        form = AssetForm(school=school)

    return render(request, 'inventory/asset_form.html', {'school': school, 'form': form, 'title': 'Register New Fixed Asset'})


@login_required
def asset_detail(request, asset_id):
    if not _check_inventory_access(request.user, allow_read_only=True):
        raise PermissionDenied("Permission denied.")
    school = _resolve_school(request)
    asset = inventory_selectors.get_asset_detail_with_history(asset_id, school)
    if not asset:
        raise PermissionDenied("Asset not found or unauthorized.")

    return render(request, 'inventory/asset_detail.html', {
        'school': school,
        'asset': asset,
        'is_admin': _check_inventory_access(request.user, allow_read_only=False),
    })


@login_required
def asset_assignment_list(request):
    if not _check_inventory_access(request.user, allow_read_only=False):
        raise PermissionDenied("Permission denied.")
    school = _resolve_school(request)
    assignments = AssetAssignment.objects.filter(school=school).select_related(
        'asset', 'assigned_to_employee', 'assigned_to_department', 'assigned_by'
    )
    return render(request, 'inventory/asset_assignments.html', {'school': school, 'assignments': assignments})


@login_required
def asset_assign(request, asset_id):
    if not _check_inventory_access(request.user, allow_read_only=False):
        raise PermissionDenied("Permission denied.")
    school = _resolve_school(request)
    asset = get_object_or_404(Asset, school=school, pk=asset_id)

    if request.method == 'POST':
        form = AssetAssignmentForm(request.POST, school=school)
        if form.is_valid():
            try:
                assignment = inventory_service.assign_asset(
                    school=school,
                    asset=asset,
                    assigned_to_employee=form.cleaned_data.get('assigned_to_employee'),
                    assigned_to_department=form.cleaned_data.get('assigned_to_department'),
                    location=form.cleaned_data.get('location', ''),
                    assigned_date=form.cleaned_data.get('assigned_date'),
                    assigned_by=request.user,
                    notes=form.cleaned_data.get('notes', '')
                )
                messages.success(request, f"Asset '{asset.asset_tag}' assigned successfully.")
                return redirect('inventory:asset_detail', asset_id=asset.pk)
            except ValidationError as e:
                messages.error(request, str(e.message if hasattr(e, 'message') else e))
    else:
        form = AssetAssignmentForm(school=school, initial={'asset': asset})

    return render(request, 'inventory/asset_assign_form.html', {'school': school, 'asset': asset, 'form': form})


@login_required
def asset_return(request, asset_id):
    if not _check_inventory_access(request.user, allow_read_only=False):
        raise PermissionDenied("Permission denied.")
    school = _resolve_school(request)
    asset = get_object_or_404(Asset, school=school, pk=asset_id)

    if request.method == 'POST':
        form = AssetReturnForm(request.POST)
        if form.is_valid():
            try:
                inventory_service.return_asset(
                    school=school,
                    asset=asset,
                    returned_date=form.cleaned_data.get('returned_date'),
                    condition=form.cleaned_data.get('condition'),
                    notes=form.cleaned_data.get('notes', '')
                )
                messages.success(request, f"Asset '{asset.asset_tag}' marked as returned to storage.")
                return redirect('inventory:asset_detail', asset_id=asset.pk)
            except ValidationError as e:
                messages.error(request, str(e.message if hasattr(e, 'message') else e))
    else:
        form = AssetReturnForm(initial={'returned_date': timezone.now().date(), 'condition': asset.condition})

    return render(request, 'inventory/asset_return_form.html', {'school': school, 'asset': asset, 'form': form})


@login_required
def maintenance_list(request):
    if not _check_inventory_access(request.user, allow_read_only=False):
        raise PermissionDenied("Permission denied.")
    school = _resolve_school(request)
    records = AssetMaintenance.objects.filter(school=school).select_related('asset', 'created_by')
    return render(request, 'inventory/maintenance.html', {'school': school, 'records': records})


@login_required
def maintenance_create(request, asset_id=None):
    if not _check_inventory_access(request.user, allow_read_only=False):
        raise PermissionDenied("Permission denied.")
    school = _resolve_school(request)

    initial_asset = get_object_or_404(Asset, school=school, pk=asset_id) if asset_id else None

    if request.method == 'POST':
        form = AssetMaintenanceForm(request.POST, school=school)
        if form.is_valid():
            try:
                rec = inventory_service.log_asset_maintenance_start(
                    school=school,
                    asset=form.cleaned_data['asset'],
                    maintenance_type=form.cleaned_data['maintenance_type'],
                    issue_description=form.cleaned_data['issue_description'],
                    service_provider=form.cleaned_data.get('service_provider', ''),
                    start_date=form.cleaned_data.get('start_date'),
                    estimated_cost=form.cleaned_data.get('cost', Decimal('0.00')),
                    created_by=request.user,
                    notes=form.cleaned_data.get('notes', '')
                )
                messages.success(request, f"Maintenance log logged for {rec.asset.asset_tag}.")
                return redirect('inventory:maintenance_list')
            except ValidationError as e:
                messages.error(request, str(e.message if hasattr(e, 'message') else e))
    else:
        form = AssetMaintenanceForm(school=school, initial={'asset': initial_asset} if initial_asset else None)

    return render(request, 'inventory/maintenance_form.html', {'school': school, 'form': form})


@login_required
def maintenance_complete(request, record_id):
    if not _check_inventory_access(request.user, allow_read_only=False):
        raise PermissionDenied("Permission denied.")
    school = _resolve_school(request)
    record = get_object_or_404(AssetMaintenance, asset__school=school, pk=record_id)

    if request.method == 'POST':
        form = AssetMaintenanceCompleteForm(request.POST)
        if form.is_valid():
            try:
                inventory_service.complete_asset_maintenance(
                    school=school,
                    maintenance_record=record,
                    completion_date=form.cleaned_data.get('completion_date'),
                    final_cost=form.cleaned_data.get('cost'),
                    restored_status=form.cleaned_data.get('restored_status'),
                    notes=form.cleaned_data.get('notes', '')
                )
                messages.success(request, f"Maintenance completed. Asset restored to active status.")
                return redirect('inventory:maintenance_list')
            except ValidationError as e:
                messages.error(request, str(e.message if hasattr(e, 'message') else e))
    else:
        form = AssetMaintenanceCompleteForm(initial={
            'completion_date': timezone.now().date(),
            'cost': record.cost,
            'restored_status': Asset.STATUS_AVAILABLE
        })

    return render(request, 'inventory/maintenance_complete_form.html', {'school': school, 'record': record, 'form': form})


@login_required
def asset_lifecycle_action(request, asset_id):
    """Mark damaged, lost, disposed or retired."""
    if not _check_inventory_access(request.user, allow_read_only=False):
        raise PermissionDenied("Permission denied.")
    school = _resolve_school(request)
    asset = get_object_or_404(Asset, school=school, pk=asset_id)

    if request.method == 'POST':
        form = AssetLifecycleForm(request.POST)
        if form.is_valid():
            try:
                inventory_service.dispose_or_retire_asset(
                    school=school,
                    asset=asset,
                    status=form.cleaned_data['action'],
                    reason=form.cleaned_data['reason'],
                    performed_by=request.user,
                    notes=form.cleaned_data.get('notes', '')
                )
                messages.success(request, f"Asset lifecycle updated to {asset.get_status_display()}.")
                return redirect('inventory:asset_detail', asset_id=asset.pk)
            except ValidationError as e:
                messages.error(request, str(e.message if hasattr(e, 'message') else e))
    else:
        form = AssetLifecycleForm()

    return render(request, 'inventory/asset_lifecycle_form.html', {'school': school, 'asset': asset, 'form': form})
