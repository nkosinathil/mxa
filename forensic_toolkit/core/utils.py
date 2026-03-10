"""
Miscellaneous helper functions.
"""
import re, os, chardet, pandas as pd
from datetime import datetime
from typing import Optional, List

def html_escape(s: str) -> str:
    return (str(s)
            .replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#039;"))

def detect_encoding(path: str) -> str:
    try:
        with open(path, "rb") as f:
            raw = f.read(8192)
        det = chardet.detect(raw)
        return det.get("encoding") or "utf-8"
    except:
        return "utf-8"

def parse_timestamp(val: str) -> Optional[datetime]:
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    s = re.sub(r"^Date:\s*", "", s, flags=re.I).strip()
    fmts = [
        "%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M", "%m/%d/%Y %I:%M %p", "%m/%d/%y %H:%M",
        "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M",
        "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
        "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M",
    ]
    for fmt in fmts:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    try:
        dt = pd.to_datetime(s, errors="coerce")
        if pd.isna(dt): return None
        return dt.to_pydatetime()
    except:
        return None

def pick_datetime_col(df: pd.DataFrame) -> Optional[str]:
    if df is None or df.empty: return None
    sample = df.head(200)
    best, hits_best = None, 0
    for col in df.columns:
        nn, hits = 0, 0
        for v in sample[col]:
            if pd.isna(v): continue
            nn += 1
            if parse_timestamp(str(v)) is not None:
                hits += 1
        if nn >= 5 and hits / max(1, nn) >= 0.6:
            return col
        if hits > hits_best:
            best, hits_best = col, hits
    return best if hits_best >= 3 else None
