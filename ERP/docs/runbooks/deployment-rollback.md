# 🔄 Deployment Rollback Runbook

**Version:** 1.0  
**Owner:** DevOps Team  
**Last Updated:** 2024-01-15

---

## 📋 Table of Contents
1. [Overview](#overview)
2. [When to Rollback](#when-to-rollback)
3. [Rollback Strategies](#rollback-strategies)
4. [Step-by-Step Procedures](#step-by-step-procedures)
5. [Verification](#verification)
6. [Database Rollback](#database-rollback)

---

## 🎯 Overview

This runbook covers rollback procedures for Himalytix ERP deployments. Use when:
- New deployment causes errors or degraded performance
- Database migrations fail
- Critical bug discovered in production
- Customer-reported issues spike after deployment

**Rollback SLAs:**
- **Critical issues (P0):** Rollback within 15 minutes
- **High issues (P1):** Rollback within 30 minutes
- **Medium issues (P2):** Fix forward or rollback within 2 hours

---

## 🚦 When to Rollback

### ✅ **ROLLBACK If:**
- Error rate >5% after deployment
- User-facing features completely broken
- Database migration causes data loss
- Security vulnerability introduced
- Customer escalation from VIP client

### ❌ **DON'T ROLLBACK If:**
- Minor UI glitch (fix forward instead)
- Single tenant affected (fix in next hotfix)
- Non-critical feature degraded
- Issue has simple configuration fix

**Decision Tree:**
```
Is it a P0/P1 incident?
├─ YES → Can it be fixed in <10 minutes?
│         ├─ YES → Fix forward
│         └─ NO → Rollback
└─ NO → Fix forward in next release
```

---

## 🔧 Rollback Strategies

### **Strategy 1: Git Revert (Recommended)**
- **Use Case:** Code-only changes, no database migrations
- **Rollback Time:** 5-10 minutes
- **Risk:** Low

### **Strategy 2: Container Revert (Blue-Green)**
- **Use Case:** Docker deployments with image tags
- **Rollback Time:** 2-5 minutes
- **Risk:** Very Low

### **Strategy 3: Database Rollback + Code Revert**
- **Use Case:** Deployment included database migrations
- **Rollback Time:** 15-30 minutes
- **Risk:** Medium (data loss possible)

### **Strategy 4: Full Backup Restore**
- **Use Case:** Data corruption, catastrophic failure
- **Rollback Time:** 30-60 minutes
- **Risk:** High (recent data loss)

---

## 📖 Step-by-Step Procedures

### **OPTION 1: Git Revert (Code-Only Rollback)**

**Prerequisites:**
- Recent deployment SHA known
- No database migrations in failed deployment
- Git repository access

**Steps:**
```bash
# 1. SSH into production server
ssh deploy@himalytix.com

# 2. Navigate to application directory
cd /var/www/himalytix

# 3. Check current commit
git log --oneline -5

# Example output:
# a1b2c3d (HEAD -> main) Fix user auth bug (BAD COMMIT)
# e4f5g6h Add email validation (LAST GOOD COMMIT)
# h7i8j9k Update dashboard UI

# 4. Create revert commit
git revert a1b2c3d --no-edit

# 5. Restart application
sudo systemctl restart gunicorn
sudo systemctl restart celery

# 6. Verify (see Verification section below)
curl -f http://localhost:8000/health/ready/

# 7. Clear cache (if using Redis)
docker-compose exec redis redis-cli -a changeme FLUSHALL

# 8. Monitor logs for 5 minutes
tail -f /var/log/gunicorn/error.log
```

**Rollback Time:** ~5 minutes  
**Success Criteria:** Error rate <1%, health checks pass

---

### **OPTION 2: Docker Container Rollback (Blue-Green)**

**Prerequisites:**
- Previous Docker image tag known
- Docker Compose or Kubernetes deployment
- Image registry accessible

**Steps (Docker Compose):**
```bash
# 1. Check current image version
docker-compose ps web

# Example output:
# himalytix-web   himalytix-erp:v1.5.3   Up 2 hours

# 2. Identify previous working version
docker images himalytix-erp --format "{{.Tag}}" | head -5

# Example output:
# v1.5.3 (current - BAD)
# v1.5.2 (last stable - GOOD)
# v1.5.1

# 3. Update docker-compose.yml
sed -i 's/himalytix-erp:v1.5.3/himalytix-erp:v1.5.2/g' docker-compose.yml

# 4. Pull previous image (if not cached)
docker-compose pull web

# 5. Restart web service
docker-compose up -d --no-deps web

# 6. Wait for health check
until curl -f http://localhost:8000/health/ready/; do
  echo "Waiting for service..."
  sleep 5
done

# 7. Monitor logs
docker-compose logs -f --tail=100 web

# 8. If successful, restart other services
docker-compose restart celery celery-beat
```

**Rollback Time:** ~3 minutes  
**Success Criteria:** Health checks pass, error rate normal

---

### **OPTION 3: Database Migration Rollback**

**⚠️ WARNING:** Database rollbacks can cause data loss. Always restore from backup if unsure.

**Prerequisites:**
- Migration name known
- Database backup taken before deployment (see `backup-restore.md`)
- Downtime window approved

**Steps:**
```bash
# 1. Check current migration status
docker-compose exec web python manage.py showmigrations

# Example output:
# accounting
#  [X] 0001_initial
#  [X] 0002_add_journal_entry
#  [X] 0003_add_audit_log (NEW - FAILING)

# 2. Stop application to prevent new writes
docker-compose stop web celery celery-beat

# 3. Create database snapshot (safety)
docker-compose exec postgres pg_dump -U erp -Fc himalytix > /tmp/pre-rollback-$(date +%Y%m%d-%H%M%S).dump

# 4. Attempt migration rollback
docker-compose exec web python manage.py migrate accounting 0002_add_journal_entry

# 5. If rollback fails, restore from backup
# See: docs/runbooks/backup-restore.md

# 6. Revert code to previous version
git revert <migration_commit_sha> --no-edit

# 7. Restart services
docker-compose up -d web celery celery-beat

# 8. Verify database state
docker-compose exec postgres psql -U erp -d himalytix -c \
  "SELECT table_name FROM information_schema.tables WHERE table_schema='public';"

# 9. Run smoke tests
docker-compose exec web python manage.py check --deploy
curl -f http://localhost:8000/api/v1/health/
```

**Rollback Time:** 15-30 minutes  
**Success Criteria:** Migration reverted, no data loss

---

### **OPTION 4: Full Backup Restore (Catastrophic)**

**Use Case:** Data corruption, complete system failure

**See Full Procedure:** [Backup & Restore Runbook](./backup-restore.md)

**Quick Steps:**
```bash
# 1. Stop all services
docker-compose down

# 2. Download latest backup
aws s3 cp s3://himalytix-backups/postgres/latest.dump.gz.enc /tmp/

# 3. Decrypt and restore
openssl enc -aes-256-cbc -d -in /tmp/latest.dump.gz.enc -out /tmp/latest.dump.gz
gunzip /tmp/latest.dump.gz
docker-compose up -d postgres
docker-compose exec -T postgres pg_restore -U erp -d himalytix -c /tmp/latest.dump

# 4. Restart application
docker-compose up -d
```

**Rollback Time:** 30-60 minutes  
**Data Loss:** Last N minutes since backup

---

## ✅ Verification

**After ANY rollback, verify these checks:**

### **1. Health Checks**
```bash
# Basic health
curl -f http://localhost:8000/health/

# Readiness (DB, Redis, Celery)
curl -f http://localhost:8000/health/ready/ | jq

# Expected output:
# {
#   "status": "ready",
#   "checks": {
#     "database": {"status": "ok"},
#     "redis_cache": {"status": "ok"},
#     "celery": {"status": "ok"}
#   }
# }
```

---

### **2. Smoke Tests**
```bash
# Test critical endpoints
curl -f http://localhost:8000/accounts/login/  # Login page
curl -f http://localhost:8000/api/v1/health/   # API health
curl -f http://localhost:8000/admin/           # Admin panel

# Test API authentication
TOKEN=$(curl -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"test"}' | jq -r .token)

curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/users/me/ | jq
```

---

### **3. Error Rate Check**
```bash
# Check Prometheus metrics
curl 'http://localhost:9090/api/v1/query?query=rate(django_http_requests_total_by_view_transport_method_total{status=~"5.."}[5m])' | jq

# Should be <1% of total requests
```

---

### **4. Database Integrity**
```sql
-- Check table counts
SELECT 
  schemaname,
  tablename,
  n_tup_ins AS inserts,
  n_tup_upd AS updates,
  n_tup_del AS deletes
FROM pg_stat_user_tables
WHERE schemaname = 'public'
ORDER BY n_tup_ins DESC
LIMIT 10;

-- Check for corrupted indexes
REINDEX DATABASE himalytix;
```

---

### **5. User Acceptance Test (UAT)**
```markdown
Manual UAT Checklist:
- [ ] Login with test account
- [ ] Create new journal entry
- [ ] View dashboard (no errors)
- [ ] Generate report (PDF export)
- [ ] Send test email notification
- [ ] Check audit logs
```

---

## 🗄️ Database Rollback

### **Migration Dependency Chain**
Django migrations are sequential. Rolling back migration `0005` requires rolling back `0006`, `0007`, etc.

**Check Dependencies:**
```python
# Django shell
from django.db.migrations.loader import MigrationLoader
loader = MigrationLoader(None)
loader.graph.forwards_plan(('accounting', '0003_add_audit_log'))
```

---

### **Data Preservation**
Before rolling back migrations that drop tables/columns:

```bash
# 1. Export data from tables about to be dropped
docker-compose exec postgres pg_dump -U erp -d himalytix \
  --table=audit_log \
  --data-only \
  --column-inserts > /tmp/audit_log_backup.sql

# 2. Rollback migration
docker-compose exec web python manage.py migrate accounting 0002

# 3. Re-import data if needed (after forward fix)
docker-compose exec -T postgres psql -U erp -d himalytix < /tmp/audit_log_backup.sql
```

---

## 📊 Rollback Metrics

**Track these metrics post-rollback:**
```promql
# Error rate (should drop to <1%)
rate(django_http_requests_total_by_view_transport_method_total{status=~"5.."}[5m])

# Request duration (should return to baseline)
histogram_quantile(0.95, rate(django_http_request_duration_seconds_bucket[5m]))

# Database connections (should stabilize)
pg_stat_database_numbackends{datname="himalytix"}
```

---

## 🚨 Rollback Failed - Escalation

If rollback fails after 2 attempts:

1. **Declare Major Incident (P0)**
   ```markdown
   🚨 ROLLBACK FAILED 🚨
   Deployment: v1.5.3 → v1.5.2
   Attempts: 2
   Current State: Service partially down
   Escalation: DevOps Lead, CTO
   ```

2. **Enable Maintenance Mode**
   ```bash
   # Create maintenance page
   echo "System maintenance in progress. Back in 30 minutes." > /var/www/maintenance.html
   
   # Configure nginx to serve maintenance page
   sudo systemctl reload nginx
   ```

3. **Contact Vendor Support**
   - Database vendor (if migration issues)
   - Cloud provider (if infrastructure issues)
   - Django community (#django-deployment Slack)

4. **Document Incident**
   - Create postmortem (see `incident-response.md`)
   - Add to rollback runbook (lessons learned)

---

## 📞 Emergency Contacts

| Role | Contact | Availability |
|------|---------|--------------|
| **DevOps Lead** | @devops-oncall (Slack) | 24/7 |
| **Database Admin** | dba@himalytix.com | Business hours |
| **CTO** | cto@himalytix.com | P0 incidents only |
| **Cloud Support** | AWS Enterprise Support | 24/7 |

---

## 🔗 Related Runbooks
- [Incident Response](./incident-response.md)
- [Backup & Restore](./backup-restore.md)
- [Scaling Procedures](./scaling.md)

---

**Feedback:** Improve this runbook via PR to `docs/runbooks/`.
