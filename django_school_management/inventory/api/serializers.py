"""
PrimeSoul School ERP - Phase 16: Inventory & Asset Management REST Serializers
"""
from decimal import Decimal
from rest_framework import serializers
from django_school_management.inventory.models import (
    InventoryCategory, UnitOfMeasure, Supplier, Store,
    InventoryItem, ItemStoreStock, StockMovement,
    PurchaseReceipt, PurchaseReceiptItem, StockIssue,
    StockReturn, StockTransfer, StockAdjustment,
    AssetCategory, Asset, AssetAssignment, AssetMaintenance
)


class InventoryCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryCategory
        fields = ['id', 'name', 'parent', 'description', 'is_active', 'created', 'modified']


class UnitOfMeasureSerializer(serializers.ModelSerializer):
    class Meta:
        model = UnitOfMeasure
        fields = ['id', 'name', 'short_code', 'is_active']


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = ['id', 'name', 'contact_person', 'phone', 'email', 'address', 'gstin', 'notes', 'is_active', 'created']


class StoreSerializer(serializers.ModelSerializer):
    manager_name = serializers.CharField(source='manager.get_full_name', read_only=True)

    class Meta:
        model = Store
        fields = ['id', 'name', 'code', 'location', 'manager', 'manager_name', 'is_active', 'created']


class ItemStoreStockSerializer(serializers.ModelSerializer):
    store_name = serializers.CharField(source='store.name', read_only=True)

    class Meta:
        model = ItemStoreStock
        fields = ['id', 'store', 'store_name', 'quantity']


class InventoryItemSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    unit_code = serializers.CharField(source='unit.short_code', read_only=True)
    total_stock = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    is_low_stock = serializers.BooleanField(read_only=True)
    is_out_of_stock = serializers.BooleanField(read_only=True)
    store_stocks = ItemStoreStockSerializer(many=True, read_only=True)

    class Meta:
        model = InventoryItem
        fields = [
            'id', 'category', 'category_name', 'name', 'sku', 'unit', 'unit_code',
            'reorder_level', 'default_purchase_price', 'description', 'is_active',
            'total_stock', 'is_low_stock', 'is_out_of_stock', 'store_stocks', 'created'
        ]
        read_only_fields = ['sku']


class StockMovementSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source='item.name', read_only=True)
    item_sku = serializers.CharField(source='item.sku', read_only=True)
    unit_code = serializers.CharField(source='item.unit.short_code', read_only=True)
    source_store_name = serializers.CharField(source='source_store.name', read_only=True)
    destination_store_name = serializers.CharField(source='destination_store.name', read_only=True)
    performed_by_name = serializers.CharField(source='performed_by.get_full_name', read_only=True)

    class Meta:
        model = StockMovement
        fields = [
            'id', 'item', 'item_name', 'item_sku', 'unit_code', 'movement_type',
            'source_store', 'source_store_name', 'destination_store', 'destination_store_name',
            'quantity', 'unit_cost', 'total_cost', 'reference_number', 'reason',
            'notes', 'performed_by', 'performed_by_name', 'timestamp'
        ]


class PurchaseReceiptItemSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source='item.name', read_only=True)

    class Meta:
        model = PurchaseReceiptItem
        fields = ['id', 'item', 'item_name', 'quantity', 'unit_cost', 'total_cost']


class PurchaseReceiptSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    store_name = serializers.CharField(source='store.name', read_only=True)
    items = PurchaseReceiptItemSerializer(many=True, read_only=True)

    class Meta:
        model = PurchaseReceipt
        fields = [
            'id', 'supplier', 'supplier_name', 'store', 'store_name',
            'receipt_number', 'purchase_date', 'total_amount', 'status', 'notes',
            'received_by', 'items', 'created'
        ]


class StockIssueSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source='item.name', read_only=True)
    store_name = serializers.CharField(source='store.name', read_only=True)
    recipient_display = serializers.CharField(source='get_recipient_display', read_only=True)

    class Meta:
        model = StockIssue
        fields = [
            'id', 'item', 'item_name', 'store', 'store_name', 'quantity', 'returned_quantity',
            'recipient_type', 'recipient_employee', 'recipient_department', 'recipient_name',
            'recipient_display', 'purpose', 'issue_date', 'issued_by', 'status', 'notes', 'created'
        ]


class StockReturnSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source='item.name', read_only=True)
    store_name = serializers.CharField(source='store.name', read_only=True)

    class Meta:
        model = StockReturn
        fields = [
            'id', 'stock_issue', 'item', 'item_name', 'store', 'store_name',
            'quantity', 'return_date', 'received_by', 'reason', 'condition', 'notes', 'created'
        ]


class StockTransferSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source='item.name', read_only=True)
    source_store_name = serializers.CharField(source='source_store.name', read_only=True)
    destination_store_name = serializers.CharField(source='destination_store.name', read_only=True)

    class Meta:
        model = StockTransfer
        fields = [
            'id', 'item', 'item_name', 'source_store', 'source_store_name',
            'destination_store', 'destination_store_name', 'quantity',
            'transfer_date', 'reference_number', 'notes', 'created'
        ]


class StockAdjustmentSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source='item.name', read_only=True)
    store_name = serializers.CharField(source='store.name', read_only=True)

    class Meta:
        model = StockAdjustment
        fields = [
            'id', 'item', 'item_name', 'store', 'store_name',
            'previous_quantity', 'new_quantity', 'delta_quantity',
            'reason', 'adjustment_date', 'performed_by', 'created'
        ]


# ==============================================================================
# ASSET SERIALIZERS
# ==============================================================================

class AssetCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetCategory
        fields = ['id', 'name', 'description', 'is_active', 'created']


class AssetAssignmentSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='assigned_to_employee.full_name', read_only=True)
    department_name = serializers.CharField(source='assigned_to_department.name', read_only=True)
    assigned_by_name = serializers.CharField(source='assigned_by.get_full_name', read_only=True)

    class Meta:
        model = AssetAssignment
        fields = [
            'id', 'asset', 'assigned_to_employee', 'employee_name',
            'assigned_to_department', 'department_name', 'location',
            'assigned_date', 'returned_date', 'assigned_by', 'assigned_by_name',
            'notes', 'is_active', 'created'
        ]


class AssetMaintenanceSerializer(serializers.ModelSerializer):
    asset_tag = serializers.CharField(source='asset.asset_tag', read_only=True)
    asset_name = serializers.CharField(source='asset.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)

    class Meta:
        model = AssetMaintenance
        fields = [
            'id', 'asset', 'asset_tag', 'asset_name', 'maintenance_type',
            'issue_description', 'service_provider', 'start_date', 'completion_date',
            'cost', 'status', 'notes', 'created_by', 'created_by_name', 'created'
        ]


class AssetSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    assigned_employee_name = serializers.CharField(source='assigned_employee.full_name', read_only=True)
    is_under_warranty = serializers.BooleanField(read_only=True)
    assignment_history = AssetAssignmentSerializer(many=True, read_only=True)
    maintenance_records = AssetMaintenanceSerializer(many=True, read_only=True)

    class Meta:
        model = Asset
        fields = [
            'id', 'category', 'category_name', 'name', 'asset_tag', 'serial_number',
            'manufacturer', 'model_number', 'purchase_date', 'purchase_cost',
            'supplier', 'supplier_name', 'warranty_start', 'warranty_expiry',
            'current_location', 'department', 'department_name',
            'assigned_employee', 'assigned_employee_name', 'status', 'condition',
            'is_under_warranty', 'notes', 'assignment_history', 'maintenance_records', 'created'
        ]
        read_only_fields = ['asset_tag']
