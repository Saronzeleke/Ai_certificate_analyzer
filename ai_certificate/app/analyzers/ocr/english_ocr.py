import logging
import pytesseract
import cv2
import numpy as np
from typing import Dict, Any, List, Optional
from datetime import datetime
import re
import asyncio
import unicodedata
from dateutil import parser
import spacy

logger = logging.getLogger(__name__)
nlp = spacy.load("en_core_web_sm")  

class EnglishOCREngine:
    """Production-ready OCR engine for English certificates"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.model_version = "2025.1.0-eng-production"
        self.language = "eng"

        # Tesseract configurations
        self.configs = {
            'document': '--oem 3 --psm 1 -l eng --dpi 300',
            'sparse_text': '--oem 3 --psm 6 -l eng --dpi 300',
            'single_line': '--oem 3 --psm 7 -l eng --dpi 300',
            'single_word': '--oem 3 --psm 8 -l eng --dpi 300'
        }

        # Regex patterns for certificate fields
        self.field_patterns = {
            'name': [
                r'Name[:\s]*([A-Z][a-z]+(?: [A-Z][a-z]+){0,3})',
                r'Student Name[:\s]*([A-Z][a-z]+(?: [A-Z][a-z]+){0,3})',
                r'Candidate[:\s]*([A-Z][a-z]+(?: [A-Z][a-z]+){0,3})',
                r'^\s*([A-Z][a-z]+(?: [A-Z][a-z]+){0,3})\s*$'
            ],
            'student_id': [
                r'Student ID[:\s]*([A-Z0-9\-]{5,15})',
                r'ID[:\s]*([A-Z0-9\-]{5,15})',
                r'Registration No[:\s]*([A-Z0-9\-]{5,15})',
                r'\b([A-Z]{2,3}\d{5,8})\b'
            ],
            'university': [
                r'University[:\s]*([A-Z][a-zA-Z\s&.,\-]{5,50})',
                r'College[:\s]*([A-Z][a-zA-Z\s&.,\-]{5,50})',
                r'Institution[:\s]*([A-Z][a-zA-Z\s&.,\-]{5,50})',
                r'\b(University|College|Institute) of ([A-Z][a-zA-Z\s&.,\-]{3,40})\b'
            ],
            'course': [
                r'Course[:\s]*([A-Za-z\s&.,\-]{5,60})',
                r'Program[:\s]*([A-Za-z\s&.,\-]{5,60})',
                r'Degree[:\s]*([A-Za-z\s&.,\-]{5,60})',
                r'in ([A-Za-z\s&.,\-]{5,60}) program'
            ],
            'gpa': [
                r'GPA[:\s]*([0-4]\.\d{1,2})',
                r'Grade Point Average[:\s]*([0-4]\.\d{1,2})',
                r'CGPA[:\s]*([0-4]\.\d{1,2})',
                r'\b([0-4]\.\d{2})\b'
            ],
            'issue_date': [
                r'Date[:\s]*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{4})',
                r'Issued[:\s]*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{4})',
                r'Completed[:\s]*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{4})',
                r'(\d{1,2} (?:January|February|March|April|May|June|July|August|September|October|November|December) \d{4})'
            ],
            'expiry_date': [
                r'Valid until[:\s]*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{4})',
                r'Expires[:\s]*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{4})',
                r'Expiry[:\s]*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{4})'
            ]
        }

        # Validation rules
        self.validation_rules = {
            'name': {'min_length': 4, 'max_length': 50, 'require_caps': True},
            'student_id': {'min_length': 5, 'max_length': 15, 'require_alphanumeric': True},
            'gpa': {'min_value': 0.0, 'max_value': 4.0, 'is_float': True}
        }

        logger.info(f"EnglishOCREngine v{self.model_version} initialized")

    # -----------------------
    # Public API
    # -----------------------
    async def extract(self, image: np.ndarray) -> Dict[str, Any]:
        """Extract structured fields from English certificate image"""
        try:
            start_time = datetime.now()
            images = self._preprocess(image)
            ocr_results = await self._run_ocr_all_configs(images)

            if not ocr_results:
                return self._error("No OCR results")

            best_result = max(ocr_results, key=lambda x: x['confidence'])
            text = self._normalize_text(best_result['text'])
            fields = self._extract_fields(text)

            # ML fallback for critical fields
            fields = self._ml_fallback(fields, text)

            field_conf = self._calculate_confidence(fields, text)
            processing_time = (datetime.now() - start_time).total_seconds()

            return {
                'extracted_text': fields,
                'field_confidence': field_conf,
                'ocr_confidence': best_result['confidence'],
                'raw_text': best_result['text'],
                'language': 'eng',
                'engine': 'tesseract+ner',
                'model_version': self.model_version,
                'processing_time': processing_time,
                'timestamp': datetime.now().isoformat(),
                'success': True
            }

        except Exception as e:
            logger.error(f"OCR extraction failed: {e}")
            return self._error(str(e))

    async def batch_extract(self, image_paths: List[str], batch_size: int = 10) -> List[Dict[str, Any]]:
        """Async batch extraction for multiple images"""
        results = []
        for i in range(0, len(image_paths), batch_size):
            batch = image_paths[i:i+batch_size]
            tasks = [self.extract(cv2.imread(p)) for p in batch]
            results.extend(await asyncio.gather(*tasks))
        return results

    async def validate_certificate(self, fields: Dict[str, str]) -> Dict[str, Any]:
        """Validate certificate fields with scoring"""
        issues = []
        results = {}
        required_fields = ['name', 'student_id', 'university', 'course']

        for f in required_fields:
            if f not in fields or not fields[f]:
                issues.append(f"Missing {f}")
                results[f] = {'valid': False, 'message': 'Missing'}
            else:
                results[f] = {'valid': True, 'message': 'Present'}

        for date_field in ['issue_date', 'expiry_date']:
            if date_field in fields:
                if not self._validate_date(fields[date_field]):
                    issues.append(f"Invalid {date_field}")
                    results[date_field] = {'valid': False, 'message': 'Invalid format'}
                elif date_field == 'expiry_date' and self._is_expired(fields[date_field]):
                    issues.append("Certificate expired")
                    results[date_field] = {'valid': False, 'message': 'Expired'}

        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'field_validations': results,
            'score': max(0.0, 1.0 - 0.2 * len(issues))
        }

    # -----------------------
    # Internal helpers
    # -----------------------
    def _preprocess(self, image: np.ndarray) -> Dict[str, np.ndarray]:
        """Generate multiple preprocessed variants"""
        variants = {}
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        variants['original'] = gray

        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        variants['contrast'] = clahe.apply(gray)
        variants['denoise'] = cv2.fastNlMeansDenoising(gray, h=10)
        _, variants['thresh'] = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        variants['adaptive'] = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                                     cv2.THRESH_BINARY, 11, 2)
        return variants

    async def _run_ocr_all_configs(self, images: Dict[str, np.ndarray]) -> List[Dict[str, Any]]:
        """Run OCR across all configs and image variants"""
        results = []
        loop = asyncio.get_running_loop()

        for cfg_name, cfg in self.configs.items():
            best_text, best_conf = "", 0.0
            for var_name, img in images.items():
                data = await loop.run_in_executor(
                    None,
                    lambda img=img, cfg=cfg: pytesseract.image_to_data(img, config=cfg, output_type=pytesseract.Output.DICT)
                )
                text_parts, conf_parts = [], []
                for i in range(len(data['text'])):
                    word = data['text'][i].strip()
                    try:
                        conf = float(data['conf'][i])
                    except:
                        conf = 0
                    if word and conf > 0:
                        text_parts.append(word)
                        conf_parts.append(conf)
                if text_parts:
                    text = ' '.join(text_parts)
                    avg_conf = sum(conf_parts) / len(conf_parts) / 100
                    if avg_conf > best_conf:
                        best_conf = avg_conf
                        best_text = text
            if best_text:
                results.append({'text': best_text, 'confidence': best_conf, 'config': cfg_name})
        return results

    def _normalize_text(self, text: str) -> str:
        """Clean OCR text"""
        text = unicodedata.normalize('NFKD', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _extract_fields(self, text: str) -> Dict[str, str]:
        """Regex-based field extraction"""
        extracted = {}
        for field, patterns in self.field_patterns.items():
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    value = match.group(1).strip() if match.groups() else match.group(0).strip()
                    extracted[field] = value
                    break
        return extracted

    def _ml_fallback(self, fields: Dict[str, str], text: str) -> Dict[str, str]:
        """Use NER to fill missing name/university/course"""
        doc = nlp(text)
        if 'name' not in fields:
            for ent in doc.ents:
                if ent.label_ == 'PERSON':
                    fields['name'] = ent.text
                    break
        if 'university' not in fields:
            for ent in doc.ents:
                if ent.label_ in ['ORG', 'GPE']:
                    fields['university'] = ent.text
                    break
        return fields

    def _calculate_confidence(self, fields: Dict[str, str], text: str) -> Dict[str, float]:
        """Heuristic confidence scoring"""
        conf = {}
        for f, val in fields.items():
            factors = [1.0] if val else [0.0]
            if val and f in self.validation_rules:
                rules = self.validation_rules[f]
                if 'min_length' in rules and 'max_length' in rules:
                    factors.append(0.8 if rules['min_length'] <= len(val) <= rules['max_length'] else 0.4)
            conf[f] = min(sum(factors)/len(factors), 1.0)
        return conf

    def _validate_date(self, date_str: str) -> bool:
        try:
            parser.parse(date_str)
            return True
        except:
            return False

    def _is_expired(self, date_str: str) -> bool:
        try:
            return parser.parse(date_str).date() < datetime.now().date()
        except:
            return False

    def _error(self, msg: str) -> Dict[str, Any]:
        return {
            'extracted_text': {},
            'field_confidence': {},
            'ocr_confidence': 0.0,
            'raw_text': '',
            'language': 'eng',
            'engine': 'tesseract+ner',
            'model_version': self.model_version,
            'error': msg,
            'success': False,
            'timestamp': datetime.now().isoformat()
        }
