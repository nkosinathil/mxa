"""
Chain‑of‑custody logging and manifest generation.
"""
import os, logging, hashlib, getpass, json, traceback
from datetime import datetime

_CHAIN_LOGGER = None
SUB_LOGS = "logs"

def init_chain_logger(session_dir: str) -> str:
    global _CHAIN_LOGGER
    log_dir = os.path.join(session_dir, SUB_LOGS)
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "chain_of_custody.log")
    logger = logging.getLogger("coc")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s",
                                      "%Y-%m-%d %H:%M:%S"))
    logger.addHandler(fh)
    _CHAIN_LOGGER = logger
    return log_path

def chain_log(msg: str, level: str = "info"):
    logger = _CHAIN_LOGGER or logging.getLogger("coc")
    if level == "error":
        logger.error(msg)
    elif level == "warning":
        logger.warning(msg)
    else:
        logger.info(msg)

def chain_log_exception(context: str, exc: Exception):
    chain_log(f"{context} FAILED: {exc}\n{traceback.format_exc()}", level="error")

def write_manifest(session_dir: str, files: list):
    log_dir = os.path.join(session_dir, SUB_LOGS)
    os.makedirs(log_dir, exist_ok=True)
    records = []
    for p in files:
        rec = {"path": p}
        try:
            rec["size"] = os.path.getsize(p)
            h = hashlib.sha256()
            with open(p, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)
            rec["sha256"] = h.hexdigest()
            chain_log(f"INPUT HASHED: {p} sha256={rec['sha256']}")
        except Exception as e:
            chain_log_exception(f"HASH {p}", e)
        records.append(rec)
    manifest = {
        "session_dir": session_dir,
        "created_utc": datetime.utcnow().isoformat() + "Z",
        "user": getpass.getuser(),
        "inputs": records,
    }
    with open(os.path.join(log_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
