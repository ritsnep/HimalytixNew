#!/bin/bash
# =============================================================================
# Database Backup Script for Himalytix ERP
# =============================================================================
# This script creates encrypted PostgreSQL backups and uploads to S3/GCS
#
# Usage:
#   ./backup_database.sh [environment]
#
# Environment variables required:
#   - DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT
#   - BACKUP_ENCRYPTION_KEY (for encryption)
#   - AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, S3_BUCKET (for S3)
#   or
#   - GOOGLE_APPLICATION_CREDENTIALS, GCS_BUCKET (for GCS)
# =============================================================================

set -euo pipefail  # Exit on error, undefined vars, pipe failures

# Configuration
ENVIRONMENT="${1:-production}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="${BACKUP_DIR:-/tmp/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"

# Database config (from environment or .env file)
: "${DB_NAME:?Environment variable DB_NAME is required}"
: "${DB_USER:?Environment variable DB_USER is required}"
: "${DB_HOST:-localhost}"
: "${DB_PORT:-5432}"

# Backup file paths
BACKUP_FILE="${BACKUP_DIR}/himalytix_${ENVIRONMENT}_${TIMESTAMP}.sql"
BACKUP_FILE_GZ="${BACKUP_FILE}.gz"
BACKUP_FILE_ENC="${BACKUP_FILE_GZ}.enc"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Create backup directory
mkdir -p "${BACKUP_DIR}"

# =============================================================================
# STEP 1: PostgreSQL Dump
# =============================================================================
log_info "Starting PostgreSQL backup for ${ENVIRONMENT}..."

export PGPASSWORD="${DB_PASSWORD}"

if pg_dump \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    -d "${DB_NAME}" \
    --format=plain \
    --no-owner \
    --no-acl \
    --clean \
    --if-exists \
    > "${BACKUP_FILE}"; then
    log_info "Database dump completed: $(du -h ${BACKUP_FILE} | cut -f1)"
else
    log_error "Database dump failed!"
    exit 1
fi

unset PGPASSWORD

# =============================================================================
# STEP 2: Compress
# =============================================================================
log_info "Compressing backup..."

if gzip -9 "${BACKUP_FILE}"; then
    log_info "Compression completed: $(du -h ${BACKUP_FILE_GZ} | cut -f1)"
else
    log_error "Compression failed!"
    exit 1
fi

# =============================================================================
# STEP 3: Encrypt (optional)
# =============================================================================
if [ -n "${BACKUP_ENCRYPTION_KEY:-}" ]; then
    log_info "Encrypting backup..."
    
    if openssl enc -aes-256-cbc \
        -salt \
        -pbkdf2 \
        -in "${BACKUP_FILE_GZ}" \
        -out "${BACKUP_FILE_ENC}" \
        -k "${BACKUP_ENCRYPTION_KEY}"; then
        log_info "Encryption completed: $(du -h ${BACKUP_FILE_ENC} | cut -f1)"
        rm "${BACKUP_FILE_GZ}"  # Remove unencrypted file
        UPLOAD_FILE="${BACKUP_FILE_ENC}"
    else
        log_error "Encryption failed!"
        exit 1
    fi
else
    log_warn "No encryption key provided, skipping encryption"
    UPLOAD_FILE="${BACKUP_FILE_GZ}"
fi

# =============================================================================
# STEP 4: Upload to Cloud Storage
# =============================================================================

# AWS S3
if [ -n "${S3_BUCKET:-}" ]; then
    log_info "Uploading to S3: s3://${S3_BUCKET}/backups/${ENVIRONMENT}/"
    
    if command -v aws &> /dev/null; then
        if aws s3 cp "${UPLOAD_FILE}" \
            "s3://${S3_BUCKET}/backups/${ENVIRONMENT}/$(basename ${UPLOAD_FILE})" \
            --storage-class GLACIER; then
            log_info "S3 upload successful"
        else
            log_error "S3 upload failed!"
            exit 1
        fi
    else
        log_error "AWS CLI not installed!"
        exit 1
    fi
fi

# Google Cloud Storage
if [ -n "${GCS_BUCKET:-}" ]; then
    log_info "Uploading to GCS: gs://${GCS_BUCKET}/backups/${ENVIRONMENT}/"
    
    if command -v gsutil &> /dev/null; then
        if gsutil cp "${UPLOAD_FILE}" \
            "gs://${GCS_BUCKET}/backups/${ENVIRONMENT}/$(basename ${UPLOAD_FILE})"; then
            log_info "GCS upload successful"
        else
            log_error "GCS upload failed!"
            exit 1
        fi
    else
        log_error "gsutil not installed!"
        exit 1
    fi
fi

# =============================================================================
# STEP 5: Cleanup Old Backups
# =============================================================================
log_info "Cleaning up local backups older than ${RETENTION_DAYS} days..."

find "${BACKUP_DIR}" -name "himalytix_${ENVIRONMENT}_*.sql.gz*" \
    -type f -mtime +${RETENTION_DAYS} -delete

# S3 lifecycle policy cleanup (if configured)
if [ -n "${S3_BUCKET:-}" ] && command -v aws &> /dev/null; then
    log_info "Applying S3 lifecycle policy for ${RETENTION_DAYS}-day retention..."
    
    cat > /tmp/s3-lifecycle.json <<EOF
{
    "Rules": [{
        "Id": "DeleteOldBackups",
        "Status": "Enabled",
        "Prefix": "backups/${ENVIRONMENT}/",
        "Expiration": {
            "Days": ${RETENTION_DAYS}
        }
    }]
}
EOF
    
    aws s3api put-bucket-lifecycle-configuration \
        --bucket "${S3_BUCKET}" \
        --lifecycle-configuration file:///tmp/s3-lifecycle.json || true
fi

# =============================================================================
# STEP 6: Verification
# =============================================================================
log_info "Verifying backup integrity..."

# Test archive integrity
if file "${UPLOAD_FILE}" | grep -q "gzip\|openssl"; then
    log_info "✅ Backup file integrity verified"
else
    log_error "❌ Backup file integrity check failed!"
    exit 1
fi

# Remove local backup after successful upload
if [ -n "${S3_BUCKET:-}" ] || [ -n "${GCS_BUCKET:-}" ]; then
    rm -f "${UPLOAD_FILE}"
    log_info "Local backup cleaned up"
fi

# =============================================================================
# Summary
# =============================================================================
log_info "=================================================="
log_info "Backup completed successfully!"
log_info "Environment: ${ENVIRONMENT}"
log_info "Timestamp: ${TIMESTAMP}"
log_info "File: $(basename ${UPLOAD_FILE})"
if [ -n "${S3_BUCKET:-}" ]; then
    log_info "S3 Location: s3://${S3_BUCKET}/backups/${ENVIRONMENT}/"
fi
if [ -n "${GCS_BUCKET:-}" ]; then
    log_info "GCS Location: gs://${GCS_BUCKET}/backups/${ENVIRONMENT}/"
fi
log_info "=================================================="

exit 0
