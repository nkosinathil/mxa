"""
Heuristics to classify a DataFrame as calls or messages.
"""
import re, os, pandas as pd
from typing import Optional

CALL_KEYWORDS_IN_FILENAME = re.compile(r"(call|history|call_history|dial|recents)", re.I)
TEXT_HINT_COLS = {"message","content","body","text","sms","mms","snippet"}
CALL_HINT_COLS = {"duration","call duration","duration(s)","duration (s)","type","call type","direction","number","phone","phone number"}

def score_headers_for_calls(df: pd.DataFrame) -> int:
    cols = {c.lower(): c for c in df.columns}
    has_callish = sum(any(k in c for k in CALL_HINT_COLS) for c in cols)
    has_textish = sum(any(k in c for k in TEXT_HINT_COLS) for c in cols)
    return has_callish - has_textish

def score_content_for_calls(df: pd.DataFrame) -> int:
    msg_col = next((c for c in df.columns if c.lower() in TEXT_HINT_COLS), None)
    dur_col = next((c for c in df.columns if 'duration' in c.lower()), None)
    score = 0
    sample = df.head(300)
    if dur_col:
        numericish = pd.to_numeric(sample[dur_col], errors="coerce").notna().sum()
        if numericish >= max(5, len(sample)*0.3):
            score += 3
    if msg_col:
        lens = sample[msg_col].astype(str).str.len()
        long_msgs = (lens >= 30).sum()
        short_msgs = (lens <= 6).sum()
        if long_msgs >= max(8, len(sample)*0.25):
            score -= 3
        if short_msgs >= max(8, len(sample)*0.25):
            score += 1
    else:
        score += 1
    return score

def classify_table(path_hint: str, df: pd.DataFrame) -> str:
    fname = os.path.basename(path_hint)
    if CALL_KEYWORDS_IN_FILENAME.search(path_hint) or CALL_KEYWORDS_IN_FILENAME.search(fname):
        return "calls"
    h = score_headers_for_calls(df)
    if h >= 2:   return "calls"
    if h <= -1:  return "texts"
    c = score_content_for_calls(df)
    if c >= 2:   return "calls"
    if c <= -1:  return "texts"
    return "undecided"
