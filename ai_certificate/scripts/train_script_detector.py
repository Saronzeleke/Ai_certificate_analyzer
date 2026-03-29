#!/usr/bin/env python3
"""
Production script to train Amharic/English script detector
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from datetime import datetime
import numpy as np
import cv2
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix
import joblib
import mlflow
from mlflow.sklearn import log_model
import pandas as pd

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from app.utils.image_processing import ImageProcessor
from app.analyzers.script_detector import ScriptDetector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ScriptDetectorTrainer:
    """Production-ready script detector trainer"""
    
    def __init__(self, experiment_name="script_detector"):
        self.experiment_name = experiment_name
        self.mlflow_tracking_uri = "http://localhost:5000"  # MLflow tracking server
        mlflow.set_tracking_uri(self.mlflow_tracking_uri)
        mlflow.set_experiment(experiment_name)
    
    def extract_features(self, image_path: str, label: str) -> dict:
        """Extract features from image for script detection"""
        img = cv2.imread(str(image_path))
        if img is None:
            return None
        
        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Resize for consistency
        resized = cv2.resize(gray, (256, 256))
        
        features = {
            'mean_intensity': np.mean(resized),
            'std_intensity': np.std(resized),
            'skewness': float(pd.Series(resized.flatten()).skew()),
            'kurtosis': float(pd.Series(resized.flatten()).kurtosis()),
            
            # Edge features
            'edges_sobel': np.mean(cv2.Sobel(resized, cv2.CV_64F, 1, 1)),
            'edges_canny': np.mean(cv2.Canny(resized, 100, 200)) / 255.0,
            
            # Texture features
            'contrast': self._calculate_contrast(resized),
            'homogeneity': self._calculate_homogeneity(resized),
            
            # Fourier transform features (text frequency)
            'high_freq_energy': self._calculate_frequency_energy(resized),
            
            # Label
            'label': 0 if label == 'eng' else 1 if label == 'amh' else 2,  # mixed=2
            'label_name': label
        }
        
        # Histogram features
        hist = cv2.calcHist([resized], [0], None, [16], [0, 256]).flatten()
        hist = hist / hist.sum()
        for i, val in enumerate(hist):
            features[f'hist_bin_{i}'] = float(val)
        
        return features
    
    def _calculate_contrast(self, image: np.ndarray) -> float:
        """Calculate image contrast"""
        min_val = np.min(image)
        max_val = np.max(image)
        return float((max_val - min_val) / (max_val + min_val + 1e-10))
    
    def _calculate_homogeneity(self, image: np.ndarray) -> float:
        """Calculate image homogeneity"""
        from skimage.feature import graycomatrix, graycoprops
        
        try:
            glcm = graycomatrix(image.astype(np.uint8), [1], [0], symmetric=True, normed=True)
            return float(graycoprops(glcm, 'homogeneity')[0, 0])
        except:
            return 0.5
    
    def _calculate_frequency_energy(self, image: np.ndarray) -> float:
        """Calculate high-frequency energy in Fourier domain"""
        f = np.fft.fft2(image)
        fshift = np.fft.fftshift(f)
        magnitude_spectrum = 20 * np.log(np.abs(fshift) + 1)
        
        # High frequency energy (corners)
        h, w = magnitude_spectrum.shape
        center_h, center_w = h // 2, w // 2
        corner_energy = np.sum(magnitude_spectrum[center_h-20:center_h+20, center_w-20:center_w+20])
        total_energy = np.sum(magnitude_spectrum)
        
        return float(1 - (corner_energy / total_energy) if total_energy > 0 else 0)
    
    def prepare_dataset(self, data_dir: str) -> tuple:
        """Prepare dataset from directory structure"""
        data_dir = Path(data_dir)
        
        features_list = []
        labels = []
        
        # Expected structure: data_dir/{eng,amh,mixed}/*.png
        for script_type in ['eng', 'amh', 'mixed']:
            script_dir = data_dir / script_type
            if not script_dir.exists():
                logger.warning(f"Directory not found: {script_dir}")
                continue
            
            image_files = list(script_dir.glob("*.png")) + list(script_dir.glob("*.jpg"))
            
            for img_path in image_files:
                features = self.extract_features(img_path, script_type)
                if features:
                    features_list.append(features)
                    labels.append(features['label'])
            
            logger.info(f"Loaded {len(image_files)} images for {script_type}")
        
        if not features_list:
            raise ValueError("No training data found")
        
        # Convert to DataFrame
        df = pd.DataFrame(features_list)
        
        # Prepare X and y
        feature_cols = [col for col in df.columns if not col.startswith(('label', 'hist_bin_'))]
        X = df[feature_cols].values
        y = df['label'].values
        
        logger.info(f"Dataset shape: {X.shape}, Labels: {np.unique(y, return_counts=True)}")
        
        return X, y, feature_cols
    
    def train(self, X_train, y_train, X_val, y_val, params: dict = None):
        """Train model with MLflow tracking"""
        if params is None:
            params = {
                'n_estimators': 200,
                'max_depth': 15,
                'min_samples_split': 5,
                'min_samples_leaf': 2,
                'random_state': 42,
                'n_jobs': -1
            }
        
        with mlflow.start_run():
            # Log parameters
            mlflow.log_params(params)
            
            # Train model
            model = RandomForestClassifier(**params)
            model.fit(X_train, y_train)
            
            # Evaluate
            train_score = model.score(X_train, y_train)
            val_score = model.score(X_val, y_val)
            
            y_pred = model.predict(X_val)
            report = classification_report(y_val, y_pred, output_dict=True)
            
            # Log metrics
            mlflow.log_metric("train_accuracy", train_score)
            mlflow.log_metric("val_accuracy", val_score)
            mlflow.log_metric("precision", report['weighted avg']['precision'])
            mlflow.log_metric("recall", report['weighted avg']['recall'])
            mlflow.log_metric("f1_score", report['weighted avg']['f1-score'])
            
            # Log confusion matrix
            cm = confusion_matrix(y_val, y_pred)
            cm_path = "confusion_matrix.png"
            self._plot_confusion_matrix(cm, ['eng', 'amh', 'mixed'], cm_path)
            mlflow.log_artifact(cm_path)
            
            # Log model
            model_info = mlflow.sklearn.log_model(model, "script_detector_model")
            
            logger.info(f"Training complete. Validation accuracy: {val_score:.4f}")
            
            return model, model_info
    
    def _plot_confusion_matrix(self, cm, classes, save_path):
        """Plot and save confusion matrix"""
        import matplotlib.pyplot as plt
        
        plt.figure(figsize=(8, 6))
        plt.imshow(cm, interpolation='nearest', cmap=plt.cm.Blues)
        plt.title('Confusion Matrix')
        plt.colorbar()
        tick_marks = np.arange(len(classes))
        plt.xticks(tick_marks, classes, rotation=45)
        plt.yticks(tick_marks, classes)
        
        # Add text annotations
        thresh = cm.max() / 2.
        for i in range(cm.shape[0]):
            for j in range(cm.shape[1]):
                plt.text(j, i, format(cm[i, j], 'd'),
                        horizontalalignment="center",
                        color="white" if cm[i, j] > thresh else "black")
        
        plt.tight_layout()
        plt.ylabel('True label')
        plt.xlabel('Predicted label')
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close()
    
    def save_model(self, model, output_path: str, feature_cols: list):
        """Save model with metadata"""
        model_data = {
            'model': model,
            'feature_columns': feature_cols,
            'version': '1.0.0',
            'trained_at': datetime.now().isoformat(),
            'classes': ['eng', 'amh', 'mixed']
        }
        
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        joblib.dump(model_data, output_path)
        logger.info(f"Model saved to {output_path}")
        
        # Save feature importance
        importance_df = pd.DataFrame({
            'feature': feature_cols,
            'importance': model.feature_importances_
        }).sort_values('importance', ascending=False)
        
        importance_path = output_path.parent / "feature_importance.csv"
        importance_df.to_csv(importance_path, index=False)
        logger.info(f"Feature importance saved to {importance_path}")

def main():
    parser = argparse.ArgumentParser(description="Train script detector for Amharic/English")
    parser.add_argument("--data-dir", required=True, help="Directory with training data")
    parser.add_argument("--output-dir", default="models/script_detector", help="Output directory")
    parser.add_argument("--test-size", type=float, default=0.2, help="Test set size")
    parser.add_argument("--random-state", type=int, default=42, help="Random seed")
    parser.add_argument("--mlflow", action="store_true", help="Enable MLflow tracking")
    
    args = parser.parse_args()
    
    # Start training
    trainer = ScriptDetectorTrainer()
    
    logger.info("Preparing dataset...")
    X, y, feature_cols = trainer.prepare_dataset(args.data_dir)
    
    # Split data
    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=args.test_size, random_state=args.random_state, stratify=y
    )
    
    logger.info(f"Training set: {X_train.shape}, Validation set: {X_val.shape}")
    
    # Train model
    logger.info("Training model...")
    model, model_info = trainer.train(X_train, y_train, X_val, y_val)
    
    # Save model
    output_path = Path(args.output_dir) / "script_detector.joblib"
    trainer.save_model(model, output_path, feature_cols)
    
    logger.info("✅ Training completed successfully!")

if __name__ == "__main__":
    main()