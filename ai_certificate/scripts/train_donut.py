#!/usr/bin/env python3
"""
Script to train Donut model on synthetic certificate data
"""

import argparse
import sys
from pathlib import Path
import json
from PIL import Image

# Add app to path
sys.path.append(str(Path(__file__).parent.parent))

# def create_donut_dataset(synthetic_dir: str, output_dir: str):
#     """Create dataset in Donut format from synthetic data"""
#     synthetic_path = Path(synthetic_dir)
#     output_path = Path(output_dir)
#     output_path.mkdir(parents=True, exist_ok=True)
    
#     images_dir = synthetic_path / "images"
#     labels_dir = synthetic_path / "labels"
    
#     dataset = []
    
#     # Get all image files
#     image_files = list(images_dir.glob("*.png"))
    
#     print(f"Found {len(image_files)} images")
    
#     for i, img_path in enumerate(image_files[:10000]):  # Limit for training
#         # Get corresponding label
#         label_path = labels_dir / f"{img_path.stem}.json"
        
#         if not label_path.exists():
#             print(f"Warning: No label for {img_path.name}")
#             continue
        
#         # Load image
#         image = Image.open(img_path).convert("RGB")
        
#         # Load label
#         import gzip

#         try:
#             # Try reading as gzip
#             with gzip.open(label_path, 'rt', encoding='utf-8') as f:
#                 label_data = json.load(f)
#         except OSError:
#             # Fallback: plain JSON
#             with open(label_path, 'r', encoding='utf-8') as f:
#                 label_data = json.load(f)

#         # Create Donut format sample
#         sample = {
#             "image": image,
#             "label": {
#                 "name": label_data.get("name", ""),
#                 "student_id": label_data.get("student_id", label_data.get("certificate_id", "")),
#                 "university": label_data.get("university", label_data.get("organization", "")),
#                 "course": label_data.get("course", ""),
#                 "gpa": str(label_data.get("gpa", "")),
#                 "issue_date": label_data.get("issue_date", ""),
#                 "language": label_data.get("language", "english")
#             }
#         }
        
#         dataset.append(sample)
        
#         if (i + 1) % 100 == 0:
#             print(f"Processed {i + 1}/{len(image_files[:10000])} samples")
    
#     return dataset
def create_donut_dataset(synthetic_dir: str, output_dir: str):
    """Create dataset with lazy loading (store paths, not images)"""
    synthetic_path = Path(synthetic_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    images_dir = synthetic_path / "images"
    labels_dir = synthetic_path / "labels"
    
    dataset = []
    
    image_files = list(images_dir.glob("*.png"))
    print(f"Found {len(image_files)} images")
    
    for i, img_path in enumerate(image_files):  # remove the 10000 limit
        label_path = labels_dir / f"{img_path.stem}.json"
        if not label_path.exists():
            print(f"Warning: No label for {img_path.name}")
            continue

        # Store only paths and label paths
        dataset.append({
            "image_path": str(img_path),
            "label_path": str(label_path)
        })

        if (i + 1) % 100 == 0:
            print(f"Processed {i + 1}/{len(image_files)} samples")
    
    return dataset

def split_dataset(dataset, train_ratio=0.8):
    """Split dataset into train and validation"""
    split_idx = int(len(dataset) * train_ratio)
    train_dataset = dataset[:split_idx]
    val_dataset = dataset[split_idx:]
    
    return train_dataset, val_dataset

def main():
    parser = argparse.ArgumentParser(description="Train Donut model on synthetic data")
    parser.add_argument("--synthetic-dir", type=str, default="data/training/synthetic",
                        help="Directory with synthetic data")
    parser.add_argument("--output-dir", type=str, default="models/donut_certificate",
                        help="Output directory for trained model")
    parser.add_argument("--epochs", type=int, default=10,
                        help="Number of training epochs")
    parser.add_argument("--batch-size", type=int, default=2,
                        help="Batch size for training")
    
    args = parser.parse_args()
    
    print("Creating Donut dataset...")
    #dataset = create_donut_dataset(args.synthetic_dir, args.output_dir)
    dataset = create_donut_dataset(args.synthetic_dir, args.output_dir)
    for i, item in enumerate(dataset):
       if "image_path" not in item or "label_path" not in item:
          print(f"Malformed dataset item at index {i}: {item}")
          sys.exit(1)
    
    if len(dataset) < 100:
        print(f"Warning: Only {len(dataset)} samples available. Need at least 100 for training.")
        sys.exit(1)
    
    print(f"Created dataset with {len(dataset)} samples")
    
    # Split dataset
    train_dataset, val_dataset = split_dataset(dataset)
    print(f"Train: {len(train_dataset)} samples, Validation: {len(val_dataset)} samples")
    
    # Initialize Donut model
    from app.analyzers.ml_models.donut_model import DonutCertificateParser
    
    print("Initializing Donut model...")
    donut_parser = DonutCertificateParser()
    
    # Train model
    print(f"Starting training for {args.epochs} epochs...")
    try:
        train_result = donut_parser.fine_tune(
            train_dataset=train_dataset,
            val_dataset=val_dataset,
            output_dir=args.output_dir
        )
        
        print(f"\n✅ Training completed successfully!")
        print(f"   Model saved to: {args.output_dir}")
        
    except Exception as e:
        print(f"\n❌ Training failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
