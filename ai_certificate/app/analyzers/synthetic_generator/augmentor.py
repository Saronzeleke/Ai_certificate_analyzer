import numpy as np
import cv2
from PIL import Image
import random
from typing import List
import logging

logger = logging.getLogger(__name__)

class CertificateAugmentor:
    """Apply realistic augmentations to certificates"""

    def __init__(self):
        self.augmentation_config = {
            "noise": {"min": 0.0, "max": 0.3, "weight": 0.7},
            "blur": {"min": 0.0, "max": 0.3, "weight": 0.5},
            "brightness": {"min": -0.2, "max": 0.2, "weight": 0.8},
            "contrast": {"min": 0.8, "max": 1.2, "weight": 0.6},
            "rotation": {"min": -2.0, "max": 2.0, "weight": 0.4},
            "perspective": {"min": 0.0, "max": 0.05, "weight": 0.3},
            "compression": {"min": 75, "max": 95, "weight": 0.9},
            "texture": {"weight": 0.5},
            "shadows": {"weight": 0.2},
            "folds": {"weight": 0.1}
        }

    def augment_image(self, image: Image.Image, intensity: float = 0.5) -> Image.Image:
        """Apply augmentations to image based on intensity"""
        img_np = np.array(image)
        h, w = img_np.shape[:2]
        augmentations = []

        # 1. Rotation
        if random.random() < self.augmentation_config["rotation"]["weight"] * intensity:
            angle = random.uniform(-1.5, 1.5)
            img_np = self._apply_rotation(img_np, angle)
            augmentations.append(f"rotation:{angle:.1f}")

        # 2. Perspective distortion
        if random.random() < self.augmentation_config["perspective"]["weight"] * intensity:
            max_offset = int(min(h, w) * 0.02 * intensity)
            img_np = self._apply_perspective(img_np, max_offset)
            augmentations.append("perspective")

        # 3. Brightness
        if random.random() < self.augmentation_config["brightness"]["weight"] * intensity:
            delta = random.uniform(-0.15, 0.15)
            img_np = self._adjust_brightness(img_np, delta)
            augmentations.append(f"brightness:{delta:.2f}")

        # 4. Contrast
        if random.random() < self.augmentation_config["contrast"]["weight"] * intensity:
            alpha = random.uniform(0.9, 1.1)
            beta = random.uniform(-10, 10)
            img_np = cv2.convertScaleAbs(img_np, alpha=alpha, beta=beta)
            augmentations.append(f"contrast:{alpha:.2f}")

        # 5. Noise
        if random.random() < self.augmentation_config["noise"]["weight"] * intensity:
            noise_level = random.uniform(0.05, 0.2) * intensity
            img_np = self._add_noise(img_np, noise_level)
            augmentations.append(f"noise:{noise_level:.2f}")

        # 6. Blur
        if random.random() < self.augmentation_config["blur"]["weight"] * intensity:
            blur_level = random.uniform(0.1, 0.3) * intensity
            img_np = self._apply_blur(img_np, blur_level)
            augmentations.append(f"blur:{blur_level:.2f}")

        # 7. Paper texture
        if random.random() < self.augmentation_config["texture"]["weight"] * intensity:
            img_np = self._add_paper_texture(img_np, intensity)
            augmentations.append("texture")

        # 8. Shadows
        if random.random() < self.augmentation_config["shadows"]["weight"] * intensity * 0.5:
            img_np = self._add_shadow(img_np)
            augmentations.append("shadow")

        # 9. Compression
        if random.random() < self.augmentation_config["compression"]["weight"] * intensity:
            quality = random.randint(80, 92)
            img_np = self._apply_compression(img_np, quality)
            augmentations.append(f"compression:{quality}")

        logger.debug(f"Applied augmentations: {augmentations}")
        return Image.fromarray(img_np)

    # ---------------- Helper methods ---------------- #

    def _apply_rotation(self, image: np.ndarray, angle: float) -> np.ndarray:
        h, w = image.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        return cv2.warpAffine(image, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)

    def _apply_perspective(self, image: np.ndarray, max_offset: int) -> np.ndarray:
        h, w = image.shape[:2]
        src = np.float32([[0,0],[w,0],[0,h],[w,h]])
        dst = src + np.random.uniform(-max_offset, max_offset, src.shape).astype(np.float32)
        dst = np.clip(dst, 0, [w, h])
        M = cv2.getPerspectiveTransform(src, dst)
        return cv2.warpPerspective(image, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)

    def _adjust_brightness(self, image: np.ndarray, delta: float) -> np.ndarray:
        delta_int = int(delta * 255)
        if len(image.shape) == 3:
            hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
            hsv[:, :, 2] = np.clip(hsv[:, :, 2] + delta_int, 0, 255)
            return cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)
        else:
            return np.clip(image + delta_int, 0, 255).astype(np.uint8)

    def _add_noise(self, image: np.ndarray, intensity: float) -> np.ndarray:
        noise_type = random.choice(["gaussian", "salt_pepper", "speckle"])
        noisy = image.copy()
        h, w = image.shape[:2]

        if noise_type == "gaussian":
            noise = np.random.normal(0, intensity * 25, image.shape)
            return np.clip(image.astype(np.float32) + noise, 0, 255).astype(np.uint8)

        elif noise_type == "salt_pepper":
            num_salt = int(np.ceil(intensity * 0.025 * image.size))
            coords = (np.random.randint(0, h, num_salt), np.random.randint(0, w, num_salt))
            if len(image.shape) == 3:
                noisy[coords[0], coords[1], :] = 255
            else:
                noisy[coords[0], coords[1]] = 255

            num_pepper = int(np.ceil(intensity * 0.025 * image.size))
            coords = (np.random.randint(0, h, num_pepper), np.random.randint(0, w, num_pepper))
            if len(image.shape) == 3:
                noisy[coords[0], coords[1], :] = 0
            else:
                noisy[coords[0], coords[1]] = 0

            return noisy

        else:  # speckle
            noise = np.random.randn(*image.shape) * intensity * 0.5
            return np.clip(image + image * noise, 0, 255).astype(np.uint8)

    def _apply_blur(self, image: np.ndarray, intensity: float) -> np.ndarray:
        ksize = int(3 + intensity * 4)
        ksize += 1 if ksize % 2 == 0 else 0
        blur_type = random.choice(["gaussian", "median", "bilateral"])
        if blur_type == "gaussian":
            return cv2.GaussianBlur(image, (ksize, ksize), 0)
        elif blur_type == "median":
            return cv2.medianBlur(image, ksize)
        else:
            return cv2.bilateralFilter(image, ksize, 75, 75)

    def _add_paper_texture(self, image: np.ndarray, intensity: float) -> np.ndarray:
        h, w = image.shape[:2]
        texture = np.random.normal(128, 10, (h, w, 3) if len(image.shape) == 3 else (h, w))
        grain = np.random.normal(0, intensity * 5, texture.shape)
        texture = np.clip(texture + grain, 0, 255).astype(np.uint8)
        alpha = 0.05 * intensity
        return cv2.addWeighted(image, 1 - alpha, texture, alpha, 0)

    def _add_shadow(self, image: np.ndarray) -> np.ndarray:
        h, w = image.shape[:2]
        shadow = np.ones((h, w), dtype=np.float32)
        direction = random.choice(["top", "bottom", "left", "right", "corner"])
        for i in range(h):
            for j in range(w):
                if direction == "top":
                    shadow[i, j] = 1.0 - (i/h)*0.3
                elif direction == "bottom":
                    shadow[i, j] = 0.7 + (i/h)*0.3
                elif direction == "left":
                    shadow[i, j] = 1.0 - (j/w)*0.3
                elif direction == "right":
                    shadow[i, j] = 0.7 + (j/w)*0.3
                else:  # corner
                    distance = np.sqrt((i/h)**2 + (j/w)**2)/np.sqrt(2)
                    shadow[i, j] = 0.8 + distance * 0.2
        if len(image.shape) == 3:
            shadow = shadow[:, :, np.newaxis]
        return np.clip(image.astype(np.float32) * shadow, 0, 255).astype(np.uint8)

    def _apply_compression(self, image: np.ndarray, quality: int) -> np.ndarray:
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
        result, encimg = cv2.imencode('.jpg', image, encode_param)
        if result:
            decimg = cv2.imdecode(encimg, 1)
            if len(decimg.shape) == 3 and image.shape[2] == 3:
                decimg = cv2.cvtColor(decimg, cv2.COLOR_BGR2RGB)
            return decimg
        return image

    def apply_fold_effect(self, image: Image.Image, intensity: float = 0.5) -> Image.Image:
        """Apply fold effect with optional intensity control"""
        if random.random() < self.augmentation_config["folds"]["weight"] * intensity:
            img_np = np.array(image)
            h, w = img_np.shape[:2]
            fold_type = random.choice(["horizontal", "vertical", "diagonal"])
            if fold_type == "horizontal":
                fold_y = random.randint(h//3, 2*h//3)
                for i in range(max(0, fold_y-10), min(h, fold_y+10)):
                    alpha = 1.0 - abs(fold_y-i)/10
                    img_np[i, :] = np.clip(img_np[i, :] * (0.7 + 0.3*alpha), 0, 255)
            elif fold_type == "vertical":
                fold_x = random.randint(w//3, 2*w//3)
                for j in range(max(0, fold_x-10), min(w, fold_x+10)):
                    alpha = 1.0 - abs(fold_x-j)/10
                    img_np[:, j] = np.clip(img_np[:, j] * (0.7 + 0.3*alpha), 0, 255)
            image = Image.fromarray(img_np.astype(np.uint8))
        return image

    def augment_for_training(self, image: Image.Image, augmentations_per_image: int = 3) -> List[Image.Image]:
        augmented_images = [image]
        for _ in range(augmentations_per_image):
            intensity = random.uniform(0.3, 0.8)
            augmented_images.append(self.augment_image(image.copy(), intensity))
        return augmented_images
