"""
PrimeSoul School ERP - Phase 16: Inventory & Asset Management Forms
Tenant-scoped model forms with clean widgets and validation.
"""
from decimal import Decimal
from django import forms
from django_school_management.tenants.models import School
from django_school_management.inventory.models import (
    InventoryCategory, UnitOfMeasure, Supplier, Store,
    InventoryItem, ItemStoreStock, StockMovement,
    PurchaseReceipt, PurchaseReceiptItem, StockIssue,
    StockReturn, StockTransfer, StockAdjustment,
    AssetCategory, Asset, AssetAssignment, AssetMaintenance
)
from django_school_management.hr.models import Employee, Department


class InventoryCategoryForm(forms.ModelForm):
    class Meta:
        model = InventoryCategory
        fields = ['name', 'parent', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Stationery, Lab Supplies'}),
            'parent': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        if school:
            self.fields['parent'].queryset = InventoryCategory.objects.filter(school=school, is_active=True)
            if self.instance.pk:
                self.fields['parent'].queryset = self.fields['parent'].queryset.exclude(pk=self.instance.pk)


class UnitOfMeasureForm(forms.ModelForm):
    class Meta:
        model = UnitOfMeasure
        fields = ['name', 'short_code', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Piece, Box, Kilogram'}),
            'short_code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. pcs, box, kg'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ['name', 'contact_person', 'phone', 'email', 'address', 'gstin', 'notes', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Vendor / Company Name'}),
            'contact_person': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Contact Person'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+91 9876543210'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'vendor@example.com'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'gstin': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '07AAAAA0000A1Z5'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class StoreForm(forms.ModelForm):
    class Meta:
        model = Store
        fields = ['name', 'code', 'location', 'manager', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Main Store, Science Lab Store'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. STR-MAIN, STR-LAB'}),
            'location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Ground Floor, Block B'}),
            'manager': forms.Select(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        # manager is user


class InventoryItemForm(forms.ModelForm):
    class Meta:
        model = InventoryItem
        fields = ['category', 'name', 'sku', 'unit', 'reorder_level', 'default_purchase_price', 'description', 'is_active']
        widgets = {
            'category': forms.Select(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Item Name (e.g. A4 Paper Rim)'}),
            'sku': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Leave blank to auto-generate'}),
            'unit': forms.Select(attrs={'class': 'form-control'}),
            'reorder_level': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'default_purchase_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['sku'].required = False
        if school:
            self.fields['category'].queryset = InventoryCategory.objects.filter(school=school, is_active=True)
            self.fields['unit'].queryset = UnitOfMeasure.objects.filter(school=school, is_active=True)


class PurchaseReceiptForm(forms.ModelForm):
    class Meta:
        model = PurchaseReceipt
        fields = ['supplier', 'store', 'receipt_number', 'purchase_date', 'notes']
        widgets = {
            'supplier': forms.Select(attrs={'class': 'form-control'}),
            'store': forms.Select(attrs={'class': 'form-control'}),
            'receipt_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Leave blank to auto-generate'}),
            'purchase_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['receipt_number'].required = False
        if school:
            self.fields['supplier'].queryset = Supplier.objects.filter(school=school, is_active=True)
            self.fields['store'].queryset = Store.objects.filter(school=school, is_active=True)


class StockIssueForm(forms.ModelForm):
    class Meta:
        model = StockIssue
        fields = [
            'item', 'store', 'quantity', 'recipient_type',
            'recipient_employee', 'recipient_department', 'recipient_name',
            'purpose', 'issue_date', 'notes'
        ]
        widgets = {
            'item': forms.Select(attrs={'class': 'form-control'}),
            'store': forms.Select(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
            'recipient_type': forms.Select(attrs={'class': 'form-control'}),
            'recipient_employee': forms.Select(attrs={'class': 'form-control'}),
            'recipient_department': forms.Select(attrs={'class': 'form-control'}),
            'recipient_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Name / Event / Class'}),
            'purpose': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Purpose / Academic Activity'}),
            'issue_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        if school:
            self.fields['item'].queryset = InventoryItem.objects.filter(school=school, is_active=True)
            self.fields['store'].queryset = Store.objects.filter(school=school, is_active=True)
            self.fields['recipient_employee'].queryset = Employee.objects.filter(school=school, status='ACTIVE')
            self.fields['recipient_department'].queryset = Department.objects.filter(school=school)


class StockReturnForm(forms.ModelForm):
    class Meta:
        model = StockReturn
        fields = ['stock_issue', 'item', 'store', 'quantity', 'return_date', 'reason', 'condition', 'notes']
        widgets = {
            'stock_issue': forms.Select(attrs={'class': 'form-control'}),
            'item': forms.Select(attrs={'class': 'form-control'}),
            'store': forms.Select(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
            'return_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'reason': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Reason for return'}),
            'condition': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Condition (e.g. Good, Unused)'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        if school:
            self.fields['stock_issue'].queryset = StockIssue.objects.filter(school=school).exclude(status=StockIssue.STATUS_RETURNED_FULL)
            self.fields['item'].queryset = InventoryItem.objects.filter(school=school, is_active=True)
            self.fields['store'].queryset = Store.objects.filter(school=school, is_active=True)


class StockTransferForm(forms.ModelForm):
    class Meta:
        model = StockTransfer
        fields = ['item', 'source_store', 'destination_store', 'quantity', 'transfer_date', 'reference_number', 'notes']
        widgets = {
            'item': forms.Select(attrs={'class': 'form-control'}),
            'source_store': forms.Select(attrs={'class': 'form-control'}),
            'destination_store': forms.Select(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
            'transfer_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'reference_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional reference code'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        if school:
            self.fields['item'].queryset = InventoryItem.objects.filter(school=school, is_active=True)
            self.fields['source_store'].queryset = Store.objects.filter(school=school, is_active=True)
            self.fields['destination_store'].queryset = Store.objects.filter(school=school, is_active=True)


class StockAdjustmentForm(forms.Form):
    item = forms.ModelChoiceField(queryset=InventoryItem.objects.none(), widget=forms.Select(attrs={'class': 'form-control'}))
    store = forms.ModelChoiceField(queryset=Store.objects.none(), widget=forms.Select(attrs={'class': 'form-control'}))
    new_quantity = forms.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.00'), widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}))
    reason = forms.CharField(max_length=255, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Reason for count adjustment'}))
    adjustment_date = forms.DateField(widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}))

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        if school:
            self.fields['item'].queryset = InventoryItem.objects.filter(school=school, is_active=True)
            self.fields['store'].queryset = Store.objects.filter(school=school, is_active=True)


# ==============================================================================
# ASSET FORMS
# ==============================================================================

class AssetCategoryForm(forms.ModelForm):
    class Meta:
        model = AssetCategory
        fields = ['name', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. IT Equipment, Lab Equipment'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class AssetForm(forms.ModelForm):
    class Meta:
        model = Asset
        fields = [
            'category', 'name', 'asset_tag', 'serial_number', 'manufacturer', 'model_number',
            'purchase_date', 'purchase_cost', 'supplier', 'warranty_start', 'warranty_expiry',
            'current_location', 'department', 'assigned_employee', 'status', 'condition', 'notes'
        ]
        widgets = {
            'category': forms.Select(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Dell Optiplex 7090'}),
            'asset_tag': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Leave blank to auto-generate'}),
            'serial_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Serial Number'}),
            'manufacturer': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Dell, HP, Epson'}),
            'model_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 7090-MT'}),
            'purchase_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'purchase_cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'supplier': forms.Select(attrs={'class': 'form-control'}),
            'warranty_start': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'warranty_expiry': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'current_location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Computer Lab 1'}),
            'department': forms.Select(attrs={'class': 'form-control'}),
            'assigned_employee': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'condition': forms.Select(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['asset_tag'].required = False
        if school:
            self.fields['category'].queryset = AssetCategory.objects.filter(school=school, is_active=True)
            self.fields['supplier'].queryset = Supplier.objects.filter(school=school, is_active=True)
            self.fields['department'].queryset = Department.objects.filter(school=school)
            self.fields['assigned_employee'].queryset = Employee.objects.filter(school=school, status='ACTIVE')


class AssetAssignmentForm(forms.ModelForm):
    class Meta:
        model = AssetAssignment
        fields = ['asset', 'assigned_to_employee', 'assigned_to_department', 'location', 'assigned_date', 'notes']
        widgets = {
            'asset': forms.Select(attrs={'class': 'form-control'}),
            'assigned_to_employee': forms.Select(attrs={'class': 'form-control'}),
            'assigned_to_department': forms.Select(attrs={'class': 'form-control'}),
            'location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Location / Room Number'}),
            'assigned_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        if school:
            self.fields['asset'].queryset = Asset.objects.filter(
                school=school,
                status__in=[Asset.STATUS_AVAILABLE, Asset.STATUS_ASSIGNED]
            )
            self.fields['assigned_to_employee'].queryset = Employee.objects.filter(school=school, status='ACTIVE')
            self.fields['assigned_to_department'].queryset = Department.objects.filter(school=school)


class AssetReturnForm(forms.Form):
    returned_date = forms.DateField(widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}))
    condition = forms.ChoiceField(choices=Asset.CONDITION_CHOICES, widget=forms.Select(attrs={'class': 'form-control'}))
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}))


class AssetMaintenanceForm(forms.ModelForm):
    class Meta:
        model = AssetMaintenance
        fields = ['asset', 'maintenance_type', 'issue_description', 'service_provider', 'start_date', 'cost', 'notes']
        widgets = {
            'asset': forms.Select(attrs={'class': 'form-control'}),
            'maintenance_type': forms.Select(attrs={'class': 'form-control'}),
            'issue_description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Describe issue or service required'}),
            'service_provider': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Vendor / Service Center'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        if school:
            self.fields['asset'].queryset = Asset.objects.filter(
                school=school
            ).exclude(status__in=[Asset.STATUS_DISPOSED, Asset.STATUS_RETIRED])


class AssetMaintenanceCompleteForm(forms.Form):
    completion_date = forms.DateField(widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}))
    cost = forms.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.00'), widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}))
    restored_status = forms.ChoiceField(
        choices=[(Asset.STATUS_AVAILABLE, 'Available in Stock'), (Asset.STATUS_ASSIGNED, 'Assigned / In Use')],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}))


class AssetLifecycleForm(forms.Form):
    ACTION_DAMAGED = Asset.STATUS_DAMAGED
    ACTION_LOST = Asset.STATUS_LOST
    ACTION_DISPOSED = Asset.STATUS_DISPOSED
    ACTION_RETIRED = Asset.STATUS_RETIRED

    LIFECYCLE_CHOICES = (
        (ACTION_DAMAGED, 'Mark Damaged / Non-Functional'),
        (ACTION_LOST, 'Mark Lost / Missing'),
        (ACTION_DISPOSED, 'Dispose / Scrapped / Sold'),
        (ACTION_RETIRED, 'Retire / End of Life'),
    )

    action = forms.ChoiceField(choices=LIFECYCLE_CHOICES, widget=forms.Select(attrs={'class': 'form-control'}))
    reason = forms.CharField(max_length=255, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Reason for status update'}))
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}))
