import torch
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from PIL import Image
import json
import logging
from pathlib import Path
from datetime import datetime
import os

# Use Auto classes instead of Donut-specific ones
from transformers import AutoProcessor, AutoModelForVision2Seq

logger = logging.getLogger(__name__)

class DonutCertificateParser:
    """Simplified Donut model for certificate parsing"""
    
    def __init__(self, model_path: Optional[str] = None):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"Initializing Donut parser on {self.device}")
        
        try:
            # Check if model path exists
            if model_path and os.path.exists(model_path):
                logger.info(f"Loading model from: {model_path}")
                
                # List files to debug
                files = os.listdir(model_path)
                logger.info(f"Available files: {files}")
                
                # Try to load with Auto classes (more flexible)
                try:
                    self.processor = AutoProcessor.from_pretrained(model_path)
                    self.model = AutoModelForVision2Seq.from_pretrained(model_path)
                    logger.info("Model loaded successfully with AutoProcessor")
                except Exception as e:
                    logger.warning(f"Auto loading failed: {e}. Trying manual approach...")
                    
                    # Fallback to specific Donut classes
                    from transformers import DonutProcessor, VisionEncoderDecoderModel
                    self.processor = DonutProcessor.from_pretrained(model_path)
                    self.model = VisionEncoderDecoderModel.from_pretrained(model_path)
                    
            else:
                logger.info("Model path not found or not specified. Using default model.")
                # Use default Donut model
                self.processor = AutoProcessor.from_pretrained("naver-clova-ix/donut-base")
                self.model = AutoModelForVision2Seq.from_pretrained("naver-clova-ix/donut-base")
            
            # Move to device
            self.model.to(self.device)
            self.model.eval()
            
            logger.info(f"Donut model ready on {self.device}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Donut parser: {e}")
            # Create a dummy processor/model to prevent crashes
            self.processor = None
            self.model = None
            raise
    
    def parse_certificate(self, image: Image.Image, language: str = "english") -> Dict[str, Any]:
        """Simple certificate parsing"""
        try:
            if self.processor is None or self.model is None:
                return {
                    "parsed_data": {},
                    "confidence": 0.0,
                    "error": "Model not loaded",
                    "success": False
                }
            
            # Convert image to RGB
            if image.mode != "RGB":
                image = image.convert("RGB")
            
            # Prepare input
            pixel_values = self.processor(images=image, return_tensors="pt").pixel_values
            pixel_values = pixel_values.to(self.device)
            
            # Prepare prompt (simplified)
            prompt = "<s_cord-v2>"
            decoder_input_ids = self.processor.tokenizer(
                prompt,
                add_special_tokens=False,
                return_tensors="pt"
            ).input_ids.to(self.device)
            
            # Generate
            with torch.no_grad():
                outputs = self.model.generate(
                    pixel_values,
                    decoder_input_ids=decoder_input_ids,
                    max_length=512,
                    pad_token_id=self.processor.tokenizer.pad_token_id,
                    eos_token_id=self.processor.tokenizer.eos_token_id,
                    use_cache=True,
                    num_beams=1,
                    early_stopping=True
                )
            
            # Decode
            decoded = self.processor.batch_decode(outputs)[0]
            decoded = decoded.replace(self.processor.tokenizer.eos_token, "")
            decoded = decoded.replace(self.processor.tokenizer.pad_token, "")
            
            # Try to extract JSON
            parsed_data = self._extract_json(decoded)
            
            return {
                "parsed_data": parsed_data,
                "confidence": 0.7,
                "model": "donut",
                "success": True,
                "raw_output": decoded[:200]  # First 200 chars for debugging
            }
            
        except Exception as e:
            logger.error(f"Parsing failed: {e}")
            return {
                "parsed_data": {},
                "confidence": 0.0,
                "error": str(e),
                "success": False
            }
    
    def _extract_json(self, text: str) -> Dict[str, Any]:
        """Extract JSON from text"""
        try:
            # Find JSON part
            start = text.find('{')
            end = text.rfind('}') + 1
            
            if start >= 0 and end > start:
                json_str = text[start:end]
                
                # Clean common issues
                json_str = json_str.replace('\n', ' ')
                json_str = json_str.replace('\\', '')
                
                # Try to parse
                return json.loads(json_str)
        except:
            pass
        
        # Return empty dict if parsing fails
        return {}
    
    def health_check(self) -> Dict[str, Any]:
        """Check if model is working"""
        return {
            "ready": self.processor is not None and self.model is not None,
            "device": str(self.device),
            "model_type": "AutoModelForVision2Seq" if self.model else "None",
            "processor_type": "AutoProcessor" if self.processor else "None"
        }
# import torch
# import numpy as np
# from typing import Dict, List, Optional, Tuple, Any
# from PIL import Image
# import json
# from transformers import DonutProcessor, VisionEncoderDecoderModel
# import logging
# from pathlib import Path
# from  datetime import datetime
# logger = logging.getLogger(__name__)

# class DonutCertificateParser:
#     """Donut model for structured certificate parsing"""
    
#     def __init__(self, model_path: Optional[str] = None, device: Optional[str] = None):
#         self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
#         logger.info(f"Loading Donut model on {self.device}")
        
#         try:
#             if model_path and Path(model_path).exists():
#                 # Load fine-tuned model
#                 self.processor = DonutProcessor.from_pretrained(model_path)
#                 self.model = VisionEncoderDecoderModel.from_pretrained(model_path)
#                 logger.info(f"Loaded fine-tuned model from {model_path}")
#             else:
#                 # Load base model
#                 self.processor = DonutProcessor.from_pretrained("naver-clova-ix/donut-base")
#                 self.model = VisionEncoderDecoderModel.from_pretrained("naver-clova-ix/donut-base")
#                 logger.info("Loaded base Donut model")
            
#             self.model.to(self.device)
#             self.model.eval()
            
#             # Certificate-specific configuration
#             self.prompt_templates = {
#                 "english": "<s_cord-v2>",
#                 "amharic": "<s_cord-v2>",
#                 "general": "<s_cord-v2>"
#             }
            
#             self.model_version = "2024.1.0-donut"
#             logger.info(f"Donut model loaded successfully on {self.device}")
            
#         except Exception as e:
#             logger.error(f"Failed to load Donut model: {e}")
#             raise
    
#     def preprocess_image(self, image: Image.Image, max_size: int = 2560) -> torch.Tensor:
#         """Preprocess image for Donut model"""
#         try:
#             # Convert to RGB if needed
#             if image.mode != 'RGB':
#                 image = image.convert('RGB')
            
#             # Resize while maintaining aspect ratio
#             w, h = image.size
            
#             if max(w, h) > max_size:
#                 scale = max_size / max(w, h)
#                 new_w, new_h = int(w * scale), int(h * scale)
#                 image = image.resize((new_w, new_h), Image.Resampling.LANCZOS)
            
#             # Process with Donut processor
#             pixel_values = self.processor(image, return_tensors="pt").pixel_values
#             return pixel_values.to(self.device)
            
#         except Exception as e:
#             logger.error(f"Image preprocessing failed: {e}")
#             raise
    
#     def parse_certificate(self, image: Image.Image, 
#                          language: str = "english") -> Dict[str, Any]:
#         """Parse certificate image to structured JSON"""
#         try:
#             # Preprocess image
#             pixel_values = self.preprocess_image(image)
            
#             # Prepare decoder input
#             prompt = self.prompt_templates.get(language, "<s_cord-v2>")
#             decoder_input_ids = self.processor.tokenizer(
#                 prompt, 
#                 add_special_tokens=False, 
#                 return_tensors="pt"
#             ).input_ids.to(self.device)
            
#             # Generate
#             with torch.no_grad():
#                 outputs = self.model.generate(
#                     pixel_values,
#                     decoder_input_ids=decoder_input_ids,
#                     max_length=512,
#                     early_stopping=True,
#                     pad_token_id=self.processor.tokenizer.pad_token_id,
#                     eos_token_id=self.processor.tokenizer.eos_token_id,
#                     use_cache=True,
#                     num_beams=3,
#                     bad_words_ids=[[self.processor.tokenizer.unk_token_id]],
#                     return_dict_in_generate=True,
#                     output_scores=True,
#                 )
            
#             # Decode sequence
#             sequence = self.processor.batch_decode(outputs.sequences)[0]
#             sequence = sequence.replace(self.processor.tokenizer.eos_token, "").replace(
#                 self.processor.tokenizer.pad_token, "")
#             sequence = sequence.replace(self.processor.tokenizer.bos_token, "")
            
#             # Parse JSON from sequence
#             parsed_data = self._extract_json_from_sequence(sequence)
            
#             # Calculate confidence from beam scores
#             confidence = self._calculate_confidence(outputs)
            
#             return {
#                 "parsed_data": parsed_data,
#                 "raw_sequence": sequence,
#                 "confidence": confidence,
#                 "model": "donut",
#                 "model_version": self.model_version,
#                 "language": language,
#                 "success": True,
#                 "timestamp": datetime.now().isoformat()
#             }
            
#         except Exception as e:
#             logger.error(f"Donut parsing failed: {e}")
#             return {
#                 "parsed_data": {},
#                 "error": str(e),
#                 "confidence": 0.0,
#                 "success": False
#             }
    
#     def _extract_json_from_sequence(self, sequence: str) -> Dict[str, Any]:
#         """Extract JSON from Donut output sequence"""
#         try:
#             # Find JSON part in sequence
#             start_idx = sequence.find("{")
#             end_idx = sequence.rfind("}") + 1
            
#             if start_idx != -1 and end_idx != -1:
#                 json_str = sequence[start_idx:end_idx]
                
#                 # Clean up JSON string
#                 json_str = self._clean_json_string(json_str)
                
#                 try:
#                     parsed = json.loads(json_str)
                    
#                     # Validate and normalize parsed data
#                     parsed = self._normalize_parsed_data(parsed)
#                     return parsed
                    
#                 except json.JSONDecodeError as e:
#                     logger.warning(f"JSON decode error: {e}, attempting repair")
#                     # Try to repair JSON
#                     json_str = self._repair_json_string(json_str)
#                     try:
#                         parsed = json.loads(json_str)
#                         parsed = self._normalize_parsed_data(parsed)
#                         return parsed
#                     except:
#                         # Fallback to key-value extraction
#                         return self._extract_key_value_pairs(sequence)
            
#             # No JSON found, extract key-value pairs
#             return self._extract_key_value_pairs(sequence)
            
#         except Exception as e:
#             logger.error(f"JSON extraction failed: {e}")
#             return {}
    
#     def _clean_json_string(self, json_str: str) -> str:
#         """Clean JSON string from common issues"""
#         # Remove trailing commas
#         import re
#         json_str = re.sub(r',\s*}', '}', json_str)
#         json_str = re.sub(r',\s*]', ']', json_str)
        
#         # Fix missing quotes
#         json_str = re.sub(r'(\w+):', r'"\1":', json_str)
        
#         # Fix single quotes
#         json_str = json_str.replace("'", '"')
        
#         return json_str
    
#     def _repair_json_string(self, json_str: str) -> str:
#         """Attempt to repair broken JSON"""
#         try:
#             # Simple repair: ensure it starts with { and ends with }
#             if not json_str.startswith("{"):
#                 json_str = "{" + json_str
#             if not json_str.endswith("}"):
#                 json_str = json_str + "}"
            
#             # Add missing quotes
#             import re
#             # Find unquoted keys and quote them
#             json_str = re.sub(r'([{,]\s*)(\w+)(\s*:)', r'\1"\2"\3', json_str)
            
#             return json_str
#         except:
#             return json_str
    
#     def _normalize_parsed_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
#         """Normalize parsed data to standard format"""
#         normalized = {}
        
#         # Common field mappings
#         field_mappings = {
#             'student_name': 'name',
#             'student_id': 'student_id',
#             'university_name': 'university',
#             'course_name': 'course',
#             'gpa_score': 'gpa',
#             'issue_date': 'issue_date',
#             'expiry_date': 'expiry_date',
#             'certificate_id': 'certificate_id'
#         }
        
#         for key, value in data.items():
#             if isinstance(value, (str, int, float)):
#                 # Map to standard field names
#                 mapped_key = field_mappings.get(key.lower().replace(' ', '_'), key)
#                 normalized[mapped_key] = str(value).strip()
        
#         return normalized
    
#     def _extract_key_value_pairs(self, text: str) -> Dict[str, str]:
#         """Extract key-value pairs from text (fallback)"""
#         pairs = {}
        
#         # Look for common patterns
#         patterns = [
#             r'"([^"]+)"\s*:\s*"([^"]+)"',  # JSON style
#             r'([A-Za-z\s]+)[:\-]\s*([^\n]+)',  # Label: value
#             r'([A-Za-z]+)\s+is\s+([^\n\.]+)',  # X is Y
#         ]
        
#         import re
#         for pattern in patterns:
#             matches = re.findall(pattern, text, re.IGNORECASE)
#             for key, value in matches:
#                 key = key.strip().lower().replace(' ', '_')
#                 value = value.strip()
#                 if key and value and len(value) > 1:
#                     pairs[key] = value
        
#         return pairs
    
#     def _calculate_confidence(self, outputs) -> float:
#         """Calculate confidence from beam search scores"""
#         try:
#             if hasattr(outputs, 'sequences_scores'):
#                 scores = outputs.sequences_scores.cpu().numpy()
#                 # Convert log probabilities to confidence
#                 confidence = np.exp(scores[0]) if len(scores) > 0 else 0.5
#                 return float(min(max(confidence, 0.0), 1.0))
#             else:
#                 return 0.7  # Default confidence
#         except:
#             return 0.5
    
#     async def batch_parse(self, images: List[Image.Image], 
#                         languages: List[str] = None) -> List[Dict[str, Any]]:
#         """Parse multiple certificates in batch"""
#         if languages is None:
#             languages = ["english"] * len(images)
        
#         results = []
#         for img, lang in zip(images, languages):
#             result = self.parse_certificate(img, lang)
#             results.append(result)
        
#         return results
    
#     def fine_tune(self, train_dataset, val_dataset, 
#                  output_dir: str = "models/donut_certificate"):
#         """Fine-tune Donut model on certificate data"""
#         from transformers import Seq2SeqTrainingArguments, Seq2SeqTrainer
        
#         logger.info(f"Starting fine-tuning, output directory: {output_dir}")
        
#         # Prepare datasets
#         from PIL import Image
#         import json
       
        
#         def prepare_dataset(batch):
#             import gzip
#             import os
#             import torch
            
#             pixel_values = []
#             labels = []
            
#             for item in batch:
#                 image = Image.open(item["image_path"]).convert("RGB")
#                 def is_gzipped(path):
#                    with open(path, 'rb') as f:
#                      return f.read(2) == b'\x1f\x8b'
#                 opener = gzip.open if is_gzipped(item["label_path"]) else open
#                 mode = 'rt' if opener == gzip.open else 'r'

#                 with opener(item["label_path"], mode, encoding='utf-8') as f:
#                     label_data = json.load(f)

#                 # ✅ Donut-required format
#                 text = f"<s_cord-v2>{json.dumps(label_data, ensure_ascii=False)}</s_cord-v2>"

#                 # if len(text.strip()) < 10:
#                 #     raise ValueError("Empty or invalid label text")
#                 pixel_values.append(self.processor(image, return_tensors="pt").pixel_values.squeeze())
#                 labels_batch = self.processor.tokenizer(
#                     text,
#                     max_length=512,
#                     padding="max_length",
#                     truncation=True,
#                     return_tensors="pt"
#                 ).input_ids.squeeze()
#                 #encoding = self.processor(
#                 #     image,
#                 #     text,
#                 #     max_length=512,
#                 #     padding="max_length",
#                 #     truncation=True,
#                 #     return_tensors="pt"
#                 # )
#                 # Replace pad_token_id with -100 for loss calculation
#                 #labels_batch = encoding.input_ids.squeeze().clone()
#                 labels_batch[labels_batch == self.processor.tokenizer.pad_token_id] = -100
#                 #pixel_values.append(encoding.pixel_values.squeeze())
#                 labels.append(labels_batch)
            

#             # with (gzip.open(item["label_path"], 'rt', encoding='utf-8') if is_gzipped(item["label_path"]) else open(item["label_path"], 'r', encoding='utf-8')) as f:
#             #    label_data = json.load(f) 
#             return {
#                 "pixel_values": torch.stack(pixel_values),
#                 "labels": torch.stack(labels)
#             }
        
        
        
#         # def prepare_dataset(batch):
#         #     pixel_values = []
#         #     text_labels = []
            
#         #     for item in batch:
#         #         # Convert image
#         #         pixel_values.append(self.processor(item["image"], return_tensors="pt").pixel_values)
                
#         #         # Convert JSON to string for Donut
#         #         json_str = json.dumps(item["label"], ensure_ascii=False)
#         #         text_labels.append(f"<s_cord-v2>{json_str}</s_cord-v2>")
            
#         #     # Tokenize labels
#         #     labels = self.processor.tokenizer(
#         #         text_labels, 
#         #         padding=True, 
#         #         return_tensors="pt"
#         #     )
            
#         #     return {
#         #         "pixel_values": torch.stack(pixel_values),
#         #         "labels": labels["input_ids"]
#         #     }
        
#         # Training arguments
#         training_args = Seq2SeqTrainingArguments(
#             output_dir=output_dir,
#             num_train_epochs=10,
#             learning_rate=2e-5,
#             per_device_train_batch_size=2,
#             per_device_eval_batch_size=2,
#             warmup_steps=100,
#             weight_decay=0.01,
#             logging_dir=f"{output_dir}/logs",
#             logging_steps=50,
#             save_steps=500,
#             eval_steps=500,
#             evaluation_strategy="steps",  
#             save_strategy="steps",
#             save_total_limit=3,
#             load_best_model_at_end=False,
#             metric_for_best_model="eval_loss",
#             predict_with_generate=True,
#             fp16=torch.cuda.is_available(),
#             remove_unused_columns=False,
#             dataloader_num_workers=0,
#             report_to="none"  # Disable wandb/tensorboard
#         )
#         from datasets import Dataset
#         train_dataset = Dataset.from_list(train_dataset)
#         val_dataset = Dataset.from_list(val_dataset)

#         # Trainer
#         trainer = Seq2SeqTrainer(
#             model=self.model,
#             args=training_args,
#             train_dataset=train_dataset,
#             eval_dataset=val_dataset,
#             data_collator=lambda x: prepare_dataset(x),
#         )
        
#         # Train
#         logger.info("Starting training...")
#         train_result = trainer.train()
        
#         # Save
#         trainer.save_model(output_dir)
#         self.processor.save_pretrained(output_dir)
        
#         logger.info(f"Model fine-tuned and saved to {output_dir}")
#         logger.info(f"Training results: {train_result.metrics}")
        
#         return train_result
    
#     def save_model(self, output_path: str):
#         """Save model to disk"""
#         self.model.save_pretrained(output_path)
#         self.processor.save_pretrained(output_path)
#         logger.info(f"Model saved to {output_path}")
    
#     def load_model(self, model_path: str):
#         """Load model from disk"""
#         self.processor = DonutProcessor.from_pretrained(model_path)
#         self.model = VisionEncoderDecoderModel.from_pretrained(model_path)
#         self.model.to(self.device)
#         #self.model.
#         # ()
#         logger.info(f"Model loaded from {model_path}")