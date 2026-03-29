import pytest
import numpy as np
import cv2
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent))

from app.analyzers.ocr.english_ocr import EnglishOCREngine
from app.analyzers.ocr.amharic_ocr import AmharicOCREngine
from app.analyzers.ocr.multilingual_ocr import MultilingualOCREngine

class TestOCREngines:
    """Production tests for OCR engines"""
    
    @pytest.fixture
    def english_engine(self):
        return EnglishOCREngine()
    
    @pytest.fixture
    def amharic_engine(self):
        return AmharicOCREngine()
    
    @pytest.fixture
    def multilingual_engine(self):
        return MultilingualOCREngine()
    
    def create_test_image(self, text: str, lang: str = 'eng'):
        """Create test image with text"""
        if lang == 'amh':
            # Amharic text might need special handling
            text = "ሙከራ ጽሑፍ" if not text else text
        
        img = np.ones((200, 400, 3), dtype=np.uint8) * 255
        
        # Add text
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.7
        thickness = 2
        
        # Calculate text size for centering
        text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
        text_x = (img.shape[1] - text_size[0]) // 2
        text_y = (img.shape[0] + text_size[1]) // 2
        
        cv2.putText(img, text, (text_x, text_y), font, font_scale, (0, 0, 0), thickness)
        
        return img
    
    @pytest.mark.asyncio
    async def test_english_ocr_basic(self, english_engine):
        """Test basic English OCR"""
        test_text = "CERTIFICATE OF COMPLETION"
        test_image = self.create_test_image(test_text, 'eng')
        
        result = await english_engine.extract(test_image)
        
        assert result['success'] is True
        assert 'extracted_text' in result
        assert 'ocr_confidence' in result
        assert result['ocr_confidence'] > 0.1
        assert result['language'] == 'eng'
    
    @pytest.mark.asyncio
    async def test_english_field_extraction(self, english_engine):
        """Test field extraction from English text"""
        # Create image with certificate-like text
        text_lines = [
            "Name: John Michael Doe",
            "Student ID: STU2023-456",
            "University: Oxford University",
            "Course: Computer Science",
            "GPA: 3.75",
            "Issue Date: 2023-06-15"
        ]
        
        test_image = np.ones((400, 600, 3), dtype=np.uint8) * 255
        font = cv2.FONT_HERSHEY_SIMPLEX
        
        for i, line in enumerate(text_lines):
            y_pos = 50 + i * 50
            cv2.putText(test_image, line, (50, y_pos), font, 0.6, (0, 0, 0), 2)
        
        result = await english_engine.extract(test_image)
        
        assert result['success']
        
        extracted = result['extracted_text']
        # Should extract at least some fields
        assert len(extracted) >= 2
        
        # Check field confidence
        field_conf = result['field_confidence']
        for field, conf in field_conf.items():
            assert 0 <= conf <= 1
    
    @pytest.mark.asyncio
    async def test_amharic_ocr_availability(self, amharic_engine):
        """Test Amharic OCR availability"""
        # Just test that engine initializes
        assert amharic_engine is not None
        assert hasattr(amharic_engine, 'amharic_available')
        
        # Test might fail if Amharic Tesseract not installed
        # That's okay - it's a valid test outcome
        if not amharic_engine.amharic_available:
            pytest.skip("Amharic OCR not available")
    
    @pytest.mark.asyncio
    async def test_multilingual_detection(self, multilingual_engine):
        """Test multilingual language detection"""
        # Create English test image
        eng_image = self.create_test_image("Certificate Test", 'eng')
        
        result = await multilingual_engine.extract(eng_image)
        
        assert result['success']
        assert 'language' in result or 'engine_used' in result
        
        # Should use English engine for English text
        if 'engine_used' in result:
            assert 'english' in result['engine_used'].lower()
    
    @pytest.mark.asyncio
    async def test_ocr_error_handling(self, english_engine):
        """Test OCR error handling"""
        # Test with empty/black image
        empty_image = np.zeros((100, 100, 3), dtype=np.uint8)
        
        result = await english_engine.extract(empty_image)
        
        # Should handle gracefully
        assert 'success' in result
        # Might be False or True with low confidence
        if not result['success']:
            assert 'error' in result
        else:
            assert result['ocr_confidence'] < 0.5
    
    @pytest.mark.asyncio
    async def test_batch_ocr_processing(self, multilingual_engine):
        """Test batch OCR processing"""
        # Create multiple test images
        images = []
        for i in range(3):
            text = f"Test Certificate {i+1}"
            images.append(self.create_test_image(text, 'eng'))
        
        results = await multilingual_engine.batch_extract(images)
        
        assert len(results) == 3
        for result in results:
            assert 'success' in result
            assert 'processing_time' in result or 'timestamp' in result
    
    def test_ocr_configurations(self, english_engine):
        """Test OCR configuration options"""
        assert hasattr(english_engine, 'configs')
        assert isinstance(english_engine.configs, dict)
        
        # Should have multiple configurations for different scenarios
        assert len(english_engine.configs) >= 3
        assert 'document' in english_engine.configs
        assert 'single_line' in english_engine.configs
        
        # Check field patterns
        assert hasattr(english_engine, 'field_patterns')
        assert isinstance(english_engine.field_patterns, dict)
        assert 'name' in english_engine.field_patterns
        assert 'student_id' in english_engine.field_patterns
    
    @pytest.mark.asyncio
    async def test_confidence_calculation(self, english_engine):
        """Test OCR confidence calculation"""
        # Good quality text
        good_image = self.create_test_image("Clear Text for OCR", 'eng')
        good_result = await english_engine.extract(good_image)
        
        # Poor quality (blurry) text
        poor_image = cv2.GaussianBlur(good_image, (9, 9), 5)
        poor_result = await english_engine.extract(poor_image)
        
        # Good result should have higher confidence
        if good_result['success'] and poor_result['success']:
            assert good_result['ocr_confidence'] > poor_result['ocr_confidence']
    
    @pytest.mark.asyncio
    async def test_date_validation(self, english_engine):
        """Test date field validation"""
        # Test valid dates
        valid_dates = ["2023-12-31", "31/12/2023", "12/31/2023"]
        
        for date_str in valid_dates:
            assert english_engine._validate_date(date_str)
        
        # Test invalid dates
        invalid_dates = ["", "not-a-date", "2023-13-45", "31/13/2023"]
        
        for date_str in invalid_dates:
            assert not english_engine._validate_date(date_str)
    
    @pytest.mark.asyncio
    async def test_performance_benchmark(self, english_engine):
        """Benchmark OCR performance"""
        import time
        
        # Create test image
        test_image = self.create_test_image("Performance Test Text", 'eng')
        
        # Time the extraction
        start_time = time.time()
        result = await english_engine.extract(test_image)
        end_time = time.time()
        
        processing_time = end_time - start_time
        
        # Should complete within reasonable time
        assert processing_time < 10.0  # 10 seconds max
        
        # Result should include processing time
        if 'processing_time' in result:
            assert abs(result['processing_time'] - processing_time) < 1.0

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])