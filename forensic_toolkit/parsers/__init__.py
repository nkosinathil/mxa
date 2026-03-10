"""
Parsers module for forensic toolkit.
Contains all file format parsers for different evidence types.
"""

from .base import BaseParser
from .whatsapp_html import WhatsAppHTMLParser
from .calls_parser import CallsParser
from .messages_parser import MessagesParser
from .image_parser import ImageParser
from .audio_parser import AudioParser
from .vision_parser import VisionParser
from .email_parser import EmailParser
from .fnb_statement_parser import FNBStatementParser

__all__ = [
    'BaseParser',
    'WhatsAppHTMLParser',
    'CallsParser',
    'MessagesParser',
    'ImageParser',
    'AudioParser',
    'VisionParser',
    'EmailParser',
    'FNBStatementParser',
]