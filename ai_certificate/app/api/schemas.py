from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, Any, List, Optional, Union, Tuple
from datetime import datetime

class AnalysisRequest(BaseModel):
    """Request schema for certificate analysis"""
    document_url: Optional[str] = Field(None, description="URL of document to analyze")
    provider_id: str = Field(..., description="Provider identifier")
    language_hint: Optional[str] = Field(None, description="Language hint (eng/amh)")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "document_url": "https://example.com/certificate.pdf",
                "provider_id": "provider_123",
                "language_hint": "eng"
            }
        }
    )

# Sub-models for nested structures
class ExtractedDataField(BaseModel):
    """Individual extracted field"""
    text: str
    confidence: Optional[float] = None
    bbox: Optional[List[int]] = None

class ExtractedDataResponse(BaseModel):
    """Response for extracted data"""
    fields: Optional[Dict[str, Any]] = Field(default_factory=dict)
    raw_text: Optional[Dict[str, Any]] = Field(default_factory=dict)
    confidence_scores: Optional[Dict[str, float]] = Field(default_factory=dict)
    field_regions: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    present_fields: Optional[Dict[str, float]] = Field(default_factory=dict)
    field_confidence: Optional[Dict[str, float]] = Field(default_factory=dict)
    spatial_features_shape: Optional[List[int]] = None  # Changed from tuple to List[int]
    processing_time: Optional[float] = None
    success: Optional[bool] = None
    extracted_text: Optional[Dict[str, Any]] = Field(default_factory=dict)

class QualityMetricsResponse(BaseModel):
    """Quality metrics response"""
    ocr_confidence: float = 0.0
    tampering_confidence: float = 0.0
    page_count: int = 0
    average_entropy: float = 0.0
    valid_page_count: Optional[int] = 0
    failed_pages: Optional[int] = 0
    ml_confidence: Optional[float] = None
    extraction_method: Optional[str] = None
    script_detected: Optional[str] = None

class FlagsResponse(BaseModel):
    """Analysis flags"""
    tampering_detected: bool = False
    low_quality_scan: bool = False
    incomplete_fields: bool = False
    multiple_pages: bool = False
    suspicious_patterns: bool = False
    expired_certificate: bool = False
    analysis_failed: bool = False
    ml_used: Optional[bool] = None
    low_confidence_extraction: Optional[bool] = None
    mixed_language: Optional[bool] = None
    potential_forgery: Optional[bool] = None

class PageSummaryResponse(BaseModel):
    """Page summary"""
    page: int
    tampering_detected: bool
    extraction_method: Optional[str] = None
    script: Optional[str] = None
    status: Optional[str] = None
    ocr_confidence: Optional[float] = None

class ModelMetadataResponse(BaseModel):
    """Model metadata"""
    version: str
    config_hash: str
    use_ml: Optional[bool] = None
    thresholds: Dict[str, float]

class AnalysisResponse(BaseModel):
    """Response schema for certificate analysis"""
    analysis_id: str = Field(..., description="Unique analysis ID")
    timestamp: str = Field(..., description="Analysis timestamp")
    provider_id: str = Field(..., description="Provider identifier")
    request_id: Optional[str] = Field(None, description="Request identifier")
    
    extracted_data: Union[Dict[str, Any], ExtractedDataResponse] = Field(
        ..., 
        description="Extracted certificate data"
    )
    authenticity_score: float = Field(
        ..., 
        ge=0.0, 
        le=1.0, 
        description="Authenticity score (0.0-1.0)"
    )
    status: str = Field(..., description="Analysis status")
    admin_action: str = Field(..., description="Recommended admin action")
    
    quality_metrics: Union[Dict[str, Any], QualityMetricsResponse] = Field(
        default_factory=dict, 
        description="Quality metrics"
    )
    flags: Union[Dict[str, Any], FlagsResponse] = Field(
        default_factory=dict, 
        description="Analysis flags"
    )
    
    processing_time: float = Field(
        ..., 
        ge=0.0, 
        description="Processing time in seconds"
    )
    model_version: str = Field(..., description="Model version used")
    config_hash: str = Field(..., description="Configuration hash")
    
    cache_hit: bool = Field(False, description="Whether result was cached")
    redis_available: bool = Field(True, description="Redis availability")
    cache_stored: Optional[bool] = Field(None, description="Cache storage status")
    
    page_summaries: List[Union[Dict[str, Any], PageSummaryResponse]] = Field(
        default_factory=list,
        description="Page analysis summaries"
    )
    recommendations: List[str] = Field(
        default_factory=list,
        description="Recommendations based on analysis"
    )
    
    # New fields from your analyzer
    analysis_mode: Optional[str] = Field(None, description="Analysis mode used")
    source_type: Optional[str] = Field(None, description="Source type (upload/url)")
    model_metadata: Optional[Union[Dict[str, Any], ModelMetadataResponse]] = Field(
        None, 
        description="Model metadata"
    )
    error: Optional[str] = Field(None, description="Error message if failed")
    
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_schema_extra={
            "example": {
                "analysis_id": "anal_abc123def456",
                "timestamp": "2024-01-15T10:30:00Z",
                "provider_id": "provider_123",
                "request_id": "req_789",
                "extracted_data": {
                    "fields": {
                        "name": "John Smith",
                        "student_id": "STU12345"
                    },
                    "present_fields": {
                        "name": 0.95,
                        "student_id": 0.87
                    },
                    "field_confidence": {
                        "name": 0.95,
                        "student_id": 0.87
                    },
                    "processing_time": 4.37,
                    "success": True,
                    "spatial_features_shape": [1, 512, 16, 16]
                },
                "authenticity_score": 0.85,
                "status": "Pending Admin Review",
                "admin_action": "approve",
                "quality_metrics": {
                    "ocr_confidence": 0.92,
                    "tampering_confidence": 0.15,
                    "page_count": 1,
                    "average_entropy": 7.2,
                    "ml_confidence": 0.78,
                    "extraction_method": "hybrid_ai"
                },
                "flags": {
                    "tampering_detected": False,
                    "low_quality_scan": False,
                    "incomplete_fields": False,
                    "ml_used": True
                },
                "processing_time": 2.34,
                "model_version": "2024.2.0-ai-hybrid",
                "config_hash": "abc123def456",
                "cache_hit": False,
                "redis_available": True,
                "page_summaries": [
                    {
                        "page": 1,
                        "tampering_detected": False,
                        "extraction_method": "hybrid_ai",
                        "script": "latin"
                    }
                ],
                "recommendations": [
                    "Certificate appears valid - proceed with verification"
                ],
                "analysis_mode": "hybrid_ai",
                "source_type": "upload",
                "model_metadata": {
                    "version": "2024.2.0-ai-hybrid",
                    "config_hash": "abc123def456",
                    "use_ml": True,
                    "thresholds": {
                        "reject": 0.65,
                        "ml_confidence": 0.6
                    }
                }
            }
        }
    )

class HealthResponse(BaseModel):
    """Health check response"""
    status: str = Field(..., description="Service status")
    timestamp: str = Field(..., description="Check timestamp")
    version: str = Field(..., description="Service version")
    
    components: Optional[Dict[str, Any]] = Field(
        None, 
        description="Component statuses"
    )
    errors: Optional[List[str]] = Field(
        None, 
        description="Error messages"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "timestamp": "2024-01-15T10:30:00Z",
                "version": "2024.2.0-ai-hybrid",
                "components": {
                    "tamper_detector": True,
                    "script_detector": True,
                    "ocr_router": True,
                    "image_processor": True,
                    "donut_model": True,
                    "ml_extractor": True,
                    "redis_available": True
                }
            }
        }
    )

class ErrorResponse(BaseModel):
    """Error response schema"""
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Error details")
    timestamp: str = Field(..., description="Error timestamp")
    path: Optional[str] = Field(None, description="API path")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error": "Analysis failed",
                "detail": "Failed to extract text from document",
                "timestamp": "2024-01-15T10:30:00Z",
                "path": "/api/v1/analyze/upload"
            }
        }
    )

class SyntheticGenerationRequest(BaseModel):
    """Request for synthetic data generation"""
    num_samples: int = Field(
        1000, 
        ge=1, 
        le=100000, 
        description="Number of samples"
    )
    tampering_ratio: float = Field(
        0.2, 
        ge=0.0, 
        le=1.0, 
        description="Tampering ratio"
    )
    languages: List[str] = Field(
        ["eng", "amh"], 
        description="Languages to generate"
    )
    certificate_types: List[str] = Field(
        ["university", "training"], 
        description="Certificate types"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "num_samples": 1000,
                "tampering_ratio": 0.2,
                "languages": ["eng", "amh"],
                "certificate_types": ["university", "training"]
            }
        }
    )

class SyntheticGenerationResponse(BaseModel):
    """Response for synthetic data generation"""
    status: str = Field(..., description="Generation status")
    samples_generated: int = Field(..., description="Number of samples generated")
    output_dir: str = Field(..., description="Output directory")
    tampering_ratio: float = Field(..., description="Applied tampering ratio")
    processing_time: float = Field(..., description="Processing time in seconds")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "success",
                "samples_generated": 1000,
                "output_dir": "data/training/synthetic",
                "tampering_ratio": 0.2,
                "processing_time": 125.7
            }
        }
    )

# Helper function to convert analyzer output to response
def analyzer_to_response(analyzer_result: Dict[str, Any]) -> AnalysisResponse:
    """Convert analyzer result to Pydantic response"""
    
    # Get extracted data
    extracted_data = analyzer_result.get("extracted_data", {})
    
    # Ensure spatial_features_shape is a list if it's a tuple
    if isinstance(extracted_data, dict) and "spatial_features_shape" in extracted_data:
        if isinstance(extracted_data["spatial_features_shape"], tuple):
            extracted_data["spatial_features_shape"] = list(extracted_data["spatial_features_shape"])
    
    # Convert to ExtractedDataResponse if needed
    if isinstance(extracted_data, dict) and extracted_data:
        # Check if this looks like it should be an ExtractedDataResponse
        if any(key in extracted_data for key in ["fields", "raw_text", "confidence_scores", 
                                                 "field_regions", "present_fields", "field_confidence",
                                                 "spatial_features_shape", "processing_time", "success", 
                                                 "extracted_text"]):
            try:
                extracted_data = ExtractedDataResponse(**extracted_data)
            except Exception:
                # Keep as dict if conversion fails
                pass
    
    # Ensure quality_metrics is dict or QualityMetricsResponse
    quality_metrics = analyzer_result.get("quality_metrics", {})
    if isinstance(quality_metrics, dict) and quality_metrics:
        try:
            quality_metrics = QualityMetricsResponse(**quality_metrics)
        except Exception:
            pass
    
    # Ensure flags is dict or FlagsResponse
    flags = analyzer_result.get("flags", {})
    if isinstance(flags, dict) and flags:
        try:
            flags = FlagsResponse(**flags)
        except Exception:
            pass
    
    # Ensure page_summaries is list of proper objects
    page_summaries = analyzer_result.get("page_summaries", [])
    formatted_page_summaries = []
    for summary in page_summaries if isinstance(page_summaries, list) else []:
        if isinstance(summary, dict):
            try:
                formatted_page_summaries.append(PageSummaryResponse(**summary))
            except Exception:
                formatted_page_summaries.append(summary)
        else:
            formatted_page_summaries.append(summary)
    
    # Ensure model_metadata is properly formatted
    model_metadata = analyzer_result.get("model_metadata")
    if isinstance(model_metadata, dict) and model_metadata:
        try:
            model_metadata = ModelMetadataResponse(**model_metadata)
        except Exception:
            pass
    
    return AnalysisResponse(
        analysis_id=analyzer_result.get("analysis_id", ""),
        timestamp=analyzer_result.get("timestamp", datetime.now().isoformat()),
        provider_id=analyzer_result.get("provider_id", ""),
        request_id=analyzer_result.get("request_id"),
        extracted_data=extracted_data,
        authenticity_score=analyzer_result.get("authenticity_score", 0.0),
        status=analyzer_result.get("status", "failed"),
        admin_action=analyzer_result.get("admin_action", "reject"),
        quality_metrics=quality_metrics,
        flags=flags,
        processing_time=analyzer_result.get("processing_time", 0.0),
        model_version=analyzer_result.get("model_version", ""),
        config_hash=analyzer_result.get("config_hash", ""),
        cache_hit=analyzer_result.get("cache_hit", False),
        redis_available=analyzer_result.get("redis_available", False),
        cache_stored=analyzer_result.get("cache_stored"),
        page_summaries=formatted_page_summaries,
        recommendations=analyzer_result.get("recommendations", []),
        analysis_mode=analyzer_result.get("analysis_mode"),
        source_type=analyzer_result.get("source_type"),
        model_metadata=model_metadata,
        error=analyzer_result.get("error")
    )
# from pydantic import BaseModel, Field
# from typing import Dict, Any, List, Optional
# from datetime import datetime

# class AnalysisRequest(BaseModel):
#     """Request schema for certificate analysis"""
#     document_url: Optional[str] = Field(None, description="URL of document to analyze")
#     provider_id: str = Field(..., description="Provider identifier")
#     language_hint: Optional[str] = Field(None, description="Language hint (eng/amh)")
    
#     class Config:
#         schema_extra = {
#             "example": {
#                 "document_url": "https://example.com/certificate.pdf",
#                 "provider_id": "provider_123",
#                 "language_hint": "eng"
#             }
#         }

# class AnalysisResponse(BaseModel):
#     """Response schema for certificate analysis"""
#     analysis_id: str = Field(..., description="Unique analysis ID")
#     timestamp: str = Field(..., description="Analysis timestamp")
#     provider_id: str = Field(..., description="Provider identifier")
#     request_id: Optional[str] = Field(None, description="Request identifier")
    
#     extracted_data: Dict[str, str] = Field(..., description="Extracted certificate data")
#     authenticity_score: float = Field(..., description="Authenticity score (0.0-1.0)")
#     status: str = Field(..., description="Analysis status")
#     admin_action: str = Field(..., description="Recommended admin action")
    
#     quality_metrics: Dict[str, Any] = Field(..., description="Quality metrics")
#     flags: Dict[str, bool] = Field(..., description="Analysis flags")
    
#     processing_time: float = Field(..., description="Processing time in seconds")
#     model_version: str = Field(..., description="Model version used")
#     config_hash: str = Field(..., description="Configuration hash")
    
#     cache_hit: bool = Field(False, description="Whether result was cached")
#     redis_available: bool = Field(True, description="Redis availability")
    
#     page_summaries: List[Dict[str, Any]] = Field(default_factory=list)
#     recommendations: List[str] = Field(default_factory=list)
    
#     class Config:
#         schema_extra = {
#             "example": {
#                 "analysis_id": "anal_abc123def456",
#                 "timestamp": "2024-01-15T10:30:00Z",
#                 "provider_id": "provider_123",
#                 "extracted_data": {
#                     "name": "John Smith",
#                     "student_id": "STU12345",
#                     "university": "University of Example",
#                     "course": "Computer Science",
#                     "gpa": "3.75",
#                     "issue_date": "2023-06-15"
#                 },
#                 "authenticity_score": 0.85,
#                 "status": "Pending Admin Review",
#                 "admin_action": "approve",
#                 "quality_metrics": {
#                     "ocr_confidence": 0.92,
#                     "tampering_confidence": 0.15,
#                     "page_count": 1,
#                     "average_entropy": 7.2
#                 },
#                 "flags": {
#                     "tampering_detected": False,
#                     "low_quality_scan": False,
#                     "incomplete_fields": False
#                 },
#                 "processing_time": 2.34,
#                 "model_version": "2024.2.0",
#                 "config_hash": "abc123def456"
#             }
#         }

# class HealthResponse(BaseModel):
#     """Health check response"""
#     status: str = Field(..., description="Service status")
#     timestamp: str = Field(..., description="Check timestamp")
#     version: str = Field(..., description="Service version")
    
#     components: Optional[Dict[str, str]] = Field(None, description="Component statuses")
#     errors: Optional[List[str]] = Field(None, description="Error messages")
    
#     class Config:
#         schema_extra = {
#             "example": {
#                 "status": "healthy",
#                 "timestamp": "2024-01-15T10:30:00Z",
#                 "version": "2024.2.0",
#                 "components": {
#                     "redis": "connected",
#                     "ocr_engine": "ready",
#                     "tamper_detector": "ready"
#                 }
#             }
#         }

# class ErrorResponse(BaseModel):
#     """Error response schema"""
#     error: str = Field(..., description="Error message")
#     detail: Optional[str] = Field(None, description="Error details")
#     timestamp: str = Field(..., description="Error timestamp")
    
#     class Config:
#         schema_extra = {
#             "example": {
#                 "error": "Analysis failed",
#                 "detail": "Failed to extract text from document",
#                 "timestamp": "2024-01-15T10:30:00Z"
#             }
#         }

# class SyntheticGenerationRequest(BaseModel):
#     """Request for synthetic data generation"""
#     num_samples: int = Field(1000, ge=1, le=100000, description="Number of samples")
#     tampering_ratio: float = Field(0.2, ge=0.0, le=1.0, description="Tampering ratio")
#     languages: List[str] = Field(["eng", "amh"], description="Languages to generate")
#     certificate_types: List[str] = Field(["university", "training"], description="Certificate types")
    
#     class Config:
#         schema_extra = {
#             "example": {
#                 "num_samples": 1000,
#                 "tampering_ratio": 0.2,
#                 "languages": ["eng", "amh"],
#                 "certificate_types": ["university", "training"]
#             }
#         }

# class SyntheticGenerationResponse(BaseModel):
#     """Response for synthetic data generation"""
#     status: str = Field(..., description="Generation status")
#     samples_generated: int = Field(..., description="Number of samples generated")
#     output_dir: str = Field(..., description="Output directory")
#     tampering_ratio: float = Field(..., description="Applied tampering ratio")
#     processing_time: float = Field(..., description="Processing time in seconds")
    
#     class Config:
#         schema_extra = {
#             "example": {
#                 "status": "success",
#                 "samples_generated": 1000,
#                 "output_dir": "data/training/synthetic",
#                 "tampering_ratio": 0.2,
#                 "processing_time": 125.7
#             }
#         }