import logging
import pytesseract
import cv2
import numpy as np
from typing import Dict, Any, List, Optional
from datetime import datetime
import re
import asyncio
import os

logger = logging.getLogger(__name__)

class AmharicOCREngine:
    """OCR engine for Amharic certificates with English fallback"""
    
    def __init__(self, tessdata_path: Optional[str] = None):
        self.model_version = "2024.1.0-amh-enhanced"
        self.language = "amh+eng"  # Include English for mixed content
        
        # Set Tesseract data path for Amharic
        if tessdata_path and os.path.exists(tessdata_path):
            os.environ['TESSDATA_PREFIX'] = tessdata_path
            logger.info(f"TESSDATA_PREFIX set to: {tessdata_path}")
        
        # Test if Amharic is available
        self.amharic_available = self._check_amharic_available()
        
        # Configuration optimized for Ethiopic script
        self.configs = {
            'amharic_primary': '--oem 3 --psm 6 -l amh --dpi 300',
            'amharic_sparse': '--oem 3 --psm 3 -l amh --dpi 300',
            'mixed': '--oem 3 --psm 6 -l amh+eng --dpi 300',
            'english_fallback': '--oem 3 --psm 6 -l eng --dpi 300'
        }
        
        # Production-grade Amharic field patterns (University + Training certificates)
        self.field_patterns = {
            'name': [
                # Training certificate: "ስም:" followed by name
                r'ስም[:\s]+([\u1200-\u137F\s]+?)(?=\s*የተማሪ|\s*ዩኒቨርሲቲ|\s*ኮርስ|\s*የተሰጠበት|\n|$)',
                # English fallback
                r'Name[:\s]*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})',
            ],
            'student_id': [
                # Amharic with brackets support
                r'የተማሪ\s+መታወቂያ[:\s]*([A-Z0-9\[\]]+\d+)',
                r'መታወቂያ[:\s]*([A-Z0-9\[\]]+\d+)',
                # English
                r'Student\s+ID[:\s]*([A-Z0-9\-]+)',
                r'ID[:\s]*([A-Z]{2,3}\d{5,})',
            ],
            'university': [
                # Training certificate: "ዩኒቨርሲቲ:" or organization
                r'ዩኒቨርሲቲ[:\s]+([\u1200-\u137F\s]+?)(?=\s*ኮርስ|\s*አማካይ|\s*የተሰጠበት|\n|$)',
                # English
                r'University[:\s]*([A-Z][a-zA-Z\s]+?)(?=\s+Course|\s+GPA|\n|$)',
            ],
            'course': [
                # Training certificate: "ኮርስ:" followed by course name (can be short)
                r'ኮርስ[:\s]+([\u1200-\u137F\s]+?)(?=\s*አማካይ|\s*ነጥብ|\s*የተሰጠበት|\n|$)',
                # English
                r'Course[:\s]*([A-Za-z\s]+?)(?=\s+GPA|\s+Grade|\n|$)',
            ],
            'gpa': [
                # Amharic GPA patterns
                r'አማካይ\s+ነጥብ[:\s]*([0-4]\.\d{1,2})',
                r'ነጥብ[:\s]*([0-4]\.\d{1,2})',
                # English
                r'GPA[:\s]*([0-4]\.\d{1,2})',
                # Standalone number (last resort)
                r'(?<![0-9])([0-4]\.\d{2})(?![0-9])',
            ],
            'issue_date': [
                # Training certificate: "የተሰጠበት ቀን:" followed by date
                r'የተሰጠበት\s+ቀን[:\s]*(\d{4}[-/]\d{1,2}[-/]\d{1,2})',
                r'ቀን[:\s]*(\d{4}[-/]\d{1,2}[-/]\d{1,2})',
                # English
                r'Date[:\s]*(\d{4}[-/]\d{1,2}[-/]\d{1,2})',
                # Any date
                r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})',
            ]
        }
        
        # Ethiopic Unicode ranges for validation
        self.ethiopic_ranges = [
            (0x1200, 0x137F),  # Ethiopic
            (0x1380, 0x139F),  # Ethiopic Supplement
            (0x2D80, 0x2DDF),  # Ethiopic Extended
        ]
        
        logger.info(f"AmharicOCREngine v{self.model_version} initialized")
        logger.info(f"Amharic language available: {self.amharic_available}")
    
    def _check_amharic_available(self) -> bool:
        """Check if Amharic language is available in Tesseract"""
        try:
            # Try to get available languages
            import subprocess
            result = subprocess.run(['tesseract', '--list-langs'], 
                                  capture_output=True, text=True)
            langs = result.stdout.lower()
            return 'amh' in langs
        except:
            try:
                # Alternative method
                pytesseract.get_tesseract_version()
                # Try a simple OCR with Amharic
                test_image = np.zeros((100, 100, 3), dtype=np.uint8)
                pytesseract.image_to_string(test_image, lang='amh')
                return True
            except:
                return False
    
    def _is_ethiopic_char(self, char: str) -> bool:
        """Check if character is Ethiopic"""
        try:
            code = ord(char)
            for start, end in self.ethiopic_ranges:
                if start <= code <= end:
                    return True
            return False
        except:
            return False
    
    def _contains_amharic(self, text: str) -> bool:
        """Check if text contains Amharic characters"""
        return any(self._is_ethiopic_char(c) for c in text)
    
    def _calculate_amharic_ratio(self, text: str) -> float:
        """Calculate ratio of Amharic characters in text"""
        if not text:
            return 0.0
        
        total_chars = len(text)
        amharic_chars = sum(1 for c in text if self._is_ethiopic_char(c))
        
        return amharic_chars / total_chars
    
    async def extract(self, image: np.ndarray) -> Dict[str, Any]:
        """Extract text from certificate with Amharic/English detection"""
        try:
            start_time = datetime.now()
            
            # Detect script
            script_type = self._detect_script(image)
            logger.info(f"Detected script: {script_type}")
            
            # Preprocess based on script
            processed_images = self._preprocess_for_script(image, script_type)
            
            # Try appropriate OCR configurations
            ocr_results = []
            
            if script_type == "amharic" and self.amharic_available:
                # Try Amharic configurations first
                configs_to_try = ['amharic_primary', 'amharic_sparse', 'mixed']
            elif script_type == "mixed":
                configs_to_try = ['mixed', 'amharic_primary', 'english_fallback']
            else:
                # Fallback to English
                configs_to_try = ['english_fallback', 'mixed']
            
            for config_name in configs_to_try:
                config = self.configs[config_name]
                try:
                    result = await self._run_ocr_with_config(processed_images, config_name, config)
                    
                    # Calculate Amharic ratio for confidence adjustment
                    amharic_ratio = self._calculate_amharic_ratio(result['text'])
                    
                    # Adjust confidence based on script match
                    if script_type == "amharic" and amharic_ratio > 0.3:
                        result['confidence'] *= (1.0 + amharic_ratio * 0.5)
                    elif script_type == "english" and amharic_ratio < 0.1:
                        result['confidence'] *= 1.1
                    
                    if result['confidence'] > 0.1:
                        ocr_results.append(result)
                        
                except Exception as e:
                    logger.debug(f"OCR config {config_name} failed: {e}")
                    continue
            
            if not ocr_results:
                # Ultimate fallback: English only
                logger.warning("All OCR attempts failed, using English fallback")
                from .english_ocr import EnglishOCREngine
                eng_engine = EnglishOCREngine()
                return await eng_engine.extract(image)
            
            # Select best result
            best_result = max(ocr_results, key=lambda x: x['confidence'])
            
            # Extract structured fields
            extracted_fields = self._extract_structured_fields(best_result['text'], script_type)
            
            # Calculate confidence scores
            field_confidence = self._calculate_field_confidence(extracted_fields, best_result['text'])
            
            # Prepare response
            processing_time = (datetime.now() - start_time).total_seconds()
            
            return {
                'extracted_text': extracted_fields,
                'field_confidence': field_confidence,
                'ocr_confidence': best_result['confidence'],
                'raw_text': best_result['text'],
                'language': 'amh' if script_type == "amharic" else 'mixed',
                'script_detected': script_type,
                'amharic_available': self.amharic_available,
                'engine': 'tesseract',
                'model_version': self.model_version,
                'processing_time': processing_time,
                'timestamp': datetime.now().isoformat(),
                'success': True
            }
            
        except Exception as e:
            logger.error(f"Amharic OCR extraction failed: {e}")
            # Fallback to English
            try:
                from .english_ocr import EnglishOCREngine
                eng_engine = EnglishOCREngine()
                result = await eng_engine.extract(image)
                result['fallback_used'] = True
                result['error'] = str(e)
                return result
            except Exception as fallback_error:
                return self._get_error_response(f"Amharic failed: {e}, English fallback also failed: {fallback_error}")
    
    def _detect_script(self, image: np.ndarray) -> str:
        """Detect if image contains Amharic or English text"""
        try:
            # Quick OCR with English to check for Latin script
            config_eng = '--oem 3 --psm 6 -l eng --dpi 150'
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
            
            # Run quick OCR
            text_eng = pytesseract.image_to_string(gray, config=config_eng)
            
            # Count Latin characters
            latin_chars = sum(1 for c in text_eng if c.isalpha() and c.isascii())
            latin_ratio = latin_chars / max(1, len(text_eng))
            
            if self.amharic_available:
                # Try Amharic OCR
                config_amh = '--oem 3 --psm 6 -l amh --dpi 150'
                text_amh = pytesseract.image_to_string(gray, config=config_amh)
                
                # Count Ethiopic characters
                amharic_chars = sum(1 for c in text_amh if self._is_ethiopic_char(c))
                amharic_ratio = amharic_chars / max(1, len(text_amh))
                
                # Determine script
                if amharic_ratio > 0.3 and amharic_ratio > latin_ratio:
                    return "amharic"
                elif latin_ratio > 0.3 and latin_ratio > amharic_ratio:
                    return "english"
                elif amharic_ratio > 0.1 and latin_ratio > 0.1:
                    return "mixed"
            
            # Default to English if Amharic not available or ratios low
            return "english" if latin_ratio > 0.1 else "unknown"
            
        except Exception as e:
            logger.debug(f"Script detection failed: {e}")
            return "unknown"
    
    def _preprocess_for_script(self, image: np.ndarray, script_type: str) -> Dict[str, np.ndarray]:
        """Preprocess image based on script type"""
        variants = {}
        
        # Convert to grayscale
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        
        # Common preprocessing
        variants['original'] = gray
        
        # Amharic-specific preprocessing
        if script_type in ["amharic", "mixed"]:
            # Gentle contrast enhancement for Ethiopic script
            clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8))
            variants['contrast_enhanced'] = clahe.apply(gray)
            
            # Bilateral filter to preserve edges
            variants['bilateral'] = cv2.bilateralFilter(gray, 9, 75, 75)
        
        # English/fallback preprocessing
        if script_type in ["english", "unknown"]:
            # Stronger contrast for Latin script
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            variants['high_contrast'] = clahe.apply(gray)
            
            # Thresholding
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            variants['thresholded'] = thresh
        
        # Common additional variants
        variants['denoised'] = cv2.fastNlMeansDenoising(gray, h=10)
        
        return variants
    
    async def _run_ocr_with_config(self, images: Dict[str, np.ndarray],
                                 config_name: str, config: str) -> Dict[str, Any]:
        """Run OCR with specific configuration"""
        best_text = ""
        best_confidence = 0.0
        
        for variant_name, image in images.items():
            try:
                loop = asyncio.get_event_loop()
                data = await loop.run_in_executor(
                    None,
                    lambda: pytesseract.image_to_data(image, config=config, 
                                                     output_type=pytesseract.Output.DICT)
                )
                
                # Extract text and confidence
                text_parts = []
                confidences = []
                
                for i in range(len(data['text'])):
                    word = data['text'][i].strip()
                    conf = float(data['conf'][i])
                    
                    if word and conf > 0:
                        text_parts.append(word)
                        confidences.append(conf)
                
                if text_parts:
                    text = ' '.join(text_parts)
                    avg_confidence = sum(confidences) / len(confidences) / 100.0
                    
                    # Adjust confidence based on text quality
                    if config_name.startswith('amharic') and self._contains_amharic(text):
                        avg_confidence *= 1.2
                    
                    if avg_confidence > best_confidence:
                        best_confidence = avg_confidence
                        best_text = text
                        
            except Exception as e:
                logger.debug(f"OCR failed for variant {variant_name}: {e}")
                continue
        
        return {
            'text': best_text,
            'confidence': best_confidence,
            'config': config_name
        }
    
    def _extract_structured_fields(self, text: str, script_type: str) -> Dict[str, str]:
        """Extract structured fields from OCR text"""
        extracted = {}
        
        for field, patterns in self.field_patterns.items():
            field_value = None
            
            for pattern in patterns:
                try:
                    # Adjust pattern based on script
                    if script_type == "amharic" and 'ስም' in pattern:
                        flags = re.UNICODE
                    else:
                        flags = re.IGNORECASE | re.UNICODE
                    
                    match = re.search(pattern, text, flags)
                    if match:
                        if len(match.groups()) > 0:
                            value = match.group(1).strip()
                        else:
                            value = match.group(0).strip()
                        
                        # Validate the value
                        if self._validate_field(field, value, script_type):
                            field_value = value
                            break
                except Exception as e:
                    logger.debug(f"Pattern {pattern} failed: {e}")
                    continue
            
            if field_value:
                extracted[field] = field_value
        
        return extracted
    
    def _validate_field(self, field: str, value: str, script_type: str) -> bool:
        """Production-grade field validation"""
        if not value:
            return False
        
        value = value.strip()
        
        if len(value) < 1:  # Allow single char for short courses
            return False
        
        # Field-specific validation
        if field == 'name':
            if script_type == "amharic":
                # Must have Amharic chars, no numbers, no field keywords
                has_amharic = self._contains_amharic(value)
                has_numbers = any(c.isdigit() for c in value)
                bad_keywords = ['መታወቂያ', 'ዩኒቨርሲቲ', 'ኮርስ', 'ነጥብ', 'ቀን', 'ID', 'GPA', 'የተሰጠበት']
                has_bad_keywords = any(kw in value for kw in bad_keywords)
                return has_amharic and len(value) >= 3 and not has_numbers and not has_bad_keywords
            else:
                # English: 2+ words, no numbers, no "FOR SUCCESSFULLY"
                words = value.split()
                has_numbers = any(c.isdigit() for c in value)
                bad_phrases = ['FOR SUCCESSFULLY', 'FOR COMPLETING', 'HAS BEEN']
                has_bad_phrases = any(phrase in value.upper() for phrase in bad_phrases)
                return len(words) >= 2 and all(len(w) > 1 for w in words) and not has_numbers and not has_bad_phrases
        
        elif field == 'student_id':
            # Must have at least one digit
            clean_value = value.replace('[', '').replace(']', '').replace('-', '').replace(',', '').replace('#', '').replace(' ', '')
            has_digit = any(c.isdigit() for c in clean_value)
            return has_digit and 3 <= len(clean_value) <= 30
        
        elif field == 'university':
            if script_type == "amharic":
                has_amharic = self._contains_amharic(value)
                # No GPA numbers, no bad keywords
                has_gpa_pattern = bool(re.search(r'\d\.\d', value))
                bad_keywords = ['ኮርስ', 'ነጥብ', 'ቀን', 'መታወቂያ', 'GPA', 'ID', 'የተሰጠበት']
                has_bad_keywords = any(kw in value for kw in bad_keywords)
                return has_amharic and len(value) >= 2 and not has_gpa_pattern and not has_bad_keywords
            else:
                # English: reasonable length, no GPA, not "STATEMENT OF"
                has_gpa_pattern = bool(re.search(r'\d\.\d', value))
                is_statement = 'STATEMENT OF' in value.upper()
                return 2 <= len(value) <= 100 and not has_gpa_pattern and not is_statement
        
        elif field == 'course':
            if script_type == "amharic":
                has_amharic = self._contains_amharic(value)
                # No GPA numbers, no bad keywords - allow short courses like "ህግ"
                has_gpa_pattern = bool(re.search(r'\d\.\d', value))
                bad_keywords = ['ነጥብ', 'ቀን', 'መታወቂያ', 'ዩኒቨርሲቲ', 'GPA', 'ID', 'የተሰጠበት', 'ስም']
                has_bad_keywords = any(kw in value for kw in bad_keywords)
                return has_amharic and len(value) >= 1 and not has_gpa_pattern and not has_bad_keywords
            else:
                # English: reasonable length, no GPA, not "LENGTH" or "COMPLETED"
                has_gpa_pattern = bool(re.search(r'\d\.\d', value))
                bad_words = ['LENGTH', 'COMPLETED', 'HRS', 'HOURS']
                has_bad_words = any(word in value.upper() for word in bad_words)
                return 2 <= len(value) <= 100 and not has_gpa_pattern and not has_bad_words
        
        elif field == 'gpa':
            # Must be valid GPA number
            try:
                gpa_val = float(value)
                return 0.0 <= gpa_val <= 4.0
            except:
                return False
        
        elif field == 'issue_date':
            # Must match date pattern
            return bool(re.search(r'\d{4}[-/]\d{1,2}[-/]\d{1,2}', value)) or bool(re.search(r'[A-Z]{3}\s+\d{1,2},\s+\d{4}', value))
        
        elif field == 'duration':
            # Training duration validation
            return bool(re.search(r'\d+\s+(?:HRS|HOURS|DAYS|WEEKS|MONTHS)', value.upper()))
        
        return True
    
    def _calculate_field_confidence(self, extracted_fields: Dict[str, str],
                                  raw_text: str) -> Dict[str, float]:
        """Calculate confidence for each extracted field"""
        confidences = {}
        
        for field, value in extracted_fields.items():
            if not value:
                confidences[field] = 0.0
                continue
            
            factors = []
            
            # 1. Field presence
            factors.append(1.0)
            
            # 2. Script consistency
            amharic_ratio = self._calculate_amharic_ratio(value)
            if field == 'name' and amharic_ratio > 0.5:
                factors.append(0.9)  # High confidence for Amharic names
            elif field in ['student_id', 'gpa'] and amharic_ratio < 0.1:
                factors.append(0.9)  # High confidence for non-text fields
            
            # 3. Position in text
            if value in raw_text:
                position = raw_text.find(value) / len(raw_text)
                factors.append(1.0 - position * 0.5)
            
            # 4. Length appropriateness
            if len(value) >= 3:
                factors.append(0.8)
            
            # Average the factors
            avg_confidence = sum(factors) / len(factors) if factors else 0.5
            confidences[field] = min(avg_confidence, 1.0)
        
        return confidences
    
    def _get_error_response(self, error_msg: str) -> Dict[str, Any]:
        """Return error response"""
        return {
            'extracted_text': {},
            'field_confidence': {},
            'ocr_confidence': 0.0,
            'raw_text': '',
            'language': 'unknown',
            'script_detected': 'unknown',
            'amharic_available': self.amharic_available,
            'engine': 'tesseract',
            'model_version': self.model_version,
            'error': error_msg,
            'success': False,
            'timestamp': datetime.now().isoformat()
        }