import torch
import torch.nn as nn
import torchvision.transforms as transforms
from torch.utils.data import Dataset, DataLoader
from PIL import Image
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import logging
import cv2
import json
from pathlib import Path
import albumentations as A
from albumentations.pytorch import ToTensorV2
import joblib
from sklearn.preprocessing import LabelEncoder
import mlflow
import mlflow.pytorch
import pytesseract

logger = logging.getLogger(__name__)

class CertificateFieldDataset(Dataset):
    """Dataset for certificate field extraction"""
    
    def __init__(self, data_dir: str, transform=None, mode: str = 'train'):
        self.data_dir = Path(data_dir)
        self.transform = transform
        self.mode = mode
        
        # Load annotations
        self.annotations = self._load_annotations()
        
        logger.info(f"Loaded {len(self.annotations)} samples for {mode}")
    
    def _load_annotations(self) -> List[Dict]:
        """Load annotations from JSON files"""
        annotations = []
        
        labels_dir = self.data_dir / 'labels'
        images_dir = self.data_dir / 'images'
        
        if not labels_dir.exists() or not images_dir.exists():
            logger.warning(f"Directories not found: {labels_dir}, {images_dir}")
            return annotations
        
        # Load all JSON files
        for label_file in labels_dir.glob('*.json'):
            try:
                with open(label_file, 'r') as f:
                    label_data = json.load(f)
                
                # Get corresponding image
                image_file = images_dir / f"{label_file.stem}.png"
                if not image_file.exists():
                    continue
                
                annotations.append({
                    'image_path': str(image_file),
                    'label': label_data,
                    'image_id': label_file.stem
                })
            except Exception as e:
                logger.debug(f"Failed to load {label_file}: {e}")
        
        return annotations
    
    def __len__(self):
        return len(self.annotations)
    
    def __getitem__(self, idx):
        annotation = self.annotations[idx]
        
        # Load image
        image = Image.open(annotation['image_path']).convert('RGB')
        image_np = np.array(image)
        
        # Get labels
        label_data = annotation['label']
        
        # Extract field information
        # In production, you would have bounding box annotations
        # For now, we'll use a simplified approach
        
        if self.transform:
            augmented = self.transform(image=image_np)
            image_np = augmented['image']
        
        # Convert to tensor
        if isinstance(image_np, np.ndarray):
            image_tensor = torch.from_numpy(image_np).float()
            if len(image_tensor.shape) == 3:
                image_tensor = image_tensor.permute(2, 0, 1)  # HWC to CHW
        else:
            image_tensor = image_np
        
        # Prepare target
        target = {
            'name': label_data.get('name', ''),
            'student_id': label_data.get('student_id', ''),
            'university': label_data.get('university', ''),
            'course': label_data.get('course', ''),
            'gpa': label_data.get('gpa', ''),
            'issue_date': label_data.get('issue_date', ''),
            'language': label_data.get('language', 'english'),
            'image_id': annotation['image_id']
        }
        
        return image_tensor, target

class FieldExtractionModel(nn.Module):
    """CNN model for field extraction"""
    
    def __init__(self, num_fields: int = 6, pretrained: bool = True):
        super().__init__()
        
        # Use ResNet backbone
        from torchvision import models
        
        if pretrained:
            backbone = models.resnet34(pretrained=True)
        else:
            backbone = models.resnet34(pretrained=False)
        
        # Remove final classification layer
        self.backbone = nn.Sequential(*list(backbone.children())[:-2])
        
        # Field detection heads
        self.field_heads = nn.ModuleDict({
            'name': self._create_field_head(),
            'student_id': self._create_field_head(),
            'university': self._create_field_head(),
            'course': self._create_field_head(),
            'gpa': self._create_field_head(),
            'date': self._create_field_head()
        })
        
        # OCR feature extractor (simplified)
        self.ocr_features = nn.Sequential(
            nn.Conv2d(512, 256, kernel_size=3, padding=1),
            nn.BatchNorm2d(256),
            nn.ReLU(),
            nn.AdaptiveAvgPool2d((1, 1))
        )
        
        # Field classifier
        self.field_classifier = nn.Sequential(
            nn.Linear(256 * len(self.field_heads), 512),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(512, num_fields)
        )
    
    def _create_field_head(self) -> nn.Module:
        """Create head for individual field detection"""
        return nn.Sequential(
            nn.Conv2d(512, 256, kernel_size=3, padding=1),
            nn.BatchNorm2d(256),
            nn.ReLU(),
            nn.AdaptiveAvgPool2d((1, 1)),
            nn.Flatten()
        )
    
    def forward(self, x):
        # Extract features
        features = self.backbone(x)
        
        # Process through field heads
        field_features = []
        for head_name, head in self.field_heads.items():
            field_feat = head(features)
            field_features.append(field_feat)
        
        # Concatenate all field features
        combined = torch.cat(field_features, dim=1)
        
        # Classify fields
        field_presence = self.field_classifier(combined)
        
        # Extract OCR-ready features
        ocr_features = self.ocr_features(features)
        ocr_features = ocr_features.view(ocr_features.size(0), -1)
        
        return {
            'field_presence': field_presence,
            'ocr_features': ocr_features,
            'spatial_features': features
        }

class MLFieldExtractor:
    """Production field extractor with ML training capability"""
    
    def __init__(self, model_path: Optional[str] = None, device: Optional[str] = None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model_version = "2.0.0-production"
        
        # Initialize model
        self.model = FieldExtractionModel(pretrained=True)
        self.model.to(self.device)
        
        # Load if pretrained model exists
        if model_path and Path(model_path).exists():
            try:
                self.load_model(model_path)
                logger.info(f"Loaded field extraction model from {model_path}")
            except Exception as e:
                logger.warning(f"Failed to load model: {e}")
        
        # Transform for inference
        self.inference_transform = A.Compose([
            A.Resize(512, 512),
            A.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
            ToTensorV2()
        ])
        
        # Transform for training
        self.train_transform = A.Compose([
            A.Resize(512, 512),
            A.HorizontalFlip(p=0.5),
            A.RandomBrightnessContrast(p=0.2),
            A.GaussNoise(p=0.1),
            A.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
            ToTensorV2()
        ])
        
        # Field mappings
        self.field_mappings = {
            0: 'name',
            1: 'student_id', 
            2: 'university',
            3: 'course',
            4: 'gpa',
            5: 'date'
        }
        
        logger.info(f"ProductionFieldExtractor v{self.model_version} initialized on {self.device}")
    
    def extract_fields(self, image: Image.Image) -> Dict[str, Any]:
        """Extract fields from certificate image"""
        try:
            start_time = datetime.now()
            
            # Preprocess image
            image_np = np.array(image)
            augmented = self.inference_transform(image=image_np)
            image_tensor = augmented['image'].unsqueeze(0).to(self.device)
            
            # Inference
            with torch.no_grad():
                outputs = self.model(image_tensor)
            
            # Process outputs
            field_presence = torch.sigmoid(outputs['field_presence']).cpu().numpy()[0]
            
            # Identify present fields
            present_fields = {}
            for idx, confidence in enumerate(field_presence):
                if confidence > 0.5:  # Threshold
                    field_name = self.field_mappings.get(idx, f'field_{idx}')
                    present_fields[field_name] = float(confidence)
            
            # Get spatial features for field localization
            spatial_features = outputs['spatial_features'].cpu().numpy()
            
            # Estimate field regions (simplified)
            field_regions = self._estimate_field_regions(spatial_features[0])
            
            # Use OCR for text extraction in identified regions
            extracted_text = self._extract_text_from_regions(image, field_regions)
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            return {
                'present_fields': present_fields,
                'field_regions': field_regions,
                'extracted_text': extracted_text,
                'field_confidence': present_fields,  # Same as present_fields for now
                'spatial_features_shape': spatial_features.shape,
                'processing_time': processing_time,
                'model_version': self.model_version,
                'success': True
            }
            
        except Exception as e:
            logger.error(f"Field extraction failed: {e}")
            return {
                'present_fields': {},
                'extracted_text': {},
                'error': str(e),
                'success': False
            }
    
    def _estimate_field_regions(self, spatial_features: np.ndarray) -> List[Dict]:
        """Estimate field regions from spatial features"""
        regions = []
        
        try:
            # Simple heuristic: look for high activation regions
            # In production, you would use a proper region proposal network
            
            h, w = spatial_features.shape[1:]
            num_features = spatial_features.shape[0]
            
            # Find feature maps with high activation
            for i in range(min(num_features, 10)):  # Check first 10 features
                feature_map = spatial_features[i]
                max_activation = np.max(feature_map)
                
                if max_activation > 0.5:
                    # Find region with high activation
                    threshold = max_activation * 0.7
                    high_activation = feature_map > threshold
                    
                    if np.any(high_activation):
                        # Find bounding box
                        rows = np.any(high_activation, axis=1)
                        cols = np.any(high_activation, axis=0)
                        
                        y1, y2 = np.where(rows)[0][[0, -1]] if len(np.where(rows)[0]) > 1 else (0, h-1)
                        x1, x2 = np.where(cols)[0][[0, -1]] if len(np.where(cols)[0]) > 1 else (0, w-1)
                        
                        # Convert to image coordinates (simplified scaling)
                        scale_x = 1024 / w  # Assuming original image width
                        scale_y = 768 / h   # Assuming original image height
                        
                        regions.append({
                            'bbox': [
                                int(x1 * scale_x),
                                int(y1 * scale_y),
                                int((x2 - x1) * scale_x),
                                int((y2 - y1) * scale_y)
                            ],
                            'confidence': float(max_activation),
                            'feature_idx': i
                        })
            
        except Exception as e:
            logger.debug(f"Region estimation failed: {e}")
        
        return regions
    
    def _extract_text_from_regions(self, image: Image.Image, 
                                 regions: List[Dict]) -> Dict[str, str]:
        """Extract text from identified regions using OCR"""
        extracted = {}
        
        try:
            
            
            for i, region in enumerate(regions[:5]):  # Limit to top 5 regions
                x, y, w, h = region['bbox']
                
                # Crop region
                cropped = image.crop((x, y, x + w, y + h))
                
                # OCR
                text = pytesseract.image_to_string(cropped, config='--psm 6')
                text = text.strip()
                
                if text:
                    extracted[f'region_{i}'] = {
                        'text': text,
                        'bbox': region['bbox'],
                        'confidence': region['confidence']
                    }
                    
                    # Try to classify the text
                    field_type = self._classify_text(text)
                    if field_type:
                        extracted[field_type] = text
        
        except Exception as e:
            logger.debug(f"Text extraction failed: {e}")
        
        return extracted
    
    def _classify_text(self, text: str) -> Optional[str]:
        """Classify extracted text into field types"""
        text_lower = text.lower()
        
        # Name patterns
        name_keywords = ['name', 'ስም', 'mr.', 'mrs.', 'ms.']
        if any(keyword in text_lower for keyword in name_keywords):
            return 'name'
        
        # ID patterns
        id_patterns = [r'\bID\b', r'\b\d{5,}\b', r'STU\d+', r'EMP\d+']
        import re
        for pattern in id_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return 'student_id'
        
        # University patterns
        uni_keywords = ['university', 'college', 'institute', 'ዩኒቨርሲቲ']
        if any(keyword in text_lower for keyword in uni_keywords):
            return 'university'
        
        # Course patterns
        course_keywords = ['course', 'program', 'degree', 'ኮርስ']
        if any(keyword in text_lower for keyword in course_keywords):
            return 'course'
        
        # GPA patterns
        gpa_patterns = [r'\b[0-4]\.\d{1,2}\b', r'GPA', r'grade']
        for pattern in gpa_patterns:
            if re.search(pattern, text_lower):
                return 'gpa'
        
        # Date patterns
        date_patterns = [
            r'\d{4}-\d{2}-\d{2}',
            r'\d{2}/\d{2}/\d{4}',
            r'\d{2}-\d{2}-\d{4}'
        ]
        for pattern in date_patterns:
            if re.search(pattern, text):
                return 'date'
        
        return None
    
    def train(self, train_data_dir: str, val_data_dir: str,
             output_dir: str = "models/field_extractor",
             experiment_name: str = "field_extraction"):
        """Train the field extraction model"""
        try:
            logger.info(f"Starting training with MLflow experiment: {experiment_name}")
            
            # Setup MLflow
            mlflow.set_experiment(experiment_name)
            
            # Create datasets
            train_dataset = CertificateFieldDataset(
                train_data_dir, 
                transform=self.train_transform,
                mode='train'
            )
            
            val_dataset = CertificateFieldDataset(
                val_data_dir,
                transform=self.inference_transform,
                mode='val'
            )
            
            if len(train_dataset) == 0 or len(val_dataset) == 0:
                raise ValueError("No training data found")
            
            logger.info(f"Training samples: {len(train_dataset)}, "
                       f"Validation samples: {len(val_dataset)}")
            
            # Create data loaders
            train_loader = DataLoader(
                train_dataset,
                batch_size=8,
                shuffle=True,
                num_workers=2,
                pin_memory=True
            )
            
            val_loader = DataLoader(
                val_dataset,
                batch_size=8,
                shuffle=False,
                num_workers=2,
                pin_memory=True
            )
            
            # Training configuration
            epochs = 50
            learning_rate = 1e-4
            weight_decay = 1e-5
            
            # Optimizer and scheduler
            optimizer = torch.optim.AdamW(
                self.model.parameters(),
                lr=learning_rate,
                weight_decay=weight_decay
            )
            
            scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
                optimizer, 
                T_max=epochs
            )
            
            # Loss function
            criterion = nn.BCEWithLogitsLoss()
            
            # Training loop
            best_val_loss = float('inf')
            patience = 10
            patience_counter = 0
            
            with mlflow.start_run():
                # Log parameters
                mlflow.log_params({
                    'epochs': epochs,
                    'batch_size': 8,
                    'learning_rate': learning_rate,
                    'weight_decay': weight_decay,
                    'model': 'ResNet34-based',
                    'train_samples': len(train_dataset),
                    'val_samples': len(val_dataset)
                })
                
                for epoch in range(epochs):
                    # Training phase
                    self.model.train()
                    train_loss = 0.0
                    
                    for batch_idx, (images, targets) in enumerate(train_loader):
                        images = images.to(self.device)
                        
                        # Convert targets to field presence tensor
                        # This is simplified - in production you'd have proper labels
                        field_presence = self._targets_to_tensor(targets).to(self.device)
                        
                        optimizer.zero_grad()
                        outputs = self.model(images)
                        loss = criterion(outputs['field_presence'], field_presence)
                        
                        loss.backward()
                        optimizer.step()
                        
                        train_loss += loss.item()
                        
                        if batch_idx % 10 == 0:
                            logger.info(f"Epoch {epoch+1}/{epochs}, "
                                       f"Batch {batch_idx}/{len(train_loader)}, "
                                       f"Loss: {loss.item():.4f}")
                    
                    avg_train_loss = train_loss / len(train_loader)
                    
                    # Validation phase
                    self.model.eval()
                    val_loss = 0.0
                    
                    with torch.no_grad():
                        for images, targets in val_loader:
                            images = images.to(self.device)
                            field_presence = self._targets_to_tensor(targets).to(self.device)
                            
                            outputs = self.model(images)
                            loss = criterion(outputs['field_presence'], field_presence)
                            val_loss += loss.item()
                    
                    avg_val_loss = val_loss / len(val_loader)
                    
                    # Log metrics
                    mlflow.log_metrics({
                        'train_loss': avg_train_loss,
                        'val_loss': avg_val_loss,
                        'learning_rate': scheduler.get_last_lr()[0]
                    }, step=epoch)
                    
                    logger.info(f"Epoch {epoch+1}/{epochs} - "
                               f"Train Loss: {avg_train_loss:.4f}, "
                               f"Val Loss: {avg_val_loss:.4f}")
                    
                    # Early stopping
                    if avg_val_loss < best_val_loss:
                        best_val_loss = avg_val_loss
                        patience_counter = 0
                        
                        # Save best model
                        self.save_model(Path(output_dir) / "best_model.pth")
                        logger.info(f"New best model saved with val loss: {best_val_loss:.4f}")
                    else:
                        patience_counter += 1
                        if patience_counter >= patience:
                            logger.info(f"Early stopping at epoch {epoch+1}")
                            break
                    
                    scheduler.step()
                
                # Log final model
                mlflow.pytorch.log_model(self.model, "model")
                
                # Save training summary
                training_summary = {
                    'final_train_loss': avg_train_loss,
                    'final_val_loss': avg_val_loss,
                    'best_val_loss': best_val_loss,
                    'epochs_completed': epoch + 1,
                    'early_stopped': patience_counter >= patience,
                    'model_version': self.model_version,
                    'trained_at': datetime.now().isoformat()
                }
                
                summary_path = Path(output_dir) / "training_summary.json"
                summary_path.parent.mkdir(parents=True, exist_ok=True)
                with open(summary_path, 'w') as f:
                    json.dump(training_summary, f, indent=2)
                
                logger.info(f"Training completed. Best val loss: {best_val_loss:.4f}")
                logger.info(f"Model saved to {output_dir}")
                
                return training_summary
                
        except Exception as e:
            logger.error(f"Training failed: {e}")
            raise
    
    def _targets_to_tensor(self, targets: List[Dict]) -> torch.Tensor:
        """Convert targets to field presence tensor"""
        batch_size = len(targets)
        num_fields = len(self.field_mappings)
        
        tensor = torch.zeros(batch_size, num_fields)
        
        for i, target in enumerate(targets):
            # Check which fields are present in the target
            for field_name in target.keys():
                if field_name in ['name', 'student_id', 'university', 'course', 'gpa', 'issue_date']:
                    # Map field name to index
                    for idx, name in self.field_mappings.items():
                        if name == field_name or (field_name == 'issue_date' and name == 'date'):
                            if target[field_name]:  # Field is present
                                tensor[i, idx] = 1.0
        
        return tensor
    
    def save_model(self, output_path: str):
        """Save model to disk"""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        torch.save({
            'model_state_dict': self.model.state_dict(),
            'model_version': self.model_version,
            'field_mappings': self.field_mappings,
            'saved_at': datetime.now().isoformat()
        }, output_path)
        
        logger.info(f"Model saved to {output_path}")
    
    def load_model(self, model_path: str):
        """Load model from disk"""
        checkpoint = torch.load(model_path, map_location=self.device)
        
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.model.to(self.device)
        self.model.eval()
        
        logger.info(f"Model loaded from {model_path}")
    
    def evaluate(self, test_data_dir: str) -> Dict[str, Any]:
        """Evaluate model on test data"""
        try:
            test_dataset = CertificateFieldDataset(
                test_data_dir,
                transform=self.inference_transform,
                mode='test'
            )
            
            if len(test_dataset) == 0:
                return {'error': 'No test data found'}
            
            test_loader = DataLoader(
                test_dataset,
                batch_size=8,
                shuffle=False
            )
            
            self.model.eval()
            
            criterion = nn.BCEWithLogitsLoss()
            total_loss = 0.0
            correct_predictions = 0
            total_predictions = 0
            
            with torch.no_grad():
                for images, targets in test_loader:
                    images = images.to(self.device)
                    field_presence = self._targets_to_tensor(targets).to(self.device)
                    
                    outputs = self.model(images)
                    loss = criterion(outputs['field_presence'], field_presence)
                    total_loss += loss.item()
                    
                    # Calculate accuracy
                    predictions = (torch.sigmoid(outputs['field_presence']) > 0.5).float()
                    correct_predictions += (predictions == field_presence).sum().item()
                    total_predictions += field_presence.numel()
            
            avg_loss = total_loss / len(test_loader)
            accuracy = correct_predictions / total_predictions
            
            logger.info(f"Evaluation - Loss: {avg_loss:.4f}, Accuracy: {accuracy:.4f}")
            
            return {
                'test_loss': avg_loss,
                'accuracy': accuracy,
                'samples_evaluated': len(test_dataset),
                'model_version': self.model_version
            }
            
        except Exception as e:
            logger.error(f"Evaluation failed: {e}")
            return {'error': str(e)}
    
    async def batch_extract(self, images: List[Image.Image]) -> List[Dict[str, Any]]:
        """Batch extract fields from multiple images"""
        import asyncio
        
        tasks = []
        for image in images:
            # Run extraction in thread pool
            tasks.append(asyncio.to_thread(self.extract_fields, image))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Batch extraction failed for image {i}: {result}")
                processed_results.append({
                    'error': str(result),
                    'success': False
                })
            else:
                processed_results.append(result)
        
        return processed_results