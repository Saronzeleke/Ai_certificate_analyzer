import cv2
import numpy as np
from PIL import Image, ImageFilter
from typing import Dict, List, Optional, Tuple, Any
import logging
from datetime import datetime
from pathlib import Path
import joblib
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import pickle

logger = logging.getLogger(__name__)

class ProductionTamperDetector:
    """
    Production-ready tampering detector for certificates.
    Detects: cloning, erasing, copy-move, splicing, text manipulation.
    """
    
    def __init__(self, model_path: Optional[str] = None):
        self.model_version = "2.0.0-production"
        
        # Load trained models if available
        self.isolation_forest = None
        self.scaler = StandardScaler()
        
        if model_path and Path(model_path).exists():
            try:
                with open(model_path, 'rb') as f:
                    model_data = pickle.load(f)
                    self.isolation_forest = model_data.get('model')
                    self.scaler = model_data.get('scaler', StandardScaler())
                logger.info(f"Loaded tamper detection model from {model_path}")
            except Exception as e:
                logger.warning(f"Failed to load model: {e}")
        
        # Configuration
        self.CONFIDENCE_THRESHOLD = 0.75
        self.MIN_REGION_SIZE = 50  # pixels
        self.ELA_THRESHOLD = 25
        self.NOISE_THRESHOLD = 0.15
        
        # Cache for performance
        self._cache = {}
        self._cache_size = 100
        
        logger.info(f"ProductionTamperDetector v{self.model_version} initialized")
    
    async def detect(self, image: np.ndarray, 
                    certificate_type: str = "unknown") -> Dict[str, Any]:
        """
        Detect tampering in certificate image.
        Returns comprehensive tampering analysis.
        """
        try:
            start_time = datetime.now()
            
            # Generate cache key
            cache_key = self._generate_cache_key(image, certificate_type)
            if cache_key in self._cache:
                result = self._cache[cache_key].copy()
                result['cached'] = True
                result['processing_time'] = (datetime.now() - start_time).total_seconds()
                return result
            
            # Run detection methods
            detection_results = []
            
            # 1. ELA (Error Level Analysis) - detects recompression
            ela_result = self._detect_with_ela(image)
            if ela_result['confidence'] > self.CONFIDENCE_THRESHOLD:
                detection_results.append(ela_result)
            
            # 2. Noise inconsistency analysis
            noise_result = self._detect_noise_inconsistency(image)
            if noise_result['confidence'] > self.CONFIDENCE_THRESHOLD:
                detection_results.append(noise_result)
            
            # 3. Copy-move detection
            copy_move_result = self._detect_copy_move(image)
            if copy_move_result['confidence'] > self.CONFIDENCE_THRESHOLD:
                detection_results.append(copy_move_result)
            
            # 4. Text region analysis
            text_result = self._analyze_text_regions(image)
            if text_result['confidence'] > self.CONFIDENCE_THRESHOLD:
                detection_results.append(text_result)
            
            # 5. Machine learning detection (if model loaded)
            ml_result = self._detect_with_ml(image)
            if ml_result['confidence'] > self.CONFIDENCE_THRESHOLD:
                detection_results.append(ml_result)
            
            # 6. Metadata analysis (if available from PIL)
            metadata_result = self._analyze_metadata(image)
            if metadata_result['confidence'] > 0.5:
                detection_results.append(metadata_result)
            
            # Combine results
            combined_result = self._combine_detections(detection_results)
            
            # Calculate overall score
            overall_score = self._calculate_overall_score(combined_result)
            
            # Prepare final result
            processing_time = (datetime.now() - start_time).total_seconds()
            
            result = {
                'is_tampered': overall_score > self.CONFIDENCE_THRESHOLD,
                'tampering_score': overall_score,
                'tampering_confidence': overall_score,
                'detected_types': combined_result['detected_types'],
                'regions': combined_result['regions'],
                'anomalies': combined_result['anomalies'],
                'recommendations': self._generate_recommendations(combined_result),
                'detailed_analysis': {
                    'ela_analysis': ela_result,
                    'noise_analysis': noise_result,
                    'copy_move_analysis': copy_move_result,
                    'text_analysis': text_result,
                    'ml_analysis': ml_result
                },
                'model_version': self.model_version,
                'processing_time': processing_time,
                'timestamp': datetime.now().isoformat()
            }
            
            # Cache result
            self._cache_result(cache_key, result)
            
            logger.info(f"Tamper detection complete: {result['is_tampered']} "
                       f"(score: {overall_score:.2f}, time: {processing_time:.2f}s)")
            
            return result
            
        except Exception as e:
            logger.error(f"Tamper detection failed: {e}")
            return {
                'is_tampered': False,
                'tampering_score': 0.0,
                'error': str(e),
                'model_version': self.model_version,
                'timestamp': datetime.now().isoformat()
            }
    
    def _generate_cache_key(self, image: np.ndarray, cert_type: str) -> str:
        """Generate cache key from image and certificate type"""
        try:
            # Use perceptual hash for caching
            import imagehash
            pil_image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
            img_hash = str(imagehash.phash(pil_image))
            return f"{cert_type}_{img_hash}"
        except:
            # Fallback to simple hash
            return f"{cert_type}_{hash(image.tobytes())}"
    
    def _cache_result(self, key: str, result: dict):
        """Cache detection result"""
        if len(self._cache) >= self._cache_size:
            # Remove oldest
            self._cache.pop(next(iter(self._cache)))
        
        # Remove processing time from cached version
        cached_result = result.copy()
        if 'processing_time' in cached_result:
            del cached_result['processing_time']
        if 'cached' in cached_result:
            del cached_result['cached']
        
        self._cache[key] = cached_result
    
    def _detect_with_ela(self, image: np.ndarray) -> Dict[str, Any]:
        """
        Error Level Analysis - detects areas with different compression levels.
        Useful for detecting cloned/edited regions.
        """
        try:
            # Convert to RGB if needed
            if len(image.shape) == 2:
                rgb_image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
            else:
                rgb_image = image.copy()
            
            # Save at 95% quality
            _, buffer = cv2.imencode('.jpg', rgb_image, [cv2.IMWRITE_JPEG_QUALITY, 95])
            recompressed = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
            
            # Calculate difference
            if rgb_image.shape != recompressed.shape:
                recompressed = cv2.resize(recompressed, (rgb_image.shape[1], rgb_image.shape[0]))
            
            diff = cv2.absdiff(rgb_image, recompressed)
            diff_gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
            
            # Calculate ELA score
            ela_score = np.mean(diff_gray)
            
            # Find suspicious regions
            _, binary = cv2.threshold(diff_gray, self.ELA_THRESHOLD, 255, cv2.THRESH_BINARY)
            
            # Find contours of suspicious regions
            contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            regions = []
            for contour in contours:
                area = cv2.contourArea(contour)
                if area > self.MIN_REGION_SIZE:
                    x, y, w, h = cv2.boundingRect(contour)
                    regions.append({
                        'bbox': [int(x), int(y), int(w), int(h)],
                        'area': float(area),
                        'type': 'ela_anomaly'
                    })
            
            # Calculate confidence
            max_possible_diff = 255
            confidence = min(ela_score / max_possible_diff, 1.0)
            
            return {
                'method': 'ela',
                'score': float(ela_score),
                'confidence': float(confidence),
                'regions': regions,
                'threshold': self.ELA_THRESHOLD,
                'anomaly_count': len(regions)
            }
            
        except Exception as e:
            logger.debug(f"ELA detection failed: {e}")
            return {
                'method': 'ela',
                'score': 0.0,
                'confidence': 0.0,
                'error': str(e)
            }
    
    def _detect_noise_inconsistency(self, image: np.ndarray) -> Dict[str, Any]:
        """
        Detect noise inconsistency across image.
        Edited regions often have different noise patterns.
        """
        try:
            # Convert to grayscale
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image
            
            # Divide image into blocks
            h, w = gray.shape
            block_size = 32
            
            noise_levels = []
            noise_positions = []
            
            for y in range(0, h - block_size, block_size):
                for x in range(0, w - block_size, block_size):
                    block = gray[y:y+block_size, x:x+block_size]
                    
                    # Calculate noise level (variance after high-pass filter)
                    laplacian = cv2.Laplacian(block, cv2.CV_64F)
                    noise = np.var(laplacian)
                    
                    noise_levels.append(noise)
                    noise_positions.append((x, y, noise))
            
            if len(noise_levels) < 4:
                return {
                    'method': 'noise',
                    'score': 0.0,
                    'confidence': 0.0,
                    'error': 'Insufficient blocks'
                }
            
            # Calculate statistics
            noise_mean = np.mean(noise_levels)
            noise_std = np.std(noise_levels)
            
            # Find inconsistent blocks (more than 2 std dev from mean)
            inconsistent_blocks = []
            for x, y, noise in noise_positions:
                if abs(noise - noise_mean) > 2 * noise_std:
                    inconsistent_blocks.append({
                        'bbox': [int(x), int(y), block_size, block_size],
                        'noise_level': float(noise),
                        'deviation': float(abs(noise - noise_mean) / noise_std if noise_std > 0 else 0)
                    })
            
            # Calculate confidence based on inconsistency
            inconsistency_ratio = len(inconsistent_blocks) / len(noise_positions)
            confidence = min(inconsistency_ratio / self.NOISE_THRESHOLD, 1.0)
            
            return {
                'method': 'noise',
                'score': float(inconsistency_ratio),
                'confidence': float(confidence),
                'inconsistent_blocks': inconsistent_blocks,
                'noise_statistics': {
                    'mean': float(noise_mean),
                    'std': float(noise_std),
                    'min': float(np.min(noise_levels)),
                    'max': float(np.max(noise_levels))
                },
                'block_size': block_size
            }
            
        except Exception as e:
            logger.debug(f"Noise detection failed: {e}")
            return {
                'method': 'noise',
                'score': 0.0,
                'confidence': 0.0,
                'error': str(e)
            }
    
    def _detect_copy_move(self, image: np.ndarray) -> Dict[str, Any]:
        """
        Detect copy-move forgery using keypoint matching.
        """
        try:
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image
            
            # Initialize SIFT detector
            sift = cv2.SIFT_create()
            
            # Detect keypoints and descriptors
            keypoints, descriptors = sift.detectAndCompute(gray, None)
            
            if descriptors is None or len(keypoints) < 10:
                return {
                    'method': 'copy_move',
                    'score': 0.0,
                    'confidence': 0.0,
                    'error': 'Insufficient keypoints'
                }
            
            # Match descriptors using FLANN
            index_params = dict(algorithm=1, trees=5)
            search_params = dict(checks=50)
            flann = cv2.FlannBasedMatcher(index_params, search_params)
            
            matches = flann.knnMatch(descriptors, descriptors, k=2)
            
            # Apply ratio test
            good_matches = []
            for match_pair in matches:
                if len(match_pair) == 2:
                    m, n = match_pair
                    if m.distance < 0.7 * n.distance and m.queryIdx != m.trainIdx:
                        good_matches.append(m)
            
            # Find suspicious duplicate regions
            duplicate_regions = []
            if len(good_matches) > 5:
                # Group matches by spatial consistency
                src_pts = np.float32([keypoints[m.queryIdx].pt for m in good_matches])
                dst_pts = np.float32([keypoints[m.trainIdx].pt for m in good_matches])
                
                # Calculate distances between matched points
                distances = np.linalg.norm(src_pts - dst_pts, axis=1)
                
                # Consider matches with significant spatial shift as suspicious
                min_shift = 20  # pixels
                suspicious_indices = np.where(distances > min_shift)[0]
                
                for idx in suspicious_indices[:10]:  # Limit to top 10
                    src_point = keypoints[good_matches[idx].queryIdx].pt
                    dst_point = keypoints[good_matches[idx].trainIdx].pt
                    
                    duplicate_regions.append({
                        'source': [float(src_point[0]), float(src_point[1])],
                        'destination': [float(dst_point[0]), float(dst_point[1])],
                        'distance': float(distances[idx])
                    })
            
            # Calculate confidence
            match_ratio = len(good_matches) / max(1, len(matches))
            confidence = min(match_ratio * 2, 1.0)  # Scale confidence
            
            return {
                'method': 'copy_move',
                'score': float(match_ratio),
                'confidence': float(confidence),
                'keypoint_count': len(keypoints),
                'good_matches': len(good_matches),
                'duplicate_regions': duplicate_regions,
                'suspicious_count': len(duplicate_regions)
            }
            
        except Exception as e:
            logger.debug(f"Copy-move detection failed: {e}")
            return {
                'method': 'copy_move',
                'score': 0.0,
                'confidence': 0.0,
                'error': str(e)
            }
    
    def _analyze_text_regions(self, image: np.ndarray) -> Dict[str, Any]:
        """Analyze text regions for inconsistencies"""
        try:
            # Use OCR to detect text regions
            import pytesseract
            
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image
            
            # Get text data with bounding boxes
            data = pytesseract.image_to_data(gray, output_type=pytesseract.Output.DICT)
            
            text_regions = []
            anomalies = []
            
            for i in range(len(data['text'])):
                text = data['text'][i].strip()
                conf = data['conf'][i]
                
                if text and conf > 0:
                    x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
                    
                    text_regions.append({
                        'text': text,
                        'bbox': [x, y, w, h],
                        'confidence': conf / 100.0
                    })
                    
                    # Check for suspicious text characteristics
                    if self._is_suspicious_text(text, conf):
                        anomalies.append({
                            'type': 'suspicious_text',
                            'text': text,
                            'bbox': [x, y, w, h],
                            'reason': 'Low confidence or suspicious pattern'
                        })
            
            # Analyze text region consistency
            if len(text_regions) >= 3:
                # Check for consistent font sizes (heuristic)
                heights = [r['bbox'][3] for r in text_regions]
                height_std = np.std(heights)
                height_cv = height_std / np.mean(heights) if np.mean(heights) > 0 else 0
                
                if height_cv > 0.5:  # High variation in text height
                    anomalies.append({
                        'type': 'inconsistent_font_sizes',
                        'coefficient_of_variation': float(height_cv)
                    })
            
            # Calculate confidence
            anomaly_ratio = len(anomalies) / max(1, len(text_regions))
            confidence = min(anomaly_ratio * 3, 1.0)  # Scale based on anomalies
            
            return {
                'method': 'text_analysis',
                'score': float(anomaly_ratio),
                'confidence': float(confidence),
                'text_regions': text_regions,
                'anomalies': anomalies,
                'total_text_regions': len(text_regions)
            }
            
        except Exception as e:
            logger.debug(f"Text analysis failed: {e}")
            return {
                'method': 'text_analysis',
                'score': 0.0,
                'confidence': 0.0,
                'error': str(e)
            }
    
    def _is_suspicious_text(self, text: str, confidence: float) -> bool:
        """Check if text appears suspicious"""
        # Check for overlapping/misaligned text patterns
        suspicious_patterns = [
            r'\b\w\w\w\w\w\w\w\w\b',  # Very long words
            r'[0-9]{10,}',  # Long sequences of numbers
            r'[A-Z]{5,}',  # Long sequences of capitals
        ]
        
        import re
        for pattern in suspicious_patterns:
            if re.search(pattern, text):
                return True
        
        # Low confidence text
        if confidence < 30:
            return True
        
        return False
    
    def _detect_with_ml(self, image: np.ndarray) -> Dict[str, Any]:
        """Use machine learning model for detection"""
        try:
            if self.isolation_forest is None:
                return {
                    'method': 'ml',
                    'score': 0.0,
                    'confidence': 0.0,
                    'error': 'Model not loaded'
                }
            
            # Extract features for ML model
            features = self._extract_ml_features(image)
            
            if len(features) == 0:
                return {
                    'method': 'ml',
                    'score': 0.0,
                    'confidence': 0.0,
                    'error': 'Feature extraction failed'
                }
            
            # Scale features
            features_scaled = self.scaler.transform([features])[0]
            
            # Predict anomaly score
            anomaly_score = self.isolation_forest.score_samples([features_scaled])[0]
            
            # Convert to confidence (higher score = more normal)
            confidence = 1.0 - (1.0 / (1.0 + np.exp(-anomaly_score)))  # Sigmoid
            
            return {
                'method': 'ml',
                'score': float(anomaly_score),
                'confidence': float(confidence),
                'features_extracted': len(features),
                'model_loaded': True
            }
            
        except Exception as e:
            logger.debug(f"ML detection failed: {e}")
            return {
                'method': 'ml',
                'score': 0.0,
                'confidence': 0.0,
                'error': str(e)
            }
    
    def _extract_ml_features(self, image: np.ndarray) -> np.ndarray:
        """Extract features for ML model"""
        features = []
        
        try:
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image
            
            # Basic statistics
            features.append(np.mean(gray))
            features.append(np.std(gray))
            features.append(np.median(gray))
            
            # Edge features
            edges = cv2.Canny(gray, 50, 150)
            features.append(np.mean(edges))
            features.append(np.std(edges))
            
            # Texture features
            from skimage.feature import graycomatrix, graycoprops
            glcm = graycomatrix(gray.astype(np.uint8), [1], [0], symmetric=True, normed=True)
            
            texture_props = ['contrast', 'dissimilarity', 'homogeneity', 'energy', 'correlation']
            for prop in texture_props:
                try:
                    value = graycoprops(glcm, prop)[0, 0]
                    features.append(value)
                except:
                    features.append(0.0)
            
            # Frequency domain features
            f = np.fft.fft2(gray)
            fshift = np.fft.fftshift(f)
            magnitude_spectrum = np.log(np.abs(fshift) + 1)
            
            features.append(np.mean(magnitude_spectrum))
            features.append(np.std(magnitude_spectrum))
            
            # Histogram features
            hist = cv2.calcHist([gray], [0], None, [16], [0, 256]).flatten()
            hist = hist / hist.sum() if hist.sum() > 0 else hist
            features.extend(hist[:8])  # First 8 bins
            
        except Exception as e:
            logger.debug(f"Feature extraction failed: {e}")
        
        return np.array(features)
    
    def _analyze_metadata(self, image: np.ndarray) -> Dict[str, Any]:
        """Analyze image metadata for inconsistencies"""
        try:
            # Convert to PIL for metadata analysis
            pil_image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
            
            anomalies = []
            
            # Check for multiple software tags (could indicate editing)
            # This is a simplified check - in production you'd use exifread
            
            return {
                'method': 'metadata',
                'score': 0.0,
                'confidence': 0.3,  # Low confidence for metadata alone
                'anomalies': anomalies,
                'metadata_available': False
            }
            
        except:
            return {
                'method': 'metadata',
                'score': 0.0,
                'confidence': 0.0,
                'metadata_available': False
            }
    
    def _combine_detections(self, detections: List[Dict]) -> Dict[str, Any]:
        """Combine results from different detection methods"""
        combined = {
            'detected_types': [],
            'regions': [],
            'anomalies': [],
            'scores': [],
            'confidences': []
        }
        
        for detection in detections:
            if detection.get('confidence', 0) > 0.3:  # Only consider meaningful detections
                combined['detected_types'].append(detection.get('method', 'unknown'))
                combined['scores'].append(detection.get('score', 0))
                combined['confidences'].append(detection.get('confidence', 0))
                
                # Collect regions
                if 'regions' in detection:
                    for region in detection['regions']:
                        region['detection_method'] = detection.get('method', 'unknown')
                        combined['regions'].append(region)
                
                # Collect anomalies
                if 'anomalies' in detection:
                    for anomaly in detection['anomalies']:
                        anomaly['detection_method'] = detection.get('method', 'unknown')
                        combined['anomalies'].append(anomaly)
        
        return combined
    
    def _calculate_overall_score(self, combined_result: Dict) -> float:
        """Calculate overall tampering score"""
        if not combined_result['confidences']:
            return 0.0
        
        # Weight different detection methods
        method_weights = {
            'ela': 0.35,
            'copy_move': 0.30,
            'noise': 0.20,
            'text_analysis': 0.10,
            'ml': 0.05
        }
        
        weighted_sum = 0
        total_weight = 0
        
        for i, method in enumerate(combined_result['detected_types']):
            weight = method_weights.get(method, 0.05)
            confidence = combined_result['confidences'][i]
            
            weighted_sum += confidence * weight
            total_weight += weight
        
        if total_weight == 0:
            return 0.0
        
        overall_score = weighted_sum / total_weight
        
        # Boost score if multiple methods agree
        if len(combined_result['detected_types']) >= 2:
            overall_score = min(overall_score * 1.3, 1.0)
        
        return overall_score
    
    def _generate_recommendations(self, combined_result: Dict) -> List[str]:
        """Generate recommendations based on detection results"""
        recommendations = []
        
        if not combined_result['detected_types']:
            recommendations.append("No significant tampering detected")
            return recommendations
        
        # Method-specific recommendations
        if 'ela' in combined_result['detected_types']:
            recommendations.append("Possible recompression detected - verify original source")
        
        if 'copy_move' in combined_result['detected_types']:
            recommendations.append("Possible copy-move forgery detected - check for duplicated regions")
        
        if 'noise' in combined_result['detected_types']:
            recommendations.append("Noise inconsistency detected - image may be composited")
        
        if 'text_analysis' in combined_result['detected_types']:
            recommendations.append("Text region anomalies detected - verify text consistency")
        
        # General recommendations
        anomaly_count = len(combined_result['anomalies'])
        if anomaly_count > 3:
            recommendations.append(f"Multiple anomalies detected ({anomaly_count}) - high suspicion")
        
        if len(combined_result['detected_types']) >= 3:
            recommendations.append("Multiple detection methods indicate tampering - high confidence")
        
        return recommendations
    
    def train_model(self, normal_images: List[np.ndarray], 
                   tampered_images: List[np.ndarray],
                   output_path: str):
        """Train isolation forest model for tamper detection"""
        try:
            logger.info(f"Training tamper detection model with {len(normal_images)} normal "
                       f"and {len(tampered_images)} tampered images")
            
            # Extract features from all images
            all_features = []
            all_labels = []
            
            for img in normal_images:
                features = self._extract_ml_features(img)
                if len(features) > 0:
                    all_features.append(features)
                    all_labels.append(0)  # Normal
            
            for img in tampered_images:
                features = self._extract_ml_features(img)
                if len(features) > 0:
                    all_features.append(features)
                    all_labels.append(1)  # Tampered
            
            if len(all_features) < 20:
                raise ValueError(f"Insufficient training data: {len(all_features)} samples")
            
            # Convert to numpy
            X = np.array(all_features)
            y = np.array(all_labels)
            
            # Scale features
            self.scaler.fit(X)
            X_scaled = self.scaler.transform(X)
            
            # Train isolation forest (unsupervised)
            self.isolation_forest = IsolationForest(
                n_estimators=200,
                max_samples='auto',
                contamination=0.1,
                random_state=42,
                n_jobs=-1
            )
            
            self.isolation_forest.fit(X_scaled)
            
            # Evaluate
            scores = self.isolation_forest.score_samples(X_scaled)
            normal_scores = scores[y == 0]
            tampered_scores = scores[y == 1]
            
            logger.info(f"Normal images average score: {np.mean(normal_scores):.4f}")
            logger.info(f"Tampered images average score: {np.mean(tampered_scores):.4f}")
            
            # Save model
            model_data = {
                'model': self.isolation_forest,
                'scaler': self.scaler,
                'training_stats': {
                    'normal_samples': len(normal_images),
                    'tampered_samples': len(tampered_images),
                    'feature_count': X.shape[1],
                    'normal_score_mean': float(np.mean(normal_scores)),
                    'tampered_score_mean': float(np.mean(tampered_scores))
                },
                'version': self.model_version,
                'trained_at': datetime.now().isoformat()
            }
            
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'wb') as f:
                pickle.dump(model_data, f)
            
            logger.info(f"Model trained and saved to {output_path}")
            
            return model_data
            
        except Exception as e:
            logger.error(f"Model training failed: {e}")
            raise
    
    def clear_cache(self):
        """Clear detection cache"""
        self._cache.clear()
        logger.info("Tamper detection cache cleared")
    
    async def batch_detect(self, images: List[np.ndarray]) -> List[Dict[str, Any]]:
        """Batch detect tampering in multiple images"""
        import asyncio
        
        tasks = [self.detect(img) for img in images]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Batch detection failed for image {i}: {result}")
                processed_results.append({
                    'is_tampered': False,
                    'tampering_score': 0.0,
                    'error': str(result),
                    'model_version': self.model_version
                })
            else:
                processed_results.append(result)
        
        return processed_results