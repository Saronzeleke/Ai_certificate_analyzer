# Setup Guide - AI Certificate Analyzer

Complete step-by-step setup instructions for development and production environments.

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Development Setup](#development-setup)
3. [Production Setup](#production-setup)
4. [Docker Setup](#docker-setup)
5. [Configuration](#configuration)
6. [Verification](#verification)
7. [Troubleshooting](#troubleshooting)

## System Requirements

### Minimum Requirements
- **OS**: Windows 10/11, Ubuntu 20.04+, macOS 11+
- **CPU**: 4 cores
- **RAM**: 8GB (16GB recommended)
- **Storage**: 10GB free space
- **Python**: 3.10 or higher
- **Redis**: 7.0 or higher
- **Tesseract OCR**: 4.0 or higher

### Recommended Requirements
- **RAM**: 16GB
- **CPU**: 8 cores
- **Storage**: 20GB SSD
- **GPU**: Optional (CUDA-compatible for faster ML inference)

## Development Setup

### Step 1: Install Python

**Windows:**
1. Download Python 3.10+ from [python.org](https://www.python.org/downloads/)
2. Run installer and check "Add Python to PATH"
3. Verify installation:
```bash
python --version
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install python3.10 python3.10-venv python3-pip
python3.10 --version
```

**macOS:**
```bash
brew install python@3.10
python3.10 --version
```

### Step 2: Install Tesseract OCR

**Windows:**
1. Download installer from [UB-Mannheim Tesseract](https://github.com/UB-Mannheim/tesseract/wiki)
2. Install to `C:\Program Files\Tesseract-OCR`
3. Add to System PATH:
   - Open System Properties → Environment Variables
   - Add `C:\Program Files\Tesseract-OCR` to PATH
4. Download Amharic language pack:
   - Download `amh.traineddata` from [tessdata](https://github.com/tesseract-ocr/tessdata)
   - Place in `C:\Program Files\Tesseract-OCR\tessdata\`
5. Verify:
```bash
tesseract --version
tesseract --list-langs
# Should show: eng, amh
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr tesseract-ocr-eng tesseract-ocr-amh
sudo apt-get install -y libgl1 libglib2.0-0 libsm6 libxext6 libxrender-dev poppler-utils

# Verify
tesseract --version
tesseract --list-langs
```

**macOS:**
```bash
brew install tesseract tesseract-lang
tesseract --version
tesseract --list-langs
```

### Step 3: Install Redis

**Windows:**

Option 1 - Using Docker (Recommended):
```bash
docker run -d --name redis -p 6379:6379 redis:7-alpine
```

Option 2 - Native Installation:
1. Download from [Redis Windows](https://github.com/microsoftarchive/redis/releases)
2. Extract and run `redis-server.exe`

**Linux:**
```bash
sudo apt-get install redis-server
sudo systemctl start redis
sudo systemctl enable redis

# Verify
redis-cli ping
# Should return: PONG
```

**macOS:**
```bash
brew install redis
brew services start redis

# Verify
redis-cli ping
```

### Step 4: Clone and Setup Project

```bash
# Clone repository
git clone <repository-url>
cd ai_certificate

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt
```

### Step 5: Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env file with your settings
# Windows users: Update TESSDATA_PATH
```

**Windows `.env` configuration:**
```bash
TESSDATA_PATH=C:\Program Files\Tesseract-OCR\tessdata
REDIS_URL=redis://localhost:6379/0
USE_ML=true
DEBUG=true
LOG_LEVEL=INFO
PORT=8001
WORKERS=2
```

**Linux/macOS `.env` configuration:**
```bash
TESSDATA_PATH=/usr/share/tesseract-ocr/4.00/tessdata
REDIS_URL=redis://localhost:6379/0
USE_ML=true
DEBUG=true
LOG_LEVEL=INFO
PORT=8001
WORKERS=4
```

### Step 6: Create Required Directories

```bash
# Create directories
mkdir -p uploads logs data/training/synthetic/images data/training/synthetic/labels
mkdir -p models/donut_certificate
```

### Step 7: Download ML Models (Optional)

The Donut model will auto-download on first use, or manually download:

```bash
# Using Python
python -c "
from transformers import VisionEncoderDecoderModel, DonutProcessor
model = VisionEncoderDecoderModel.from_pretrained('naver-clova-ix/donut-base')
processor = DonutProcessor.from_pretrained('naver-clova-ix/donut-base')
model.save_pretrained('models/donut_certificate')
processor.save_pretrained('models/donut_certificate')
"
```

### Step 8: Run the Application

```bash
# Development mode (with auto-reload)
python app/main.py

# Or using uvicorn directly
uvicorn app.main:app --host localhost --port 8001 --reload
```

The application will start at:
- API: http://localhost:8001
- Interactive API Docs: http://localhost:8001/docs
- Alternative Docs: http://localhost:8001/redoc

### Step 9: Verify Installation

```bash
# Test health endpoint
curl http://localhost:8001/api/v1/health

# Expected response:
# {
#   "status": "healthy",
#   "model_version": "2024.2.0-ai-hybrid",
#   "components": {...}
# }
```

## Production Setup

### Step 1: Production Environment Configuration

Create production `.env`:
```bash
# Application
APP_NAME=AI Certificate Analyzer
APP_VERSION=2024.2.0
DEBUG=false
LOG_LEVEL=WARNING

# Server
HOST=0.0.0.0
PORT=8001
WORKERS=4
RELOAD=false

# Redis (use password in production)
REDIS_URL=redis://:your-password@localhost:6379/0

# Security
ALLOWED_ORIGINS=https://yourdomain.com,https://api.yourdomain.com
API_KEY_HEADER=X-API-Key

# Performance
MAX_FILE_SIZE=10485760
MAX_WORKERS=4
BATCH_SIZE=25
```

### Step 2: Install System Dependencies

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y \
    python3.10 python3.10-venv python3-pip \
    tesseract-ocr tesseract-ocr-eng tesseract-ocr-amh \
    redis-server \
    libgl1 libglib2.0-0 libsm6 libxext6 libxrender-dev \
    poppler-utils \
    nginx \
    supervisor
```

### Step 3: Setup Application User

```bash
# Create dedicated user
sudo useradd -m -s /bin/bash certanalyzer
sudo su - certanalyzer

# Clone and setup
git clone <repository-url> /home/certanalyzer/app
cd /home/certanalyzer/app
python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Step 4: Configure Systemd Service

Create `/etc/systemd/system/certanalyzer.service`:

```ini
[Unit]
Description=AI Certificate Analyzer API
After=network.target redis.service

[Service]
Type=notify
User=certanalyzer
Group=certanalyzer
WorkingDirectory=/home/certanalyzer/app
Environment="PATH=/home/certanalyzer/app/venv/bin"
ExecStart=/home/certanalyzer/app/venv/bin/uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8001 \
    --workers 4 \
    --log-level warning
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable certanalyzer
sudo systemctl start certanalyzer
sudo systemctl status certanalyzer
```

### Step 5: Configure Nginx Reverse Proxy

Create `/etc/nginx/sites-available/certanalyzer`:

```nginx
upstream certanalyzer_backend {
    server localhost:8001;
}

server {
    listen 80;
    server_name your-domain.com;

    client_max_body_size 20M;

    location / {
        proxy_pass http://certanalyzer_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts for long-running analysis
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 120s;
    }

    location /docs {
        proxy_pass http://certanalyzer_backend/docs;
    }

    location /health {
        proxy_pass http://certanalyzer_backend/api/v1/health;
        access_log off;
    }
}
```

Enable site:
```bash
sudo ln -s /etc/nginx/sites-available/certanalyzer /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### Step 6: SSL/TLS Setup (Let's Encrypt)

```bash
sudo apt-get install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
sudo systemctl reload nginx
```

## Docker Setup

### Quick Start with Docker

```bash
# Build and start
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f api

# Stop
docker-compose down
```

### Custom Docker Build

```bash
# Build image
docker build -t certanalyzer:latest .

# Run container
docker run -d \
  --name certanalyzer \
  -p 8001:8001 \
  -e REDIS_URL=redis://host.docker.internal:6379/0 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/models:/app/models \
  certanalyzer:latest
```

### Docker Compose Services

The `docker-compose.yml` includes:

1. **API Service** (port 8001)
   - Main application
   - Auto-restart on failure
   - Health checks enabled
   - Memory limits: 8GB

2. **Redis Service** (port 6379)
   - Persistent storage
   - Memory limit: 1GB
   - LRU eviction policy

3. **Monitoring Service** (port 3000)
   - Grafana dashboards
   - Pre-configured datasources

4. **Synthetic Generator**
   - Background data generation
   - Runs on-demand

## Configuration

### Core Settings

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `APP_NAME` | Application name | AI Certificate Analyzer | No |
| `DEBUG` | Debug mode | false | No |
| `LOG_LEVEL` | Logging level | INFO | No |
| `HOST` | Server host | 0.0.0.0 | No |
| `PORT` | Server port | 8001 | No |
| `WORKERS` | Worker processes | 4 | No |

### OCR Settings

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `OCR_LANGUAGES` | Languages (+ separated) | eng+amh | Yes |
| `TESSDATA_PATH` | Tesseract data path | System default | Yes (Windows) |
| `USE_PADDLEOCR` | Enable PaddleOCR | false | No |

### ML Settings

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `USE_ML` | Enable ML models | true | No |
| `ML_CONFIDENCE_THRESHOLD` | ML confidence threshold | 0.6 | No |
| `DONUT_MODEL_PATH` | Donut model directory | app/models/donut_certificate | No |

### Analysis Thresholds

| Variable | Description | Default | Range |
|----------|-------------|---------|-------|
| `REJECT_THRESHOLD` | Auto-reject below this | 0.65 | 0.0-1.0 |
| `LOW_QUALITY_THRESHOLD` | Low quality flag | 0.7 | 0.0-1.0 |
| `TAMPERING_THRESHOLD` | Tampering detection | 0.75 | 0.0-1.0 |

### Performance Settings

| Variable | Description | Default | Notes |
|----------|-------------|---------|-------|
| `MAX_FILE_SIZE` | Max upload size (bytes) | 10485760 | 10MB |
| `MAX_WORKERS` | Thread pool size | 4 | Reduce for 8GB RAM |
| `BATCH_SIZE` | Batch processing size | 25 | Reduce if OOM |

## Verification

### 1. Check All Services

```bash
# Check Python
python --version

# Check Tesseract
tesseract --version
tesseract --list-langs

# Check Redis
redis-cli ping

# Check pip packages
pip list | grep -E "fastapi|torch|transformers|pytesseract"
```

### 2. Test API Endpoints

```bash
# Health check
curl http://localhost:8001/api/v1/health

# Root endpoint
curl http://localhost:8001/

# Performance metrics
curl http://localhost:8001/health/performance
```

### 3. Test Certificate Analysis

Create a test certificate image or use sample:

```bash
# Test with file upload
curl -X POST "http://localhost:8001/api/v1/analyze/upload?provider_id=test" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@test_certificate.pdf"
```

### 4. Run Test Suite

```bash
# Activate virtual environment
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate  # Windows

# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=app --cov-report=term-missing
```

Expected output:
```
tests/test_analyzer.py::TestCertificateAnalyzer::test_initialization PASSED
tests/test_analyzer.py::TestCertificateAnalyzer::test_health_check PASSED
tests/test_ocr.py::TestOCREngines::test_english_ocr_basic PASSED
...
```

### 5. Generate Synthetic Data (Optional)

```bash
# Generate 100 samples for testing
python scripts/generate_synthetic.py --samples 100 --tampering 0.2 --processes 2

# Check output
ls -la data/training/synthetic/images/ | head
ls -la data/training/synthetic/labels/ | head
```

## Troubleshooting

### Issue: ModuleNotFoundError

```bash
# Ensure virtual environment is activated
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows

# Reinstall dependencies
pip install -r requirements.txt
```

### Issue: Tesseract not found

**Windows:**
```bash
# Add to PATH manually
set PATH=%PATH%;C:\Program Files\Tesseract-OCR

# Or set in .env
TESSDATA_PATH=C:\Program Files\Tesseract-OCR\tessdata
```

**Linux:**
```bash
# Install if missing
sudo apt-get install tesseract-ocr tesseract-ocr-eng tesseract-ocr-amh

# Check installation
which tesseract
tesseract --list-langs
```

### Issue: Redis connection refused

```bash
# Check if Redis is running
redis-cli ping

# Start Redis
# Linux:
sudo systemctl start redis
# macOS:
brew services start redis
# Windows/Docker:
docker start redis
```

### Issue: Out of memory

```bash
# Reduce workers in .env
WORKERS=2
MAX_WORKERS=2
BATCH_SIZE=10

# Restart application
```

### Issue: Port already in use

```bash
# Find process using port 8001
# Linux/macOS:
lsof -i :8001
# Windows:
netstat -ano | findstr :8001

# Kill process or change port in .env
PORT=8002
```

### Issue: ML models not loading

```bash
# Check model directory
ls -la app/models/donut_certificate/

# If empty, models will auto-download on first run
# Or disable ML temporarily:
USE_ML=false
```

### Issue: Amharic OCR not working

```bash
# Verify Amharic language pack
tesseract --list-langs | grep amh

# If missing, download manually:
# Linux:
sudo apt-get install tesseract-ocr-amh

# Windows:
# Download amh.traineddata from:
# https://github.com/tesseract-ocr/tessdata/raw/main/amh.traineddata
# Place in: C:\Program Files\Tesseract-OCR\tessdata\
```

### Issue: Import errors with cv2

```bash
# Install OpenCV dependencies
# Linux:
sudo apt-get install libgl1 libglib2.0-0

# Reinstall opencv-python
pip uninstall opencv-python
pip install opencv-python==4.8.1.78
```

### Issue: Slow performance

```bash
# Check system resources
curl http://localhost:8001/health/performance

# Optimize settings in .env:
MAX_FILE_SIZE=5242880  # 5MB
WORKERS=2
MAX_WORKERS=2
BATCH_SIZE=10

# Disable ML if needed:
USE_ML=false
```

## Advanced Configuration

### Custom Model Paths

```bash
# Use custom Donut model
DONUT_MODEL_PATH=/path/to/custom/model

# Use custom training data
TRAINING_DATA_DIR=/path/to/training/data
```

### Redis Configuration

For production, secure Redis:

```bash
# Edit redis.conf
requirepass your-strong-password
maxmemory 2gb
maxmemory-policy allkeys-lru

# Update .env
REDIS_URL=redis://:your-strong-password@localhost:6379/0
```

### Logging Configuration

```bash
# Enable file logging
LOG_LEVEL=INFO
LOG_FILE=logs/app.log

# Rotate logs (Linux)
sudo apt-get install logrotate
```

Create `/etc/logrotate.d/certanalyzer`:
```
/home/certanalyzer/app/logs/*.log {
    daily
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 certanalyzer certanalyzer
}
```

### Performance Tuning

For high-traffic production:

```bash
# Increase workers
WORKERS=8

# Increase Redis memory
maxmemory 4gb

# Use Gunicorn
gunicorn app.main:app \
  --workers 8 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8001 \
  --timeout 120 \
  --keep-alive 5 \
  --max-requests 1000 \
  --max-requests-jitter 50
```

## Database Setup (Optional)

For persistent storage of analysis results:

```bash
# Install PostgreSQL
sudo apt-get install postgresql postgresql-contrib

# Create database
sudo -u postgres psql
CREATE DATABASE certanalyzer;
CREATE USER certuser WITH PASSWORD 'password';
GRANT ALL PRIVILEGES ON DATABASE certanalyzer TO certuser;
\q

# Add to .env
DATABASE_URL=postgresql://certuser:password@localhost/certanalyzer
```

## Monitoring Setup

### Prometheus Metrics

```bash
# Install Prometheus
wget https://github.com/prometheus/prometheus/releases/download/v2.45.0/prometheus-2.45.0.linux-amd64.tar.gz
tar xvfz prometheus-*.tar.gz
cd prometheus-*

# Configure prometheus.yml
scrape_configs:
  - job_name: 'certanalyzer'
    static_configs:
      - targets: ['localhost:8001']

# Start Prometheus
./prometheus --config.file=prometheus.yml
```

### Grafana Dashboards

```bash
# Access Grafana (if using docker-compose)
http://localhost:3000
Username: admin
Password: admin

# Import dashboard
# Use provided dashboard JSON in monitoring/dashboards/
```

## Backup and Recovery

### Backup Redis Data

```bash
# Manual backup
redis-cli SAVE
cp /var/lib/redis/dump.rdb /backup/redis-$(date +%Y%m%d).rdb

# Automated backup (cron)
0 2 * * * redis-cli SAVE && cp /var/lib/redis/dump.rdb /backup/redis-$(date +\%Y\%m\%d).rdb
```

### Backup ML Models

```bash
# Backup models directory
tar -czf models-backup-$(date +%Y%m%d).tar.gz models/

# Restore
tar -xzf models-backup-YYYYMMDD.tar.gz
```

## Security Hardening

### 1. Enable API Key Authentication

```python
# Add to app/api/routes.py
from fastapi import Security, HTTPException
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key")

async def verify_api_key(api_key: str = Security(api_key_header)):
    if api_key != os.getenv("API_KEY"):
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key
```

### 2. Configure Firewall

```bash
# Ubuntu UFW
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

### 3. Secure Redis

```bash
# Edit /etc/redis/redis.conf
bind 127.0.0.1
requirepass your-strong-password
rename-command CONFIG ""
rename-command FLUSHALL ""
```

## Next Steps

After successful setup:

1. **Test the API** using the interactive docs at `/docs`
2. **Generate synthetic data** for model training
3. **Configure monitoring** and alerts
4. **Set up backups** for Redis and models
5. **Implement authentication** for production
6. **Review logs** regularly for issues
7. **Monitor performance** metrics

## Support

If you encounter issues:
1. Check logs: `tail -f logs/app.log`
2. Review health endpoint: `curl http://localhost:8001/api/v1/health`
3. Check system resources: `curl http://localhost:8001/health/performance`
4. Consult troubleshooting section above
5. Open an issue on GitHub

---

**Setup Version**: 1.0  
**Last Updated**: March 2024
