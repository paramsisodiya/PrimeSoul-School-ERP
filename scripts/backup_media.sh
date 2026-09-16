#!/usr/bin/env bash
# ==============================================================================
# PrimeSoul School ERP - Media & Document Storage Backup Script
# Archives student documents, admission KYC, and institutional assets.
# ==============================================================================

set -euo pipefail

MEDIA_DIR="${MEDIA_DIR:-/var/www/primesoul/media}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/primesoul/media}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/primesoul_media_${TIMESTAMP}.tar.gz"
CHECKSUM_FILE="${BACKUP_FILE}.sha256"

mkdir -p "${BACKUP_DIR}"

echo "[$(date)] Starting Media directory backup from ${MEDIA_DIR}..."

if [ -d "${MEDIA_DIR}" ]; then
    tar -czf "${BACKUP_FILE}" -C "$(dirname "${MEDIA_DIR}")" "$(basename "${MEDIA_DIR}")"
    sha256sum "${BACKUP_FILE}" > "${CHECKSUM_FILE}"
    
    FILESIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
    echo "[$(date)] Media backup completed: ${BACKUP_FILE} (${FILESIZE})"
else
    echo "[$(date)] Warning: Media directory ${MEDIA_DIR} does not exist. Skipping."
fi

# Rotate old backups
find "${BACKUP_DIR}" -type f -name "primesoul_media_*.tar.gz*" -mtime +"${RETENTION_DAYS}" -delete
echo "[$(date)] Media backup rotation completed."
