"""
Base class for parsing pandas DataFrames (CSV/XLSX).
"""
import os, pandas as pd
from typing import List, Dict, Any, Optional
from abc import abstractmethod
from ..core.utils import detect_encoding, pick_datetime_col
from .base import BaseParser

# --- Excel reader guard ---
def _read_excel_guard(path):
    try:
        import openpyxl
    except Exception as e:
        raise RuntimeError("Install 'openpyxl' to read XLSX: {}".format(e))
    return pd.read_excel(path, engine='openpyxl')

class DataFrameParser(BaseParser):
    def can_parse(self, file_path: str) -> bool:
        low = file_path.lower()
        return low.endswith((".csv", ".xlsx"))

    def parse(self, file_path: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        low = file_path.lower()
        try:
            if low.endswith(".xlsx"):
                df = _read_excel_guard(file_path)
            else:
                df = pd.read_csv(file_path, encoding=detect_encoding(file_path))
        except Exception as e:
            chain_log_exception(f"READ TABLE {file_path}", e)
            return []
        return self.parse_dataframe(file_path, df, context)

    @abstractmethod
    def parse_dataframe(self, path_hint: str, df: pd.DataFrame, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        pass
