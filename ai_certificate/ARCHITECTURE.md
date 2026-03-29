# Architecture Documentation - AI Certificate Analyzer

Technical architecture and design decisions for the AI Certificate Analyzer system.

## System Overview

The AI Certificate Analyzer is a production-ready microservice designed to verify educational and professional certificates using a hybrid approach combining traditional OCR with modern machine learning models.

### Design Principles

1. **Hybrid Intelligence**: Combine rule-based OCR with ML for maximum accuracy
2. **Fail-Safe Operation**: Graceful degradation when components fail
3. **Performance First**: Optimized for 8GB RAM environments
4. **Multilingual Support**: Native English and Amharic processing
5. **Production Ready**: Comprehensive error handling, logging, and monitoring

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Client Layer                             │
│  (Web Apps, Mobile Apps, Service Provider Dashboards)           │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             │ HTTPS/REST
                             │
┌────────────────────────────┴────────────────────────────────────┐
│                      API Gateway Layer                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   FastAPI    │  │  Middleware  │  │   CORS       │         │
│  │   Router     │  │  (Timing,    │  │   GZip       │         │
│  │              │  │   Logging)   │  │              │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────┴────────────────────────────────────┐
│                   Business Logic Layer                           │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │       ProductionCertificateAnalyzer (Orchestrator)       │  │
│  │                                                          │  │
│  │  ┌────────────────┐  ┌────────────────┐               │  │
│  │  │ Script         │  │ Image          │               │  │
│  │  │ Detector       │  │ Processor      │               │  │
│  │  └────────────────┘  └────────────────┘               │  │
│  │                                                          │  │
│  │  ┌────────────────┐  ┌────────────────┐               │  │
│  │  │ Multilingual   │  │ Tamper         │               │  │
│  │  │ OCR Router     │  │ Detector       │               │  │
│  │  └────────────────┘  └────────────────┘               │  │
│  │                                                          │  │
│  │  ┌────────────────┐  ┌────────────────┐               │  │
│  │  │ Donut ML       │  │ Recommendation │               │  │
│  │  │ Parser         │  │ Engine         │               │  │
│  │  └────────────────┘  └────────────────┘               │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────┴────────────────────────────────────┐
│                      Data Layer                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │    Redis     │  │  File System │  │   ML Models  │         │
│  │    Cache     │  │   Storage    │  │   Storage    │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
└──────────────────────────────────────────────────────────────────┘
```

## Component Architecture

### 1. API Layer (`app/api/`)

**Responsibilities:**
- HTTP request handling
- Input validation
- Response formatting
- Background task management
- Error handling

**Key Files:**
- `routes.py`: Endpoint definitions
- `schemas.py`: Pydantic models for request/response validation

**Design Patterns:**
- Dependency Injection for analyzer instance
- Singleton pattern for shared resources
- Background tasks for async operations

### 2. Certificate Analyzer (`app/analyzers/certificate_analyzer.py`)

**Core Orchestrator** - Coordinates all analysis components.

**Workflow:**
```
1. Receive document (file or URL)
2. Check cache (Redis)
3. Process document → Extract images
4. For each page:
   a. Detect script (English/Amharic)
   b. Run OCR extraction (parallel)
   c. Run tamper detection (parallel)
   d. Run ML analysis (if enabled, parallel)
   e. Merge results
5. Calculate authenticity score
6. Generate recommendations
7. Cache result
8. Return structured response
```

**Key Methods:**
- `analyze_certificate_file()`: Main entry for file uploads
- `analyze_certificate_url()`: Main entry for URL analysis
- `_analyze_single_page_hybrid()`: Per-page hybrid analysis
- `_combine_hybrid_results()`: Result aggregation
- `create_provider_summary()`: Admin-friendly transformation

**Performance Optimizations:**
- Singleton instance (loaded once at startup)
- Thread pool for CPU-bound tasks
- Parallel processing of detection tasks
- Redis caching with 1-hour TTL
- Image size limits and compression

### 3. OCR Subsystem (`app/analyzers/ocr/`)

**Multi-Engine Architecture:**

```
┌─────────────────────────────────────┐
│     MultilingualOCRRouter           │
│  (Intelligent routing logic)        │
└──────────┬──────────────────────────┘
           │
    ┌──────┴──────┐
    │             │
┌───▼────┐   ┌───▼────┐
│English │   │Amharic │
│  OCR   │   │  OCR   │
│Engine  │   │Engine  │
└────────┘   └────────┘
```

**Components:**

1. **EnglishOCREngine** (`english_ocr.py`)
   - Tesseract-based with custom configs
   - Field pattern matching
   - Confidence scoring
   - Multiple OCR configurations (document, single_line, sparse_text)

2. **AmharicOCREngine** (`amharic_ocr.py`)
   - Ethiopic script support
   - Unicode normalization
   - Character validation
   - Fallback to English for mixed content

3. **MultilingualOCREngine** (`multilingual_ocr.py`)
   - Runs both engines in parallel
   - Selects best result based on confidence
   - Handles mixed-language documents

4. **MultilingualOCRRouter** (`router.py`)
   - Script detection integration
   - Routing strategy selection
   - Performance tracking
   - Fallback mechanisms

**OCR Configurations:**
```python
configs = {
    'document': '--psm 3 --oem 3',      # Full page
    'single_line': '--psm 7 --oem 3',   # Single line
    'sparse_text': '--psm 11 --oem 3',  # Sparse text
    'single_word': '--psm 8 --oem 3'    # Single word
}
```

### 4. ML Subsystem (`app/analyzers/ml_models/`)

**Components:**

1. **DonutCertificateParser** (`donut_model.py`)
   - Transformer-based document understanding
   - Vision encoder + text decoder
   - JSON output parsing
   - Confidence scoring

2. **MLFieldExtractor** (`field_extractor.py`)
   - Custom CNN for field extraction
   - Spatial feature analysis
   - Bounding box prediction
   - Training pipeline

3. **CertificateValidator** (`validator.py`)
   - Business rule validation
   - Field format checking
   - Anomaly detection
   - Cross-field validation

**ML Pipeline:**
```
Image → Donut Parser → Structured JSON
                    ↓
              Field Extractor → Bounding Boxes
                    ↓
               Validator → Validation Results
```

### 5. Tamper Detection (`app/analyzers/tamper_detector.py`)

**Multi-Layer Detection System:**

```
Image Input
    │
    ├─→ Error Level Analysis (ELA)
    │   └─→ Compression artifact detection
    │
    ├─→ Noise Inconsistency Analysis
    │   └─→ Statistical noise patterns
    │
    ├─→ Copy-Move Detection
    │   └─→ Duplicate region identification
    │
    ├─→ Text Region Analysis
    │   └─→ OCR-based text validation
    │
    ├─→ Metadata Analysis
    │   └─→ EXIF data verification
    │
    └─→ ML-Based Detection (Optional)
        └─→ Trained classifier
            ↓
    Combined Score → Tampering Confidence
```

**Detection Methods:**

1. **ELA (Error Level Analysis)**
   - Detects compression inconsistencies
   - Identifies edited regions
   - Generates heat map

2. **Noise Analysis**
   - Statistical noise distribution
   - Region-based comparison
   - Outlier detection

3. **Copy-Move Detection**
   - Feature matching
   - Duplicate region identification
   - Spatial analysis

4. **Text Region Analysis**
   - OCR confidence per region
   - Font consistency
   - Alignment validation

5. **Metadata Verification**
   - EXIF data extraction
   - Timestamp validation
   - Software detection

### 6. Script Detection (`app/analyzers/script_detector.py`)

**Detection Strategy:**

```
Image → Fast OCR Sample → Character Analysis → Script Classification
     ↓
Visual Features → ML Classifier → Confidence Score
     ↓
Combined Result → English | Amharic | Mixed
```

**Methods:**
- Fast OCR sampling (100ms)
- Unicode range detection
- Visual feature extraction
- ML-based classification
- Confidence scoring

**Character Ranges:**
- English: U+0041-U+007A
- Amharic: U+1200-U+137F (Ethiopic)

### 7. Recommendation Engine (`app/analyzers/recommendation_engine.py`)

**Decision Logic:**

```
Input: Authenticity Score + Extracted Fields + Flags
    │
    ├─→ Field Validation
    │   ├─→ Name validation
    │   ├─→ ID validation
    │   ├─→ Date validation
    │   └─→ Cross-field checks
    │
    ├─→ Risk Assessment
    │   ├─→ Score thresholds
    │   ├─→ Tampering flags
    │   ├─→ Quality metrics
    │   └─→ Expiry status
    │
    └─→ Recommendation Generation
        ├─→ APPROVE (score > 0.75, no flags)
        ├─→ REJECT (score < 0.4, tampering)
        └─→ MANUAL_REVIEW (0.4-0.75, flags)
```

**Risk Levels:**
- **LOW**: Score > 0.75, no issues
- **MEDIUM**: Score 0.5-0.75, minor issues
- **HIGH**: Score 0.3-0.5, multiple issues
- **CRITICAL**: Score < 0.3, tampering detected

### 8. Synthetic Data Generator (`app/analyzers/synthetic_generator/`)

**Generation Pipeline:**

```
Template Selection
    ↓
Field Population (Random/Realistic)
    ↓
Image Rendering (PIL + Fonts)
    ↓
Augmentation (Rotation, Noise, Blur)
    ↓
Optional Tampering (20% of samples)
    ↓
Label Generation (JSON)
    ↓
Save to Disk
```

**Components:**
- `generator.py`: Main generation logic
- `templates.py`: Certificate templates
- `augmentor.py`: Image augmentation

**Tampering Types:**
- Text modification
- Seal removal
- Date alteration
- Field duplication

## Data Flow

### Analysis Request Flow

```
1. Client Request
   ↓
2. FastAPI Endpoint
   ↓
3. Input Validation
   ↓
4. Cache Check (Redis)
   ├─→ Cache Hit → Return Cached Result
   └─→ Cache Miss → Continue
       ↓
5. File Processing
   ├─→ Upload: Save to temp
   └─→ URL: Download to temp
       ↓
6. Image Extraction (PDF → Images)
   ↓
7. Image Enhancement
   ↓
8. Parallel Analysis (per page)
   ├─→ Script Detection
   ├─→ OCR Extraction
   ├─→ Tamper Detection
   └─→ ML Analysis (if enabled)
       ↓
9. Result Merging
   ↓
10. Score Calculation
    ↓
11. Recommendation Generation
    ↓
12. Cache Storage (Redis)
    ↓
13. Response Formatting
    ↓
14. Return to Client
```

### Caching Strategy

**Cache Keys:**
- Upload: `ai_upload:{provider_id}:{file_hash}`
- URL: `ai_url:{provider_id}:{url_hash}`
- Analysis: `analysis:{analysis_id}`

**TTL:**
- Analysis results: 3600s (1 hour)
- Statistics: 300s (5 minutes)
- Health checks: 60s (1 minute)

**Eviction Policy:**
- LRU (Least Recently Used)
- Max memory: 1GB (configurable)

## Database Schema (Future)

For persistent storage:

```sql
-- Analysis Results
CREATE TABLE analysis_results (
    id SERIAL PRIMARY KEY,
    analysis_id VARCHAR(50) UNIQUE NOT NULL,
    provider_id VARCHAR(100) NOT NULL,
    request_id VARCHAR(100) NOT NULL,
    authenticity_score DECIMAL(5,4),
    status VARCHAR(50),
    extracted_data JSONB,
    quality_metrics JSONB,
    flags JSONB,
    recommendations TEXT[],
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_provider (provider_id),
    INDEX idx_analysis (analysis_id),
    INDEX idx_created (created_at)
);

-- Provider Statistics
CREATE TABLE provider_stats (
    provider_id VARCHAR(100) PRIMARY KEY,
    total_requests INTEGER DEFAULT 0,
    approved_count INTEGER DEFAULT 0,
    rejected_count INTEGER DEFAULT 0,
    average_score DECIMAL(5,4),
    last_request_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Audit Log
CREATE TABLE audit_log (
    id SERIAL PRIMARY KEY,
    analysis_id VARCHAR(50),
    action VARCHAR(50),
    user_id VARCHAR(100),
    details JSONB,
    ip_address INET,
    created_at TIMESTAMP DEFAULT NOW()
);
```

## Security Architecture

### Authentication Flow

```
Client Request
    ↓
API Key Header Check
    ├─→ Missing → 401 Unauthorized
    ├─→ Invalid → 403 Forbidden
    └─→ Valid → Continue
        ↓
Rate Limit Check
    ├─→ Exceeded → 429 Too Many Requests
    └─→ OK → Continue
        ↓
Input Validation
    ├─→ Invalid → 400 Bad Request
    └─→ Valid → Process Request
```

### Security Layers

1. **Input Validation**
   - File type checking
   - Size limits
   - Content validation
   - Sanitization

2. **Authentication**
   - API key validation
   - Provider ID verification
   - Request signing (future)

3. **Authorization**
   - Provider-level access control
   - Endpoint permissions
   - Resource quotas

4. **Data Protection**
   - Temporary file cleanup
   - Secure file handling
   - No persistent storage of sensitive data
   - Redis password protection

## Performance Architecture

### Memory Management (8GB RAM)

**Optimization Strategies:**

1. **Singleton Pattern**
   - Single analyzer instance
   - Loaded once at startup
   - Shared across requests

2. **Thread Pool**
   - 2 workers for CPU-bound tasks
   - Prevents memory overload
   - Async/await for I/O

3. **Image Processing**
   - Max dimension: 2000px
   - Automatic downscaling
   - Efficient numpy operations

4. **Batch Processing**
   - Configurable batch size
   - Memory-aware batching
   - Progressive processing

5. **Caching**
   - Redis for results
   - In-memory LRU for hot data
   - Automatic eviction

### Concurrency Model

```
FastAPI (ASGI)
    ↓
Uvicorn Workers (4)
    ↓
Async Request Handlers
    ↓
Thread Pool (2) for CPU-bound
    ├─→ Image Processing
    ├─→ ML Inference
    └─→ OCR Extraction
```

**Concurrency Limits:**
- Max concurrent requests: 5
- Backlog: 20
- Worker timeout: 120s

## Scalability

### Horizontal Scaling

```
┌──────────┐
│  Nginx   │ (Load Balancer)
└────┬─────┘
     │
     ├─→ API Instance 1 (8GB RAM)
     ├─→ API Instance 2 (8GB RAM)
     ├─→ API Instance 3 (8GB RAM)
     └─→ API Instance N
          ↓
     ┌────────┐
     │ Redis  │ (Shared Cache)
     └────────┘
```

**Scaling Considerations:**
- Stateless API design
- Shared Redis cache
- Load balancer with health checks
- Session affinity not required

### Vertical Scaling

For single-instance optimization:

| RAM | Workers | Thread Pool | Batch Size |
|-----|---------|-------------|------------|
| 8GB | 2 | 2 | 10 |
| 16GB | 4 | 4 | 25 |
| 32GB | 8 | 8 | 50 |
| 64GB | 16 | 16 | 100 |

## ML Model Architecture

### Donut Model

**Architecture:**
```
Input Image (PIL)
    ↓
Vision Encoder (Swin Transformer)
    ├─→ Patch Embedding
    ├─→ Multi-head Attention
    └─→ Visual Features
        ↓
Text Decoder (BART)
    ├─→ Autoregressive Generation
    ├─→ JSON Formatting
    └─→ Structured Output
```

**Model Specs:**
- Base Model: `naver-clova-ix/donut-base`
- Parameters: ~200M
- Input Size: 224x224 (resized)
- Output: JSON structure

### Field Extractor

**CNN Architecture:**
```
Input: 224x224x3
    ↓
Conv2D(32) → ReLU → MaxPool
    ↓
Conv2D(64) → ReLU → MaxPool
    ↓
Conv2D(128) → ReLU → MaxPool
    ↓
Flatten → Dense(512) → Dropout(0.5)
    ↓
Output: Field Predictions
```

**Training:**
- Dataset: 10,000 synthetic samples
- Augmentation: Rotation, noise, blur
- Loss: Binary cross-entropy
- Optimizer: Adam
- Epochs: 50

## Monitoring Architecture

### Metrics Collection

```
Application
    ↓
Prometheus Client
    ↓
Prometheus Server
    ↓
Grafana Dashboards
```

**Key Metrics:**
- Request rate (requests/sec)
- Response time (p50, p95, p99)
- Error rate (%)
- Cache hit rate (%)
- Memory usage (MB)
- CPU usage (%)
- Analysis success rate (%)
- OCR vs ML usage (%)

### Logging Architecture

**Log Levels:**
- `DEBUG`: Detailed diagnostic info
- `INFO`: General informational messages
- `WARNING`: Warning messages
- `ERROR`: Error messages
- `CRITICAL`: Critical failures

**Log Destinations:**
- Console (stdout/stderr)
- File (`logs/app.log`)
- Audit log (`audit.log`)
- Structured logging (JSON format)

**Log Format:**
```
2024-03-29 10:30:00 - app.analyzers.certificate_analyzer - INFO - Starting AI analysis for req_xyz789
```

## Error Handling Strategy

### Error Hierarchy

```
BaseException
    ↓
Exception
    ├─→ HTTPException (FastAPI)
    │   ├─→ 400 Bad Request
    │   ├─→ 404 Not Found
    │   ├─→ 500 Internal Server Error
    │   └─→ 503 Service Unavailable
    │
    ├─→ ValidationError (Pydantic)
    ├─→ OCRError (Custom)
    ├─→ MLModelError (Custom)
    └─→ TamperDetectionError (Custom)
```

### Error Recovery

1. **Graceful Degradation**
   - ML fails → Fall back to OCR
   - Redis fails → Skip caching
   - Amharic OCR fails → Use English

2. **Retry Logic**
   - Transient errors: 3 retries with exponential backoff
   - Network errors: 2 retries
   - No retry for validation errors

3. **Circuit Breaker**
   - Track failure rates
   - Open circuit after 5 consecutive failures
   - Half-open after 60s
   - Close after 3 successes

## Deployment Architecture

### Docker Deployment

```
┌─────────────────────────────────────┐
│         Docker Host                  │
│                                      │
│  ┌────────────┐  ┌────────────┐    │
│  │    API     │  │   Redis    │    │
│  │ Container  │  │ Container  │    │
│  │ (Port 8001)│  │ (Port 6379)│    │
│  └────────────┘  └────────────┘    │
│                                      │
│  ┌────────────┐  ┌────────────┐    │
│  │ Monitoring │  │ Synthetic  │    │
│  │ (Grafana)  │  │ Generator  │    │
│  │ (Port 3000)│  │            │    │
│  └────────────┘  └────────────┘    │
└─────────────────────────────────────┘
```

### Production Deployment

```
┌─────────────────────────────────────┐
│         Internet                     │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│      Nginx (Reverse Proxy)          │
│      SSL/TLS Termination            │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│    Load Balancer (Optional)         │
└──────────────┬──────────────────────┘
               │
    ┌──────────┼──────────┐
    │          │          │
┌───▼───┐  ┌──▼───┐  ┌──▼───┐
│ API 1 │  │ API 2│  │ API 3│
└───┬───┘  └──┬───┘  └──┬───┘
    │         │         │
    └─────────┼─────────┘
              │
    ┌─────────▼─────────┐
    │   Redis Cluster   │
    └───────────────────┘
```

## Technology Stack

### Core Technologies

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| Web Framework | FastAPI | 0.104+ | REST API |
| ASGI Server | Uvicorn | 0.24+ | HTTP server |
| OCR Engine | Tesseract | 4.0+ | Text extraction |
| ML Framework | PyTorch | 2.1+ | Deep learning |
| Transformers | Hugging Face | 4.35+ | Donut model |
| Image Processing | OpenCV | 4.8+ | Computer vision |
| Caching | Redis | 7.0+ | Result caching |
| Validation | Pydantic | 2.5+ | Data validation |

### Supporting Libraries

| Library | Purpose |
|---------|---------|
| `numpy` | Numerical operations |
| `Pillow` | Image manipulation |
| `scikit-image` | Image analysis |
| `pdf2image` | PDF processing |
| `aiohttp` | Async HTTP client |
| `psutil` | System monitoring |
| `albumentations` | Data augmentation |
| `augraphy` | Document augmentation |

## Design Patterns

### 1. Singleton Pattern
- Analyzer instance
- Redis client
- Configuration settings

### 2. Factory Pattern
- OCR engine creation
- ML model initialization
- Recommendation engine

### 3. Strategy Pattern
- OCR routing strategies
- Detection methods
- Scoring algorithms

### 4. Observer Pattern
- Background tasks
- Event logging
- Metrics collection

### 5. Dependency Injection
- FastAPI dependencies
- Component initialization
- Testing mocks

## Testing Architecture

### Test Pyramid

```
        ┌─────────┐
        │   E2E   │ (10%)
        └─────────┘
      ┌─────────────┐
      │ Integration │ (30%)
      └─────────────┘
    ┌─────────────────┐
    │   Unit Tests    │ (60%)
    └─────────────────┘
```

### Test Coverage

- **Unit Tests**: Individual components
- **Integration Tests**: Component interactions
- **E2E Tests**: Full API workflows
- **Performance Tests**: Load and stress testing

### Test Structure

```
tests/
├── test_analyzer.py       # Analyzer tests
├── test_ocr.py           # OCR engine tests
├── test_synthetic.py     # Generator tests
├── test_api.py           # API endpoint tests
└── conftest.py           # Shared fixtures
```

## Future Enhancements

### Planned Features

1. **Database Integration**
   - PostgreSQL for persistent storage
   - Analysis history
   - Provider statistics

2. **Advanced ML Models**
   - Custom fine-tuned Donut
   - Ensemble models
   - Active learning

3. **Real-time Processing**
   - WebSocket support
   - Streaming analysis
   - Progress updates

4. **Enhanced Security**
   - OAuth2 authentication
   - Role-based access control
   - Audit logging

5. **Multi-region Support**
   - CDN integration
   - Regional deployments
   - Data residency compliance

6. **Advanced Analytics**
   - Fraud pattern detection
   - Provider risk scoring
   - Trend analysis

## Performance Benchmarks

### Target Metrics

| Metric | Target | Current |
|--------|--------|---------|
| Response Time (p95) | < 5s | ~3s |
| Throughput | 100 req/min | 80 req/min |
| Memory Usage | < 6GB | ~4GB |
| CPU Usage | < 70% | ~50% |
| Cache Hit Rate | > 40% | ~42% |
| Error Rate | < 1% | ~0.5% |

### Optimization Opportunities

1. **Model Quantization**: Reduce model size by 4x
2. **GPU Acceleration**: 10x faster ML inference
3. **Batch Processing**: Process multiple certificates together
4. **CDN Caching**: Cache static assets
5. **Database Indexing**: Faster query performance

---

**Architecture Version**: 1.0  
**Last Updated**: March 2024  
**Status**: Production Ready
