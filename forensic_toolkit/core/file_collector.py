"""
File collection and ZIP extraction.
"""
import os, glob, zipfile, tempfile, shutil
from typing import List, Tuple, Set, Optional
from .custody import chain_log, chain_log_exception  # FIXED: Import from custody, not utils
from .media_handler import MEDIA_EXTS

INPUT_EXTS = {".zip", ".html", ".htm", ".csv", ".xlsx"}

def collect_inputs_from_dir(root: str, recursive: bool = True) -> List[str]:
    """Return a sorted list of supported evidence files under 'root'."""
    if not os.path.isdir(root):
        raise RuntimeError(f"Not a directory: {root}")
    hits = []
    for dirpath, _, filenames in os.walk(root):
        for f in filenames:
            ext = os.path.splitext(f)[1].lower()
            if ext in INPUT_EXTS:
                hits.append(os.path.join(dirpath, f))
        if not recursive:
            break
    hits.sort()
    return hits

def expand_inputs(inputs: List[str]) -> List[str]:
    """Expand glob patterns and directories into a flat list of files."""
    expanded = []
    for item in inputs:
        if os.path.isdir(item):
            expanded.extend(collect_inputs_from_dir(item, recursive=True))
            continue
        hits = glob.glob(item, recursive=True)
        if hits:
            expanded.extend(sorted(hits))
        else:
            expanded.append(item)
    # deduplicate preserving order
    seen, out = set(), []
    for p in expanded:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out

def process_zip(path: str, out_media_dir: str, log=None) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]]]:
    """
    Extract a ZIP file to a temporary location.
    Returns (html_files, table_files) where each element is (temp_path, original_arcname).
    Media files are copied directly to out_media_dir.
    """
    htmls: List[Tuple[str, str]] = []
    tables: List[Tuple[str, str]] = []
    try:
        with zipfile.ZipFile(path, "r") as z:
            tmpdir = tempfile.mkdtemp(prefix="zip_in_")
            if log: 
                log(f"Extracting ZIP to temp: {tmpdir}")
            chain_log(f"ZIP EXTRACT START: {path} -> {tmpdir}")
            used_names = set()
            for arcname in z.namelist():
                if arcname.endswith("/") or arcname.startswith("__MACOSX/"):
                    continue
                base = os.path.basename(arcname)
                if not base:
                    base = arcname.strip("/").replace("/", "_")
                stem, ext = os.path.splitext(base)
                name = base
                idx = 1
                while name in used_names:
                    name = f"{stem}_{idx}{ext}"
                    idx += 1
                used_names.add(name)
                tmp_path = os.path.join(tmpdir, name)
                with z.open(arcname) as src, open(tmp_path, "wb") as dst:
                    dst.write(src.read())
                ext_l = os.path.splitext(tmp_path)[1].lower()
                if ext_l in MEDIA_EXTS:
                    # copy to media folder
                    media_name = base
                    mstem, mext = os.path.splitext(media_name)
                    midx = 1
                    out_target = os.path.join(out_media_dir, media_name)
                    while os.path.exists(out_target):
                        media_name = f"{mstem}_{midx}{mext}"
                        out_target = os.path.join(out_media_dir, media_name)
                        midx += 1
                    try:
                        shutil.copy2(tmp_path, out_target)
                        chain_log(f"MEDIA COPIED: {media_name}")
                    except Exception as e:
                        if log: 
                            log(f"Media copy skipped ({media_name}): {e}")
                        chain_log_exception(f"MEDIA COPY {media_name}", e)
                if ext_l in (".html", ".htm"):
                    htmls.append((tmp_path, arcname))
                elif ext_l in (".csv", ".xlsx"):
                    tables.append((tmp_path, arcname))
            chain_log(f"ZIP EXTRACT COMPLETE: {path} (htmls={len(htmls)}, tables={len(tables)})")
    except Exception as e:
        if log: 
            log(f"ZIP error: {os.path.basename(path)} -> {e}")
        chain_log_exception(f"ZIP {path}", e)
    return htmls, tables