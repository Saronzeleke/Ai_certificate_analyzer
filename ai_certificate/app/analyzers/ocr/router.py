import logging
from typing import Dict, Any, Optional
import numpy as np
from datetime import datetime

from .multilingual_ocr import MultilingualOCREngine
from ..script_detector import ScriptDetector

logger = logging.getLogger(__name__)

class MultilingualOCRRouter:
    """Intelligent router for OCR engine selection"""
    
    def __init__(self, script_detector: Optional[ScriptDetector] = None,
                 tessdata_path: Optional[str] = None):
        self.script_detector = script_detector
        self.ocr_engine = MultilingualOCREngine(tessdata_path)
        
        # Performance tracking
        self.stats = {
            'total_requests': 0,
            'english_requests': 0,
            'amharic_requests': 0,
            'mixed_requests': 0,
            'fallbacks': 0,
            'success_rate': 0.0
        }
        
        # Cache for script detection (small LRU)
        self._script_cache = {}
        self._cache_size = 100
        
        logger.info("MultilingualOCRRouter initialized")
    
    async def extract_text(self, image: np.ndarray, 
                          language_hint: Optional[str] = None) -> Dict[str, Any]:
        """Extract text with intelligent routing"""
        self.stats['total_requests'] += 1
        
        try:
            start_time = datetime.now()
            
            # Step 1: Script detection (if available)
            detected_script = None
            detection_confidence = 0.0
            
            if self.script_detector:
                # Check cache first
                image_hash = hash(image.tobytes())
                if image_hash in self._script_cache:
                    detected_script, detection_confidence = self._script_cache[image_hash]
                else:
                    detection_result = self.script_detector.detect(image)
                    detected_script = detection_result.get('script', 'unknown')
                    detection_confidence = detection_result.get('confidence', 0.0)
                    
                    # Cache result
                    if len(self._script_cache) >= self._cache_size:
                        self._script_cache.pop(next(iter(self._script_cache)))
                    self._script_cache[image_hash] = (detected_script, detection_confidence)
            
            # Step 2: Determine routing strategy
            routing_strategy = self._determine_routing_strategy(
                detected_script, detection_confidence, language_hint
            )
            
            logger.info(f"Routing: script={detected_script}, "
                       f"conf={detection_confidence:.2f}, strategy={routing_strategy}")
            
            # Step 3: Execute OCR with chosen strategy
            if routing_strategy == 'english_primary':
                self.stats['english_requests'] += 1
                result = await self.ocr_engine.extract_with_fallback(image, 'english')
                
            elif routing_strategy == 'amharic_primary':
                self.stats['amharic_requests'] += 1
                result = await self.ocr_engine.extract_with_fallback(image, 'amharic')
                
            elif routing_strategy == 'mixed_analysis':
                self.stats['mixed_requests'] += 1
                result = await self.ocr_engine.extract(image)
                
            else:  # auto or unknown
                result = await self.ocr_engine.extract(image)
            
            # Step 4: Enhance results with script detection info
            if detected_script and detection_confidence > 0.5:
                result['script_detection'] = {
                    'script': detected_script,
                    'confidence': detection_confidence
                }
            
            # Step 5: Update statistics
            if result.get('success', False):
                self._update_success_stats()
            else:
                self.stats['fallbacks'] += 1
            
            # Add routing metadata
            result['routing'] = {
                'strategy': routing_strategy,
                'detected_script': detected_script,
                'detection_confidence': detection_confidence,
                'language_hint': language_hint
            }
            
            # Calculate processing time
            processing_time = (datetime.now() - start_time).total_seconds()
            result['routing_time'] = processing_time
            
            logger.info(f"OCR routing completed in {processing_time:.2f}s")
            return result
            
        except Exception as e:
            logger.error(f"OCR routing failed: {e}")
            self.stats['fallbacks'] += 1
            
            # Ultimate fallback
            try:
                result = await self.ocr_engine.extract_with_fallback(image, 'english')
                result['routing_fallback'] = True
                result['routing_error'] = str(e)
                return result
            except Exception as fallback_error:
                return self._get_error_response(f"Routing failed: {e}, Fallback failed: {fallback_error}")
    
    def _determine_routing_strategy(self, detected_script: Optional[str],
                                  detection_confidence: float,
                                  language_hint: Optional[str]) -> str:
        """Determine the best OCR routing strategy"""
        
        # Priority 1: Language hint from user
        if language_hint:
            if language_hint.lower() in ['eng', 'english']:
                return 'english_primary'
            elif language_hint.lower() in ['amh', 'amharic']:
                return 'amharic_primary'
        
        # Priority 2: High-confidence script detection
        if detected_script and detection_confidence > 0.7:
            if detected_script == 'english':
                return 'english_primary'
            elif detected_script == 'amharic':
                return 'amharic_primary'
            elif detected_script == 'mixed':
                return 'mixed_analysis'
        
        # Priority 3: Medium-confidence detection
        if detected_script and detection_confidence > 0.5:
            if detected_script in ['english', 'amharic']:
                return f'{detected_script}_primary'
            else:
                return 'mixed_analysis'
        
        # Priority 4: Default to mixed analysis
        return 'mixed_analysis'
    
    def _update_success_stats(self):
        """Update success rate statistics"""
        successful = (self.stats['english_requests'] + 
                     self.stats['amharic_requests'] + 
                     self.stats['mixed_requests'])
        total = self.stats['total_requests']
        
        if total > 0:
            self.stats['success_rate'] = successful / total
    
    def _get_error_response(self, error_msg: str) -> Dict[str, Any]:
        """Return error response"""
        return {
            'extracted_text': {},
            'field_confidence': {},
            'ocr_confidence': 0.0,
            'raw_text': '',
            'language': 'unknown',
            'error': error_msg,
            'success': False,
            'timestamp': datetime.now().isoformat(),
            'routing': {'strategy': 'error', 'error': error_msg}
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get performance statistics"""
        stats = self.stats.copy()
        stats['cache_size'] = len(self._script_cache)
        stats['timestamp'] = datetime.now().isoformat()
        return stats
    
    def reset_statistics(self):
        """Reset performance statistics"""
        self.stats = {
            'total_requests': 0,
            'english_requests': 0,
            'amharic_requests': 0,
            'mixed_requests': 0,
            'fallbacks': 0,
            'success_rate': 0.0
        }
        self._script_cache.clear()
        logger.info("OCR router statistics reset")
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on OCR router"""
        try:
            # Test with a simple image
            test_image = np.zeros((100, 100, 3), dtype=np.uint8)
            test_image[25:75, 25:75] = 255  # White square
            
            # Test OCR engine
            result = await self.ocr_engine.extract(test_image)
            
            # Test script detector if available
            script_status = "not_available"
            if self.script_detector:
                script_result = self.script_detector.detect(test_image)
                script_status = "available" if script_result else "failed"
            
            return {
                'status': 'healthy',
                'ocr_engine': 'operational',
                'script_detector': script_status,
                'timestamp': datetime.now().isoformat(),
                'statistics': self.get_statistics()
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }