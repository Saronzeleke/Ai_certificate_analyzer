from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
import logging
import time
import asyncio
from contextlib import asynccontextmanager
from fastapi import HTTPException
from app.api.routes import router as api_router
from app.utils.config import settings
from app.utils.cache import init_cache, close_cache
from app.analyzers.certificate_analyzer import ProductionCertificateAnalyzer
from concurrent.futures import ThreadPoolExecutor
from app.analyzers.recommendation_engine import create_recommendation_engine
from fastapi import FastAPI, Request, UploadFile, File
import json  
from app.utils.cache import init_cache, close_cache, redis_client
from datetime import datetime  
# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# === CRITICAL FIX 1: Global thread pool for CPU-bound tasks ===
executor = ThreadPoolExecutor(max_workers=2)  # Don't overload 8GB RAM

# === CRITICAL FIX 2: Global analyzer instance (SINGLETON) ===
analyzer_instance = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown events"""
    global analyzer_instance
    
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    
    # Initialize cache
    try:
        await init_cache()
        logger.info("Cache initialized")
    except Exception as e:
        logger.warning(f"Cache initialization failed: {e}")
    
    # === CRITICAL FIX: Initialize analyzer ONCE at startup ===
    try:
        analyzer_instance = ProductionCertificateAnalyzer(use_ml=settings.use_ml)
        health = analyzer_instance.health_check()
        if health.get("status") != "healthy":
            raise RuntimeError(f"Analyzer unhealthy: {health}")
        logger.info("Analyzer initialized and passed health check")
    except Exception as e:
        logger.error(f"Analyzer initialization failed: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down application")
    await close_cache()
    executor.shutdown(wait=True)  # Cleanup thread pool


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="AI-powered certificate analyzer with English/Amharic support",
    version=settings.app_version,
    docs_url="/docs",   
    redoc_url="/redoc", 
    lifespan=lifespan
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)


# Add request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    # Add warning if slow
    if process_time > 5:
        logger.warning(f"Slow request: {request.url.path} took {process_time:.2f}s")
    return response


# Include API router
app.include_router(api_router)


# Root endpoint
@app.get("/")
async def root():
    return {
        "service": settings.app_name,
        "version": settings.app_version,
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


# NEW: Enhanced analysis endpoint with admin summary
@app.get("/api/v1/analyze/status/{analysis_id}")
async def get_analysis_status(analysis_id: str):
    """
    Get analysis status and admin-friendly summary by analysis ID
    """
    try:
        return {
            "message": "Analysis status endpoint",
            "note": "Implement database/cache lookup for analysis_id",
            "analysis_id": analysis_id
        }
    except Exception as e:
        logger.error(f"Failed to get analysis status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# === CRITICAL FIX 3: Optimized direct endpoint ===
@app.post("/api/v1/analyze/direct")
async def analyze_direct(
    request: Request,
    provider_id: str,
    request_id: str,
    file_upload: bool = False,
    document_url: str = None
):
    """
    Clean direct analysis endpoint with CPU optimization for 8GB RAM
    Returns structured JSON with proper handling of missing fields.
    """
    global analyzer_instance

    if analyzer_instance is None:
        raise HTTPException(status_code=503, detail="Analyzer not initialized")

    try:
        loop = asyncio.get_event_loop()
        
        # === File or URL analysis ===
        if file_upload:
            form_data = await request.form()
            if "file" not in form_data:
                raise HTTPException(status_code=400, detail="No file provided")
            file = form_data["file"]

            full_result = await loop.run_in_executor(
                executor,
                lambda: asyncio.run(analyzer_instance.analyze_certificate_file(
                    file, provider_id, request_id
                ))
            )
        elif document_url:
            full_result = await loop.run_in_executor(
                executor,
                lambda: asyncio.run(analyzer_instance.analyze_certificate_url(
                    document_url, provider_id, request_id
                ))
            )
        else:
            raise HTTPException(status_code=400, detail="Either file_upload=True or document_url required")
        
        # === Create admin-friendly summary ===
        admin_summary = await loop.run_in_executor(
            executor,
            lambda: analyzer_instance.create_provider_summary(full_result)
        )

        # === Clean extracted fields ===
        extracted = full_result.get("extracted_data", {}).get("extracted_text", {})
        cleaned_fields = {
            "student_id": extracted.get("student_id") if extracted.get("student_id") and extracted.get("student_id").isdigit() else None,
            "name": extracted.get("name") or None,
            "university": extracted.get("university") or None,
            "course": extracted.get("course") or None
        }

        return {
            "success": True,
            "analysis_id": full_result.get("analysis_id"),
            "cleaned_fields": cleaned_fields,
            "full_analysis": full_result,
            "admin_summary": admin_summary,
            "metadata": {
                "provider_id": provider_id,
                "request_id": request_id,
                "analysis_mode": "hybrid_ai" if getattr(analyzer_instance, "use_ml", True) else "ocr_only",
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Direct analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
# @app.post("/api/v1/analyze/direct")
# async def analyze_direct(
#     request: Request,
#     provider_id: str,
#     request_id: str,
#     file_upload: bool = False,
#     document_url: str = None
# ):
#     """
#     Direct analysis endpoint optimized for 8GB RAM.
#     Returns both full AI output (internal) and a collapsed admin-friendly summary.
#     """
#     global analyzer_instance

#     if analyzer_instance is None:
#         raise HTTPException(status_code=503, detail="Analyzer not initialized")

#     try:
#         loop = asyncio.get_event_loop()

#         # Handle file upload
#         if file_upload:
#             form_data = await request.form()
#             if "file" not in form_data:
#                 raise HTTPException(status_code=400, detail="No file provided")
#             file = form_data["file"]

#             full_result = await loop.run_in_executor(
#                 executor,
#                 lambda: asyncio.run(analyzer_instance.analyze_certificate_file(file, provider_id, request_id))
#             )

#         # Handle URL analysis
#         elif document_url:
#             full_result = await loop.run_in_executor(
#                 executor,
#                 lambda: asyncio.run(analyzer_instance.analyze_certificate_url(document_url, provider_id, request_id))
#             )
#         else:
#             raise HTTPException(status_code=400, detail="Either file_upload=True or document_url required")

#         # Create admin-friendly summary
#         admin_summary = await loop.run_in_executor(
#             executor,
#             lambda: analyzer_instance.create_provider_summary(full_result)
#         )

#         # Collapse key info for clean API response
#         collapsed_output = {
#             "analysis_id": full_result.get("analysis_id"),
#             "timestamp": full_result.get("timestamp"),
#             "status": full_result.get("status"),
#             "admin_action": full_result.get("admin_action"),
#             "authenticity_score": full_result.get("authenticity_score"),
#             "recommendation": full_result.get("recommendations", ["No recommendation provided"]),
#             "fields": full_result.get("extracted_data", {}).get("extracted_text", {}),
#             "quality_metrics": full_result.get("quality_metrics", {}),
#             "processing_time": full_result.get("processing_time"),
#             "model_version": full_result.get("model_version")
#         }

#         return {
#             "success": True,
#             "provider_id": provider_id,
#             "request_id": request_id,
#             "analysis_mode": "hybrid_ai" if settings.use_ml else "ocr_only",
#             "collapsed_output": collapsed_output,
#             "full_analysis": full_result  
#         }

#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Direct analysis failed: {e}", exc_info=True)
#         raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
engine = create_recommendation_engine()

@app.post("/recommend")
async def recommend(file: UploadFile = File(...), provider_id: str = "default"):
    """Generate recommendation from analyzed certificate"""
    global analyzer_instance, engine
    
    if analyzer_instance is None:
        return {"success": False, "error": "Analyzer not initialized"}, 503
    
    try:
        # FIXED: Use analyzer_instance, not analyzer
        doc = await analyzer_instance.analyze_certificate(file, provider_id)
        
        if not isinstance(doc, dict):
            return {"success": False, "error": "Invalid analysis result"}, 500
        
        # SAFE extraction with multiple fallbacks
        authenticity_score = (
            doc.get("authenticity_score") or 
            doc.get("auth_score") or 
            doc.get("recommendation_result", {}).get("authenticity_score") or 
            0.5
        )
        
        extracted_fields = (
            doc.get("extracted_fields") or 
            doc.get("fields") or 
            doc.get("extracted_data", {}).get("extracted_text") or 
            {}
        )
        
        # Generate recommendation
        recommendation = engine.generate_recommendation(
            authenticity_score=float(authenticity_score),
            extracted_fields=extracted_fields,
            tampering_detected=bool(doc.get("tampering_detected", False)),
            ocr_confidence=doc.get("ocr_confidence"),
            ml_confidence=doc.get("ml_confidence")
        )
        
        # Try caching (non-critical)
        try:
            cache_data = recommendation.dict()
            cache_data["cached_at"] = datetime.now().isoformat()
            await redis_client.setex(
                f"rec:{file.filename}",
                3600,
                json.dumps(cache_data, default=str)
            )
        except Exception as e:
            logger.debug(f"Cache failed: {e}")
        
        return {
            "success": True,
            "analysis_id": doc.get("analysis_id"),
            "recommendation": recommendation.dict()
        }
            
    except Exception as e:
        logger.error(f"Recommendation failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }, 500

# === CRITICAL FIX 4: Add health check with performance metrics ===
@app.get("/health/performance")
async def performance_health():
    """Check system performance for 8GB RAM setup"""
    import psutil
    
    memory = psutil.virtual_memory()
    
    return {
        "status": "warning" if memory.percent > 85 else "healthy",
        "memory_usage_percent": memory.percent,
        "available_memory_mb": memory.available / (1024 * 1024),
        "cpu_percent": psutil.cpu_percent(interval=1),
        "thread_pool_size": executor._max_workers,
        "recommendations": [
            "Reduce image quality if memory > 85%",
            "Process one file at a time",
            "Max file size: 5MB recommended"
        ] if memory.percent > 85 else []
    }


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "path": request.url.path,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if settings.debug else "Contact support",
            "path": request.url.path,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="localhost",
        port=8001,
        reload=True, 
        workers=1, 
        log_level=settings.log_level.lower(),
        limit_concurrency=5, 
        backlog=20
    )
#1
# from fastapi import FastAPI, Request
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.middleware.gzip import GZipMiddleware
# from fastapi.responses import JSONResponse
# import logging
# import time
# from contextlib import asynccontextmanager
# from fastapi import HTTPException
# from app.api.routes import router as api_router
# from app.utils.config import settings
# from app.utils.cache import init_cache, close_cache
# from app.analyzers.certificate_analyzer import ProductionCertificateAnalyzer

# # Configure logging
# logging.basicConfig(
#     level=getattr(logging, settings.log_level.upper()),
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
# )
# logger = logging.getLogger(__name__)


# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     """Lifespan context manager for startup/shutdown events"""
#     logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    
#     # Initialize cache
#     try:
#         await init_cache()
#         logger.info("Cache initialized")
#     except Exception as e:
#         logger.warning(f"Cache initialization failed: {e}")
    
#     # Initialize and validate analyzer
#     try:
#         analyzer = ProductionCertificateAnalyzer(use_ml=settings.use_ml)
#         health = analyzer.health_check()
#         if health.get("status") != "healthy":
#             raise RuntimeError(f"Analyzer unhealthy: {health}")
#         logger.info("Analyzer initialized and passed health check")
#     except Exception as e:
#         logger.error(f"Analyzer initialization failed: {e}")
#         raise  # Fail fast — service should not start if core component is broken
    
#     yield
    
#     # Shutdown
#     logger.info("Shutting down application")
#     await close_cache()


# # Create FastAPI app
# app = FastAPI(
#     title=settings.app_name,
#     description="AI-powered certificate analyzer with English/Amharic support",
#     version=settings.app_version,
#     docs_url="/docs",   
#     redoc_url="/redoc", 
#     lifespan=lifespan
# )

# # Add middleware
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=settings.allowed_origins_list,
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# app.add_middleware(GZipMiddleware, minimum_size=1000)


# # Add request timing middleware
# @app.middleware("http")
# async def add_process_time_header(request: Request, call_next):
#     start_time = time.time()
#     response = await call_next(request)
#     process_time = time.time() - start_time
#     response.headers["X-Process-Time"] = str(process_time)
#     return response


# # Include API router
# app.include_router(api_router)


# # Root endpoint
# @app.get("/")
# async def root():
#     return {
#         "service": settings.app_name,
#         "version": settings.app_version,
#         "status": "operational",
#         "endpoints": {
#             "health": "/api/v1/health",
#             "analyze_upload": "/api/v1/analyze/upload",
#             "analyze_url": "/api/v1/analyze/url",
#             "generate_synthetic": "/api/v1/generate/synthetic",
#             "statistics": "/api/v1/statistics"
#         },
#         "features": [
#             "Hybrid OCR/ML analysis",
#             "English & Amharic support",
#             "Script detection",
#             "Tampering detection",
#             "Synthetic data generation",
#             "Production-ready API",
#             "Service provider verification dashboard"
#         ]
#     }


# # NEW: Enhanced analysis endpoint with admin summary
# @app.get("/api/v1/analyze/status/{analysis_id}")
# async def get_analysis_status(analysis_id: str):
#     """
#     Get analysis status and admin-friendly summary by analysis ID
#     """
#     try:
#         # In production, you'd fetch from database/cache
#         # This is a placeholder - implement your data retrieval logic
#         return {
#             "message": "Analysis status endpoint",
#             "note": "Implement database/cache lookup for analysis_id",
#             "analysis_id": analysis_id
#         }
#     except Exception as e:
#         logger.error(f"Failed to get analysis status: {e}")
#         raise HTTPException(status_code=500, detail=str(e))


# # NEW: Direct analyzer endpoint (for testing/direct access)
# @app.post("/api/v1/analyze/direct")
# async def analyze_direct(
#     request: Request,
#     provider_id: str,
#     request_id: str,
#     file_upload: bool = False,
#     document_url: str = None
# ):
#     """
#     Direct analysis endpoint that returns both full analysis and admin summary
#     Use file_upload=True with multipart form, or provide document_url
#     """
#     try:
#         analyzer = ProductionCertificateAnalyzer(use_ml=settings.use_ml)
        
#         if file_upload:
#             # Handle file upload
#             form_data = await request.form()
#             if "file" not in form_data:
#                 raise HTTPException(status_code=400, detail="No file provided")
            
#             file = form_data["file"]
#             full_result = await analyzer.analyze_certificate_file(
#                 file, provider_id, request_id
#             )
#         elif document_url:
#             # Handle URL analysis
#             full_result = await analyzer.analyze_certificate_url(
#                 document_url, provider_id, request_id
#             )
#         else:
#             raise HTTPException(status_code=400, detail="Either file_upload=True or document_url required")
        
#         # Create admin-friendly summary
#         admin_summary = analyzer.create_provider_summary(full_result)
        
#         return {
#             "success": True,
#             "analysis_id": full_result.get("analysis_id"),
#             "full_analysis": full_result,  # Detailed AI output
#             "admin_summary": admin_summary,  # Clean view for dashboard
#             "metadata": {
#                 "provider_id": provider_id,
#                 "request_id": request_id,
#                 "analysis_mode": "hybrid_ai" if settings.use_ml else "ocr_only",
#                 "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
#             }
#         }
        
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Direct analysis failed: {e}", exc_info=True)
#         raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


# # Error handlers
# @app.exception_handler(HTTPException)
# async def http_exception_handler(request: Request, exc: HTTPException):
#     return JSONResponse(
#         status_code=exc.status_code,
#         content={
#             "error": exc.detail,
#             "path": request.url.path,
#             "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
#         }
#     )


# @app.exception_handler(Exception)
# async def general_exception_handler(request: Request, exc: Exception):
#     logger.error(f"Unhandled exception: {exc}", exc_info=True)
#     return JSONResponse(
#         status_code=500,
#         content={
#             "error": "Internal server error",
#             "detail": str(exc) if settings.debug else "Contact support",
#             "path": request.url.path,
#             "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
#         }
#     )


# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(
#         "app.main:app",
#         host="localhost",
#         port=8000,
#         reload=True,
#         workers=settings.workers,
#         log_level=settings.log_level.lower()
#     )
    2
# from fastapi import FastAPI, Request
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.middleware.gzip import GZipMiddleware
# from fastapi.responses import JSONResponse
# import logging
# import time
# from contextlib import asynccontextmanager
# from fastapi import HTTPException
# from app.api.routes import router as api_router
# from app.utils.config import settings
# from app.utils.cache import init_cache, close_cache
# from app.analyzers.certificate_analyzer import ProductionCertificateAnalyzer

# # Configure logging
# logging.basicConfig(
#     level=getattr(logging, settings.log_level.upper()),
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
# )
# logger = logging.getLogger(__name__)


# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     """Lifespan context manager for startup/shutdown events"""
#     logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    
#     # Initialize cache
#     try:
#         await init_cache()
#         logger.info("Cache initialized")
#     except Exception as e:
#         logger.warning(f"Cache initialization failed: {e}")
    
#     # Initialize and validate analyzer
#     try:
#         analyzer = ProductionCertificateAnalyzer(use_ml=settings.use_ml)
#         health = analyzer.health_check()
#         if health.get("status") != "healthy":
#             raise RuntimeError(f"Analyzer unhealthy: {health}")
#         logger.info("Analyzer initialized and passed health check")
#     except Exception as e:
#         logger.error(f"Analyzer initialization failed: {e}")
#         raise  # Fail fast — service should not start if core component is broken
    
#     yield
    
#     # Shutdown
#     logger.info("Shutting down application")
#     await close_cache()


# # Create FastAPI app
# app = FastAPI(
#     title=settings.app_name,
#     description="AI-powered certificate analyzer with English/Amharic support",
#     version=settings.app_version,
#     docs_url="/docs",   
#     redoc_url="/redoc", 
#     lifespan=lifespan
# )

# # Add middleware
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=settings.allowed_origins_list,
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# app.add_middleware(GZipMiddleware, minimum_size=1000)


# # Add request timing middleware
# @app.middleware("http")
# async def add_process_time_header(request: Request, call_next):
#     start_time = time.time()
#     response = await call_next(request)
#     process_time = time.time() - start_time
#     response.headers["X-Process-Time"] = str(process_time)
#     return response


# # Include API router
# app.include_router(api_router)


# # Root endpoint
# @app.get("/")
# async def root():
#     return {
#         "service": settings.app_name,
#         "version": settings.app_version,
#         "status": "operational",
#         "endpoints": {
#             "health": "/api/v1/health",
#             "analyze_upload": "/api/v1/analyze/upload",
#             "analyze_url": "/api/v1/analyze/url",
#             "generate_synthetic": "/api/v1/generate/synthetic",
#             "statistics": "/api/v1/statistics"
#         },
#         "features": [
#             "Hybrid OCR/ML analysis",
#             "English & Amharic support",
#             "Script detection",
#             "Tampering detection",
#             "Synthetic data generation",
#             "Production-ready API"
#         ]
#     }


# # Error handlers
# @app.exception_handler(HTTPException)
# async def http_exception_handler(request: Request, exc: HTTPException):
#     return JSONResponse(
#         status_code=exc.status_code,
#         content={
#             "error": exc.detail,
#             "path": request.url.path,
#             "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
#         }
#     )


# @app.exception_handler(Exception)
# async def general_exception_handler(request: Request, exc: Exception):
#     logger.error(f"Unhandled exception: {exc}", exc_info=True)
#     return JSONResponse(
#         status_code=500,
#         content={
#             "error": "Internal server error",
#             "detail": str(exc) if settings.debug else "Contact support",
#             "path": request.url.path,
#             "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
#         }
#     )


# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(
#         "app.main:app",
#         host="localhost",
#         port=8000,
#         reload=True,
#         workers=settings.workers,
#         log_level=settings.log_level.lower()
#     )