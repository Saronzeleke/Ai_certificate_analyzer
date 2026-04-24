import logging
import hashlib
import tempfile
import asyncio
import os
from datetime import datetime
from typing import Dict, Any, List, Optional, Union
from pathlib import Path
import json
import time
import re
from app.analyzers.tamper_detector import ProductionTamperDetector
from app.analyzers.script_detector import ScriptDetector
from app.analyzers.ocr.router import MultilingualOCRRouter
from app.analyzers.ml_models.donut_model import DonutCertificateParser
from app.analyzers.ml_models.field_extractor import MLFieldExtractor
from app.utils.image_processing import ImageProcessor
from fastapi import UploadFile
import aiohttp
from app.utils.config import settings
import aiofiles
import numpy as np
import cv2
from PIL import Image
from app.analyzers.recommendation_engine import create_recommendation_engine
engine = create_recommendation_engine()
logger = logging.getLogger(__name__)

def clean_extracted_text(text: str) -> str:
    """Clean common OCR/ML extraction artifacts"""
    if not text:
        return text
    
    replacements = {
        "| OF COMPLETIO}": "CERTIFICATE OF COMPLETION",
        "_t\nOF COMPLETIO}": "CERTIFICATE OF COMPLETION",
        "F cerniric": "CERTIFICATE",
        "}n": "}\n",
        "_t": "",
    }
    
    for old, new in replacements.items():
        text = text.replace(old, new)
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    text = '\n'.join(lines)
    
    return text

def map_extracted_text_to_fields(text_dict: Dict[str, Any]) -> Dict[str, str]:
    """Try to map extracted text to specific fields"""
    mapped_fields = {}
    
    if not text_dict:
        return mapped_fields
    
    # Look for patterns in text
    for key, value in text_dict.items():
        if isinstance(value, dict) and 'text' in value:
            text = value['text']
            text = clean_extracted_text(text)
            
            if any(name_indicator in text for name_indicator in ['GIVEN TO', 'GIVEN TO\n', 'IS GIVEN TO', 'AWARDED TO']):
                lines = text.split('\n')
                for i, line in enumerate(lines):
                    if any(indicator in line for indicator in ['GIVEN TO', 'AWARDED TO']):
                        if i + 1 < len(lines):
                            mapped_fields['student_name'] = lines[i + 1].strip()
                            break
            
            if 'at ' in text.lower() or 'from ' in text.lower():
                org_patterns = [
                    r'at\s+([A-Za-z\s]+?)(?:\.|,|\n|$)',
                    r'from\s+([A-Za-z\s]+?)(?:\.|,|\n|$)'
                ]
                for pattern in org_patterns:
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        mapped_fields['university'] = match.group(1).strip()
                        break
            
            # Look for date patterns
            date_patterns = [
                r'\b(?:summer|spring|fall|winter)\s+of\s+(\d{4})\b',
                r'\b(\d{4}-\d{2}-\d{2})\b',
                r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)[\s\d,]*\d{4}\b'
            ]
            for pattern in date_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    mapped_fields['issue_date'] = match.group(0).strip()
                    break
    
    return mapped_fields

class ProductionCertificateAnalyzer:
    """AI-powered certificate analyzer with hybrid approach for SERVICE PROVIDERS"""
    
    def __init__(self, use_ml: bool = True):
        self.model_version = "2024.2.0-ai-hybrid"
        self.use_ml = use_ml
        
        # Initialize components
        self.tamper_detector = ProductionTamperDetector()
        self.script_detector = ScriptDetector()
        self.ocr_router = MultilingualOCRRouter(self.script_detector)
        self.image_processor = ImageProcessor()
        self.use_small_model = True  
        self.max_image_size = 640  
        # ML models (optional)
        if self.use_ml and settings.use_ml:
            try:
                logger.info("Loading Donut from HuggingFace cache")
                self.donut_parser = DonutCertificateParser(model_path=None)
                
                health = self.donut_parser.health_check()
                logger.info(f"Donut health check: {health}")
                
                if health["ready"]:
                    self.ml_extractor = MLFieldExtractor()
                    logger.info("ML models loaded successfully")
                else:
                    logger.warning("Donut model not ready, disabling ML")
                    self.use_ml = False
                    
            except Exception as e:
                logger.warning(f"Failed to load ML models: {e}. Using OCR only.")
                self.use_ml = False
        else:
            logger.info("ML disabled via settings")
            self.use_ml = False
        
        # Configurable thresholds
        self.reject_threshold = float(settings.reject_threshold)
        self.low_quality_threshold = float(settings.low_quality_threshold)
        self.ml_confidence_threshold = float(settings.ml_confidence_threshold)
        self.CACHE_TTL = 3600
        
        # Redis safety flag
        self._redis_available = True
        self.config_hash = self._get_config_hash()
        
        logger.info(f"ProductionCertificateAnalyzer v{self.model_version} initialized")
        logger.info(f"ML enabled: {self.use_ml}, Hybrid mode: {'OCR+ML' if self.use_ml else 'OCR only'}")
        logger.info(f"Thresholds - Reject: {self.reject_threshold}, ML Confidence: {self.ml_confidence_threshold}")
    
    # ========== NEW SERVICE PROVIDER TRANSFORMATION METHODS ==========
    
    def create_provider_summary(self, full_analysis_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform full AI analysis result into clean admin-friendly summary for SERVICE PROVIDERS.
        Returns simplified view for admin dashboard.
        """
        try:
            extracted_data = full_analysis_result.get("extracted_data", {})
            extracted_fields = extracted_data.get("fields", {})
            extracted_text = extracted_data.get("extracted_text", {})
            raw_text = extracted_data.get("raw_text", "")
            
            # Determine certificate type based on content
            cert_type = self._identify_certificate_type(raw_text)
            
            # Extract provider info
            provider_name = self._extract_provider_name(extracted_text, raw_text, cert_type)
            
            # Extract skill/qualification
            skill = self._extract_skill(extracted_fields, extracted_text, raw_text, cert_type)
            
            # Extract issuing authority
            issuer = self._extract_issuer_authority(extracted_fields, extracted_text, raw_text, cert_type)
            
            # Extract validity/date
            validity = self._extract_validity_date(extracted_fields, extracted_text, raw_text, cert_type)
            
            # Check if expired
            expired = self._check_expiry(validity)
            
            # Build SERVICE PROVIDER summary
            provider_summary = {
                "provider_id": full_analysis_result.get("provider_id", "unknown"),
                "certificate_type": cert_type,
                "authenticity_score": full_analysis_result.get("authenticity_score", 0.0),
                "extracted_information": {
                    "provider_name": provider_name,
                    "skill_or_qualification": skill,
                    "issuing_authority": issuer,
                    "validity_date": validity,
                    "certificate_number": extracted_fields.get("certificate_number", ""),
                    "license_class": extracted_fields.get("license_class", "")
                },
                "verification_flags": {
                    "tampering_detected": full_analysis_result.get("flags", {}).get("tampering_detected", False),
                    "low_quality_scan": full_analysis_result.get("flags", {}).get("low_quality_scan", False),
                    "expired_certificate": expired,
                    "needs_manual_review": full_analysis_result.get("status") == "Pending Admin Review",
                    "high_risk_forgery": full_analysis_result.get("flags", {}).get("potential_forgery", False)
                },
                "status": full_analysis_result.get("status", "Unknown"),
                "admin_action": full_analysis_result.get("admin_action", "review"),
                "recommendations": full_analysis_result.get("recommendations", []),
                "analysis_id": full_analysis_result.get("analysis_id"),
                "timestamp": full_analysis_result.get("timestamp"),
                "quick_summary": f"{skill} - {cert_type} | Issued by: {issuer}"
            }
            
            return provider_summary
            
        except Exception as e:
            logger.error(f"Failed to create provider summary: {e}")
            return {
                "error": f"Transformation failed: {str(e)}",
                "raw_analysis_id": full_analysis_result.get("analysis_id", "unknown"),
                "status": "Error in transformation"
            }
    
    def _identify_certificate_type(self, raw_text: str) -> str:
        """Identify what type of professional certificate this is"""
        text_upper = raw_text.upper()
        
        if any(word in text_upper for word in ["LICENSE", "PERMIT", "REGISTRATION"]):
            return "Professional License"
        elif any(word in text_upper for word in ["ELECTRICIAN", "PLUMBER", "MECHANIC", "TECHNICIAN"]):
            return "Trade Certificate"
        elif any(word in text_upper for word in ["TRAINING", "COURSE", "WORKSHOP", "SEMINAR"]):
            return "Training Certificate"
        elif any(word in text_upper for word in ["EXPERIENCE", "EMPLOYMENT", "WORKED AS", "SERVICE"]):
            return "Work Experience Certificate"
        elif any(word in text_upper for word in ["DEGREE", "DIPLOMA", "BACHELOR", "MASTER"]):
            return "Academic Certificate"
        elif "CERTIFICATE" in text_upper:
            return "General Certificate"
        else:
            return "Unknown Document"
    
    def _extract_provider_name(self, extracted_text: Dict, raw_text: str, cert_type: str) -> str:
        """Extract service provider's name"""
        # Common patterns in professional certificates
        patterns = [
            "THIS IS TO CERTIFY THAT",
            "IS HEREBY CERTIFIED",
            "CERTIFICATE AWARDED TO",
            "LICENSE ISSUED TO",
            "HOLDER OF THIS LICENSE",
            "THIS CERTIFICATE IS GRANTED TO",
            "ISSUED TO"
        ]
        
        for pattern in patterns:
            if pattern in raw_text:
                parts = raw_text.split(pattern)
                if len(parts) > 1:
                    name_line = parts[1].split('\n')[0].strip()
                    if name_line and len(name_line) > 3:
                        return name_line
        
        # Fallback: look for any name-like pattern
        name_pattern = r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)'
        matches = re.findall(name_pattern, raw_text)
        if matches and len(matches[0].split()) >= 2:
            return matches[0]
        
        return "Provider Name Not Found"
    
    def _extract_skill(self, extracted_fields: Dict, extracted_text: Dict, raw_text: str, cert_type: str) -> str:
        """Extract skill or qualification from certificate"""
        text_upper = raw_text.upper()
        
        # Look for skill indicators
        skills_keywords = [
            "ELECTRICIAN", "PLUMBER", "CARPENTER", "MECHANIC", 
            "TECHNICIAN", "CLEANER", "PAINTER", "DRIVER",
            "WELDER", "MASON", "GARDENER", "COOK", "REPAIR",
            "MAINTENANCE", "INSTALLER", "FITTER"
        ]
        
        for skill in skills_keywords:
            if skill in text_upper:
                return skill.title()
        
        # Look for qualification level
        qual_keywords = [
            "CLASS A", "CLASS B", "CLASS C", "LEVEL 1", "LEVEL 2", 
            "LEVEL 3", "CERTIFIED", "LICENSED", "QUALIFIED",
            "PROFESSIONAL", "EXPERT", "SPECIALIST"
        ]
        
        for qual in qual_keywords:
            if qual in text_upper:
                return f"{cert_type} - {qual}"
        
        return extracted_fields.get("skill", extracted_fields.get("qualification", "Skill Not Specified"))
    
    def _extract_issuer_authority(self, extracted_fields: Dict, extracted_text: Dict, raw_text: str, cert_type: str) -> str:
        """Extract issuing authority (government, training center, company)"""
        issuer_keywords = [
            "MINISTRY OF", "DEPARTMENT OF", "GOVERNMENT OF",
            "TRAINING CENTER", "INSTITUTE", "ACADEMY",
            "CERTIFICATION BOARD", "LICENSING AUTHORITY",
            "CITY OF", "MUNICIPALITY", "COMMISSION"
        ]
        
        for keyword in issuer_keywords:
            pattern = rf'({keyword}[A-Za-z\s]+?)(?:\.|,|\n|$)'
            match = re.search(pattern, raw_text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        # Fallback: company name
        company_pattern = r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:Technologies|Solutions|Services|Company|Corp|Ltd|Inc))'
        match = re.search(company_pattern, raw_text)
        if match:
            return match.group(1)
        
        return extracted_fields.get("issuer", extracted_fields.get("authority", "Unknown Authority"))
    
    def _extract_validity_date(self, extracted_fields: Dict, extracted_text: Dict, raw_text: str, cert_type: str) -> str:
        """Extract validity/expiry/issue date"""
        date_patterns = [
            r'VALID UNTIL\s+(\d{2}/\d{2}/\d{4})',
            r'EXPIRY DATE\s+(\d{2}/\d{2}/\d{4})',
            r'EXPIRES ON\s+(\d{2}/\d{2}/\d{4})',
            r'ISSUED ON\s+(\d{2}/\d{2}/\d{4})',
            r'DATE OF ISSUE\s+(\d{2}/\d{2}/\d{4})',
            r'(\d{2}/\d{2}/\d{4})\s+TO\s+(\d{2}/\d{2}/\d{4})',
            r'YEAR\s*:\s*(\d{4})'
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, raw_text, re.IGNORECASE)
            if match:
                if match.lastindex == 1:
                    return match.group(1)
                elif match.lastindex == 2:
                    return f"{match.group(1)} to {match.group(2)}"
        
        # Simple year extraction
        year_match = re.search(r'\b(20\d{2}|19\d{2})\b', raw_text)
        if year_match:
            return f"Year: {year_match.group(1)}"
        
        return extracted_fields.get("validity", extracted_fields.get("issue_date", "Date Not Specified"))
    
    def _check_expiry(self, validity_date: str) -> bool:
        """Check if certificate is expired"""
        try:
            if not validity_date or "Not Specified" in validity_date:
                return False
            
            # Extract date from validity string
            date_patterns = [
                r'(\d{2})/(\d{2})/(\d{4})',
                r'(\d{4})-(\d{2})-(\d{2})'
            ]
            
            for pattern in date_patterns:
                match = re.search(pattern, validity_date)
                if match:
                    day, month, year = match.groups()
                    expiry_date = datetime(int(year), int(month), int(day))
                    return expiry_date < datetime.now()
            
            # Check for year-only format
            year_match = re.search(r'Year:\s*(\d{4})', validity_date)
            if year_match:
                expiry_year = int(year_match.group(1))
                current_year = datetime.now().year
                return expiry_year < current_year
            
            return False
        except Exception:
            return False
    
    # ========== ORIGINAL METHODS (UNCHANGED) ==========
    
    def _get_config_hash(self) -> str:
        """Generate config hash for version tracking"""
        config_data = {
            'model_version': self.model_version,
            'use_ml': self.use_ml,
            'reject_threshold': self.reject_threshold,
            'low_quality_threshold': self.low_quality_threshold,
            'ml_threshold': self.ml_confidence_threshold,
            'tampering_threshold': settings.tampering_threshold
        }
        return hashlib.sha256(json.dumps(config_data, sort_keys=True).encode()).hexdigest()[:16]
    
    async def _get_file_hash(self, file: UploadFile) -> str:
        """Generate hash for uploaded file"""
        try:
            content = await file.read()
            await file.seek(0)  # Reset file pointer
            return hashlib.md5(content).hexdigest()
        except Exception as e:
            logger.warning(f"Failed to generate file hash: {e}")
            return "unknown"
    
    async def _get_redis_client(self):
        """Safely get Redis client with fallback"""
        try:
            from app.utils.cache import get_redis_client
            client = await get_redis_client()
            return client
        except ImportError:
            logger.error("Redis module not available")
            return None
        except Exception as e:
            logger.warning(f"Failed to get Redis client: {e}")
            return None
    
    async def _safe_redis_setex(self, cache_key: str, ttl: int, data: dict) -> bool:
        """Safely set cache with fallback"""
        try:
            client = await self._get_redis_client()
            if client:
                await client.setex(cache_key, ttl, json.dumps(data))
                logger.debug(f"Cache set for key: {cache_key}")
                return True
            else:
                logger.warning("Redis not available, skipping cache set")
                self._redis_available = False
                return False
        except Exception as e:
            logger.error(f"Redis setex failed: {e}")
            self._redis_available = False
            return False
    
    async def _safe_redis_get(self, cache_key: str) -> Optional[dict]:
        """Safely get from cache with fallback"""
        try:
            client = await self._get_redis_client()
            if client:
                cached = await client.get(cache_key)
                if cached:
                    logger.debug(f"Cache hit for key: {cache_key}")
                    return json.loads(cached)
            return None
        except Exception as e:
            logger.warning(f"Redis get failed: {e}")
            return None
    
    def _generate_error_report(
        self, 
        provider_id: str, 
        request_id: str, 
        error_message: str, 
        source_type: str
    ) -> Dict[str, Any]:
        """Generate error report when analysis fails"""
        return {
            'analysis_id': f"error_{hashlib.md5(f'{provider_id}{request_id}'.encode()).hexdigest()[:12]}",
            'timestamp': datetime.now().isoformat(),
            'provider_id': provider_id,
            'request_id': request_id,
            'authenticity_score': 0.0,
            'status': 'Analysis Failed',
            'error': error_message,
            'source_type': source_type,
            'cache_hit': False,
            'redis_available': self._redis_available,
            'quality_metrics': {
                'ocr_confidence': 0.0,
                'tampering_confidence': 0.0,
                'page_count': 0,
                'average_entropy': 0.0
            },
            'flags': {
                'analysis_failed': True,
                'tampering_detected': False,
                'low_quality_scan': True,
                'incomplete_fields': True
            },
            'model_metadata': {
                'version': self.model_version,
                'config_hash': self.config_hash,
                'thresholds': {
                    'reject': self.reject_threshold,
                    'low_quality': self.low_quality_threshold
                }
            },
            'recommendations': ['Analysis failed. Please try again or contact support.']
        }
    
    async def _save_upload(self, file: UploadFile) -> str:
        """Save UploadFile to temporary file with proper cleanup"""
        try:
            suffix = Path(file.filename).suffix if file.filename else ".pdf"
            if suffix.lower() not in ['.pdf', '.jpg', '.jpeg', '.png', '.tiff', '.bmp']:
                suffix = '.pdf'  # Default to PDF for documents
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                content = await file.read()
                tmp.write(content)
                return tmp.name
                
        except Exception as e:
            logger.error(f"Failed to save uploaded file: {str(e)}")
            raise Exception(f"File upload failed: {str(e)}")
    
    def _calculate_image_entropy(self, image) -> float:
        """Calculate image entropy for quality assessment"""
        try:
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image
            
            if gray.size == 0:
                return 0.0
                
            # Calculate histogram
            hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
            hist = hist.ravel() / hist.sum()
            
            # Calculate entropy
            entropy = -np.sum(hist * np.log2(hist + 1e-10))
            return float(entropy)
        except Exception:
            return 0.0
    
    async def analyze_certificate_url(
        self, 
        document_url: str, 
        provider_id: str, 
        request_id: str
    ) -> Dict[str, Any]:
        """Analyze certificate from URL"""
        temp_path = None
        try:
            logger.info(f"Starting URL analysis for {request_id}")
            start_time = datetime.now()
            
            # Check cache
            cache_key = f"ai_url:{provider_id}:{hashlib.md5(document_url.encode()).hexdigest()}"
            
            if self._redis_available:
                cached_result = await self._safe_redis_get(cache_key)
                if cached_result:
                    cached_result['cache_hit'] = True
                    return cached_result
            
            # Download document
            temp_path = await self._download_document(document_url)
            
            # Process document
            processed_images = await self.image_processor.process_document(temp_path)
            if not processed_images:
                raise Exception("No valid images extracted from document")
            
            logger.info(f"Processing {len(processed_images)} pages")
            
            # Analyze each page with hybrid approach
            page_tasks = [
                self._analyze_single_page_hybrid(img, idx, request_id)
                for idx, img in enumerate(processed_images)
            ]
            page_results = await asyncio.gather(*page_tasks, return_exceptions=True)
            
            # Combine results
            valid_results = [r for r in page_results if not isinstance(r, Exception)]
            if not valid_results:
                raise Exception("All page analyses failed")
            
            final_report = self._combine_hybrid_results(
                valid_results, provider_id, request_id
            )
            
            # Add processing metadata
            processing_time = (datetime.now() - start_time).total_seconds()
            final_report.update({
                'processing_time': round(processing_time, 3),
                'model_version': self.model_version,
                'config_hash': self.config_hash,
                'analysis_mode': 'hybrid_ai' if self.use_ml else 'ocr_only',
                'cache_hit': False,
                'redis_available': self._redis_available
            })
            
            # Cache result
            if self._redis_available:
                cache_data = final_report.copy()
                if 'recommendation_result' in cache_data and hasattr(cache_data['recommendation_result'], 'dict'):
                    cache_data['recommendation_result'] = cache_data['recommendation_result'].dict()
                await self._safe_redis_setex(cache_key, self.CACHE_TTL, cache_data)
            
            logger.info(f"URL analysis completed in {processing_time}s")
            return final_report
            
        except Exception as e:
            logger.error(f"URL analysis pipeline failed: {str(e)}", exc_info=True)
            return self._generate_error_report(
                provider_id, request_id, str(e), "url"
            )
        finally:
            if temp_path and Path(temp_path).exists():
                try:
                    Path(temp_path).unlink()
                except:
                    pass
    
    async def _download_document(self, document_url: str) -> str:
        """Download document from URL with timeout and validation"""
        try:
            timeout = aiohttp.ClientTimeout(total=30, connect=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(document_url) as response:
                    if response.status != 200:
                        raise Exception(f"HTTP {response.status}: Failed to download")
                    
                    # Get file extension from Content-Type or URL
                    content_type = response.headers.get('Content-Type', '')
                    if 'pdf' in content_type.lower():
                        suffix = '.pdf'
                    elif 'image' in content_type.lower():
                        suffix = '.jpg'
                    else:
                        # Extract from URL
                        suffix = Path(document_url).suffix or '.pdf'
                    
                    fd, temp_path = tempfile.mkstemp(suffix=suffix)
                    os.close(fd)
                    
                    async with aiofiles.open(temp_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(8192):
                            await f.write(chunk)
                    
                    return temp_path
                    
        except asyncio.TimeoutError:
            raise Exception("Download timeout - server took too long to respond")
        except Exception as e:
            logger.error(f"Document download failed: {str(e)}")
            raise Exception(f"Download failed: {str(e)}")
    
    async def analyze_certificate_file(
        self, 
        file: UploadFile, 
        provider_id: str, 
        request_id: str
    ) -> Dict[str, Any]:
        """Analyze uploaded certificate with AI hybrid approach"""
        temp_path = None
        try:
            logger.info(f"Starting AI analysis for {request_id}")
            start_time = datetime.now()
            
            # Check cache
            file_hash = await self._get_file_hash(file)
            await file.seek(0)
            cache_key = f"ai_upload:{provider_id}:{file_hash}"
            
            if self._redis_available:
                cached_result = await self._safe_redis_get(cache_key)
                if cached_result:
                    cached_result['cache_hit'] = True
                    return cached_result
            
            # Save uploaded file
            temp_path = await self._save_upload(file)
            
            # Process document
            processed_images = await self.image_processor.process_document(temp_path)
            if not processed_images:
                raise Exception("No valid images extracted from document")
            
            logger.info(f"Processing {len(processed_images)} pages")
            
            # Analyze each page with hybrid approach
            page_tasks = [
                self._analyze_single_page_hybrid(img, idx, request_id)
                for idx, img in enumerate(processed_images)
            ]
            page_results = await asyncio.gather(*page_tasks, return_exceptions=True)
            
            # Combine results
            valid_results = [r for r in page_results if not isinstance(r, Exception)]
            if not valid_results:
                raise Exception("All page analyses failed")
            
            final_report = self._combine_hybrid_results(
                valid_results, provider_id, request_id
            )
            
            # Add processing metadata
            processing_time = (datetime.now() - start_time).total_seconds()
            final_report.update({
                'processing_time': round(processing_time, 3),
                'model_version': self.model_version,
                'config_hash': self.config_hash,
                'analysis_mode': 'hybrid_ai' if self.use_ml else 'ocr_only',
                'cache_hit': False,
                'redis_available': self._redis_available
            })
            
            # Cache result
            if self._redis_available:
                cache_data = final_report.copy()
                if 'recommendation_result' in cache_data and hasattr(cache_data['recommendation_result'], 'dict'):
                    cache_data['recommendation_result'] = cache_data['recommendation_result'].dict()
                await self._safe_redis_setex(cache_key, self.CACHE_TTL, cache_data)
            
            logger.info(f"AI analysis completed in {processing_time}s")
            return final_report
            
        except Exception as e:
            logger.error(f"AI analysis pipeline failed: {str(e)}", exc_info=True)
            return self._generate_error_report(
                provider_id, request_id, str(e), "upload"
            )
        finally:
            if temp_path and Path(temp_path).exists():
                try:
                    Path(temp_path).unlink()
                except:
                    pass
    
    async def _analyze_single_page_hybrid(
        self, 
        image: np.ndarray, 
        page_num: int, 
        request_id: str
    ) -> Dict[str, Any]:
        """Hybrid analysis: OCR + ML"""
        try:
            # Convert to PIL for ML models
            if len(image.shape) == 3:
                pil_image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
            else:
                pil_image = Image.fromarray(image)
            
            # Step 1: Script detection
            script_result = self.script_detector.detect(image)
            language = script_result.get('script', 'unknown')
            
            # Step 2: Parallel processing
            ocr_task = self.ocr_router.extract_text(image)
            tamper_task = self.tamper_detector.detect(image)
            ml_task = self._ml_analysis(pil_image, language) if self.use_ml else None
            
            # Wait for OCR and tampering
            ocr_results, tampering_results = await asyncio.gather(ocr_task, tamper_task)
            
            # Wait for ML if enabled
            ml_results = await ml_task if ml_task else None
            
            # Step 3: Merge results
            if ml_results and ml_results.get('confidence', 0) > self.ml_confidence_threshold:
                # Use ML results as primary
                extracted_fields = ml_results.get('extracted_fields', {})
                extraction_method = 'ml'
                extraction_confidence = ml_results.get('confidence', 0)
            else:
                # Use OCR results
                extracted_fields = ocr_results.get('extracted_text', {})
                extraction_method = 'ocr'
                extraction_confidence = ocr_results.get('ocr_confidence', 0)
                
                # Enhance with ML if available
                if ml_results:
                    extracted_fields = self._merge_fields(
                        extracted_fields, 
                        ml_results.get('extracted_fields', {})
                    )
            
            # Extract features
            ml_features = self._extract_ml_features(
                image, ocr_results, tampering_results, ml_results
            )
            
            return {
                'page_number': page_num,
                'script_detection': script_result,
                'ocr_results': ocr_results,
                'tampering_results': tampering_results,
                'ml_results': ml_results,
                'extracted_fields': extracted_fields,
                'field_confidence': ocr_results.get('field_confidence', {}),
                'extraction_method': extraction_method,
                'extraction_confidence': extraction_confidence,
                'ml_features': ml_features,
                'timestamp': datetime.now().isoformat(),
                'request_id': request_id
            }
            
        except Exception as e:
            logger.error(f"Hybrid analysis failed for page {page_num}: {e}")
            return {
                'page_number': page_num,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    async def _ml_analysis(self, image: Image.Image, language: str) -> Optional[Dict[str, Any]]:
        """ML-based analysis"""
        try:
            # Use Donut for parsing
            donut_result = self.donut_parser.parse_certificate(image, language)
            
            # Use ML field extractor
            ml_fields = self.ml_extractor.extract_fields(image)
            
            # Merge results
            extracted_fields = {}
            if donut_result.get('parsed_data'):
                extracted_fields.update(donut_result['parsed_data'])
            if ml_fields:
                extracted_fields.update(ml_fields)
            
            return {
                'extracted_fields': extracted_fields,
                'confidence': donut_result.get('confidence', 0.7),
                'donut_result': donut_result,
                'ml_fields': ml_fields,
                'model_used': 'donut+ml_extractor'
            }
        except Exception as e:
            logger.debug(f"ML analysis failed: {e}")
            return None
    
    def _merge_fields(self, ocr_fields: Dict, ml_fields: Dict) -> Dict:
        """Intelligently merge OCR and ML results"""
        merged = ocr_fields.copy()
        
        for key, ml_value in ml_fields.items():
            if key not in merged:
                # ML found something OCR missed
                merged[key] = ml_value
            elif ml_value and (not merged[key] or len(ml_value) > len(merged[key])):
                # ML value is better (longer/more complete)
                merged[key] = ml_value
        
        return merged
    
    def _extract_ml_features(self, image, ocr_results, tampering_results, ml_results):
        """Enhanced feature extraction"""
        features = {
            'image_stats': {
                'shape': image.shape if hasattr(image, 'shape') else (0, 0, 0),
                'entropy': self._calculate_image_entropy(image)
            },
            'ocr_features': {
                'confidence': ocr_results.get('ocr_confidence', 0),
                'language': ocr_results.get('language', 'unknown'),
                'word_count': ocr_results.get('word_count', 0)
            },
            'tampering_features': {
                'detected': tampering_results.get('tampering_detected', False),
                'confidence': tampering_results.get('tampering_confidence', 0)
            },
            'ml_features': {
                'used': ml_results is not None,
                'confidence': ml_results.get('confidence', 0) if ml_results else 0,
                'model': ml_results.get('model_used', 'none') if ml_results else 'none'
            }
        }
        return features
    
    def _generate_analysis_id(self, provider_id: str, request_id: str) -> str:
        """Generate secure analysis ID"""
        salt = getattr(settings, 'analysis_id_salt', 'serveease-cert-salt-2024')
        hash_input = f"{provider_id}{request_id}{salt}{datetime.now().isoformat()}"
        return f"anal_{hashlib.sha256(hash_input.encode()).hexdigest()[:12]}"
    # Inside your analyzer class (ProductionCertificateAnalyzer or similar)

    def _combine_hybrid_results(self, page_results, provider_id, request_id):
        """Combine hybrid analysis results with cleaned text and generate AI recommendation"""
        primary_result = page_results[0]

        # --- Extracted Data ---
        extracted_fields = primary_result.get("extracted_fields", {})
        ml_results = primary_result.get("ml_results", {})
        ocr_results = primary_result.get("ocr_results", {})

        # --- Clean OCR Text ---
        if "extracted_text" in ocr_results:
            extracted_text = ocr_results.get("extracted_text",{})
            for key, value in extracted_text.items():
                if isinstance(value, dict) and "text" in value:
                    extracted_text[key]["text"] = clean_extracted_text(value["text"])
                elif isinstance(value, str):
                    extracted_text[key] = clean_extracted_text(value)

        # --- Map text to fields ---
        mapped_fields = map_extracted_text_to_fields(ocr_results.get("extracted_text", {}))
        if mapped_fields:
            extracted_fields.update(mapped_fields)

        # --- Prepare extracted data ---
        cleaned_fields = {}
        for field, value in extracted_fields.items():
              # Skip invalid values
            if not value or (isinstance(value, str) and value.strip().upper() in ["CERTIFICATE", "N/A", "UNKNOWN"]):
                cleaned_fields[field] = None
                continue
             # Specific rules
            elif field in ["student_id", "certificate_id", "certificate_number", "license_number"]:
               value_str = str(value).strip()

             # Must contain at least one digit
               if not re.search(r"\d", value_str):
                  cleaned_fields[field] = None
               else:
                   cleaned_fields[field] = re.sub(r"[^A-Za-z0-9\-\/]", "", value_str)
            elif field in ["name", "university", "course"]:
               cleaned_fields[field] = str(value).strip()
            else:
              cleaned_fields[field] = value
        extracted_data = {
            "fields":cleaned_fields,
            "raw_text": ocr_results.get("raw_text", {}),
            "confidence_scores": ocr_results.get("confidence_scores", {}),
            "field_regions": ocr_results.get("field_regions", []),
            "present_fields": ocr_results.get("present_fields", {}),
            "field_confidence": ocr_results.get("field_confidence", {}),
            "spatial_features_shape": ml_results.get("spatial_features", {}).get("shape", []) if ml_results else [],
            "processing_time": primary_result.get("processing_time", 0),
            "success": "error" not in primary_result,
            "extracted_text": ocr_results.get("extracted_text", {})
        }

        # --- Calculate authenticity score ---
        authenticity_score = self._calculate_hybrid_score(primary_result)

        # --- Determine status ---
        if authenticity_score >= self.reject_threshold:
            status = "Pending Admin Review"
            admin_action = "approve"
        else:
            status = "Auto-Rejected"
            admin_action = "reject"

        # --- Generate analysis ID ---
        analysis_id = self._generate_analysis_id(provider_id, request_id)

        # --- Build report ---
        report = {
            "analysis_id": analysis_id,
            "timestamp": datetime.now().isoformat(),
            "provider_id": provider_id,
            "request_id": request_id,
            "extracted_data": extracted_data,
            "authenticity_score": round(authenticity_score, 4),
            "status": status,
            "admin_action": admin_action,
            "quality_metrics": {
                "ocr_confidence":primary_result.get('ocr_results', {}).get("ocr_confidence", 0),
                "tampering_confidence": primary_result.get("tampering_results", {}).get("tampering_confidence", 0),
                "ml_confidence":primary_result.get('ml_results', {}).get("confidence", 0),
                "extraction_method": primary_result.get("extraction_method", "ocr"),
                "script_detected": primary_result.get("script_detection", {}).get("script", "unknown")
            },
            "flags": self._generate_hybrid_flags(primary_result),
            "page_summaries": [
                {
                    "page": page["page_number"],
                    "tampering_detected": page.get("tampering_results", {}).get("tampering_detected", False),
                    "extraction_method": page.get("extraction_method", "ocr"),
                    "script": page.get("script_detection", {}).get("script", "unknown")
                }
                for page in page_results
            ],
            "model_metadata": {
                "version": self.model_version,
                "config_hash": self.config_hash,
                "use_ml": self.use_ml,
                "thresholds": {
                    "reject": self.reject_threshold,
                    "ml_confidence": self.ml_confidence_threshold
                }
            },
            # Existing recommendations (if any)
            "recommendations": self._generate_ai_recommendations(authenticity_score, primary_result)
        }

        # --- Generate AI recommendation automatically ---
        if engine is not None:
            recommendation_result = engine.generate_recommendation(
                authenticity_score=report["authenticity_score"],
                extracted_fields=report["extracted_data"]["fields"],
                ocr_confidence=report["quality_metrics"]["ocr_confidence"],
                ml_confidence=report["quality_metrics"]["ml_confidence"]
            )
            report["recommendation_result"] = recommendation_result

        return report

    # def _combine_hybrid_results(self, page_results, provider_id, request_id):
    #     """Combine hybrid analysis results with cleaned text"""
    #     primary_result = page_results[0]
        
    #     # Get extracted data
    #     extracted_fields = primary_result.get('extracted_fields', {})
    #     ml_results = primary_result.get('ml_results', {})
    #     ocr_results = primary_result.get('ocr_results', {})
        
    #     # Clean extracted text if available
    #     if 'extracted_text' in ocr_results:
    #         extracted_text = ocr_results.get('extracted_text', {})
    #         # Clean each text entry
    #         for key, value in extracted_text.items():
    #             if isinstance(value, dict) and 'text' in value:
    #                 extracted_text[key]['text'] = clean_extracted_text(value['text'])
    #             elif isinstance(value, str):
    #                 extracted_text[key] = clean_extracted_text(value)
        
    #     # Try to map text to specific fields
    #     mapped_fields = map_extracted_text_to_fields(ocr_results.get('extracted_text', {}))
    #     if mapped_fields:
    #         extracted_fields.update(mapped_fields)
        
    #     # Prepare extracted_data structure
    #     extracted_data = {
    #         'fields': extracted_fields,
    #         'raw_text': ocr_results.get('raw_text', {}),
    #         'confidence_scores': ocr_results.get('confidence_scores', {}),
    #         'field_regions': ocr_results.get('field_regions', []),
    #         'present_fields': ocr_results.get('present_fields', {}),
    #         'field_confidence': ocr_results.get('field_confidence', {}),
    #         'spatial_features_shape': ml_results.get('spatial_features', {}).get('shape', []) if ml_results else [],
    #         'processing_time': primary_result.get('processing_time', 0),
    #         'success': 'error' not in primary_result,
    #         'extracted_text': ocr_results.get('extracted_text', {})
    #     }
        
    #     # Calculate authenticity score
    #     authenticity_score = self._calculate_hybrid_score(primary_result)
        
    #     # Determine status
    #     if authenticity_score >= self.reject_threshold:
    #         status = "Pending Admin Review"
    #         admin_action = "approve"
    #     else:
    #         status = "Auto-Rejected"
    #         admin_action = "reject"
        
    #     # Generate analysis ID
    #     analysis_id = self._generate_analysis_id(provider_id, request_id)
        
    #     # Build comprehensive report
    #     report = {
    #         'analysis_id': analysis_id,
    #         'timestamp': datetime.now().isoformat(),
    #         'provider_id': provider_id,
    #         'request_id': request_id,
    #         'extracted_data': extracted_data,
    #         'authenticity_score': round(authenticity_score, 4),
    #         'status': status,
    #         'admin_action': admin_action,
    #         'quality_metrics': {
    #             'ocr_confidence': primary_result.get('ocr_results', {}).get('ocr_confidence', 0),
    #             'tampering_confidence': primary_result.get('tampering_results', {}).get('tampering_confidence', 0),
    #             'ml_confidence': primary_result.get('ml_results', {}).get('confidence', 0),
    #             'extraction_method': primary_result.get('extraction_method', 'ocr'),
    #             'script_detected': primary_result.get('script_detection', {}).get('script', 'unknown')
    #         },
    #         'flags': self._generate_hybrid_flags(primary_result),
    #         'page_summaries': [
    #             {
    #                 'page': page['page_number'],
    #                 'tampering_detected': page.get('tampering_results', {}).get('tampering_detected', False),
    #                 'extraction_method': page.get('extraction_method', 'ocr'),
    #                 'script': page.get('script_detection', {}).get('script', 'unknown')
    #             }
    #             for page in page_results
    #         ],
    #         'model_metadata': {
    #             'version': self.model_version,
    #             'config_hash': self.config_hash,
    #             'use_ml': self.use_ml,
    #             'thresholds': {
    #                 'reject': self.reject_threshold,
    #                 'ml_confidence': self.ml_confidence_threshold
    #             }
    #         },
    #         'recommendations': self._generate_ai_recommendations(authenticity_score, primary_result)
    #     }
    #     recommendation = engine.generate_recommendation(
    #       authenticity_score=report['authenticity_score'],
    #       extracted_fields=report['extracted_data']['fields'],
    #       ocr_confidence=report['quality_metrics']['ocr_confidence'],
    #       ml_confidence=report['quality_metrics']['ml_confidence']
    #      )
    #     report['recommendation_result'] = recommendation
    #     return report
    
    def _calculate_hybrid_score(self, analysis_result):
        """Calculate score using OCR, tampering, and ML confidence"""
        ocr_confidence = analysis_result.get('ocr_results', {}).get('ocr_confidence', 0)
        tampering_confidence = 1.0 - analysis_result.get('tampering_results', {}).get('tampering_confidence', 0)
        ml_confidence = analysis_result.get('ml_results', {}).get('confidence', 0)
        extraction_confidence = analysis_result.get('extraction_confidence', 0)
        
        # Field completeness
        extracted_fields = analysis_result.get('extracted_fields', {})
        field_completeness = len([v for v in extracted_fields.values() if v]) / max(1, len(extracted_fields))
        
        # Weighted score
        if self.use_ml and ml_confidence > 0.5:
            # ML-weighted scoring
            weights = {'ocr': 0.3, 'tampering': 0.3, 'ml': 0.2, 'fields': 0.2}
            score = (
                weights['ocr'] * ocr_confidence +
                weights['tampering'] * tampering_confidence +
                weights['ml'] * ml_confidence +
                weights['fields'] * field_completeness
            )
        else:
            # OCR-weighted scoring
            weights = {'ocr': 0.4, 'tampering': 0.4, 'fields': 0.2}
            score = (
                weights['ocr'] * extraction_confidence +
                weights['tampering'] * tampering_confidence +
                weights['fields'] * field_completeness
            )
        
        # Apply sigmoid
        score = 1 / (1 + np.exp(-10 * (score - 0.5)))
        return float(max(0.0, min(1.0, score)))
    
    def _generate_hybrid_flags(self, analysis_result):
        """Generate flags for hybrid analysis"""
        flags = {
            'tampering_detected': analysis_result.get('tampering_results', {}).get('tampering_detected', False),
            'ml_used': analysis_result.get('extraction_method') == 'ml',
            'low_confidence_extraction': analysis_result.get('extraction_confidence', 0) < 0.6,
            'mixed_language': analysis_result.get('script_detection', {}).get('script') == 'mixed',
            'potential_forgery': analysis_result.get('tampering_results', {}).get('tampering_confidence', 0) > 0.7
        }
        return flags
    
    def _generate_ai_recommendations(self, score, analysis_result):
        """Generate AI-powered recommendations"""
        recommendations = []
        
        if score < 0.3:
            recommendations.append("High risk of forgery detected - escalate immediately")
            recommendations.append("Request original physical document")
        
        if analysis_result.get('extraction_method') == 'ocr' and score > 0.5:
            recommendations.append("Consider enabling ML analysis for better accuracy")
        
        if analysis_result.get('tampering_results', {}).get('tampering_detected'):
            recommendations.append("Tampering detected - flag for manual review")
        
        if not recommendations:
            recommendations.append("Certificate appears valid - proceed with verification")
        
        return recommendations

    def health_check(self) -> Dict[str, Any]:
        """
        Health check used during application startup.
        Ensures analyzer is ready for requests.
        """
        try:
            status = {
                "status": "healthy",
                "model_version": self.model_version,
                "use_ml": self.use_ml,
                "components": {
                    "tamper_detector": self.tamper_detector is not None,
                    "script_detector": self.script_detector is not None,
                    "ocr_router": self.ocr_router is not None,
                    "image_processor": self.image_processor is not None,
                    "donut_model": self.use_ml and hasattr(self, "donut_parser"),
                    "ml_extractor": self.use_ml and hasattr(self, "ml_extractor"),
                },
                "redis_available": self._redis_available,
            }

            # Hard failure if a core component is missing
            if not all([
                status["components"]["tamper_detector"],
                status["components"]["script_detector"],
                status["components"]["ocr_router"],
                status["components"]["image_processor"],
            ]):
                status["status"] = "unhealthy"

            return status

        except Exception as e:
            logger.error(f"Analyzer health check failed: {e}", exc_info=True)
            return {
                "status": "unhealthy",
                "error": str(e)
            }
# import logging
# import hashlib
# import tempfile
# import asyncio
# import os
# from datetime import datetime
# from typing import Dict, Any, List, Optional, Union
# from pathlib import Path
# import json
# import time

# from app.analyzers.tamper_detector import ProductionTamperDetector
# from app.analyzers.script_detector import ScriptDetector
# from app.analyzers.ocr.router import MultilingualOCRRouter
# from app.analyzers.ml_models.donut_model import DonutCertificateParser
# from app.analyzers.ml_models.field_extractor import MLFieldExtractor
# from app.utils.image_processing import ImageProcessor
# from fastapi import UploadFile
# import aiohttp
# from app.utils.config import settings
# import aiofiles
# import numpy as np
# import cv2
# from PIL import Image

# logger = logging.getLogger(__name__)


# class ProductionCertificateAnalyzer:
#     """AI-powered certificate analyzer with hybrid approach"""
    
#     def __init__(self, use_ml: bool = True):
#         self.model_version = "2024.2.0-ai-hybrid"
#         self.use_ml = use_ml
        
#         # Initialize components
#         self.tamper_detector = ProductionTamperDetector()
#         self.script_detector = ScriptDetector()
#         self.ocr_router = MultilingualOCRRouter(self.script_detector)
#         self.image_processor = ImageProcessor()
        
#         # ML models (optional)
#         if self.use_ml:
#             try:
#                 self.donut_parser = DonutCertificateParser()
#                 self.ml_extractor = MLFieldExtractor()
#                 logger.info("ML models loaded successfully")
#             except Exception as e:
#                 logger.warning(f"Failed to load ML models: {e}. Using OCR only.")
#                 self.use_ml = False
        
#         # Configurable thresholds
#         self.reject_threshold = float(settings.reject_threshold)
#         self.low_quality_threshold = 0.7
#         self.ml_confidence_threshold = 0.6
#         self.CACHE_TTL = 3600
        
#         # Redis safety flag
#         self._redis_available = True
#         self.config_hash = self._get_config_hash()
        
#         logger.info(f"ProductionCertificateAnalyzer v{self.model_version} initialized")
#         logger.info(f"ML enabled: {self.use_ml}, Hybrid mode: {'OCR+ML' if self.use_ml else 'OCR only'}")
    
#     def _get_config_hash(self) -> str:
#         """Generate config hash for version tracking"""
#         config_data = {
#             'model_version': self.model_version,
#             'use_ml': self.use_ml,
#             'reject_threshold': self.reject_threshold,
#             'ml_threshold': self.ml_confidence_threshold
#         }
#         return hashlib.sha256(json.dumps(config_data, sort_keys=True).encode()).hexdigest()[:16]
    
#     async def analyze_certificate_file(
#         self, 
#         file: UploadFile, 
#         provider_id: str, 
#         request_id: str
#     ) -> Dict[str, Any]:
#         """Analyze uploaded certificate with AI hybrid approach"""
#         temp_path = None
#         try:
#             logger.info(f"Starting AI analysis for {request_id}")
#             start_time = datetime.now()
            
#             # Check cache
#             file_hash = await self._get_file_hash(file)
#             await file.seek(0)
#             cache_key = f"ai_upload:{provider_id}:{file_hash}"
            
#             if self._redis_available:
#                 cached_result = await self._safe_redis_get(cache_key)
#                 if cached_result:
#                     cached_result['cache_hit'] = True
#                     return cached_result
            
#             # Save uploaded file
#             temp_path = await self._save_upload(file)
            
#             # Process document
#             processed_images = await self.image_processor.process_document(temp_path)
#             if not processed_images:
#                 raise Exception("No valid images extracted from document")
            
#             logger.info(f"Processing {len(processed_images)} pages")
            
#             # Analyze each page with hybrid approach
#             page_tasks = [
#                 self._analyze_single_page_hybrid(img, idx, request_id)
#                 for idx, img in enumerate(processed_images)
#             ]
#             page_results = await asyncio.gather(*page_tasks, return_exceptions=True)
            
#             # Combine results
#             valid_results = [r for r in page_results if not isinstance(r, Exception)]
#             if not valid_results:
#                 raise Exception("All page analyses failed")
            
#             final_report = self._combine_hybrid_results(
#                 valid_results, provider_id, request_id
#             )
            
#             # Add processing metadata
#             processing_time = (datetime.now() - start_time).total_seconds()
#             final_report.update({
#                 'processing_time': round(processing_time, 3),
#                 'model_version': self.model_version,
#                 'config_hash': self.config_hash,
#                 'analysis_mode': 'hybrid_ai' if self.use_ml else 'ocr_only',
#                 'cache_hit': False,
#                 'redis_available': self._redis_available
#             })
            
#             # Cache result
#             if self._redis_available:
#                 await self._safe_redis_setex(cache_key, self.CACHE_TTL, final_report)
            
#             logger.info(f"AI analysis completed in {processing_time}s")
#             return final_report
            
#         except Exception as e:
#             logger.error(f"AI analysis pipeline failed: {str(e)}", exc_info=True)
#             return self._generate_error_report(
#                 provider_id, request_id, str(e), "upload"
#             )
#         finally:
#             if temp_path and Path(temp_path).exists():
#                 try:
#                     Path(temp_path).unlink()
#                 except:
#                     pass
    
#     async def _analyze_single_page_hybrid(
#         self, 
#         image: np.ndarray, 
#         page_num: int, 
#         request_id: str
#     ) -> Dict[str, Any]:
#         """Hybrid analysis: OCR + ML"""
#         try:
#             # Convert to PIL for ML models
#             if len(image.shape) == 3:
#                 pil_image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
#             else:
#                 pil_image = Image.fromarray(image)
            
#             # Step 1: Script detection
#             script_result = self.script_detector.detect(image)
#             language = script_result.get('script', 'unknown')
            
#             # Step 2: Parallel processing
#             ocr_task = self.ocr_router.extract_text(image)
#             tamper_task = self.tamper_detector.detect_tampering(image)
#             ml_task = self._ml_analysis(pil_image, language) if self.use_ml else None
            
#             # Wait for OCR and tampering
#             ocr_results, tampering_results = await asyncio.gather(ocr_task, tamper_task)
            
#             # Wait for ML if enabled
#             ml_results = await ml_task if ml_task else None
            
#             # Step 3: Merge results
#             if ml_results and ml_results.get('confidence', 0) > self.ml_confidence_threshold:
#                 # Use ML results as primary
#                 extracted_fields = ml_results.get('extracted_fields', {})
#                 extraction_method = 'ml'
#                 extraction_confidence = ml_results.get('confidence', 0)
#             else:
#                 # Use OCR results
#                 extracted_fields = ocr_results.get('extracted_text', {})
#                 extraction_method = 'ocr'
#                 extraction_confidence = ocr_results.get('ocr_confidence', 0)
                
#                 # Enhance with ML if available
#                 if ml_results:
#                     extracted_fields = self._merge_fields(
#                         extracted_fields, 
#                         ml_results.get('extracted_fields', {})
#                     )
            
#             # Extract features
#             ml_features = self._extract_ml_features(
#                 image, ocr_results, tampering_results, ml_results
#             )
            
#             return {
#                 'page_number': page_num,
#                 'script_detection': script_result,
#                 'ocr_results': ocr_results,
#                 'tampering_results': tampering_results,
#                 'ml_results': ml_results,
#                 'extracted_fields': extracted_fields,
#                 'field_confidence': ocr_results.get('field_confidence', {}),
#                 'extraction_method': extraction_method,
#                 'extraction_confidence': extraction_confidence,
#                 'ml_features': ml_features,
#                 'timestamp': datetime.now().isoformat(),
#                 'request_id': request_id
#             }
            
#         except Exception as e:
#             logger.error(f"Hybrid analysis failed for page {page_num}: {e}")
#             return {
#                 'page_number': page_num,
#                 'error': str(e),
#                 'timestamp': datetime.now().isoformat()
#             }
    
#     async def _ml_analysis(self, image: Image.Image, language: str) -> Optional[Dict[str, Any]]:
#         """ML-based analysis"""
#         try:
#             # Use Donut for parsing
#             donut_result = self.donut_parser.parse_certificate(image, language)
            
#             # Use ML field extractor
#             ml_fields = self.ml_extractor.extract_fields(image)
            
#             # Merge results
#             extracted_fields = {}
#             if donut_result.get('parsed_data'):
#                 extracted_fields.update(donut_result['parsed_data'])
#             if ml_fields:
#                 extracted_fields.update(ml_fields)
            
#             return {
#                 'extracted_fields': extracted_fields,
#                 'confidence': donut_result.get('confidence', 0.7),
#                 'donut_result': donut_result,
#                 'ml_fields': ml_fields,
#                 'model_used': 'donut+ml_extractor'
#             }
#         except Exception as e:
#             logger.debug(f"ML analysis failed: {e}")
#             return None
    
#     def _merge_fields(self, ocr_fields: Dict, ml_fields: Dict) -> Dict:
#         """Intelligently merge OCR and ML results"""
#         merged = ocr_fields.copy()
        
#         for key, ml_value in ml_fields.items():
#             if key not in merged:
#                 # ML found something OCR missed
#                 merged[key] = ml_value
#             elif ml_value and (not merged[key] or len(ml_value) > len(merged[key])):
#                 # ML value is better (longer/more complete)
#                 merged[key] = ml_value
        
#         return merged
    
#     def _extract_ml_features(self, image, ocr_results, tampering_results, ml_results):
#         """Enhanced feature extraction"""
#         features = {
#             'image_stats': {
#                 'shape': image.shape if hasattr(image, 'shape') else (0, 0, 0),
#                 'entropy': self._calculate_image_entropy(image)
#             },
#             'ocr_features': {
#                 'confidence': ocr_results.get('ocr_confidence', 0),
#                 'language': ocr_results.get('language', 'unknown'),
#                 'word_count': ocr_results.get('word_count', 0)
#             },
#             'tampering_features': {
#                 'detected': tampering_results.get('tampering_detected', False),
#                 'confidence': tampering_results.get('tampering_confidence', 0)
#             },
#             'ml_features': {
#                 'used': ml_results is not None,
#                 'confidence': ml_results.get('confidence', 0) if ml_results else 0,
#                 'model': ml_results.get('model_used', 'none') if ml_results else 'none'
#             }
#         }
#         return features
    
#     def _combine_hybrid_results(self, page_results, provider_id, request_id):
#         """Combine hybrid analysis results"""
#         primary_result = page_results[0]
        
#         # Calculate authenticity score
#         authenticity_score = self._calculate_hybrid_score(primary_result)
        
#         # Determine status
#         if authenticity_score >= self.reject_threshold:
#             status = "Pending Admin Review"
#             admin_action = "approve"
#         else:
#             status = "Auto-Rejected"
#             admin_action = "reject"
        
#         # Generate analysis ID
#         analysis_id = self._generate_analysis_id(provider_id, request_id)
        
#         # Build comprehensive report
#         report = {
#             'analysis_id': analysis_id,
#             'timestamp': datetime.now().isoformat(),
#             'provider_id': provider_id,
#             'request_id': request_id,
#             'extracted_data': primary_result.get('extracted_fields', {}),
#             'authenticity_score': round(authenticity_score, 4),
#             'status': status,
#             'admin_action': admin_action,
#             'quality_metrics': {
#                 'ocr_confidence': primary_result.get('ocr_results', {}).get('ocr_confidence', 0),
#                 'tampering_confidence': primary_result.get('tampering_results', {}).get('tampering_confidence', 0),
#                 'ml_confidence': primary_result.get('ml_results', {}).get('confidence', 0),
#                 'extraction_method': primary_result.get('extraction_method', 'ocr'),
#                 'script_detected': primary_result.get('script_detection', {}).get('script', 'unknown')
#             },
#             'flags': self._generate_hybrid_flags(primary_result),
#             'page_summaries': [
#                 {
#                     'page': page['page_number'],
#                     'tampering_detected': page.get('tampering_results', {}).get('tampering_detected', False),
#                     'extraction_method': page.get('extraction_method', 'ocr'),
#                     'script': page.get('script_detection', {}).get('script', 'unknown')
#                 }
#                 for page in page_results
#             ],
#             'model_metadata': {
#                 'version': self.model_version,
#                 'config_hash': self.config_hash,
#                 'use_ml': self.use_ml,
#                 'thresholds': {
#                     'reject': self.reject_threshold,
#                     'ml_confidence': self.ml_confidence_threshold
#                 }
#             },
#             'recommendations': self._generate_ai_recommendations(authenticity_score, primary_result)
#         }
        
#         return report
    
#     def _calculate_hybrid_score(self, analysis_result):
#         """Calculate score using OCR, tampering, and ML confidence"""
#         ocr_confidence = analysis_result.get('ocr_results', {}).get('ocr_confidence', 0)
#         tampering_confidence = 1.0 - analysis_result.get('tampering_results', {}).get('tampering_confidence', 0)
#         ml_confidence = analysis_result.get('ml_results', {}).get('confidence', 0)
#         extraction_confidence = analysis_result.get('extraction_confidence', 0)
        
#         # Field completeness
#         extracted_fields = analysis_result.get('extracted_fields', {})
#         field_completeness = len([v for v in extracted_fields.values() if v]) / max(1, len(extracted_fields))
        
#         # Weighted score
#         if self.use_ml and ml_confidence > 0.5:
#             # ML-weighted scoring
#             weights = {'ocr': 0.3, 'tampering': 0.3, 'ml': 0.2, 'fields': 0.2}
#             score = (
#                 weights['ocr'] * ocr_confidence +
#                 weights['tampering'] * tampering_confidence +
#                 weights['ml'] * ml_confidence +
#                 weights['fields'] * field_completeness
#             )
#         else:
#             # OCR-weighted scoring
#             weights = {'ocr': 0.4, 'tampering': 0.4, 'fields': 0.2}
#             score = (
#                 weights['ocr'] * extraction_confidence +
#                 weights['tampering'] * tampering_confidence +
#                 weights['fields'] * field_completeness
#             )
        
#         # Apply sigmoid
#         score = 1 / (1 + np.exp(-10 * (score - 0.5)))
#         return float(max(0.0, min(1.0, score)))
    
#     def _generate_hybrid_flags(self, analysis_result):
#         """Generate flags for hybrid analysis"""
#         flags = {
#             'tampering_detected': analysis_result.get('tampering_results', {}).get('tampering_detected', False),
#             'ml_used': analysis_result.get('extraction_method') == 'ml',
#             'low_confidence_extraction': analysis_result.get('extraction_confidence', 0) < 0.6,
#             'mixed_language': analysis_result.get('script_detection', {}).get('script') == 'mixed',
#             'potential_forgery': analysis_result.get('tampering_results', {}).get('tampering_confidence', 0) > 0.7
#         }
#         return flags
    
#     def _generate_ai_recommendations(self, score, analysis_result):
#         """Generate AI-powered recommendations"""
#         recommendations = []
        
#         if score < 0.3:
#             recommendations.append("High risk of forgery detected - escalate immediately")
#             recommendations.append("Request original physical document")
        
#         if analysis_result.get('extraction_method') == 'ocr' and score > 0.5:
#             recommendations.append("Consider enabling ML analysis for better accuracy")
        
#         if analysis_result.get('tampering_results', {}).get('tampering_detected'):
#             recommendations.append("Tampering detected - flag for manual review")
        
#         if not recommendations:
#             recommendations.append("Certificate appears valid - proceed with verification")
        
#         return recommendations

#     def health_check(self) -> Dict[str, Any]:
#         """
#         Health check used during application startup.
#         Ensures analyzer is ready for requests.
#         """
#         try:
#             status = {
#                 "status": "healthy",
#                 "model_version": self.model_version,
#                 "use_ml": self.use_ml,
#                 "components": {
#                     "tamper_detector": self.tamper_detector is not None,
#                     "script_detector": self.script_detector is not None,
#                     "ocr_router": self.ocr_router is not None,
#                     "image_processor": self.image_processor is not None,
#                     "donut_model": self.use_ml and hasattr(self, "donut_parser"),
#                     "ml_extractor": self.use_ml and hasattr(self, "ml_extractor"),
#                 },
#                 "redis_available": self._redis_available,
#             }

#             # Hard failure if a core component is missing
#             if not all([
#                 status["components"]["tamper_detector"],
#                 status["components"]["script_detector"],
#                 status["components"]["ocr_router"],
#                 status["components"]["image_processor"],
#             ]):
#                 status["status"] = "unhealthy"

#             return status

#         except Exception as e:
#             logger.error(f"Analyzer health check failed: {e}", exc_info=True)
#             return {
#                 "status": "unhealthy",
#                 "error": str(e)
#             }
