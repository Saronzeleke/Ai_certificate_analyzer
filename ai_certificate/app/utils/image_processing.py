import cv2
import numpy as np
from PIL import Image, ImageEnhance
from typing import List, Optional, Tuple
import logging
import asyncio
from pathlib import Path
from pdf2image import convert_from_path
from typing import Dict

logger = logging.getLogger(__name__)

class ImageProcessor:
    """Image processing utilities for certificate analysis"""
    
    def __init__(self):
        self.supported_formats = ['.pdf', '.jpg', '.jpeg', '.png', '.tiff', '.bmp']
        self.model_version = "2024.1.0-image-processor"
        
        logger.info(f"ImageProcessor v{self.model_version} initialized")
    
    async def process_document(self, document_path: str) -> List[np.ndarray]:
        """Process document and extract images from all pages"""
        try:
            images = []
            
            # Check file type
            file_path = Path(document_path)
            suffix = file_path.suffix.lower()
            
            if suffix == '.pdf':
                images = await self._extract_from_pdf(document_path)
            elif suffix in ['.jpg', '.jpeg', '.png', '.tiff', '.bmp']:
                images = await self._extract_from_image(document_path)
            else:
                raise ValueError(f"Unsupported file format: {suffix}")
            
            if not images:
                raise Exception("No images extracted from document")
            
            # Process each image
            processed_images = []
            for img in images:
                processed = await self._process_image(img)
                if processed is not None:
                    processed_images.append(processed)
            
            logger.info(f"Extracted {len(processed_images)} processed images")
            return processed_images
            
        except Exception as e:
            logger.error(f"Document processing failed: {e}")
            raise
    
    async def _extract_from_pdf(self, pdf_path: str) -> List[np.ndarray]:
        """Extract images from PDF"""
        try:
           
            
            images = convert_from_path(pdf_path, dpi=200)
            image_arrays = []
            
            for img in images:
                # Convert PIL to numpy
                img_array = np.array(img)
                
                # Convert RGB to BGR for OpenCV if needed
                if len(img_array.shape) == 3 and img_array.shape[2] == 3:
                    img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
                
                image_arrays.append(img_array)
            
            return image_arrays
            
        except ImportError:
            logger.error("pdf2image not installed. Install with: pip install pdf2image")
            raise
        except Exception as e:
            logger.error(f"PDF extraction failed: {e}")
            raise
    
    async def _extract_from_image(self, image_path: str) -> List[np.ndarray]:
        """Load image from file"""
        try:
            img = cv2.imread(image_path)
            if img is None:
                raise Exception(f"Failed to load image: {image_path}")
            
            return [img]
            
        except Exception as e:
            logger.error(f"Image loading failed: {e}")
            raise
    
    async def _process_image(self, image: np.ndarray) -> Optional[np.ndarray]:
        """Process single image for analysis"""
        try:
            # Convert to RGB if needed
            if len(image.shape) == 3 and image.shape[2] == 4:
                image = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
            elif len(image.shape) == 3 and image.shape[2] == 3:
                pass  # Already BGR
            elif len(image.shape) == 2:
                image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
            else:
                raise ValueError(f"Unsupported image shape: {image.shape}")
            
            # Resize if too large
            h, w = image.shape[:2]
            max_dimension = 2000
            
            if max(h, w) > max_dimension:
                scale = max_dimension / max(h, w)
                new_h, new_w = int(h * scale), int(w * scale)
                image = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
            
            # Enhance image for better OCR
            enhanced = await self._enhance_image(image)
            
            return enhanced
            
        except Exception as e:
            logger.error(f"Image processing failed: {e}")
            return None
    
    async def _enhance_image(self, image: np.ndarray) -> np.ndarray:
        """Enhance image for OCR"""
        try:
            # Convert to PIL for enhancement
            pil_img = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
            
            # Enhance contrast
            enhancer = ImageEnhance.Contrast(pil_img)
            pil_img = enhancer.enhance(1.2)
            
            # Enhance sharpness
            enhancer = ImageEnhance.Sharpness(pil_img)
            pil_img = enhancer.enhance(1.1)
            
            # Convert back to numpy
            enhanced = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
            
            # Additional OpenCV enhancements
            # Convert to LAB color space
            lab = cv2.cvtColor(enhanced, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            
            # Apply CLAHE to L-channel
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            cl = clahe.apply(l)
            
            # Merge channels
            limg = cv2.merge([cl, a, b])
            enhanced = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)
            
            # Denoise
            enhanced = cv2.fastNlMeansDenoisingColored(enhanced, None, 10, 10, 7, 21)
            
            return enhanced
            
        except Exception as e:
            logger.debug(f"Image enhancement failed, using original: {e}")
            return image
    
    def deskew_image(self, image: np.ndarray) -> np.ndarray:
        """Deskew image if tilted"""
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            gray = cv2.bitwise_not(gray)
            
            # Threshold the image
            thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
            
            # Find coordinates of non-zero pixels
            coords = np.column_stack(np.where(thresh > 0))
            
            # Get angle of minimum area rectangle
            angle = cv2.minAreaRect(coords)[-1]
            
            # Adjust angle
            if angle < -45:
                angle = 90 + angle
            else:
                angle = -angle
            
            # Rotate image if angle is significant
            if abs(angle) > 0.5:
                (h, w) = image.shape[:2]
                center = (w // 2, h // 2)
                M = cv2.getRotationMatrix2D(center, angle, 1.0)
                rotated = cv2.warpAffine(image, M, (w, h), 
                                        flags=cv2.INTER_CUBIC,
                                        borderMode=cv2.BORDER_REPLICATE)
                return rotated
            
            return image
            
        except Exception as e:
            logger.debug(f"Deskew failed: {e}")
            return image
    
    def detect_and_crop_edges(self, image: np.ndarray) -> np.ndarray:
        """Detect and crop edges to remove borders"""
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Apply edge detection
            edges = cv2.Canny(gray, 50, 150)
            
            # Find contours
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if contours:
                # Find largest contour (assumed to be document)
                largest_contour = max(contours, key=cv2.contourArea)
                x, y, w, h = cv2.boundingRect(largest_contour)
                
                # Add padding
                padding = 20
                x = max(0, x - padding)
                y = max(0, y - padding)
                w = min(image.shape[1] - x, w + 2 * padding)
                h = min(image.shape[0] - y, h + 2 * padding)
                
                # Crop image
                cropped = image[y:y+h, x:x+w]
                
                # Only return if crop is significantly smaller than original
                if w < image.shape[1] * 0.9 or h < image.shape[0] * 0.9:
                    return cropped
            
            return image
            
        except Exception as e:
            logger.debug(f"Edge cropping failed: {e}")
            return image
    
    def calculate_image_quality(self, image: np.ndarray) -> Dict[str, float]:
        """Calculate image quality metrics"""
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Calculate blurriness (Laplacian variance)
            blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()
            
            # Calculate contrast
            contrast_score = np.std(gray)
            
            # Calculate brightness
            brightness_score = np.mean(gray)
            
            # Calculate entropy
            hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
            hist = hist.ravel() / hist.sum()
            entropy_score = -np.sum(hist * np.log2(hist + 1e-10))
            
            # Calculate noise
            denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
            noise_score = np.mean(np.abs(gray.astype(float) - denoised.astype(float)))
            
            return {
                'blur_score': float(blur_score),
                'contrast_score': float(contrast_score),
                'brightness_score': float(brightness_score),
                'entropy_score': float(entropy_score),
                'noise_score': float(noise_score),
                'overall_quality': float(min(
                    (blur_score / 100) * 0.3 +
                    (contrast_score / 50) * 0.3 +
                    (1 - brightness_score / 255) * 0.2 +
                    (entropy_score / 8) * 0.2,
                    1.0
                ))
            }
            
        except Exception as e:
            logger.debug(f"Quality calculation failed: {e}")
            return {
                'blur_score': 0.0,
                'contrast_score': 0.0,
                'brightness_score': 0.0,
                'entropy_score': 0.0,
                'noise_score': 0.0,
                'overall_quality': 0.0
            }