import cv2
import torch
from pathlib import Path
from typing import List, Tuple


class DetectionResult:
    """Standard detection output for OCR / Donut / validators"""

    def __init__(self, label: str, confidence: float, bbox: Tuple[int, int, int, int]):
        self.label = label
        self.confidence = confidence
        self.bbox = bbox  

    def to_dict(self):
        return {
            "label": self.label,
            "confidence": round(self.confidence, 4),
            "bbox": {
                "x1": self.bbox[0],
                "y1": self.bbox[1],
                "x2": self.bbox[2],
                "y2": self.bbox[3],
            },
        }


class VisionDetector:
    """
    Production-grade YOLO detector for Amharic certificates
    Supports:
      - text_block
      - stamp
      - seal
      - signature
    """

    def __init__(
        self,
        model_path: str,
        conf_threshold: float = 0.4,
        device: str | None = None,
    ):
        self.model_path = Path(model_path)
        if not self.model_path.exists():
            raise FileNotFoundError(f"Model not found: {self.model_path}")

        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.conf_threshold = conf_threshold

        self.model = self._load_model()

    def _load_model(self):
        """Load YOLO model using Ultralytics (correct way)"""
        try:
            from ultralytics import YOLO
        except ImportError:
            raise RuntimeError("Install ultralytics: pip install ultralytics")

        model = YOLO(str(self.model_path))
        model.to(self.device)
        return model

    def detect(self, image_path: str) -> List[DetectionResult]:
        """Run detection on image"""
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Cannot read image: {image_path}")

        results = self.model(
            image,
            conf=self.conf_threshold,
            device=self.device,
            verbose=False,
        )

        return self._parse_results(results, image.shape)

    def _parse_results(self, results, img_shape) -> List[DetectionResult]:
        """Convert YOLO results to DetectionResult"""
        detections: List[DetectionResult] = []

        if not results or len(results[0].boxes) == 0:
            return detections

        boxes = results[0].boxes
        names = results[0].names  
        for box in boxes:
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
            conf = float(box.conf[0])
            cls_id = int(box.cls[0])
            label = names[cls_id]

            detections.append(
                DetectionResult(
                    label=label,
                    confidence=conf,
                    bbox=(x1, y1, x2, y2),
                )
            )

        return detections
