"""
Analysis modules: risk scoring, meter extraction, categorization.
"""
from .risk import assess_risk
from .meter import extract_meter_numbers
from .categorization import categorize_message

def analyze_message_text(msg: str) -> dict:
    """Combined analysis for a message."""
    from .risk import assess_risk
    from .meter import extract_meter_numbers
    from .categorization import categorize_message
    mlow = (msg or "").lower()
    meter_hits = {}
    if "meter" in mlow:
        meter_hits = extract_meter_numbers(msg)
    has_meter_no = any(meter_hits.values())
    if "meter" in mlow and has_meter_no:
        category = "Meters"
    else:
        category = categorize_message(msg)

    risk = assess_risk(msg)
    meter_numbers_flat = []
    meter_types = []
    for typ, vals in meter_hits.items():
        if vals:
            meter_types.append(typ)
            meter_numbers_flat.extend(vals)
    seen = set()
    meter_numbers_flat = [x for x in meter_numbers_flat if not (x in seen or seen.add(x))]

    import json
    return {
        "category": category,
        "meter_numbers": ", ".join(meter_numbers_flat),
        "meter_types": ", ".join(meter_types),
        "risk_pct": risk["pct"],
        "risk_level": risk["level"],
        "risk_factors_json": json.dumps(risk["matched"], ensure_ascii=False),
    }
