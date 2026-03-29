import json
from pathlib import Path
from typing import Dict, List, Any
from enum import Enum
import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# Document Categories (EXTENDED – PRODUCTION REALITY)
# ---------------------------------------------------------------------
class CertificateLayout(Enum):
    UNIVERSITY = "university"
    TRAINING = "training"
    PROFESSIONAL = "professional"
    AWARD = "award"

    SUPPORT_LETTER = "support_letter"
    SKILL_VERIFICATION = "skill_verification"


# ---------------------------------------------------------------------
# Template Manager
# ---------------------------------------------------------------------
class CertificateTemplates:
    """
    Manage certificate AND verification-document templates
    (Certificates, support letters, skill letters).
    Designed for Donut training + admin approval workflows.
    """

    def __init__(self, templates_dir: str = "app/data/templates"):
        self.templates_dir = Path(templates_dir)
        self.templates_dir.mkdir(parents=True, exist_ok=True)

        self._init_default_templates()
        logger.info("CertificateTemplates initialized (production, multilingual)")

    # -----------------------------------------------------------------
    # Default Templates
    # -----------------------------------------------------------------
    def _init_default_templates(self):
        default_templates = {

            # =============================================================
            # UNIVERSITY – EN
            # =============================================================
            "university_en": {
                "name": "University Certificate",
                "document_type": CertificateLayout.UNIVERSITY.value,
                "intent": "academic_verification",
                "fields": [
                    {"name": "header", "type": "text", "position": [0.5, 0.1], "size": 0.08, "align": "center"},
                    {"name": "name_label", "type": "label", "position": [0.15, 0.25], "text": "Name:", "size": 0.04},
                    {"name": "name_value", "type": "field", "position": [0.35, 0.25], "field": "name", "size": 0.045},
                    {"name": "id_label", "type": "label", "position": [0.15, 0.32], "text": "Student ID:", "size": 0.04},
                    {"name": "id_value", "type": "field", "position": [0.35, 0.32], "field": "student_id", "size": 0.04},
                    {"name": "university_label", "type": "label", "position": [0.15, 0.39], "text": "University:", "size": 0.04},
                    {"name": "university_value", "type": "field", "position": [0.35, 0.39], "field": "university", "size": 0.04},
                    {"name": "course_label", "type": "label", "position": [0.15, 0.46], "text": "Course:", "size": 0.04},
                    {"name": "course_value", "type": "field", "position": [0.35, 0.46], "field": "course", "size": 0.04},
                    {"name": "gpa_label", "type": "label", "position": [0.15, 0.53], "text": "GPA:", "size": 0.04},
                    {"name": "gpa_value", "type": "field", "position": [0.35, 0.53], "field": "gpa", "size": 0.04},
                    {"name": "date_label", "type": "label", "position": [0.15, 0.60], "text": "Issue Date:", "size": 0.04},
                    {"name": "date_value", "type": "field", "position": [0.35, 0.60], "field": "issue_date", "size": 0.04},
                    {"name": "seal", "type": "seal", "position": [0.8, 0.15], "size": 0.15},
                    {"name": "signature", "type": "signature", "position": [0.7, 0.8], "size": 0.2},
                    {"name": "footer", "type": "text", "position": [0.5, 0.95],
                     "text": "This certificate is computer generated.",
                     "size": 0.03, "align": "center"}
                ]
            },

            # =============================================================
            # UNIVERSITY – AM
            # =============================================================
            "university_am": {
                "name": "የዩኒቨርሲቲ ማረጋገጫ",
                "document_type": CertificateLayout.UNIVERSITY.value,
                "intent": "academic_verification",
                "fields": [
                    {"name": "header", "type": "text", "position": [0.5, 0.1], "size": 0.08, "align": "center"},
                    {"name": "name_label", "type": "label", "position": [0.15, 0.25], "text": "ስም:", "size": 0.04},
                    {"name": "name_value", "type": "field", "position": [0.35, 0.25], "field": "name", "size": 0.045},
                    {"name": "id_label", "type": "label", "position": [0.15, 0.32], "text": "የተማሪ መታወቂያ:", "size": 0.04},
                    {"name": "id_value", "type": "field", "position": [0.35, 0.32], "field": "student_id", "size": 0.04},
                    {"name": "university_label", "type": "label", "position": [0.15, 0.39], "text": "ዩኒቨርሲቲ:", "size": 0.04},
                    {"name": "university_value", "type": "field", "position": [0.35, 0.39], "field": "university", "size": 0.04},
                    {"name": "course_label", "type": "label", "position": [0.15, 0.46], "text": "ኮርስ:", "size": 0.04},
                    {"name": "course_value", "type": "field", "position": [0.35, 0.46], "field": "course", "size": 0.04},
                    {"name": "gpa_label", "type": "label", "position": [0.15, 0.53], "text": "አማካይ ነጥብ:", "size": 0.04},
                    {"name": "gpa_value", "type": "field", "position": [0.35, 0.53], "field": "gpa", "size": 0.04},
                    {"name": "date_label", "type": "label", "position": [0.15, 0.60], "text": "የተሰጠበት ቀን:", "size": 0.04},
                    {"name": "date_value", "type": "field", "position": [0.35, 0.60], "field": "issue_date", "size": 0.04},
                    {"name": "seal", "type": "seal", "position": [0.8, 0.15], "size": 0.15},
                    {"name": "signature", "type": "signature", "position": [0.7, 0.8], "size": 0.2},
                    {"name": "footer", "type": "text", "position": [0.5, 0.95],
                     "text": "ይህ ማረጋገጫ በኮምፒውተር የታደሰ ነው።",
                     "size": 0.03, "align": "center"}
                ]
            },

            # =============================================================
            # SUPPORT LETTER – EN
            # =============================================================
            "support_letter_en": {
                "name": "Official Support Letter",
                "document_type": CertificateLayout.SUPPORT_LETTER.value,
                "intent": "identity_or_skill_support",
                "fields": [
                    {"name": "header", "type": "text", "position": [0.5, 0.08], "size": 0.075, "align": "center"},
                    {"name": "ref_label", "type": "label", "position": [0.1, 0.18], "text": "Reference No:", "size": 0.035},
                    {"name": "ref_value", "type": "field", "position": [0.3, 0.18], "field": "reference_number", "size": 0.035},
                    {"name": "body", "type": "paragraph", "position": [0.1, 0.30], "field": "body", "size": 0.038},
                    {"name": "office_label", "type": "label", "position": [0.1, 0.72], "text": "Issuing Office:", "size": 0.035},
                    {"name": "office_value", "type": "field", "position": [0.35, 0.72], "field": "organization", "size": 0.035},
                    {"name": "signature", "type": "signature", "position": [0.65, 0.78], "size": 0.2},
                    {"name": "seal", "type": "seal", "position": [0.8, 0.75], "size": 0.15}
                ]
            },

            # =============================================================
            # SUPPORT LETTER – AM
            # =============================================================
            "support_letter_am": {
                "name": "የድጋፍ ደብዳቤ",
                "document_type": CertificateLayout.SUPPORT_LETTER.value,
                "intent": "identity_or_skill_support",
                "fields": [
                    {"name": "header", "type": "text", "position": [0.5, 0.08], "size": 0.075, "align": "center"},
                    {"name": "ref_label", "type": "label", "position": [0.1, 0.18], "text": "መለያ ቁጥር:", "size": 0.035},
                    {"name": "ref_value", "type": "field", "position": [0.3, 0.18], "field": "reference_number", "size": 0.035},
                    {"name": "body", "type": "paragraph", "position": [0.1, 0.30], "field": "body", "size": 0.038},
                    {"name": "office_label", "type": "label", "position": [0.1, 0.72], "text": "የሰጠው ቢሮ:", "size": 0.035},
                    {"name": "office_value", "type": "field", "position": [0.35, 0.72], "field": "organization", "size": 0.035},
                    {"name": "signature", "type": "signature", "position": [0.65, 0.78], "size": 0.2},
                    {"name": "seal", "type": "seal", "position": [0.8, 0.75], "size": 0.15}
                ]
            }
        }

        # Save templates safely (UTF-8)
        for name, data in default_templates.items():
            path = self.templates_dir / f"{name}.json"
            if not path.exists():
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                logger.info(f"Created template: {name}")

    # -----------------------------------------------------------------
    # Access & Utilities
    # -----------------------------------------------------------------
    def get_template(self, template_name: str) -> Dict[str, Any]:
        path = self.templates_dir / f"{template_name}.json"
        if not path.exists():
            raise FileNotFoundError(f"No template found: {template_name}")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_template_for_certificate(self, cert_type: str, language: str) -> Dict[str, Any]:
        template_name = f"{cert_type}_{language[:2]}"
        return self.get_template(template_name)

    def list_templates(self) -> List[str]:
        return sorted(p.stem for p in self.templates_dir.glob("*.json"))

    def validate_template(self, template_data: Dict[str, Any]) -> List[str]:
        errors = []
        for key in ["name", "fields", "document_type"]:
            if key not in template_data:
                errors.append(f"Missing required key: {key}")

        for i, field in enumerate(template_data.get("fields", [])):
            if "type" not in field:
                errors.append(f"Field {i} missing type")
            if "position" in field:
                pos = field["position"]
                if not isinstance(pos, list) or len(pos) != 2:
                    errors.append(f"Field {i} invalid position format")
                elif not (0 <= pos[0] <= 1 and 0 <= pos[1] <= 1):
                    errors.append(f"Field {i} position out of bounds")
        return errors
