"""
Abstract base class for all parsers.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class BaseParser(ABC):
    @abstractmethod
    def can_parse(self, file_path: str) -> bool:
        """Return True if this parser can handle the given file."""
        pass

    @abstractmethod
    def parse(self, file_path: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse the file and return a list of record dictionaries.
        Context may contain: rel_media_prefix, log function, etc.
        """
        pass
