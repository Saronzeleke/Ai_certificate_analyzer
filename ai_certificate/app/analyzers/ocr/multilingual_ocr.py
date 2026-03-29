import logging
import asyncio
from typing import Dict, Any, List, Optional
import numpy as np
from datetime import datetime

from .english_ocr import EnglishOCREngine
from .amharic_ocr import AmharicOCREngine

logger = logging.getLogger(__name__)

class MultilingualOCREngine:
    """Unified OCR engine that handles both English and Amharic"""
    
    def __init__(self, tessdata_path: Optional[str] = None):
        self.model_version = "2024.1.0-multilingual"
        
        # Initialize individual engines
        self.english_engine = EnglishOCREngine()
        self.amharic_engine = AmharicOCREngine(tessdata_path)
        
        # Script detection cache
        self._script_cache = {}
        
        logger.info(f"MultilingualOCREngine v{self.model_version} initialized")
    
    async def extract(self, image: np.ndarray, 
                     language_hint: Optional[str] = None) -> Dict[str, Any]:
        """Extract text with automatic language detection"""
        try:
            start_time = datetime.now()
            
            # If language hint provided, use specific engine
            if language_hint and language_hint.lower() in ['eng', 'english']:
                logger.info("Using English engine (hint provided)")
                result = await self.english_engine.extract(image)
                result['engine_used'] = 'english_only'
                return result
            
            elif language_hint and language_hint.lower() in ['amh', 'amharic']:
                logger.info("Using Amharic engine (hint provided)")
                result = await self.amharic_engine.extract(image)
                result['engine_used'] = 'amharic_only'
                return result
            
            # Auto-detect: try both engines in parallel
            english_task = asyncio.create_task(self.english_engine.extract(image))
            amharic_task = asyncio.create_task(self.amharic_engine.extract(image))
            
            english_result, amharic_result = await asyncio.gather(
                english_task, amharic_task, return_exceptions=True
            )
            
            # Handle exceptions
            if isinstance(english_result, Exception):
                logger.error(f"English OCR failed: {english_result}")
                english_result = None
            if isinstance(amharic_result, Exception):
                logger.error(f"Amharic OCR failed: {amharic_result}")
                amharic_result = None
            
            # Determine best result
            best_result = self._select_best_result(english_result, amharic_result, image)
            
            # Calculate processing time
            processing_time = (datetime.now() - start_time).total_seconds()
            best_result['processing_time'] = processing_time
            
            logger.info(f"Multilingual OCR completed in {processing_time:.2f}s")
            return best_result
            
        except Exception as e:
            logger.error(f"Multilingual OCR extraction failed: {e}")
            # Ultimate fallback
            try:
                result = await self.english_engine.extract(image)
                result['fallback_used'] = True
                result['error'] = str(e)
                return result
            except Exception as fallback_error:
                return self._get_error_response(f"All OCR failed: {e}, {fallback_error}")
    
    def _select_best_result(self, english_result: Optional[Dict], 
                          amharic_result: Optional[Dict],
                          image: np.ndarray) -> Dict[str, Any]:
        """Select the best OCR result between English and Amharic"""
        
        if not english_result and not amharic_result:
            return self._get_error_response("No OCR results from any engine")
        
        if not amharic_result:
            english_result['engine_used'] = 'english_fallback'
            return english_result
        
        if not english_result:
            amharic_result['engine_used'] = 'amharic_only'
            return amharic_result
        
        # Both results available, choose based on confidence and content
        eng_confidence = english_result.get('ocr_confidence', 0)
        amh_confidence = amharic_result.get('ocr_confidence', 0)
        
        # Check which text looks more like a certificate
        eng_score = self._calculate_certificate_score(english_result)
        amh_score = self._calculate_certificate_score(amharic_result)
        
        # Combined score
        eng_total = eng_confidence * 0.7 + eng_score * 0.3
        amh_total = amh_confidence * 0.7 + amh_score * 0.3
        
        logger.info(f"English score: {eng_total:.3f} (conf: {eng_confidence:.3f}, cert: {eng_score:.3f})")
        logger.info(f"Amharic score: {amh_total:.3f} (conf: {amh_confidence:.3f}, cert: {amh_score:.3f})")
        
        if amh_total > eng_total + 0.1:  # Amharic significantly better
            amharic_result['engine_used'] = 'amharic_selected'
            amharic_result['selection_reason'] = f"Higher score ({amh_total:.3f} > {eng_total:.3f})"
            return amharic_result
        else:
            english_result['engine_used'] = 'english_selected'
            english_result['selection_reason'] = f"Higher or equal score ({eng_total:.3f} >= {amh_total:.3f})"
            return english_result
    
    def _calculate_certificate_score(self, ocr_result: Dict) -> float:
        """Calculate how much the text looks like a certificate"""
        if not ocr_result.get('success', False):
            return 0.0
        
        extracted = ocr_result.get('extracted_text', {})
        raw_text = ocr_result.get('raw_text', '').lower()
        
        score = 0.0
        
        # Check for certificate keywords
        certificate_keywords = ['certificate', 'diploma', 'degree', 'university', 
                               'college', 'issued', 'completed', 'awarded']
        
        keyword_count = sum(1 for keyword in certificate_keywords if keyword in raw_text)
        score += min(keyword_count * 0.1, 0.3)
        
        # Check field completeness
        required_fields = ['name', 'student_id', 'university', 'course']
        present_fields = sum(1 for field in required_fields if field in extracted and extracted[field])
        
        score += (present_fields / len(required_fields)) * 0.4
        
        # Check text structure (should have multiple lines)
        lines = raw_text.split('\n')
        if len(lines) >= 5:
            score += 0.2
        
        # Check for date patterns
        import re
        date_patterns = [
            r'\d{1,2}/\d{1,2}/\d{4}',
            r'\d{1,2}-\d{1,2}-\d{4}',
            r'\d{4}-\d{1,2}-\d{1,2}'
        ]
        
        for pattern in date_patterns:
            if re.search(pattern, raw_text):
                score += 0.1
                break
        
        return min(score, 1.0)
    
    async def extract_with_fallback(self, image: np.ndarray, 
                                  primary_language: str = 'auto') -> Dict[str, Any]:
        """Extract text with primary language preference and fallback"""
        if primary_language == 'english':
            result = await self.english_engine.extract(image)
            if result.get('success', False) and result.get('ocr_confidence', 0) > 0.5:
                result['engine_used'] = 'english_primary'
                return result
            else:
                # Fallback to Amharic
                logger.info("English failed, falling back to Amharic")
                result = await self.amharic_engine.extract(image)
                result['engine_used'] = 'amharic_fallback'
                return result
        
        elif primary_language == 'amharic':
            result = await self.amharic_engine.extract(image)
            if result.get('success', False) and result.get('ocr_confidence', 0) > 0.5:
                result['engine_used'] = 'amharic_primary'
                return result
            else:
                # Fallback to English
                logger.info("Amharic failed, falling back to English")
                result = await self.english_engine.extract(image)
                result['engine_used'] = 'english_fallback'
                return result
        
        else:  # auto
            return await self.extract(image)
    
    def _get_error_response(self, error_msg: str) -> Dict[str, Any]:
        """Return error response"""
        return {
            'extracted_text': {},
            'field_confidence': {},
            'ocr_confidence': 0.0,
            'raw_text': '',
            'language': 'unknown',
            'engine_used': 'none',
            'model_version': self.model_version,
            'error': error_msg,
            'success': False,
            'timestamp': datetime.now().isoformat()
        }
    
    async def batch_extract(self, images: List[np.ndarray],
                          language_hints: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Extract text from multiple images"""
        tasks = []
        
        for i, image in enumerate(images):
            hint = language_hints[i] if language_hints and i < len(language_hints) else None
            tasks.append(self.extract(image, hint))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions in batch
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Batch item {i} failed: {result}")
                processed_results.append(self._get_error_response(str(result)))
            else:
                processed_results.append(result)
        
        return processed_results