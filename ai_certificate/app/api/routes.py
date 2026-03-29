from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from typing import Optional
import uuid
import logging
from datetime import datetime
from app.analyzers.certificate_analyzer import ProductionCertificateAnalyzer
from app.utils.cache import get_redis_client
from .schemas import (
    AnalysisRequest, AnalysisResponse, HealthResponse, ErrorResponse,
    SyntheticGenerationRequest, SyntheticGenerationResponse,
    analyzer_to_response  # Import the helper function
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["certificate-analysis"])

# Initialize analyzer (singleton)
_analyzer = None

def get_analyzer():
    """Get analyzer instance (singleton)"""
    global _analyzer
    if _analyzer is None:
        _analyzer = ProductionCertificateAnalyzer(use_ml=True)
    return _analyzer

@router.get("/health", response_model=HealthResponse)
async def health_check(
    analyzer = Depends(get_analyzer)
):
    """Health check endpoint"""
    try:
        #health_data = await analyzer.health_check()
        health_data = analyzer.health_check() 
        health_data["timestamp"] = datetime.now().isoformat()
        health_data["version"] = analyzer.model_version
        # Check Redis health
        redis_client = await get_redis_client()
        redis_stats = await redis_client.get_stats()
        
        health_data["components"]["redis"] = redis_stats.get("status", "unknown")
        
        return HealthResponse(**health_data)
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error="Health check failed",
                detail=str(e),
                timestamp=datetime.now().isoformat()
            ).dict()
        )

@router.post("/analyze/upload", response_model=AnalysisResponse)
async def analyze_upload(
    file: UploadFile = File(...),
    provider_id: str = "default",
    language_hint: Optional[str] = None,
    background_tasks: BackgroundTasks = None,
    analyzer = Depends(get_analyzer)
):
    """Analyze uploaded certificate"""
    try:
        # Validate file
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")
        
        # Check file size
        content = await file.read()
        if len(content) > 100 * 1024 * 1024:  
            raise HTTPException(status_code=400, detail="File too large (max 100MB)")
        
        # Reset file pointer
        await file.seek(0)
        
        # Generate request ID
        request_id = str(uuid.uuid4())[:12]
        
        logger.info(f"Processing upload: {file.filename}, request_id: {request_id}")
        
        # Analyze certificate
        result = await analyzer.analyze_certificate_file(file, provider_id, request_id)
        
        # Convert to proper response format using the helper function
        response = analyzer_to_response(result)
        
        # Store in background if needed (use the original result dict)
        if background_tasks and result.get('authenticity_score', 0) > 0.5:
            background_tasks.add_task(
                store_analysis_result,
                result,
                "upload"
            )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/analyze/url", response_model=AnalysisResponse)
async def analyze_url(
    request: AnalysisRequest,
    background_tasks: BackgroundTasks = None,
    analyzer = Depends(get_analyzer)
):
    """Analyze certificate from URL"""
    try:
        if not request.document_url:
            raise HTTPException(status_code=400, detail="document_url is required")
        
        request_id = str(uuid.uuid4())[:12]
        
        logger.info(f"Processing URL: {request.document_url[:100]}...")
        
        # Analyze certificate
        result = await analyzer.analyze_certificate_url(
            request.document_url,
            request.provider_id,
            request_id
        )
        
        # Convert to proper response format using the helper function
        response = analyzer_to_response(result)
        
        # Store in background (use the original result dict)
        if background_tasks:
            background_tasks.add_task(
                store_analysis_result,
                result,
                "url"
            )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"URL analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate/synthetic", response_model=SyntheticGenerationResponse)
async def generate_synthetic_data(
    request: SyntheticGenerationRequest,
    background_tasks: BackgroundTasks
):
    """Generate synthetic training data"""
    try:
        from app.analyzers.synthetic_generator import generate_optimized_dataset
        
        # Start generation in background
        background_tasks.add_task(
            generate_synthetic_background,
            request.num_samples,
            request.tampering_ratio
        )
        
        return SyntheticGenerationResponse(
            status="started",
            samples_generated=0,
            output_dir="data/training/synthetic",
            tampering_ratio=request.tampering_ratio,
            processing_time=0.0
        )
        
    except Exception as e:
        logger.error(f"Synthetic generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/statistics")
async def get_statistics(
    analyzer = Depends(get_analyzer)
):
    """Get system statistics"""
    try:
        # Get OCR statistics
        ocr_stats = analyzer.ocr_router.get_statistics() if hasattr(analyzer, 'ocr_router') else {}
        
        # Get Redis statistics
        redis_client = await get_redis_client()
        redis_stats = await redis_client.get_stats()
        
        return {
            "timestamp": datetime.now().isoformat(),
            "ocr_statistics": ocr_stats,
            "redis_statistics": redis_stats,
            "analyzer_version": analyzer.model_version
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def store_analysis_result(result: dict, source: str):
    """Store analysis result in database (async)"""
    try:
        # This would connect to your database
        # For now, just log it
        logger.info(f"Storing analysis result for {result.get('analysis_id')} from {source}")
        
        # Example: Store in Redis for quick access
        redis_client = await get_redis_client()
        await redis_client.set(
            f"analysis:{result['analysis_id']}",
            result,
            ttl=86400  # 24 hours
        )
        
    except Exception as e:
        logger.error(f"Failed to store analysis result: {e}")

async def generate_synthetic_background(num_samples: int, tampering_ratio: float):
    """Background task for synthetic data generation"""
    try:
        from app.analyzers.synthetic_generator import generate_optimized_dataset
        
        logger.info(f"Starting synthetic data generation: {num_samples} samples")
        
        output_dir = generate_optimized_dataset(
            num_samples=num_samples,
            tampering_ratio=tampering_ratio,
            use_parallel=True
        )
        
        logger.info(f"Synthetic data generation complete: {output_dir}")
        
    except Exception as e:
        logger.error(f"Synthetic generation background task failed: {e}")