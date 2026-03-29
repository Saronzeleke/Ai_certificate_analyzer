import json
from pathlib import Path
from typing import Tuple, List
import tempfile
import shutil

def generate_optimized_dataset(
    output_dir: str,
    num_samples: int,
    tampering_ratio: float,
    image_size: Tuple[int, int],
    max_processes: int = 2,
    batch_size: int = 25,
    use_parallel: bool = True
) -> str:
    """
    Bulletproof synthetic dataset generator
    - Writes images + labels safely
    - Ensures no empty or corrupted JSON
    """

    output_dir = Path(output_dir)
    images_dir = output_dir / "images"
    labels_dir = output_dir / "labels"

    images_dir.mkdir(parents=True, exist_ok=True)
    labels_dir.mkdir(parents=True, exist_ok=True)

    for i in range(num_samples):
        # Simulate image generation
        image_file = images_dir / f"cert_{i:05d}.png"
        image_file.touch()  # Placeholder for real image generation

        # Simulate label generation
        label_data = {
            "id": i,
            "tampered": i < int(num_samples * tampering_ratio),
            "fields": {"name": f"Name{i}", "score": 100}
        }

        # Write JSON safely using temp file + atomic rename
        temp_file = labels_dir / f"cert_{i:05d}.json.tmp"
        final_file = labels_dir / f"cert_{i:05d}.json"

        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(label_data, f, ensure_ascii=False, indent=2)

        temp_file.rename(final_file)  # atomic move ensures no empty JSON

    # Write metadata
    metadata = {
        "num_samples": num_samples,
        "tampering_ratio": tampering_ratio,
        "image_size": image_size
    }
    with open(output_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    return str(output_dir)
