"""
Parser for image files to perform object detection, OCR, and captioning.
"""
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from ..core.custody import chain_log, chain_log_exception
from .base import BaseParser

# Image extensions supported by vision module
VISION_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff', '.webp'}

class VisionParser(BaseParser):
    """Parser for images to prepare them for vision processing."""
    
    def can_parse(self, file_path: str) -> bool:
        ext = os.path.splitext(file_path)[1].lower()
        return ext in VISION_EXTS
    
    def parse(self, file_path: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse image file - returns metadata. Actual vision processing happens in processor.
        """
        log = context.get("log")
        try:
            p = Path(file_path)
            st = p.stat()
            
            # Basic metadata (vision processing happens in processor phase)
            record = {
                "file_path": str(p.resolve()),
                "filename": p.name,
                "size_bytes": st.st_size,
                "processed": False,
                "has_caption": False,
                "has_ocr": False,
                "has_detections": False,
            }
            
            if log:
                log(f"Found image for vision processing: {p.name}")
            chain_log(f"FOUND Image for vision: {file_path}")
            
            return [record]
            
        except Exception as e:
            if log:
                log(f"Vision parse failed: {os.path.basename(file_path)} -> {e}")
            chain_log_exception(f"PARSE Vision {file_path}", e)
            return []