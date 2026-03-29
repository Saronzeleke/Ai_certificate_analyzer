"""
API module for AI Certificate Analyzer
"""

from .routes import router
from .schemas import AnalysisRequest, AnalysisResponse, HealthResponse

__all__ = [
    'router',
    'AnalysisRequest',
    'AnalysisResponse',
    'HealthResponse'
]