"""
Parser for email files (EML, MSG, MBOX, PST).
"""
import os
import re
import mailbox
import email
from email.header import decode_header
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from ..core.custody import chain_log, chain_log_exception
from .base import BaseParser

# Email extensions supported
EMAIL_EXTS = {'.eml', '.msg', '.mbox', '.pst'}

# Try to import MSG parser if available
try:
    import extract_msg
    MSG_SUPPORT = True
except ImportError:
    MSG_SUPPORT = False

# Try to import PST parser if available
try:
    import pypff
    PST_SUPPORT = True
except ImportError:
    PST_SUPPORT = False

class EmailParser(BaseParser):
    """Parser for email files to extract metadata, headers, body, and attachments."""
    
    def can_parse(self, file_path: str) -> bool:
        ext = os.path.splitext(file_path)[1].lower()
        return ext in EMAIL_EXTS
    
    def parse(self, file_path: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse email file and extract all relevant data.
        Returns a list with one or more email records (for MBOX/PST containers).
        """
        log = context.get("log")
        ext = os.path.splitext(file_path)[1].lower()
        
        try:
            if ext == '.eml':
                return self._parse_eml(file_path, context)
            elif ext == '.msg' and MSG_SUPPORT:
                return self._parse_msg(file_path, context)
            elif ext == '.mbox':
                return self._parse_mbox(file_path, context)
            elif ext == '.pst' and PST_SUPPORT:
                return self._parse_pst(file_path, context)
            else:
                if log:
                    log(f"Unsupported or missing dependencies for: {file_path}")
                return []
                
        except Exception as e:
            if log:
                log(f"Email parse failed: {os.path.basename(file_path)} -> {e}")
            chain_log_exception(f"PARSE Email {file_path}", e)
            return []
    
    def _parse_eml(self, file_path: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse a single EML file."""
        log = context.get("log")
        records = []
        
        try:
            with open(file_path, 'rb') as f:
                msg = email.message_from_binary_file(f)
            
            record = self._extract_email_data(msg, file_path)
            records.append(record)
            
            if log:
                log(f"Parsed EML: {os.path.basename(file_path)} - Subject: {record.get('subject', '')[:50]}")
            chain_log(f"PARSED EML: {file_path}")
            
        except Exception as e:
            if log:
                log(f"EML parse failed: {os.path.basename(file_path)} -> {e}")
            chain_log_exception(f"PARSE EML {file_path}", e)
        
        return records
    
    def _parse_msg(self, file_path: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse a single MSG file using extract_msg."""
        log = context.get("log")
        records = []
        
        try:
            msg = extract_msg.Message(file_path)
            msg_record = self._extract_msg_data(msg, file_path)
            records.append(msg_record)
            msg.close()
            
            if log:
                log(f"Parsed MSG: {os.path.basename(file_path)} - Subject: {msg_record.get('subject', '')[:50]}")
            chain_log(f"PARSED MSG: {file_path}")
            
        except Exception as e:
            if log:
                log(f"MSG parse failed: {os.path.basename(file_path)} -> {e}")
            chain_log_exception(f"PARSE MSG {file_path}", e)
        
        return records
    
    def _parse_mbox(self, file_path: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse an MBOX file containing multiple emails."""
        log = context.get("log")
        records = []
        
        try:
            mbox = mailbox.mbox(file_path)
            total = len(mbox)
            
            if log:
                log(f"Processing MBOX with {total} messages: {os.path.basename(file_path)}")
            
            for i, msg in enumerate(mbox, 1):
                try:
                    record = self._extract_email_data(msg, f"{file_path}#{i}")
                    record["mbox_position"] = i
                    records.append(record)
                    
                    if i % 100 == 0 and log:
                        log(f"  Processed {i}/{total} messages")
                        
                except Exception as e:
                    if log:
                        log(f"  Error on message {i}: {e}")
                    chain_log_exception(f"PARSE MBOX message {i} in {file_path}", e)
            
            if log:
                log(f"Completed MBOX: {len(records)} messages parsed")
            chain_log(f"PARSED MBOX: {file_path} (rows={len(records)})")
            
        except Exception as e:
            if log:
                log(f"MBOX parse failed: {os.path.basename(file_path)} -> {e}")
            chain_log_exception(f"PARSE MBOX {file_path}", e)
        
        return records
    
    def _parse_pst(self, file_path: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse a PST file using libpff."""
        log = context.get("log")
        records = []
        
        if not PST_SUPPORT:
            if log:
                log(f"PST support requires pypff library. Skipping: {file_path}")
            return records
        
        try:
            pst = pypff.file()
            pst.open(file_path)
            
            root = pst.get_root_folder()
            total = self._count_pst_messages(root)
            
            if log:
                log(f"Processing PST with approximately {total} messages: {os.path.basename(file_path)}")
            
            self._extract_pst_folder(root, file_path, records, log)
            pst.close()
            
            if log:
                log(f"Completed PST: {len(records)} messages parsed")
            chain_log(f"PARSED PST: {file_path} (rows={len(records)})")
            
        except Exception as e:
            if log:
                log(f"PST parse failed: {os.path.basename(file_path)} -> {e}")
            chain_log_exception(f"PARSE PST {file_path}", e)
        
        return records
    
    def _count_pst_messages(self, folder) -> int:
        """Count messages in a PST folder recursively."""
        count = folder.get_number_of_sub_messages()
        
        for sub_folder in folder.sub_folders:
            if sub_folder:
                count += self._count_pst_messages(sub_folder)
        
        return count
    
    def _extract_pst_folder(self, folder, source_path: str, records: List, log=None, path=""):
        """Recursively extract messages from PST folders."""
        folder_name = folder.get_name()
        current_path = f"{path}/{folder_name}" if path else folder_name
        
        # Process messages in this folder
        for message in folder.sub_messages:
            try:
                record = self._extract_pst_message(message, source_path, current_path)
                records.append(record)
            except Exception as e:
                if log:
                    log(f"  Error extracting message from {current_path}: {e}")
        
        # Process subfolders
        for sub_folder in folder.sub_folders:
            if sub_folder:
                self._extract_pst_folder(sub_folder, source_path, records, log, current_path)
    
    def _extract_pst_message(self, message, source_path: str, folder_path: str) -> Dict[str, Any]:
        """Extract data from a PST message object."""
        record = {
            "source_file": source_path,
            "folder": folder_path,
            "message_id": self._safe_decode(message.get_identifier()),
            "subject": self._safe_decode(message.get_subject()),
            "sender_name": self._safe_decode(message.get_sender_name()),
            "sender_address": self._safe_decode(message.get_sender_email_address()),
            "display_to": self._safe_decode(message.get_display_to()),
            "display_cc": self._safe_decode(message.get_display_cc()),
            "display_bcc": self._safe_decode(message.get_display_bcc()),
            "body": self._safe_decode(message.get_plain_text_body()) or self._safe_decode(message.get_html_body()),
            "has_attachments": message.get_number_of_attachments() > 0,
            "attachment_count": message.get_number_of_attachments(),
            "conversation_topic": self._safe_decode(message.get_conversation_topic()),
            "conversation_index": self._safe_decode(message.get_conversation_index()),
            "importance": message.get_importance(),
            "sensitivity": message.get_sensitivity(),
        }
        
        # Parse timestamps
        record["sent_date"] = self._parse_pst_time(message.get_client_submit_time())
        record["received_date"] = self._parse_pst_time(message.get_message_delivery_time())
        record["date_str"] = record["sent_date"] or record["received_date"] or ""
        
        return record
    
    def _parse_pst_time(self, timestamp) -> Optional[str]:
        """Parse PST timestamp to ISO format."""
        if timestamp:
            try:
                # pypff returns timestamps in various formats
                if hasattr(timestamp, 'strftime'):
                    return timestamp.strftime("%Y-%m-%d %H:%M:%S")
                elif isinstance(timestamp, (int, float)):
                    from datetime import datetime
                    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
            except:
                pass
        return None
    
    def _extract_email_data(self, msg, source: str) -> Dict[str, Any]:
        """Extract common email data from an email.message object."""
        record = {
            "source_file": source,
            "message_id": self._decode_header(msg.get('Message-ID', '')),
            "subject": self._decode_header(msg.get('Subject', '')),
            "from": self._decode_header(msg.get('From', '')),
            "to": self._decode_header(msg.get('To', '')),
            "cc": self._decode_header(msg.get('Cc', '')),
            "bcc": self._decode_header(msg.get('Bcc', '')),
            "reply_to": self._decode_header(msg.get('Reply-To', '')),
            "in_reply_to": self._decode_header(msg.get('In-Reply-To', '')),
            "references": self._decode_header(msg.get('References', '')),
            "content_type": msg.get_content_type(),
            "has_attachments": False,
            "attachment_count": 0,
            "attachments": [],
            "headers": dict(msg.items()),
        }
        
        # Parse dates
        date_str = msg.get('Date', '')
        record["date"] = self._parse_email_date(date_str)
        record["date_str"] = record["date"] or date_str
        
        # Extract body and attachments
        body_parts = []
        
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))
                
                if "attachment" in content_disposition:
                    # Handle attachment
                    filename = part.get_filename()
                    if filename:
                        filename = self._decode_header(filename)
                        record["has_attachments"] = True
                        record["attachment_count"] += 1
                        record["attachments"].append({
                            "filename": filename,
                            "content_type": content_type,
                            "size": len(part.get_payload(decode=True)) if part.get_payload(decode=True) else 0
                        })
                elif content_type == "text/plain":
                    # Plain text body
                    payload = part.get_payload(decode=True)
                    if payload:
                        body_parts.append(payload.decode('utf-8', errors='ignore'))
                elif content_type == "text/html" and not body_parts:
                    # HTML body (only if we don't have plain text)
                    payload = part.get_payload(decode=True)
                    if payload:
                        body_parts.append(payload.decode('utf-8', errors='ignore'))
        else:
            # Not multipart - just get payload
            payload = msg.get_payload(decode=True)
            if payload:
                body_parts.append(payload.decode('utf-8', errors='ignore'))
        
        record["body"] = "\n".join(body_parts) if body_parts else ""
        
        # Extract email addresses
        record["from_name"], record["from_address"] = self._parse_email_address(record["from"])
        
        to_addresses = []
        for addr in record["to"].split(','):
            name, email_addr = self._parse_email_address(addr)
            if email_addr:
                to_addresses.append({"name": name, "address": email_addr})
        record["to_addresses"] = to_addresses
        
        return record
    
    def _extract_msg_data(self, msg, source: str) -> Dict[str, Any]:
        """Extract data from an MSG file."""
        record = {
            "source_file": source,
            "subject": msg.subject,
            "sender": msg.sender,
            "to": msg.to,
            "cc": msg.cc,
            "bcc": msg.bcc,
            "body": msg.body,
            "html_body": getattr(msg, 'htmlBody', None),
            "has_attachments": len(msg.attachments) > 0,
            "attachment_count": len(msg.attachments),
            "attachments": [],
            "headers": {},
        }
        
        # Parse date
        date_str = msg.date
        record["date"] = self._parse_email_date(date_str)
        record["date_str"] = record["date"] or date_str
        
        # Extract attachments info
        for attachment in msg.attachments:
            record["attachments"].append({
                "filename": attachment.longFilename or attachment.shortFilename,
                "size": attachment.dataSize if hasattr(attachment, 'dataSize') else 0
            })
        
        # Parse sender into name and address
        record["from_name"], record["from_address"] = self._parse_email_address(msg.sender)
        
        return record
    
    def _decode_header(self, header_value: str) -> str:
        """Decode email header that may be encoded."""
        if not header_value:
            return ""
        
        try:
            decoded_parts = []
            for part, encoding in decode_header(header_value):
                if isinstance(part, bytes):
                    try:
                        decoded_parts.append(part.decode(encoding or 'utf-8', errors='ignore'))
                    except:
                        decoded_parts.append(part.decode('utf-8', errors='ignore'))
                else:
                    decoded_parts.append(str(part))
            return " ".join(decoded_parts)
        except:
            return str(header_value)
    
    def _safe_decode(self, value) -> str:
        """Safely decode a value to string."""
        if value is None:
            return ""
        if isinstance(value, bytes):
            return value.decode('utf-8', errors='ignore')
        return str(value)
    
    def _parse_email_date(self, date_str: str) -> Optional[str]:
        """Parse email date string to ISO format."""
        if not date_str:
            return None
        
        # Common email date formats
        formats = [
            "%a, %d %b %Y %H:%M:%S %z",     # RFC 2822
            "%d %b %Y %H:%M:%S %z",
            "%a, %d %b %Y %H:%M:%S %Z",
            "%Y-%m-%d %H:%M:%S",
        ]
        
        from datetime import datetime
        import email.utils
        
        # Try email.utils first
        parsed = email.utils.parsedate_to_datetime(date_str)
        if parsed:
            return parsed.strftime("%Y-%m-%d %H:%M:%S")
        
        # Try custom formats
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            except:
                continue
        
        return date_str
    
    def _parse_email_address(self, addr_str: str) -> Tuple[str, str]:
        """Parse email address into name and address components."""
        if not addr_str:
            return "", ""
        
        import email.utils
        name, addr = email.utils.parseaddr(addr_str)
        return name or "", addr or ""