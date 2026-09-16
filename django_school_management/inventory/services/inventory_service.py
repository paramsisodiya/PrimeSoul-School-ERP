"""
PrimeSoul School ERP - Phase 16: Inventory & Asset Management Services
Atomic, transactional domain logic for stock movements, goods receipts,
stock issues, returns, transfers, adjustments, and asset lifecycles.
"""
import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any

from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone

from django_school_management.tenants.models import School
from django_school_management.inventory.models import (
    InventoryCategory, UnitOfMeasure, Supplier, Store,
    InventoryItem, ItemStoreStock, StockMovement,
    PurchaseReceipt, PurchaseReceiptItem, StockIssue,
    StockReturn, StockTransfer, StockAdjustment,
    AssetCategory, Asset, AssetAssignment, AssetMaintenance
)


# ==============================================================================
# NUMBERING HELPERS
# ==============================================================================

def generate_sku(school: School, category: InventoryCategory) -> str:
    """Generates unique sequential SKU for an inventory item (e.g. STN-00001)."""
    prefix = category.name[:3].upper() if category and category.name else "ITM"
    prefix = f"{prefix}-"
    last_item = (
        InventoryItem.objects.filter(school=school, sku__startswith=prefix)
        .order_by('-sku')
        .values_list('sku', flat=True)
        .first()
    )
    if last_item:
        try:
            seq_part = last_item.replace(prefix, "")
            next_seq = int(seq_part) + 1
        except (ValueError, TypeError):
            next_seq = InventoryItem.objects.filter(school=school, sku__startswith=prefix).count() + 1
    else:
        next_seq = 1
    return f"{prefix}{next_seq:05d}"


def generate_asset_tag(school: School, category: Optional[AssetCategory] = None) -> str:
    """Generates unique sequential Asset Tag (e.g. AST-00001 or IT-00001)."""
    prefix = category.name[:3].upper() if category and category.name else "AST"
    prefix = f"{prefix}-"
    last_tag = (
        Asset.objects.filter(school=school, asset_tag__startswith=prefix)
        .order_by('-asset_tag')
        .values_list('asset_tag', flat=True)
        .first()
    )
    if last_tag:
        try:
            seq_part = last_tag.replace(prefix, "")
            next_seq = int(seq_part) + 1
        except (ValueError, TypeError):
            next_seq = Asset.objects.filter(school=school, asset_tag__startswith=prefix).count() + 1
    else:
        next_seq = 1
    return f"{prefix}{next_seq:05d}"


def generate_purchase_receipt_number(school: School, year: Optional[int] = None) -> str:
    """Generates sequential Goods Receipt Note (GRN) number (e.g. GRN-2026-00001)."""
    if not year:
        year = timezone.now().year
    prefix = f"GRN-{year}-"
    last_rcp = (
        PurchaseReceipt.objects.filter(school=school, receipt_number__startswith=prefix)
        .order_by('-receipt_number')
        .values_list('receipt_number', flat=True)
        .first()
    )
    if last_rcp:
        try:
            seq_part = last_rcp.replace(prefix, "")
            next_seq = int(seq_part) + 1
        except (ValueError, TypeError):
            next_seq = PurchaseReceipt.objects.filter(school=school, receipt_number__startswith=prefix).count() + 1
    else:
        next_seq = 1
    return f"{prefix}{next_seq:05d}"


# ==============================================================================
# STORE STOCK & LEDGER HELPERS
# ==============================================================================

def get_or_create_store_stock(school: School, item: InventoryItem, store: Store) -> ItemStoreStock:
    """Retrieves or creates store-level inventory balance record."""
    stock, _ = ItemStoreStock.objects.get_or_create(
        school=school,
        item=item,
        store=store,
        defaults={'quantity': Decimal('0.00')}
    )
    return stock


# ==============================================================================
# GOODS RECEIPT / PURCHASE SERVICES
# ==============================================================================

@transaction.atomic
def receive_purchase_receipt(receipt: PurchaseReceipt, user=None) -> PurchaseReceipt:
    """
    Confirms a Goods Receipt Note (GRN), updates store stock atomically,
    and logs immutable IN stock movements for each item.
    """
    if receipt.status != PurchaseReceipt.STATUS_DRAFT:
        raise ValidationError(f"Cannot receive purchase: Receipt is already in '{receipt.status}' status.")

    items = receipt.items.select_related('item').all()
    if not items.exists():
        raise ValidationError("Cannot receive an empty purchase receipt. Add at least one item.")

    school = receipt.school
    store = receipt.store

    total_amount = Decimal('0.00')
    for line in items:
        qty = line.quantity
        if qty <= Decimal('0.00'):
            raise ValidationError(f"Invalid quantity {qty} for item {line.item.name}. Must be greater than 0.")

        unit_cost = line.unit_cost or Decimal('0.00')
        line_total = qty * unit_cost
        line.total_cost = line_total
        line.save(update_fields=['total_cost'])
        total_amount += line_total

        # Atomic stock increment
        stock = get_or_create_store_stock(school, line.item, store)
        stock.quantity += qty
        stock.save(update_fields=['quantity', 'updated_at'])

        # Stock Movement Ledger Entry
        StockMovement.objects.create(
            school=school,
            item=line.item,
            movement_type=StockMovement.TYPE_IN,
            destination_store=store,
            quantity=qty,
            unit_cost=unit_cost,
            total_cost=line_total,
            reference_number=receipt.receipt_number,
            reason="Purchase Receipt / GRN",
            performed_by=user or receipt.received_by,
            timestamp=timezone.now()
        )

    receipt.total_amount = total_amount
    receipt.status = PurchaseReceipt.STATUS_RECEIVED
    receipt.received_by = user or receipt.received_by
    receipt.save(update_fields=['total_amount', 'status', 'received_by', 'updated_at'])

    return receipt


# ==============================================================================
# STOCK ISSUE & RETURN SERVICES
# ==============================================================================

@transaction.atomic
def issue_stock(
    school: School,
    item: InventoryItem,
    store: Store,
    quantity: Decimal,
    purpose: str,
    recipient_type: str = StockIssue.RECIPIENT_EMPLOYEE,
    recipient_employee=None,
    recipient_department=None,
    recipient_name: str = '',
    user=None,
    issue_date: Optional[datetime.date] = None,
    notes: str = ''
) -> StockIssue:
    """
    Issues consumable stock from a store to an employee, department, or student.
    Enforces non-negative inventory constraints and creates an immutable OUT movement.
    """
    quantity = Decimal(str(quantity))
    if quantity <= Decimal('0.00'):
        raise ValidationError("Issue quantity must be greater than 0.")

    stock = get_or_create_store_stock(school, item, store)
    if stock.quantity < quantity:
        raise ValidationError(
            f"Insufficient stock for '{item.name}' in {store.name}. "
            f"Requested: {quantity} {item.unit.short_code}, Available: {stock.quantity} {item.unit.short_code}."
        )

    # Decrement stock
    stock.quantity -= quantity
    stock.save(update_fields=['quantity', 'updated_at'])

    issue = StockIssue.objects.create(
        school=school,
        item=item,
        store=store,
        quantity=quantity,
        returned_quantity=Decimal('0.00'),
        recipient_type=recipient_type,
        recipient_employee=recipient_employee,
        recipient_department=recipient_department,
        recipient_name=recipient_name,
        purpose=purpose,
        issue_date=issue_date or timezone.now().date(),
        issued_by=user,
        status=StockIssue.STATUS_ISSUED,
        notes=notes
    )

    StockMovement.objects.create(
        school=school,
        item=item,
        movement_type=StockMovement.TYPE_OUT,
        source_store=store,
        quantity=quantity,
        unit_cost=item.default_purchase_price,
        total_cost=quantity * item.default_purchase_price,
        reference_number=f"ISSUE-{issue.id}",
        reason=purpose,
        performed_by=user,
        timestamp=timezone.now()
    )

    return issue


@transaction.atomic
def return_stock(
    school: School,
    item: InventoryItem,
    store: Store,
    quantity: Decimal,
    stock_issue: Optional[StockIssue] = None,
    user=None,
    return_date: Optional[datetime.date] = None,
    reason: str = '',
    condition: str = 'Good',
    notes: str = ''
) -> StockReturn:
    """
    Returns issued stock back into a store. Updates issue record and creates a RETURN movement.
    """
    quantity = Decimal(str(quantity))
    if quantity <= Decimal('0.00'):
        raise ValidationError("Return quantity must be greater than 0.")

    if stock_issue:
        if stock_issue.item != item:
            raise ValidationError("Returned item does not match the original stock issue item.")
        remaining = stock_issue.quantity - stock_issue.returned_quantity
        if quantity > remaining:
            raise ValidationError(
                f"Cannot return {quantity} {item.unit.short_code}. "
                f"Only {remaining} {item.unit.short_code} pending return on this issue."
            )
        stock_issue.returned_quantity += quantity
        if stock_issue.returned_quantity >= stock_issue.quantity:
            stock_issue.status = StockIssue.STATUS_RETURNED_FULL
        else:
            stock_issue.status = StockIssue.STATUS_RETURNED_PARTIAL
        stock_issue.save(update_fields=['returned_quantity', 'status', 'updated_at'])

    stock = get_or_create_store_stock(school, item, store)
    stock.quantity += quantity
    stock.save(update_fields=['quantity', 'updated_at'])

    ret = StockReturn.objects.create(
        school=school,
        stock_issue=stock_issue,
        item=item,
        store=store,
        quantity=quantity,
        return_date=return_date or timezone.now().date(),
        received_by=user,
        reason=reason,
        condition=condition,
        notes=notes
    )

    StockMovement.objects.create(
        school=school,
        item=item,
        movement_type=StockMovement.TYPE_RETURN,
        destination_store=store,
        quantity=quantity,
        unit_cost=item.default_purchase_price,
        total_cost=quantity * item.default_purchase_price,
        reference_number=f"RET-{ret.id}",
        reason=reason or "Stock Return",
        performed_by=user,
        timestamp=timezone.now()
    )

    return ret


# ==============================================================================
# STORE TRANSFER SERVICES
# ==============================================================================

@transaction.atomic
def transfer_stock(
    school: School,
    item: InventoryItem,
    source_store: Store,
    destination_store: Store,
    quantity: Decimal,
    user=None,
    transfer_date: Optional[datetime.date] = None,
    notes: str = ''
) -> StockTransfer:
    """
    Atomically transfers stock between two stores of the same school tenant.
    """
    if source_store == destination_store:
        raise ValidationError("Source store and destination store cannot be the same.")

    if source_store.school != school or destination_store.school != school:
        raise ValidationError("Both source and destination stores must belong to the same school tenant.")

    quantity = Decimal(str(quantity))
    if quantity <= Decimal('0.00'):
        raise ValidationError("Transfer quantity must be greater than 0.")

    src_stock = get_or_create_store_stock(school, item, source_store)
    if src_stock.quantity < quantity:
        raise ValidationError(
            f"Insufficient stock in '{source_store.name}' for transfer. "
            f"Available: {src_stock.quantity} {item.unit.short_code}, Requested: {quantity} {item.unit.short_code}."
        )

    # 1. Decrement source store
    src_stock.quantity -= quantity
    src_stock.save(update_fields=['quantity', 'updated_at'])

    # 2. Increment destination store
    dest_stock = get_or_create_store_stock(school, item, destination_store)
    dest_stock.quantity += quantity
    dest_stock.save(update_fields=['quantity', 'updated_at'])

    # 3. Create Transfer record
    ref_no = f"TRF-{timezone.now().strftime('%Y%m%d%H%M%S')}"
    transfer = StockTransfer.objects.create(
        school=school,
        item=item,
        source_store=source_store,
        destination_store=destination_store,
        quantity=quantity,
        transfer_date=transfer_date or timezone.now().date(),
        reference_number=ref_no,
        transferred_by=user,
        notes=notes
    )

    # 4. Create Ledger Movement
    StockMovement.objects.create(
        school=school,
        item=item,
        movement_type=StockMovement.TYPE_TRANSFER,
        source_store=source_store,
        destination_store=destination_store,
        quantity=quantity,
        unit_cost=item.default_purchase_price,
        total_cost=quantity * item.default_purchase_price,
        reference_number=ref_no,
        reason=f"Transfer: {source_store.name} -> {destination_store.name}",
        performed_by=user,
        timestamp=timezone.now()
    )

    return transfer


# ==============================================================================
# STOCK ADJUSTMENT SERVICES
# ==============================================================================

@transaction.atomic
def adjust_stock(
    school: School,
    item: InventoryItem,
    store: Store,
    new_quantity: Decimal,
    reason: str,
    user=None,
    adjustment_date: Optional[datetime.date] = None
) -> StockAdjustment:
    """
    Applies physical count correction to stock. Calculates delta and creates audit trail.
    """
    new_quantity = Decimal(str(new_quantity))
    if new_quantity < Decimal('0.00'):
        raise ValidationError("Stock quantity cannot be negative.")

    if not reason or not reason.strip():
        raise ValidationError("A valid reason is required for stock count adjustment.")

    stock = get_or_create_store_stock(school, item, store)
    previous_qty = stock.quantity
    delta = new_quantity - previous_qty

    stock.quantity = new_quantity
    stock.save(update_fields=['quantity', 'updated_at'])

    adj = StockAdjustment.objects.create(
        school=school,
        item=item,
        store=store,
        previous_quantity=previous_qty,
        new_quantity=new_quantity,
        delta_quantity=delta,
        reason=reason.strip(),
        adjustment_date=adjustment_date or timezone.now().date(),
        performed_by=user
    )

    StockMovement.objects.create(
        school=school,
        item=item,
        movement_type=StockMovement.TYPE_ADJUSTMENT,
        source_store=store if delta < 0 else None,
        destination_store=store if delta > 0 else None,
        quantity=abs(delta),
        unit_cost=item.default_purchase_price,
        total_cost=abs(delta) * item.default_purchase_price,
        reference_number=f"ADJ-{adj.id}",
        reason=reason.strip(),
        performed_by=user,
        timestamp=timezone.now()
    )

    return adj


# ==============================================================================
# ASSET LIFECYCLE & ASSIGNMENT SERVICES
# ==============================================================================

@transaction.atomic
def assign_asset(
    asset: Asset,
    assigned_to_employee=None,
    assigned_to_department=None,
    location: str = '',
    assigned_by=None,
    assigned_date: Optional[datetime.date] = None,
    notes: str = ''
) -> AssetAssignment:
    """
    Assigns an asset to an employee or department, preserving full historical records.
    """
    if asset.status in [Asset.STATUS_DISPOSED, Asset.STATUS_RETIRED, Asset.STATUS_LOST, Asset.STATUS_DAMAGED]:
        raise ValidationError(f"Cannot assign asset: Current status is '{asset.get_status_display()}'.")

    # Close any currently active assignments
    active_assignments = asset.assignment_history.filter(is_active=True)
    for act in active_assignments:
        act.is_active = False
        act.returned_date = assigned_date or timezone.now().date()
        act.save(update_fields=['is_active', 'returned_date', 'updated_at'])

    assignment = AssetAssignment.objects.create(
        school=asset.school,
        asset=asset,
        assigned_to_employee=assigned_to_employee,
        assigned_to_department=assigned_to_department,
        location=location or asset.current_location,
        assigned_date=assigned_date or timezone.now().date(),
        assigned_by=assigned_by,
        notes=notes,
        is_active=True
    )

    asset.status = Asset.STATUS_ASSIGNED
    asset.assigned_employee = assigned_to_employee
    asset.department = assigned_to_department
    if location:
        asset.current_location = location
    asset.save(update_fields=['status', 'assigned_employee', 'department', 'current_location', 'updated_at'])

    return assignment


@transaction.atomic
def return_asset(
    asset: Asset,
    returned_by=None,
    return_date: Optional[datetime.date] = None,
    return_location: str = 'Main Store',
    condition: str = 'Good',
    notes: str = ''
) -> Asset:
    """
    Returns an assigned asset back to available storage inventory.
    """
    active_assignments = asset.assignment_history.filter(is_active=True)
    for act in active_assignments:
        act.is_active = False
        act.returned_date = return_date or timezone.now().date()
        if notes:
            act.notes = f"{act.notes} [Returned: {notes}]".strip()
        act.save(update_fields=['is_active', 'returned_date', 'notes', 'updated_at'])

    asset.status = Asset.STATUS_AVAILABLE
    asset.assigned_employee = None
    asset.department = None
    if return_location:
        asset.current_location = return_location
    if condition:
        asset.condition = condition
    asset.save(update_fields=['status', 'assigned_employee', 'department', 'current_location', 'condition', 'updated_at'])

    return asset


@transaction.atomic
def log_asset_maintenance_start(
    asset: Asset,
    issue_description: str,
    maintenance_type: str = AssetMaintenance.TYPE_CORRECTIVE,
    service_provider: str = '',
    estimated_cost: Decimal = Decimal('0.00'),
    start_date: Optional[datetime.date] = None,
    user=None,
    notes: str = ''
) -> AssetMaintenance:
    """
    Logs an asset maintenance incident and updates status to IN_REPAIR.
    """
    if asset.status in [Asset.STATUS_DISPOSED, Asset.STATUS_RETIRED]:
        raise ValidationError("Cannot service an already disposed or retired asset.")

    record = AssetMaintenance.objects.create(
        school=asset.school,
        asset=asset,
        maintenance_type=maintenance_type,
        issue_description=issue_description,
        service_provider=service_provider,
        start_date=start_date or timezone.now().date(),
        cost=estimated_cost or Decimal('0.00'),
        status=AssetMaintenance.STATUS_IN_PROGRESS,
        notes=notes,
        created_by=user
    )

    asset.status = Asset.STATUS_IN_REPAIR
    asset.save(update_fields=['status', 'updated_at'])

    return record


@transaction.atomic
def complete_asset_maintenance(
    maintenance: AssetMaintenance,
    completion_date: Optional[datetime.date] = None,
    actual_cost: Optional[Decimal] = None,
    resulting_condition: str = 'Good',
    notes: str = ''
) -> AssetMaintenance:
    """
    Completes maintenance and restores asset operational status.
    """
    maintenance.status = AssetMaintenance.STATUS_COMPLETED
    maintenance.completion_date = completion_date or timezone.now().date()
    if actual_cost is not None:
        maintenance.cost = Decimal(str(actual_cost))
    if notes:
        maintenance.notes = f"{maintenance.notes} [Completed: {notes}]".strip()
    maintenance.save(update_fields=['status', 'completion_date', 'cost', 'notes', 'updated_at'])

    asset = maintenance.asset
    # If it was previously assigned to someone, return to assigned, else available
    if asset.assigned_employee or asset.department:
        asset.status = Asset.STATUS_ASSIGNED
    else:
        asset.status = Asset.STATUS_AVAILABLE

    if resulting_condition:
        asset.condition = resulting_condition
    asset.save(update_fields=['status', 'condition', 'updated_at'])

    return maintenance


@transaction.atomic
def dispose_or_retire_asset(
    asset: Asset,
    new_status: str,
    reason: str,
    user=None,
    date: Optional[datetime.date] = None
) -> Asset:
    """
    Safely retires, disposes, or marks an asset as lost/damaged without data loss.
    """
    valid_terminal_statuses = [
        Asset.STATUS_DISPOSED,
        Asset.STATUS_RETIRED,
        Asset.STATUS_LOST,
        Asset.STATUS_DAMAGED
    ]
    if new_status not in valid_terminal_statuses:
        raise ValidationError(f"Invalid status '{new_status}'. Allowed: {valid_terminal_statuses}")

    # Close active assignments
    active_assignments = asset.assignment_history.filter(is_active=True)
    for act in active_assignments:
        act.is_active = False
        act.returned_date = date or timezone.now().date()
        act.notes = f"{act.notes} [Decommissioned: {reason}]".strip()
        act.save(update_fields=['is_active', 'returned_date', 'notes', 'updated_at'])

    asset.status = new_status
    asset.assigned_employee = None
    asset.department = None
    asset.notes = f"{asset.notes}\n[{timezone.now().date()}] Status changed to {new_status}: {reason}".strip()
    asset.save(update_fields=['status', 'assigned_employee', 'department', 'notes', 'updated_at'])

    return asset
