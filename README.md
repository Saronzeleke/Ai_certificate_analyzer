# AI Certificate Analyzer

> **Production-ready certificate verification system with hybrid OCR/ML analysis and multilingual support (English & Amharic)**

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## Overview

AI Certificate Analyzer is an intelligent document verification system designed for service providers to authenticate educational and professional certificates. The system combines advanced OCR technology with machine learning models to detect tampering, extract structured data, and provide automated recommendations.

### Key Features

- **Hybrid Analysis Engine**: Combines OCR and ML models for maximum accuracy
- **Multilingual Support**: Native support for English and Amharic scripts with automatic detection
- **Tampering Detection**: Advanced forensic analysis using ELA, noise analysis, and copy-move detection
- **Synthetic Data Generation**: Built-in tools to generate 10,000+ training samples with realistic variations
- **Production-Ready API**: RESTful API with caching, rate limiting, and comprehensive error handling
- **Real-time Processing**: Optimized for 8GB RAM systems with concurrent request handling
- **Service Provider Dashboard**: Admin-friendly summaries for quick decision-making

### Architecture

```
┌─────────────────┐
│  FastAPI Server │
└────────┬────────┘
         │
    ┌────┴────┐
    │ Router  │
    └────┬────┘
         │
┌────────┴─────────────────────────────────┐
│   ProductionCertificateAnalyzer          │
├──────────────────────────────────────────┤
│  ┌──────────────┐  ┌─────────────────┐  │
│  │ Script       │  │ Multilingual    │  │
│  │ Detector     │──│ OCR Router      │  │
│  └──────────────┘  └─────────────────┘  │
│                                          │
│  ┌──────────────┐  ┌─────────────────┐  │
│  │ Tamper       │  │ Donut ML        │  │
│  │ Detector     │  │ Parser          │  │
│  └──────────────┘  └─────────────────┘  │
│                                          │
│  ┌──────────────┐  ┌─────────────────┐  │
│  │ Image        │  │ Recommendation  │  │
│  │ Processor    │  │ Engine          │  │
│  └──────────────┘  └─────────────────┘  │
└──────────────────────────────────────────┘
         │
    ┌────┴────┐
    │  Redis  │
    │  Cache  │
    └─────────┘
```

## Quick Start

### Prerequisites

- Python 3.10 or higher
- Redis Server 7.0+
- Tesseract OCR 4.0+ with English and Amharic language packs
- 8GB RAM minimum (16GB recommended)
- Windows/Linux/macOS

### Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd ai_certificate
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Install Tesseract OCR**

**Windows:**
```bash
# Download installer from: https://github.com/UB-Mannheim/tesseract/wiki
# Install to: C:\Program Files\Tesseract-OCR
# Add to PATH
```

**Linux:**
```bash
sudo apt-get update
sudo apt-get install tesseract-ocr tesseract-ocr-eng tesseract-ocr-amh
```

**macOS:**
```bash
brew install tesseract tesseract-lang
```

5. **Install and start Redis**

**Windows:**
```bash
# Download from: https://github.com/microsoftarchive/redis/releases
# Or use Docker: docker run -d -p 6379:6379 redis:7-alpine
```

**Linux:**
```bash
sudo apt-get install redis-server
sudo systemctl start redis
```

**macOS:**
```bash
brew install redis
brew services start redis
```

6. **Configure environment**
```bash
cp .env.example .env
# Edit .env with your settings
```

7. **Download ML models** (Optional but recommended)
```bash
# Models will be auto-downloaded on first run
# Or manually place in: app/models/donut_certificate/
```

### Running the Application

**Development Mode:**
```bash
python app/main.py
```

**Production Mode:**
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8001 --workers 4
```

**Using Docker:**
```bash
docker-compose up -d
```

The API will be available at:
- API: http://localhost:8001
- Interactive Docs: http://localhost:8001/docs
- ReDoc: http://localhost:8001/redoc

## API Endpoints

### Core Endpoints

#### Health Check
```http
GET /api/v1/health
```

#### Analyze Certificate (File Upload)
```http
POST /api/v1/analyze/upload
Content-Type: multipart/form-data

Parameters:
- file: Certificate image/PDF (required)
- provider_id: Service provider identifier (default: "default")
- language_hint: "english" | "amharic" | null (optional)
```

#### Analyze Certificate (URL)
```http
POST /api/v1/analyze/url
Content-Type: application/json

{
  "document_url": "https://example.com/certificate.pdf",
  "provider_id": "provider_123",
  "language_hint": "english"
}
```

#### Direct Analysis (Optimized)
```http
POST /api/v1/analyze/direct?provider_id=xxx&request_id=yyy&file_upload=true
Content-Type: multipart/form-data

Returns: Full analysis + admin-friendly summary
```

#### Generate Synthetic Data
```http
POST /api/v1/generate/synthetic
Content-Type: application/json

{
  "num_samples": 1000,
  "tampering_ratio": 0.2,
  "languages": ["english", "amharic"]
}
```

#### System Statistics
```http
GET /api/v1/statistics
```

### Response Format

```json
{
  "analysis_id": "anal_a1b2c3d4e5f6",
  "timestamp": "2024-03-29T10:30:00Z",
  "authenticity_score": 0.87,
  "status": "Pending Admin Review",
  "admin_action": "approve",
  "extracted_data": {
    "fields": {
      "name": "John Doe",
      "student_id": "STU123456",
      "university": "Example University",
      "course": "Computer Science",
      "issue_date": "2023-06-15"
    },
    "confidence_scores": {...}
  },
  "quality_metrics": {
    "ocr_confidence": 0.92,
    "tampering_confidence": 0.05,
    "ml_confidence": 0.88,
    "extraction_method": "ml"
  },
  "flags": {
    "tampering_detected": false,
    "low_quality_scan": false,
    "potential_forgery": false
  },
  "recommendations": [
    "Certificate appears valid - proceed with verification"
  ]
}
```

## Configuration

### Environment Variables

Key configuration options in `.env`:

```bash
# Application
APP_NAME=AI Certificate Analyzer
DEBUG=false
LOG_LEVEL=INFO

# Server
HOST=0.0.0.0
PORT=8001
WORKERS=4

# Redis
REDIS_URL=redis://localhost:6379/0

# OCR
OCR_LANGUAGES=eng+amh
TESSDATA_PATH=/usr/share/tesseract-ocr/4.00/tessdata  # Linux
# TESSDATA_PATH=C:\Program Files\Tesseract-OCR\tessdata  # Windows

# ML Models
USE_ML=true
ML_CONFIDENCE_THRESHOLD=0.6
DONUT_MODEL_PATH=app/models/donut_certificate

# Analysis Thresholds
REJECT_THRESHOLD=0.65
LOW_QUALITY_THRESHOLD=0.7
TAMPERING_THRESHOLD=0.75

# Performance
MAX_FILE_SIZE=10485760  # 10MB
MAX_WORKERS=4
BATCH_SIZE=25
```

## Project Structure

```
ai_certificate/
├── app/
│   ├── analyzers/              # Core analysis engines
│   │   ├── certificate_analyzer.py    # Main analyzer
│   │   ├── script_detector.py         # Language detection
│   │   ├── tamper_detector.py         # Forgery detection
│   │   ├── recommendation_engine.py   # AI recommendations
│   │   ├── ml_models/                 # ML components
│   │   │   ├── donut_model.py        # Document parser
│   │   │   ├── field_extractor.py    # Field extraction
│   │   │   └── validator.py          # Data validation
│   │   ├── ocr/                       # OCR engines
│   │   │   ├── english_ocr.py
│   │   │   ├── amharic_ocr.py
│   │   │   ├── multilingual_ocr.py
│   │   │   └── router.py             # OCR routing logic
│   │   └── synthetic_generator/       # Training data
│   │       ├── generator.py
│   │       ├── augmentor.py
│   │       └── templates.py
│   ├── api/                    # API layer
│   │   ├── routes.py          # Endpoint definitions
│   │   └── schemas.py         # Pydantic models
│   ├── utils/                  # Utilities
│   │   ├── config.py          # Configuration
│   │   ├── cache.py           # Redis caching
│   │   ├── image_processing.py
│   │   └── fonts/             # Font files
│   ├── vision/                 # Computer vision
│   │   └── detector.py        # YOLO detector
│   ├── data/                   # Data storage
│   │   ├── templates/         # Certificate templates
│   │   └── training/          # Training datasets
│   └── main.py                # Application entry point
├── tests/                      # Test suite
├── scripts/                    # Utility scripts
├── models/                     # ML model storage
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── .env
```

## Core Components

### 1. Certificate Analyzer
The main orchestrator that coordinates all analysis components:
- Manages hybrid OCR/ML pipeline
- Calculates authenticity scores
- Generates recommendations
- Handles caching and performance optimization

### 2. OCR Engines
- **English OCR**: Tesseract-based with custom configurations
- **Amharic OCR**: Specialized Ethiopic script support
- **Multilingual Router**: Automatic language detection and routing

### 3. ML Models
- **Donut Parser**: Transformer-based document understanding
- **Field Extractor**: Structured data extraction
- **Validator**: Business rule validation

### 4. Tamper Detection
Multi-layered forgery detection:
- Error Level Analysis (ELA)
- Noise inconsistency detection
- Copy-move detection
- Text region analysis
- Metadata verification

### 5. Script Detector
Automatic language identification using:
- Fast OCR sampling
- Visual feature analysis
- ML-based classification
- Character set detection

### 6. Recommendation Engine
AI-powered decision support:
- Risk level assessment
- Field validation
- Confidence scoring
- Actionable recommendations

## Usage Examples

### Python Client

```python
import requests

# Analyze certificate from file
with open('certificate.pdf', 'rb') as f:
    response = requests.post(
        'http://localhost:8001/api/v1/analyze/upload',
        files={'file': f},
        params={'provider_id': 'provider_123'}
    )
    result = response.json()
    print(f"Authenticity Score: {result['authenticity_score']}")
    print(f"Status: {result['status']}")
```

### cURL

```bash
# Upload certificate
curl -X POST "http://localhost:8001/api/v1/analyze/upload?provider_id=test" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@certificate.pdf"

# Analyze from URL
curl -X POST "http://localhost:8001/api/v1/analyze/url" \
  -H "Content-Type: application/json" \
  -d '{
    "document_url": "https://example.com/cert.pdf",
    "provider_id": "provider_123"
  }'
```

### JavaScript/TypeScript

```typescript
const formData = new FormData();
formData.append('file', certificateFile);

const response = await fetch('http://localhost:8001/api/v1/analyze/upload?provider_id=provider_123', {
  method: 'POST',
  body: formData
});

const result = await response.json();
console.log('Authenticity Score:', result.authenticity_score);
```

## Testing

### Run Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_analyzer.py -v

# Run with coverage
pytest tests/ --cov=app --cov-report=html

# Run OCR tests only
pytest tests/test_ocr.py -v
```

### Test Coverage

The test suite includes:
- Unit tests for all analyzers
- Integration tests for API endpoints
- OCR engine validation
- ML model testing
- Performance benchmarks
- Error handling scenarios

## Synthetic Data Generation

Generate training data for model improvement:

```bash
# Generate 10,000 samples with 20% tampering
python scripts/generate_synthetic.py --samples 10000 --tampering 0.2 --processes 4

# Generate Amharic certificates
python scripts/generate_synthetic.py --samples 5000 --language amharic --processes 2
```

Generated data structure:
```
data/training/synthetic/
├── images/
│   ├── cert_00000000.png
│   ├── cert_00000001.png
│   └── ...
└── labels/
    ├── cert_00000000.json
    ├── cert_00000001.json
    └── ...
```

## Model Training

### Train Script Detector

```bash
python scripts/train_script_detector.py \
  --data-dir data/training/synthetic \
  --epochs 50 \
  --batch-size 32
```

### Train Donut Model

```bash
python scripts/train_donut.py \
  --train-dir data/training/synthetic \
  --output-dir models/donut_certificate \
  --epochs 30
```

## Performance Optimization

### Memory Management (8GB RAM)

The system is optimized for 8GB RAM environments:
- Singleton analyzer instance (loaded once at startup)
- Thread pool with 2 workers for CPU-bound tasks
- Image size limits (max 2000px dimension)
- Batch processing with size limits
- Redis caching to reduce reprocessing

### Monitoring

Check system performance:
```bash
curl http://localhost:8001/health/performance
```

Response includes:
- Memory usage percentage
- Available memory
- CPU utilization
- Thread pool status
- Performance recommendations

## Deployment

### Docker Deployment

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f api

# Stop services
docker-compose down
```

Services included:
- **api**: Main FastAPI application (port 8001)
- **redis**: Cache layer (port 6379)
- **monitoring**: Grafana dashboard (port 3000)
- **synthetic-generator**: Background data generation

### Production Deployment

1. **Set production environment variables**
```bash
DEBUG=false
LOG_LEVEL=WARNING
WORKERS=4
RELOAD=false
```

2. **Use production WSGI server**
```bash
gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8001 \
  --timeout 120
```

3. **Set up reverse proxy** (Nginx example)
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Troubleshooting

### Common Issues

**Issue: Tesseract not found**
```bash
# Verify installation
tesseract --version

# Check language packs
tesseract --list-langs

# Should show: eng, amh
```

**Issue: Redis connection failed**
```bash
# Check Redis is running
redis-cli ping
# Should return: PONG

# Test connection
redis-cli -h localhost -p 6379
```

**Issue: Out of memory errors**
```bash
# Reduce workers in .env
WORKERS=2
MAX_WORKERS=2
BATCH_SIZE=10

# Reduce image quality
MAX_FILE_SIZE=5242880  # 5MB
```

**Issue: ML models not loading**
```bash
# Check model path
ls -la app/models/donut_certificate/

# Disable ML temporarily
USE_ML=false
```

## API Authentication

For production, implement API key authentication:

```python
# Add to headers
headers = {
    'X-API-Key': 'your-api-key-here'
}
```

Configure in `.env`:
```bash
API_KEY_HEADER=X-API-Key
REQUIRE_API_KEY=true
```

## Monitoring & Logging

### Application Logs

Logs are written to:
- Console (stdout/stderr)
- File: `logs/app.log` (if configured)
- Audit log: `audit.log`

### Metrics

Access Grafana dashboard:
```
http://localhost:3000
Username: admin
Password: admin
```

Metrics include:
- Request rate and latency
- Analysis success/failure rates
- Cache hit rates
- Memory and CPU usage
- OCR vs ML usage statistics

## Security Considerations

- Input validation on all endpoints
- File size limits enforced
- Secure file handling with automatic cleanup
- Redis password protection (configure in production)
- CORS configuration for allowed origins
- Rate limiting (implement as needed)
- API key authentication (implement as needed)

## Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

### Code Style

- Follow PEP 8 guidelines
- Use type hints
- Add docstrings to all functions
- Write tests for new features
- Run `black` and `flake8` before committing

```bash
# Format code
black app/ tests/

# Check linting
flake8 app/ tests/
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues, questions, or contributions:
- Open an issue on GitHub
- Contact: support@example.com
- Documentation: https://docs.example.com

## Acknowledgments

- Tesseract OCR for text extraction
- Hugging Face Transformers for ML models
- FastAPI for the web framework
- Redis for caching layer
- OpenCV for image processing

---

**Version**: 2024.2.0  
**Last Updated**: March 2024  
**Status**: Production Ready
