"""
PrimeSoul School ERP - Phase 16: Inventory & Asset Management Models
Complete tenant-isolated stock ledger, stores, goods receipts, stock issues,
transfers, adjustments, asset registers, assignments, and maintenance.
"""
import re
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from model_utils.models import TimeStampedModel
from django_prometheus.models import ExportModelOperationsMixin

from django_school_management.tenants.models import TenantModel


def validate_gstin(value):
    """
    Validates Indian GSTIN format (15 characters alphanumeric).
    Pattern: 2 digits state code + 10 char PAN + 1 entity code + 'Z' + 1 checksum char.
    """
    if not value:
        return
    gstin_regex = r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$'
    if not re.match(gstin_regex, value.strip().upper()):
        raise ValidationError("Invalid Indian GSTIN format (e.g. 07AAAAA0000A1Z5).")


# ==============================================================================
# 1. INVENTORY MASTER DATA
# ==============================================================================

class InventoryCategory(ExportModelOperationsMixin('inventory_category'), TenantModel, TimeStampedModel):
    """
    Tenant-scoped category for stock/consumable inventory items.
    Examples: Stationery, Cleaning Supplies, Lab Consumables, Sports Equipment.
    """
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='subcategories'
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['school', 'name'], name='unique_school_inventory_category')
        ]
        verbose_name = 'Inventory Category'
        verbose_name_plural = 'Inventory Categories'

    def __str__(self):
        if self.parent:
            return f"{self.parent.name} > {self.name}"
        return self.name


class UnitOfMeasure(ExportModelOperationsMixin('unit_of_measure'), TenantModel, TimeStampedModel):
    """
    Units of measurement (Piece, Box, Packet, Kg, Litre, Set, Dozen, etc.).
    """
    name = models.CharField(max_length=50)
    short_code = models.CharField(max_length=15)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['school', 'short_code'], name='unique_school_uom_code')
        ]
        verbose_name = 'Unit of Measure'
        verbose_name_plural = 'Units of Measure'

    def __str__(self):
        return f"{self.name} ({self.short_code})"


class Supplier(ExportModelOperationsMixin('inventory_supplier'), TenantModel, TimeStampedModel):
    """
    Suppliers / Vendors for institutional purchases and asset procurement.
    """
    name = models.CharField(max_length=200)
    contact_person = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    gstin = models.CharField(
        max_length=15,
        blank=True,
        validators=[validate_gstin],
        help_text="15-digit Indian GSTIN number (e.g. 07AAAAA0000A1Z5)"
    )
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['school', 'name'], name='unique_school_supplier_name')
        ]
        verbose_name = 'Supplier / Vendor'
        verbose_name_plural = 'Suppliers & Vendors'

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if self.gstin:
            self.gstin = self.gstin.strip().upper()


class Store(ExportModelOperationsMixin('inventory_store'), TenantModel, TimeStampedModel):
    """
    Physical store or warehouse within the school.
    Examples: Main Store, Science Lab Store, Sports Store, IT Store.
    """
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=50)
    location = models.CharField(max_length=200, blank=True)
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='managed_stores'
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['school', 'code'], name='unique_school_store_code')
        ]
        verbose_name = 'Store / Warehouse'
        verbose_name_plural = 'Stores & Warehouses'

    def __str__(self):
        return f"{self.name} ({self.code})"


class InventoryItem(ExportModelOperationsMixin('inventory_item'), TenantModel, TimeStampedModel):
    """
    Consumable or stock-managed product master.
    """
    category = models.ForeignKey(
        InventoryCategory,
        on_delete=models.CASCADE,
        related_name='items'
    )
    name = models.CharField(max_length=200)
    sku = models.CharField(max_length=100, db_index=True)
    description = models.TextField(blank=True)
    unit = models.ForeignKey(
        UnitOfMeasure,
        on_delete=models.PROTECT,
        related_name='items'
    )
    reorder_level = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('10.00'),
        help_text="Threshold below which item is flagged as low-stock"
    )
    default_purchase_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Standard purchase price in ₹ (INR)"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['school', 'sku'], name='unique_school_item_sku')
        ]
        verbose_name = 'Inventory Item'
        verbose_name_plural = 'Inventory Items'

    def __str__(self):
        return f"{self.name} [{self.sku}]"

    @property
    def total_stock(self) -> Decimal:
        """Returns aggregated stock across all stores."""
        total = self.store_stocks.aggregate(total=models.Sum('quantity'))['total']
        return total or Decimal('0.00')

    @property
    def is_low_stock(self) -> bool:
        stock = self.total_stock
        return Decimal('0.00') < stock <= self.reorder_level

    @property
    def is_out_of_stock(self) -> bool:
        return self.total_stock <= Decimal('0.00')


class ItemStoreStock(ExportModelOperationsMixin('item_store_stock'), TenantModel, TimeStampedModel):
    """
    Quantity balance of an InventoryItem in a specific Store.
    Updated atomically via StockMovement transactions.
    """
    item = models.ForeignKey(
        InventoryItem,
        on_delete=models.CASCADE,
        related_name='store_stocks'
    )
    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name='item_stocks'
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['school', 'item', 'store'], name='unique_school_item_store_stock')
        ]
        verbose_name = 'Item Store Stock'
        verbose_name_plural = 'Item Store Stocks'

    def __str__(self):
        return f"{self.item.name} @ {self.store.name}: {self.quantity} {self.item.unit.short_code}"


# ==============================================================================
# 2. STOCK MOVEMENTS & TRANSACTIONS
# ==============================================================================

class StockMovement(ExportModelOperationsMixin('stock_movement'), TenantModel, TimeStampedModel):
    """
    Immutable stock ledger recording every quantity change.
    """
    TYPE_IN = 'IN'
    TYPE_OUT = 'OUT'
    TYPE_TRANSFER = 'TRANSFER'
    TYPE_ADJUSTMENT = 'ADJUSTMENT'
    TYPE_RETURN = 'RETURN'

    MOVEMENT_TYPE_CHOICES = (
        (TYPE_IN, 'Stock In (Purchase / Receipt)'),
        (TYPE_OUT, 'Stock Out (Issue / Consumption)'),
        (TYPE_TRANSFER, 'Store Transfer'),
        (TYPE_ADJUSTMENT, 'Inventory Count Adjustment'),
        (TYPE_RETURN, 'Stock Return'),
    )

    item = models.ForeignKey(
        InventoryItem,
        on_delete=models.CASCADE,
        related_name='stock_movements'
    )
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPE_CHOICES, db_index=True)
    source_store = models.ForeignKey(
        Store,
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='outward_movements'
    )
    destination_store = models.ForeignKey(
        Store,
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='inward_movements'
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    reference_number = models.CharField(max_length=100, blank=True, db_index=True)
    reason = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True
    )
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ['-timestamp', '-created']
        verbose_name = 'Stock Movement'
        verbose_name_plural = 'Stock Movements'

    def __str__(self):
        return f"[{self.movement_type}] {self.item.name} ({self.quantity}) - {self.reference_number}"


class PurchaseReceipt(ExportModelOperationsMixin('purchase_receipt'), TenantModel, TimeStampedModel):
    """
    Purchase Goods Receipt Note (GRN) confirming delivery from a vendor into a store.
    """
    STATUS_DRAFT = 'DRAFT'
    STATUS_RECEIVED = 'RECEIVED'
    STATUS_CANCELLED = 'CANCELLED'

    STATUS_CHOICES = (
        (STATUS_DRAFT, 'Draft'),
        (STATUS_RECEIVED, 'Received & Added to Stock'),
        (STATUS_CANCELLED, 'Cancelled'),
    )

    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        related_name='purchase_receipts'
    )
    store = models.ForeignKey(
        Store,
        on_delete=models.PROTECT,
        related_name='purchase_receipts'
    )
    receipt_number = models.CharField(max_length=100, db_index=True)
    purchase_date = models.DateField(default=timezone.now)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    notes = models.TextField(blank=True)
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True
    )

    class Meta:
        ordering = ['-purchase_date', '-created']
        constraints = [
            models.UniqueConstraint(fields=['school', 'receipt_number'], name='unique_school_purchase_receipt_no')
        ]
        verbose_name = 'Purchase Receipt'
        verbose_name_plural = 'Purchase Receipts'

    def __str__(self):
        return f"GRN {self.receipt_number} - {self.supplier.name} (₹{self.total_amount})"


class PurchaseReceiptItem(ExportModelOperationsMixin('purchase_receipt_item'), models.Model):
    """
    Line item inside a Purchase Receipt.
    """
    purchase_receipt = models.ForeignKey(
        PurchaseReceipt,
        on_delete=models.CASCADE,
        related_name='items'
    )
    item = models.ForeignKey(
        InventoryItem,
        on_delete=models.PROTECT,
        related_name='purchase_receipt_items'
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2)
    total_cost = models.DecimalField(max_digits=12, decimal_places=2)

    def save(self, *args, **kwargs):
        self.total_cost = (self.quantity or Decimal('0')) * (self.unit_cost or Decimal('0'))
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.item.name} x {self.quantity} @ ₹{self.unit_cost}"


class StockIssue(ExportModelOperationsMixin('stock_issue'), TenantModel, TimeStampedModel):
    """
    Stock issue record (consumable stationery, chemicals, office supplies)
    issued to an Employee, Department, Student, or School Event.
    """
    RECIPIENT_EMPLOYEE = 'EMPLOYEE'
    RECIPIENT_DEPARTMENT = 'DEPARTMENT'
    RECIPIENT_STUDENT = 'STUDENT'
    RECIPIENT_OTHER = 'OTHER'

    RECIPIENT_TYPE_CHOICES = (
        (RECIPIENT_EMPLOYEE, 'Employee / Faculty'),
        (RECIPIENT_DEPARTMENT, 'Academic / Admin Department'),
        (RECIPIENT_STUDENT, 'Student'),
        (RECIPIENT_OTHER, 'Other / School Event'),
    )

    STATUS_ISSUED = 'ISSUED'
    STATUS_RETURNED_PARTIAL = 'RETURNED_PARTIAL'
    STATUS_RETURNED_FULL = 'RETURNED_FULL'

    STATUS_CHOICES = (
        (STATUS_ISSUED, 'Issued'),
        (STATUS_RETURNED_PARTIAL, 'Partially Returned'),
        (STATUS_RETURNED_FULL, 'Fully Returned'),
    )

    item = models.ForeignKey(
        InventoryItem,
        on_delete=models.PROTECT,
        related_name='stock_issues'
    )
    store = models.ForeignKey(
        Store,
        on_delete=models.PROTECT,
        related_name='stock_issues'
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    returned_quantity = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    recipient_type = models.CharField(max_length=20, choices=RECIPIENT_TYPE_CHOICES, default=RECIPIENT_EMPLOYEE)
    recipient_employee = models.ForeignKey(
        'hr.Employee',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='inventory_issues'
    )
    recipient_department = models.ForeignKey(
        'hr.Department',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='inventory_issues'
    )
    recipient_name = models.CharField(max_length=150, blank=True)
    purpose = models.CharField(max_length=255)
    issue_date = models.DateField(default=timezone.now)
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ISSUED)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-issue_date', '-created']
        verbose_name = 'Stock Issue'
        verbose_name_plural = 'Stock Issues'

    def __str__(self):
        return f"Issue {self.item.name} ({self.quantity}) -> {self.get_recipient_display()}"

    def get_recipient_display(self) -> str:
        if self.recipient_type == self.RECIPIENT_EMPLOYEE and self.recipient_employee:
            return self.recipient_employee.full_name
        elif self.recipient_type == self.RECIPIENT_DEPARTMENT and self.recipient_department:
            return self.recipient_department.name
        return self.recipient_name or "General"


class StockReturn(ExportModelOperationsMixin('stock_return'), TenantModel, TimeStampedModel):
    """
    Record of issued stock returned to store.
    """
    stock_issue = models.ForeignKey(
        StockIssue,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='returns'
    )
    item = models.ForeignKey(
        InventoryItem,
        on_delete=models.PROTECT,
        related_name='stock_returns'
    )
    store = models.ForeignKey(
        Store,
        on_delete=models.PROTECT,
        related_name='stock_returns'
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    return_date = models.DateField(default=timezone.now)
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True
    )
    reason = models.CharField(max_length=255, blank=True)
    condition = models.CharField(max_length=50, default='Good')
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-return_date', '-created']
        verbose_name = 'Stock Return'
        verbose_name_plural = 'Stock Returns'

    def __str__(self):
        return f"Return {self.item.name} ({self.quantity}) to {self.store.name}"


class StockTransfer(ExportModelOperationsMixin('stock_transfer'), TenantModel, TimeStampedModel):
    """
    Inter-store stock transfer within the same school tenant.
    """
    item = models.ForeignKey(
        InventoryItem,
        on_delete=models.PROTECT,
        related_name='transfers'
    )
    source_store = models.ForeignKey(
        Store,
        on_delete=models.PROTECT,
        related_name='transfers_out'
    )
    destination_store = models.ForeignKey(
        Store,
        on_delete=models.PROTECT,
        related_name='transfers_in'
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    transfer_date = models.DateField(default=timezone.now)
    reference_number = models.CharField(max_length=100, blank=True)
    transferred_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-transfer_date', '-created']
        verbose_name = 'Stock Transfer'
        verbose_name_plural = 'Stock Transfers'

    def __str__(self):
        return f"Transfer {self.item.name} ({self.quantity}): {self.source_store.name} -> {self.destination_store.name}"


class StockAdjustment(ExportModelOperationsMixin('stock_adjustment'), TenantModel, TimeStampedModel):
    """
    Controlled stock count correction.
    """
    item = models.ForeignKey(
        InventoryItem,
        on_delete=models.PROTECT,
        related_name='adjustments'
    )
    store = models.ForeignKey(
        Store,
        on_delete=models.PROTECT,
        related_name='adjustments'
    )
    previous_quantity = models.DecimalField(max_digits=12, decimal_places=2)
    new_quantity = models.DecimalField(max_digits=12, decimal_places=2)
    delta_quantity = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.CharField(max_length=255)
    adjustment_date = models.DateField(default=timezone.now)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True
    )

    class Meta:
        ordering = ['-adjustment_date', '-created']
        verbose_name = 'Stock Adjustment'
        verbose_name_plural = 'Stock Adjustments'

    def __str__(self):
        return f"Adjustment {self.item.name} @ {self.store.name}: {self.previous_quantity} -> {self.new_quantity} (Delta: {self.delta_quantity})"


# ==============================================================================
# 3. ASSET MANAGEMENT (Fixed & Capital Assets)
# ==============================================================================

class AssetCategory(ExportModelOperationsMixin('asset_category'), TenantModel, TimeStampedModel):
    """
    Categorization for fixed / capital assets.
    Examples: IT Equipment, Furniture, Lab Equipment, Electrical, Audio-Visual, Vehicles.
    """
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['school', 'name'], name='unique_school_asset_category')
        ]
        verbose_name = 'Asset Category'
        verbose_name_plural = 'Asset Categories'

    def __str__(self):
        return self.name


class Asset(ExportModelOperationsMixin('asset'), TenantModel, TimeStampedModel):
    """
    Fixed / Capital Asset registry.
    """
    STATUS_AVAILABLE = 'AVAILABLE'
    STATUS_ASSIGNED = 'ASSIGNED'
    STATUS_IN_REPAIR = 'IN_REPAIR'
    STATUS_LOST = 'LOST'
    STATUS_DAMAGED = 'DAMAGED'
    STATUS_DISPOSED = 'DISPOSED'
    STATUS_RETIRED = 'RETIRED'

    STATUS_CHOICES = (
        (STATUS_AVAILABLE, 'Available in Stock / Storage'),
        (STATUS_ASSIGNED, 'Assigned / In Use'),
        (STATUS_IN_REPAIR, 'Under Maintenance / Repair'),
        (STATUS_LOST, 'Lost / Missing'),
        (STATUS_DAMAGED, 'Damaged / Non-Functional'),
        (STATUS_DISPOSED, 'Disposed / Sold / Scrapped'),
        (STATUS_RETIRED, 'Retired / End of Life'),
    )

    CONDITION_NEW = 'NEW'
    CONDITION_GOOD = 'GOOD'
    CONDITION_FAIR = 'FAIR'
    CONDITION_POOR = 'POOR'
    CONDITION_DAMAGED = 'DAMAGED'

    CONDITION_CHOICES = (
        (CONDITION_NEW, 'Brand New'),
        (CONDITION_GOOD, 'Good'),
        (CONDITION_FAIR, 'Fair / Functional'),
        (CONDITION_POOR, 'Poor / Needs Service'),
        (CONDITION_DAMAGED, 'Damaged'),
    )

    category = models.ForeignKey(
        AssetCategory,
        on_delete=models.PROTECT,
        related_name='assets'
    )
    name = models.CharField(max_length=200, help_text="e.g. Dell Latitude 3420, Epson EB-X06 Projector")
    asset_tag = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Institutional Unique Asset Identifier / Barcode (e.g. AST-DPS-00102)"
    )
    serial_number = models.CharField(max_length=150, blank=True, db_index=True)
    manufacturer = models.CharField(max_length=150, blank=True)
    model_number = models.CharField(max_length=150, blank=True)
    purchase_date = models.DateField(null=True, blank=True)
    purchase_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text="Purchase cost in ₹ (INR)")
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='supplied_assets'
    )
    warranty_start = models.DateField(null=True, blank=True)
    warranty_expiry = models.DateField(null=True, blank=True)
    current_location = models.CharField(max_length=200, blank=True, help_text="e.g. Physics Lab, Room 204, Principal Office")
    department = models.ForeignKey(
        'hr.Department',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='assets'
    )
    assigned_employee = models.ForeignKey(
        'hr.Employee',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='assigned_assets'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_AVAILABLE, db_index=True)
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, default=CONDITION_GOOD)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['name', 'asset_tag']
        constraints = [
            models.UniqueConstraint(fields=['school', 'asset_tag'], name='unique_school_asset_tag')
        ]
        verbose_name = 'Asset'
        verbose_name_plural = 'Assets'

    def __str__(self):
        return f"{self.name} [{self.asset_tag}] ({self.get_status_display()})"

    @property
    def is_under_warranty(self) -> bool:
        if not self.warranty_expiry:
            return False
        return self.warranty_expiry >= timezone.now().date()


class AssetAssignment(ExportModelOperationsMixin('asset_assignment'), TenantModel, TimeStampedModel):
    """
    Historical log of asset assignments to employees or departments.
    """
    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        related_name='assignment_history'
    )
    assigned_to_employee = models.ForeignKey(
        'hr.Employee',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='asset_assignments'
    )
    assigned_to_department = models.ForeignKey(
        'hr.Department',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='asset_assignments'
    )
    location = models.CharField(max_length=200, blank=True)
    assigned_date = models.DateField(default=timezone.now)
    returned_date = models.DateField(null=True, blank=True)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True
    )
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-assigned_date', '-created']
        verbose_name = 'Asset Assignment'
        verbose_name_plural = 'Asset Assignments'

    def __str__(self):
        assignee = self.assigned_to_employee.full_name if self.assigned_to_employee else (self.assigned_to_department.name if self.assigned_to_department else "Location")
        status_str = "Active" if self.is_active else f"Returned ({self.returned_date})"
        return f"{self.asset.asset_tag} -> {assignee} [{status_str}]"


class AssetMaintenance(ExportModelOperationsMixin('asset_maintenance'), TenantModel, TimeStampedModel):
    """
    Service, repair, and maintenance tracking for fixed assets.
    """
    TYPE_PREVENTIVE = 'PREVENTIVE'
    TYPE_CORRECTIVE = 'CORRECTIVE'
    TYPE_CALIBRATION = 'CALIBRATION'
    TYPE_UPGRADE = 'UPGRADE'

    MAINTENANCE_TYPE_CHOICES = (
        (TYPE_PREVENTIVE, 'Preventive Maintenance / Service'),
        (TYPE_CORRECTIVE, 'Corrective Repair / Breakdown'),
        (TYPE_CALIBRATION, 'Calibration / Testing'),
        (TYPE_UPGRADE, 'Hardware Upgrade / Enhancement'),
    )

    STATUS_OPEN = 'OPEN'
    STATUS_IN_PROGRESS = 'IN_PROGRESS'
    STATUS_COMPLETED = 'COMPLETED'
    STATUS_CANCELLED = 'CANCELLED'

    STATUS_CHOICES = (
        (STATUS_OPEN, 'Open / Scheduled'),
        (STATUS_IN_PROGRESS, 'In Progress / At Service Center'),
        (STATUS_COMPLETED, 'Completed & Operational'),
        (STATUS_CANCELLED, 'Cancelled'),
    )

    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        related_name='maintenance_records'
    )
    maintenance_type = models.CharField(max_length=30, choices=MAINTENANCE_TYPE_CHOICES, default=TYPE_CORRECTIVE)
    issue_description = models.TextField()
    service_provider = models.CharField(max_length=200, blank=True, help_text="Vendor or service technician")
    start_date = models.DateField(default=timezone.now)
    completion_date = models.DateField(null=True, blank=True)
    cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text="Service cost in ₹")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True
    )

    class Meta:
        ordering = ['-start_date', '-created']
        verbose_name = 'Asset Maintenance'
        verbose_name_plural = 'Asset Maintenance Records'

    def __str__(self):
        return f"{self.asset.asset_tag} - {self.get_maintenance_type_display()} ({self.get_status_display()})"
