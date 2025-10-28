# 🚨 Incident Response Runbook

**Version:** 1.0  
**Owner:** DevOps Team  
**Last Updated:** 2024-01-15

---

## 📋 Table of Contents
1. [Overview](#overview)
2. [Severity Levels](#severity-levels)
3. [Incident Response Process](#incident-response-process)
4. [Alert Triage](#alert-triage)
5. [Common Incidents](#common-incidents)
6. [Escalation Paths](#escalation-paths)
7. [Postmortem Template](#postmortem-template)

---

## 🎯 Overview

This runbook defines the incident response process for Himalytix ERP. Follow these procedures to:
- Detect and triage alerts
- Mitigate customer impact
- Restore service availability
- Prevent future occurrences

**SLA Targets:**
- **Critical (P0):** Response < 15 min, Resolution < 2 hours
- **High (P1):** Response < 1 hour, Resolution < 8 hours
- **Medium (P2):** Response < 4 hours, Resolution < 24 hours
- **Low (P3):** Response < 24 hours, Resolution < 5 days

---

## 🚦 Severity Levels

| Level | Criteria | Examples | Response Time |
|-------|----------|----------|---------------|
| **P0 - Critical** | Total service outage, data loss | Database down, authentication broken | < 15 min |
| **P1 - High** | Major feature degraded, multi-tenant impact | API 50% error rate, slow queries (>5s) | < 1 hour |
| **P2 - Medium** | Minor feature degraded, single tenant impact | Search broken, report export failed | < 4 hours |
| **P3 - Low** | UI issue, non-critical bug | UI glitch, cosmetic error | < 24 hours |

---

## 🔄 Incident Response Process

### **1. DETECTION (0-5 min)**
```bash
# Check monitoring dashboards
- Grafana: http://localhost:3000 (Metrics)
- Jaeger: http://localhost:16686 (Traces)
- Prometheus: http://localhost:9090/alerts (Active alerts)
- Logs: docker-compose logs -f web celery
```

**Automatic Alerts:**
- Prometheus → Slack #incidents
- Health check failures → PagerDuty
- Error rate spike (>5%) → Email + Slack

---

### **2. TRIAGE (5-15 min)**

**Assess Impact:**
```python
# Quick impact check (run from Django shell)
from django.contrib.auth import get_user_model
from tenancy.models import Tenant

# Active users (last 5 min)
User = get_user_model()
active_users = User.objects.filter(last_login__gte=timezone.now() - timedelta(minutes=5)).count()
print(f"Active users: {active_users}")

# Total tenants
total_tenants = Tenant.objects.count()
print(f"Total tenants: {total_tenants}")
```

**Determine Severity:**
1. Is the service down completely? → **P0**
2. Can users login? → If no, **P0**
3. Can users access core features (journal entry, reports)? → If no, **P1**
4. Is only one tenant affected? → **P2**
5. Is it a UI cosmetic issue? → **P3**

---

### **3. COMMUNICATION (15-20 min)**

**Update Stakeholders:**
```markdown
# Slack Template (#incidents channel)
🚨 **INCIDENT DETECTED** 🚨
**Severity:** P0 - Critical
**Status:** Investigating
**Impact:** Login page returns 500 errors
**Affected:** All users (estimated 120 active sessions)
**Started:** 2024-01-15 14:35 UTC
**Responder:** @john.doe

**Next Update:** In 30 minutes (15:05 UTC)
```

**Status Page Update:**
```bash
# If using external status page (e.g., Statuspage.io)
curl -X POST https://api.statuspage.io/v1/pages/YOUR_PAGE_ID/incidents \
  -H "Authorization: OAuth YOUR_API_KEY" \
  -d "incident[name]=Login Service Degraded" \
  -d "incident[status]=investigating" \
  -d "incident[body]=We are investigating reports of login failures"
```

---

### **4. MITIGATION (20-120 min)**

#### **A. Quick Health Checks**
```bash
# 1. Check all services are running
docker-compose ps

# 2. Check health endpoints
curl http://localhost:8000/health/ready/ | jq

# 3. Check database connectivity
docker-compose exec postgres psql -U erp -d himalytix -c "SELECT 1;"

# 4. Check Redis
docker-compose exec redis redis-cli -a changeme PING

# 5. Check Celery workers
docker-compose exec celery celery -A dashboard inspect active

# 6. View recent logs
docker-compose logs --tail=100 -f web
```

---

#### **B. Common Mitigation Steps**

**Scenario 1: High Memory Usage**
```bash
# Check container memory
docker stats --no-stream

# Restart web service if OOM
docker-compose restart web

# Scale horizontally (if docker-compose v3.9+)
docker-compose up -d --scale web=3
```

**Scenario 2: Database Connection Pool Exhausted**
```python
# Django shell - kill idle connections
from django.db import connections
for conn in connections.all():
    conn.close()

# PostgreSQL - check active connections
docker-compose exec postgres psql -U erp -d himalytix -c \
  "SELECT count(*) FROM pg_stat_activity WHERE state = 'active';"

# Kill long-running queries (>5 min)
docker-compose exec postgres psql -U erp -d himalytix -c \
  "SELECT pg_terminate_backend(pid) FROM pg_stat_activity 
   WHERE state = 'active' AND query_start < NOW() - INTERVAL '5 minutes';"
```

**Scenario 3: Disk Space Full**
```bash
# Check disk usage
df -h

# Clean Docker logs
docker system prune -a --volumes -f

# Rotate application logs
find /app/logs -name "*.log" -mtime +7 -delete

# Remove old media files (if safe)
find /app/media/temp -type f -mtime +30 -delete
```

**Scenario 4: Redis Memory Exceeded**
```bash
# Check Redis memory usage
docker-compose exec redis redis-cli -a changeme INFO memory

# Clear cache (if safe)
docker-compose exec redis redis-cli -a changeme FLUSHDB

# Restart Redis
docker-compose restart redis
```

---

### **5. RESOLUTION (Variable)**

**Verify Service Restored:**
```bash
# Run smoke tests
curl -f http://localhost:8000/health/ready/ || echo "FAILED"
curl -f http://localhost:8000/accounts/login/ || echo "FAILED"
curl -f http://localhost:8000/api/v1/health/ || echo "FAILED"

# Check error rate in Prometheus
curl 'http://localhost:9090/api/v1/query?query=rate(django_http_requests_total_by_view_transport_method_total{status=~"5.."}[5m])'

# Load test (if available)
ab -n 100 -c 10 http://localhost:8000/
```

**Update Stakeholders:**
```markdown
# Slack Resolution Message
✅ **INCIDENT RESOLVED** ✅
**Severity:** P0 - Critical
**Status:** Resolved
**Root Cause:** PostgreSQL connection pool exhausted (max_connections=100)
**Resolution:** Restarted web service, increased pool size to 200
**Duration:** 47 minutes (14:35 - 15:22 UTC)
**Affected Users:** ~120 concurrent sessions

**Action Items:**
- [ ] Schedule postmortem (2024-01-16 10:00 UTC)
- [ ] Update connection pool config in production
- [ ] Add connection pool monitoring alert
```

---

### **6. POSTMORTEM (Within 5 days)**

**Schedule Meeting:**
- **Attendees:** Incident responders, engineering leads, product manager
- **Duration:** 60 minutes
- **Agenda:** Timeline review, root cause analysis, action items

**Use Template Below ⬇️**

---

## 🔍 Alert Triage

### **High CPU Alert (>80% for 5 min)**
```bash
# Identify process consuming CPU
docker stats --no-stream
top -b -n 1 | head -20

# Check for runaway Celery tasks
docker-compose exec celery celery -A dashboard inspect active

# Rollback recent deployment if spike coincides
git log --oneline -10
docker-compose exec web git rev-parse HEAD
```

---

### **High Error Rate Alert (>5% requests)**
```bash
# Check error logs
docker-compose logs web | grep -i "error" | tail -50

# Group errors by type
docker-compose logs web --since 30m | grep "ERROR" | awk '{print $NF}' | sort | uniq -c

# Check Sentry (if integrated)
curl "https://sentry.io/api/0/projects/YOUR_ORG/YOUR_PROJECT/issues/?statsPeriod=1h" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

### **Slow Query Alert (>1s avg)**
```sql
-- Find slow queries in PostgreSQL
SELECT pid, now() - pg_stat_activity.query_start AS duration, query
FROM pg_stat_activity
WHERE (now() - pg_stat_activity.query_start) > interval '1 second'
ORDER BY duration DESC;

-- Terminate specific query
SELECT pg_terminate_backend(PID_HERE);
```

---

### **Health Check Failure**
```bash
# Check specific health endpoint
curl -v http://localhost:8000/health/ready/

# Component-wise checks
docker-compose exec web python manage.py check --deploy
docker-compose exec postgres pg_isready -U erp
docker-compose exec redis redis-cli -a changeme PING
```

---

## 🛠️ Common Incidents

### **Incident 1: Database Migration Failure**

**Symptoms:**
- 500 errors on all pages
- Logs: `django.db.utils.ProgrammingError: relation "table_name" does not exist`

**Resolution:**
```bash
# 1. Check migration status
docker-compose exec web python manage.py showmigrations

# 2. Attempt to re-run migrations
docker-compose exec web python manage.py migrate

# 3. If stuck, fake problematic migration
docker-compose exec web python manage.py migrate --fake app_name migration_name

# 4. Restore from backup if data corruption
# See: docs/runbooks/backup-restore.md
```

---

### **Incident 2: Celery Task Queue Backlog**

**Symptoms:**
- Delayed email notifications
- Reports not generating
- Logs: `Too many pending tasks (5000+)`

**Resolution:**
```bash
# 1. Check queue length
docker-compose exec redis redis-cli -a changeme LLEN celery

# 2. Purge failed tasks
docker-compose exec celery celery -A dashboard purge

# 3. Scale workers
docker-compose up -d --scale celery=4

# 4. Identify stuck tasks
docker-compose exec celery celery -A dashboard inspect active
```

---

### **Incident 3: HTTPS Certificate Expired**

**Symptoms:**
- Browser warnings: "Your connection is not private"
- API clients failing with SSL errors

**Resolution:**
```bash
# 1. Check certificate expiry
openssl s_client -connect himalytix.com:443 -servername himalytix.com < /dev/null 2>/dev/null | \
  openssl x509 -noout -dates

# 2. Renew Let's Encrypt certificate
certbot renew --force-renewal

# 3. Reload web server
docker-compose restart web

# 4. Verify
curl -vI https://himalytix.com
```

---

## 📞 Escalation Paths

| Issue Type | Level 1 | Level 2 | Level 3 |
|------------|---------|---------|---------|
| **Database** | On-call Engineer | Database Admin | CTO |
| **Infrastructure** | DevOps Lead | Cloud Provider Support | CTO |
| **Application** | Backend Lead | Engineering Manager | CTO |
| **Security** | Security Lead | CISO | CEO |

**Contact Methods:**
1. Slack: @oncall (fastest)
2. PagerDuty: Automatic escalation
3. Phone: Emergency contact list (stored in 1Password)

---

## 📝 Postmortem Template

**Copy this to a new Markdown file after each P0/P1 incident:**

```markdown
# Postmortem: [Incident Title]

**Date:** 2024-01-15  
**Author:** John Doe  
**Severity:** P0 - Critical  
**Duration:** 47 minutes (14:35 - 15:22 UTC)

---

## Summary
One-paragraph description of the incident.

---

## Timeline (All times UTC)
| Time | Event |
|------|-------|
| 14:35 | Alert triggered: High error rate on /accounts/login/ |
| 14:37 | Incident declared (P0), responder assigned |
| 14:40 | Investigation started - checked logs, health endpoints |
| 14:50 | Root cause identified - PostgreSQL max_connections reached |
| 15:05 | Mitigation applied - restarted web service |
| 15:10 | Service restored, monitoring for stability |
| 15:22 | Incident resolved - error rate back to baseline |

---

## Root Cause
PostgreSQL connection pool exhausted due to:
1. Traffic spike (3x normal load)
2. Connection pool size too small (100 connections)
3. Connections not being released (Django bug in v5.0.1)

---

## Impact
- **Users Affected:** ~120 concurrent users
- **Duration:** 47 minutes
- **Revenue Impact:** ~$500 (estimated lost transactions)
- **Tenants Affected:** All (multi-tenant system)

---

## Resolution
1. Restarted web service (cleared stuck connections)
2. Increased `DATABASES['default']['CONN_MAX_AGE']` from 0 to 600
3. Upgraded Django to 5.0.2 (fixes connection leak)

---

## Detection
- **How detected:** Prometheus alert (error_rate > 5%)
- **Time to detect:** 2 minutes (alert triggered 14:35, traffic spike 14:33)
- **Could detection be faster?** No - alert threshold is appropriate

---

## Action Items
| Action | Owner | Due Date | Priority |
|--------|-------|----------|----------|
| Increase PostgreSQL max_connections to 200 | DevOps Lead | 2024-01-16 | P0 |
| Add connection pool monitoring alert | Backend Lead | 2024-01-18 | P1 |
| Load test staging environment weekly | QA Lead | 2024-01-22 | P2 |
| Document connection pool tuning | Tech Writer | 2024-01-25 | P3 |

---

## Lessons Learned
### What Went Well
- Alert detected issue quickly (2 min)
- Clear escalation process followed
- Mitigation applied in 15 minutes

### What Went Wrong
- No connection pool monitoring
- Didn't anticipate traffic spike (marketing campaign)
- Django version outdated (known bug)

### Where We Got Lucky
- Incident occurred during business hours (15:00 local time)
- Database snapshot taken 1 hour before incident
- No data loss or corruption

---

## Follow-up
- Share postmortem with team in #engineering Slack channel
- Add connection pool metrics to Grafana dashboard
- Schedule capacity planning review meeting
```

---

## 📊 Metrics to Track

**Incident Metrics (Monthly):**
- Total incidents by severity (P0, P1, P2, P3)
- MTTD (Mean Time To Detect)
- MTTR (Mean Time To Resolve)
- Incidents by category (database, infrastructure, application)
- Repeat incidents (same root cause)

**Example Query (Prometheus):**
```promql
# Error rate over time
rate(django_http_requests_total_by_view_transport_method_total{status=~"5.."}[5m])

# Request duration 95th percentile
histogram_quantile(0.95, rate(django_http_request_duration_seconds_bucket[5m]))
```

---

## 🔗 Related Runbooks
- [Backup & Restore](./backup-restore.md)
- [Deployment Rollback](./deployment-rollback.md)
- [Scaling Procedures](./scaling.md)

---

**Feedback:** Please send improvements to #devops-runbooks in Slack.
