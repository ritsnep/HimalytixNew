# Phase 3 Deployment Guide

**Status:** 🚀 Production Deployment Ready  
**Phase 3 Version:** 1.0  
**Deployment Date:** [Current Date]  
**Environment:** Production  

---

## 📋 Pre-Deployment Checklist

### 1. Environment Prerequisites

- [ ] Python 3.9+ installed
- [ ] Virtual environment created and activated
- [ ] All dependencies from `requirements.txt` installed
- [ ] Database server (PostgreSQL recommended for production)
- [ ] Redis server running (for caching and Celery)
- [ ] Celery worker environment ready
- [ ] Web server (Nginx/Apache) configured
- [ ] SSL certificates obtained (HTTPS)
- [ ] Domain name configured (DNS records set)

### 2. Code Readiness

- [ ] All Phase 3 tests pass: `python manage.py test`
- [ ] Code coverage at 95%+ verified
- [ ] No security warnings: `python manage.py check --deploy`
- [ ] No database migration conflicts: `python manage.py makemigrations --dry-run`
- [ ] Static files collected: `python manage.py collectstatic --noinput`
- [ ] Git repository clean (all changes committed)
- [ ] Version tag created: `git tag -a v3.0 -m "Phase 3 Release"`

### 3. Database Readiness

- [ ] Database backup created
- [ ] Database user and password configured
- [ ] Database initial tables created
- [ ] Migration plan reviewed
- [ ] Rollback strategy documented
- [ ] Database indexes verified (9 strategic indexes)
- [ ] Multi-tenant isolation tested

### 4. Security Review

- [ ] Secret key configured (not in git)
- [ ] DEBUG=False in production
- [ ] ALLOWED_HOSTS configured correctly
- [ ] CSRF protection enabled
- [ ] CORS settings restricted
- [ ] API token authentication tested
- [ ] Permission classes verified
- [ ] Organization isolation tested
- [ ] SSL/TLS configuration verified

### 5. Monitoring & Logging

- [ ] Logging configuration set up
- [ ] Error tracking (Sentry/similar) configured
- [ ] Performance monitoring enabled
- [ ] Alert thresholds defined
- [ ] Log rotation configured
- [ ] Backup strategy defined

### 6. Team Preparation

- [ ] Deployment team trained
- [ ] Rollback procedure documented
- [ ] On-call rotation established
- [ ] Communication plan ready
- [ ] Stakeholder notifications prepared
- [ ] Maintenance window scheduled

---

## 🔧 Deployment Procedures

### Phase 3.1: Pre-Deployment Verification (1-2 hours)

#### Step 1: Environment Validation
```bash
# Verify Python version
python --version  # Should be 3.9+

# Verify virtual environment
where python  # Should show venv path

# Verify key packages
pip list | findstr "Django djangorestframework celery redis"
```

#### Step 2: Database Preparation
```bash
# Create database backup
# PostgreSQL example:
pg_dump erp_production > erp_backup_$(date +%Y%m%d).sql

# For SQLite:
copy db.sqlite3 db.sqlite3.backup

# Run migrations on test database first
python manage.py migrate --database=test_db

# Verify migration plan
python manage.py migrate --plan
```

#### Step 3: Test Suite Execution
```bash
# Run all Phase 3 tests
python manage.py test accounting --verbosity=2

# Run specific test categories
python manage.py test accounting.tests.test_approval -v 2
python manage.py test accounting.tests.test_reporting -v 2
python manage.py test accounting.tests.test_import_export -v 2
python manage.py test accounting.tests.test_celery_tasks -v 2
python manage.py test accounting.tests.test_i18n -v 2
python manage.py test accounting.tests.test_api -v 2
python manage.py test accounting.tests.test_analytics -v 2

# Verify coverage
coverage run --source='accounting' manage.py test
coverage report  # Should show 95%+
```

#### Step 4: Performance Baseline Capture
```bash
# Capture baseline metrics before deployment
# Create baseline_metrics.json with:
# - Dashboard load time (target: <500ms)
# - Report generation time (target: <3s)
# - API response times (target: <200ms)
# - Cache hit rates (target: >85%)
# - Database query counts

python manage.py shell
>>> from accounting.services.analytics_service import PerformanceMetrics
>>> metrics = PerformanceMetrics()
>>> baseline = metrics.get_system_metrics()
>>> import json
>>> with open('baseline_metrics.json', 'w') as f:
...     json.dump(baseline, f, indent=2, default=str)
```

#### Step 5: Configuration Verification
```bash
# Verify critical settings
python manage.py shell
>>> from django.conf import settings
>>> print(f"DEBUG: {settings.DEBUG}")  # Should be False
>>> print(f"ALLOWED_HOSTS: {settings.ALLOWED_HOSTS}")
>>> print(f"DATABASES: {settings.DATABASES}")
>>> print(f"REDIS_URL: {settings.REDIS_URL or 'Not set'}")
>>> print(f"EMAIL_BACKEND: {settings.EMAIL_BACKEND}")
```

### Phase 3.2: Production Deployment (2-4 hours)

#### Step 1: Database Migration
```bash
# Run migrations (ensure database is backed up first!)
python manage.py migrate --noinput

# Verify migration success
python manage.py migrate --plan  # Should show no pending migrations

# Verify data integrity
python manage.py shell
>>> from accounting.models import Account, Journal, Organization
>>> print(f"Organizations: {Organization.objects.count()}")
>>> print(f"Accounts: {Account.objects.count()}")
>>> print(f"Journals: {Journal.objects.count()}")
```

#### Step 2: Static Files and Assets
```bash
# Collect static files
python manage.py collectstatic --noinput --clear

# Verify static files
# Check that static/ directory contains all CSS, JS, images
dir static/  # or ls -la static/
```

#### Step 3: Cache Initialization
```bash
# Clear cache and reinitialize
python manage.py shell
>>> from django.core.cache import cache
>>> cache.clear()
>>> print("Cache cleared and ready")

# Verify Redis connection
>>> import redis
>>> r = redis.Redis.from_url('redis://localhost:6379/0')
>>> r.ping()  # Should return True
```

#### Step 4: Service Startup

##### Web Server (Django/Gunicorn)
```bash
# Start Gunicorn (example with 4 workers)
gunicorn ERP.wsgi:application --bind 0.0.0.0:8000 --workers 4 --timeout 120

# Or with systemd (create erp-web.service)
[Unit]
Description=ERP Web Service
After=network.target

[Service]
User=www-data
WorkingDirectory=/var/www/erp
ExecStart=/usr/bin/gunicorn ERP.wsgi:application --bind 0.0.0.0:8000 --workers 4
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

##### Celery Worker
```bash
# Start Celery worker
celery -A ERP worker --loglevel=info --concurrency=4

# Or with systemd (create erp-celery.service)
[Unit]
Description=ERP Celery Worker
After=network.target redis.service

[Service]
User=www-data
WorkingDirectory=/var/www/erp
ExecStart=/usr/bin/celery -A ERP worker --loglevel=info --concurrency=4
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

##### Celery Beat (Scheduler)
```bash
# Start Celery Beat
celery -A ERP beat --loglevel=info

# Or with systemd (create erp-celery-beat.service)
[Unit]
Description=ERP Celery Beat
After=network.target redis.service

[Service]
User=www-data
WorkingDirectory=/var/www/erp
ExecStart=/usr/bin/celery -A ERP beat --loglevel=info
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

##### Nginx Configuration
```nginx
upstream erp_app {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name your-domain.com;
    
    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    ssl_certificate /etc/ssl/certs/your-domain.crt;
    ssl_certificate_key /etc/ssl/private/your-domain.key;
    
    client_max_body_size 100M;  # For file uploads
    
    location / {
        proxy_pass http://erp_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }
    
    location /static/ {
        alias /var/www/erp/static/;
        expires 30d;
    }
    
    location /media/ {
        alias /var/www/erp/media/;
        expires 7d;
    }
}
```

#### Step 5: Service Health Check
```bash
# Verify all services are running
ps aux | grep celery
ps aux | grep gunicorn
ps aux | grep redis

# Check service logs
tail -f /var/log/erp/django.log
tail -f /var/log/celery/worker.log
tail -f /var/log/celery/beat.log
```

### Phase 3.3: Post-Deployment Verification (1-2 hours)

#### Step 1: Web Application Tests
```bash
# Test main endpoints
curl https://your-domain.com/
curl https://your-domain.com/login/
curl https://your-domain.com/dashboard/

# Expected: 200 OK responses
```

#### Step 2: API Endpoint Verification
```bash
# Obtain API token
curl -X POST https://your-domain.com/api/v1/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"password"}'

# Store token: export TOKEN="your-token-here"

# Test API endpoints
curl -H "Authorization: Token $TOKEN" \
  https://your-domain.com/api/v1/accounts/

curl -H "Authorization: Token $TOKEN" \
  https://your-domain.com/api/v1/journals/

curl -H "Authorization: Token $TOKEN" \
  https://your-domain.com/api/v1/trial-balance/

# Expected: 200 OK with JSON response
```

#### Step 3: Database Integrity Check
```bash
# Verify data consistency
python manage.py shell
>>> from accounting.models import Account, Journal, JournalLine
>>> from django.db.models import Sum
>>> 
>>> # Verify all journals are balanced
>>> for journal in Journal.objects.all():
...     if not journal.is_balanced():
...         print(f"Unbalanced journal: {journal.id}")
>>> 
>>> # Count all records
>>> print(f"Accounts: {Account.objects.count()}")
>>> print(f"Journals: {Journal.objects.count()}")
>>> print(f"Journal Lines: {JournalLine.objects.count()}")
```

#### Step 4: Cache Functionality Test
```bash
# Test cache operations
python manage.py shell
>>> from django.core.cache import cache
>>> cache.set('test_key', 'test_value', 300)
>>> value = cache.get('test_key')
>>> print(f"Cache test: {value}")  # Should print 'test_value'
>>> cache.delete('test_key')
```

#### Step 5: Celery Task Testing
```bash
# Test Celery task execution
python manage.py shell
>>> from accounting.celery_tasks import generate_trial_balance_report
>>> result = generate_trial_balance_report.delay(
...     organization_id=1,
...     as_of_date='2024-01-01'
... )
>>> print(f"Task ID: {result.id}")
>>> print(f"Task status: {result.status}")

# Monitor task in Celery
celery -A ERP inspect active  # Show active tasks
celery -A ERP inspect reserved  # Show reserved tasks
```

#### Step 6: i18n Functionality Test
```bash
# Test internationalization
python manage.py shell
>>> from django.utils.translation import activate
>>> activate('ar')  # Arabic
>>> from django.utils.translation import gettext as _
>>> print(_('Welcome'))  # Should print in Arabic if translation exists
>>> activate('en')  # Reset to English
```

#### Step 7: Analytics Dashboard Test
```bash
# Verify analytics views
# Navigate to: https://your-domain.com/analytics/dashboard/
# Expected: Dashboard loads with KPI cards
# Verify charts load without JavaScript errors
# Verify all 8 dashboard views accessible:
# - /analytics/dashboard/
# - /analytics/financial/
# - /analytics/cash-flow/
# - /analytics/account/
# - /analytics/trends/
# - /analytics/performance/
# - /analytics/data/ (AJAX endpoint)
# - /analytics/export/ (CSV/JSON)
```

#### Step 8: Approval Workflow Test
```bash
# Test approval workflow (if applicable)
# Create a test journal in approval-required state
# Navigate to approval queue
# Expected: Workflow appears in approval pending status
# Can approve/reject with comments
```

#### Step 9: Performance Baseline Comparison
```bash
# Capture post-deployment metrics
python manage.py shell
>>> from accounting.services.analytics_service import PerformanceMetrics
>>> metrics = PerformanceMetrics()
>>> current = metrics.get_system_metrics()
>>> 
>>> # Compare with baseline_metrics.json
>>> # Dashboard load: should be <500ms
>>> # Reports: should be <3s
>>> # API: should be <200ms
>>> print(f"Current metrics: {current}")
```

#### Step 10: User Access Testing
```bash
# Test with different user roles
# - Test with Organization Admin
# - Test with Accounting Manager
# - Test with Regular User
# 
# Expected: Each role sees appropriate data
# Multi-tenant isolation verified
# Permissions enforced correctly
```

---

## 🔄 Rollback Procedures

### Quick Rollback (< 30 minutes)

If critical issues are discovered:

#### Step 1: Stop Services
```bash
# Stop web service
systemctl stop erp-web.service

# Stop Celery
systemctl stop erp-celery.service
systemctl stop erp-celery-beat.service
```

#### Step 2: Restore Database
```bash
# For PostgreSQL
psql erp_production < erp_backup_20240115.sql

# For SQLite
copy db.sqlite3.backup db.sqlite3

# Verify restoration
python manage.py migrate
```

#### Step 3: Restart Services with Previous Version
```bash
# Checkout previous Git version
git checkout v2.9  # or previous stable version

# Reinstall dependencies
pip install -r requirements.txt

# Restart services
systemctl start erp-web.service
systemctl start erp-celery.service
systemctl start erp-celery-beat.service
```

#### Step 4: Verification
```bash
# Verify services running
ps aux | grep gunicorn
ps aux | grep celery

# Test key endpoints
curl https://your-domain.com/dashboard/
```

### Full Rollback (> 30 minutes)

For major issues requiring investigation:

1. Stop all services
2. Restore database from backup
3. Restore code from previous Git tag
4. Clear caches
5. Run migrations
6. Restart services one-by-one
7. Test each component
8. Document issue and resolution

---

## 📊 Post-Deployment Monitoring

### Day 1 Monitoring (Continuous)

Monitor every 30 minutes:
- Web server response times
- Database connection pool
- Cache hit rates
- Celery task execution times
- Error log entries
- User access patterns

### Week 1 Monitoring

Monitor daily:
- Peak traffic response times
- Database query performance
- Memory usage
- Storage usage
- Error rates
- User feedback

### Ongoing Monitoring

Monitor weekly:
- Performance trends
- Error patterns
- User growth
- Data growth
- Cache effectiveness
- Task execution reliability

### Key Metrics to Track

```python
# Performance Metrics
- Dashboard load time: Target <500ms
- Report generation: Target <3s
- API response times: Target <200ms
- Page load time: Target <2s
- Cache hit rate: Target >85%

# System Metrics
- CPU usage: Alert if >70%
- Memory usage: Alert if >80%
- Disk usage: Alert if >85%
- Database connections: Alert if >90%
- Queue depth (Celery): Alert if >100

# Application Metrics
- Error rate: Alert if >0.1%
- Failed tasks: Alert if any
- API errors: Alert if >0.5%
- Login failures: Alert if spike
- Permission violations: Alert if any
```

### Logging Strategy

```python
# Django logging configuration (settings.py)
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/var/log/erp/django.log',
            'maxBytes': 1024*1024*10,  # 10MB
            'backupCount': 10,
        },
        'error_file': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/var/log/erp/errors.log',
            'maxBytes': 1024*1024*10,
            'backupCount': 10,
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True,
        },
        'django.request': {
            'handlers': ['error_file'],
            'level': 'ERROR',
            'propagate': False,
        },
    },
}
```

---

## 📞 Support & Escalation

### Escalation Matrix

| Issue | Priority | Response Time | Owner |
|-------|----------|----------------|-------|
| System down | Critical | 15 minutes | DevOps Lead |
| API errors >1% | High | 30 minutes | Backend Lead |
| Performance degradation | High | 30 minutes | Infrastructure |
| Database warnings | Medium | 1 hour | DBA |
| Non-critical errors | Low | 4 hours | Support |

### Support Contacts

- **On-Call Engineer:** [Contact Info]
- **DevOps Lead:** [Contact Info]
- **Database Admin:** [Contact Info]
- **Application Lead:** [Contact Info]

### Documentation References

- Phase 3 Completion: `PHASE_3_COMPLETION_SUMMARY.md`
- Task 7 (API): `PHASE_3_TASK_7_COMPLETION.md`
- Task 8 (Analytics): `PHASE_3_TASK_8_COMPLETION.md`
- All other tasks: `PHASE_3_TASK_*_COMPLETION.md`

---

## ✅ Deployment Sign-Off

**Deployment Team Sign-Off:**

- [ ] DevOps Engineer: _________________ Date: _______
- [ ] Database Admin: __________________ Date: _______
- [ ] Application Lead: ________________ Date: _______
- [ ] Product Manager: ________________ Date: _______

**Post-Deployment Verification:** 

- [ ] All tests passed
- [ ] Performance baseline established
- [ ] No critical errors in logs
- [ ] User acceptance verified
- [ ] Monitoring alerts configured
- [ ] Rollback procedure tested

**Deployment Status:** 🚀 **READY FOR PRODUCTION**

---

## 📚 Related Documentation

- **Phase 3 Summary:** `PHASE_3_COMPLETION_SUMMARY.md`
- **REST API Guide:** `PHASE_3_TASK_7_COMPLETION.md`
- **Analytics Guide:** `PHASE_3_TASK_8_COMPLETION.md`
- **Architecture Overview:** `architecture_overview.md`
- **Requirements:** `requirements.txt`
- **Changelog:** `CHANGELOG.md`

---

**Last Updated:** [Current Date]  
**Version:** 3.0  
**Status:** ✅ Production Ready for Deployment
