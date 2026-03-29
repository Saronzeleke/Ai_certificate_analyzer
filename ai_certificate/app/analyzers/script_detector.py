import cv2
import numpy as np
from typing import Dict, Any, Literal, Tuple
import pickle
import os
from pathlib import Path
import logging
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
import joblib

logger = logging.getLogger(__name__)

class ScriptDetector:
    """
    Efficient script detector for Amharic vs English certificates.
    Optimized for production with ML fallback.
    """
    
    def __init__(self, model_path: str = None):
        self.model_version = "1.1.0-optimized"
        
        # Load ML model if available
        self.model = None
        self.scaler = None
        
        if model_path and os.path.exists(model_path):
            try:
                # Try joblib first (more efficient)
                if model_path.endswith('.joblib'):
                    loaded = joblib.load(model_path)
                    self.model = loaded.get('model')
                    self.scaler = loaded.get('scaler')
                else:
                    # Fallback to pickle
                    with open(model_path, 'rb') as f:
                        loaded = pickle.load(f)
                        self.model = loaded.get('model')
                        self.scaler = loaded.get('scaler')
                
                if self.model and self.scaler:
                    logger.info(f"Loaded script detection model from {model_path}")
                else:
                    logger.warning("Model loaded but missing components")
                    self.model = None
                    self.scaler = None
                    
            except Exception as e:
                logger.warning(f"Failed to load model: {e}")
                self.model = None
                self.scaler = None
        
        # Ethiopic script Unicode ranges for Amharic
        self.ETHIOPIC_RANGES = [
            (0x1200, 0x137F),    # Ethiopic
            (0x1380, 0x139F),    # Ethiopic Supplement
            (0x2D80, 0x2DDF),    # Ethiopic Extended
        ]
        
        # Configuration
        self.CONFIDENCE_THRESHOLD = 0.65
        self.MIN_TEXT_LENGTH = 8
        self.CACHE_SIZE = 1000
        
        # Simple cache for performance
        self._detection_cache = {}
        
        logger.info(f"ScriptDetector v{self.model_version} initialized")
        logger.info(f"ML model: {'loaded' if self.model else 'not available'}")
    
    def detect(self, image: np.ndarray) -> Dict[str, Any]:
        """
        Detect script in image with confidence.
        Returns: {'script': 'amh'|'eng'|'mixed'|'unknown', 'confidence': float, 'method': str}
        """
        # Generate cache key
        cache_key = self._generate_cache_key(image)
        
        if cache_key in self._detection_cache:
            result = self._detection_cache[cache_key]
            result['cached'] = True
            return result
        
        try:
            # Method 1: Fast OCR-based detection (most reliable)
            ocr_result = self._detect_with_fast_ocr(image)
            
            if ocr_result['confidence'] > self.CONFIDENCE_THRESHOLD:
                self._cache_result(cache_key, ocr_result)
                return ocr_result
            
            # Method 2: ML model if available
            if self.model is not None:
                ml_result = self._detect_with_ml(image)
                if ml_result['confidence'] > self.CONFIDENCE_THRESHOLD:
                    self._cache_result(cache_key, ml_result)
                    return ml_result
            
            # Method 3: Visual feature detection (fallback)
            visual_result = self._detect_with_visual_features(image)
            self._cache_result(cache_key, visual_result)
            return visual_result
            
        except Exception as e:
            logger.error(f"Script detection failed: {e}")
            result = {
                'script': 'unknown',
                'confidence': 0.0,
                'method': 'error',
                'error': str(e)
            }
            self._cache_result(cache_key, result)
            return result
    
    def _generate_cache_key(self, image: np.ndarray) -> str:
        """Generate cache key from image"""
        # Use image hash for caching
        try:
            # Convert to grayscale and resize for consistent hashing
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image
            
            # Resize to small size for hashing
            resized = cv2.resize(gray, (32, 32))
            
            # Calculate simple hash
            hash_value = hash(resized.tobytes())
            return str(hash_value)
        except:
            return "unknown"
    
    def _cache_result(self, key: str, result: Dict[str, Any]):
        """Cache detection result"""
        if len(self._detection_cache) >= self.CACHE_SIZE:
            # Remove oldest entry (FIFO)
            self._detection_cache.pop(next(iter(self._detection_cache)))
        
        # Store without cached flag
        result_copy = result.copy()
        if 'cached' in result_copy:
            del result_copy['cached']
        
        self._detection_cache[key] = result_copy
    
    def _detect_with_fast_ocr(self, image: np.ndarray) -> Dict[str, Any]:
        """
        Fast script detection using OCR with minimal processing.
        Most reliable method for production.
        """
        try:
            import pytesseract
            
            # Preprocess for fast OCR
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image
            
            # Fast preprocessing
            gray = cv2.resize(gray, (800, 800))  # Resize for speed
            gray = cv2.GaussianBlur(gray, (3, 3), 0)
            
            # Try English OCR (fast)
            config_eng = '--oem 1 --psm 3 -l eng --dpi 150'
            eng_text = pytesseract.image_to_string(gray, config=config_eng)
            eng_confidence = self._calculate_ocr_confidence(eng_text, 'eng')
            
            # Try Amharic OCR if available
            amh_text = ""
            amh_confidence = 0.0
            
            try:
                config_amh = '--oem 1 --psm 3 -l amh --dpi 150'
                amh_text = pytesseract.image_to_string(gray, config=config_amh)
                amh_confidence = self._calculate_ocr_confidence(amh_text, 'amh')
            except:
                # Amharic not available or failed
                pass
            
            # Determine script based on confidence
            if amh_confidence > eng_confidence and amh_confidence > 0.3:
                script = 'amh'
                confidence = amh_confidence
                method = 'ocr_amharic'
            elif eng_confidence > amh_confidence and eng_confidence > 0.3:
                script = 'eng'
                confidence = eng_confidence
                method = 'ocr_english'
            elif amh_confidence > 0.2 and eng_confidence > 0.2:
                script = 'mixed'
                confidence = (amh_confidence + eng_confidence) / 2
                method = 'ocr_mixed'
            else:
                script = 'unknown'
                confidence = max(amh_confidence, eng_confidence)
                method = 'ocr_low_confidence'
            
            return {
                'script': script,
                'confidence': confidence,
                'method': method,
                'details': {
                    'eng_confidence': eng_confidence,
                    'amh_confidence': amh_confidence,
                    'eng_text_length': len(eng_text.strip()),
                    'amh_text_length': len(amh_text.strip())
                }
            }
            
        except Exception as e:
            logger.debug(f"Fast OCR detection failed: {e}")
            return {
                'script': 'unknown',
                'confidence': 0.0,
                'method': 'ocr_failed',
                'error': str(e)
            }
    
    def _detect_with_ml(self, image: np.ndarray) -> Dict[str, Any]:
        """Use ML model for script detection"""
        try:
            # Extract features
            features = self._extract_ml_features(image)
            
            if self.scaler:
                features = self.scaler.transform([features])[0]
            
            # Predict
            prediction = self.model.predict([features])[0]
            proba = self.model.predict_proba([features])[0]
            
            # Map prediction to script
            script_map = {0: 'eng', 1: 'amh', 2: 'mixed'}
            script = script_map.get(prediction, 'unknown')
            confidence = float(max(proba))
            
            return {
                'script': script,
                'confidence': confidence,
                'method': 'ml_model',
                'details': {
                    'prediction': int(prediction),
                    'probabilities': [float(p) for p in proba]
                }
            }
            
        except Exception as e:
            logger.debug(f"ML detection failed: {e}")
            return {
                'script': 'unknown',
                'confidence': 0.0,
                'method': 'ml_failed',
                'error': str(e)
            }
    
    def _detect_with_visual_features(self, image: np.ndarray) -> Dict[str, Any]:
        """Detect script using visual features"""
        try:
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image
            
            # Calculate basic features
            h, w = gray.shape
            
            # Edge detection
            edges = cv2.Canny(gray, 50, 150)
            edge_density = np.sum(edges > 0) / edges.size
            
            # Texture analysis
            from skimage.feature import graycomatrix, graycoprops
            glcm = graycomatrix(gray, [1], [0], symmetric=True, normed=True)
            contrast = graycoprops(glcm, 'contrast')[0, 0]
            homogeneity = graycoprops(glcm, 'homogeneity')[0, 0]
            
            # Connected components analysis
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            num_labels, _, stats, _ = cv2.connectedComponentsWithStats(binary, 8, cv2.CV_32S)
            
            if num_labels > 1:
                areas = stats[1:, cv2.CC_STAT_AREA]
                avg_area = np.mean(areas) if len(areas) > 0 else 0
                area_std = np.std(areas) if len(areas) > 0 else 0
                uniformity = 1.0 / (1.0 + area_std) if area_std > 0 else 0
            else:
                uniformity = 0
                avg_area = 0
            
            # Heuristic rules based on research about Ethiopic vs Latin scripts
            # Ethiopic script tends to have more uniform character sizes and higher edge density
            ethiopic_score = 0.0
            latin_score = 0.0
            
            # Rule 1: Edge density (Ethiopic often has denser edges)
            if edge_density > 0.15:
                ethiopic_score += 0.3
            elif edge_density < 0.08:
                latin_score += 0.3
            
            # Rule 2: Uniformity of character sizes
            if uniformity > 0.7:
                ethiopic_score += 0.3
            elif uniformity < 0.4:
                latin_score += 0.3
            
            # Rule 3: Contrast (Ethiopic often has higher contrast)
            if contrast > 0.3:
                ethiopic_score += 0.2
            
            # Rule 4: Homogeneity
            if homogeneity > 0.4:
                latin_score += 0.2
            
            # Determine script
            if ethiopic_score > latin_score and ethiopic_score > 0.4:
                script = 'amh'
                confidence = min(ethiopic_score / 1.0, 0.8)  # Cap at 0.8 for heuristic
            elif latin_score > ethiopic_score and latin_score > 0.4:
                script = 'eng'
                confidence = min(latin_score / 1.0, 0.8)
            else:
                script = 'mixed' if max(ethiopic_score, latin_score) > 0.3 else 'unknown'
                confidence = max(ethiopic_score, latin_score) / 1.0
            
            return {
                'script': script,
                'confidence': confidence,
                'method': 'visual_features',
                'details': {
                    'edge_density': edge_density,
                    'uniformity': uniformity,
                    'contrast': contrast,
                    'homogeneity': homogeneity,
                    'avg_area': avg_area,
                    'ethiopic_score': ethiopic_score,
                    'latin_score': latin_score
                }
            }
            
        except Exception as e:
            logger.debug(f"Visual feature detection failed: {e}")
            return {
                'script': 'unknown',
                'confidence': 0.0,
                'method': 'visual_failed',
                'error': str(e)
            }
    
    def _calculate_ocr_confidence(self, text: str, language: str) -> float:
        """Calculate confidence that text is in specified language"""
        if not text or len(text.strip()) < self.MIN_TEXT_LENGTH:
            return 0.0
        
        clean_text = text.strip()
        total_chars = len(clean_text)
        
        if language == 'amh':
            # Count Ethiopic characters
            ethiopic_chars = sum(1 for char in clean_text if self._is_ethiopic_char(char))
            ratio = ethiopic_chars / max(1, total_chars)
            
            # Boost confidence if we have a good amount of Ethiopic
            if ratio > 0.3:
                return min(ratio * 1.5, 1.0)
            else:
                return ratio
        
        elif language == 'eng':
            # Count Latin characters
            latin_chars = sum(1 for char in clean_text if char.isalpha() and char.isascii())
            ratio = latin_chars / max(1, total_chars)
            
            # Penalize if contains Ethiopic (shouldn't be in English text)
            ethiopic_chars = sum(1 for char in clean_text if self._is_ethiopic_char(char))
            penalty = ethiopic_chars * 0.5
            
            return max(0.0, ratio - penalty)
        
        return 0.0
    
    def _is_ethiopic_char(self, char: str) -> bool:
        """Check if character is Ethiopic"""
        try:
            code = ord(char)
            for start, end in self.ETHIOPIC_RANGES:
                if start <= code <= end:
                    return True
            return False
        except:
            return False
    
    def _extract_ml_features(self, image: np.ndarray) -> np.ndarray:
        """Extract features for ML model"""
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        
        # Resize for consistent feature extraction
        resized = cv2.resize(gray, (64, 64))
        
        features = []
        
        # Basic statistics
        features.append(np.mean(resized))
        features.append(np.std(resized))
        features.append(np.median(resized))
        
        # Histogram features
        hist = cv2.calcHist([resized], [0], None, [16], [0, 256]).flatten()
        hist = hist / hist.sum() if hist.sum() > 0 else hist
        features.extend(hist)
        
        # Edge features
        edges = cv2.Canny(resized, 50, 150)
        features.append(np.mean(edges))
        features.append(np.std(edges))
        
        # Texture features
        from skimage.feature import graycomatrix, graycoprops
        glcm = graycomatrix(resized, [1], [0], symmetric=True, normed=True)
        
        for prop in ['contrast', 'dissimilarity', 'homogeneity', 'energy', 'correlation']:
            try:
                value = graycoprops(glcm, prop)[0, 0]
                features.append(value)
            except:
                features.append(0.0)
        
        return np.array(features)
    
    def train_model(self, X_train, y_train, X_val, y_val, save_path: str = None):
        """Train a new ML model for script detection"""
        try:
            from sklearn.ensemble import RandomForestClassifier
            from sklearn.preprocessing import StandardScaler
            from sklearn.metrics import accuracy_score, classification_report
            
            # Scale features
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_val_scaled = scaler.transform(X_val)
            
            # Train model
            model = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                random_state=42,
                n_jobs=-1
            )
            
            model.fit(X_train_scaled, y_train)
            
            # Evaluate
            y_pred = model.predict(X_val_scaled)
            accuracy = accuracy_score(y_val, y_pred)
            
            logger.info(f"Model trained with accuracy: {accuracy:.4f}")
            logger.info(f"Classification report:\n{classification_report(y_val, y_pred)}")
            
            # Save model
            if save_path:
                save_data = {
                    'model': model,
                    'scaler': scaler,
                    'accuracy': accuracy,
                    'version': self.model_version
                }
                
                # Use joblib for efficiency
                joblib.dump(save_data, save_path)
                logger.info(f"Model saved to {save_path}")
            
            return model, scaler, accuracy
            
        except Exception as e:
            logger.error(f"Model training failed: {e}")
            raise
    
    def clear_cache(self):
        """Clear detection cache"""
        self._detection_cache.clear()
        logger.info("Detection cache cleared")
    
    def get_cache_info(self) -> Dict[str, Any]:
        """Get cache information"""
        return {
            'cache_size': len(self._detection_cache),
            'max_cache_size': self.CACHE_SIZE,
            'hit_rate': 'N/A'  # Would need hit tracking
        }