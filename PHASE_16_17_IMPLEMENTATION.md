# PrimeSoul School ERP — Phase 16 & Phase 17 Technical Implementation Document

**Module Scope**: 
- **Phase 16**: Inventory & Asset Management
- **Phase 17**: Advanced Reports & Analytics
**Author**: PrimeSoul ERP Engineering Team  
**Status**: Completed & Verified (100%)  
**Target Environment**: Multi-Tenant Indian K-12 Institutional Architecture  

---

## 1. Executive Summary

Phases 16 and 17 deliver foundational enterprise capabilities to PrimeSoul School ERP:
1. **Phase 16 (Inventory & Asset Management)**: A double-entry stock ledger, store partitions, Goods Receipt Note (GRN) procurement tracking, stock distribution/issues, inter-store transfers, return/damage reconciliation, and a complete Fixed Asset Register with maintenance and lifecycle management.
2. **Phase 17 (Advanced Reports & Analytics)**: An Executive Decision Support Dashboard and 9 specialized domain reporting engines aggregating live database metrics across Academics, Attendance, Admissions, Examinations, Finance, Transport, Library, HR, and Inventory, complete with UTF-8 CSV (Excel BOM) and ReportLab PDF export pipelines, strict RBAC, and sensitive data (PAN/Bank) masking.

---

## 2. Phase 16: Inventory & Asset Management Architecture

### 2.1 Database Models (`django_school_management/inventory/models.py`)

All models inherit from `TenantModel` (strict school tenant isolation) and `TimeStampedModel`:

| Model | Classification | Description & Key Attributes |
| :--- | :--- | :--- |
| `InventoryCategory` | Master Data | Hierarchical product categories (Stationery, Lab Consumables, Cleaning, Sports). |
| `UnitOfMeasure` | Master Data | Standard units (PCS, BOX, PKT, KG, LTR, SET, DOZ). |
| `Supplier` | Master Data | Vendors with Indian 15-digit GSTIN validation regex (`^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$`). |
| `Store` | Master Data | Physical store/warehouse partitions (Main Warehouse, Physics Lab Store, Sports Store, IT Store). |
| `InventoryItem` | Master Data | Consumable item master with SKU, reorder level, default unit purchase cost, and stock aggregate properties. |
| `ItemStoreStock` | State Model | Real-time stock balance per item per physical store. |
| `StockMovement` | Immutable Ledger | Transactional audit log recording `IN`, `OUT`, `TRANSFER`, `ADJUSTMENT`, and `RETURN` movements with timestamps and users. |
| `PurchaseReceipt` & `PurchaseReceiptItem` | Workflow | Goods Receipt Notes (GRN) capturing vendor deliveries and atomically updating store stock upon verification. |
| `StockIssue` | Workflow | Consumable stock distribution to faculty, departments, or students with non-negative stock guards. |
| `StockReturn` | Workflow | Return of unused items back into store inventory. |
| `StockTransfer` | Workflow | Inter-store transfer atomically decrementing source store and incrementing destination store. |
| `StockAdjustment` | Workflow | Physical stock reconciliation logging surplus or deficit variances. |
| `AssetCategory` | Master Data | Fixed capital asset classifications (IT Hardware, Lab Equipment, Furniture, Audio-Visual). |
| `Asset` | Master Data | Individual fixed assets with unique Asset Tag (`AST-XXXXX`), serial number, purchase cost, warranty expiry, lifecycle status (`AVAILABLE`, `ASSIGNED`, `IN_REPAIR`, `DISPOSED`, `RETIRED`), and physical condition. |
| `AssetAssignment` | Workflow | Custody tracking linking assets to faculty or departments with checkout and return timestamps. |
| `AssetMaintenance` | Workflow | Maintenance and repair ticket tracking updating asset state to `IN_REPAIR` and logging repair costs upon completion. |

---

### 2.2 Transactional Service Layer (`services/inventory_service.py`)

- `@transaction.atomic` guarantees that inventory movements, stock adjustments, and asset status updates maintain 100% ACID compliance.
- `receive_purchase_receipt(receipt, user)`: Validates receipt items, increments `ItemStoreStock`, generates `StockMovement(TYPE_IN)`, and marks GRN as `RECEIVED`.
- `issue_stock(...)`: Enforces `stock.quantity >= issue_quantity`, decrements stock, records `StockIssue`, and generates `StockMovement(TYPE_OUT)`.
- `transfer_stock(...)`: Atomically updates source and destination stores and logs `StockMovement(TYPE_TRANSFER)`.
- `adjust_stock(...)`: Reconciles actual physical counts against ledger balances and records `StockMovement(TYPE_ADJUSTMENT)`.
- `assign_asset(...)` & `return_asset(...)`: Manages asset custody transitions and state changes between `AVAILABLE` and `ASSIGNED`.
- `log_asset_maintenance(...)` & `complete_asset_maintenance(...)`: Transitions asset between `IN_REPAIR` and `AVAILABLE`/`RETIRED`.

---

### 2.3 UI & REST APIs

- **Web Views (`inventory/views.py`)**: 20+ tenant-scoped views protected by `@login_required` and `@role_required` (School Admin, Accountant).
- **Templates (`templates/inventory/`)**: 27 PrimeSoul-branded responsive HTML templates with KPI metric cards, badge indicators, modals, and tables.
- **REST Endpoints (`/api/v1/inventory/`)**:
  - `GET /api/v1/inventory/dashboard/`: Dashboard KPIs, valuation, and low stock count.
  - `GET /api/v1/inventory/items/`: Inventory items with live stock balances.
  - `GET /api/v1/inventory/assets/`: Asset register with status and assignment filters.
  - `GET /api/v1/inventory/movements/`: Immutable stock movement audit ledger.

---

## 3. Phase 17: Advanced Reports & Analytics Architecture

### 3.1 Live Database Aggregation Engine (`reports/selectors/report_selectors.py`)

Zero hardcoded or fake metrics. All indicators are computed in real-time from active Django ORM models partitioned by tenant school:

1. **Executive Dashboard KPIs**: Macro summary combining Student Enrollment, Today's Attendance %, Academics overview, Exam pass rates, Total invoiced vs collected fee balances, Admission funnel metrics, Transport fleet utilization, Library circulation, HR staff headcount, and Inventory asset valuation.
2. **Finance Reports**: Date-filtered fee register, payment mode breakdowns (UPI, Cash, Online, Cheque), and outstanding invoice trackers.
3. **Academic Reports**: Class and section strength breakdown, gender ratios (Boys/Girls), and section room capacity utilization.
4. **Attendance Reports**: Daily institutional attendance summary (Present, Absent, Late, Half-Day) and percentage calculations.
5. **Examination Reports**: Exam performance metrics, subject pass percentages, highest/average marks, and grade distributions.
6. **Admissions Funnel**: Conversion tracking from Inquiry $\to$ Application $\to$ Document Review $\to$ Interview $\to$ Approved $\to$ Admitted.
7. **Transport Utilization**: Route-wise capacity vs student seat allocation and vehicle status.
8. **Library Analytics**: Total loans, active checkouts, overdue titles, and fine collection status.
9. **HR & Payroll Reports**: Department headcounts, active staff rosters, and payroll disbursement history.
10. **Inventory Reports**: Current store stock balances, low-stock threshold triggers, and fixed asset valuations.

---

### 3.2 Security, RBAC & Sensitive PII Masking

- **RBAC Enforcement**: The Reporting Hub is strictly accessible to Executive/Admin roles (`Platform Super Admin`, `School Admin`, `Principal`, `Vice Principal`, `Accountant`). Portal users (`Student`, `Parent`, `Teacher`) receive an immediate `HTTP 403 Forbidden`.
- **PII Masking (`report_selectors.get_hr_reports`)**:
  - PAN Numbers: Masked as `AB******4F` (only first 2 and last 2 characters visible).
  - Bank Accounts: Masked as `******1234` (only last 4 digits visible).

---

### 3.3 Export Engine (`services/export_service.py`)

- **Excel-Compatible UTF-8 CSV**: Prepends `\ufeff` Byte Order Mark (BOM) to ensure Microsoft Excel correctly parses Indian regional characters and Rupee (`₹`) symbols without encoding errors. Generates timestamped attachments (`filename_YYYYMMDD_HHMMSS.csv`).
- **Institutional PDF Reports**: Built on ReportLab with branded PrimeSoul headers, school metadata, timestamped watermarks, styled data tables, and pagination.

---

### 3.4 REST APIs (`/api/v1/reports/`)

- `GET /api/v1/reports/dashboard/`: Executive intelligence dashboard data.
- `GET /api/v1/reports/finance/`: Financial collections, dues, and payment methods.
- `GET /api/v1/reports/hr/`: PII-masked staff directory and department headcounts.
- `GET /api/v1/reports/academics/`: Class section strengths and capacity.
- `GET /api/v1/reports/attendance/`: Daily attendance roll summary.
- `GET /api/v1/reports/examinations/`: Exam performance metrics.
- `GET /api/v1/reports/admissions/`: Admission conversion funnel.
- `GET /api/v1/reports/transport/`: Transport route utilization.
- `GET /api/v1/reports/library/`: Library circulation and fine stats.
- `GET /api/v1/reports/inventory/`: Stock valuation and low-stock alerts.

---

## 4. Verification & Test Suite

Automated test suites executed and verified with 100% pass rate:
- `tests/test_inventory_management.py` (10 tests) $\to$ **OK**
- `tests/test_advanced_reports.py` (8 tests) $\to$ **OK**

```
Ran 18 tests in 79.753s
OK
```
