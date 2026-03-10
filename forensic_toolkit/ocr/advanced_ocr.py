"""
Advanced OCR module with comprehensive image preprocessing.
Handles skewed documents, poor quality scans, and multiple formats.
"""
import os
import cv2
import numpy as np
from PIL import Image
import pytesseract
from pdf2image import convert_from_path
from typing import List, Optional, Tuple, Dict, Any, Union
from pathlib import Path
import json
import csv
from dataclasses import dataclass, asdict
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class OCRResult:
    """OCR processing result for a single document/page."""
    file_path: str
    page_number: int
    text: str
    confidence: float
    language: str
    preprocessing_steps: List[str]
    processing_time: float
    word_count: int
    layout_blocks: List[Dict[str, Any]]
    image_dimensions: Tuple[int, int]


class AdvancedOCR:
    """
    Advanced OCR engine with comprehensive preprocessing.
    Handles skewed documents, poor quality, and multiple formats.
    """
    
    def __init__(self, tesseract_cmd: Optional[str] = None, 
                 languages: str = 'eng',
                 config: str = '--oem 3 --psm 3'):
        """
        Initialize OCR engine.
        
        Args:
            tesseract_cmd: Path to tesseract executable
            languages: Tesseract language codes (e.g., 'eng+afr')
            config: Tesseract configuration string
        """
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
        
        self.languages = languages
        self.base_config = config
        self.supported_formats = {'.jpg', '.jpeg', '.png', '.bmp', '.tif', 
                                  '.tiff', '.pdf', '.gif', '.webp'}
    
    def preprocess_image(self, image: np.ndarray) -> Tuple[np.ndarray, List[str]]:
        """
        Apply comprehensive preprocessing to improve OCR accuracy.
        
        Args:
            image: Input image as numpy array (BGR format)
        
        Returns:
            Tuple of (preprocessed image, list of applied steps)
        """
        steps = []
        original = image.copy()
        
        # Convert to grayscale if needed
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            steps.append('grayscale_conversion')
        else:
            gray = image
            steps.append('already_grayscale')
        
        # Denoise
        denoised = cv2.fastNlMeansDenoising(gray, h=30, templateWindowSize=7, searchWindowSize=21)
        steps.append('denoising')
        
        # Deskew
        denoised, deskewed = self._deskew(denoised)
        if deskewed:
            steps.append('deskewing')
        
        # Enhance contrast with CLAHE
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        enhanced = clahe.apply(denoised)
        steps.append('contrast_enhancement')
        
        # Adaptive thresholding
        binary = cv2.adaptiveThreshold(enhanced, 255, 
                                       cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                       cv2.THRESH_BINARY, 11, 2)
        steps.append('adaptive_thresholding')
        
        # Remove small noise
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2,2))
        cleaned = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        steps.append('noise_removal')
        
        # Dilation to connect text
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1,2))
        dilated = cv2.dilate(cleaned, kernel, iterations=1)
        steps.append('text_connection')
        
        return dilated, steps
    
    def _deskew(self, image: np.ndarray) -> Tuple[np.ndarray, bool]:
        """
        Detect and correct skew in document images.
        
        Returns:
            Tuple of (deskewed image, whether skew was corrected)
        """
        # Find all points where text is present
        coords = np.column_stack(np.where(image > 0))
        
        if len(coords) < 100:  # Not enough points to determine skew
            return image, False
        
        # Calculate minimum area rectangle
        try:
            rect = cv2.minAreaRect(coords)
            angle = rect[-1]
            
            # Adjust angle
            if angle < -45:
                angle = -(90 + angle)
            else:
                angle = -angle
            
            # Only rotate if skew is significant (>0.5 degrees)
            if abs(angle) > 0.5:
                (h, w) = image.shape[:2]
                center = (w // 2, h // 2)
                M = cv2.getRotationMatrix2D(center, angle, 1.0)
                rotated = cv2.warpAffine(image, M, (w, h),
                                        flags=cv2.INTER_CUBIC,
                                        borderMode=cv2.BORDER_REPLICATE)
                return rotated, True
        except:
            pass
        
        return image, False
    
    def extract_layout(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """
        Extract layout information (text blocks, tables, images).
        
        Returns:
            List of layout blocks with position and type
        """
        blocks = []
        
        try:
            # Get layout information from Tesseract
            data = pytesseract.image_to_data(image, lang=self.languages, 
                                            config='--oem 3 --psm 3',
                                            output_type=pytesseract.Output.DICT)
            
            n_boxes = len(data['level'])
            for i in range(n_boxes):
                if data['conf'][i] > 30:  # Only include confident detections
                    block = {
                        'type': 'text',
                        'level': data['level'][i],
                        'page_num': data['page_num'][i],
                        'block_num': data['block_num'][i],
                        'par_num': data['par_num'][i],
                        'line_num': data['line_num'][i],
                        'word_num': data['word_num'][i],
                        'left': data['left'][i],
                        'top': data['top'][i],
                        'width': data['width'][i],
                        'height': data['height'][i],
                        'conf': data['conf'][i],
                        'text': data['text'][i]
                    }
                    blocks.append(block)
        except:
            pass
        
        return blocks
    
    def ocr_image(self, image: Union[str, Path, np.ndarray, Image.Image],
                 preprocessing: bool = True,
                 config: Optional[str] = None) -> OCRResult:
        """
        Perform OCR on a single image.
        
        Args:
            image: Image file path or numpy array
            preprocessing: Whether to apply preprocessing
            config: Optional Tesseract config override
        
        Returns:
            OCRResult object
        """
        import time
        start_time = time.time()
        
        # Load image
        if isinstance(image, (str, Path)):
            img = cv2.imread(str(image))
            file_path = str(image)
        elif isinstance(image, Image.Image):
            img = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            file_path = "PIL_image"
        else:
            img = image.copy()
            file_path = "numpy_array"
        
        if img is None:
            raise ValueError(f"Could not load image: {image}")
        
        # Get dimensions
        h, w = img.shape[:2]
        
        # Apply preprocessing
        preprocessing_steps = []
        if preprocessing:
            processed_img, preprocessing_steps = self.preprocess_image(img)
        else:
            if len(img.shape) == 3:
                processed_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                preprocessing_steps = ['grayscale_conversion']
            else:
                processed_img = img
                preprocessing_steps = ['none']
        
        # Try multiple PSM modes for best results
        psms = [3, 4, 6, 11, 12]  # Different page segmentation modes
        best_text = ""
        best_conf = 0
        best_config = ""
        
        for psm in psms:
            try:
                current_config = config or f'--oem 3 --psm {psm}'
                
                # Get detailed data including confidence
                data = pytesseract.image_to_data(processed_img, lang=self.languages,
                                                config=current_config,
                                                output_type=pytesseract.Output.DICT)
                
                # Calculate average confidence for non-empty text
                confidences = []
                texts = []
                for i, text in enumerate(data['text']):
                    if text.strip():
                        conf = int(data['conf'][i])
                        if conf > 0:
                            confidences.append(conf)
                            texts.append(text)
                
                if confidences:
                    avg_conf = sum(confidences) / len(confidences)
                    full_text = ' '.join(texts)
                    
                    if avg_conf > best_conf:
                        best_conf = avg_conf
                        best_text = full_text
                        best_config = current_config
            except:
                continue
        
        # If all PSMs failed, try basic OCR
        if not best_text:
            best_text = pytesseract.image_to_string(processed_img, lang=self.languages,
                                                   config=config or self.base_config)
            best_conf = 50.0  # Default confidence
            best_config = config or self.base_config
        
        # Extract layout
        layout_blocks = self.extract_layout(processed_img)
        
        # Calculate word count
        word_count = len(best_text.split())
        
        processing_time = time.time() - start_time
        
        return OCRResult(
            file_path=file_path,
            page_number=1,
            text=best_text,
            confidence=best_conf,
            language=self.languages,
            preprocessing_steps=preprocessing_steps,
            processing_time=processing_time,
            word_count=word_count,
            layout_blocks=layout_blocks,
            image_dimensions=(w, h)
        )
    
    def ocr_pdf(self, pdf_path: Union[str, Path], 
               dpi: int = 300,
               first_page: Optional[int] = None,
               last_page: Optional[int] = None,
               preprocessing: bool = True) -> List[OCRResult]:
        """
        Perform OCR on all pages of a PDF.
        
        Args:
            pdf_path: Path to PDF file
            dpi: DPI for PDF to image conversion
            first_page: First page to process (1-indexed)
            last_page: Last page to process
            preprocessing: Whether to apply preprocessing
        
        Returns:
            List of OCRResult objects, one per page
        """
        results = []
        
        # Convert PDF to images
        images = convert_from_path(pdf_path, dpi=dpi, 
                                   first_page=first_page, 
                                   last_page=last_page)
        
        for i, img in enumerate(images, start=first_page or 1):
            logger.info(f"Processing page {i}/{len(images)}")
            
            result = self.ocr_image(img, preprocessing=preprocessing)
            result.page_number = i
            result.file_path = str(pdf_path)
            results.append(result)
        
        return results
    
    def process_file(self, file_path: Union[str, Path],
                    preprocessing: bool = True,
                    **kwargs) -> Union[OCRResult, List[OCRResult]]:
        """
        Process a single file (image or PDF).
        
        Args:
            file_path: Path to file
            preprocessing: Whether to apply preprocessing
            **kwargs: Additional arguments (dpi, first_page, last_page for PDFs)
        
        Returns:
            OCRResult for images, list of OCRResult for PDFs
        """
        file_path = Path(file_path)
        ext = file_path.suffix.lower()
        
        if ext == '.pdf':
            return self.ocr_pdf(file_path, 
                               dpi=kwargs.get('dpi', 300),
                               first_page=kwargs.get('first_page'),
                               last_page=kwargs.get('last_page'),
                               preprocessing=preprocessing)
        elif ext in self.supported_formats:
            return self.ocr_image(file_path, preprocessing=preprocessing,
                                 config=kwargs.get('config'))
        else:
            raise ValueError(f"Unsupported file format: {ext}")


def process_document(file_path: str, 
                    output_dir: Optional[str] = None,
                    languages: str = 'eng',
                    preprocessing: bool = True,
                    tesseract_cmd: Optional[str] = None) -> Dict[str, Any]:
    """
    Convenience function to process a document and save results.
    
    Args:
        file_path: Path to document
        output_dir: Directory to save results (JSON, TXT)
        languages: Tesseract language codes
        preprocessing: Whether to apply preprocessing
        tesseract_cmd: Path to tesseract executable
    
    Returns:
        Dictionary with processing results
    """
    ocr = AdvancedOCR(tesseract_cmd=tesseract_cmd, languages=languages)
    
    results = ocr.process_file(file_path, preprocessing=preprocessing)
    
    output = {
        'file': file_path,
        'pages': [],
        'total_pages': 1 if not isinstance(results, list) else len(results),
    }
    
    if isinstance(results, list):
        for i, result in enumerate(results, 1):
            output['pages'].append(asdict(result))
    else:
        output['pages'].append(asdict(results))
    
    # Save results if output directory provided
    if output_dir:
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        
        base_name = Path(file_path).stem
        
        # Save JSON
        json_path = out_path / f"{base_name}_ocr.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, default=str)
        
        # Save text
        txt_path = out_path / f"{base_name}_ocr.txt"
        with open(txt_path, 'w', encoding='utf-8') as f:
            if isinstance(results, list):
                for i, result in enumerate(results, 1):
                    f.write(f"--- Page {i} ---\n\n")
                    f.write(result.text)
                    f.write("\n\n")
            else:
                f.write(results.text)
    
    return output


def process_batch(file_paths: List[str],
                 output_dir: str,
                 languages: str = 'eng',
                 preprocessing: bool = True,
                 tesseract_cmd: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Process multiple documents in batch.
    
    Args:
        file_paths: List of file paths
        output_dir: Output directory for results
        languages: Tesseract language codes
        preprocessing: Whether to apply preprocessing
        tesseract_cmd: Path to tesseract executable
    
    Returns:
        List of processing results
    """
    results = []
    
    for file_path in file_paths:
        logger.info(f"Processing: {file_path}")
        try:
            result = process_document(file_path, output_dir, languages,
                                     preprocessing, tesseract_cmd)
            results.append(result)
        except Exception as e:
            logger.error(f"Failed to process {file_path}: {e}")
            results.append({
                'file': file_path,
                'error': str(e),
                'status': 'failed'
            })
    
    # Create batch summary
    summary_path = Path(output_dir) / "batch_summary.csv"
    with open(summary_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['File', 'Pages', 'Words', 'Confidence', 'Status'])
        
        for result in results:
            if 'error' in result:
                writer.writerow([result['file'], 0, 0, 0, 'FAILED'])
            else:
                total_words = sum(p['word_count'] for p in result['pages'])
                avg_conf = sum(p['confidence'] for p in result['pages']) / result['total_pages']
                writer.writerow([
                    result['file'],
                    result['total_pages'],
                    total_words,
                    f"{avg_conf:.1f}",
                    'SUCCESS'
                ])
    
    return results