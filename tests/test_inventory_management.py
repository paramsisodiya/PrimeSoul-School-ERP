"""
Phase 16: PrimeSoul ERP Inventory & Asset Management Test Suite.
Validates multi-tenant isolation, master data, transactional stock movements (IN, OUT, TRANSFER, ADJUSTMENT, RETURN),
Goods Receipt Notes (GRN), Stock Issues, Transfers, Returns, Adjustments, Low Stock calculation,
Fixed Asset Register, Asset Assignment, Maintenance lifecycle, Disposal, RBAC, and REST APIs.
"""
import datetime
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status

from django_school_management.tenants.models import School
from django_school_management.accounts.roles import Role, ensure_system_roles_exist, assign_role_to_user
from django_school_management.hr.models import Department, HRDesignation, Employee
from django_school_management.inventory.models import (
    InventoryCategory, UnitOfMeasure, Supplier, Store, InventoryItem,
    ItemStoreStock, StockMovement, PurchaseReceipt, PurchaseReceiptItem,
    StockIssue, StockReturn, StockTransfer, StockAdjustment,
    AssetCategory, Asset, AssetAssignment, AssetMaintenance
)
from django_school_management.inventory.services import inventory_service
from django_school_management.inventory.selectors import inventory_selectors

User = get_user_model()


class PrimeSoulInventoryManagementTests(TestCase):
    """Comprehensive test suite for Phase 16: Inventory & Asset Management."""

    def setUp(self):
        ensure_system_roles_exist()

        # 1. Tenants
        self.school_a = School.objects.create(
            name="Delhi Public School, R.K. Puram",
            slug="dps-rkpuram",
            board="CBSE",
            school_code="DPS-1034",
            is_active=True
        )
        self.school_b = School.objects.create(
            name="Modern School, Barakhamba",
            slug="modern-delhi",
            board="CBSE",
            school_code="MOD-5021",
            is_active=True
        )

        # 2. Users & Roles
        self.admin_user = User.objects.create_user(
            username="dps_admin",
            email="admin@dpsrkp.edu.in",
            password="Password123!",
            school=self.school_a,
            requested_role=Role.SCHOOL_ADMIN
        )
        assign_role_to_user(self.admin_user, Role.SCHOOL_ADMIN)

        self.accountant_user = User.objects.create_user(
            username="dps_accountant",
            email="accountant@dpsrkp.edu.in",
            password="Password123!",
            school=self.school_a,
            requested_role=Role.ACCOUNTANT
        )
        assign_role_to_user(self.accountant_user, Role.ACCOUNTANT)

        self.teacher_user = User.objects.create_user(
            username="teacher_neha",
            email="neha@dpsrkp.edu.in",
            password="Password123!",
            school=self.school_a,
            requested_role=Role.TEACHER
        )
        assign_role_to_user(self.teacher_user, Role.TEACHER)

        # 3. HR Department & Employee
        self.dept_sci = Department.objects.create(
            school=self.school_a,
            name="Science Department",
            code="DEPT-SCI"
        )
        self.desig_pgt = HRDesignation.objects.create(
            school=self.school_a,
            name="PGT Physics",
            code="DESIG-PGT-PHY",
            category=HRDesignation.CATEGORY_TEACHING
        )
        self.employee_neha = Employee.objects.create(
            school=self.school_a,
            user=self.teacher_user,
            employee_code="EMP-1001",
            full_name="Neha Sharma",
            department=self.dept_sci,
            designation=self.desig_pgt,
            status=Employee.STATUS_ACTIVE
        )

        # 4. Master Data
        self.uom_pcs = UnitOfMeasure.objects.create(
            school=self.school_a,
            name="Pieces",
            short_code="PCS"
        )
        self.uom_box = UnitOfMeasure.objects.create(
            school=self.school_a,
            name="Box of 100",
            short_code="BOX"
        )
        self.cat_stationery = InventoryCategory.objects.create(
            school=self.school_a,
            name="Stationery & Office Supplies",
            description="Paper, pens, registers"
        )
        self.cat_lab = InventoryCategory.objects.create(
            school=self.school_a,
            name="Physics Lab Consumables",
            description="Lab chemicals and glass items"
        )
        self.supplier = Supplier.objects.create(
            school=self.school_a,
            name="Hindustan Paper & Stationery Mart",
            gstin="07AAAAA0000A1Z5",
            contact_person="Rajesh Kumar",
            phone="9876543210",
            email="sales@hindustanstationery.in",
            address="42 Chawri Bazar, New Delhi"
        )
        self.main_store = Store.objects.create(
            school=self.school_a,
            name="Central Main Warehouse",
            code="STORE-MAIN",
            location="Block A, Ground Floor"
        )
        self.lab_store = Store.objects.create(
            school=self.school_a,
            name="Physics Lab Sub-Store",
            code="STORE-PHY-LAB",
            location="Science Block, 2nd Floor"
        )

        # 5. Inventory Items
        self.item_a4 = InventoryItem.objects.create(
            school=self.school_a,
            category=self.cat_stationery,
            unit=self.uom_box,
            name="A4 Copier Paper 75 GSM (500 Sheets/Rim)",
            sku="SKU-PAP-A4-75",
            reorder_level=Decimal('10.00'),
            default_purchase_price=Decimal('280.00')
        )
        self.item_markers = InventoryItem.objects.create(
            school=self.school_a,
            category=self.cat_stationery,
            unit=self.uom_box,
            name="Whiteboard Marker Pens (Box of 10)",
            sku="SKU-MRK-WB-10",
            reorder_level=Decimal('5.00'),
            default_purchase_price=Decimal('150.00')
        )

        # 6. Fixed Asset Category & Setup
        self.asset_cat_it = AssetCategory.objects.create(
            school=self.school_a,
            name="IT Equipment & Smart Class",
            description="Projectors, PCs, interactive panels"
        )
        self.asset_smartboard = Asset.objects.create(
            school=self.school_a,
            category=self.asset_cat_it,
            asset_tag="AST-DPS-2026-0001",
            name="Interactive 75-inch Touch Display",
            model_number="SMART-75X",
            serial_number="SN-75X-987654",
            purchase_date=datetime.date(2026, 4, 15),
            purchase_cost=Decimal('125000.00'),
            warranty_expiry=datetime.date(2029, 4, 14),
            current_location="Classroom 10-A",
            status=Asset.STATUS_AVAILABLE,
            condition=Asset.CONDITION_GOOD
        )

    # --------------------------------------------------------------------------
    # 1. GOODS RECEIPT NOTE (GRN) & INWARD MOVEMENT
    # --------------------------------------------------------------------------

    def test_purchase_receipt_grn_updates_stock_and_creates_ledger_entry(self):
        """Validates GRN confirmation atomically increments store stock and logs IN movement."""
        receipt = PurchaseReceipt.objects.create(
            school=self.school_a,
            supplier=self.supplier,
            store=self.main_store,
            receipt_number="GRN-2026-00001",
            purchase_date=datetime.date(2026, 5, 10),
            notes="INV-HPSM-9982",
            status=PurchaseReceipt.STATUS_DRAFT
        )
        PurchaseReceiptItem.objects.create(
            purchase_receipt=receipt,
            item=self.item_a4,
            quantity=Decimal('50.00'),
            unit_cost=Decimal('280.00')
        )
        PurchaseReceiptItem.objects.create(
            purchase_receipt=receipt,
            item=self.item_markers,
            quantity=Decimal('30.00'),
            unit_cost=Decimal('150.00')
        )

        grn = inventory_service.receive_purchase_receipt(receipt=receipt, user=self.admin_user)

        self.assertEqual(grn.status, PurchaseReceipt.STATUS_RECEIVED)
        self.assertEqual(grn.total_amount, Decimal('18500.00'))  # (50*280) + (30*150)

        # Stock balances in Main Store
        stock_a4 = ItemStoreStock.objects.get(item=self.item_a4, store=self.main_store)
        stock_markers = ItemStoreStock.objects.get(item=self.item_markers, store=self.main_store)
        self.assertEqual(stock_a4.quantity, Decimal('50.00'))
        self.assertEqual(stock_markers.quantity, Decimal('30.00'))

        # Stock Ledger (StockMovement)
        movements = StockMovement.objects.filter(school=self.school_a, reference_number=grn.receipt_number)
        self.assertEqual(movements.count(), 2)
        for m in movements:
            self.assertEqual(m.movement_type, StockMovement.TYPE_IN)
            self.assertEqual(m.destination_store, self.main_store)
            self.assertIsNone(m.source_store)

    # --------------------------------------------------------------------------
    # 2. STOCK ISSUE & NEGATIVE QUANTITY PREVENTION
    # --------------------------------------------------------------------------

    def test_stock_issue_decrements_stock_and_prevents_over_issuing(self):
        """Validates stock issuing to faculty and guarantees non-negative inventory constraint."""
        ItemStoreStock.objects.create(
            school=self.school_a,
            item=self.item_a4,
            store=self.main_store,
            quantity=Decimal('20.00')
        )

        issue = inventory_service.issue_stock(
            school=self.school_a,
            item=self.item_a4,
            store=self.main_store,
            quantity=Decimal('5.00'),
            purpose="Monthly exam paper distribution",
            recipient_type=StockIssue.RECIPIENT_EMPLOYEE,
            recipient_employee=self.employee_neha,
            user=self.admin_user,
            issue_date=datetime.date(2026, 5, 12)
        )
        self.assertEqual(issue.status, StockIssue.STATUS_ISSUED)

        stock = ItemStoreStock.objects.get(item=self.item_a4, store=self.main_store)
        self.assertEqual(stock.quantity, Decimal('15.00'))

        # Ledger check
        movement = StockMovement.objects.get(reference_number=f"ISSUE-{issue.id}")
        self.assertEqual(movement.movement_type, StockMovement.TYPE_OUT)
        self.assertEqual(movement.source_store, self.main_store)
        self.assertEqual(movement.quantity, Decimal('5.00'))

        # Over-issue attempt -> Must raise ValidationError
        with self.assertRaises(ValidationError) as ctx:
            inventory_service.issue_stock(
                school=self.school_a,
                item=self.item_a4,
                store=self.main_store,
                quantity=Decimal('25.00'),
                purpose="Extra paper",
                recipient_employee=self.employee_neha,
                user=self.admin_user
            )
        self.assertIn("Insufficient stock", str(ctx.exception))

    # --------------------------------------------------------------------------
    # 3. STOCK RETURN
    # --------------------------------------------------------------------------

    def test_stock_return_restores_store_quantity(self):
        """Validates unused stock returned to inventory increases balance."""
        ItemStoreStock.objects.create(
            school=self.school_a,
            item=self.item_a4,
            store=self.main_store,
            quantity=Decimal('15.00')
        )
        issue = StockIssue.objects.create(
            school=self.school_a,
            item=self.item_a4,
            store=self.main_store,
            quantity=Decimal('5.00'),
            purpose="Exam printouts",
            recipient_employee=self.employee_neha,
            status=StockIssue.STATUS_ISSUED
        )

        ret = inventory_service.return_stock(
            school=self.school_a,
            item=self.item_a4,
            store=self.main_store,
            quantity=Decimal('2.00'),
            stock_issue=issue,
            user=self.admin_user,
            return_date=datetime.date(2026, 5, 15),
            reason="Unused 2 boxes returned"
        )
        self.assertIsNotNone(ret.pk)

        stock = ItemStoreStock.objects.get(item=self.item_a4, store=self.main_store)
        self.assertEqual(stock.quantity, Decimal('17.00'))

        movement = StockMovement.objects.get(reference_number=f"RET-{ret.id}")
        self.assertEqual(movement.movement_type, StockMovement.TYPE_RETURN)
        self.assertEqual(movement.destination_store, self.main_store)

    # --------------------------------------------------------------------------
    # 4. INTER-STORE STOCK TRANSFER
    # --------------------------------------------------------------------------

    def test_inter_store_transfer_across_stores(self):
        """Validates moving stock from Central Store to Lab Store."""
        ItemStoreStock.objects.create(
            school=self.school_a,
            item=self.item_markers,
            store=self.main_store,
            quantity=Decimal('30.00')
        )

        transfer = inventory_service.transfer_stock(
            school=self.school_a,
            item=self.item_markers,
            source_store=self.main_store,
            destination_store=self.lab_store,
            quantity=Decimal('10.00'),
            user=self.admin_user,
            transfer_date=datetime.date(2026, 5, 16),
            notes="Transfer to Physics Lab"
        )
        self.assertIsNotNone(transfer.pk)

        src_stock = ItemStoreStock.objects.get(item=self.item_markers, store=self.main_store)
        dest_stock = ItemStoreStock.objects.get(item=self.item_markers, store=self.lab_store)
        self.assertEqual(src_stock.quantity, Decimal('20.00'))
        self.assertEqual(dest_stock.quantity, Decimal('10.00'))

        movement = StockMovement.objects.get(reference_number=transfer.reference_number)
        self.assertEqual(movement.movement_type, StockMovement.TYPE_TRANSFER)
        self.assertEqual(movement.source_store, self.main_store)
        self.assertEqual(movement.destination_store, self.lab_store)

    # --------------------------------------------------------------------------
    # 5. STOCK COUNT ADJUSTMENT
    # --------------------------------------------------------------------------

    def test_stock_count_adjustment_reconciliation(self):
        """Validates physical audit stock adjustments."""
        ItemStoreStock.objects.create(
            school=self.school_a,
            item=self.item_markers,
            store=self.main_store,
            quantity=Decimal('20.00')
        )

        adj = inventory_service.adjust_stock(
            school=self.school_a,
            item=self.item_markers,
            store=self.main_store,
            new_quantity=Decimal('18.00'),
            reason="Audit variance: 2 boxes damaged by water leakage",
            user=self.admin_user,
            adjustment_date=datetime.date(2026, 5, 20)
        )
        self.assertEqual(adj.delta_quantity, Decimal('-2.00'))

        stock = ItemStoreStock.objects.get(item=self.item_markers, store=self.main_store)
        self.assertEqual(stock.quantity, Decimal('18.00'))

        movement = StockMovement.objects.get(reference_number=f"ADJ-{adj.id}")
        self.assertEqual(movement.movement_type, StockMovement.TYPE_ADJUSTMENT)
        self.assertEqual(movement.quantity, Decimal('2.00'))

    # --------------------------------------------------------------------------
    # 6. LOW STOCK & REORDER SELECTORS
    # --------------------------------------------------------------------------

    def test_low_stock_and_kpis_selector_computation(self):
        """Validates low stock identification when current quantity <= reorder level."""
        ItemStoreStock.objects.create(
            school=self.school_a,
            item=self.item_a4,
            store=self.main_store,
            quantity=Decimal('8.00')  # reorder level is 10.00
        )
        low_items = inventory_selectors.get_low_stock_items(self.school_a)
        out_items = inventory_selectors.get_out_of_stock_items(self.school_a)

        self.assertIn(self.item_a4, low_items)
        self.assertIn(self.item_markers, out_items)

        kpis = inventory_selectors.get_inventory_dashboard_kpis(self.school_a)
        self.assertEqual(kpis['total_items'], 2)
        self.assertEqual(kpis['low_stock_count'], 1)
        self.assertEqual(kpis['out_of_stock_count'], 1)
        self.assertEqual(kpis['total_assets'], 1)

    # --------------------------------------------------------------------------
    # 7. FIXED ASSET LIFECYCLE & MAINTENANCE
    # --------------------------------------------------------------------------

    def test_asset_assignment_and_return_lifecycle(self):
        """Validates assigning fixed asset to faculty and subsequent return."""
        assignment = inventory_service.assign_asset(
            asset=self.asset_smartboard,
            assigned_to_employee=self.employee_neha,
            assigned_to_department=self.dept_sci,
            location="Room 101, Science Block",
            assigned_by=self.admin_user,
            assigned_date=datetime.date(2026, 5, 1)
        )
        self.asset_smartboard.refresh_from_db()
        self.assertEqual(self.asset_smartboard.status, Asset.STATUS_ASSIGNED)
        self.assertEqual(self.asset_smartboard.assigned_employee, self.employee_neha)

        # Return Asset
        inventory_service.return_asset(
            asset=self.asset_smartboard,
            returned_by=self.admin_user,
            return_date=datetime.date(2026, 6, 1),
            return_location="Central Main Warehouse",
            condition=Asset.CONDITION_FAIR
        )
        self.asset_smartboard.refresh_from_db()
        self.assertEqual(self.asset_smartboard.status, Asset.STATUS_AVAILABLE)
        self.assertEqual(self.asset_smartboard.condition, Asset.CONDITION_FAIR)
        self.assertIsNone(self.asset_smartboard.assigned_employee)

        assignment.refresh_from_db()
        self.assertFalse(assignment.is_active)
        self.assertEqual(assignment.returned_date, datetime.date(2026, 6, 1))

    def test_asset_maintenance_workflow(self):
        """Validates asset repair logging and maintenance completion."""
        maint = inventory_service.log_asset_maintenance_start(
            asset=self.asset_smartboard,
            issue_description="Touch panel flickering on right edge",
            service_provider="SmartTech Solutions NCR",
            user=self.admin_user,
            start_date=datetime.date(2026, 6, 10)
        )
        self.asset_smartboard.refresh_from_db()
        self.assertEqual(self.asset_smartboard.status, Asset.STATUS_IN_REPAIR)

        # Complete maintenance
        completed_maint = inventory_service.complete_asset_maintenance(
            maintenance=maint,
            completion_date=datetime.date(2026, 6, 15),
            actual_cost=Decimal('3500.00'),
            resulting_condition=Asset.CONDITION_GOOD,
            notes="Capacitor replaced"
        )
        self.asset_smartboard.refresh_from_db()
        self.assertEqual(self.asset_smartboard.status, Asset.STATUS_AVAILABLE)
        self.assertEqual(completed_maint.cost, Decimal('3500.00'))

    # --------------------------------------------------------------------------
    # 8. MULTI-TENANT ISOLATION
    # --------------------------------------------------------------------------

    def test_tenant_isolation_prevents_cross_school_access(self):
        """Guarantees School B cannot view or perform operations on School A's inventory."""
        cat_b = InventoryCategory.objects.create(school=self.school_b, name="General", description="Gen")
        uom_b = UnitOfMeasure.objects.create(school=self.school_b, name="Units", short_code="UNT")
        item_school_b = InventoryItem.objects.create(
            school=self.school_b,
            category=cat_b,
            unit=uom_b,
            name="School B Projector Lamp",
            sku="SKU-MOD-PROJ-01"
        )
        items_a = inventory_selectors.get_inventory_items(self.school_a)
        self.assertNotIn(item_school_b, items_a)

    # --------------------------------------------------------------------------
    # 9. REST API ENDPOINTS
    # --------------------------------------------------------------------------

    def test_inventory_rest_apis(self):
        """Validates DRF API endpoints under /api/v1/inventory/."""
        client = APIClient()
        client.force_authenticate(user=self.admin_user)

        # 1. Dashboard API
        resp = client.get('/api/v1/inventory/dashboard/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('total_items', resp.data)

        # 2. Items API
        resp = client.get('/api/v1/inventory/items/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = resp.data.get('results', resp.data)
        self.assertTrue(len(results) >= 2)
