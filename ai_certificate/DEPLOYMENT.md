# Deployment Guide - AI Certificate Analyzer

Production deployment guide for various environments.

## Deployment Options

1. **Docker Compose** (Recommended for quick deployment)
2. **Kubernetes** (For large-scale production)
3. **Traditional Server** (VM or bare metal)
4. **Cloud Platforms** (AWS, Azure, GCP)

## Docker Compose Deployment

### Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- 8GB RAM minimum

### Quick Deploy

```bash
# Clone repository
git clone <repository-url>
cd ai_certificate

# Configure environment
cp .env.example .env
# Edit .env with production settings

# Start services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f api
```

### Services

The docker-compose setup includes:

1. **API Service** (port 8001)
   - Main application
   - 4 workers
   - 8GB memory limit
   - Auto-restart enabled

2. **Redis** (port 6379)
   - Cache layer
   - Persistent storage
   - 1GB memory limit

3. **Grafana** (port 3000)
   - Monitoring dashboard
   - Default credentials: admin/admin

4. **Synthetic Generator**
   - Background data generation
   - On-demand execution

### Production Configuration

Edit `docker-compose.yml` for production:

```yaml
services:
  api:
    environment:
      - DEBUG=false
      - LOG_LEVEL=WARNING
      - WORKERS=8
      - ALLOWED_ORIGINS=https://yourdomain.com
    deploy:
      resources:
        limits:
          memory: 16G
        reservations:
          memory: 8G
```

## Kubernetes Deployment

### Prerequisites

- Kubernetes cluster 1.24+
- kubectl configured
- Helm 3.0+ (optional)

### Deployment Files

Create `k8s/` directory with:


**deployment.yaml:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: certanalyzer-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: certanalyzer
  template:
    metadata:
      labels:
        app: certanalyzer
    spec:
      containers:
      - name: api
        image: certanalyzer:latest
        ports:
        - containerPort: 8001
        env:
        - name: REDIS_URL
          value: redis://redis-service:6379/0
        - name: USE_ML
          value: "true"
        resources:
          requests:
            memory: "4Gi"
            cpu: "2"
          limits:
            memory: "8Gi"
            cpu: "4"
        livenessProbe:
          httpGet:
            path: /api/v1/health
            port: 8001
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /api/v1/health
            port: 8001
          initialDelaySeconds: 10
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: certanalyzer-service
spec:
  selector:
    app: certanalyzer
  ports:
  - port: 80
    targetPort: 8001
  type: LoadBalancer
```

**redis.yaml:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
      - name: redis
        image: redis:7-alpine
        ports:
        - containerPort: 6379
        volumeMounts:
        - name: redis-storage
          mountPath: /data
      volumes:
      - name: redis-storage
        persistentVolumeClaim:
          claimName: redis-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: redis-service
spec:
  selector:
    app: redis
  ports:
  - port: 6379
    targetPort: 6379
```

### Deploy to Kubernetes

```bash
# Create namespace
kubectl create namespace certanalyzer

# Apply configurations
kubectl apply -f k8s/ -n certanalyzer

# Check status
kubectl get pods -n certanalyzer
kubectl get services -n certanalyzer

# View logs
kubectl logs -f deployment/certanalyzer-api -n certanalyzer
```

## AWS Deployment

### EC2 Deployment

**1. Launch EC2 Instance**
- Instance type: t3.xlarge (4 vCPU, 16GB RAM)
- OS: Ubuntu 22.04 LTS
- Storage: 50GB SSD
- Security group: Allow ports 22, 80, 443, 8001

**2. Install Dependencies**
```bash
# Connect to instance
ssh -i key.pem ubuntu@<instance-ip>

# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y python3.10 python3-pip redis-server tesseract-ocr \
  tesseract-ocr-eng tesseract-ocr-amh nginx

# Clone and setup
git clone <repository-url> /home/ubuntu/certanalyzer
cd /home/ubuntu/certanalyzer
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**3. Configure Systemd**
```bash
sudo cp deployment/certanalyzer.service /etc/systemd/system/
sudo systemctl enable certanalyzer
sudo systemctl start certanalyzer
```

**4. Configure Nginx**
```bash
sudo cp deployment/nginx.conf /etc/nginx/sites-available/certanalyzer
sudo ln -s /etc/nginx/sites-available/certanalyzer /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### ECS Deployment

**1. Create ECR Repository**
```bash
aws ecr create-repository --repository-name certanalyzer
```

**2. Build and Push Image**
```bash
# Login to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

# Build image
docker build -t certanalyzer:latest .

# Tag image
docker tag certanalyzer:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/certanalyzer:latest

# Push image
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/certanalyzer:latest
```

**3. Create ECS Task Definition**
```json
{
  "family": "certanalyzer",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "2048",
  "memory": "8192",
  "containerDefinitions": [
    {
      "name": "api",
      "image": "<account-id>.dkr.ecr.us-east-1.amazonaws.com/certanalyzer:latest",
      "portMappings": [
        {
          "containerPort": 8001,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {"name": "REDIS_URL", "value": "redis://redis-endpoint:6379/0"},
        {"name": "USE_ML", "value": "true"}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/certanalyzer",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "api"
        }
      }
    }
  ]
}
```

## Azure Deployment

### Azure Container Instances

```bash
# Create resource group
az group create --name certanalyzer-rg --location eastus

# Create container
az container create \
  --resource-group certanalyzer-rg \
  --name certanalyzer-api \
  --image certanalyzer:latest \
  --cpu 4 \
  --memory 8 \
  --ports 8001 \
  --environment-variables \
    REDIS_URL=redis://redis-host:6379/0 \
    USE_ML=true
```

### Azure Kubernetes Service (AKS)

```bash
# Create AKS cluster
az aks create \
  --resource-group certanalyzer-rg \
  --name certanalyzer-cluster \
  --node-count 3 \
  --node-vm-size Standard_D4s_v3 \
  --enable-managed-identity

# Get credentials
az aks get-credentials --resource-group certanalyzer-rg --name certanalyzer-cluster

# Deploy
kubectl apply -f k8s/
```

## GCP Deployment

### Cloud Run

```bash
# Build and push to GCR
gcloud builds submit --tag gcr.io/PROJECT_ID/certanalyzer

# Deploy to Cloud Run
gcloud run deploy certanalyzer \
  --image gcr.io/PROJECT_ID/certanalyzer \
  --platform managed \
  --region us-central1 \
  --memory 8Gi \
  --cpu 4 \
  --set-env-vars REDIS_URL=redis://redis-host:6379/0,USE_ML=true
```

### GKE Deployment

```bash
# Create GKE cluster
gcloud container clusters create certanalyzer-cluster \
  --num-nodes 3 \
  --machine-type n1-standard-4 \
  --region us-central1

# Deploy
kubectl apply -f k8s/
```

## Monitoring Setup

### Prometheus

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'certanalyzer'
    static_configs:
      - targets: ['localhost:8001']
    metrics_path: '/metrics'
```

### Grafana Dashboards

Import pre-built dashboard:
```bash
# Copy dashboard JSON
cp monitoring/dashboards/certanalyzer.json /var/lib/grafana/dashboards/
```

## Backup Strategy

### Automated Backups

```bash
# Create backup script
cat > /usr/local/bin/backup-certanalyzer.sh << 'EOF'
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR=/backup/certanalyzer

# Backup Redis
redis-cli SAVE
cp /var/lib/redis/dump.rdb $BACKUP_DIR/redis-$DATE.rdb

# Backup models
tar -czf $BACKUP_DIR/models-$DATE.tar.gz models/

# Cleanup old backups (keep 7 days)
find $BACKUP_DIR -mtime +7 -delete
EOF

chmod +x /usr/local/bin/backup-certanalyzer.sh

# Add to crontab
echo "0 2 * * * /usr/local/bin/backup-certanalyzer.sh" | crontab -
```

## SSL/TLS Configuration

### Let's Encrypt (Certbot)

```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d your-domain.com

# Auto-renewal
sudo certbot renew --dry-run
```

### Manual Certificate

```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    location / {
        proxy_pass http://localhost:8001;
    }
}
```

## Health Checks

### Application Health

```bash
# Basic health
curl http://localhost:8001/api/v1/health

# Performance health
curl http://localhost:8001/health/performance
```

### Automated Monitoring

```bash
# Create health check script
cat > /usr/local/bin/health-check.sh << 'EOF'
#!/bin/bash
HEALTH=$(curl -s http://localhost:8001/api/v1/health | jq -r '.status')
if [ "$HEALTH" != "healthy" ]; then
    echo "Service unhealthy, restarting..."
    systemctl restart certanalyzer
fi
EOF

chmod +x /usr/local/bin/health-check.sh

# Run every 5 minutes
echo "*/5 * * * * /usr/local/bin/health-check.sh" | crontab -
```

## Rollback Procedures

### Docker Compose

```bash
# Stop current version
docker-compose down

# Checkout previous version
git checkout <previous-tag>

# Rebuild and start
docker-compose up -d --build
```

### Kubernetes

```bash
# Rollback deployment
kubectl rollout undo deployment/certanalyzer-api -n certanalyzer

# Check rollout status
kubectl rollout status deployment/certanalyzer-api -n certanalyzer
```

## Performance Tuning

### For High Traffic

```bash
# Increase workers
WORKERS=8

# Increase Redis memory
maxmemory 4gb

# Use connection pooling
REDIS_MAX_CONNECTIONS=50
```

### For Low Memory

```bash
# Reduce workers
WORKERS=2
MAX_WORKERS=2

# Reduce batch size
BATCH_SIZE=10

# Disable ML
USE_ML=false
```

## Security Hardening

### 1. Firewall Configuration

```bash
# UFW (Ubuntu)
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

### 2. Redis Security

```bash
# Edit /etc/redis/redis.conf
bind 127.0.0.1
requirepass <strong-password>
rename-command CONFIG ""
rename-command FLUSHALL ""
```

### 3. Application Security

```bash
# Set secure environment variables
API_KEY=<generate-strong-key>
ALLOWED_ORIGINS=https://yourdomain.com
DEBUG=false
```

## Maintenance

### Regular Tasks

**Daily:**
- Check logs for errors
- Monitor disk space
- Review performance metrics

**Weekly:**
- Update dependencies
- Review security advisories
- Backup verification

**Monthly:**
- Update system packages
- Review and optimize cache
- Performance analysis

### Update Procedure

```bash
# 1. Backup current state
./backup-certanalyzer.sh

# 2. Pull latest changes
git pull origin main

# 3. Update dependencies
pip install -r requirements.txt --upgrade

# 4. Run migrations (if any)
# alembic upgrade head

# 5. Restart service
sudo systemctl restart certanalyzer

# 6. Verify health
curl http://localhost:8001/api/v1/health
```

---

**Deployment Guide Version**: 1.0  
**Last Updated**: March 2024
