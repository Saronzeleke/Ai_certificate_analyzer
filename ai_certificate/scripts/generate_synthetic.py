#!/usr/bin/env python3
"""
Production-grade script to generate synthetic certificate dataset
- Uses templates from template.py
- Generates real PNG images with filled fields
- Saves JSON labels
- Validates dataset integrity
"""

import argparse
import sys
import json
import shutil
from pathlib import Path
from typing import Tuple, Dict, Any, List
import random
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np

# Ensure app/ is importable
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))
from app.analyzers.synthetic_generator.templates import CertificateTemplates

# -----------------------------
# Validation
# -----------------------------
def validate_dataset(output_dir: Path) -> None:
    images_dir = output_dir / "images"
    labels_dir = output_dir / "labels"

    if not images_dir.exists() or not labels_dir.exists():
        raise RuntimeError("Missing images/ or labels/ directory")

    image_files = sorted(images_dir.glob("*.png"))
    label_files = sorted(labels_dir.glob("*.json"))

    if not image_files:
        raise RuntimeError("No images generated")
    if not label_files:
        raise RuntimeError("No labels generated")
    if len(image_files) != len(label_files):
        raise RuntimeError(f"Image/label count mismatch: {len(image_files)} vs {len(label_files)}")

    for label_path in label_files:
        if label_path.stat().st_size == 0:
            raise RuntimeError(f"Empty JSON detected: {label_path}")
        try:
            with open(label_path, "r", encoding="utf-8") as f:
                json.load(f)
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            raise RuntimeError(f"Invalid JSON {label_path}: {e}")

# -----------------------------
# DPI → image size mapping
# -----------------------------
def resolve_image_size(dpi: int) -> Tuple[int, int]:
    if dpi == 100: return (800, 1131)
    if dpi == 150: return (1240, 1754)
    if dpi == 200: return (1654, 2339)
    return (1240, 1754)

# -----------------------------
# Clean output dir
# -----------------------------
def clean_output_dir(output_dir: Path) -> None:
    if output_dir.exists():
        print(f"⚠️ Cleaning previous output at {output_dir}")
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

# -----------------------------
# Data Generators
# -----------------------------
class DataGenerator:
    """Generate realistic certificate data"""
    
    NAMES = {
        "en": ["John Smith", "Emma Wilson", "Michael Brown", "Sarah Johnson", "David Lee"],
        "am": ["መለሰ ደምሴ", "የስመኘን ታደሰ", "ሰላሳዊ አበበ", "ፍቅርነህ ገብረእግዚአብሔር", "ደረጀ መኮንን"]
    }
    
    UNIVERSITIES = {
        "en": ["Harvard University", "Stanford", "MIT", "Cambridge", "Oxford"],
        "am": ["አዲስ አበባ ዩኒቨርሲቲ", "ባህር ዳር ዩኒቨርሲቲ", "ጅማ ዩኒቨርሲቲ", "ማክሌ ዩኒቨርሲቲ"]
    }
    
    COURSES = {
        "en": ["Computer Science", "Business Administration", "Engineering", "Medicine", "Law"],
        "am": ["ኮምፒውተር ሳይንስ", "ንግድ አስተዳደር", "ኢንጅነሪንግ", "ሕክምና", "ህግ"]
    }
    
    @staticmethod
    def get_language_from_template(template_name: str) -> str:
        """Extract language from template name (e.g., university_en -> en)"""
        if template_name.endswith("_am"):
            return "am"
        return "en"
    
    @staticmethod
    def generate_certificate_data(template_name: str, index: int, is_tampered: bool) -> Dict[str, Any]:
        """Generate realistic data based on template type"""
        language = DataGenerator.get_language_from_template(template_name)
        
        # Extract certificate type
        cert_type = template_name.split("_")[0]
        
        # Base data structure
        data = {
            "id": f"CERT{index:06d}",
            "document_type": cert_type,
            "template_name": template_name,
            "language": language,
            "generated_date": datetime.now().strftime("%Y-%m-%d"),
            "tampered": is_tampered,
            "tampering_type": None,
            "confidence": round(random.uniform(0.7, 1.0), 2)
        }
        
        # Add type-specific fields
        if cert_type == "university":
            data.update({
                "name": random.choice(DataGenerator.NAMES.get(language, DataGenerator.NAMES["en"])),
                "student_id": f"STU{random.randint(10000, 99999)}",
                "university": random.choice(DataGenerator.UNIVERSITIES.get(language, DataGenerator.UNIVERSITIES["en"])),
                "course": random.choice(DataGenerator.COURSES.get(language, DataGenerator.COURSES["en"])),
                "gpa": round(random.uniform(2.5, 4.0), 2),
                "issue_date": (datetime.now() - timedelta(days=random.randint(0, 365))).strftime("%Y-%m-%d"),
                "graduation_year": str(random.randint(2018, 2024))
            })
            
            # Apply tampering if needed
            if is_tampered:
                tampering_type = random.choice(["gpa_modified", "date_modified", "name_modified"])
                data["tampering_type"] = tampering_type
                if tampering_type == "gpa_modified":
                    data["gpa"] = min(4.0, data["gpa"] + random.uniform(0.3, 0.8))
                elif tampering_type == "date_modified":
                    data["issue_date"] = (datetime.now() - timedelta(days=random.randint(400, 700))).strftime("%Y-%m-%d")
                elif tampering_type == "name_modified":
                    data["name"] = data["name"] + " (Modified)"
                    
        elif cert_type == "support_letter":
            data.update({
                "reference_number": f"REF{random.randint(1000, 9999)}",
                "organization": random.choice(DataGenerator.UNIVERSITIES.get(language, DataGenerator.UNIVERSITIES["en"])),
                "body": f"This is to certify that the individual has successfully completed the requirements.",
                "issue_date": datetime.now().strftime("%Y-%m-%d"),
                "valid_until": (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")
            })
            
            if is_tampered:
                data["tampering_type"] = "content_modified"
                data["body"] = data["body"] + " [TAMPERED CONTENT]"
        
        return data

# -----------------------------
# Certificate generation with template mapping
# -----------------------------
def generate_certificate_image(template: Dict[str, Any], data: Dict[str, Any], 
                               image_size: Tuple[int, int]) -> Image.Image:
    """Generate certificate image from template with data mapping"""
    img = Image.new("RGB", image_size, color=(248, 248, 248))  # Light gray background
    draw = ImageDraw.Draw(img)
    
    # Add subtle background texture
    add_background_texture(img)
    
    # Load fonts
    try:
        regular_font = ImageFont.truetype("arial.ttf", 36)
        bold_font = ImageFont.truetype("arialbd.ttf", 40)
        title_font = ImageFont.truetype("arialbd.ttf", 60)
    except:
        print("⚠️ Using default fonts (arial.ttf/arialbd.ttf not found)")
        regular_font = ImageFont.load_default()
        bold_font = regular_font
        title_font = regular_font
    
    # Process each field in template
    for field in template.get("fields", []):
        field_type = field.get("type")
        pos_x, pos_y = field.get("position", [0.5, 0.5])
        size_ratio = field.get("size", 0.04)
        
        # Convert relative to absolute coordinates
        x = int(pos_x * image_size[0])
        y = int(pos_y * image_size[1])
        font_size = int(size_ratio * image_size[1])
        
        # Select appropriate font
        if field_type == "text" and "header" in field.get("name", ""):
            font = title_font
            color = (30, 60, 120)  # Dark blue for headers
        elif field_type == "label":
            font = bold_font
            color = (50, 50, 50)  # Dark gray
        else:
            font = regular_font
            color = (0, 0, 0)  # Black
        
        # Get content based on field type
        content = ""
        if field_type == "text":
            content = field.get("text", "")
        elif field_type == "label":
            content = field.get("text", "")
        elif field_type == "field" and "field" in field:
            field_name = field["field"]
            content = str(data.get(field_name, ""))
        elif field_type == "paragraph" and "field" in field:
            field_name = field["field"]
            content = str(data.get(field_name, ""))
        
        # Handle special field types
        if field_type == "seal":
            add_seal(img, (x, y), int(size_ratio * image_size[1]))
            continue
        elif field_type == "signature":
            add_signature(img, draw, (x, y), int(size_ratio * image_size[1]), data.get("name", ""))
            continue
        
        # Draw text with alignment
        if field.get("align") == "center":
            bbox = draw.textbbox((0, 0), content, font=font)
            text_width = bbox[2] - bbox[0]
            x = x - text_width // 2
        
        draw.text((x, y), content, fill=color, font=font)
    
    # Add tampering artifacts if needed
    if data.get("tampered", False):
        apply_tampering_effects(img, data.get("tampering_type", ""))
    
    return img

def add_background_texture(img: Image.Image) -> None:
    """Add subtle background texture to certificate"""
    width, height = img.size
    noise = np.random.normal(0, 3, (height, width, 3)).astype(np.uint8)
    noise_img = Image.fromarray(noise, mode='RGB')
    img.paste(noise_img, (0, 0), Image.new('L', (width, height), 10))  # 10% opacity

def add_seal(img: Image.Image, position: Tuple[int, int], size: int) -> None:
    """Add a seal/stamp to the certificate"""
    draw = ImageDraw.Draw(img)
    x, y = position
    
    # Draw outer circle
    draw.ellipse([x-size//2, y-size//2, x+size//2, y+size//2], 
                 outline=(200, 0, 0), width=3)
    
    # Draw inner circle
    draw.ellipse([x-size//4, y-size//4, x+size//4, y+size//4], 
                 outline=(200, 0, 0), width=2)
    
    # Add text around seal
    text = "OFFICIAL SEAL"
    try:
        font = ImageFont.truetype("arial.ttf", size//10)
    except:
        font = ImageFont.load_default()
    
    # Simple text in seal (would need more complex for circular text)
    draw.text((x-30, y-10), "SEAL", fill=(200, 0, 0), font=font)

def add_signature(img: Image.Image, draw: ImageDraw.Draw, 
                  position: Tuple[int, int], size: int, name: str) -> None:
    """Add a signature line"""
    x, y = position
    length = size * 2
    
    # Draw signature line
    draw.line([x, y, x+length, y], fill=(0, 0, 0), width=2)
    
    # Add name below line
    try:
        font = ImageFont.truetype("ariali.ttf", size//4)
    except:
        font = ImageFont.load_default()
    
    draw.text((x, y+10), name, fill=(50, 50, 50), font=font)

def apply_tampering_effects(img: Image.Image, tampering_type: str) -> None:
    """Apply tampering effects to image"""
    if tampering_type == "gpa_modified":
        # Add subtle overlay to GPA area
        draw = ImageDraw.Draw(img)
        width, height = img.size
        draw.rectangle([width//2, height//2, width//2+200, height//2+50], 
                      fill=(255, 255, 200, 128))
    elif tampering_type == "date_modified":
        # Add blur effect to date area
        region = img.crop((0, 0, 300, 100))
        region = region.filter(ImageFilter.GaussianBlur(radius=1))
        img.paste(region, (0, 0))
    elif tampering_type == "name_modified":
        # Add red highlight
        draw = ImageDraw.Draw(img)
        draw.rectangle([100, 200, 400, 250], outline=(255, 0, 0), width=2)

# -----------------------------
# Main
# -----------------------------
def main():
    parser = argparse.ArgumentParser(description="Generate production-grade synthetic certificate dataset")
    parser.add_argument("--samples", type=int, default=1000, help="Number of samples to generate")
    parser.add_argument("--tampering", type=float, default=0.2, help="Tampering ratio (0.0–1.0)")
    parser.add_argument("--output", type=str, default="data/training/synthetic", help="Output directory")
    parser.add_argument("--dpi", type=int, default=150, choices=[100, 150, 200], help="Image DPI")
    parser.add_argument("--language", type=str, default="both", choices=["en", "am", "both"], help="Language preference")
    
    args = parser.parse_args()

    print("\n🔧 Synthetic Certificate Dataset Generator (PRODUCTION MODE)")
    print(f"Samples        : {args.samples}")
    print(f"Tampering ratio: {args.tampering:.2f}")
    print(f"DPI            : {args.dpi}")
    print(f"Language       : {args.language}")
    print(f"Output         : {args.output}\n")

    if not (0.0 <= args.tampering <= 1.0):
        raise ValueError("Tampering ratio must be between 0.0 and 1.0")

    image_size = resolve_image_size(args.dpi)
    output_dir = Path(args.output)
    
    # Clean and prepare output directory
    clean_output_dir(output_dir)
    images_dir = output_dir / "images"
    labels_dir = output_dir / "labels"
    images_dir.mkdir(parents=True, exist_ok=True)
    labels_dir.mkdir(parents=True, exist_ok=True)

    # Initialize template manager
    templates = CertificateTemplates()
    all_templates = templates.list_templates()
    
    # Filter templates by language if specified
    if args.language != "both":
        all_templates = [t for t in all_templates if t.endswith(f"_{args.language}")]
    
    if not all_templates:
        raise ValueError(f"No templates found for language: {args.language}")
    
    print(f"📋 Available templates: {', '.join(all_templates)}")
    print(f"🎯 Using {len(all_templates)} template(s)")
    
    try:
        tampered_count = 0
        
        for i in range(args.samples):
            # Select template
            template_name = random.choice(all_templates)
            template = templates.get_template(template_name)
            
            # Determine if this sample should be tampered
            is_tampered = i < int(args.samples * args.tampering)
            if is_tampered:
                tampered_count += 1
            
            # Generate data for this template
            label_data = DataGenerator.generate_certificate_data(template_name, i, is_tampered)
            
            # Generate image
            img = generate_certificate_image(template, label_data, image_size)
            image_filename = f"cert_{i:06d}_{template_name}.png"
            image_file = images_dir / image_filename
            img.save(image_file, "PNG", dpi=(args.dpi, args.dpi))
            
            # Add image path to label data
            label_data["image_path"] = str(image_file.relative_to(output_dir))
            
            # Save JSON label
            label_filename = f"label_{i:06d}_{template_name}.json"
            label_file = labels_dir / label_filename
            with open(label_file, "w", encoding="utf-8") as f:
                json.dump(label_data, f, ensure_ascii=False, indent=2)
            
            # Progress indicator
            if (i + 1) % 100 == 0:
                print(f"📊 Generated {i + 1}/{args.samples} samples...")
        
        # Create metadata file
        metadata = {
            "num_samples": args.samples,
            "tampered_samples": tampered_count,
            "tampering_ratio": args.tampering,
            "image_size": image_size,
            "dpi": args.dpi,
            "templates_used": all_templates,
            "generation_date": datetime.now().isoformat(),
            "dataset_version": "1.0"
        }
        
        metadata_file = output_dir / "metadata.json"
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        # Validate dataset
        print("\n🔍 Validating dataset integrity...")
        validate_dataset(output_dir)
        
        # Summary
        print("\n" + "="*50)
        print("✅ DATASET GENERATION COMPLETE")
        print("="*50)
        print(f"📊 Total samples  : {args.samples}")
        print(f"🔴 Tampered       : {tampered_count} ({args.tampering*100:.1f}%)")
        print(f"🟢 Clean          : {args.samples - tampered_count}")
        print(f"🖼️  Image size     : {image_size[0]}x{image_size[1]}")
        print(f"📁 Images dir     : {images_dir}")
        print(f"📁 Labels dir     : {labels_dir}")
        print(f"📄 Metadata       : {metadata_file}")
        print(f"🌐 Templates used : {len(all_templates)}")
        print("="*50 + "\n")
        
    except Exception as e:
        print("\n❌ DATASET GENERATION FAILED")
        print(f"Error type: {type(e).__name__}")
        print(f"Reason: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()