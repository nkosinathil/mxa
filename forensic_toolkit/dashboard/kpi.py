"""
KPI calculations for messages and calls.
"""
import pandas as pd
from typing import Dict, List

def kpis_from_messages(rows: List[Dict]) -> Dict:
    if not rows:
        return {"total":0,"unique_chats":0,"start":"-","end":"-","days":0,"avg_per_day":0.0,
                "high_risk":0,"med_risk":0,"low_risk":0,"high_risk_pct":0,
                "meter_msgs":0}
    df = pd.DataFrame(rows).sort_values("timestamp")
    start = df["timestamp"].iloc[0]; end = df["timestamp"].iloc[-1]
    days = max(1, (end-start).days)
    rl = df.get("risk_level", pd.Series([""]*len(df))).fillna("")
    high = int((rl=="High").sum())
    med  = int((rl=="Medium").sum())
    low  = int((rl=="Low").sum())
    high_pct = int(round((high / max(1,len(df))) * 100.0))
    meter_msgs = 0
    if "meter_numbers" in df.columns:
        meter_msgs = int((df["meter_numbers"].fillna("").astype(str).str.len() > 0).sum())
    return {
        "total": len(df),
        "unique_chats": df["chat"].fillna("").nunique(),
        "start": start.strftime("%d %b %Y"),
        "end": end.strftime("%d %b %Y"),
        "days": days,
        "avg_per_day": len(df)/days,
        "high_risk": high,
        "med_risk": med,
        "low_risk": low,
        "high_risk_pct": high_pct,
        "meter_msgs": meter_msgs,
    }

def kpis_from_calls(rows: List[Dict]) -> Dict:
    if not rows:
        return {"total":0,"unique_numbers":0,"start":"-","end":"-","total_duration":0}
    df = pd.DataFrame(rows).sort_values("timestamp")
    start = df["timestamp"].iloc[0]; end = df["timestamp"].iloc[-1]
    total_dur = int(pd.to_numeric(df["DurationSec"], errors="coerce").fillna(0).sum())
    return {
        "total": len(df),
        "unique_numbers": df["Number"].fillna("").nunique(),
        "start": start.strftime("%d %b %Y"),
        "end": end.strftime("%d %b %Y"),
        "total_duration": total_dur
    }
