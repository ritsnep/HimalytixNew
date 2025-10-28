# 📈 Scaling Runbook

**Version:** 1.0  
**Owner:** DevOps Team  
**Last Updated:** 2024-01-15

---

## 📋 Table of Contents
1. [Overview](#overview)
2. [Scaling Indicators](#scaling-indicators)
3. [Horizontal Scaling](#horizontal-scaling)
4. [Vertical Scaling](#vertical-scaling)
5. [Database Scaling](#database-scaling)
6. [Load Testing](#load-testing)
7. [Cost Optimization](#cost-optimization)

---

## 🎯 Overview

This runbook covers scaling procedures for Himalytix ERP. Use when:
- Traffic exceeds current capacity
- Response times degrade (>1s p95)
- Database queries slow down (>500ms avg)
- Celery queue backlog grows (>1000 tasks)

**Scaling Targets:**
- **Response Time:** p95 <1s, p99 <3s
- **Throughput:** 1000 req/sec per web instance
- **Database:** <100ms query time (p95)
- **Queue:** <500 pending tasks

---

## 🚦 Scaling Indicators

### **When to Scale UP (Add Resources)**

| Metric | Threshold | Action |
|--------|-----------|--------|
| **CPU Usage** | >80% sustained for 5 min | Add web instances |
| **Memory Usage** | >85% | Increase instance size |
| **Database Connections** | >80% of max | Scale DB or add read replicas |
| **Queue Length** | >1000 tasks | Add Celery workers |
| **Response Time (p95)** | >1s | Add web instances + caching |
| **Error Rate** | >2% | Investigate, then scale if needed |

### **When to Scale DOWN (Save Costs)**

| Metric | Threshold | Action |
|--------|-----------|--------|
| **CPU Usage** | <30% for 24 hours | Remove web instances |
| **Memory Usage** | <40% | Downgrade instance size |
| **Queue Length** | <100 tasks | Remove Celery workers |
| **Traffic** | <50% of capacity | Scale down (weekends, nights) |

---

## 🔄 Horizontal Scaling

### **Scaling Web Instances (Docker Compose)**

**Add Web Instances:**
```bash
# Current state
docker-compose ps web

# Scale to 4 instances
docker-compose up -d --scale web=4

# Verify
docker-compose ps web

# Check load balancer (if using nginx)
curl http://localhost/health/ -I
```

**Configure Load Balancer (Nginx):**
```nginx
# /etc/nginx/sites-available/himalytix.conf
upstream web_backend {
    least_conn;  # Use least connections algorithm
    server web1:8000 max_fails=3 fail_timeout=30s;
    server web2:8000 max_fails=3 fail_timeout=30s;
    server web3:8000 max_fails=3 fail_timeout=30s;
    server web4:8000 max_fails=3 fail_timeout=30s;
}

server {
    listen 80;
    server_name himalytix.com;

    location / {
        proxy_pass http://web_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

**Reload Nginx:**
```bash
sudo nginx -t  # Test config
sudo systemctl reload nginx
```

---

### **Scaling Celery Workers**

**Add Workers:**
```bash
# Scale to 6 workers
docker-compose up -d --scale celery=6

# Check worker status
docker-compose exec celery celery -A dashboard inspect active

# Monitor queue length
docker-compose exec redis redis-cli -a changeme LLEN celery
```

**Configure Worker Concurrency:**
```yaml
# docker-compose.yml
celery:
  command: celery -A dashboard worker --loglevel=info --concurrency=8
  # Concurrency = CPU cores * 2 (for I/O-bound tasks)
```

---

### **Auto-Scaling (Kubernetes Example)**

**HorizontalPodAutoscaler (HPA):**
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: web-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: web
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

**Apply:**
```bash
kubectl apply -f k8s/hpa.yaml
kubectl get hpa web-hpa --watch
```

---

## 📏 Vertical Scaling

### **Increase Web Instance Size**

**AWS EC2 Example:**
```bash
# 1. Stop instance
aws ec2 stop-instances --instance-ids i-1234567890abcdef0

# 2. Change instance type (t3.medium → t3.large)
aws ec2 modify-instance-attribute \
  --instance-id i-1234567890abcdef0 \
  --instance-type t3.large

# 3. Start instance
aws ec2 start-instances --instance-ids i-1234567890abcdef0

# 4. Verify
ssh user@instance-ip
lscpu  # Check CPU cores
free -h  # Check memory
```

**Docker Resource Limits:**
```yaml
# docker-compose.yml
web:
  deploy:
    resources:
      limits:
        cpus: '4.0'      # Increased from 2.0
        memory: 8G       # Increased from 4G
      reservations:
        cpus: '2.0'
        memory: 4G
```

---

### **Increase Gunicorn Workers**

**Calculate Optimal Workers:**
```python
# Formula: (2 * CPU_CORES) + 1
import multiprocessing
workers = (2 * multiprocessing.cpu_count()) + 1
print(f"Recommended workers: {workers}")
```

**Update Configuration:**
```bash
# docker-compose.yml
web:
  command: >
    gunicorn dashboard.wsgi:application 
    --bind 0.0.0.0:8000 
    --workers 9               # Increased from 4
    --worker-class gevent     # Use async workers
    --worker-connections 1000
    --timeout 120
    --max-requests 1000       # Restart workers after 1k requests
    --max-requests-jitter 50
```

---

## 🗄️ Database Scaling

### **Strategy 1: Read Replicas**

**Setup PostgreSQL Replication:**
```bash
# 1. Enable WAL archiving on primary (postgresql.conf)
wal_level = replica
max_wal_senders = 3
wal_keep_size = 1GB

# 2. Create replication user
docker-compose exec postgres psql -U erp -d himalytix -c \
  "CREATE ROLE replicator WITH REPLICATION LOGIN PASSWORD 'secure_password';"

# 3. Configure pg_hba.conf
echo "host replication replicator replica-ip/32 md5" >> /var/lib/postgresql/data/pg_hba.conf

# 4. Restart PostgreSQL
docker-compose restart postgres

# 5. Create replica from base backup (on replica server)
pg_basebackup -h primary-ip -D /var/lib/postgresql/data -U replicator -P -v -R

# 6. Start replica
docker-compose up -d postgres-replica
```

**Django Database Routing:**
```python
# dashboard/settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'himalytix',
        'USER': 'erp',
        'PASSWORD': os.environ['POSTGRES_PASSWORD'],
        'HOST': os.environ.get('DB_PRIMARY_HOST', 'localhost'),
        'PORT': '5432',
    },
    'replica': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'himalytix',
        'USER': 'erp',
        'PASSWORD': os.environ['POSTGRES_PASSWORD'],
        'HOST': os.environ.get('DB_REPLICA_HOST', 'localhost'),
        'PORT': '5432',
    },
}

# Database router
DATABASE_ROUTERS = ['dashboard.routers.ReplicaRouter']
```

**Router Implementation:**
```python
# dashboard/routers.py
class ReplicaRouter:
    def db_for_read(self, model, **hints):
        """Send read queries to replica"""
        return 'replica'
    
    def db_for_write(self, model, **hints):
        """Send write queries to primary"""
        return 'default'
    
    def allow_relation(self, obj1, obj2, **hints):
        return True
    
    def allow_migrate(self, db, app_label, model_name=None, **hints):
        return db == 'default'  # Only migrate on primary
```

---

### **Strategy 2: Connection Pooling**

**PgBouncer Setup:**
```ini
# /etc/pgbouncer/pgbouncer.ini
[databases]
himalytix = host=postgres port=5432 dbname=himalytix

[pgbouncer]
listen_addr = 0.0.0.0
listen_port = 6432
auth_type = md5
auth_file = /etc/pgbouncer/userlist.txt
pool_mode = transaction
max_client_conn = 1000
default_pool_size = 25
reserve_pool_size = 5
reserve_pool_timeout = 3
```

**Django Configuration:**
```python
# dashboard/settings.py
DATABASES['default']['HOST'] = 'pgbouncer'
DATABASES['default']['PORT'] = '6432'
DATABASES['default']['CONN_MAX_AGE'] = 0  # Disable Django pooling
```

---

### **Strategy 3: Query Optimization**

**Identify Slow Queries:**
```sql
-- Enable pg_stat_statements extension
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Top 10 slowest queries
SELECT 
  query,
  calls,
  mean_exec_time,
  max_exec_time,
  total_exec_time
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;
```

**Common Optimizations:**
```python
# 1. Use select_related (JOIN) for foreign keys
users = User.objects.select_related('profile', 'tenant').all()

# 2. Use prefetch_related for many-to-many
tenants = Tenant.objects.prefetch_related('users', 'permissions').all()

# 3. Use only() to fetch specific fields
users = User.objects.only('id', 'email', 'username')

# 4. Use values() for dictionaries (faster)
user_data = User.objects.values('id', 'email')

# 5. Batch inserts
User.objects.bulk_create([User(...), User(...), User(...)])
```

---

## 🧪 Load Testing

### **Tool 1: Apache Bench (ab)**

**Basic Load Test:**
```bash
# 1000 requests, 100 concurrent
ab -n 1000 -c 100 http://localhost:8000/

# With authentication
ab -n 1000 -c 100 -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/users/

# POST request
ab -n 1000 -c 100 -p data.json -T application/json \
  http://localhost:8000/api/v1/journal-entries/
```

---

### **Tool 2: Locust (Python-based)**

**Install:**
```bash
pip install locust
```

**Create Test Script:**
```python
# locustfile.py
from locust import HttpUser, task, between

class WebsiteUser(HttpUser):
    wait_time = between(1, 3)
    
    def on_start(self):
        # Login
        response = self.client.post("/api/v1/auth/login/", json={
            "username": "testuser",
            "password": "testpass"
        })
        self.token = response.json()['token']
    
    @task(3)
    def view_dashboard(self):
        self.client.get("/dashboard/", headers={
            "Authorization": f"Bearer {self.token}"
        })
    
    @task(1)
    def create_journal_entry(self):
        self.client.post("/api/v1/journal-entries/", json={
            "date": "2024-01-15",
            "amount": 1000.00,
            "description": "Load test entry"
        }, headers={
            "Authorization": f"Bearer {self.token}"
        })
```

**Run Test:**
```bash
# Web UI mode
locust -f locustfile.py --host=http://localhost:8000

# Headless mode
locust -f locustfile.py --host=http://localhost:8000 \
  --users 100 --spawn-rate 10 --run-time 5m --headless
```

---

### **Tool 3: K6 (Go-based)**

**Install:**
```bash
brew install k6  # macOS
# or
choco install k6  # Windows
```

**Create Test Script:**
```javascript
// script.js
import http from 'k6/http';
import { check, sleep } from 'k6';

export let options = {
  stages: [
    { duration: '2m', target: 100 },  // Ramp-up
    { duration: '5m', target: 100 },  // Steady state
    { duration: '2m', target: 0 },    // Ramp-down
  ],
  thresholds: {
    http_req_duration: ['p(95)<1000'],  // 95% <1s
    http_req_failed: ['rate<0.01'],     // <1% errors
  },
};

export default function () {
  let response = http.get('http://localhost:8000/');
  check(response, {
    'status is 200': (r) => r.status === 200,
    'response time <500ms': (r) => r.timings.duration < 500,
  });
  sleep(1);
}
```

**Run Test:**
```bash
k6 run script.js
```

---

## 💰 Cost Optimization

### **Right-Sizing Instances**

**Monitor Resource Usage:**
```bash
# Check average CPU/memory over 7 days (Prometheus)
curl 'http://localhost:9090/api/v1/query?query=avg_over_time(container_cpu_usage_seconds_total[7d])'
curl 'http://localhost:9090/api/v1/query?query=avg_over_time(container_memory_usage_bytes[7d])'
```

**Recommendations:**
- If CPU <30% for 7 days → Downgrade instance type
- If memory <40% for 7 days → Reduce memory allocation
- If queue <100 tasks → Remove Celery workers

---

### **Auto-Scaling Schedule (Save Costs)**

**Scale Down Nights/Weekends:**
```yaml
# Kubernetes CronJob to scale down at 6 PM
apiVersion: batch/v1
kind: CronJob
metadata:
  name: scale-down
spec:
  schedule: "0 18 * * 1-5"  # 6 PM weekdays
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: kubectl
            image: bitnami/kubectl
            command:
            - /bin/sh
            - -c
            - kubectl scale deployment web --replicas=2

# Scale up at 7 AM
---
apiVersion: batch/v1
kind: CronJob
metadata:
  name: scale-up
spec:
  schedule: "0 7 * * 1-5"  # 7 AM weekdays
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: kubectl
            image: bitnami/kubectl
            command:
            - /bin/sh
            - -c
            - kubectl scale deployment web --replicas=6
```

---

### **Database Cost Optimization**

**Reduce Backup Retention:**
```bash
# Delete backups older than 30 days (S3 lifecycle policy)
aws s3api put-bucket-lifecycle-configuration --bucket himalytix-backups --lifecycle-configuration '{
  "Rules": [{
    "Id": "delete-old-backups",
    "Status": "Enabled",
    "Filter": {"Prefix": "postgres/"},
    "Expiration": {"Days": 30}
  }]
}'
```

**Archive Old Data:**
```python
# Archive journal entries older than 3 years
from accounting.models import JournalEntry
from django.utils import timezone
from datetime import timedelta

cutoff_date = timezone.now() - timedelta(days=3*365)
old_entries = JournalEntry.objects.filter(created_at__lt=cutoff_date)

# Export to CSV
import csv
with open('archived_entries.csv', 'w') as f:
    writer = csv.writer(f)
    for entry in old_entries.iterator(chunk_size=1000):
        writer.writerow([entry.id, entry.date, entry.amount, ...])

# Delete from production DB
old_entries.delete()
```

---

## 📊 Scaling Metrics

**Track these metrics during/after scaling:**

```promql
# Request throughput (req/sec)
rate(django_http_requests_total_by_view_transport_method_total[5m])

# Response time (p95)
histogram_quantile(0.95, rate(django_http_request_duration_seconds_bucket[5m]))

# Error rate
rate(django_http_requests_total_by_view_transport_method_total{status=~"5.."}[5m])

# Database connections
pg_stat_database_numbackends{datname="himalytix"}

# Celery queue length
redis_list_length{key="celery"}
```

---

## 🔗 Related Runbooks
- [Incident Response](./incident-response.md)
- [Deployment Rollback](./deployment-rollback.md)
- [Backup & Restore](./backup-restore.md)

---

**Feedback:** Suggest improvements via #devops-runbooks in Slack.
