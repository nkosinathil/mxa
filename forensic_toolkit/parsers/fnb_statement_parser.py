"""
Parser for FNB bank statement PDFs.
Extracts transaction data with OCR fallback for scanned documents.
"""
import os
import re
import hashlib
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import List, Optional, Tuple, Set, Dict, Any
from pathlib import Path

import pdfplumber

# OCR fallback
from pdf2image import convert_from_path
import pytesseract

from ..core.custody import chain_log, chain_log_exception
from .base import BaseParser

# Optional: Configure Tesseract path if needed
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

MONTHS = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12
}

# Supported extensions
FNB_EXTS = {'.pdf'}


@dataclass
class FNBTransaction:
    """Represents a single FNB bank transaction."""
    txn_date: str           # YYYY-MM-DD
    description: str
    debit: Optional[float]
    credit: Optional[float]
    source_file: str
    file_hash: str
    statement_date: str
    balance: Optional[float] = None
    balance_type: Optional[str] = None  # 'Cr' or 'Dr'


class FNBStatementParser(BaseParser):
    """Parser for FNB bank statement PDFs with OCR fallback."""
    
    def can_parse(self, file_path: str) -> bool:
        ext = os.path.splitext(file_path)[1].lower()
        return ext in FNB_EXTS
    
    def parse(self, file_path: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse an FNB bank statement PDF.
        Returns a list with transaction records.
        """
        log = context.get("log")
        filename = os.path.basename(file_path)
        
        try:
            logprint = log if log else lambda x: None
            logprint(f"Parsing FNB statement: {filename}")
            
            # Parse the PDF
            statement_date, transactions, file_hash = self._parse_pdf_statement(file_path, logprint)
            
            # Convert to dictionary format for the toolkit
            records = []
            for txn in transactions:
                records.append({
                    "file_path": file_path,
                    "filename": filename,
                    "file_hash": file_hash,
                    "statement_date": statement_date,
                    "txn_date": txn.txn_date,
                    "description": txn.description,
                    "debit": txn.debit,
                    "credit": txn.credit,
                    "balance": txn.balance,
                    "balance_type": txn.balance_type,
                    "transaction_type": "debit" if txn.debit else "credit",
                    "amount": txn.debit if txn.debit else txn.credit,
                })
            
            chain_log(f"PARSED FNB statement: {filename} - {len(transactions)} transactions")
            logprint(f"  → {len(transactions)} transactions extracted")
            
            return records
            
        except Exception as e:
            if log:
                log(f"FNB parse failed: {filename} -> {e}")
            chain_log_exception(f"PARSE FNB {file_path}", e)
            return []
    
    def _sha256_file(self, path: str) -> str:
        """Calculate SHA256 hash of file."""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    
    def _clean_amount(self, s: str) -> str:
        """Clean amount string by removing commas."""
        return s.replace(",", "").strip()
    
    def _parse_statement_date(self, full_text: str) -> Optional[str]:
        """Extract statement date from text."""
        m = re.search(r"Statement Date\s*:\s*(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", full_text)
        if m:
            day = int(m.group(1))
            mon_name = m.group(2)[:3].title()
            year = int(m.group(3))
            mon = MONTHS.get(mon_name)
            if mon:
                return f"{year:04d}-{mon:02d}-{day:02d}"
        return None
    
    def _parse_statement_period(self, full_text: str) -> Tuple[Optional[datetime], Optional[datetime]]:
        """Extract statement period for handling year rollover."""
        m = re.search(
            r"Statement Period\s*:\s*(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})\s+to\s+(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})",
            full_text
        )
        if not m:
            return None, None
        
        d1, mon1, y1, d2, mon2, y2 = m.groups()
        mon1 = MONTHS.get(mon1[:3].title())
        mon2 = MONTHS.get(mon2[:3].title())
        if not mon1 or not mon2:
            return None, None
        
        start = datetime(int(y1), mon1, int(d1))
        end = datetime(int(y2), mon2, int(d2))
        return start, end
    
    def _infer_year_for_txn(self, day: int, mon: int, period_start: Optional[datetime], 
                           period_end: Optional[datetime], statement_year: int) -> int:
        """Handle year rollover in statements (e.g., Dec to Jan)."""
        if period_start and period_end:
            if period_start.year == period_end.year:
                return period_start.year
            
            # Cross-year: months >= start_month => start.year else end.year
            if mon >= period_start.month:
                return period_start.year
            return period_end.year
        
        return statement_year
    
    def _extract_transactions_from_text(self, full_text: str) -> List[str]:
        """Extract transaction lines from text using regex."""
        # Transaction line regex
        txn_re = re.compile(
            r"""
            ^(?P<day>\d{2})\s+(?P<mon>[A-Za-z]{3})\s+
            (?P<desc>.+?)\s+
            (?P<amt>[\d,]+\.\d{2})(?P<cr>Cr)?\s+
            (?P<bal>[\d,]+\.\d{2})(?P<balcr>Cr|Dr)?
            (?:\s+.*)?$
            """,
            re.VERBOSE
        )
        
        lines = [ln.strip() for ln in full_text.splitlines() if ln.strip()]
        txn_lines = []
        
        for ln in lines:
            # Skip common non-txn rows
            if ln.startswith("Transactions in RAND"):
                continue
            if ln.startswith("Date Description Amount"):
                continue
            if "Closing Balance" in ln or "Turnover for Statement Period" in ln:
                continue
            
            if txn_re.match(ln):
                txn_lines.append(ln)
        
        return txn_lines
    
    def _ocr_pdf_to_text(self, pdf_path: str, logprint) -> str:
        """
        OCR fallback for scanned PDFs with enhanced image preprocessing.
        """
        try:
            logprint("  📸 Performing OCR on scanned document...")
            
            # Convert PDF to images with higher DPI for better quality
            images = convert_from_path(pdf_path, dpi=400)
            texts = []
            
            for i, img in enumerate(images, 1):
                logprint(f"    Processing page {i}/{len(images)}...")
                
                # Save image temporarily for debugging if needed
                # img.save(f"page_{i}.png")
                
                # Apply image preprocessing for better OCR
                import cv2
                import numpy as np
                
                # Convert PIL to OpenCV format
                img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
                
                # Convert to grayscale
                gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
                
                # Apply adaptive thresholding to handle varying lighting
                binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                              cv2.THRESH_BINARY, 11, 2)
                
                # Denoise
                denoised = cv2.fastNlMeansDenoising(binary, h=30)
                
                # Deskew if needed
                coords = np.column_stack(np.where(denoised > 0))
                if len(coords) > 0:
                    angle = cv2.minAreaRect(coords)[-1]
                    if angle < -45:
                        angle = -(90 + angle)
                    else:
                        angle = -angle
                    
                    if abs(angle) > 0.5:
                        (h, w) = denoised.shape[:2]
                        center = (w // 2, h // 2)
                        M = cv2.getRotationMatrix2D(center, angle, 1.0)
                        denoised = cv2.warpAffine(denoised, M, (w, h),
                                                  flags=cv2.INTER_CUBIC,
                                                  borderMode=cv2.BORDER_REPLICATE)
                
                # OCR with multiple configurations
                # Try different PSM modes for better accuracy
                configs = [
                    '--oem 3 --psm 6',      # Assume uniform block of text
                    '--oem 3 --psm 4',      # Assume variable text
                    '--oem 3 --psm 3',      # Fully automatic
                ]
                
                page_text = ""
                for config in configs:
                    try:
                        text = pytesseract.image_to_string(denoised, config=config)
                        if len(text) > len(page_text):
                            page_text = text
                    except:
                        continue
                
                texts.append(page_text)
            
            return "\n".join(texts)
            
        except ImportError as e:
            logprint(f"  ⚠️  OCR dependencies missing: {e}")
            logprint("     Install: pip install opencv-python numpy")
            return ""
        except Exception as e:
            logprint(f"  ⚠️  OCR failed: {e}")
            return ""
    
    def _parse_pdf_statement(self, pdf_path: str, logprint) -> Tuple[str, List[FNBTransaction], str]:
        """
        Parse PDF statement and return transactions.
        """
        file_hash = self._sha256_file(pdf_path)
        filename = os.path.basename(pdf_path)
        
        # Try text extraction first
        try:
            with pdfplumber.open(pdf_path) as pdf:
                all_text = "\n".join((page.extract_text() or "") for page in pdf.pages)
        except Exception as e:
            logprint(f"  ⚠️  PDF text extraction failed: {e}")
            all_text = ""
        
        statement_date = self._parse_statement_date(all_text)
        period_start, period_end = self._parse_statement_period(all_text)
        txn_lines = self._extract_transactions_from_text(all_text)
        
        # OCR fallback if no transactions found
        if len(txn_lines) == 0:
            logprint("  ℹ️  No transactions found in text, using OCR...")
            ocr_text = self._ocr_pdf_to_text(pdf_path, logprint)
            
            if ocr_text:
                if not statement_date:
                    statement_date = self._parse_statement_date(ocr_text)
                
                if not period_start and not period_end:
                    period_start, period_end = self._parse_statement_period(ocr_text)
                
                txn_lines = self._extract_transactions_from_text(ocr_text)
        
        if not statement_date:
            raise ValueError(f"Could not detect statement date in {filename}")
        
        statement_year = int(statement_date[:4])
        
        if len(txn_lines) == 0:
            raise ValueError(f"No transaction lines detected in {filename}")
        
        # Parse transactions
        transactions = []
        seen = set()
        
        txn_re = re.compile(
            r"""
            ^(?P<day>\d{2})\s+(?P<mon>[A-Za-z]{3})\s+
            (?P<desc>.+?)\s+
            (?P<amt>[\d,]+\.\d{2})(?P<cr>Cr)?\s+
            (?P<bal>[\d,]+\.\d{2})(?P<balcr>Cr|Dr)?
            """,
            re.VERBOSE
        )
        
        for line in txn_lines:
            m = txn_re.match(line)
            if not m:
                continue
            
            day = int(m.group("day"))
            mon_txt = m.group("mon")[:3].title()
            mon = MONTHS.get(mon_txt)
            if not mon:
                continue
            
            year = self._infer_year_for_txn(day, mon, period_start, period_end, statement_year)
            txn_date = f"{year:04d}-{mon:02d}-{day:02d}"
            
            desc = m.group("desc").strip()
            amt_raw = self._clean_amount(m.group("amt"))
            is_credit = bool(m.group("cr"))
            
            # Parse balance
            bal_raw = self._clean_amount(m.group("bal"))
            bal_type = m.group("balcr")
            
            debit = None
            credit = None
            if is_credit:
                credit = float(amt_raw)
            else:
                debit = float(amt_raw)
            
            # Deduplicate
            key = (txn_date, desc, debit, credit)
            if key in seen:
                continue
            seen.add(key)
            
            transactions.append(FNBTransaction(
                txn_date=txn_date,
                description=desc,
                debit=debit,
                credit=credit,
                balance=float(bal_raw) if bal_raw else None,
                balance_type=bal_type,
                source_file=filename,
                file_hash=file_hash,
                statement_date=statement_date
            ))
        
        if not transactions:
            raise ValueError(f"Transaction lines found but none could be parsed in {filename}")
        
        return statement_date, transactions, file_hash