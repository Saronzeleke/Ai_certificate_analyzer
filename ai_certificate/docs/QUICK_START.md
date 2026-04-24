# Quick Start Guide - AI Certificate Analyzer

## 5-Minute Setup

### 1. Install Tesseract + Amharic Language

**Windows (PowerShell as Admin):**
```powershell
# Download and install Tesseract from:
# https://github.com/UB-Mannheim/tesseract/wiki

# Then install Amharic language:
Invoke-WebRequest -Uri "https://github.com/tesseract-ocr/tessdata/raw/main/amh.traineddata" -OutFile "$env:TEMP\amh.traineddata"
Copy-Item "$env:TEMP\amh.traineddata" -Destination "C:\Program Files\Tesseract-OCR\tessdata\amh.traineddata"

# Verify:
tesseract --list-langs
# Should show: eng, amh, osd
```

**Linux:**
```bash
sudo apt-get install tesseract-ocr
sudo wget https://github.com/tesseract-ocr/tessdata/raw/main/amh.traineddata -P /usr/share/tesseract-ocr/4.00/tessdata/
tesseract --list-langs
```

### 2. Install Python Dependencies

```bash
cd ai_certificate
python -m venv my_env
my_env\Scripts\activate  # Windows
# source my_env/bin/activate  # Linux/Mac

pip install -r requirements.txt
```

### 3. Run the Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Test with Certificate

```bash
# Upload Amharic certificate
curl -X POST "http://localhost:8000/api/analyze" \
  -F "file=@certificate.jpg" \
  -F "language_hint=amh"

# Upload English certificate
curl -X POST "http://localhost:8000/api/analyze" \
  -F "file=@certificate.jpg" \
  -F "language_hint=eng"
```

---

## What Gets Installed

### Core Components

1. **Tesseract OCR** (~50MB)
   - English language data (included)
   - Amharic language data (~1MB download)
   - OCR engine for text extraction

2. **Python Packages** (~2GB)
   - FastAPI - Web framework
   - PyTorch - Deep learning (largest component)
   - Transformers - Donut model
   - OpenCV - Image processing
   - Pytesseract - Tesseract wrapper

3. **Donut Model** (~1.5GB, downloaded on first use)
   - ML model for field extraction
   - Cached in `~/.cache/huggingface/`
   - Optional but recommended

### Total Disk Space: ~4GB

---

## What It Does

### Input
- Certificate image (JPG, PNG, PDF)
- Optional language hint (amh/eng)

### Processing
1. Detects script (Amharic/English/Mixed)
2. Extracts text using Tesseract OCR
3. Uses ML model to identify fields
4. Validates extracted data
5. Checks for tampering

### Output
```json
{
  "extracted_data": {
    "name": "ሄኖክ ወልደማርያም",
    "student_id": "ID62778",
    "university": "ሀርቫርድ ዩኒቨርሲቲ",
    "course": "ሕክምና",
    "gpa": "2.87",
    "issue_date": "2022-09-14"
  },
  "authenticity_score": 0.95,
  "script_detected": "amh",
  "ocr_confidence": 0.91
}
```

---

## Supported Fields

### Amharic Certificates
- **ስም** (Name)
- **የተማሪ መታወቂያ** (Student ID)
- **ዩኒቨርሲቲ** (University)
- **ኮርስ** (Course)
- **አማካይ ነጥብ** (GPA)
- **የተሰጠበት ቀን** (Issue Date)

### English Certificates
- Name
- Student ID
- University
- Course
- GPA
- Issue Date

---

## Common Issues

### "Amharic not working"
✅ **Solution**: Install Amharic language data (see Step 1)
```bash
tesseract --list-langs  # Must show 'amh'
```

### "Fields extracted incorrectly"
✅ **Solution**: 
- Ensure good image quality (300 DPI minimum)
- Check that certificate follows standard format
- Verify script detection: `"script_detected": "amh"`

### "Slow first run"
✅ **Normal**: Donut model downloads on first use (~1.5GB)
- Subsequent runs are fast (uses cache)

---

## API Endpoints

### Analyze Certificate
```http
POST /api/analyze
Content-Type: multipart/form-data

Parameters:
- file: Certificate image (required)
- language_hint: "amh" or "eng" (optional)
```

### Health Check
```http
GET /health
```

### Get Analysis
```http
GET /api/analysis/{analysis_id}
```

---

## Configuration

Create `.env` file:
```bash
# Tesseract
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
TESSDATA_PREFIX=C:\Program Files\Tesseract-OCR\tessdata

# ML Model
USE_ML_MODEL=true
ML_CONFIDENCE_THRESHOLD=0.6

# API
API_HOST=0.0.0.0
API_PORT=8000
```

---

## Next Steps

1. ✅ Install Tesseract + Amharic
2. ✅ Install Python dependencies
3. ✅ Run server
4. ✅ Test with sample certificates
5. 📖 Read full [INSTALLATION.md](INSTALLATION.md) for advanced setup
6. 🔧 Configure for production
7. 🚀 Deploy

---

## Need Help?

- Check [INSTALLATION.md](INSTALLATION.md) for detailed guide
- Review logs in `audit.log`
- Verify Tesseract: `tesseract --version`
- Test imports: `python -c "import pytesseract, cv2; print('OK')"`
