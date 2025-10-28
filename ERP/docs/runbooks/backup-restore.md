# Runbook: Database Backup Restore

**Document Version:** 1.0  
**Last Updated:** 2025-10-18  
**Owner:** DevOps Team  
**Severity:** P1 (Critical)

---

## 📋 Purpose

This runbook provides step-by-step instructions to restore Himalytix ERP PostgreSQL database from encrypted backups stored in S3/GCS.

## ⏱️ Expected Duration

- **Staging**: 15-30 minutes
- **Production**: 30-60 minutes (including verification)

## 🎯 Prerequisites

### Access Requirements
- [ ] SSH access to target server
- [ ] AWS CLI configured (for S3) or gcloud (for GCS)
- [ ] PostgreSQL client installed (`psql`, `pg_restore`)
- [ ] `BACKUP_ENCRYPTION_KEY` secret available
- [ ] Database credentials (superuser access)

### Tools Required
```bash
# Verify tools are installed
psql --version
aws --version  # or: gcloud --version
openssl version
```

### Environment Variables
```bash
export DB_NAME="erpdb"
export DB_USER="postgres"
export DB_PASSWORD="your_password"
export DB_HOST="localhost"
export DB_PORT="5432"
export BACKUP_ENCRYPTION_KEY="your_encryption_key"
export S3_BUCKET="your-backup-bucket"  # or GCS_BUCKET
```

---

## 🚨 Pre-Restore Checklist

- [ ] **Verify backup exists** in S3/GCS
- [ ] **Create database snapshot** (current state)
- [ ] **Stop application services** (Django, Celery workers)
- [ ] **Notify stakeholders** (downtime window)
- [ ] **Verify disk space** (2x backup size)

---

## 📥 Step 1: Download Backup from Cloud

### Option A: AWS S3

```bash
# List available backups
aws s3 ls s3://${S3_BUCKET}/backups/production/ --human-readable

# Download specific backup
BACKUP_DATE="20251018_020000"  # Set to desired backup timestamp
BACKUP_FILE="himalytix_production_${BACKUP_DATE}.sql.gz.enc"

aws s3 cp \
  "s3://${S3_BUCKET}/backups/production/${BACKUP_FILE}" \
  "/tmp/${BACKUP_FILE}"

# Verify download
ls -lh "/tmp/${BACKUP_FILE}"
```

### Option B: Google Cloud Storage

```bash
# List available backups
gsutil ls gs://${GCS_BUCKET}/backups/production/

# Download specific backup
BACKUP_DATE="20251018_020000"
BACKUP_FILE="himalytix_production_${BACKUP_DATE}.sql.gz.enc"

gsutil cp \
  "gs://${GCS_BUCKET}/backups/production/${BACKUP_FILE}" \
  "/tmp/${BACKUP_FILE}"

# Verify download
ls -lh "/tmp/${BACKUP_FILE}"
```

---

## 🔓 Step 2: Decrypt Backup

```bash
# Decrypt backup (if encrypted)
openssl enc -aes-256-cbc \
  -d \
  -pbkdf2 \
  -in "/tmp/${BACKUP_FILE}" \
  -out "/tmp/${BACKUP_FILE%.enc}" \
  -k "${BACKUP_ENCRYPTION_KEY}"

# Verify decryption
file "/tmp/${BACKUP_FILE%.enc}"
# Output should show: gzip compressed data
```

---

## 📦 Step 3: Decompress Backup

```bash
# Decompress gzip archive
gunzip "/tmp/${BACKUP_FILE%.enc}"

# Verify SQL file
BACKUP_SQL="/tmp/${BACKUP_FILE%.gz.enc}"
head -n 10 "${BACKUP_SQL}"
# Should show SQL commands
```

---

## 🛑 Step 4: Stop Application Services

```bash
# Stop Django application
sudo systemctl stop himalytix-django

# Stop Celery workers
sudo systemctl stop himalytix-celery

# Stop Celery beat scheduler
sudo systemctl stop himalytix-celery-beat

# Verify services stopped
sudo systemctl status himalytix-django
sudo systemctl status himalytix-celery
```

---

## 🗄️ Step 5: Create Current Database Snapshot

```bash
# Create safety snapshot of current database
SNAPSHOT_DATE=$(date +%Y%m%d_%H%M%S)
SNAPSHOT_FILE="/tmp/pre_restore_snapshot_${SNAPSHOT_DATE}.sql"

export PGPASSWORD="${DB_PASSWORD}"

pg_dump \
  -h "${DB_HOST}" \
  -p "${DB_PORT}" \
  -U "${DB_USER}" \
  -d "${DB_NAME}" \
  --format=plain \
  > "${SNAPSHOT_FILE}"

gzip "${SNAPSHOT_FILE}"

echo "✅ Snapshot created: ${SNAPSHOT_FILE}.gz"
```

---

## 🔄 Step 6: Drop and Recreate Database

⚠️ **CRITICAL**: This step will delete all current data!

```bash
export PGPASSWORD="${DB_PASSWORD}"

# Terminate active connections
psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d postgres <<EOF
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = '${DB_NAME}' AND pid <> pg_backend_pid();
EOF

# Drop database
psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d postgres <<EOF
DROP DATABASE IF EXISTS ${DB_NAME};
EOF

# Recreate database
psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d postgres <<EOF
CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};
EOF

echo "✅ Database recreated"
```

---

## 📥 Step 7: Restore Backup

```bash
# Restore SQL dump
psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" \
  < "${BACKUP_SQL}"

# Check for errors
if [ $? -eq 0 ]; then
  echo "✅ Restore completed successfully"
else
  echo "❌ Restore failed! Check logs above"
  exit 1
fi

unset PGPASSWORD
```

---

## ✅ Step 8: Verification

### 8.1 Check Table Counts

```bash
export PGPASSWORD="${DB_PASSWORD}"

psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" <<EOF
-- Check table counts
SELECT 
  schemaname,
  tablename,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
LIMIT 10;

-- Check total record count for critical tables
SELECT 'CustomUser' AS table, COUNT(*) FROM usermanagement_customuser
UNION ALL
SELECT 'Organizations', COUNT(*) FROM usermanagement_organization
UNION ALL
SELECT 'JournalEntries', COUNT(*) FROM accounting_journalentry;
EOF

unset PGPASSWORD
```

### 8.2 Test Database Connectivity

```bash
# Run Django check
cd /path/to/himalytix-erp
source venv/bin/activate

python manage.py check --database default

# Test migration status
python manage.py showmigrations
```

---

## 🚀 Step 9: Restart Application Services

```bash
# Start Celery workers
sudo systemctl start himalytix-celery

# Start Celery beat
sudo systemctl start himalytix-celery-beat

# Start Django application
sudo systemctl start himalytix-django

# Verify services started
sudo systemctl status himalytix-django
sudo systemctl status himalytix-celery

# Check logs
sudo journalctl -u himalytix-django -f --lines=50
```

---

## 🧪 Step 10: Smoke Tests

```bash
# Test login
curl -X POST http://localhost:8000/accounts/login/ \
  -d "username=admin&password=test" \
  -c /tmp/cookies.txt

# Test API health
curl -X GET http://localhost:8000/api/v1/health/ \
  -b /tmp/cookies.txt

# Test dashboard
curl -X GET http://localhost:8000/ \
  -b /tmp/cookies.txt

# Test database query
python manage.py shell <<EOF
from usermanagement.models import CustomUser
print(f"Total users: {CustomUser.objects.count()}")
EOF
```

---

## 🧹 Step 11: Cleanup

```bash
# Remove downloaded backup files
rm -f "/tmp/${BACKUP_FILE}"
rm -f "/tmp/${BACKUP_FILE%.enc}"
rm -f "${BACKUP_SQL}"

# Archive snapshot (optional - keep for 7 days)
mv "${SNAPSHOT_FILE}.gz" "/backups/snapshots/"

echo "✅ Cleanup complete"
```

---

## 🔄 Rollback Procedure

If restore fails, rollback to snapshot:

```bash
# Restore from snapshot
SNAPSHOT_FILE="/tmp/pre_restore_snapshot_YYYYMMDD_HHMMSS.sql"

gunzip "${SNAPSHOT_FILE}.gz"

export PGPASSWORD="${DB_PASSWORD}"

psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d postgres <<EOF
DROP DATABASE IF EXISTS ${DB_NAME};
CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};
EOF

psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" \
  < "${SNAPSHOT_FILE}"

unset PGPASSWORD

# Restart services
sudo systemctl restart himalytix-celery
sudo systemctl restart himalytix-django
```

---

## 🐛 Troubleshooting

### Issue: "role does not exist" errors

**Solution:**
```sql
-- Create missing roles
CREATE ROLE your_role_name LOGIN PASSWORD 'password';
GRANT ALL PRIVILEGES ON DATABASE erpdb TO your_role_name;
```

### Issue: "disk full" during restore

**Solution:**
```bash
# Check disk space
df -h

# Clear temp files
sudo du -sh /tmp/* | sort -h
sudo rm -rf /tmp/old_files

# Extend volume (AWS EBS)
aws ec2 modify-volume --volume-id vol-xxx --size 100
```

### Issue: Slow restore performance

**Solution:**
```sql
-- Disable triggers during restore (add to SQL file)
ALTER TABLE table_name DISABLE TRIGGER ALL;
-- ... restore data ...
ALTER TABLE table_name ENABLE TRIGGER ALL;
```

### Issue: Foreign key constraint violations

**Solution:**
```sql
-- Temporarily disable foreign key checks
SET session_replication_role = 'replica';
-- ... restore data ...
SET session_replication_role = 'origin';
```

---

## 📊 Monitoring & Alerts

After restore, monitor:

- **Application logs:** `/var/log/himalytix/app.log`
- **Database logs:** `/var/log/postgresql/postgresql.log`
- **Metrics:** http://localhost:8000/metrics
- **Error rate:** Check Sentry dashboard
- **Response time:** Check APM dashboard

---

## 📝 Post-Restore Checklist

- [ ] Verify user login works
- [ ] Check critical tables have data
- [ ] Test API endpoints
- [ ] Verify Celery tasks running
- [ ] Check error logs (no new errors)
- [ ] Update stakeholders (restore complete)
- [ ] Document any issues in incident report

---

## 📞 Escalation

If restore fails after 2 attempts:

1. **Notify:** DevOps Lead, CTO
2. **Contact:** Database vendor support
3. **Fallback:** Restore from older backup (T-1 day)
4. **Create:** Incident ticket with full details

---

## 🔗 Related Documents

- [Backup Script](../scripts/backup_database.sh)
- [Backup Workflow](../.github/workflows/backup.yml)
- [Disaster Recovery Plan](disaster-recovery.md)
- [Database Architecture](../architecture_overview.md)

---

**Last Tested:** 2025-10-18  
**Test Environment:** Staging  
**Test Result:** ✅ Success (restore time: 23 minutes)
