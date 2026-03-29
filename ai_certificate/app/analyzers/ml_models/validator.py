import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import re

logger = logging.getLogger(__name__)

class CertificateValidator:
    """Validate certificate data and detect anomalies"""
    
    def __init__(self):
        self.model_version = "2024.1.0-validator"
        
        # Validation rules
        self.validation_rules = {
            'name': {
                'required': True,
                'min_length': 4,
                'max_length': 50,
                'pattern': r'^[A-Za-z\u1200-\u137F\s\.\-]+$',
                'blacklist': ['test', 'example', 'sample', 'dummy']
            },
            'student_id': {
                'required': True,
                'min_length': 5,
                'max_length': 20,
                'pattern': r'^[A-Z0-9\-\/]+$'
            },
            'university': {
                'required': True,
                'min_length': 3,
                'max_length': 100,
                'blacklist': ['fake university', 'test school']
            },
            'course': {
                'required': True,
                'min_length': 3,
                'max_length': 100
            },
            'gpa': {
                'required': False,
                'min_value': 0.0,
                'max_value': 4.0,
                'pattern': r'^[0-4]\.\d{1,2}$'
            },
            'issue_date': {
                'required': True,
                'pattern': r'^\d{4}-\d{2}-\d{2}$|^\d{1,2}/\d{1,2}/\d{4}$|^\d{1,2}-\d{1,2}-\d{4}$'
            },
            'expiry_date': {
                'required': False,
                'pattern': r'^\d{4}-\d{2}-\d{2}$|^\d{1,2}/\d{1,2}/\d{4}$|^\d{1,2}-\d{1,2}-\d{4}$'
            }
        }
        
        # Anomaly detection patterns
        self.anomaly_patterns = {
            'suspicious_dates': [
                r'0000-00-00',
                r'1900-01-01',
                r'1970-01-01'
            ],
            'test_patterns': [
                'test', 'example', 'sample', 'dummy', 'fake',
                'ሙከራ', 'ናሙና', 'ምሳሌ'
            ],
            'sequential_patterns': [
                r'123456',
                r'abcdef',
                r'111111',
                r'000000'
            ]
        }
        
        logger.info(f"CertificateValidator v{self.model_version} initialized")
    
    def validate(self, certificate_data: Dict[str, str], 
                certificate_type: str = "university") -> Dict[str, Any]:
        """Validate certificate data"""
        try:
            start_time = datetime.now()
            
            # Perform validations
            field_validations = self._validate_fields(certificate_data)
            anomaly_checks = self._check_anomalies(certificate_data)
            consistency_checks = self._check_consistency(certificate_data)
            
            # Calculate overall score
            validation_score = self._calculate_validation_score(
                field_validations, anomaly_checks, consistency_checks
            )
            
            # Determine status
            is_valid = validation_score >= 0.7
            status = "VALID" if is_valid else "INVALID"
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            return {
                'is_valid': is_valid,
                'validation_score': validation_score,
                'status': status,
                'field_validations': field_validations,
                'anomaly_checks': anomaly_checks,
                'consistency_checks': consistency_checks,
                'recommendations': self._generate_recommendations(
                    field_validations, anomaly_checks, consistency_checks
                ),
                'processing_time': processing_time,
                'model_version': self.model_version,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            return {
                'is_valid': False,
                'validation_score': 0.0,
                'status': 'VALIDATION_ERROR',
                'error': str(e),
                'model_version': self.model_version
            }
    
    def _validate_fields(self, data: Dict[str, str]) -> Dict[str, Dict[str, Any]]:
        """Validate individual fields"""
        validations = {}
        
        for field_name, rules in self.validation_rules.items():
            field_value = data.get(field_name, '').strip()
            
            validation_result = {
                'present': bool(field_value),
                'valid': True,
                'errors': [],
                'warnings': []
            }
            
            # Check if required
            if rules.get('required', False) and not field_value:
                validation_result['valid'] = False
                validation_result['errors'].append('Required field is missing')
            
            # Check length
            if field_value:
                if 'min_length' in rules and len(field_value) < rules['min_length']:
                    validation_result['valid'] = False
                    validation_result['errors'].append(f'Too short (min {rules["min_length"]} chars)')
                
                if 'max_length' in rules and len(field_value) > rules['max_length']:
                    validation_result['valid'] = False
                    validation_result['errors'].append(f'Too long (max {rules["max_length"]} chars)')
                
                # Check pattern
                if 'pattern' in rules:
                    if not re.match(rules['pattern'], field_value, re.IGNORECASE):
                        validation_result['valid'] = False
                        validation_result['errors'].append('Invalid format')
                
                # Check blacklist
                if 'blacklist' in rules:
                    field_lower = field_value.lower()
                    for banned in rules['blacklist']:
                        if banned in field_lower:
                            validation_result['valid'] = False
                            validation_result['errors'].append('Contains blacklisted term')
                            break
                
                # Check numeric range
                if 'min_value' in rules and 'max_value' in rules:
                    try:
                        num = float(field_value)
                        if num < rules['min_value'] or num > rules['max_value']:
                            validation_result['valid'] = False
                            validation_result['errors'].append('Value out of range')
                    except ValueError:
                        if rules.get('is_float', False):
                            validation_result['valid'] = False
                            validation_result['errors'].append('Invalid numeric value')
            
            validations[field_name] = validation_result
        
        return validations
    
    def _check_anomalies(self, data: Dict[str, str]) -> Dict[str, List[str]]:
        """Check for anomalies in certificate data"""
        anomalies = {
            'suspicious_patterns': [],
            'date_anomalies': [],
            'content_anomalies': []
        }
        
        # Check for suspicious patterns
        for field, value in data.items():
            if not value:
                continue
            
            value_lower = value.lower()
            
            # Test patterns
            for pattern in self.anomaly_patterns['test_patterns']:
                if pattern in value_lower:
                    anomalies['suspicious_patterns'].append(
                        f"Field '{field}' contains test pattern: '{pattern}'"
                    )
            
            # Sequential patterns
            for pattern in self.anomaly_patterns['sequential_patterns']:
                if pattern in value:
                    anomalies['suspicious_patterns'].append(
                        f"Field '{field}' contains sequential pattern: '{pattern}'"
                    )
        
        # Date anomalies
        if 'issue_date' in data and data['issue_date']:
            issue_date = data['issue_date']
            
            for pattern in self.anomaly_patterns['suspicious_dates']:
                if pattern in issue_date:
                    anomalies['date_anomalies'].append(
                        f"Issue date is suspicious: {issue_date}"
                    )
            
            # Check if issue date is in future
            try:
                date_obj = self._parse_date(issue_date)
                if date_obj and date_obj > datetime.now():
                    anomalies['date_anomalies'].append(
                        f"Issue date is in the future: {issue_date}"
                    )
            except:
                pass
        
        if 'expiry_date' in data and data['expiry_date']:
            expiry_date = data['expiry_date']
            
            # Check if expiry date is in past
            try:
                date_obj = self._parse_date(expiry_date)
                if date_obj and date_obj < datetime.now():
                    anomalies['date_anomalies'].append(
                        f"Certificate has expired: {expiry_date}"
                    )
            except:
                pass
        
        # Check date consistency
        if 'issue_date' in data and 'expiry_date' in data:
            if data['issue_date'] and data['expiry_date']:
                try:
                    issue = self._parse_date(data['issue_date'])
                    expiry = self._parse_date(data['expiry_date'])
                    
                    if issue and expiry and issue > expiry:
                        anomalies['date_anomalies'].append(
                            "Issue date is after expiry date"
                        )
                except:
                    pass
        
        return anomalies
    
    def _check_consistency(self, data: Dict[str, str]) -> Dict[str, List[str]]:
        """Check consistency between fields"""
        consistency_issues = []
        
        # Check name consistency (should not contain numbers)
        if 'name' in data and data['name']:
            name = data['name']
            if any(c.isdigit() for c in name):
                consistency_issues.append("Name contains numbers")
        
        # Check ID format consistency
        if 'student_id' in data and data['student_id']:
            student_id = data['student_id']
            # ID should not be just a name
            if any(word in student_id.lower() for word in ['mr', 'mrs', 'dr', 'prof']):
                consistency_issues.append("Student ID appears to contain title/name")
        
        # Check GPA consistency
        if 'gpa' in data and data['gpa']:
            try:
                gpa = float(data['gpa'])
                if gpa == 0.0 or gpa == 4.0:
                    consistency_issues.append("GPA is at extreme value (0.0 or 4.0)")
            except:
                consistency_issues.append("Invalid GPA format")
        
        return {'issues': consistency_issues}
    
    def _calculate_validation_score(self, field_validations: Dict,
                                  anomaly_checks: Dict,
                                  consistency_checks: Dict) -> float:
        """Calculate overall validation score"""
        total_weight = 0
        weighted_score = 0
        
        # Field validations weight: 60%
        field_weight = 0.6
        field_score = 0
        
        valid_fields = 0
        total_fields = len(field_validations)
        
        for field, validation in field_validations.items():
            if validation.get('valid', False):
                valid_fields += 1
        
        if total_fields > 0:
            field_score = valid_fields / total_fields
        
        weighted_score += field_score * field_weight
        total_weight += field_weight
        
        # Anomaly checks weight: 25%
        anomaly_weight = 0.25
        anomaly_score = 1.0
        
        total_anomalies = sum(len(issues) for issues in anomaly_checks.values())
        if total_anomalies > 0:
            # Each anomaly reduces score
            anomaly_score = max(0.0, 1.0 - (total_anomalies * 0.1))
        
        weighted_score += anomaly_score * anomaly_weight
        total_weight += anomaly_weight
        
        # Consistency checks weight: 15%
        consistency_weight = 0.15
        consistency_score = 1.0
        
        total_issues = len(consistency_checks.get('issues', []))
        if total_issues > 0:
            consistency_score = max(0.0, 1.0 - (total_issues * 0.2))
        
        weighted_score += consistency_score * consistency_weight
        total_weight += consistency_weight
        
        # Normalize score
        if total_weight > 0:
            final_score = weighted_score / total_weight
        else:
            final_score = 0.0
        
        return round(final_score, 3)
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date string to datetime object"""
        try:
            # Try different date formats
            date_formats = [
                '%Y-%m-%d',
                '%d/%m/%Y',
                '%m/%d/%Y',
                '%d-%m-%Y',
                '%Y/%m/%d'
            ]
            
            for fmt in date_formats:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
            
            return None
        except:
            return None
    
    def _generate_recommendations(self, field_validations: Dict,
                                anomaly_checks: Dict,
                                consistency_checks: Dict) -> List[str]:
        """Generate recommendations based on validation results"""
        recommendations = []
        
        # Field validation recommendations
        for field, validation in field_validations.items():
            if not validation.get('valid', False):
                errors = validation.get('errors', [])
                if errors:
                    recommendations.append(f"Fix {field}: {', '.join(errors)}")
        
        # Anomaly recommendations
        for category, issues in anomaly_checks.items():
            if issues:
                for issue in issues[:3]:  # Limit to top 3 issues per category
                    recommendations.append(f"Check: {issue}")
        
        # Consistency recommendations
        issues = consistency_checks.get('issues', [])
        for issue in issues[:3]:  # Limit to top 3 issues
            recommendations.append(f"Verify: {issue}")
        
        # Add general recommendations if none specific
        if not recommendations:
            recommendations.append("Certificate data appears valid")
        
        return recommendations
    
    def validate_batch(self, certificates: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """Validate multiple certificates"""
        results = []
        
        for cert_data in certificates:
            result = self.validate(cert_data)
            results.append(result)
        
        return results
    
    def get_validation_summary(self, validation_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Get summary statistics for batch validation"""
        total = len(validation_results)
        valid = sum(1 for r in validation_results if r.get('is_valid', False))
        invalid = total - valid
        
        scores = [r.get('validation_score', 0) for r in validation_results]
        avg_score = sum(scores) / total if total > 0 else 0
        
        # Count common issues
        common_issues = {}
        for result in validation_results:
            if not result.get('is_valid', False):
                field_errors = result.get('field_validations', {})
                for field, validation in field_errors.items():
                    if not validation.get('valid', False):
                        common_issues[field] = common_issues.get(field, 0) + 1
        
        return {
            'total_certificates': total,
            'valid_certificates': valid,
            'invalid_certificates': invalid,
            'validation_rate': valid / total if total > 0 else 0,
            'average_score': avg_score,
            'common_issues': common_issues,
            'timestamp': datetime.now().isoformat()
        }