"""
Extract meter‑like numbers from text.
"""
import re, os, tempfile, subprocess, shutil
from typing import Dict, List

METER_PATTERNS = [
    ("PREPAID_11DIG", re.compile(r"\b\d{11}\b")),
    ("NUMERIC_6_14",  re.compile(r"\b\d{6,14}\b")),
    ("ALNUM",         re.compile(r"\b[A-Z]{1,4}\d{6,12}\b", re.I)),
]

def extract_meter_numbers(text: str) -> Dict[str, List[str]]:
    t = text or ""
    hits: Dict[str, List[str]] = {}
    for typ, rx in METER_PATTERNS:
        ms = rx.findall(t)
        if ms:
            seen = set()
            uniq = []
            for x in ms:
                if x not in seen:
                    seen.add(x); uniq.append(x)
            hits[typ] = uniq

    # optional grep helper (best effort)
    try:
        if shutil.which("grep"):
            with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as tf:
                tf.write(t)
                tmp = tf.name
            cmd = ["grep", "-Eo", r"([0-9]{6,14}|[A-Za-z]{1,4}[0-9]{6,12})", tmp]
            out = subprocess.run(cmd, capture_output=True, text=True)
            os.unlink(tmp)
            if out.returncode in (0,1):
                extra = [x.strip() for x in out.stdout.splitlines() if x.strip()]
                if extra:
                    hits.setdefault("GREP", [])
                    seen = set(hits["GREP"])
                    for x in extra:
                        if x not in seen:
                            seen.add(x); hits["GREP"].append(x)
    except Exception:
        pass
    return hits
