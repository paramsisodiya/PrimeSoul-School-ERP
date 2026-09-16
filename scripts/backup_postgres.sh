#!/usr/bin/env bash
# ==============================================================================
# PrimeSoul School ERP - PostgreSQL Automated Backup Script
# Creates timestamped, gzip-compressed SQL dumps with SHA256 integrity checksums.
# ==============================================================================

set -euo pipefail

# Configuration
BACKUP_DIR="${BACKUP_DIR:-/var/backups/primesoul/postgres}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/primesoul_db_${TIMESTAMP}.sql.gz"
CHECKSUM_FILE="${BACKUP_FILE}.sha256"

# Database credentials from environment
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-primesoul_erp}"
DB_USER="${DB_USER:-postgres}"

mkdir -p "${BACKUP_DIR}"

echo "[$(date)] Starting PostgreSQL backup for database: ${DB_NAME}..."

# Execute pg_dump with custom compressed format
PGPASSWORD="${DB_PASSWORD:-}" pg_dump \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    -d "${DB_NAME}" \
    --no-owner \
    --no-privileges \
    --clean \
    --if-exists \
    | gzip -9 > "${BACKUP_FILE}"

# Generate SHA256 checksum
sha256sum "${BACKUP_FILE}" > "${CHECKSUM_FILE}"

FILESIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
echo "[$(date)] Backup completed successfully: ${BACKUP_FILE} (${FILESIZE})"
echo "[$(date)] Integrity checksum generated: ${CHECKSUM_FILE}"

# Rotate old backups
echo "[$(date)] Cleaning up backups older than ${RETENTION_DAYS} days..."
find "${BACKUP_DIR}" -type f -name "primesoul_db_*.sql.gz*" -mtime +"${RETENTION_DAYS}" -delete

echo "[$(date)] Backup rotation completed."
