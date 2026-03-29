import os
from typing import Optional, Dict, Any
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings
class Settings(BaseSettings):
    """Application settings"""
    
    # Application
    app_name: str = "AI Certificate Analyzer"
    app_version: str = "2024.2.0"
    debug: bool = True
    log_level: str = "INFO"
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4
    reload: bool = False
    
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_ttl: int = 3600
    
    # OCR
    ocr_languages: str = "eng+amh"
    tessdata_path: Optional[str] = None
    use_paddleocr: bool = False
    
    # ML Models
    use_ml: bool = True
    ml_confidence_threshold: float = 0.6
    donut_model_path: Optional[str] = None
    
    # Analysis
    reject_threshold: float = 0.65
    low_quality_threshold: float = 0.7
    tampering_threshold: float = 0.75
    
    # Security
    api_key_header: str = "X-API-Key"
    allowed_origins: str = "*"
    
    # Storage
    upload_dir: str = "uploads"
    training_data_dir: str = "data/training"
    models_dir: str = "models"
    
    # Performance
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    max_workers: int = 4
    batch_size: int = 25
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
    
    @property
    def allowed_origins_list(self) -> list:
        """Get allowed origins as list"""
        if self.allowed_origins == "*":
            return ["*"]
        return [origin.strip() for origin in self.allowed_origins.split(",")]
    
    @property
    def ocr_languages_list(self) -> list:
        """Get OCR languages as list"""
        return [lang.strip() for lang in self.ocr_languages.split("+")]
    
    def get_model_path(self, model_name: str) -> str:
        """Get full path for model"""
        if self.models_dir:
            model_path = Path(self.models_dir) / model_name
            if model_path.exists():
                return str(model_path)
        return model_name

# Global settings instance
settings = Settings()

def get_settings() -> Settings:
    """Get settings instance"""
    return settings

def update_settings(**kwargs):
    """Update settings dynamically"""
    for key, value in kwargs.items():
        if hasattr(settings, key):
            setattr(settings, key, value)