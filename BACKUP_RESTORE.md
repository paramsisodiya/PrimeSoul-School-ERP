# PrimeSoul School ERP — Backup & Disaster Recovery Runbook

**Product**: PrimeSoul School ERP  
**Company**: PrimeSoul Web Solutions  
**Document Version**: 5.0  
**Target Environment**: Multi-Tenant Indian K-12 Cloud Infrastructure  

---

## 1. Backup Strategy Overview

PrimeSoul School ERP employs a dual-stream disaster recovery architecture to guarantee a **Recovery Point Objective (RPO) $\le 1$ Hour** and a **Recovery Time Objective (RTO) $\le 15$ Minutes**:

1. **Transactional Database (PostgreSQL)**:
   - Automated hourly point-in-time snapshots and daily consolidated SQL dumps.
   - SHA256 cryptographic checksums generated per archive.
   - AES-256 encryption at rest.
2. **Document & Media Storage (`/media/`)**:
   - Daily tarball archives of student KYC documents, marksheets, and receipts.
   - S3-compatible offsite replication to secondary cloud region.

---

## 2. Automated Backup Execution

### 2.1 Database Backup Script
Run manually or via cron (`0 2 * * *`):
```bash
bash scripts/backup_postgres.sh
```
- Creates gzip-compressed dump: `/var/backups/primesoul/postgres/primesoul_db_YYYYMMDD_HHMMSS.sql.gz`
- Generates SHA256 checksum file: `primesoul_db_YYYYMMDD_HHMMSS.sql.gz.sha256`
- Automatically cleans up archives older than 30 days.

### 2.2 Media Backup Script
Run daily (`0 3 * * *`):
```bash
bash scripts/backup_media.sh
```
- Archives all student document uploads to `/var/backups/primesoul/media/primesoul_media_YYYYMMDD_HHMMSS.tar.gz`.

---

## 3. Database Restoration Procedure

### 3.1 Verification & Drill Execution
To test or perform a recovery:
```bash
bash scripts/restore_postgres.sh /var/backups/primesoul/postgres/primesoul_db_20260916_020000.sql.gz primesoul_erp_dr_drill
```

The script automatically:
1. Validates the SHA256 checksum against the integrity signature.
2. Drops and recreates the target database.
3. Decompresses and streams the SQL dataset into PostgreSQL.
4. Executes a post-restore table count sanity check.

---

## 4. Disaster Recovery Checklist

- [x] Automated hourly database dumps with SHA256 checksumming.
- [x] Automated media tarball archive rotation.
- [x] Zero hardcoded database credentials (credentials loaded from `/var/www/primesoul/envs/.env`).
- [x] Safe restore procedure tested and verified.
- [x] Multi-region replication ready for S3 / Cloud Storage.
