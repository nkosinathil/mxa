"""
Parser for call log DataFrames.
"""
import os, pandas as pd
from typing import List, Dict, Any, Optional
from ..core.utils import parse_timestamp, pick_datetime_col
from ..core.custody import chain_log, chain_log_exception
from .dataframe_parser import DataFrameParser

class CallsParser(DataFrameParser):
    def parse_dataframe(self, path_hint: str, df: pd.DataFrame, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        out = []
        log = context.get("log")
        try:
            date_col = next((c for c in ["Date","date","Time","Timestamp","Call Time","Date/Time"] if c in df.columns), None)
            if not date_col:
                date_col = pick_datetime_col(df)
            if not date_col:
                if log: log(f"No datetime column in calls: {os.path.basename(path_hint)}")
                chain_log(f"NO DATETIME COL (calls): {path_hint}", level="warning")
                return out
            type_col   = next((c for c in ["Type","type","Call Type","Direction"] if c in df.columns), None)
            name_col   = next((c for c in ["Name","name","Contact","Caller Name"] if c in df.columns), None)
            number_col = next((c for c in ["Number","number","Phone","Phone Number","Address"] if c in df.columns), None)
            dur_col    = next((c for c in ["Duration","duration","Duration(s)","Duration (s)","Call Duration"] if c in df.columns), None)

            cnt = 0
            for _, r in df.iterrows():
                ts = parse_timestamp(str(r.get(date_col)))
                if not ts: continue
                ctype  = str(r.get(type_col, "")).strip()   if type_col else ""
                name   = str(r.get(name_col, "")).strip()   if name_col else ""
                number = str(r.get(number_col, "")).strip() if number_col else ""
                dur    = r.get(dur_col, "")
                try:
                    dur = int(str(dur).split(".")[0])
                except:
                    dur = ""
                out.append({
                    "timestamp": ts,
                    "date_str": ts.strftime("%Y-%m-%d %H:%M"),
                    "Type": ctype,
                    "Name": name,
                    "Number": number,
                    "DurationSec": dur,
                    "Source": path_hint
                })
                cnt += 1
            if log: log(f"Parsed {cnt} calls from {os.path.basename(path_hint)}")
            chain_log(f"PARSED Calls DF: {path_hint} (rows={cnt})")
        except Exception as e:
            if log: log(f"Call parse failed: {os.path.basename(path_hint)} -> {e}")
            chain_log_exception(f"PARSE Calls DF {path_hint}", e)
        return out
