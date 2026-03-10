"""
Advanced OCR module for forensic document analysis.
Handles skewed documents, multiple formats, and image preprocessing.
"""

from .advanced_ocr import AdvancedOCR, OCRResult, process_document, process_batch

__all__ = [
    'AdvancedOCR',
    'OCRResult',
    'process_document',
    'process_batch',
]