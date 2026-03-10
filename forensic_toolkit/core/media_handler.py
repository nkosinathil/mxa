"""
Media file detection and HTML linking.
"""
import re, os
from typing import List

MEDIA_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.mp4', '.mov', '.m4v',
              '.3gp', '.aac', '.mp3', '.opus', '.ogg', '.pdf', '.doc', '.docx',
              '.xls', '.xlsx', '.csv', '.heic', '.txt'}

def find_media_in_text(text: str) -> List[str]:
    if not text: return []
    tokens = re.findall(r"[A-Za-z0-9_\-\.]+\.[A-Za-z0-9]{1,5}", text)
    hits = []
    for t in tokens:
        _, ext = os.path.splitext(t)
        if ext.lower() in MEDIA_EXTS:
            hits.append(t)
    seen, out = set(), []
    for t in hits:
        if t not in seen:
            seen.add(t); out.append(t)
    return out

def hyperlink_media(text: str, rel_media_prefix: str) -> str:
    from .utils import html_escape
    if not text: return ""
    esc = html_escape(text)
    for fn in find_media_in_text(text):
        esc = esc.replace(html_escape(fn),
                          f"<a href=\"{rel_media_prefix}{html_escape(fn)}\" target=\"_blank\">{html_escape(fn)}</a>")
    return esc
