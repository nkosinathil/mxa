"""
Parser for text message DataFrames.
"""
import os, pandas as pd
from typing import List, Dict, Any, Optional
from ..core.utils import parse_timestamp, pick_datetime_col
from ..core.media_handler import hyperlink_media
from ..core.custody import chain_log, chain_log_exception
from ..analysis import analyze_message_text
from .dataframe_parser import DataFrameParser

TEXT_HINT_COLS = {"message","content","body","text","sms","mms","snippet"}

class MessagesParser(DataFrameParser):
    def parse_dataframe(self, path_hint: str, df: pd.DataFrame, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        out = []
        log = context.get("log")
        rel_media_prefix = context.get("rel_media_prefix", "")
        try:
            date_col = next((c for c in ["Date","date","Created","Timestamp","Time","Message Date/Time","Sent Time"] if c in df.columns), None)
            if not date_col:
                date_col = pick_datetime_col(df)
            if not date_col:
                if log: log(f"No datetime column in {os.path.basename(path_hint)}")
                chain_log(f"NO DATETIME COL (texts): {path_hint}", level="warning")
                return out

            msg_col = next((c for c in df.columns if c.lower() in TEXT_HINT_COLS), None)
            if not msg_col:
                obj_cols = [c for c in df.columns if df[c].dtype == object]
                if obj_cols:
                    msg_col = max(obj_cols, key=lambda c: df[c].astype(str).str.len().fillna(0).mean())

            chat_col = next((c for c in ["Chat","chat","Name","name","Sender","sender","From","Contact","Number","Address"] if c in df.columns), None)

            cnt = 0
            for _, r in df.iterrows():
                ts = parse_timestamp(str(r.get(date_col)))
                if not ts: continue
                text = str(r.get(msg_col, "")).strip()
                if not text: continue
                chat = (str(r.get(chat_col, "")) if chat_col else "").strip()
                enriched = analyze_message_text(text)
                out.append({
                    "timestamp": ts,
                    "date_str": ts.strftime("%Y-%m-%d %H:%M"),
                    "chat": chat,
                    "sender": chat,
                    "message": text,
                    "snippet_html": hyperlink_media(text[:800], rel_media_prefix),
                    "category": enriched.get("category"),
                    "meter_numbers": enriched.get("meter_numbers"),
                    "meter_types": enriched.get("meter_types"),
                    "risk_pct": enriched.get("risk_pct"),
                    "risk_level": enriched.get("risk_level"),
                    "risk_factors_json": enriched.get("risk_factors_json"),
                    "source": path_hint
                })
                cnt += 1
            if log: log(f"Parsed {cnt} text messages from {os.path.basename(path_hint)}")
            chain_log(f"PARSED Text DF: {path_hint} (rows={cnt})")
        except Exception as e:
            if log: log(f"Text parse failed: {os.path.basename(path_hint)} -> {e}")
            chain_log_exception(f"PARSE Text DF {path_hint}", e)
        return out
