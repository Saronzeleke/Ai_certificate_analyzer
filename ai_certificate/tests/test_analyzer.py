import pytest
import asyncio
import tempfile
from pathlib import Path
import json
import numpy as np
from unittest.mock import Mock, patch, AsyncMock
import sys

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from app.analyzers.certificate_analyzer import ProductionCertificateAnalyzer
from app.utils.image_processing import ImageProcessor

@pytest.fixture
def analyzer():
    """Fixture for certificate analyzer"""
    return ProductionCertificateAnalyzer(use_ml=True)

@pytest.fixture
def test_certificate_en():
    """Create a test English certificate image"""
    # Create a simple white image with black text
    img = np.ones((500, 700, 3), dtype=np.uint8) * 255
    
    # Add certificate-like content
    import cv2
    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(img, "CERTIFICATE OF ACHIEVEMENT", (100, 100), font, 1, (0, 0, 0), 2)
    cv2.putText(img, "Name: John Doe", (100, 200), font, 0.7, (0, 0, 0), 2)
    cv2.putText(img, "Student ID: STU12345", (100, 250), font, 0.7, (0, 0, 0), 2)
    cv2.putText(img, "University: Test University", (100, 300), font, 0.7, (0, 0, 0), 2)
    
    return img

@pytest.fixture
def test_certificate_am():
    """Create a test Amharic certificate image"""
    img = np.ones((500, 700, 3), dtype=np.uint8) * 255
    
    # Note: Actual Amharic text would require Ethiopic font
    # Using placeholder text for testing
    import cv2
    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(img, "የማረጋገጫ ወረቀት", (100, 100), font, 1, (0, 0, 0), 2)
    cv.putText(img, "Test Amharic Certificate", (100, 200), font, 0.7, (0, 0, 0), 2)
    
    return img

class TestCertificateAnalyzer:
    """Production tests for certificate analyzer"""
    
    def test_initialization(self, analyzer):
        """Test analyzer initialization"""
        assert analyzer is not None
        assert hasattr(analyzer, 'model_version')
        assert hasattr(analyzer, 'ocr_router')
        assert hasattr(analyzer, 'tamper_detector')
    
    @pytest.mark.asyncio
    async def test_health_check(self, analyzer):
        """Test health check endpoint"""
        health = await analyzer.health_check()
        
        assert 'status' in health
        assert 'components' in health
        assert 'timestamp' in health
        
        # Check required components
        components = health['components']
        assert 'ocr_engine' in components
        assert 'tamper_detector' in components
        assert 'redis' in components
        
        assert health['status'] in ['healthy', 'degraded']
    
    @pytest.mark.asyncio
    async def test_analyze_english_certificate(self, analyzer, test_certificate_en):
        """Test English certificate analysis"""
        # Mock file upload
        mock_file = Mock()
        mock_file.filename = "test_certificate_en.png"
        mock_file.read = AsyncMock(return_value=b"fake_image_data")
        
        with patch('cv2.imdecode', return_value=test_certificate_en):
            result = await analyzer.analyze_certificate_file(
                mock_file, 
                provider_id="test_provider",
                request_id="test_request"
            )
        
        assert 'analysis_id' in result
        assert 'extracted_data' in result
        assert 'authenticity_score' in result
        assert 'status' in result
        assert 'processing_time' in result
        
        # Verify structure
        assert 0 <= result['authenticity_score'] <= 1
        assert result['status'] in ['Approved', 'Rejected', 'Pending Admin Review']
        
        # Should have some extracted data even if mocked
        assert isinstance(result['extracted_data'], dict)
    
    @pytest.mark.asyncio
    async def test_analyze_amharic_certificate(self, analyzer, test_certificate_am):
        """Test Amharic certificate analysis"""
        mock_file = Mock()
        mock_file.filename = "test_certificate_am.png"
        mock_file.read = AsyncMock(return_value=b"fake_image_data")
        
        with patch('cv2.imdecode', return_value=test_certificate_am):
            result = await analyzer.analyze_certificate_file(
                mock_file,
                provider_id="test_provider",
                request_id="test_request_am"
            )
        
        assert 'analysis_id' in result
        assert 'language_detected' in result or 'script_detected' in result
        
        # Verify multilingual support
        assert result.get('model_version', '').find('multilingual') != -1
    
    @pytest.mark.asyncio
    async def test_batch_analysis(self, analyzer):
        """Test batch certificate analysis"""
        # Create multiple mock files
        mock_files = []
        for i in range(3):
            mock_file = Mock()
            mock_file.filename = f"certificate_{i}.png"
            mock_file.read = AsyncMock(return_value=b"fake_data")
            mock_files.append(mock_file)
        
        # This would test the batch processing capability
        # Note: Actual implementation might need adjustment
        results = []
        for mock_file in mock_files:
            with patch('cv2.imdecode', return_value=np.ones((100, 100, 3))):
                result = await analyzer.analyze_certificate_file(
                    mock_file,
                    provider_id="batch_test",
                    request_id=f"batch_{mock_file.filename}"
                )
                results.append(result)
        
        assert len(results) == 3
        for result in results:
            assert 'analysis_id' in result
            assert 'processing_time' in result
    
    def test_error_handling(self, analyzer):
        """Test error handling with invalid input"""
        # Test with None
        with pytest.raises(Exception):
            analyzer.analyze_certificate_file(None, "test", "test")
        
        # Test with invalid file type
        mock_file = Mock()
        mock_file.filename = "test.txt"  # Not an image
        mock_file.read = AsyncMock(return_value=b"not_an_image")
        
        # Should handle gracefully or raise appropriate error
        # Implementation specific
    
    @pytest.mark.asyncio
    async def test_cache_behavior(self, analyzer):
        """Test caching behavior"""
        from unittest.mock import patch
        
        mock_file = Mock()
        mock_file.filename = "cached_test.png"
        mock_file.read = AsyncMock(return_value=b"cached_image")
        
        # First analysis (should miss cache)
        with patch('cv2.imdecode') as mock_decode:
            mock_decode.return_value = np.ones((100, 100, 3))
            result1 = await analyzer.analyze_certificate_file(
                mock_file, "cache_test", "request_1"
            )
        
        # Reset mock and analyze again (might hit cache depending on implementation)
        mock_file.read = AsyncMock(return_value=b"cached_image")
        
        with patch('cv2.imdecode') as mock_decode:
            mock_decode.return_value = np.ones((100, 100, 3))
            result2 = await analyzer.analyze_certificate_file(
                mock_file, "cache_test", "request_2"
            )
        
        # Both should have valid results
        assert result1['analysis_id'] != result2['analysis_id']
    
    def test_configuration(self, analyzer):
        """Test configuration loading"""
        from app.utils.config import settings
        
        # Verify configuration is loaded
        assert hasattr(settings, 'app_name')
        assert hasattr(settings, 'reject_threshold')
        assert hasattr(settings, 'low_quality_threshold')
        
        # Verify thresholds are valid
        assert 0 <= settings.reject_threshold <= 1
        assert 0 <= settings.low_quality_threshold <= 1
        
        # Verify OCR languages include both English and Amharic
        assert 'eng' in settings.ocr_languages_list
        # Amharic might be 'amh' or 'am'
        assert any('am' in lang.lower() for lang in settings.ocr_languages_list)
    
    @pytest.mark.asyncio
    async def test_performance_metrics(self, analyzer, test_certificate_en):
        """Test performance metrics collection"""
        mock_file = Mock()
        mock_file.filename = "perf_test.png"
        mock_file.read = AsyncMock(return_value=b"perf_data")
        
        with patch('cv2.imdecode', return_value=test_certificate_en):
            result = await analyzer.analyze_certificate_file(
                mock_file, "perf_test", "perf_request"
            )
        
        # Check performance metrics
        assert 'processing_time' in result
        assert isinstance(result['processing_time'], float)
        assert result['processing_time'] > 0
        
        # Check quality metrics if available
        if 'quality_metrics' in result:
            metrics = result['quality_metrics']
            assert 'ocr_confidence' in metrics
            assert 0 <= metrics['ocr_confidence'] <= 1
    
    @pytest.mark.asyncio
    async def test_concurrent_requests(self, analyzer):
        """Test handling concurrent requests"""
        import asyncio
        
        async def analyze_one(i):
            mock_file = Mock()
            mock_file.filename = f"concurrent_{i}.png"
            mock_file.read = AsyncMock(return_value=b"concurrent_data")
            
            with patch('cv2.imdecode', return_value=np.ones((100, 100, 3))):
                return await analyzer.analyze_certificate_file(
                    mock_file, f"concurrent_{i}", f"req_{i}"
                )
        
        # Run multiple analyses concurrently
        tasks = [analyze_one(i) for i in range(5)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # All should complete successfully
        assert len(results) == 5
        for result in results:
            assert not isinstance(result, Exception)
            assert 'analysis_id' in result

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])