# API Documentation - AI Certificate Analyzer

Complete API reference for the AI Certificate Analyzer service.

## Base URL

```
Development: http://localhost:8001
Production: https://your-domain.com
```

## Authentication

Currently, the API is open for development. For production, implement API key authentication:

```http
X-API-Key: your-api-key-here
```

## Common Headers

```http
Content-Type: application/json
Accept: application/json
```

## Endpoints

### 1. Root Endpoint

Get service information and available endpoints.

**Request:**
```http
GET /
```

**Response:**
```json
{
  "service": "AI Certificate Analyzer",
  "version": "2024.2.0",
  "status": "operational",
  "endpoints": {
    "health": "/api/v1/health",
    "analyze_upload": "/api/v1/analyze/upload",
    "analyze_url": "/api/v1/analyze/url",
    "generate_synthetic": "/api/v1/generate/synthetic",
    "statistics": "/api/v1/statistics"
  },
  "features": [
    "Hybrid OCR/ML analysis",
    "English & Amharic support",
    "Script detection",
    "Tampering detection",
    "Synthetic data generation",
    "Production-ready API",
    "Service provider verification dashboard"
  ]
}
```

---

### 2. Health Check

Check system health and component status.

**Request:**
```http
GET /api/v1/health
```

**Response:**
```json
{
  "status": "healthy",
  "model_version": "2024.2.0-ai-hybrid",
  "use_ml": true,
  "components": {
    "tamper_detector": true,
    "script_detector": true,
    "ocr_router": true,
    "image_processor": true,
    "donut_model": true,
    "ml_extractor": true,
    "redis": "connected"
  },
  "redis_available": true,
  "timestamp": "2024-03-29T10:30:00Z",
  "version": "2024.2.0-ai-hybrid"
}
```

**Status Codes:**
- `200 OK`: System healthy
- `503 Service Unavailable`: System unhealthy

---

### 3. Performance Health

Get system performance metrics.

**Request:**
```http
GET /health/performance
```

**Response:**
```json
{
  "status": "healthy",
  "memory_usage_percent": 45.2,
  "available_memory_mb": 4096.5,
  "cpu_percent": 23.4,
  "thread_pool_size": 2,
  "recommendations": []
}
```

**Status Values:**
- `healthy`: Memory < 85%
- `warning`: Memory >= 85%

---

### 4. Analyze Certificate (File Upload)

Analyze a certificate from uploaded file.

**Request:**
```http
POST /api/v1/analyze/upload?provider_id=provider_123&language_hint=english
Content-Type: multipart/form-data

file: <binary-file-data>
```

**Parameters:**
- `file` (required): Certificate file (PDF, JPG, PNG, TIFF)
- `provider_id` (optional): Service provider identifier (default: "default")
- `language_hint` (optional): "english" | "amharic" | null

**Response:**
```json
{
  "analysis_id": "anal_a1b2c3d4e5f6",
  "timestamp": "2024-03-29T10:30:00Z",
  "provider_id": "provider_123",
  "request_id": "req_xyz789",
  "authenticity_score": 0.87,
  "status": "Pending Admin Review",
  "admin_action": "approve",
  "extracted_data": {
    "fields": {
      "name": "John Doe",
      "student_id": "STU123456",
      "university": "Example University",
      "course": "Computer Science",
      "gpa": "3.75",
      "issue_date": "2023-06-15"
    },
    "raw_text": {...},
    "confidence_scores": {...},
    "field_confidence": {
      "name": 0.95,
      "student_id": 0.92,
      "university": 0.88
    },
    "success": true
  },
  "quality_metrics": {
    "ocr_confidence": 0.92,
    "tampering_confidence": 0.05,
    "ml_confidence": 0.88,
    "extraction_method": "ml",
    "script_detected": "english"
  },
  "flags": {
    "tampering_detected": false,
    "ml_used": true,
    "low_confidence_extraction": false,
    "mixed_language": false,
    "potential_forgery": false
  },
  "page_summaries": [
    {
      "page": 0,
      "tampering_detected": false,
      "extraction_method": "ml",
      "script": "english"
    }
  ],
  "model_metadata": {
    "version": "2024.2.0-ai-hybrid",
    "config_hash": "a1b2c3d4e5f6g7h8",
    "use_ml": true,
    "thresholds": {
      "reject": 0.65,
      "ml_confidence": 0.6
    }
  },
  "recommendations": [
    "Certificate appears valid - proceed with verification"
  ],
  "recommendation_result": {
    "recommendation": "APPROVE",
    "risk_level": "LOW",
    "confidence": 0.87,
    "reasons": [
      "High authenticity score (0.87)",
      "All required fields present",
      "No tampering detected"
    ]
  },
  "processing_time": 2.345,
  "analysis_mode": "hybrid_ai",
  "cache_hit": false
}
```

**Status Codes:**
- `200 OK`: Analysis completed
- `400 Bad Request`: Invalid file or parameters
- `413 Payload Too Large`: File exceeds size limit
- `500 Internal Server Error`: Analysis failed

---

### 5. Analyze Certificate (URL)

Analyze a certificate from a URL.

**Request:**
```http
POST /api/v1/analyze/url
Content-Type: application/json

{
  "document_url": "https://example.com/certificate.pdf",
  "provider_id": "provider_123",
  "language_hint": "english"
}
```

**Request Body:**
```json
{
  "document_url": "string (required)",
  "provider_id": "string (optional, default: 'default')",
  "language_hint": "string (optional, 'english' | 'amharic')"
}
```

**Response:**
Same format as `/analyze/upload` endpoint.

**Status Codes:**
- `200 OK`: Analysis completed
- `400 Bad Request`: Invalid URL or parameters
- `408 Request Timeout`: Download timeout
- `500 Internal Server Error`: Analysis failed

---

### 6. Direct Analysis (Optimized)

Optimized endpoint with admin-friendly summary.

**Request (File Upload):**
```http
POST /api/v1/analyze/direct?provider_id=provider_123&request_id=req_456&file_upload=true
Content-Type: multipart/form-data

file: <binary-file-data>
```

**Request (URL):**
```http
POST /api/v1/analyze/direct?provider_id=provider_123&request_id=req_456&document_url=https://example.com/cert.pdf
```

**Parameters:**
- `provider_id` (required): Service provider identifier
- `request_id` (required): Unique request identifier
- `file_upload` (optional): Set to `true` for file upload
- `document_url` (optional): URL for remote document

**Response:**
```json
{
  "success": true,
  "analysis_id": "anal_a1b2c3d4e5f6",
  "cleaned_fields": {
    "student_id": "STU123456",
    "name": "John Doe",
    "university": "Example University",
    "course": "Computer Science"
  },
  "full_analysis": {
    // Complete analysis result
  },
  "admin_summary": {
    "provider_id": "provider_123",
    "certificate_type": "Academic Certificate",
    "authenticity_score": 0.87,
    "extracted_information": {
      "provider_name": "John Doe",
      "skill_or_qualification": "Computer Science",
      "issuing_authority": "Example University",
      "validity_date": "2023-06-15",
      "certificate_number": "CERT123456",
      "license_class": ""
    },
    "verification_flags": {
      "tampering_detected": false,
      "low_quality_scan": false,
      "expired_certificate": false,
      "needs_manual_review": false,
      "high_risk_forgery": false
    },
    "status": "Pending Admin Review",
    "admin_action": "approve",
    "recommendations": [...],
    "quick_summary": "Computer Science - Academic Certificate | Issued by: Example University"
  },
  "metadata": {
    "provider_id": "provider_123",
    "request_id": "req_456",
    "analysis_mode": "hybrid_ai",
    "timestamp": "2024-03-29T10:30:00Z"
  }
}
```

---

### 7. Generate Synthetic Data

Generate synthetic training data for model improvement.

**Request:**
```http
POST /api/v1/generate/synthetic
Content-Type: application/json

{
  "num_samples": 1000,
  "tampering_ratio": 0.2,
  "languages": ["english", "amharic"],
  "certificate_types": ["university", "support_letter"]
}
```

**Request Body:**
```json
{
  "num_samples": "integer (required, 1-10000)",
  "tampering_ratio": "float (optional, 0.0-1.0, default: 0.2)",
  "languages": "array (optional, default: ['english', 'amharic'])",
  "certificate_types": "array (optional)"
}
```

**Response:**
```json
{
  "status": "started",
  "samples_generated": 0,
  "output_dir": "data/training/synthetic",
  "tampering_ratio": 0.2,
  "processing_time": 0.0
}
```

**Note:** Generation runs in background. Check output directory for progress.

---

### 8. System Statistics

Get system and cache statistics.

**Request:**
```http
GET /api/v1/statistics
```

**Response:**
```json
{
  "timestamp": "2024-03-29T10:30:00Z",
  "ocr_statistics": {
    "total_requests": 1523,
    "english_requests": 1200,
    "amharic_requests": 323,
    "average_confidence": 0.85,
    "cache_hit_rate": 0.42
  },
  "redis_statistics": {
    "status": "connected",
    "redis_version": "7.0.11",
    "used_memory": "45.2M",
    "connected_clients": 3,
    "total_analysis_cache": 1523,
    "total_certificate_cache": 856
  },
  "analyzer_version": "2024.2.0-ai-hybrid"
}
```

---

### 9. Get Analysis Status

Retrieve analysis result by ID.

**Request:**
```http
GET /api/v1/analyze/status/{analysis_id}
```

**Response:**
```json
{
  "message": "Analysis status endpoint",
  "note": "Implement database/cache lookup for analysis_id",
  "analysis_id": "anal_a1b2c3d4e5f6"
}
```

**Note:** This endpoint requires database implementation for persistent storage.

---

### 10. Recommendation Endpoint

Generate recommendation from analyzed certificate.

**Request:**
```http
POST /recommend?provider_id=provider_123
Content-Type: multipart/form-data

file: <binary-file-data>
```

**Response:**
```json
{
  "success": true,
  "analysis_id": "anal_a1b2c3d4e5f6",
  "recommendation": {
    "recommendation": "APPROVE",
    "risk_level": "LOW",
    "confidence": 0.87,
    "reasons": [
      "High authenticity score (0.87)",
      "All required fields present",
      "No tampering detected"
    ],
    "validation_details": {
      "name": {"valid": true, "confidence": 0.95},
      "student_id": {"valid": true, "confidence": 0.92}
    },
    "timestamp": "2024-03-29T10:30:00Z"
  }
}
```

---

## Response Models

### AnalysisResponse

```typescript
interface AnalysisResponse {
  analysis_id: string;
  timestamp: string;
  provider_id: string;
  request_id: string;
  authenticity_score: number;  // 0.0 - 1.0
  status: "Approved" | "Rejected" | "Pending Admin Review" | "Analysis Failed";
  admin_action: "approve" | "reject" | "review";
  extracted_data: ExtractedData;
  quality_metrics: QualityMetrics;
  flags: Flags;
  page_summaries: PageSummary[];
  model_metadata: ModelMetadata;
  recommendations: string[];
  recommendation_result?: RecommendationResult;
  processing_time: number;
  analysis_mode: "hybrid_ai" | "ocr_only";
  cache_hit: boolean;
}
```

### ExtractedData

```typescript
interface ExtractedData {
  fields: {
    name?: string;
    student_id?: string;
    university?: string;
    course?: string;
    gpa?: string;
    issue_date?: string;
    certificate_number?: string;
    [key: string]: any;
  };
  raw_text: object;
  confidence_scores: object;
  field_confidence: {
    [field: string]: number;  // 0.0 - 1.0
  };
  success: boolean;
}
```

### QualityMetrics

```typescript
interface QualityMetrics {
  ocr_confidence: number;       // 0.0 - 1.0
  tampering_confidence: number; // 0.0 - 1.0
  ml_confidence: number;        // 0.0 - 1.0
  extraction_method: "ocr" | "ml";
  script_detected: "english" | "amharic" | "mixed" | "unknown";
}
```

### Flags

```typescript
interface Flags {
  tampering_detected: boolean;
  ml_used: boolean;
  low_confidence_extraction: boolean;
  mixed_language: boolean;
  potential_forgery: boolean;
}
```

### RecommendationResult

```typescript
interface RecommendationResult {
  recommendation: "APPROVE" | "REJECT" | "MANUAL_REVIEW";
  risk_level: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  confidence: number;  // 0.0 - 1.0
  reasons: string[];
  validation_details: {
    [field: string]: {
      valid: boolean;
      confidence: number;
      issues?: string[];
    };
  };
  timestamp: string;
}
```

## Error Responses

### Standard Error Format

```json
{
  "error": "Error message",
  "detail": "Detailed error description",
  "path": "/api/v1/analyze/upload",
  "timestamp": "2024-03-29T10:30:00Z"
}
```

### Common Error Codes

| Code | Message | Description |
|------|---------|-------------|
| 400 | Bad Request | Invalid parameters or file format |
| 401 | Unauthorized | Missing or invalid API key |
| 403 | Forbidden | Access denied |
| 404 | Not Found | Endpoint or resource not found |
| 408 | Request Timeout | Operation took too long |
| 413 | Payload Too Large | File exceeds size limit |
| 422 | Unprocessable Entity | Validation error |
| 500 | Internal Server Error | Server-side error |
| 503 | Service Unavailable | Service not ready |

## Rate Limiting

Current implementation does not enforce rate limits. For production, implement rate limiting:

```
Rate Limit: 100 requests per minute per IP
Burst: 20 requests
```

Headers returned:
```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1234567890
```

## Caching

The API uses Redis for caching analysis results:

- **Cache Key Format**: `ai_upload:{provider_id}:{file_hash}`
- **TTL**: 3600 seconds (1 hour)
- **Cache Hit**: Indicated by `cache_hit: true` in response

To bypass cache, use a different `provider_id` or `request_id`.

## Request Examples

### cURL Examples

**Upload Certificate:**
```bash
curl -X POST "http://localhost:8001/api/v1/analyze/upload?provider_id=test_provider" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@certificate.pdf" \
  | jq .
```

**Analyze from URL:**
```bash
curl -X POST "http://localhost:8001/api/v1/analyze/url" \
  -H "Content-Type: application/json" \
  -d '{
    "document_url": "https://example.com/certificate.pdf",
    "provider_id": "test_provider"
  }' \
  | jq .
```

**Health Check:**
```bash
curl http://localhost:8001/api/v1/health | jq .
```

### Python Examples

```python
import requests

# Upload certificate
def analyze_certificate(file_path, provider_id):
    url = "http://localhost:8001/api/v1/analyze/upload"
    
    with open(file_path, 'rb') as f:
        files = {'file': f}
        params = {'provider_id': provider_id}
        response = requests.post(url, files=files, params=params)
    
    return response.json()

# Analyze from URL
def analyze_url(document_url, provider_id):
    url = "http://localhost:8001/api/v1/analyze/url"
    
    payload = {
        'document_url': document_url,
        'provider_id': provider_id
    }
    response = requests.post(url, json=payload)
    
    return response.json()

# Usage
result = analyze_certificate('certificate.pdf', 'provider_123')
print(f"Score: {result['authenticity_score']}")
print(f"Status: {result['status']}")
```

### JavaScript/TypeScript Examples

```typescript
// Upload certificate
async function analyzeCertificate(file: File, providerId: string) {
  const formData = new FormData();
  formData.append('file', file);
  
  const response = await fetch(
    `http://localhost:8001/api/v1/analyze/upload?provider_id=${providerId}`,
    {
      method: 'POST',
      body: formData
    }
  );
  
  return await response.json();
}

// Analyze from URL
async function analyzeUrl(documentUrl: string, providerId: string) {
  const response = await fetch('http://localhost:8001/api/v1/analyze/url', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      document_url: documentUrl,
      provider_id: providerId
    })
  });
  
  return await response.json();
}

// Usage
const result = await analyzeCertificate(certificateFile, 'provider_123');
console.log('Authenticity Score:', result.authenticity_score);
console.log('Recommendations:', result.recommendations);
```

## Webhooks (Future Feature)

Configure webhooks to receive analysis results:

```json
{
  "webhook_url": "https://your-service.com/webhook",
  "events": ["analysis.completed", "analysis.failed"],
  "secret": "your-webhook-secret"
}
```

## Best Practices

### 1. File Upload
- Compress large files before upload
- Use PDF format for multi-page documents
- Ensure images are clear and well-lit
- Maximum file size: 10MB (configurable)

### 2. Error Handling
- Always check `success` field in response
- Implement retry logic with exponential backoff
- Handle timeout errors gracefully
- Log `analysis_id` for debugging

### 3. Performance
- Use caching when possible
- Batch multiple requests if needed
- Monitor `processing_time` in responses
- Check `/health/performance` regularly

### 4. Security
- Implement API key authentication in production
- Use HTTPS for all requests
- Validate file types before upload
- Sanitize user inputs

## Interactive Documentation

The API provides interactive documentation:

- **Swagger UI**: http://localhost:8001/docs
  - Try out endpoints directly
  - View request/response schemas
  - Test authentication

- **ReDoc**: http://localhost:8001/redoc
  - Clean, readable documentation
  - Searchable endpoint list
  - Detailed schema definitions

## SDK Support

### Python SDK (Recommended)

```python
from certanalyzer import CertificateAnalyzerClient

client = CertificateAnalyzerClient(
    base_url="http://localhost:8001",
    api_key="your-api-key"
)

# Analyze certificate
result = client.analyze_file('certificate.pdf', provider_id='provider_123')
print(result.authenticity_score)
```

### JavaScript/TypeScript SDK

```typescript
import { CertificateAnalyzerClient } from 'certanalyzer-js';

const client = new CertificateAnalyzerClient({
  baseUrl: 'http://localhost:8001',
  apiKey: 'your-api-key'
});

const result = await client.analyzeFile(file, 'provider_123');
console.log(result.authenticityScore);
```

**Note:** SDKs are planned for future releases.

## Versioning

The API uses semantic versioning:
- Current version: `v1`
- Base path: `/api/v1`

Breaking changes will increment the major version (e.g., `/api/v2`).

## Support

For API issues or questions:
- Check interactive docs: http://localhost:8001/docs
- Review logs: `logs/app.log`
- Open GitHub issue
- Email: api-support@example.com

---

**API Version**: v1  
**Last Updated**: March 2024  
**Status**: Production Ready
