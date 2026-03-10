"""
Parser for audio/video files to extract and transcribe speech.
"""
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from ..core.custody import chain_log, chain_log_exception
from .base import BaseParser

# Audio/Video extensions supported by Whisper
AUDIO_EXTS = {'.mp3', '.wav', '.m4a', '.ogg', '.flac', '.aac', '.wma', '.opus',
              '.mp4', '.mov', '.mkv', '.m4v', '.webm', '.3gp', '.avi', '.wmv'}

class AudioParser(BaseParser):
    """Parser for audio/video files using Faster Whisper."""
    
    def can_parse(self, file_path: str) -> bool:
        ext = os.path.splitext(file_path)[1].lower()
        return ext in AUDIO_EXTS
    
    def parse(self, file_path: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse audio file - returns metadata. Actual transcription happens in processor.
        """
        log = context.get("log")
        try:
            p = Path(file_path)
            st = p.stat()
            
            # Basic metadata (transcription happens in processor phase)
            record = {
                "file_path": str(p.resolve()),
                "filename": p.name,
                "size_bytes": st.st_size,
                "audio_duration": None,  # Will be filled during processing
                "transcribed": False,
                "language": None,
                "has_transcript": False,
            }
            
            if log:
                log(f"Found audio file: {p.name}")
            chain_log(f"FOUND Audio: {file_path}")
            
            return [record]
            
        except Exception as e:
            if log:
                log(f"Audio parse failed: {os.path.basename(file_path)} -> {e}")
            chain_log_exception(f"PARSE Audio {file_path}", e)
            return []