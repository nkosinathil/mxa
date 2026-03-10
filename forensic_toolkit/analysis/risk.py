"""
Explainable risk scoring for message texts.
"""
import re

RISK_RULES = [
    ("Banking keyword", 20, re.compile(r"\b(nedbank|capitec|fnb|standard\s*bank|absa|sanlam)\b", re.I)),
    ("Account / EFT / payment", 20, re.compile(r"\b(account|eft|payment|transfer|deposit|withdrawal|transaction)\b", re.I)),
    ("Urgency / pressure", 10, re.compile(r"\b(urgent|asap|immediately|today|now|final\s*notice)\b", re.I)),
    ("Invoice / quotation", 10, re.compile(r"\b(invoice|quotation|quote|purchase\s*order|po\b)\b", re.I)),
    ("PIN / OTP / password", 20, re.compile(r"\b(pin|otp|one[-\s]?time\s*pin|password)\b", re.I)),
    ("Suspicious links", 20, re.compile(r"(https?://|www\.)", re.I)),
]

def assess_risk(text: str) -> dict:
    t = text or ""
    matched = []
    score = 0
    for name, weight, rx in RISK_RULES:
        m = rx.search(t)
        if m:
            score += weight
            matched.append({
                "factor": name,
                "weight": weight,
                "evidence": (m.group(0) or "")[:120]
            })
    pct = max(0, min(100, int(round(score))))
    if pct >= 70:
        level = "High"
    elif pct >= 40:
        level = "Medium"
    else:
        level = "Low"
    return {"pct": pct, "level": level, "matched": matched}
