# Quick Start Guide - AI Certificate Analyzer

Get up and running in 5 minutes.

## Prerequisites

- Python 3.10+
- Redis Server
- Tesseract OCR

## Installation

### 1. Clone and Setup

```bash
git clone <repository-url>
cd ai_certificate
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Install Tesseract

**Windows:**
- Download from: https://github.com/UB-Mannheim/tesseract/wiki
- Install to: `C:\Program Files\Tesseract-OCR`
- Add to PATH

**Linux:**
```bash
sudo apt-get install tesseract-ocr tesseract-ocr-eng tesseract-ocr-amh
```

**macOS:**
```bash
brew install tesseract tesseract-lang
```

### 3. Start Redis

**Windows (Docker):**
```bash
docker run -d -p 6379:6379 redis:7-alpine
```

**Linux:**
```bash
sudo systemctl start redis
```

**macOS:**
```bash
brew services start redis
```

### 4. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` (Windows users update TESSDATA_PATH):
```bash
TESSDATA_PATH=C:\Program Files\Tesseract-OCR\tessdata  # Windows
PORT=8001
USE_ML=true
```

### 5. Run Application

```bash
python app/main.py
```

Visit: http://localhost:8001/docs

## First API Call

### Using cURL

```bash
curl -X POST "http://localhost:8001/api/v1/analyze/upload?provider_id=test" \
  -F "file=@your_certificate.pdf"
```

### Using Python

```python
import requests

with open('certificate.pdf', 'rb') as f:
    response = requests.post(
        'http://localhost:8001/api/v1/analyze/upload?provider_id=test',
        files={'file': f}
    )
    print(response.json())
```

### Using Browser

1. Open http://localhost:8001/docs
2. Click on `/api/v1/analyze/upload`
3. Click "Try it out"
4. Upload a certificate file
5. Click "Execute"

## Docker Quick Start

```bash
# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f api

# Stop services
docker-compose down
```

## Verify Installation

```bash
# Check health
curl http://localhost:8001/api/v1/health

# Expected response:
# {"status": "healthy", "components": {...}}
```

## Next Steps

- Read [API_DOCUMENTATION.md](API_DOCUMENTATION.md) for full API reference
- See [SETUP.md](SETUP.md) for detailed setup instructions
- Check [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) for development info
- Review [ARCHITECTURE.md](ARCHITECTURE.md) for system design

## Troubleshooting

**Port already in use:**
```bash
# Change port in .env
PORT=8002
```

**Tesseract not found:**
```bash
# Verify installation
tesseract --version
tesseract --list-langs
```

**Redis connection failed:**
```bash
# Check Redis is running
redis-cli ping
```

**Out of memory:**
```bash
# Reduce workers in .env
WORKERS=2
MAX_WORKERS=2
```

## Support

- Documentation: See docs/ folder
- Issues: Open GitHub issue
- Email: support@example.com

---

**Quick Start Version**: 1.0  
**Last Updated**: March 2024
