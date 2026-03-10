"""
Command‑line interface for the forensic toolkit.
"""
import os, sys, argparse, glob
from datetime import datetime
from .core import file_collector, custody
from .orchestrator import process_inputs

SUB_LOGS = "logs"
SUB_WA = "whatsapp"
SUB_TXT = "texts"
SUB_CALL = "calls"
SUB_MEDIA = "media"
SUB_PHOTOS = "photos"
SUB_AUDIO = "audio"
SUB_VISION = "vision"
SUB_EMAIL = "email"
SUB_FNB = "fnb_statements"

def parse_args():
    p = argparse.ArgumentParser(description="Forensic Toolkit - Process evidence files and generate dashboards.")
    
    # Input selection (mutually exclusive)
    mx = p.add_mutually_exclusive_group(required=True)
    mx.add_argument("-i", "--input", dest="inputs", action="append",
                    help="Input file or glob pattern (repeatable). Example: -i chat.html -i calls.xlsx -i D:\\evidence\\*.zip")
    mx.add_argument("-d", "--dir", dest="input_dir",
                    help="Process a folder of evidence. Recurses by default.")
    
    # Directory scanning options
    p.add_argument("--no-recursive", action="store_true",
                   help="With --dir, only process the top-level of the folder.")
    
    # Output options
    p.add_argument("-o", "--output", dest="out_dir", required=True,
                   help="Parent output folder (a timestamped session subfolder will be created inside).")
    p.add_argument("--session-name", default=None,
                   help="Optional custom session folder name (default: run_YYYYmmdd_HHMMSS). Use '.' to write directly to output folder.")
    
    # Processing flags
    p.add_argument("--photos", action="store_true", 
                   help="Process images and generate photo maps with GPS data")
    p.add_argument("--audio", action="store_true", 
                   help="Transcribe audio/video files with Whisper")
    p.add_argument("--audio-model", default="base", 
                   choices=["tiny", "base", "small", "medium", "large-v3"],
                   help="Whisper model size (default: base). Larger models are more accurate but slower.")
    
    # Vision processing flags
    p.add_argument("--vision", action="store_true", 
                   help="Run vision analysis (object detection, OCR, AI captioning) on images")
    p.add_argument("--vision-device", default="auto", choices=["auto", "cpu", "cuda"],
                   help="Device for vision models (default: auto)")
    p.add_argument("--vision-yolo", default="yolov8n.pt",
                   help="YOLO model name for object detection (default: yolov8n.pt)")
    p.add_argument("--vision-fail-fast", action="store_true",
                   help="Exit immediately if vision models fail to load")
    
    # Email processing flags
    p.add_argument("--email", action="store_true",
                   help="Process email files (EML, MSG, MBOX, PST, OST)")
    
    # FNB statement processing flags
    p.add_argument("--fnb", action="store_true",
                   help="Process FNB bank statement PDFs")
    p.add_argument("--fnb-db", default=None,
                   help="Custom path for FNB SQLite database (default: fnb_statements.db in output folder)")
    
    # Forensic options
    p.add_argument("--skip-manifest", action="store_true",
                   help="Skip hashing inputs & writing manifest.json (faster, but less forensically rigorous).")
    p.add_argument("--quiet", action="store_true",
                   help="Reduce console output.")
    
    return p.parse_args()

def main():
    args = parse_args()
    
    # Validate output directory
    if not os.path.isdir(args.out_dir):
        os.makedirs(args.out_dir, exist_ok=True)

    # Create session directory
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if args.session_name == ".":
        session_dir = args.out_dir
        print(f"Using output directory directly: {session_dir}")
    else:
        session_name = args.session_name or f"run_{stamp}"
        session_dir = os.path.join(args.out_dir, session_name)
    
    os.makedirs(session_dir, exist_ok=True)
    
    # Create all subdirectories
    for sub in [SUB_WA, SUB_TXT, SUB_CALL, SUB_MEDIA, SUB_LOGS, 
                SUB_PHOTOS, SUB_AUDIO, SUB_VISION, SUB_EMAIL, SUB_FNB]:
        os.makedirs(os.path.join(session_dir, sub), exist_ok=True)

    # Initialize chain of custody logging
    custody.init_chain_logger(session_dir)
    custody.chain_log(f"SESSION START user={os.getlogin()} output={session_dir}")

    # Collect input files
    if args.input_dir:
        paths = file_collector.collect_inputs_from_dir(args.input_dir, recursive=not args.no_recursive)
        if not paths:
            print(f"Error: No supported files found in directory: {args.input_dir}", file=sys.stderr)
            sys.exit(2)
        print(f"Discovered {len(paths)} evidence file(s) under {args.input_dir}")
    else:
        paths = file_collector.expand_inputs(args.inputs or [])
        if not paths:
            print("Error: No input files matched the provided patterns.", file=sys.stderr)
            sys.exit(2)
        print(f"Queued {len(paths)} evidence file(s) from -i/--input")

    # Log all input files
    for p in paths:
        custody.chain_log(f"INPUT QUEUED: {p}")

    # Generate manifest (unless skipped)
    if not args.skip_manifest:
        custody.write_manifest(session_dir, paths)

    # Display processing options
    print("\n" + "="*60)
    print("PROCESSING OPTIONS")
    print("="*60)
    print(f"Photos processing: {'Enabled' if args.photos else 'Disabled'}")
    print(f"Audio transcription: {'Enabled' if args.audio else 'Disabled'}")
    if args.audio:
        print(f"  Audio model: {args.audio_model}")
    print(f"Vision analysis: {'Enabled' if args.vision else 'Disabled'}")
    if args.vision:
        print(f"  Vision device: {args.vision_device}")
        print(f"  YOLO model: {args.vision_yolo}")
    print(f"Email analysis: {'Enabled' if args.email else 'Disabled'}")
    print(f"FNB statement analysis: {'Enabled' if args.fnb else 'Disabled'}")
    print("="*60 + "\n")

    # Process files
    try:
        outputs = process_inputs(
            paths, 
            session_dir, 
            quiet=args.quiet,
            process_photos=args.photos,
            process_audio=args.audio,
            process_vision=args.vision,
            process_email=args.email,
            process_fnb=args.fnb,
            audio_model=args.audio_model,
            vision_device=args.vision_device,
            vision_yolo=args.vision_yolo,
            vision_fail_fast=args.vision_fail_fast,
            fnb_db_path=args.fnb_db
        )
        
        # Display results
        print("\n" + "="*60)
        print("DASHBOARDS GENERATED")
        print("="*60)
        for k, v in outputs.items():
            if v and k not in ['photos', 'audio', 'vision', 'email', 'fnb']:
                print(f"{k}: {v}")
            elif k == 'photos' and v:
                print(f"Photos: {v.get('photo_count', 0)} processed, {v.get('gps_count', 0)} GPS-tagged")
            elif k == 'audio' and v:
                print(f"Audio: {v.get('successful', 0)}/{v.get('total_files', 0)} transcribed")
            elif k == 'vision' and v:
                print(f"Vision: {v.get('successful', 0)}/{v.get('total_files', 0)} images, "
                      f"{v.get('captions_success', 0)} captions")
            elif k == 'email' and v:
                print(f"Email: {v.get('total_emails', 0)} messages, {v.get('unique_senders', 0)} senders")
            elif k == 'fnb' and v:
                print(f"FNB: {v.get('total_transactions', 0)} transactions, "
                      f"net flow: R{v.get('net_flow', 0):,.2f}")
        
        print(f"\nSession folder:\n  {session_dir}")
        print(f"Chain of custody log:\n  {os.path.join(session_dir, SUB_LOGS, 'chain_of_custody.log')}")
        sys.exit(0)
        
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        print(f"See chain log for details: {os.path.join(session_dir, SUB_LOGS, 'chain_of_custody.log')}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()