"""
Photo processing module - coordinates image parsing and dashboard generation.
"""
import os
from pathlib import Path
from typing import List, Dict, Any
from ..parsers.image_parser import ImageParser
from ..dashboard import photo_dashboard
from ..core.custody import chain_log

def process_photos(input_paths: List[str], output_dir: str, quiet: bool = False):
    """Process a list of image files and generate photo dashboards."""
    def logprint(msg: str):
        if not quiet:
            print(msg, flush=True)
    
    logprint(f"Processing {len(input_paths)} image files...")
    
    # Create output directories
    out_dir = Path(output_dir)
    thumb_dir = out_dir / "thumbnails"
    thumb_dir.mkdir(parents=True, exist_ok=True)
    
    # Parse all images
    parser = ImageParser()
    records = []
    
    for path in input_paths:
        try:
            logprint(f"Processing: {path}")
            context = {"log": logprint}
            results = parser.parse(path, context)
            records.extend(results)
        except Exception as e:
            logprint(f"Error processing {path}: {e}")
            chain_log(f"ERROR processing image {path}: {e}", level="error")
    
    # Generate outputs
    photo_dashboard.write_photo_csv(records, out_dir / "photos.csv")
    photo_dashboard.write_photo_geojson(records, out_dir / "photos.geojson")
    photo_dashboard.write_photo_table(records, out_dir / "photos.html", "Photo Inventory")
    photo_dashboard.write_photo_map(records, out_dir / "map.html", "Photo Map")
    
    logprint(f"\n=== Photo Processing Complete ===")
    logprint(f"Total images: {len(records)}")
    logprint(f"GPS-tagged: {sum(1 for r in records if r.get('gps_lat'))}")
    logprint(f"Output directory: {output_dir}")
    
    return {
        "photo_count": len(records),
        "gps_count": sum(1 for r in records if r.get('gps_lat')),
        "output_dir": output_dir
    }