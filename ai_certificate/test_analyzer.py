import pytest
from app.analyzers.certificate_analyzer import ProductionCertificateAnalyzer
from app.analyzers.certificate_analyzer import clean_extracted_text
def test_health_check():
    analyzer = ProductionCertificateAnalyzer()
    result = analyzer.health_check()
    assert result["status"] == "healthy"

def test_score_calculation():
    analyzer = ProductionCertificateAnalyzer()
    test_data = {"ocr_confidence": 0.8, "tampering_confidence": 0.1}
    score = analyzer._calculate_hybrid_score(test_data)
    assert 0 <= score <= 1

def test_clean_text():
    text = "| OF COMPLETIO}"
    cleaned = clean_extracted_text(text)
    assert "CERTIFICATE" in cleaned