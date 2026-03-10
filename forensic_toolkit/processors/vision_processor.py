"""
Vision processing module - object detection, OCR, and AI captioning.
"""
import os
import sys
import json
import csv
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from html import escape

# Import vision modules with error handling
try:
    import torch
    from transformers import VisionEncoderDecoderModel, ViTImageProcessor, AutoTokenizer
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False

try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

# Configuration
YOLO_MODEL = "yolov8n.pt"
DETECT_CONF_THRESH = 0.25
LOW_CONF = 0.25

SUSPECT_LABELS = {"book", "frisbee", "refrigerator", "cell phone", "mobile phone", 
                  "tv", "laptop", "keyboard", "remote"}

METER_TOKENS = [
    "kwh", "kw h", "rev/kwh", "imp/kwh", "eskom", "conlog", "landis", "gyr", "voltex", 
    "gec", "kamstrup", "hexing", "sts", "dlms", "class 1", "230v", "220/240v", "220v", 
    "240v", "50hz", "10(100)a", "20(80)a", "5(80)a", "serial", "s/n"
]
NUM_TOKEN = re.compile(r"(?:\d[\d\s\.\-]{2,}\d)")

class VisionProcessor:
    """Handles object detection, OCR, and AI captioning for images."""
    
    def __init__(self, device: str = "auto", yolo_model: str = YOLO_MODEL, 
                 caption_model: str = "nlpconnect/vit-gpt2-image-captioning",
                 max_tokens: int = 40, fail_fast: bool = False):
        self.device = self._detect_device(device)
        self.yolo_model_name = yolo_model
        self.caption_model_name = caption_model
        self.max_tokens = max_tokens
        self.fail_fast = fail_fast
        
        # Lazy loading of models
        self.yolo = None
        self.captioner = None
        self.processor = None
        self.tokenizer = None
        self.model = None
        self.model_loaded = False
        
        # Try to load captioner (required for captions)
        if TRANSFORMERS_AVAILABLE:
            try:
                self._load_captioner()
            except Exception as e:
                if self.fail_fast:
                    raise RuntimeError(f"Failed to load caption model: {e}")
                print(f"⚠ WARNING: Caption model failed to load: {e}")
        else:
            print("⚠ WARNING: transformers not installed. Captions will be unavailable.")
        
        # Load YOLO if available
        if YOLO_AVAILABLE:
            try:
                self._load_yolo()
            except Exception as e:
                print(f"⚠ WARNING: YOLO failed to load: {e}")
        else:
            print("⚠ WARNING: ultralytics not installed. Object detection will be unavailable.")
    
    def _detect_device(self, device: str) -> str:
        if device == "auto":
            import torch
            return "cuda" if torch.cuda.is_available() else "cpu"
        return device
    
    def _load_yolo(self):
        """Load YOLO model."""
        print(f"Loading YOLO: {self.yolo_model_name}")
        self.yolo = YOLO(self.yolo_model_name)
        if torch.cuda.is_available():
            self.yolo.to("cuda")
            print(f"  ✓ YOLO on GPU")
        else:
            print(f"  ✓ YOLO on CPU")
    
    def _load_captioner(self):
        """Load vision-language captioning model."""
        print(f"\n{'='*60}")
        print("LOADING VISION-TO-TEXT MODEL")
        print(f"{'='*60}")
        print(f"Model: {self.caption_model_name}")
        
        try:
            cache_dir = os.path.expanduser('~/.cache/huggingface/hub')
            os.environ['HF_HOME'] = os.path.expanduser('~/.cache/huggingface')
            os.environ['TRANSFORMERS_CACHE'] = cache_dir
            
            print(f"Cache directory: {cache_dir}\n")
            
            print("[1/3] Loading image processor...")
            self.processor = ViTImageProcessor.from_pretrained(
                self.caption_model_name,
                cache_dir=cache_dir,
                resume_download=True
            )
            print("      ✓ Processor ready\n")
            
            print("[2/3] Loading tokenizer...")
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.caption_model_name,
                cache_dir=cache_dir,
                resume_download=True
            )
            print("      ✓ Tokenizer ready\n")
            
            print("[3/3] Loading vision model...")
            self.model = VisionEncoderDecoderModel.from_pretrained(
                self.caption_model_name,
                cache_dir=cache_dir,
                resume_download=True
            )
            print("      ✓ Model ready\n")
            
            self.model = self.model.to(self.device)
            self.model.eval()
            self.model_loaded = True
            
            print(f"{'='*60}")
            print("✓ Vision model loaded successfully")
            print(f"{'='*60}\n")
            
        except Exception as e:
            print(f"✗ Failed to load vision model: {e}")
            if self.fail_fast:
                raise
            self.model_loaded = False
    
    def detect_objects(self, image: Image.Image, conf: float = DETECT_CONF_THRESH) -> List[Dict[str, Any]]:
        """Run YOLO object detection on an image."""
        if not YOLO_AVAILABLE or not self.yolo:
            return []
        
        try:
            arr = np.array(image.convert("RGB"))
            results = self.yolo.predict(arr, conf=conf, verbose=False)
            
            if not results:
                return []
            
            detections = []
            r0 = results[0]
            names = r0.names
            
            for b in r0.boxes:
                cls = int(b.cls.cpu().numpy().item())
                score = float(b.conf.cpu().numpy().item())
                xyxy = b.xyxy.cpu().numpy().astype(float).ravel().tolist()
                detections.append({
                    "label": names.get(cls, str(cls)),
                    "confidence": score,
                    "bbox": xyxy
                })
            
            return detections
            
        except Exception as e:
            print(f"  [WARNING] Object detection failed: {e}")
            return []
    
    def extract_ocr(self, image: Image.Image) -> str:
        """Extract text using Tesseract OCR."""
        if not TESSERACT_AVAILABLE:
            return ""
        
        try:
            if image.mode != "RGB":
                image = image.convert("RGB")
            text = pytesseract.image_to_string(image, lang="eng", config="--oem 3 --psm 6")
            return text.strip()
        except Exception as e:
            print(f"  [WARNING] OCR failed: {e}")
            return ""
    
    def generate_caption(self, image: Image.Image) -> str:
        """Generate AI caption for an image."""
        if not self.model_loaded:
            return ""
        
        try:
            if image.mode != "RGB":
                image = image.convert("RGB")
            
            # Ensure minimum size
            w, h = image.size
            if w < 32 or h < 32:
                scale = max(32.0 / w, 32.0 / h)
                new_w, new_h = int(w * scale), int(h * scale)
                image = image.resize((new_w, new_h), Image.Resampling.LANCZOS)
            
            with torch.no_grad():
                pixel_values = self.processor(images=image, return_tensors="pt").pixel_values
                pixel_values = pixel_values.to(self.device)
                
                output_ids = self.model.generate(
                    pixel_values=pixel_values,
                    max_length=self.max_tokens,
                    num_beams=4,
                    early_stopping=True,
                    no_repeat_ngram_size=2,
                    length_penalty=1.0
                )
                
                caption = self.tokenizer.decode(output_ids[0], skip_special_tokens=True).strip()
                
                if caption and len(caption.split()) >= 3:
                    return caption[0].upper() + caption[1:] if caption else caption
                return ""
                
        except Exception as e:
            print(f"  [WARNING] Caption generation failed: {e}")
            return ""
    
    def detect_meter_shape(self, image: Image.Image) -> float:
        """Detect if image contains electricity meter shape."""
        if not CV2_AVAILABLE:
            return 0.0
        
        try:
            import cv2
            img = np.array(image.convert("RGB"))
            gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
            
            # Adaptive threshold to find text/display areas
            thr = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                                       cv2.THRESH_BINARY_INV, 21, 7)
            
            # Look for rectangular display areas
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 2))
            morph = cv2.morphologyEx(thr, cv2.MORPH_CLOSE, kernel, iterations=2)
            
            contours, _ = cv2.findContours(morph, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            H = gray.shape[0]
            windows = 0
            for c in contours:
                x, y, w, h = cv2.boundingRect(c)
                if w * h < 300 or w < 30 or h < 10:
                    continue
                aspect = w / max(h, 1)
                if 3.0 <= aspect <= 12.0 and h < 0.2 * H:
                    windows += 1
            
            # Look for circular dials
            median = cv2.medianBlur(gray, 5)
            circles = cv2.HoughCircles(median, cv2.HOUGH_GRADIENT, dp=1.2, minDist=40,
                                      param1=120, param2=30, minRadius=14, maxRadius=80)
            
            dials = 0 if circles is None else circles.shape[1]
            
            # Calculate score
            score = min(windows * 0.22, 0.66) + min(dials * 0.18, 0.54)
            return max(0.0, min(score, 1.0))
            
        except Exception as e:
            print(f"  [WARNING] Meter shape detection failed: {e}")
            return 0.0
    
    def extract_ocr_snippets(self, text: str) -> Dict[str, str]:
        """Extract key information from OCR text."""
        result = {"numbers": "", "brand": "", "specs": ""}
        
        if not text:
            return result
        
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        
        # Extract brand names
        brands = ["landis", "gyr", "eskom", "conlog", "kamstrup", "hexing", "voltex", "gec"]
        for line in lines:
            for brand in brands:
                if brand in line.lower():
                    result["brand"] = line[:50]
                    break
            if result["brand"]:
                break
        
        # Extract numbers
        num_matches = NUM_TOKEN.findall(text)
        if num_matches:
            result["numbers"] = ", ".join(num_matches[:3])
        
        # Extract specs (voltage, current, frequency)
        spec_patterns = [r'\d+\s*[vV]', r'\d+\s*[kK][wW][hH]?', r'\d+\s*[aA]', r'\d+\s*[hH][zZ]']
        specs = []
        for pattern in spec_patterns:
            matches = re.findall(pattern, text)
            specs.extend(matches[:2])
        if specs:
            result["specs"] = ", ".join(specs[:3])
        
        return result
    
    def draw_detections(self, image: Image.Image, detections: List[Dict[str, Any]]) -> Image.Image:
        """Draw bounding boxes and labels on image."""
        img = image.convert("RGB").copy()
        draw = ImageDraw.Draw(img)
        
        try:
            font = ImageFont.truetype("arial.ttf", 18)
        except:
            font = ImageFont.load_default()
        
        def text_size(draw, text, font):
            try:
                bbox = draw.textbbox((0, 0), text, font=font)
                return (bbox[2] - bbox[0], bbox[3] - bbox[1])
            except:
                return (len(text) * 8, 18)
        
        for det in detections:
            x1, y1, x2, y2 = [int(v) for v in det["bbox"]]
            label = f"{det['label']} {det['confidence']:.2f}"
            
            # Draw bounding box
            draw.rectangle([x1, y1, x2, y2], outline=(36, 131, 255), width=3)
            
            # Draw label background
            tw, th = text_size(draw, label, font)
            draw.rectangle([x1, y1 - th - 4, x1 + tw + 6, y1], fill=(36, 131, 255))
            
            # Draw label text
            draw.text((x1 + 3, y1 - th - 2), label, fill=(255, 255, 255), font=font)
        
        return img
    
    def process_image(self, image_path: Path, output_dir: Path) -> Dict[str, Any]:
        """Process a single image and return results."""
        result = {
            "file": str(image_path),
            "status": "pending",
            "detections": [],
            "ocr_text": "",
            "caption": "",
            "caption_status": "FAILED",
            "identifier": "[none]",
            "confidence": 0.0,
            "output_files": {}
        }
        
        try:
            # Load image
            img = Image.open(image_path)
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGB")
            w, h = img.size
            
            # Object detection
            detections = self.detect_objects(img)
            result["detections"] = detections
            
            # Get best detection
            if detections:
                best = max(detections, key=lambda d: d["confidence"])
                top_label = best["label"]
                top_conf = best["confidence"]
                top_box = best["bbox"]
            else:
                top_label, top_conf, top_box = "[none]", 0.0, [5, 5, w-5, h-5]
            
            # OCR
            ocr_text = self.extract_ocr(img)
            result["ocr_text"] = ocr_text
            
            # Meter detection
            meter_hits = sum(1 for token in METER_TOKENS if token in ocr_text.lower())
            meter_shape = self.detect_meter_shape(img)
            meter_score = min(1.0, meter_hits/3.0*0.7 + meter_shape*0.3)
            
            # Override detection if meter is likely
            if meter_score >= 0.6 and (top_label in SUSPECT_LABELS or top_label == "[none]" or top_conf < LOW_CONF):
                top_label = "digital_electricity_meter" if meter_shape >= 0.35 else "electricity_meter"
                top_conf = max(0.60, meter_score)
            
            result["identifier"] = top_label
            result["confidence"] = top_conf
            
            # Generate caption
            if self.model_loaded:
                # Crop to detection for better caption
                if detections:
                    x1, y1, x2, y2 = [int(v) for v in top_box]
                    x1, y1 = max(0, x1), max(0, y1)
                    x2, y2 = min(w-1, x2), min(h-1, y2)
                    crop = img.crop((x1, y1, x2, y2))
                    caption = self.generate_caption(crop)
                else:
                    caption = self.generate_caption(img)
                
                if caption:
                    result["caption"] = caption
                    result["caption_status"] = "SUCCESS"
            
            # Save outputs
            
            # Annotated image
            ann_img = self.draw_detections(img, detections if detections else [{
                "label": top_label, "confidence": top_conf, "bbox": top_box
            }])
            ann_path = output_dir / "annotated" / image_path.name
            ann_path.parent.mkdir(exist_ok=True)
            ann_img.save(ann_path, "JPEG", quality=92)
            result["output_files"]["annotated"] = str(ann_path)
            
            # JSON metadata
            ocr_snippets = self.extract_ocr_snippets(ocr_text)
            json_path = output_dir / "json" / f"{image_path.stem}.json"
            json_path.parent.mkdir(exist_ok=True)
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump({
                    "file": str(image_path),
                    "caption": result["caption"],
                    "caption_status": result["caption_status"],
                    "ocr_text": ocr_text,
                    "ocr_structured": ocr_snippets,
                    "detections": detections,
                    "identifier": top_label,
                    "confidence": round(top_conf, 4),
                    "width": w,
                    "height": h
                }, f, indent=2, ensure_ascii=False)
            result["output_files"]["json"] = str(json_path)
            
            result["status"] = "success"
            
        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)
        
        return result

def process_vision_files(file_paths: List[str], output_dir: str, 
                        device: str = "auto", yolo_model: str = YOLO_MODEL,
                        fail_fast: bool = False, quiet: bool = False) -> Dict[str, Any]:
    """
    Process multiple image files with vision analysis.
    
    Args:
        file_paths: List of image file paths
        output_dir: Output directory for results
        device: Device to use ('auto', 'cpu', 'cuda')
        yolo_model: YOLO model name
        fail_fast: Exit if model fails to load
        quiet: Reduce console output
    
    Returns:
        Dictionary with processing results
    """
    def logprint(msg: str):
        if not quiet:
            print(msg, flush=True)
    
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "annotated").mkdir(exist_ok=True)
    (out_dir / "json").mkdir(exist_ok=True)
    
    # Initialize processor
    try:
        processor = VisionProcessor(
            device=device,
            yolo_model=yolo_model,
            fail_fast=fail_fast
        )
    except Exception as e:
        logprint(f"ERROR: Failed to initialize vision processor: {e}")
        if fail_fast:
            raise
        processor = None
    
    results = []
    failed_captions = 0
    
    logprint(f"\n{'='*60}")
    logprint(f"PROCESSING {len(file_paths)} IMAGES")
    logprint(f"{'='*60}\n")
    
    for i, file_path in enumerate(file_paths, 1):
        logprint(f"[{i}/{len(file_paths)}] Processing: {Path(file_path).name}")
        
        if processor:
            result = processor.process_image(Path(file_path), out_dir)
        else:
            # Minimal processing without AI models
            result = {
                "file": file_path,
                "status": "failed",
                "error": "Vision processor not initialized"
            }
        
        results.append(result)
        
        if result["status"] == "success":
            status = "✓" if result["caption_status"] == "SUCCESS" else "✗"
            cap_preview = result["caption"][:60] if result["caption"] else "NO CAPTION"
            logprint(f"  {status} {cap_preview}")
            
            if result["caption_status"] != "SUCCESS":
                failed_captions += 1
        else:
            logprint(f"  ✗ Failed: {result.get('error', 'Unknown error')}")
            failed_captions += 1
    
    # Generate reports
    
    # CSV index
    csv_path = out_dir / "index.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["file", "identifier", "confidence", "caption", "caption_status", 
                        "ocr_chars", "json_path", "annotated_path"])
        
        for r in results:
            if r["status"] == "success":
                writer.writerow([
                    r["file"],
                    r["identifier"],
                    f"{r['confidence']:.4f}",
                    r["caption"],
                    r["caption_status"],
                    len(r.get("ocr_text", "")),
                    r["output_files"].get("json", ""),
                    r["output_files"].get("annotated", "")
                ])
    
    # HTML report
    html_rows = []
    for r in results:
        if r["status"] == "success":
            html_rows.append({
                "file": r["file"],
                "label_top": r["identifier"],
                "conf_top": r["confidence"],
                "caption": r["caption"],
                "ocr_text": r.get("ocr_text", ""),
                "annotated_path": r["output_files"].get("annotated", "")
            })
    
    html_path = out_dir / "results.html"
    _write_html_report(html_rows, html_path, failed_captions)
    
    # Summary report
    report = {
        "model": {
            "yolo": yolo_model,
            "caption": "nlpconnect/vit-gpt2-image-captioning" if processor and processor.model_loaded else None
        },
        "total_files": len(results),
        "successful": sum(1 for r in results if r["status"] == "success"),
        "failed": sum(1 for r in results if r["status"] == "failed"),
        "captions_success": sum(1 for r in results if r.get("caption_status") == "SUCCESS"),
        "captions_failed": failed_captions,
        "results": results
    }
    
    with open(out_dir / "_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    logprint(f"\n{'='*60}")
    logprint(f"COMPLETE: {report['successful']}/{report['total_files']} images | "
             f"{report['captions_success']} captions ✓ | {report['captions_failed']} ✗")
    logprint(f"Results: {html_path}")
    logprint(f"{'='*60}\n")
    
    return report

def _write_html_report(rows: List[Dict[str, Any]], html_path: Path, failed_count: int):
    """Write HTML report with results."""
    tr = []
    for i, r in enumerate(rows, start=1):
        what = escape(str(r.get("label_top", "[none]")))
        conf = float(r.get("conf_top", 0.0))
        cap = str(r.get("caption", "") or "")
        
        if not cap:
            cap_html = '<span style="color:#dc2626;font-weight:bold;">⚠ CAPTION FAILED</span>'
        else:
            cap_html = escape(cap)
        
        ocr_preview = escape(str(r.get("ocr_text", "") or "")[:100])
        path = str(r.get("file", ""))
        ann = str(r.get("annotated_path", ""))
        ann_rel = escape(os.path.relpath(ann, os.path.dirname(str(html_path)))) if ann else ""
        img_tag = f'<a href="{escape(ann)}" target="_blank"><img src="{ann_rel}" alt="thumb" /></a>' if ann else ""
        
        ocr_cell = (f'<div class="ocr-preview">{ocr_preview}{"..." if len(str(r.get("ocr_text", ""))) > 100 else ""}</div>' 
                   if ocr_preview else '<span class="muted">no text</span>')
        
        tr.append(f'''
<tr>
    <td class="idx">{i}</td>
    <td class="what"><b>{what}</b><br><span class="muted">conf {conf:.2f}</span></td>
    <td class="cap">{cap_html}</td>
    <td class="ocr">{ocr_cell}</td>
    <td class="file">{escape(os.path.basename(path))}</td>
    <td class="pic">{img_tag}</td>
</tr>''')
    
    status_color = "#dc2626" if failed_count > 0 else "#16a34a"
    status_msg = f"{failed_count} caption(s) failed" if failed_count > 0 else "All captions generated successfully"
    
    html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Image Analysis Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 24px; background: #fafafa; color: #111; }}
        h1 {{ color: #111827; }}
        .card {{ background: #fff; border: 1px solid #e5e7eb; border-radius: 14px; padding: 16px; margin: 12px 0; }}
        .status {{ background: #fef2f2; border-left: 4px solid {status_color}; padding: 12px; margin: 12px 0; border-radius: 8px; }}
        .status strong {{ color: {status_color}; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
        th {{ text-align: left; padding: 10px; border-bottom: 2px solid #e5e7eb; background: #f8fafc; }}
        td {{ padding: 12px 10px; border-bottom: 1px solid #e5e7eb; vertical-align: top; }}
        td.pic img {{ max-width: 320px; max-height: 240px; border-radius: 8px; }}
        td.ocr {{ max-width: 200px; font-size: 12px; font-family: monospace; }}
        .ocr-preview {{ background: #f9fafb; padding: 6px; border-radius: 4px; color: #374151; }}
        .muted {{ color: #6b7280; font-size: 12px; }}
        .idx {{ font-weight: bold; color: #6b7280; }}
        .what {{ font-weight: 500; }}
    </style>
</head>
<body>
    <h1>Image Analysis Report</h1>
    <div class="status"><strong>Status:</strong> {status_msg}</div>
    <div class="card">
        <table>
            <thead>
                <tr>
                    <th>No</th>
                    <th>Detection</th>
                    <th>AI Caption</th>
                    <th>OCR Text</th>
                    <th>File</th>
                    <th>Preview</th>
                </tr>
            </thead>
            <tbody>
                {''.join(tr)}
            </tbody>
        </table>
    </div>
</body>
</html>'''
    
    html_path.write_text(html, encoding="utf-8")