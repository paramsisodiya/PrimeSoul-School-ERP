"""
PrimeSoul School ERP - Phase 16: Inventory & Asset Management REST API Views
"""
from decimal import Decimal
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError
from django.utils import timezone

from django_school_management.tenants.models import School
from django_school_management.inventory.models import (
    InventoryCategory, UnitOfMeasure, Supplier, Store,
    InventoryItem, ItemStoreStock, StockMovement,
    PurchaseReceipt, StockIssue, StockReturn, StockTransfer, StockAdjustment,
    AssetCategory, Asset, AssetAssignment, AssetMaintenance
)
from django_school_management.inventory.api.serializers import (
    InventoryCategorySerializer, UnitOfMeasureSerializer, SupplierSerializer,
    StoreSerializer, InventoryItemSerializer, StockMovementSerializer,
    PurchaseReceiptSerializer, StockIssueSerializer, StockReturnSerializer,
    StockTransferSerializer, StockAdjustmentSerializer, AssetCategorySerializer,
    AssetSerializer, AssetAssignmentSerializer, AssetMaintenanceSerializer
)
from django_school_management.inventory.services import inventory_service
from django_school_management.inventory.selectors import inventory_selectors


def get_request_school(request):
    """Safely resolves school tenant from request."""
    if hasattr(request, 'tenant') and request.tenant:
        return request.tenant
    if hasattr(request, 'school') and request.school:
        return request.school
    if request.user.is_authenticated and getattr(request.user, 'school', None):
        return request.user.school
    return School.objects.first()


class InventoryDashboardAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        school = get_request_school(request)
        metrics = inventory_selectors.get_inventory_dashboard_metrics(school)
        # Convert non-serializable objects (querysets, decimals)
        return Response({
            'total_items': metrics['total_items'],
            'total_stores': metrics['total_stores'],
            'total_suppliers': metrics['total_suppliers'],
            'total_stock_qty': str(metrics['total_stock_qty']),
            'low_stock_count': metrics['low_stock_count'],
            'out_of_stock_count': metrics['out_of_stock_count'],
            'healthy_stock_count': metrics['healthy_stock_count'],
            'total_assets': metrics['total_assets'],
            'available_assets': metrics['available_assets'],
            'assigned_assets': metrics['assigned_assets'],
            'in_repair_assets': metrics['in_repair_assets'],
            'lost_damaged_count': metrics['lost_damaged_count'],
            'retired_disposed_count': metrics['retired_disposed_count'],
            'total_valuation': str(metrics['total_valuation']),
        })


class InventoryCategoryViewSet(viewsets.ModelViewSet):
    serializer_class = InventoryCategorySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        school = get_request_school(self.request)
        return InventoryCategory.objects.filter(school=school)

    def perform_create(self, serializer):
        serializer.save(school=get_request_school(self.request))


class UnitOfMeasureViewSet(viewsets.ModelViewSet):
    serializer_class = UnitOfMeasureSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        school = get_request_school(self.request)
        return UnitOfMeasure.objects.filter(school=school)

    def perform_create(self, serializer):
        serializer.save(school=get_request_school(self.request))


class SupplierViewSet(viewsets.ModelViewSet):
    serializer_class = SupplierSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        school = get_request_school(self.request)
        return Supplier.objects.filter(school=school)

    def perform_create(self, serializer):
        serializer.save(school=get_request_school(self.request))


class StoreViewSet(viewsets.ModelViewSet):
    serializer_class = StoreSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        school = get_request_school(self.request)
        return Store.objects.filter(school=school)

    def perform_create(self, serializer):
        serializer.save(school=get_request_school(self.request))


class InventoryItemViewSet(viewsets.ModelViewSet):
    serializer_class = InventoryItemSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        school = get_request_school(self.request)
        qs = InventoryItem.objects.filter(school=school).select_related('category', 'unit').prefetch_related('store_stocks__store')
        category = self.request.query_params.get('category')
        if category:
            qs = qs.filter(category_id=category)
        return qs

    def perform_create(self, serializer):
        school = get_request_school(self.request)
        sku = serializer.validated_data.get('sku')
        if not sku:
            sku = inventory_service.generate_sku(school, serializer.validated_data.get('category'))
        serializer.save(school=school, sku=sku)

    @action(detail=False, methods=['get'])
    def low_stock(self, request):
        school = get_request_school(request)
        items = inventory_selectors.get_low_stock_items(school)
        serializer = self.get_serializer(items, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def out_of_stock(self, request):
        school = get_request_school(request)
        items = inventory_selectors.get_out_of_stock_items(school)
        serializer = self.get_serializer(items, many=True)
        return Response(serializer.data)


class StockMovementViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = StockMovementSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        school = get_request_school(self.request)
        item_id = self.request.query_params.get('item')
        store_id = self.request.query_params.get('store')
        movement_type = self.request.query_params.get('movement_type')
        return inventory_selectors.get_stock_movement_ledger(
            school=school,
            item_id=int(item_id) if item_id else None,
            store_id=int(store_id) if store_id else None,
            movement_type=movement_type
        )


class PurchaseReceiptViewSet(viewsets.ModelViewSet):
    serializer_class = PurchaseReceiptSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        school = get_request_school(self.request)
        return PurchaseReceipt.objects.filter(school=school).select_related('supplier', 'store', 'received_by').prefetch_related('items__item')

    def create(self, request, *args, **kwargs):
        school = get_request_school(request)
        supplier_id = request.data.get('supplier')
        store_id = request.data.get('store')
        line_items_data = request.data.get('items', [])
        receipt_number = request.data.get('receipt_number')
        purchase_date = request.data.get('purchase_date')
        notes = request.data.get('notes', '')

        if not supplier_id or not store_id or not line_items_data:
            return Response({'error': 'supplier, store, and items list are required'}, status=status.HTTP_400_BAD_REQUEST)

        supplier = get_object_or_404(Supplier, school=school, pk=supplier_id)
        store = get_object_or_404(Store, school=school, pk=store_id)

        try:
            receipt = inventory_service.receive_purchase_receipt(
                school=school,
                supplier=supplier,
                store=store,
                line_items_data=line_items_data,
                receipt_number=receipt_number,
                purchase_date=purchase_date,
                received_by=request.user,
                notes=notes
            )
            serializer = self.get_serializer(receipt)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            return Response({'error': str(e.message if hasattr(e, 'message') else e)}, status=status.HTTP_400_BAD_REQUEST)


class StockIssueViewSet(viewsets.ModelViewSet):
    serializer_class = StockIssueSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        school = get_request_school(self.request)
        return StockIssue.objects.filter(school=school).select_related('item', 'store', 'recipient_employee', 'recipient_department', 'issued_by')

    def create(self, request, *args, **kwargs):
        school = get_request_school(request)
        item_id = request.data.get('item')
        store_id = request.data.get('store')
        quantity = Decimal(str(request.data.get('quantity', '0')))
        recipient_type = request.data.get('recipient_type', 'EMPLOYEE')
        purpose = request.data.get('purpose', '')
        employee_id = request.data.get('recipient_employee')
        department_id = request.data.get('recipient_department')
        recipient_name = request.data.get('recipient_name', '')
        notes = request.data.get('notes', '')

        item = get_object_or_404(InventoryItem, school=school, pk=item_id)
        store = get_object_or_404(Store, school=school, pk=store_id)

        from django_school_management.hr.models import Employee, Department
        emp = Employee.objects.filter(school=school, pk=employee_id).first() if employee_id else None
        dept = Department.objects.filter(school=school, pk=department_id).first() if department_id else None

        try:
            issue = inventory_service.issue_stock(
                school=school,
                item=item,
                store=store,
                quantity=quantity,
                recipient_type=recipient_type,
                purpose=purpose,
                recipient_employee=emp,
                recipient_department=dept,
                recipient_name=recipient_name,
                issued_by=request.user,
                notes=notes
            )
            return Response(self.get_serializer(issue).data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            return Response({'error': str(e.message if hasattr(e, 'message') else e)}, status=status.HTTP_400_BAD_REQUEST)


class StockReturnViewSet(viewsets.ModelViewSet):
    serializer_class = StockReturnSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        school = get_request_school(self.request)
        return StockReturn.objects.filter(school=school).select_related('item', 'store', 'received_by', 'stock_issue')

    def create(self, request, *args, **kwargs):
        school = get_request_school(request)
        item_id = request.data.get('item')
        store_id = request.data.get('store')
        quantity = Decimal(str(request.data.get('quantity', '0')))
        issue_id = request.data.get('stock_issue')
        reason = request.data.get('reason', '')
        condition = request.data.get('condition', 'Good')
        notes = request.data.get('notes', '')

        item = get_object_or_404(InventoryItem, school=school, pk=item_id)
        store = get_object_or_404(Store, school=school, pk=store_id)
        issue = StockIssue.objects.filter(school=school, pk=issue_id).first() if issue_id else None

        try:
            ret = inventory_service.return_stock(
                school=school,
                item=item,
                store=store,
                quantity=quantity,
                stock_issue=issue,
                reason=reason,
                condition=condition,
                received_by=request.user,
                notes=notes
            )
            return Response(self.get_serializer(ret).data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            return Response({'error': str(e.message if hasattr(e, 'message') else e)}, status=status.HTTP_400_BAD_REQUEST)


class StockTransferViewSet(viewsets.ModelViewSet):
    serializer_class = StockTransferSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        school = get_request_school(self.request)
        return StockTransfer.objects.filter(school=school).select_related('item', 'source_store', 'destination_store', 'transferred_by')

    def create(self, request, *args, **kwargs):
        school = get_request_school(request)
        item_id = request.data.get('item')
        source_id = request.data.get('source_store')
        dest_id = request.data.get('destination_store')
        quantity = Decimal(str(request.data.get('quantity', '0')))
        ref = request.data.get('reference_number', '')
        notes = request.data.get('notes', '')

        item = get_object_or_404(InventoryItem, school=school, pk=item_id)
        source = get_object_or_404(Store, school=school, pk=source_id)
        dest = get_object_or_404(Store, school=school, pk=dest_id)

        try:
            trans = inventory_service.transfer_stock(
                school=school,
                item=item,
                source_store=source,
                destination_store=dest,
                quantity=quantity,
                reference_number=ref,
                transferred_by=request.user,
                notes=notes
            )
            return Response(self.get_serializer(trans).data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            return Response({'error': str(e.message if hasattr(e, 'message') else e)}, status=status.HTTP_400_BAD_REQUEST)


class StockAdjustmentViewSet(viewsets.ModelViewSet):
    serializer_class = StockAdjustmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        school = get_request_school(self.request)
        return StockAdjustment.objects.filter(school=school).select_related('item', 'store', 'performed_by')

    def create(self, request, *args, **kwargs):
        school = get_request_school(request)
        item_id = request.data.get('item')
        store_id = request.data.get('store')
        new_quantity = Decimal(str(request.data.get('new_quantity', '0')))
        reason = request.data.get('reason', '')

        item = get_object_or_404(InventoryItem, school=school, pk=item_id)
        store = get_object_or_404(Store, school=school, pk=store_id)

        try:
            adj = inventory_service.adjust_stock(
                school=school,
                item=item,
                store=store,
                new_quantity=new_quantity,
                reason=reason,
                performed_by=request.user
            )
            return Response(self.get_serializer(adj).data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            return Response({'error': str(e.message if hasattr(e, 'message') else e)}, status=status.HTTP_400_BAD_REQUEST)


# ==============================================================================
# ASSET API VIEWSETS
# ==============================================================================

class AssetCategoryViewSet(viewsets.ModelViewSet):
    serializer_class = AssetCategorySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        school = get_request_school(self.request)
        return AssetCategory.objects.filter(school=school)

    def perform_create(self, serializer):
        serializer.save(school=get_request_school(self.request))


class AssetViewSet(viewsets.ModelViewSet):
    serializer_class = AssetSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        school = get_request_school(self.request)
        category = self.request.query_params.get('category')
        status_param = self.request.query_params.get('status')
        return inventory_selectors.get_asset_register(
            school=school,
            category_id=int(category) if category else None,
            status=status_param
        )

    def perform_create(self, serializer):
        school = get_request_school(self.request)
        tag = serializer.validated_data.get('asset_tag')
        if not tag:
            tag = inventory_service.generate_asset_tag(school, serializer.validated_data.get('category'))
        serializer.save(school=school, asset_tag=tag)

    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        school = get_request_school(request)
        asset = self.get_object()
        emp_id = request.data.get('employee_id')
        dept_id = request.data.get('department_id')
        location = request.data.get('location', '')
        notes = request.data.get('notes', '')

        from django_school_management.hr.models import Employee, Department
        emp = Employee.objects.filter(school=school, pk=emp_id).first() if emp_id else None
        dept = Department.objects.filter(school=school, pk=dept_id).first() if dept_id else None

        try:
            assignment = inventory_service.assign_asset(
                school=school,
                asset=asset,
                assigned_to_employee=emp,
                assigned_to_department=dept,
                location=location,
                assigned_by=request.user,
                notes=notes
            )
            return Response(AssetAssignmentSerializer(assignment).data)
        except ValidationError as e:
            return Response({'error': str(e.message if hasattr(e, 'message') else e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def return_asset(self, request, pk=None):
        school = get_request_school(request)
        asset = self.get_object()
        condition = request.data.get('condition')
        notes = request.data.get('notes', '')

        try:
            updated_asset = inventory_service.return_asset(
                school=school,
                asset=asset,
                condition=condition,
                notes=notes
            )
            return Response(self.get_serializer(updated_asset).data)
        except ValidationError as e:
            return Response({'error': str(e.message if hasattr(e, 'message') else e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def lifecycle_action(self, request, pk=None):
        school = get_request_school(request)
        asset = self.get_object()
        action_status = request.data.get('status')
        reason = request.data.get('reason', '')
        notes = request.data.get('notes', '')

        try:
            updated_asset = inventory_service.dispose_or_retire_asset(
                school=school,
                asset=asset,
                status=action_status,
                reason=reason,
                performed_by=request.user,
                notes=notes
            )
            return Response(self.get_serializer(updated_asset).data)
        except ValidationError as e:
            return Response({'error': str(e.message if hasattr(e, 'message') else e)}, status=status.HTTP_400_BAD_REQUEST)


class AssetMaintenanceViewSet(viewsets.ModelViewSet):
    serializer_class = AssetMaintenanceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        school = get_request_school(self.request)
        return AssetMaintenance.objects.filter(asset__school=school).select_related('asset', 'created_by')

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        school = get_request_school(request)
        record = self.get_object()
        cost = Decimal(str(request.data.get('cost', record.cost)))
        restored_status = request.data.get('restored_status', Asset.STATUS_AVAILABLE)
        notes = request.data.get('notes', '')

        try:
            updated_record = inventory_service.complete_asset_maintenance(
                school=school,
                maintenance_record=record,
                final_cost=cost,
                restored_status=restored_status,
                notes=notes
            )
            return Response(self.get_serializer(updated_record).data)
        except ValidationError as e:
            return Response({'error': str(e.message if hasattr(e, 'message') else e)}, status=status.HTTP_400_BAD_REQUEST)
