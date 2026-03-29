from enum import Enum
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from dateutil import parser as date_parser
from dateutil.tz import tzutc
from pydantic import BaseModel, Field, validator
import logging, os, json
from functools import lru_cache
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor


# ---------------------------
# Logging
# ---------------------------
class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "module": record.module,
            "message": record.getMessage()
        }
        if hasattr(record, 'audit_data'):
            log_record['audit'] = record.audit_data
        return json.dumps(log_record)


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

console_handler = logging.StreamHandler()
console_handler.setFormatter(JsonFormatter())
logger.addHandler(console_handler)

audit_handler = logging.FileHandler('audit.log')
audit_handler.setFormatter(JsonFormatter())
logger.addHandler(audit_handler)


# ---------------------------
# Enums
# ---------------------------
class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Recommendation(str, Enum):
    APPROVE = "approve"
    REVIEW = "review"
    REJECT = "reject"


class DocumentType(str, Enum):
    CERTIFICATE = "certificate"
    DIPLOMA = "diploma"
    DEGREE = "degree"
    TRANSCRIPT = "transcript"
    UNKNOWN = "unknown"


# ---------------------------
# Models
# ---------------------------
class ValidationResult(BaseModel):
    passed: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    present_fields_count: int = 0
    field_quality: Dict[str, float] = Field(default_factory=dict)
    penalty_breakdown: Dict[str, float] = Field(default_factory=dict)


class RecommendationResult(BaseModel):
    recommendation: Recommendation
    risk_level: RiskLevel
    combined_confidence: float
    raw_confidence: float
    ocr_confidence: Optional[float] = None
    ml_confidence: Optional[float] = None
    authenticity_score: float
    reasons: List[str] = Field(default_factory=list)
    validation: ValidationResult
    review_required: bool
    document_type: DocumentType = DocumentType.UNKNOWN
    timestamp: datetime = Field(default_factory=lambda: datetime.now(tzutc()))

    @validator('combined_confidence')
    def validate_confidence(cls, v):
        if not 0 <= v <= 1:
            raise ValueError(f'Confidence must be 0-1, got {v}')
        return v

    class Config:
        use_enum_values = True


# ---------------------------
# Config
# ---------------------------
class RecommendationConfig:
    def __init__(self, config_path: Optional[str] = None):
        if config_path and Path(config_path).exists():
            self._load_from_file(config_path)
        else:
            self._load_from_env()

    def _load_from_env(self):
        self.auto_approve_threshold = float(os.getenv("AUTO_APPROVE_THRESHOLD", "0.90"))
        self.auto_reject_threshold = float(os.getenv("AUTO_REJECT_THRESHOLD", "0.60"))
        self.min_required_fields = int(os.getenv("MIN_REQUIRED_FIELDS", "3"))
        self.min_confidence = float(os.getenv("MIN_CONFIDENCE", "0.3"))
        self.max_penalty = float(os.getenv("MAX_PENALTY", "0.7"))

        self.field_aliases = {
            "certificate_id": os.getenv("CERT_ID_ALIASES", "certificate_id,certificate_number,id,document_id,cert_id").split(","),
            "name": os.getenv("NAME_ALIASES", "name,full_name,student_name,candidate_name,holder_name").split(","),
            "issue_date": os.getenv("ISSUE_DATE_ALIASES", "issue_date,issued_on,date_issued,date").split(","),
            "expiry_date": os.getenv("EXPIRY_DATE_ALIASES", "expiry_date,expiration_date,valid_until,expires_on").split(","),
            "organization": os.getenv("ORG_ALIASES", "organization,issuer,institution,university,authority").split(",")
        }

        self.validity_period = {
            "min_normal": int(os.getenv("VALIDITY_MIN_DAYS", "365")),
            "max_normal": int(os.getenv("VALIDITY_MAX_DAYS", "3650"))
        }

        self.risk_thresholds = {"critical": 0.4, "high": 0.6, "medium": 0.8, "low": 1.0}

        self.confidence_weights = {
            DocumentType.CERTIFICATE: {"ocr": 0.4, "ml": 0.6},
            DocumentType.DIPLOMA: {"ocr": 0.5, "ml": 0.5},
            DocumentType.DEGREE: {"ocr": 0.3, "ml": 0.7},
            DocumentType.TRANSCRIPT: {"ocr": 0.7, "ml": 0.3},
            DocumentType.UNKNOWN: {"ocr": 0.5, "ml": 0.5}
        }

    def _load_from_file(self, path: str):
        with open(path) as f:
            config_data = json.load(f)
        for key, value in config_data.items():
            os.environ[key] = str(value)
        self._load_from_env()

    def get_weights_for_document_type(self, doc_type: DocumentType) -> Dict[str, float]:
        return self.confidence_weights.get(doc_type, self.confidence_weights[DocumentType.UNKNOWN])


# ---------------------------
# Field Validator
# ---------------------------
class FieldValidator:
    def __init__(self, config: RecommendationConfig):
        self.config = config

    @staticmethod
    @lru_cache(maxsize=256)
    def parse_date(date_str: str) -> Optional[datetime]:
        if not date_str:
            return None
        try:
            dt = date_parser.parse(str(date_str))
            if not dt.tzinfo:
                dt = dt.replace(tzinfo=tzutc())
            return dt
        except Exception:
            return None

    def validate_name(self, name: Any) -> Tuple[bool, float, List[str]]:
        warnings = []
        if not name:
            return False, 0.0, ["Name is empty"]
        s = str(name).strip()
        if len(s) < 2:
            return False, 0.2, ["Name too short"]
        alpha_ratio = sum(c.isalpha() for c in s) / len(s)
        quality = min(1.0, alpha_ratio)
        if s.isupper():
            warnings.append("All uppercase")
        if any(c.isdigit() for c in s):
            warnings.append("Contains digits")
        return True, quality, warnings

    def validate_certificate_id(self, cid: Any) -> Tuple[bool, float, List[str]]:
        warnings = []
        if not cid:
            return False, 0.0, ["Certificate ID empty"]
        s = str(cid).strip()
        if len(s) < 4:
            return False, 0.3, ["Too short"]
        if len(s) > 64:
            return False, 0.2, ["Too long"]
        quality = sum(c.isalnum() for c in s) / len(s)
        return True, quality, warnings

    def validate_dates(self, issue_date: Any, expiry_date: Any) -> Tuple[float, List[str], bool]:
        warnings = []
        quality = 1.0
        expired = False
        i_dt = self.parse_date(issue_date)
        e_dt = self.parse_date(expiry_date)
        now = datetime.now(tzutc())

        if i_dt and i_dt > now:
            warnings.append("Issue date in future")
            quality -= 0.1
        if e_dt and e_dt < now:
            warnings.append("Expired")
            quality -= 0.1
            expired = True
        if i_dt and e_dt and e_dt <= i_dt:
            warnings.append("Expiry before issue")
            quality -= 0.2

        return max(0.0, quality), warnings, expired

    def extract_field(self, fields: Dict[str, Any], key: str) -> Any:
        for alias in self.config.field_aliases.get(key, [key]):
            if alias in fields and fields[alias] not in (None, ''):
                return fields[alias]
        return None

    def detect_document_type(self, fields: Dict[str, Any]) -> DocumentType:
        s = str(fields).lower()
        for dt in DocumentType:
            if dt.value in s:
                return dt
        return DocumentType.UNKNOWN


# ---------------------------
# Recommendation Engine
# ---------------------------
class RecommendationEngine:
    def __init__(self, config: Optional[RecommendationConfig] = None):
        self.config = config or RecommendationConfig()
        self.validator = FieldValidator(self.config)

    def combine_confidence(self, ocr: Optional[float], ml: Optional[float], doc_type: DocumentType) -> float:
        ocr, ml = ocr or 0.5, ml or 0.5
        w = self.config.get_weights_for_document_type(doc_type)
        return min(max(ocr * w['ocr'] + ml * w['ml'], 0.0), 1.0)

    def apply_penalties(self, base: float, validation: ValidationResult) -> Tuple[float, Dict[str, float]]:
        final = base
        breakdown = {'base': base}
        error_penalty = 0.1 * len(validation.errors)
        warning_penalty = 0.05 * len(validation.warnings)
        final = max(final - error_penalty - warning_penalty, self.config.min_confidence)
        breakdown['errors'] = -error_penalty
        breakdown['warnings'] = -warning_penalty
        return round(final, 4), breakdown

    def determine_risk(self, conf: float, errors: List[str], expired: bool, tampering: bool) -> RiskLevel:
        if tampering:
            return RiskLevel.CRITICAL
        if expired or conf < self.config.risk_thresholds['critical']:
            return RiskLevel.HIGH
        if errors:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    def validate_fields(self, fields: Dict[str, Any]) -> ValidationResult:
        errors, warnings, fq = [], [], {}
        cert_id = self.validator.extract_field(fields, 'certificate_id')
        name = self.validator.extract_field(fields, 'name')
        issue_date = self.validator.extract_field(fields, 'issue_date')
        expiry_date = self.validator.extract_field(fields, 'expiry_date')

        present = [cert_id, name, issue_date]
        fq['completeness'] = sum(1 for f in present if f) / len(present)

        if cert_id:
            _, quality, w = self.validator.validate_certificate_id(cert_id)
            fq['certificate_id'] = quality
            warnings.extend(w)
            errors.extend([e for e in w if quality < 0.5])

        if name:
            _, quality, w = self.validator.validate_name(name)
            fq['name'] = quality
            warnings.extend(w)
            errors.extend([e for e in w if quality < 0.5])

        date_quality, date_w, _ = self.validator.validate_dates(issue_date, expiry_date)
        fq['dates'] = date_quality
        warnings.extend(date_w)

        return ValidationResult(
            passed=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            present_fields_count=sum(1 for f in present if f),
            field_quality=fq
        )

    def generate_recommendation(self, authenticity_score: float, extracted_fields: Dict[str, Any],
                                tampering_detected: bool = False,
                                ocr_confidence: Optional[float] = None,
                                ml_confidence: Optional[float] = None) -> RecommendationResult:

        doc_type = self.validator.detect_document_type(extracted_fields)
        validation = self.validate_fields(extracted_fields)
        raw_conf = self.combine_confidence(ocr_confidence, ml_confidence, doc_type)
        final_conf, penalties = self.apply_penalties(raw_conf, validation)

        final_conf = (final_conf + authenticity_score) / 2
        validation.penalty_breakdown = penalties   # <-- now actually used

        expired = any("expired" in w.lower() for w in validation.warnings)

        if tampering_detected:
            return RecommendationResult(
                recommendation=Recommendation.REJECT,
                risk_level=RiskLevel.CRITICAL,
                combined_confidence=final_conf,
                raw_confidence=raw_conf,
                ocr_confidence=ocr_confidence,
                ml_confidence=ml_confidence,
                authenticity_score=authenticity_score,
                reasons=["DOCUMENT TAMPERING DETECTED"],
                validation=validation,
                review_required=False,
                document_type=doc_type
            )

        if final_conf >= self.config.auto_approve_threshold:
            recommendation = Recommendation.APPROVE if not expired else Recommendation.REVIEW
            review_required = expired
            reasons = [f"High confidence ({final_conf:.2f})"]
        elif final_conf <= self.config.auto_reject_threshold:
            recommendation = Recommendation.REJECT
            review_required = False
            reasons = [f"Low confidence ({final_conf:.2f})"]
        else:
            recommendation = Recommendation.REVIEW
            review_required = True
            reasons = [f"Confidence ({final_conf:.2f}) in review range"]

        risk = self.determine_risk(final_conf, validation.errors, expired, tampering_detected)

        audit_data = {
            'doc_type': doc_type.value,
            'raw_conf': raw_conf,
            'final_conf': final_conf,
            'recommendation': recommendation.value,
            'risk_level': risk.value,
            'errors': validation.errors,
            'warnings': validation.warnings
        }
        logger.info("Recommendation generated", extra={'audit_data': audit_data})

        return RecommendationResult(
            recommendation=recommendation,
            risk_level=risk,
            combined_confidence=final_conf,
            raw_confidence=raw_conf,
            ocr_confidence=ocr_confidence,
            ml_confidence=ml_confidence,
            authenticity_score=authenticity_score,
            reasons=reasons,
            validation=validation,
            review_required=review_required,
            document_type=doc_type
        )

    def batch_generate(self, documents: List[Dict[str, Any]]) -> List[RecommendationResult]:
        results = []
        with ThreadPoolExecutor() as executor:
            futures = [executor.submit(self.generate_recommendation, **doc) for doc in documents]
            for f in futures:
                try:
                    results.append(f.result())
                except Exception as e:
                    logger.error(f"Batch processing error: {str(e)}")
        return results


# ---------------------------
# Factory
# ---------------------------
def create_recommendation_engine(config_path: Optional[str] = None, **kwargs) -> RecommendationEngine:
    config = RecommendationConfig(config_path)
    for k, v in kwargs.items():
        if hasattr(config, k):
            setattr(config, k, v)
    return RecommendationEngine(config)