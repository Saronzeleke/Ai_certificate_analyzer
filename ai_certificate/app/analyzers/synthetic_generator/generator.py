import os
import json
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any, Generator
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import cv2
import arabic_reshaper
from bidi.algorithm import get_display
import logging
import gc
from multiprocessing import Pool, cpu_count, Manager
from concurrent.futures import ProcessPoolExecutor, as_completed
import traceback
from dataclasses import dataclass
from enum import Enum
import psutil

logger = logging.getLogger(__name__)

class Language(Enum):
    ENGLISH = "english"
    AMHARIC = "amharic"

class CertificateType(Enum):
    UNIVERSITY = "university"
    TRAINING = "training"

class TamperingType(Enum):
    TEXT_OVERLAY = "text_overlay"
    STAMP_FORGERY = "stamp_forgery"
    DATE_ALTERATION = "date_alteration"
    PARTIAL_ERASURE = "partial_erasure"

@dataclass
class MemoryOptimizedConfig:
    """Memory-optimized configuration for 8GB RAM"""
    output_dir: str = "data/training/synthetic"
    num_samples: int = 1000
    tampering_ratio: float = 0.2
    image_size: Tuple[int, int] = (1240, 1754)  # A4 at 150 DPI (50% reduction)
    dpi: int = 150
    quality: int = 85  # Lower quality for training
    max_processes: int = 2  # Conservative for 8GB RAM
    batch_size: int = 25  # Smaller batches
    save_interval: int = 10  # Save every N images
    use_disk_streaming: bool = True
    compress_labels: bool = True
    monitor_memory: bool = True

class MemoryMonitor:
    """Monitor and manage memory usage"""
    
    @staticmethod
    def get_memory_usage() -> Dict[str, float]:
        """Get current memory usage in MB"""
        process = psutil.Process(os.getpid())
        system = psutil.virtual_memory()
        
        return {
            "process_mb": process.memory_info().rss / 1024 / 1024,
            "system_used_mb": system.used / 1024 / 1024,
            "system_available_mb": system.available / 1024 / 1024,
            "system_percent": system.percent
        }
    
    @staticmethod
    def check_memory_limit(limit_mb: int = 6000) -> bool:
        """Check if memory usage is below limit (leave 2GB for system)"""
        usage = MemoryMonitor.get_memory_usage()
        return usage["process_mb"] < limit_mb
    
    @staticmethod
    def force_garbage_collection():
        """Force garbage collection and clear caches"""
        gc.collect()
        
        # Clear OpenCV and NumPy caches if possible
        try:
            import cv2
            cv2.destroyAllWindows()
        except:
            pass
        
        try:
            import numpy as np
            np._globals._clear_cache()
        except:
            pass

class SyntheticCertificateGenerator:
    """Memory-optimized synthetic certificate generator for 8GB RAM"""
    
    def __init__(self, config: Optional[MemoryOptimizedConfig] = None):
        self.config = config or MemoryOptimizedConfig()
        self.output_dir = Path(self.config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Memory monitoring
        self.memory_monitor = MemoryMonitor() if self.config.monitor_memory else None
        
        # Load fonts efficiently
        self.fonts = self._load_fonts_memory_efficient()
        
        # Initialize minimal data pools (lazy load if needed)
        self._data_pools = None
        
        logger.info(f"Memory-optimized generator initialized")
        logger.info(f"Image size: {self.config.image_size}, Processes: {self.config.max_processes}")
        logger.info(f"Batch size: {self.config.batch_size}, DPI: {self.config.dpi}")
    
    def _load_fonts_memory_efficient(self) -> Dict[str, Dict[str, Any]]:
        """Load fonts without keeping all sizes in memory"""
        fonts_dir = Path("app/utils/fonts")
        fonts = {
            Language.ENGLISH.value: {},
            Language.AMHARIC.value: {}
        }
        
        # English fonts - load only paths, not objects
        english_fonts = [
            ("arial", fonts_dir / "english" / "Arial.ttf"),
            ("times", fonts_dir / "english" / "TimesNewRoman.ttf"),
            ("helvetica", fonts_dir / "english" / "Helvetica.ttf"),
        ]
        
        # Amharic fonts
        amharic_fonts = [
            ("abyssinica", fonts_dir / "amharic" / "AbyssinicaSIL-R.ttf"),
            #("nyala", fonts_dir / "amharic" / "Nyala.ttf"),
        ]
        
        # Store only paths - create font objects on demand
        for font_name, font_path in english_fonts:
            if font_path.exists():
                fonts[Language.ENGLISH.value][font_name] = str(font_path)
            else:
                logger.warning(f"English font not found: {font_path}")
        
        for font_name, font_path in amharic_fonts:
            if font_path.exists():
                fonts[Language.AMHARIC.value][font_name] = str(font_path)
            else:
                logger.warning(f"Amharic font not found: {font_path}")
        
        # Fallback to system fonts if needed
        if not fonts[Language.ENGLISH.value]:
            fonts[Language.ENGLISH.value]["system"] = "Arial"
        
        if not fonts[Language.AMHARIC.value]:
            # For Amharic, fallback to English fonts (not ideal but functional)
            fonts[Language.AMHARIC.value] = fonts[Language.ENGLISH.value].copy()
        
        logger.info(f"Font paths loaded: {sum(len(f) for f in fonts.values())} fonts")
        return fonts
    
    def _get_font(self, language: str, size: int) -> ImageFont.FreeTypeFont:
        """Get font object on demand (saves memory)"""
        try:
            if language not in self.fonts or not self.fonts[language]:
                language = Language.ENGLISH.value
            
            # Get first available font for the language
            font_info = next(iter(self.fonts[language].values()))
            
            if isinstance(font_info, str):
                # It's a path, load the font
                return ImageFont.truetype(font_info, size)
            else:
                # Already a font object (shouldn't happen with current implementation)
                return ImageFont.truetype(font_info, size)
                
        except Exception as e:
            logger.warning(f"Failed to load font, using default: {e}")
            return ImageFont.load_default()
    
    @property
    def data_pools(self) -> Dict[str, List]:
        """Lazy load data pools to save memory"""
        if self._data_pools is None:
            self._data_pools = self._init_minimal_data_pools()
        return self._data_pools
    
    def _init_minimal_data_pools(self) -> Dict[str, List]:
        """Initialize only essential data pools"""
        return {
            "english_names": [
                "John Smith", "Mary Johnson", "Robert Williams", "Sarah Brown",
                "Michael Davis", "Jennifer Wilson", "William Taylor"
            ],
            "amharic_names": [
                "ሳሮን ተፈራ", "ዳንኤል ገብረእግዚአብሔር", "መስቀል አለማየሁ",
                "ሄኖክ ወልደማርያም", "ሚካኤል አስራት"
            ],
            "universities_en": [
                "University of Addis Ababa", "Harvard University", "Stanford University",
                "MIT", "Cambridge University"
            ],
            "universities_am": [
                "አዲስ አበባ ዩኒቨርሲቲ", "ሀርቫርድ ዩኒቨርሲቲ", "ስታንፎርድ ዩኒቨርሲቲ"
            ],
            "courses_en": [
                "Computer Science", "Business Administration", "Engineering",
                "Medicine", "Law"
            ],
            "courses_am": [
                "ኮምፒውተር ሳይንስ", "ቢዝነስ አስተዳደር", "ኢንጂነሪንግ",
                "ሕክምና", "ህግ"
            ]
        }
    
    def _reshape_amharic(self, text: str) -> str:
        # """Reshape Amharic text with memory-efficient approach"""
        # try:
        #     # Quick check if text contains Amharic
        #     if any(0x1200 <= ord(c) <= 0x137F for c in text):
        #         reshaped = arabic_reshaper.reshape(text)
        #         return get_display(reshaped)
        #     return text
        # except:
        #     return text
        return text
    
    def generate_single_certificate(self, 
                                  index: int,
                                  language: str = None,
                                  certificate_type: str = None,
                                  add_tampering: bool = None) -> Optional[Tuple[str, str]]:
        """Generate a single certificate and return paths (memory efficient)"""
        try:
            # Use provided params or randomize
            if language is None:
                language = random.choice([Language.ENGLISH.value, Language.AMHARIC.value])
            
            if certificate_type is None:
                certificate_type = random.choice([
                    CertificateType.UNIVERSITY.value,
                    CertificateType.TRAINING.value
                ])
            
            if add_tampering is None:
                add_tampering = random.random() < self.config.tampering_ratio
            
            # Generate data first (lightweight)
            if certificate_type == CertificateType.UNIVERSITY.value:
                data = self._generate_university_data(language)
            else:
                data = self._generate_training_data(language)
            
            # Create image with minimal memory footprint
            img = self._create_certificate_image(data, language, certificate_type)
            
            # Apply tampering if needed
            if add_tampering:
                img = self._apply_tampering(img, data, language)
                data["tampering"] = True
            
            # Apply lightweight augmentations
            img = self._apply_light_augmentations(img)
            
            # Generate filenames
            img_filename = f"cert_{index:08d}.png"
            label_filename = f"cert_{index:08d}.json"
            
            img_path = self.output_dir / "images" / img_filename
            label_path = self.output_dir / "labels" / label_filename
            
            # Ensure directories exist
            img_path.parent.mkdir(parents=True, exist_ok=True)
            label_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Save image with optimized settings
            img.save(
                img_path,
                "PNG",
                optimize=True,
                compress_level=6,  # Medium compression
                dpi=(self.config.dpi, self.config.dpi)
            )
            
            # Save label with compression if enabled
            if self.config.compress_labels:
                import gzip
                with gzip.open(label_path, 'wt', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False)
            else:
                with open(label_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False)
            
            # Clear memory
            del img
            if index % self.config.save_interval == 0:
                gc.collect()
            
            return str(img_path), str(label_path)
            
        except Exception as e:
            logger.error(f"Failed to generate certificate {index}: {e}")
            logger.error(traceback.format_exc())
            return None
    
    def _create_certificate_image(self, data: Dict, language: str, 
                                cert_type: str) -> Image.Image:
        """Create certificate image with minimal memory usage"""
        # Create base image
        img = Image.new('RGB', self.config.image_size, color='white')
        draw = ImageDraw.Draw(img)
        
        # Draw simple border
        draw.rectangle([20, 20, self.config.image_size[0]-20, self.config.image_size[1]-20],
                      outline='black', width=2)
        
        # Draw header
        header_font = self._get_font(language, 48)
        header_text = "University Certificate" if cert_type == CertificateType.UNIVERSITY.value else "Training Certificate"
        if language == Language.AMHARIC.value:
            header_text = "የዩኒቨርሲቲ ማረጋገጫ" if cert_type == CertificateType.UNIVERSITY.value else "የስልጠና ማረጋገጫ"
        
        draw.text((self.config.image_size[0]//2, 100), header_text, 
                 fill='darkblue', font=header_font, anchor='mm')
        
        # Draw content
        content_font = self._get_font(language, 28)
        y_offset = 200
        
        for key, value in data.items():
            if key in ['name', 'student_id', 'university', 'course', 'gpa', 'issue_date']:
                label = key.replace('_', ' ').title()
                if language == Language.AMHARIC.value:
                    label = self._get_amharic_label(key)
                    value = self._reshape_amharic(str(value)) if isinstance(value, str) else str(value)
                
                text = f"{label}: {value}"
                draw.text((100, y_offset), text, fill='black', font=content_font)
                y_offset += 60
        
        return img
    
    def _get_amharic_label(self, key: str) -> str:
        """Get Amharic label for field"""
        labels = {
            'name': 'ስም',
            'student_id': 'የተማሪ መታወቂያ',
            'university': 'ዩኒቨርሲቲ',
            'course': 'ኮርስ',
            'gpa': 'አማካይ ነጥብ',
            'issue_date': 'የተሰጠበት ቀን'
        }
        return labels.get(key, key)
    
    def _generate_university_data(self, language: str) -> Dict:
        """Generate university certificate data"""
        if language == Language.AMHARIC.value:
            name = random.choice(self.data_pools["amharic_names"])
            university = random.choice(self.data_pools["universities_am"])
            course = random.choice(self.data_pools["courses_am"])
        else:
            name = random.choice(self.data_pools["english_names"])
            university = random.choice(self.data_pools["universities_en"])
            course = random.choice(self.data_pools["courses_en"])
        
        issue_date = datetime.now() - timedelta(days=random.randint(365, 365*4))
        
        return {
            "name": name,
            "student_id": f"ID{random.randint(10000, 99999)}",
            "university": university,
            "course": course,
            "gpa": round(random.uniform(2.5, 4.0), 2),
            "issue_date": issue_date.strftime("%Y-%m-%d"),
            "language": language,
            "certificate_type": "university"
        }
    
    def _generate_training_data(self, language: str) -> Dict:
        """Generate training certificate data"""
        if language == Language.AMHARIC.value:
            name = random.choice(self.data_pools["amharic_names"])
            course = random.choice(self.data_pools["courses_am"])
        else:
            name = random.choice(self.data_pools["english_names"])
            course = random.choice(self.data_pools["courses_en"])
        
        issue_date = datetime.now() - timedelta(days=random.randint(30, 365))
        
        return {
            "name": name,
            "certificate_id": f"CERT{random.randint(1000, 9999)}",
            "course": course,
            "issue_date": issue_date.strftime("%Y-%m-%d"),
            "duration": random.choice(["3 months", "6 months", "1 year"]),
            "grade": random.choice(["A", "B+", "B", "C+"]),
            "language": language,
            "certificate_type": "training"
        }
    
    def _apply_tampering(self, img: Image.Image, data: Dict, language: str) -> Image.Image:
        """Apply tampering to certificate"""
        tampering_type = random.choice(list(TamperingType))
        draw = ImageDraw.Draw(img)
        
        if tampering_type == TamperingType.TEXT_OVERLAY:
            # Simple text overlay
            font = self._get_font(language, 24)
            if language == Language.AMHARIC.value:
                text = "የተቀየረ"
            else:
                text = "ALTERED"
            
            x = random.randint(200, self.config.image_size[0] - 300)
            y = random.randint(300, self.config.image_size[1] - 300)
            draw.text((x, y), text, fill="red", font=font)
            
        elif tampering_type == TamperingType.STAMP_FORGERY:
            # Simple fake stamp
            x = random.randint(100, self.config.image_size[0] - 200)
            y = random.randint(100, self.config.image_size[1] - 200)
            radius = 50
            
            draw.ellipse([x, y, x + radius*2, y + radius*2], 
                        outline="red", width=3)
            
            if language == Language.AMHARIC.value:
                text = "ማህተም"
            else:
                text = "STAMP"
            
            font = self._get_font(language, 16)
            draw.text((x + radius, y + radius), text, fill="red", 
                     font=font, anchor="mm")
        
        return img
    
    def _apply_light_augmentations(self, img: Image.Image) -> Image.Image:
        """Apply memory-efficient augmentations"""
        # Convert to numpy once
        img_np = np.array(img, dtype=np.uint8)  # Use uint8 to save memory
        
        # Random noise (light)
        if random.random() > 0.7:
            noise = np.random.randint(0, 10, img_np.shape, dtype=np.uint8)
            img_np = cv2.add(img_np, noise)
        
        # Random brightness/contrast
        if random.random() > 0.6:
            alpha = random.uniform(0.9, 1.1)
            beta = random.randint(-5, 5)
            img_np = cv2.convertScaleAbs(img_np, alpha=alpha, beta=beta)
        
        # Convert back to PIL
        return Image.fromarray(img_np)
    
    def _generate_batch_sequential(self, start_idx: int, batch_size: int) -> List[Tuple[str, str]]:
        """Generate a batch sequentially (memory safe)"""
        results = []
        
        for i in range(batch_size):
            idx = start_idx + i
            if idx >= self.config.num_samples:
                break
            
            result = self.generate_single_certificate(idx)
            if result:
                results.append(result)
            
            # Monitor memory
            if self.memory_monitor and (i % 5 == 0):
                mem = self.memory_monitor.get_memory_usage()
                if mem["process_mb"] > 4000:  # 4GB threshold
                    logger.warning(f"High memory usage: {mem['process_mb']:.1f}MB")
                    self.memory_monitor.force_garbage_collection()
        
        return results
    
    def generate_single_worker(self, worker_id: int, indices: List[int], 
                             queue) -> int:
        """Worker function for parallel processing"""
        generated = 0
        for idx in indices:
            try:
                result = self.generate_single_certificate(idx)
                if result:
                    generated += 1
                    queue.put((worker_id, idx, result))
                
                # Clean memory periodically
                if generated % self.config.save_interval == 0:
                    gc.collect()
                    
            except Exception as e:
                logger.error(f"Worker {worker_id} failed on index {idx}: {e}")
                continue
        
        return generated
    
    def generate_dataset_streaming(self) -> Path:
        """Generate dataset using disk streaming (most memory efficient)"""
        logger.info(f"Generating {self.config.num_samples} certificates using disk streaming")
        
        # Create directories
        images_dir = self.output_dir / "images"
        labels_dir = self.output_dir / "labels"
        images_dir.mkdir(parents=True, exist_ok=True)
        labels_dir.mkdir(parents=True, exist_ok=True)
        
        metadata_file = self.output_dir / "metadata.json"
        
        start_time = datetime.now()
        generated = 0
        
        # Generate in small batches
        for batch_start in range(0, self.config.num_samples, self.config.batch_size):
            batch_end = min(batch_start + self.config.batch_size, self.config.num_samples)
            batch_size = batch_end - batch_start
            
            logger.info(f"Processing batch {batch_start//self.config.batch_size + 1}/"
                       f"{(self.config.num_samples + self.config.batch_size - 1)//self.config.batch_size}")
            
            # Generate and save each certificate immediately
            for idx in range(batch_start, batch_end):
                try:
                    result = self.generate_single_certificate(idx)
                    if result:
                        generated += 1
                    
                    if (idx + 1) % 10 == 0:
                        elapsed = (datetime.now() - start_time).total_seconds()
                        rate = generated / elapsed if elapsed > 0 else 0
                        logger.info(f"Progress: {generated}/{self.config.num_samples} "
                                   f"({generated/self.config.num_samples*100:.1f}%) "
                                   f"Rate: {rate:.1f} certs/sec")
                
                except Exception as e:
                    logger.error(f"Failed certificate {idx}: {e}")
                    continue
            
            # Clear memory after each batch
            gc.collect()
            
            # Check memory usage
            if self.memory_monitor:
                mem = self.memory_monitor.get_memory_usage()
                logger.debug(f"Memory after batch: {mem['process_mb']:.1f}MB")
        
        # Save metadata
        metadata = {
            "total_samples": generated,
            "tampering_ratio": self.config.tampering_ratio,
            "image_size": self.config.image_size,
            "dpi": self.config.dpi,
            "generated_at": datetime.now().isoformat(),
            "generation_time_seconds": (datetime.now() - start_time).total_seconds(),
            "rate_per_second": generated / (datetime.now() - start_time).total_seconds() if generated > 0 else 0
        }
        
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(f"Dataset generation complete: {generated} certificates in {elapsed:.1f} seconds "
                   f"({generated/elapsed:.1f} certs/sec)")
        
        return self.output_dir
    
    def generate_dataset_parallel_safe(self) -> Path:
        """Parallel generation with memory limits for 8GB RAM"""
        logger.info(f"Generating {self.config.num_samples} certificates with {self.config.max_processes} processes")
        
        # Create directories
        images_dir = self.output_dir / "images"
        labels_dir = self.output_dir / "labels"
        images_dir.mkdir(parents=True, exist_ok=True)
        labels_dir.mkdir(parents=True, exist_ok=True)
        
        start_time = datetime.now()
        generated = 0
        
        # Use ProcessPoolExecutor with limited processes
        with ProcessPoolExecutor(max_workers=self.config.max_processes) as executor:
            # Submit batches of work
            futures = []
            
            # Split work into chunks for each process
            chunk_size = max(1, self.config.num_samples // (self.config.max_processes * 4))
            
            for chunk_start in range(0, self.config.num_samples, chunk_size):
                chunk_end = min(chunk_start + chunk_size, self.config.num_samples)
                chunk_indices = list(range(chunk_start, chunk_end))
                
                # Submit chunk to executor
                future = executor.submit(self._process_chunk, chunk_indices)
                futures.append(future)
            
            # Process results as they complete
            for future in as_completed(futures):
                try:
                    chunk_generated = future.result()
                    generated += chunk_generated
                    
                    elapsed = (datetime.now() - start_time).total_seconds()
                    rate = generated / elapsed if elapsed > 0 else 0
                    logger.info(f"Progress: {generated}/{self.config.num_samples} "
                               f"({generated/self.config.num_samples*100:.1f}%) "
                               f"Rate: {rate:.1f} certs/sec")
                    
                    # Force GC after each chunk
                    gc.collect()
                    
                except Exception as e:
                    logger.error(f"Chunk failed: {e}")
                    continue
        
        # Save metadata
        metadata = {
            "total_samples": generated,
            "tampering_ratio": self.config.tampering_ratio,
            "image_size": self.config.image_size,
            "dpi": self.config.dpi,
            "generated_at": datetime.now().isoformat(),
            "generation_time_seconds": (datetime.now() - start_time).total_seconds(),
            "rate_per_second": generated / (datetime.now() - start_time).total_seconds() if generated > 0 else 0
        }
        
        metadata_file = self.output_dir / "metadata.json"
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(f"Parallel generation complete: {generated} certificates in {elapsed:.1f} seconds "
                   f"({generated/elapsed:.1f} certs/sec)")
        
        return self.output_dir
    
    def _process_chunk(self, indices: List[int]) -> int:
        """Process a chunk of indices (runs in worker process)"""
        # Each process gets its own generator instance
        worker_generator = SyntheticCertificateGenerator(self.config)
        generated = 0
        
        for idx in indices:
            try:
                result = worker_generator.generate_single_certificate(idx)
                if result:
                    generated += 1
                
                # Periodic cleanup
                if generated % self.config.save_interval == 0:
                    gc.collect()
                    
            except Exception as e:
                logger.error(f"Failed certificate {idx} in worker: {e}")
                continue
        
        return generated
    
    def generate_dataset(self, parallel: bool = None) -> Path:
        """Main dataset generation method"""
        if parallel is None:
            # Auto-detect based on sample count
            parallel = self.config.num_samples > 100
        
        if parallel and self.config.num_samples >= 100:
            # Use parallel for larger datasets
            return self.generate_dataset_parallel_safe()
        else:
            # Use streaming for small datasets or safe mode
            return self.generate_dataset_streaming()

# Optimized CLI interface
def generate_optimized_dataset(
    output_dir: str = "data/training/synthetic",
    num_samples: int = 1000,
    tampering_ratio: float = 0.2,
    image_size: Tuple[int, int] = (1240, 1754),  # 150 DPI
    max_processes: int = 2,
    batch_size: int = 25,
    use_parallel: bool = True
):
    """Memory-optimized dataset generation entry point"""
    
    # Check available memory
    try:
        import psutil
        available_mb = psutil.virtual_memory().available / 1024 / 1024
        logger.info(f"Available memory: {available_mb:.1f} MB")
        
        # Adjust based on available memory
        if available_mb < 2000:  # Less than 2GB available
            logger.warning("Low memory detected, reducing settings")
            max_processes = 1
            batch_size = 10
            image_size = (800, 1131)  # 100 DPI
    except:
        pass
    
    config = MemoryOptimizedConfig(
        output_dir=output_dir,
        num_samples=num_samples,
        tampering_ratio=tampering_ratio,
        image_size=image_size,
        max_processes=max_processes,
        batch_size=batch_size
    )
    
    generator = SyntheticCertificateGenerator(config)
    
    if use_parallel and num_samples >= 100:
        return generator.generate_dataset_parallel_safe()
    else:
        return generator.generate_dataset_streaming()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Memory-optimized synthetic certificate generator")
    parser.add_argument("--samples", type=int, default=1000, 
                       help="Number of samples to generate (default: 1000)")
    parser.add_argument("--tampering", type=float, default=0.2,
                       help="Tampering ratio (0.0-1.0, default: 0.2)")
    parser.add_argument("--output", type=str, default="data/training/synthetic",
                       help="Output directory")
    parser.add_argument("--dpi", type=int, default=150,
                       help="Image DPI (150 for 1240x1754, 100 for 800x1131)")
    parser.add_argument("--processes", type=int, default=2,
                       help="Max parallel processes (default: 2 for 8GB RAM)")
    parser.add_argument("--batch", type=int, default=25,
                       help="Batch size (default: 25)")
    parser.add_argument("--sequential", action="store_true",
                       help="Use sequential generation (safer for low memory)")
    
    args = parser.parse_args()
    
    # Calculate image size based on DPI
    if args.dpi == 100:
        image_size = (800, 1131)
    elif args.dpi == 150:
        image_size = (1240, 1754)
    elif args.dpi == 200:
        image_size = (1654, 2339)
    else:
        image_size = (1240, 1754)  # Default 150 DPI
    
    print(f"Generating {args.samples} certificates with:")
    print(f"  Output: {args.output}")
    print(f"  Tampering: {args.tampering*100}%")
    print(f"  Image size: {image_size} ({args.dpi} DPI)")
    print(f"  Processes: {args.processes}")
    print(f"  Batch size: {args.batch}")
    print(f"  Mode: {'sequential' if args.sequential else 'parallel'}")
    
    # Generate dataset
    output_dir = generate_optimized_dataset(
        output_dir=args.output,
        num_samples=args.samples,
        tampering_ratio=args.tampering,
        image_size=image_size,
        max_processes=args.processes,
        batch_size=args.batch,
        use_parallel=not args.sequential
    )
    
    print(f"\n✅ Dataset generated successfully at: {output_dir}")
    print(f"   Images: {output_dir}/images/")
    print(f"   Labels: {output_dir}/labels/")
    print(f"   Metadata: {output_dir}/metadata.json")