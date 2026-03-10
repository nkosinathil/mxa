"""
Parser for WhatsApp HTML exports.
"""
import os, re
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional
from ..core.utils import detect_encoding, parse_timestamp, html_escape
from ..core.media_handler import hyperlink_media
from ..core.custody import chain_log, chain_log_exception
from ..analysis import analyze_message_text
from .base import BaseParser

def _pick_bs4_parser() -> str:
    try:
        import lxml
        return "lxml"
    except:
        return "html.parser"

class WhatsAppHTMLParser(BaseParser):
    def can_parse(self, file_path: str) -> bool:
        low = file_path.lower()
        return low.endswith((".html", ".htm"))

    def parse(self, file_path: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        out = []
        rel_media_prefix = context.get("rel_media_prefix", "")
        source_hint = context.get("source_hint")
        log = context.get("log")
        try:
            enc = detect_encoding(file_path)
            with open(file_path, "r", encoding=enc, errors="ignore") as f:
                html = f.read()
            soup = BeautifulSoup(html, _pick_bs4_parser())
            chat_name = None
            h3 = soup.find("h3")
            if h3:
                chat_name = h3.get_text(strip=True)
            chat_hint = None
            if source_hint:
                m = re.search(r"WhatsApp/([^/]+)/HTML/WhatsApp\.html", source_hint, flags=re.I)
                if not m:
                    m = re.search(r"WhatsApp/([^/]+)/", source_hint, flags=re.I)
                if m:
                    chat_hint = m.group(1)
            if not chat_name:
                chat_name = chat_hint or os.path.splitext(os.path.basename(file_path))[0]
            extracted = 0
            date_nodes = soup.find_all("p", {"class": "date"})
            for dn in date_nodes:
                ts_text = dn.get_text(" ", strip=True)
                ts = parse_timestamp(ts_text)
                if not ts: continue
                cursor = dn.find_next_sibling()
                payloads, steps = [], 0
                while cursor and steps < 10:
                    steps += 1
                    if cursor.name == "p" and "date" in (cursor.get("class") or []):
                        break
                    if cursor.name in ("p", "table", "div", "span", "li"):
                        txt = cursor.get_text(" ", strip=True)
                        if txt: payloads.append(txt)
                    cursor = cursor.find_next_sibling()
                text = " ".join(payloads).strip()
                if not text:
                    nxt = dn.find_next_sibling("p")
                    if nxt:
                        text = nxt.get_text(" ", strip=True)
                if not text: continue
                enriched = analyze_message_text(text)
                out.append({
                    "timestamp": ts,
                    "date_str": ts.strftime("%Y-%m-%d %H:%M"),
                    "chat": chat_name,
                    "sender": chat_name,
                    "message": text,
                    "snippet_html": hyperlink_media(text[:800], rel_media_prefix),
                    "category": enriched.get("category"),
                    "meter_numbers": enriched.get("meter_numbers"),
                    "meter_types": enriched.get("meter_types"),
                    "risk_pct": enriched.get("risk_pct"),
                    "risk_level": enriched.get("risk_level"),
                    "risk_factors_json": enriched.get("risk_factors_json"),
                    "source": source_hint or file_path
                })
                extracted += 1
            if extracted == 0:
                plain = soup.get_text("\n", strip=True)
                pat = re.compile(
                    r"(?:^|\n)(?:Date:\s*)?"
                    r"((?:\d{1,2}/\d{1,2}/\d{4})|(?:\d{4}/\d{1,2}/\d{1,2}))\s+(\d{1,2}:\d{2}(?::\d{2})?)"
                    r"(.*?)(?=\n(?:Date:\s*)?(?:\d{1,2}/\d{1,2}/\d{4}|\d{4}/\d{1,2}/\d{1,2})\s+\d{1,2}:\d{2}(?::\d{2})?|$)",
                    flags=re.S
                )
                for m in pat.finditer(plain):
                    date_part = m.group(1)
                    time_part = m.group(2)
                    body = m.group(3).strip()
                    ts = parse_timestamp(f"{date_part} {time_part}")
                    if not ts or not body:
                        continue
                    enriched = analyze_message_text(body)
                    out.append({
                        "timestamp": ts,
                        "date_str": ts.strftime("%Y-%m-%d %H:%M"),
                        "chat": chat_name,
                        "sender": chat_name,
                        "message": body,
                        "snippet_html": hyperlink_media(body[:800], rel_media_prefix),
                        "category": enriched.get("category"),
                        "meter_numbers": enriched.get("meter_numbers"),
                        "meter_types": enriched.get("meter_types"),
                        "risk_pct": enriched.get("risk_pct"),
                        "risk_level": enriched.get("risk_level"),
                        "risk_factors_json": enriched.get("risk_factors_json"),
                        "source": source_hint or file_path
                    })
            if log: log(f"Parsed {len(out)} WhatsApp messages from {os.path.basename(file_path)} (chat: {chat_name})")
            chain_log(f"PARSED WhatsApp HTML: {file_path} (rows={len(out)})")
        except Exception as e:
            if log: log(f"HTML parse failed: {os.path.basename(file_path)} -> {e}")
            chain_log_exception(f"PARSE WhatsApp HTML {file_path}", e)
        return out
