"""
Main orchestration logic – ties together file collection, parsing, analysis, and dashboard generation.
"""
import os, sys, json, pandas as pd
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from .core import file_collector, custody, utils
from .core.media_handler import MEDIA_EXTS
from .parsers import (
    BaseParser,
    WhatsAppHTMLParser,
    CallsParser,
    MessagesParser,
    ImageParser,
    AudioParser,
    VisionParser,
    EmailParser,
    FNBStatementParser,
)
from .dashboard import kpi, chart_data, html_generator, photo_dashboard, audio_dashboard, vision_dashboard, email_dashboard
from .classifiers import classify_table
from .processors import photo_processor, audio_processor, vision_processor, EmailProcessor, FNBProcessor

# Define image extensions for photo processing
IMG_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff', '.webp', '.heic', '.heif'}

# Audio extensions for transcription
AUDIO_EXTS = {'.mp3', '.wav', '.m4a', '.ogg', '.flac', '.aac', '.wma', '.opus',
              '.mp4', '.mov', '.mkv', '.m4v', '.webm', '.3gp', '.avi', '.wmv'}

# Vision extensions for image analysis
VISION_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff', '.webp'}

# Email extensions for email analysis
EMAIL_EXTS = {'.eml', '.msg', '.mbox', '.pst', '.ost', '.mbx'}

# FNB statement extensions
FNB_EXTS = {'.pdf'}

# List of all available parsers
PARSERS: List[BaseParser] = [
    WhatsAppHTMLParser(),
    CallsParser(),
    MessagesParser(),
    ImageParser(),
    AudioParser(),
    VisionParser(),
    EmailParser(),
    FNBStatementParser(),
]

def process_photos_phase(paths: List[str], session_dir: str, quiet: bool = False) -> Optional[Dict]:
    """
    Process photos and generate mapping outputs.
    Returns a dictionary with photo processing results or None if no photos found.
    """
    def logprint(msg: str):
        if not quiet:
            print(msg, flush=True)
    
    # Filter for image files
    image_paths = [p for p in paths if os.path.splitext(p)[1].lower() in IMG_EXTS]
    
    if not image_paths:
        logprint("No image files found for photo processing.")
        return None
    
    logprint(f"Found {len(image_paths)} image files for photo processing.")
    
    # Create photos output directory
    out_photos = os.path.join(session_dir, "photos")
    os.makedirs(out_photos, exist_ok=True)
    
    # Process photos
    return photo_processor.process_photos(image_paths, out_photos, quiet=quiet)

def process_audio_phase(paths: List[str], session_dir: str, quiet: bool = False,
                        model_size: str = "base") -> Optional[Dict]:
    """
    Process audio files and generate transcripts.
    Returns a dictionary with audio processing results or None if no audio files found.
    """
    def logprint(msg: str):
        if not quiet:
            print(msg, flush=True)
    
    # Filter for audio files
    audio_paths = [p for p in paths if os.path.splitext(p)[1].lower() in AUDIO_EXTS]
    
    if not audio_paths:
        logprint("No audio files found for transcription.")
        return None
    
    logprint(f"Found {len(audio_paths)} audio files for transcription.")
    
    # Create audio output directory
    out_audio = os.path.join(session_dir, "audio")
    os.makedirs(out_audio, exist_ok=True)
    
    # Process audio files
    return audio_processor.process_audio_files(
        audio_paths, out_audio, model_size=model_size, quiet=quiet
    )

def process_vision_phase(paths: List[str], session_dir: str, quiet: bool = False,
                         device: str = "auto", yolo_model: str = "yolov8n.pt",
                         fail_fast: bool = False) -> Optional[Dict]:
    """
    Process images with vision analysis (object detection, OCR, captioning).
    Returns a dictionary with vision processing results or None if no images found.
    """
    def logprint(msg: str):
        if not quiet:
            print(msg, flush=True)
    
    # Filter for image files
    image_paths = [p for p in paths if os.path.splitext(p)[1].lower() in VISION_EXTS]
    
    if not image_paths:
        logprint("No image files found for vision processing.")
        return None
    
    logprint(f"Found {len(image_paths)} image files for vision analysis.")
    
    # Create vision output directory
    out_vision = os.path.join(session_dir, "vision")
    os.makedirs(out_vision, exist_ok=True)
    os.makedirs(os.path.join(out_vision, "annotated"), exist_ok=True)
    os.makedirs(os.path.join(out_vision, "json"), exist_ok=True)
    
    # Process images
    return vision_processor.process_vision_files(
        image_paths, out_vision, device=device, 
        yolo_model=yolo_model, fail_fast=fail_fast, quiet=quiet
    )

def process_email_phase(paths: List[str], session_dir: str, quiet: bool = False) -> Optional[Dict]:
    """
    Process email files and generate analysis outputs.
    Returns a dictionary with email processing results or None if no email files found.
    """
    def logprint(msg: str):
        if not quiet:
            print(msg, flush=True)
    
    # Filter for email files
    email_paths = [p for p in paths if os.path.splitext(p)[1].lower() in EMAIL_EXTS]
    
    if not email_paths:
        logprint("No email files found for processing.")
        return None
    
    logprint(f"Found {len(email_paths)} email files for analysis.")
    
    # Create email output directory
    out_email = os.path.join(session_dir, "email")
    os.makedirs(out_email, exist_ok=True)
    
    # Parse all email files
    all_records = []
    parser = EmailParser()
    
    for i, path in enumerate(email_paths, 1):
        try:
            logprint(f"[{i}/{len(email_paths)}] Parsing: {os.path.basename(path)}")
            context = {"log": logprint if not quiet else None}
            records = parser.parse(path, context)
            all_records.extend(records)
            logprint(f"  → {len(records)} messages extracted")
        except Exception as e:
            logprint(f"  Error: {e}")
            custody.chain_log_exception(f"EMAIL PARSE {path}", e)
    
    if not all_records:
        logprint("No email records extracted.")
        return None
    
    # Process emails
    logprint(f"\nProcessing {len(all_records)} email records...")
    processor = EmailProcessor()
    results = processor.process_emails(all_records, Path(out_email), quiet=quiet)
    
    # Generate dashboard
    try:
        # Prepare data for dashboard
        dashboard_data = {
            "statistics": results,
            "networks": results.get('networks', {}),
            "entities": results.get('entities', {}),
            "timeline": results.get('timeline', [])
        }
        email_dashboard.generate_email_dashboard(dashboard_data, Path(out_email))
        logprint(f"Email dashboard generated: {os.path.join(out_email, 'email_dashboard.html')}")
    except Exception as e:
        logprint(f"  Note: Dashboard generation skipped: {e}")
    
    return results

def process_fnb_phase(paths: List[str], session_dir: str, quiet: bool = False,
                     db_path: Optional[str] = None) -> Optional[Dict]:
    """
    Process FNB bank statement PDFs.
    
    Args:
        paths: List of file paths to process
        session_dir: Output directory for the session
        quiet: Suppress console output if True
        db_path: Optional path to SQLite database (default: fnb_statements.db in output dir)
    
    Returns:
        Dictionary with FNB processing results or None if no FNB statements found
    """
    def logprint(msg: str):
        if not quiet:
            print(msg, flush=True)
    
    # Filter for PDF files (will be checked by parser)
    pdf_paths = [p for p in paths if os.path.splitext(p)[1].lower() == '.pdf']
    
    if not pdf_paths:
        logprint("No PDF files found for FNB statement processing.")
        return None
    
    logprint(f"Found {len(pdf_paths)} PDF files to check for FNB statements.")
    
    # Create FNB output directory
    out_fnb = os.path.join(session_dir, "fnb_statements")
    os.makedirs(out_fnb, exist_ok=True)
    
    # Set database path
    if not db_path:
        db_path = os.path.join(out_fnb, "fnb_statements.db")
    
    # Parse all PDFs with FNB parser
    all_records = []
    parser = FNBStatementParser()
    
    for path in pdf_paths:
        try:
            logprint(f"Checking: {os.path.basename(path)}")
            context = {"log": logprint if not quiet else None}
            records = parser.parse(path, context)
            if records:
                all_records.extend(records)
                logprint(f"  → {len(records)} FNB transactions extracted")
        except Exception as e:
            logprint(f"  Not an FNB statement or error: {e}")
    
    if not all_records:
        logprint("No FNB statements found.")
        return None
    
    # Process with FNB processor
    processor = FNBProcessor()
    stats = processor.process_records(all_records, db_path, Path(out_fnb), quiet=quiet)
    
    return stats

def process_inputs(paths: List[str], session_dir: str, quiet: bool = False, 
                   process_photos: bool = False, process_audio: bool = False,
                   process_vision: bool = False, process_email: bool = False,
                   process_fnb: bool = False,
                   audio_model: str = "base",
                   vision_device: str = "auto",
                   vision_yolo: str = "yolov8n.pt",
                   vision_fail_fast: bool = False,
                   fnb_db_path: Optional[str] = None) -> Dict:
    """
    Process input files and generate dashboards.
    
    Args:
        paths: List of file paths to process
        session_dir: Output directory for the session
        quiet: Suppress console output if True
        process_photos: If True, also process image files for photo mapping
        process_audio: If True, also process audio files for transcription
        process_vision: If True, also process images with vision analysis
        process_email: If True, also process email files
        process_fnb: If True, also process FNB bank statement PDFs
        audio_model: Whisper model size (tiny, base, small, medium, large-v3)
        vision_device: Device for vision models ('auto', 'cpu', 'cuda')
        vision_yolo: YOLO model name for object detection
        vision_fail_fast: Exit immediately if vision models fail to load
        fnb_db_path: Custom path for FNB SQLite database
    
    Returns:
        Dictionary with paths to generated outputs
    """
    def logprint(msg: str):
        if not quiet:
            print(msg, flush=True)

    msgs_wa: List[Dict] = []
    msgs_text: List[Dict] = []
    calls: List[Dict] = []
    photos: List[Dict] = []
    audio_files: List[Dict] = []
    vision_files: List[Dict] = []
    email_files: List[Dict] = []
    fnb_files: List[Dict] = []

    if not paths:
        raise RuntimeError("No input files provided.")

    SUB_WA = "whatsapp"
    SUB_TXT = "texts"
    SUB_CALL = "calls"
    SUB_MEDIA = "media"
    SUB_PHOTOS = "photos"
    SUB_AUDIO = "audio"
    SUB_VISION = "vision"
    SUB_EMAIL = "email"
    SUB_FNB = "fnb_statements"
    
    out_whatsapp = os.path.join(session_dir, SUB_WA)
    out_texts   = os.path.join(session_dir, SUB_TXT)
    out_calls   = os.path.join(session_dir, SUB_CALL)
    out_media   = os.path.join(session_dir, SUB_MEDIA)
    out_photos  = os.path.join(session_dir, SUB_PHOTOS)
    out_audio   = os.path.join(session_dir, SUB_AUDIO)
    out_vision  = os.path.join(session_dir, SUB_VISION)
    out_email   = os.path.join(session_dir, SUB_EMAIL)
    out_fnb     = os.path.join(session_dir, SUB_FNB)
    
    for d in [out_whatsapp, out_texts, out_calls, out_media, out_photos, out_audio, out_vision, out_email, out_fnb]:
        os.makedirs(d, exist_ok=True)

    rel_media_prefix = "../" + SUB_MEDIA + "/"
    custody.chain_log(f"WORKER START: {len(paths)} files")

    # Separate files by type for specialized processing
    photo_paths = []
    audio_paths = []
    vision_paths = []
    email_paths = []
    fnb_paths = []
    other_paths = []
    
    for p in paths:
        ext = os.path.splitext(p)[1].lower()
        if process_photos and ext in IMG_EXTS:
            photo_paths.append(p)
        elif process_audio and ext in AUDIO_EXTS:
            audio_paths.append(p)
        elif process_vision and ext in VISION_EXTS:
            vision_paths.append(p)
        elif process_email and ext in EMAIL_EXTS:
            email_paths.append(p)
        elif process_fnb and ext in FNB_EXTS:
            fnb_paths.append(p)
        else:
            other_paths.append(p)
    
    paths_to_process = other_paths
    
    if process_photos:
        logprint(f"Photo processing enabled: {len(photo_paths)} image files will be processed separately.")
    if process_audio:
        logprint(f"Audio processing enabled: {len(audio_paths)} audio files will be processed separately.")
    if process_vision:
        logprint(f"Vision processing enabled: {len(vision_paths)} images will be analyzed.")
    if process_email:
        logprint(f"Email processing enabled: {len(email_paths)} email files will be analyzed.")
    if process_fnb:
        logprint(f"FNB statement processing enabled: {len(fnb_paths)} PDF files will be checked.")

    # Process non-media files (WhatsApp, calls, texts)
    for p in paths_to_process:
        try:
            logprint(f"Processing: {p}")
            custody.chain_log(f"PROCESSING: {p}")

            # ZIP handling
            if p.lower().endswith(".zip"):
                htmls, tables = file_collector.process_zip(p, out_media, log=logprint)
                for tmp_path, arcname in htmls:
                    context = {"rel_media_prefix": rel_media_prefix, "source_hint": arcname, "log": logprint}
                    parser = WhatsAppHTMLParser()
                    rows = parser.parse(tmp_path, context)
                    msgs_wa.extend(rows)
                for tmp_path, arcname in tables:
                    # classify using arcname as hint
                    df = (pd.read_excel(tmp_path, engine='openpyxl') if tmp_path.lower().endswith(".xlsx")
                          else pd.read_csv(tmp_path, encoding=utils.detect_encoding(tmp_path)))
                    kind = classify_table(arcname, df)
                    if kind == "calls":
                        parser = CallsParser()
                        rows = parser.parse_dataframe(arcname, df, {"log": logprint})
                        calls.extend(rows)
                    elif kind == "texts":
                        parser = MessagesParser()
                        rows = parser.parse_dataframe(arcname, df, {"log": logprint, "rel_media_prefix": rel_media_prefix})
                        msgs_text.extend(rows)
                    else:
                        # try both and keep larger set
                        calls_parser = CallsParser()
                        rows_calls = calls_parser.parse_dataframe(arcname, df, {"log": logprint})
                        texts_parser = MessagesParser()
                        rows_texts = texts_parser.parse_dataframe(arcname, df, {"log": logprint, "rel_media_prefix": rel_media_prefix})
                        if len(rows_calls) >= len(rows_texts):
                            calls.extend(rows_calls)
                        else:
                            msgs_text.extend(rows_texts)
                custody.chain_log(f"PROCESSED OK: {p}")
                continue

            # Try each parser
            parsed = False
            for parser in PARSERS:
                if parser.can_parse(p):
                    context = {"rel_media_prefix": rel_media_prefix, "log": logprint}
                    rows = parser.parse(p, context)
                    if isinstance(parser, WhatsAppHTMLParser):
                        msgs_wa.extend(rows)
                    elif isinstance(parser, CallsParser):
                        calls.extend(rows)
                    elif isinstance(parser, MessagesParser):
                        msgs_text.extend(rows)
                    elif isinstance(parser, ImageParser):
                        photos.extend(rows)
                    elif isinstance(parser, AudioParser):
                        audio_files.extend(rows)
                    elif isinstance(parser, VisionParser):
                        vision_files.extend(rows)
                    elif isinstance(parser, EmailParser):
                        email_files.extend(rows)
                    elif isinstance(parser, FNBStatementParser):
                        fnb_files.extend(rows)
                    parsed = True
                    custody.chain_log(f"PROCESSED OK: {p}")
                    break
            if not parsed:
                logprint(f"  Skipped unsupported: {os.path.basename(p)}")
                custody.chain_log(f"SKIPPED (unsupported): {p}", level="warning")

        except Exception as e:
            custody.chain_log_exception(f"PROCESSING {p}", e)
            logprint(f"Error: {p} -> {e}")

    # Process photos if enabled
    photo_results = None
    if process_photos and photo_paths:
        logprint("\n" + "="*60)
        logprint("Starting photo processing phase...")
        logprint("="*60)
        photo_results = process_photos_phase(photo_paths, session_dir, quiet=quiet)
        if photo_results:
            logprint(f"Photo processing complete: {photo_results['photo_count']} images processed")
    elif photos and not process_photos:
        logprint(f"\nFound {len(photos)} images. Use --photos flag to generate maps and GeoJSON.")
        # Generate basic photo CSV even without full processing
        try:
            photo_dashboard.write_photo_csv(photos, os.path.join(out_photos, "photos.csv"))
        except (ImportError, AttributeError):
            logprint("  Note: photo_dashboard module not fully configured")

    # Process audio if enabled
    audio_results = None
    if process_audio and audio_paths:
        logprint("\n" + "="*60)
        logprint("Starting audio transcription phase...")
        logprint("="*60)
        audio_results = process_audio_phase(audio_paths, session_dir, quiet=quiet, model_size=audio_model)
        if audio_results:
            logprint(f"Audio processing complete: {audio_results['successful']}/{audio_results['total_files']} files transcribed")
            
            # Generate audio dashboard
            try:
                audio_dashboard.generate_audio_dashboard(audio_results, Path(out_audio))
                logprint(f"Audio dashboard generated: {os.path.join(out_audio, 'audio_report.html')}")
            except (ImportError, AttributeError) as e:
                logprint(f"  Note: audio_dashboard generation skipped: {e}")
    elif audio_files and not process_audio:
        logprint(f"\nFound {len(audio_files)} audio files. Use --audio flag to transcribe them.")

    # Process vision if enabled
    vision_results = None
    if process_vision and vision_paths:
        logprint("\n" + "="*60)
        logprint("Starting vision analysis phase...")
        logprint("="*60)
        vision_results = process_vision_phase(
            vision_paths, session_dir, quiet=quiet,
            device=vision_device, yolo_model=vision_yolo,
            fail_fast=vision_fail_fast
        )
        if vision_results:
            logprint(f"Vision analysis complete: {vision_results['successful']}/{vision_results['total_files']} images processed, "
                     f"{vision_results.get('captions_success', 0)} captions")
            
            # Generate vision dashboard
            try:
                vision_dashboard.generate_vision_dashboard(vision_results, Path(out_vision))
                logprint(f"Vision dashboard generated: {os.path.join(out_vision, 'vision_report.html')}")
            except (ImportError, AttributeError) as e:
                logprint(f"  Note: vision_dashboard generation skipped: {e}")
    elif vision_files and not process_vision:
        logprint(f"\nFound {len(vision_files)} images. Use --vision flag to run object detection and captioning.")

    # Process email if enabled
    email_results = None
    if process_email and email_paths:
        logprint("\n" + "="*60)
        logprint("Starting email analysis phase...")
        logprint("="*60)
        email_results = process_email_phase(email_paths, session_dir, quiet=quiet)
        if email_results:
            logprint(f"Email analysis complete: {email_results['total_emails']} messages processed")
    elif email_files and not process_email:
        logprint(f"\nFound {len(email_files)} email files. Use --email flag to analyze them.")

    # Process FNB statements if enabled
    fnb_results = None
    if process_fnb and fnb_paths:
        logprint("\n" + "="*60)
        logprint("Starting FNB statement analysis phase...")
        logprint("="*60)
        fnb_results = process_fnb_phase(fnb_paths, session_dir, quiet=quiet, db_path=fnb_db_path)
        if fnb_results:
            logprint(f"FNB analysis complete: {fnb_results.get('total_transactions', 0)} transactions processed")
    elif fnb_files and not process_fnb:
        logprint(f"\nFound {len(fnb_files)} potential FNB statements. Use --fnb flag to analyze them.")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    outputs = {
        "whatsapp_html": None, 
        "text_messages": None, 
        "calls": None,
        "photos": photo_results,
        "audio": audio_results,
        "vision": vision_results,
        "email": email_results,
        "fnb": fnb_results,
    }

    if msgs_wa:
        msgs_wa.sort(key=lambda x: x["timestamp"])
        k = kpi.kpis_from_messages(msgs_wa)
        ch = chart_data.agg_messages_for_charts(msgs_wa)
        out_html = os.path.join(session_dir, SUB_WA, f"dashboard_whatsapp_{stamp}.html")
        html_generator.write_dashboard_html(out_html, "WhatsApp Messages Dashboard", k, ch, msgs_wa, is_calls=False)
        outputs["whatsapp_html"] = out_html
        logprint(f"WhatsApp dashboard: {out_html}")
        pd.DataFrame(msgs_wa).to_csv(os.path.join(session_dir, SUB_WA, f"whatsapp_{stamp}.csv"), index=False, encoding="utf-8")
        custody.chain_log(f"EXPORT DASHBOARD (WhatsApp): {out_html} (rows={len(msgs_wa)})")

    if msgs_text:
        msgs_text.sort(key=lambda x: x["timestamp"])
        k = kpi.kpis_from_messages(msgs_text)
        ch = chart_data.agg_messages_for_charts(msgs_text)
        out_html = os.path.join(session_dir, SUB_TXT, f"dashboard_texts_{stamp}.html")
        html_generator.write_dashboard_html(out_html, "Text Messages Dashboard", k, ch, msgs_text, is_calls=False)
        outputs["text_messages"] = out_html
        logprint(f"Text Messages dashboard: {out_html}")
        pd.DataFrame(msgs_text).to_csv(os.path.join(session_dir, SUB_TXT, f"texts_{stamp}.csv"), index=False, encoding="utf-8")
        custody.chain_log(f"EXPORT DASHBOARD (Texts): {out_html} (rows={len(msgs_text)})")

    if calls:
        calls.sort(key=lambda x: x["timestamp"])
        k = kpi.kpis_from_calls(calls)
        ch = chart_data.agg_calls_for_charts(calls)
        out_html = os.path.join(session_dir, SUB_CALL, f"dashboard_calls_{stamp}.html")
        html_generator.write_dashboard_html(out_html, "Call History Dashboard", k, ch, calls, is_calls=True)
        outputs["calls"] = out_html
        logprint(f"Call History dashboard: {out_html}")
        pd.DataFrame(calls).to_csv(os.path.join(session_dir, SUB_CALL, f"calls_{stamp}.csv"), index=False, encoding="utf-8")
        custody.chain_log(f"EXPORT DASHBOARD (Calls): {out_html} (rows={len(calls)})")

    if not any([outputs["whatsapp_html"], outputs["text_messages"], outputs["calls"], 
                outputs["photos"], outputs["audio"], outputs["vision"], 
                outputs["email"], outputs["fnb"]]):
        custody.chain_log("WORKER COMPLETE (no output)", level="warning")
        raise RuntimeError("No messages, calls, photos, audio, images, emails, or FNB statements extracted from the provided files.")

    # Summary
    logprint("\n" + "="*60)
    logprint("PROCESSING SUMMARY")
    logprint("="*60)
    if msgs_wa:
        logprint(f"WhatsApp messages: {len(msgs_wa)}")
    if msgs_text:
        logprint(f"Text messages: {len(msgs_text)}")
    if calls:
        logprint(f"Call records: {len(calls)}")
    if photo_results:
        logprint(f"Photos processed: {photo_results['photo_count']} (GPS: {photo_results['gps_count']})")
    elif photos:
        logprint(f"Photos found: {len(photos)} (use --photos to generate maps)")
    if audio_results:
        logprint(f"Audio files transcribed: {audio_results['successful']}/{audio_results['total_files']}")
    elif audio_files:
        logprint(f"Audio files found: {len(audio_files)} (use --audio to transcribe)")
    if vision_results:
        logprint(f"Vision analysis: {vision_results['successful']}/{vision_results['total_files']} images, "
                 f"{vision_results.get('captions_success', 0)} captions")
    elif vision_files:
        logprint(f"Images found: {len(vision_files)} (use --vision for object detection and captioning)")
    if email_results:
        logprint(f"Email messages: {email_results['total_emails']} (senders: {email_results['unique_senders']})")
    elif email_files:
        logprint(f"Email files found: {len(email_files)} (use --email to analyze)")
    if fnb_results:
        logprint(f"FNB transactions: {fnb_results.get('total_transactions', 0)} (net flow: R{fnb_results.get('net_flow', 0):,.2f})")
    elif fnb_files:
        logprint(f"Potential FNB statements found: {len(fnb_files)} (use --fnb to analyze)")
    logprint("="*60)

    custody.chain_log("WORKER COMPLETE (success)")
    return outputs