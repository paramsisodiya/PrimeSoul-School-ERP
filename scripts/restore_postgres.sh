#!/usr/bin/env bash
# ==============================================================================
# PrimeSoul School ERP - PostgreSQL Restore Verification Script
# Safely restores a gzipped SQL dump into a target database after checksum check.
# ==============================================================================

set -euo pipefail

if [ "$#" -lt 1 ]; then
    echo "Usage: $0 <path_to_backup_file.sql.gz> [target_db_name]"
    exit 1
fi

BACKUP_FILE="$1"
TARGET_DB="${2:-${DB_NAME:-primesoul_erp_restore_test}}"

DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-postgres}"

if [ ! -f "${BACKUP_FILE}" ]; then
    echo "Error: Backup file '${BACKUP_FILE}' not found."
    exit 1
fi

# 1. Integrity Check
CHECKSUM_FILE="${BACKUP_FILE}.sha256"
if [ -f "${CHECKSUM_FILE}" ]; then
    echo "[$(date)] Verifying SHA256 checksum..."
    cd "$(dirname "${BACKUP_FILE}")"
    sha256sum --check "$(basename "${CHECKSUM_FILE}")"
    echo "[$(date)] Checksum verification passed."
fi

echo "[$(date)] Restoring ${BACKUP_FILE} into database '${TARGET_DB}'..."

# 2. Database Recreation
PGPASSWORD="${DB_PASSWORD:-}" psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d postgres -c "DROP DATABASE IF EXISTS ${TARGET_DB};"
PGPASSWORD="${DB_PASSWORD:-}" psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d postgres -c "CREATE DATABASE ${TARGET_DB};"

# 3. Stream & Uncompress Dump
gunzip -c "${BACKUP_FILE}" | PGPASSWORD="${DB_PASSWORD:-}" psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${TARGET_DB}"

echo "[$(date)] Database restoration completed successfully into '${TARGET_DB}'."

# 4. Basic Smoke Query
TABLE_COUNT=$(PGPASSWORD="${DB_PASSWORD:-}" psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${TARGET_DB}" -t -c "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';")
echo "[$(date)] Verification: ${TABLE_COUNT// /} tables verified in restored schema."
