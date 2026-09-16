from django.contrib import admin
from .models import (
    InventoryCategory, UnitOfMeasure, Supplier, Store,
    InventoryItem, ItemStoreStock, StockMovement,
    PurchaseReceipt, PurchaseReceiptItem, StockIssue,
    StockReturn, StockTransfer, StockAdjustment,
    AssetCategory, Asset, AssetAssignment, AssetMaintenance
)

@admin.register(InventoryCategory)
class InventoryCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'school', 'is_active')
    search_fields = ('name', 'school__name')


@admin.register(UnitOfMeasure)
class UnitOfMeasureAdmin(admin.ModelAdmin):
    list_display = ('name', 'short_code', 'school', 'is_active')
    search_fields = ('name', 'short_code')


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'contact_person', 'phone', 'email', 'gstin', 'school', 'is_active')
    search_fields = ('name', 'contact_person', 'phone', 'email', 'gstin')


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'location', 'school', 'is_active')
    search_fields = ('name', 'code', 'location')


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'sku', 'category', 'unit', 'reorder_level', 'default_purchase_price', 'school', 'is_active')
    search_fields = ('name', 'sku')
    list_filter = ('category', 'is_active')


@admin.register(ItemStoreStock)
class ItemStoreStockAdmin(admin.ModelAdmin):
    list_display = ('item', 'store', 'quantity', 'school')
    search_fields = ('item__name', 'store__name')


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'item', 'movement_type', 'source_store', 'destination_store', 'quantity', 'reference_number', 'school')
    list_filter = ('movement_type',)
    search_fields = ('item__name', 'reference_number')


@admin.register(PurchaseReceipt)
class PurchaseReceiptAdmin(admin.ModelAdmin):
    list_display = ('receipt_number', 'supplier', 'store', 'purchase_date', 'total_amount', 'status', 'school')
    list_filter = ('status',)
    search_fields = ('receipt_number', 'supplier__name')


@admin.register(StockIssue)
class StockIssueAdmin(admin.ModelAdmin):
    list_display = ('item', 'store', 'quantity', 'recipient_type', 'issue_date', 'status', 'school')
    list_filter = ('recipient_type', 'status')
    search_fields = ('item__name', 'recipient_name')


@admin.register(StockReturn)
class StockReturnAdmin(admin.ModelAdmin):
    list_display = ('item', 'store', 'quantity', 'return_date', 'school')
    search_fields = ('item__name',)


@admin.register(StockTransfer)
class StockTransferAdmin(admin.ModelAdmin):
    list_display = ('item', 'source_store', 'destination_store', 'quantity', 'transfer_date', 'school')
    search_fields = ('item__name',)


@admin.register(StockAdjustment)
class StockAdjustmentAdmin(admin.ModelAdmin):
    list_display = ('item', 'store', 'previous_quantity', 'new_quantity', 'delta_quantity', 'reason', 'adjustment_date', 'school')
    search_fields = ('item__name', 'reason')


@admin.register(AssetCategory)
class AssetCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'school', 'is_active')
    search_fields = ('name',)


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ('name', 'asset_tag', 'serial_number', 'category', 'status', 'condition', 'assigned_employee', 'department', 'school')
    list_filter = ('category', 'status', 'condition')
    search_fields = ('name', 'asset_tag', 'serial_number')


@admin.register(AssetAssignment)
class AssetAssignmentAdmin(admin.ModelAdmin):
    list_display = ('asset', 'assigned_to_employee', 'assigned_to_department', 'assigned_date', 'returned_date', 'is_active', 'school')
    list_filter = ('is_active',)
    search_fields = ('asset__name', 'asset__asset_tag')


@admin.register(AssetMaintenance)
class AssetMaintenanceAdmin(admin.ModelAdmin):
    list_display = ('asset', 'maintenance_type', 'service_provider', 'start_date', 'cost', 'status', 'school')
    list_filter = ('maintenance_type', 'status')
    search_fields = ('asset__name', 'asset__asset_tag', 'service_provider')
