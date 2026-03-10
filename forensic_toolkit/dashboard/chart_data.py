"""
Aggregate data for charts.
"""
import pandas as pd
from typing import Dict, List

def month_key(ts):
    return ts.strftime("%b %Y")

def agg_messages_for_charts(rows: List[Dict]) -> Dict:
    if not rows: return {"CAT_ROWS":[], "TOP_ROWS":[], "MONTHLY_ROWS":[], "BANK_ROWS":[], "KW_ROWS":[]}
    df = pd.DataFrame(rows)
    by_cat = df["category"].value_counts()
    by_chat = df["chat"].fillna("").value_counts().head(20)
    by_month = df.groupby(df["timestamp"].apply(month_key)).size().sort_index()
    kws = ['deal','promo','offer','voucher','pin','nedbank','sanlam','capitec','standard bank','fnb','mtn','airtime']
    kw_counts = {k: int(df["message"].astype(str).str.lower().str.contains(k).sum()) for k in kws}
    bank_keys = ['nedbank','capitec','standard bank','fnb','absa','sanlam']
    bank_counts = {b: int(df["message"].astype(str).str.lower().str.contains(b).sum()) for b in bank_keys}
    return {
        "CAT_ROWS": [[k, int(v)] for k, v in by_cat.items()],
        "TOP_ROWS": [[k, int(v)] for k, v in by_chat.items()],
        "MONTHLY_ROWS": [[k, int(v)] for k, v in by_month.items()],
        "BANK_ROWS": [[k.title(), v] for k, v in bank_counts.items() if v>0],
        "KW_ROWS": [[k, v] for k, v in kw_counts.items() if v>0],
    }

def agg_calls_for_charts(rows: List[Dict]) -> Dict:
    if not rows: return {"TOP_ROWS":[], "MONTHLY_ROWS":[], "TOP_DUR_ROWS":[]}
    df = pd.DataFrame(rows)
    by_name = df["Name"].fillna(df["Number"]).value_counts().head(20)
    by_month = df.groupby(df["timestamp"].apply(month_key)).size().sort_index()
    dur = df.assign(d=pd.to_numeric(df["DurationSec"], errors="coerce").fillna(0))             .groupby(df["Name"].fillna(df["Number"]))["d"]             .sum().sort_values(ascending=False).head(20)
    return {
        "TOP_ROWS": [[str(k), int(v)] for k, v in by_name.items()],
        "MONTHLY_ROWS": [[k, int(v)] for k, v in by_month.items()],
        "TOP_DUR_ROWS": [[str(k), int(v)] for k, v in dur.items()],
    }
