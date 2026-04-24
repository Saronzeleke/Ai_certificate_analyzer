# AI Certificate Analyzer - Installation Guide

Complete setup guide for the AI-powered certificate verification system with Amharic and English support.

## System Overview

This system uses:
- **Tesseract OCR** - Text extraction (English + Amharic)
- **Donut Model** - ML-based field extraction
- **FastAPI** - REST API backend
- **Redis** - Caching (optional)
- **Python 3.8+** - Runtime environment

---

## Prerequisites

### 1. Python Environment
```bash
# Check Python version (3.8+ required)
python --version

# Create virtual environment
python -m venv my_env

# Activate (Windows)
my_env\Scripts\activate

# Activate (Linux/Mac)
source my_env/bin/activate
```

### 2. System Dependencies

#### Windows
- **Tesseract OCR**: Download from https://github.com/UB-Mannheim/tesseract/wiki
  - Install to default location: `C:\Program Files\Tesseract-OCR`
  - Add to PATH during installation

#### Linux (Ubuntu/Debian)
```bash
sudo apt-get update
sudo apt-get install tesseract-ocr
sudo apt-get install libtesseract-dev
```

#### macOS
```bash
brew install tesseract
```

---

## Installation Steps

### Step 1: Install Python Dependencies

```bash
cd ai_certificate
pip install -r requirements.txt
```

Key packages installed:
- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `pytesseract` - Tesseract wrapper
- `opencv-python` - Image processing
- `transformers` - Donut model
- `torch` - Deep learning
- `pillow` - Image handling
- `redis` - Caching (optional)

### Step 2: Install Tesseract Amharic Language Data

**Critical for Amharic certificate support!**

#### Windows (Run PowerShell as Administrator)
```powershell
# Download Amharic language data
Invoke-WebRequest -Uri "https://github.com/tesseract-ocr/tessdata/raw/main/amh.traineddata" -OutFile "$env:TEMP\amh.traineddata"

# Copy to Tesseract directory
Copy-Item "$env:TEMP\amh.traineddata" -Destination "C:\Program Files\Tesseract-OCR\tessdata\amh.traineddata"

# Verify installation
tesseract --list-langs
# Should show: eng, amh, osd
```

#### Linux/Mac
```bash
# Download Amharic language data
sudo wget https://github.com/tesseract-ocr/tessdata/raw/main/amh.traineddata -P /usr/share/tesseract-ocr/4.00/tessdata/

# Verify installation
tesseract --list-langs
# Should show: eng, amh, osd
```

### Step 3: Download Donut Model (Optional but Recommended)

The Donut model provides ML-based field extraction for better accuracy.

```bash
cd ai_certificate
python -c "from transformers import DonutProcessor, VisionEncoderDecoderModel; DonutProcessor.from_pretrained('naver-clova-ix/donut-base'); VisionEncoderDecoderModel.from_pretrained('naver-clova-ix/donut-base')"
```

This downloads ~1.5GB of model files to your cache directory:
- Windows: `C:\Users\<username>\.cache\huggingface\`
- Linux/Mac: `~/.cache/huggingface/`

**Note**: First run will be slow as it downloads the model. Subsequent runs use cached version.

### Step 4: Configure Environment Variables

Create `.env` file in `ai_certificate/` directory:

```bash
# Tesseract Configuration
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe  # Windows
# TESSERACT_CMD=/usr/bin/tesseract  # Linux/Mac

# Tesseract data path (if custom location)
TESSDATA_PREFIX=C:\Program Files\Tesseract-OCR\tessdata

# Redis (optional - for caching)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# ML Model Configuration
USE_ML_MODEL=true
ML_CONFIDENCE_THRESHOLD=0.6

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
```

### Step 5: Verify Installation

```bash
# Test Tesseract
tesseract --version
tesseract --list-langs

# Test Python imports
python -c "import pytesseract, cv2, transformers; print('All imports successful')"

# Run health check
python -c "from app.main import app; print('FastAPI app loaded successfully')"
```

---

## Running the Application

### Development Mode

```bash
cd ai_certificate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Access at: http://localhost:8000

### Production Mode

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Docker (Alternative)

```bash
docker build -t ai-certificate .
docker run -p 8000:8000 ai-certificate
```

---

## Usage

### API Endpoints

#### 1. Analyze Certificate
```bash
POST /api/analyze
Content-Type: multipart/form-data

# Upload certificate image
curl -X POST "http://localhost:8000/api/analyze" \
  -F "file=@certificate.jpg" \
  -F "language_hint=amh"
```

Response:
```json
{
  "analysis_id": "anal_xxx",
  "extracted_data": {
    "name": "ሄኖክ ወልደማርያም",
    "student_id": "ID62778",
    "university": "ሀርቫርድ ዩኒቨርሲቲ",
    "course": "ሕክምና",
    "gpa": "2.87",
    "issue_date": "2022-09-14"
  },
  "authenticity_score": 0.95,
  "script_detected": "amh"
}
```

#### 2. Health Check
```bash
GET /health
```

### Supported Languages

- **Amharic (amh)**: Full support with Ethiopic script detection
- **English (eng)**: Full support
- **Mixed**: Automatic detection and processing

### Supported Certificate Types

- University certificates
- Support letters
- Academic transcripts
- Professional certifications

---

## Architecture

### Processing Pipeline

1. **Image Upload** → FastAPI receives image
2. **Script Detection** → Detects Amharic/English/Mixed
3. **OCR Routing** → Routes to appropriate OCR engine
4. **Text Extraction** → Tesseract extracts text
5. **ML Enhancement** → Donut model extracts structured fields
6. **Field Validation** → Validates extracted data
7. **Authenticity Check** → Tamper detection
8. **Response** → Returns structured JSON

### Key Components

```
ai_certificate/
├── app/
│   ├── analyzers/
│   │   ├── certificate_analyzer.py    # Main analyzer
│   │   ├── script_detector.py         # Amharic/English detection
│   │   ├── ocr/
│   │   │   ├── amharic_ocr.py        # Amharic OCR engine
│   │   │   ├── english_ocr.py        # English OCR engine
│   │   │   ├── multilingual_ocr.py   # Combined engine
│   │   │   └── router.py             # Intelligent routing
│   │   └── ml_models/
│   │       ├── donut_model.py        # Donut integration
│   │       └── field_extractor.py    # ML field extraction
│   ├── api/
│   │   ├── routes.py                 # API endpoints
│   │   └── schemas.py                # Request/response models
│   └── main.py                       # FastAPI app
└── requirements.txt
```

---

## Troubleshooting

### Issue: "Tesseract not found"
```bash
# Windows: Add to PATH or set in .env
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe

# Linux: Install tesseract
sudo apt-get install tesseract-ocr
```

### Issue: "Amharic language not available"
```bash
# Verify installation
tesseract --list-langs

# If 'amh' not listed, reinstall language data (see Step 2)
```

### Issue: "Donut model download fails"
```bash
# Manual download
python -c "from transformers import DonutProcessor; DonutProcessor.from_pretrained('naver-clova-ix/donut-base')"

# Or disable ML model in .env
USE_ML_MODEL=false
```

### Issue: "Low OCR confidence for Amharic"
- Ensure image quality is good (300 DPI minimum)
- Check that Amharic language data is installed
- Verify script detection is working: `"script_detected": "amh"`

### Issue: "Fields extracted incorrectly"
- Check image preprocessing settings
- Verify certificate follows standard format
- Review field patterns in `amharic_ocr.py`

---

## Performance Optimization

### 1. Enable Redis Caching
```bash
# Install Redis
# Windows: Download from https://github.com/microsoftarchive/redis/releases
# Linux: sudo apt-get install redis-server

# Enable in .env
REDIS_HOST=localhost
REDIS_PORT=6379
```

### 2. GPU Acceleration (for Donut)
```bash
# Install PyTorch with CUDA
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
```

### 3. Production Settings
- Use multiple workers: `--workers 4`
- Enable caching
- Use GPU for ML models
- Optimize image preprocessing

---

## Testing

```bash
# Run tests
pytest

# Test specific component
pytest tests/test_amharic_ocr.py

# Test with sample certificate
python -m app.analyzers.certificate_analyzer --image sample.jpg
```

---

## Support

For issues or questions:
1. Check troubleshooting section
2. Review logs in `audit.log`
3. Verify all dependencies are installed
4. Test with sample certificates first

---

## License

