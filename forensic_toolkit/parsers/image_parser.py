"""
Parser for image files to extract EXIF and GPS data.
"""
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from PIL import Image, ExifTags
from ..core.custody import chain_log, chain_log_exception
from .base import BaseParser

try:
    import exifread
    EXIFREAD_OK = True
except ImportError:
    EXIFREAD_OK = False

IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff', '.webp', '.heic', '.heif'}

class ImageParser(BaseParser):
    """Parser for image files to extract EXIF metadata and GPS coordinates."""
    
    def can_parse(self, file_path: str) -> bool:
        ext = os.path.splitext(file_path)[1].lower()
        return ext in IMAGE_EXTS
    
    def parse(self, file_path: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract EXIF data from an image file.
        Returns a list with a single record containing image metadata.
        """
        log = context.get("log")
        try:
            p = Path(file_path)
            st = p.stat()
            
            # Extract EXIF data
            exif_data = self._get_exif(p)
            
            # Build record
            record = {
                "file_path": str(p.resolve()),
                "filename": p.name,
                "size_bytes": st.st_size,
                "sha256": self._sha256_file(p),
                "timestamp": self._parse_exif_datetime(exif_data.get('exif_datetime_original', '')),
                "exif_make": exif_data.get('exif_make', ''),
                "exif_model": exif_data.get('exif_model', ''),
                "gps_lat": exif_data.get('gps_lat'),
                "gps_lon": exif_data.get('gps_lon'),
                "has_gps": exif_data.get('gps_lat') is not None and exif_data.get('gps_lon') is not None,
            }
            
            if log:
                log(f"Parsed image: {p.name} (GPS: {record['has_gps']})")
            chain_log(f"PARSED Image: {file_path} (GPS: {record['has_gps']})")
            
            return [record]
            
        except Exception as e:
            if log:
                log(f"Image parse failed: {os.path.basename(file_path)} -> {e}")
            chain_log_exception(f"PARSE Image {file_path}", e)
            return []
    
    def _sha256_file(self, p: Path) -> str:
        """Calculate SHA256 hash of file."""
        import hashlib
        h = hashlib.sha256()
        with p.open('rb') as f:
            for chunk in iter(lambda: f.read(1024*1024), b''):
                h.update(chunk)
        return h.hexdigest()
    
    def _get_exif(self, p: Path) -> Dict[str, Any]:
        """Extract EXIF data including GPS coordinates."""
        out = {
            'exif_make': '',
            'exif_model': '',
            'exif_datetime_original': '',
            'gps_lat': None,
            'gps_lon': None
        }
        
        # Try Pillow first
        try:
            with Image.open(str(p)) as im:
                ex = im.getexif()
                if ex:
                    TAGS = {v: k for k, v in ExifTags.TAGS.items()}
                    out['exif_make'] = str(ex.get(TAGS.get('Make', -1)) or '')
                    out['exif_model'] = str(ex.get(TAGS.get('Model', -1)) or '')
                    out['exif_datetime_original'] = str(ex.get(TAGS.get('DateTimeOriginal', -1)) or '')
                    
                    # Extract GPS info
                    gps_info = ex.get(TAGS.get('GPSInfo', -1))
                    if gps_info:
                        from PIL import ExifTags as _ET
                        g = {_ET.GPSTAGS.get(k, k): v for k, v in gps_info.items()}
                        
                        def _rat(x):
                            try:
                                return float(x[0]) / float(x[1])
                            except:
                                try:
                                    return float(x)
                                except:
                                    return None
                        
                        def _deg(dms, ref):
                            try:
                                d = _rat(dms[0]) or 0
                                m = _rat(dms[1]) or 0
                                s = _rat(dms[2]) or 0
                                sign = -1 if str(ref).upper() in ('S', 'W') else 1
                                return sign * (d + m/60 + s/3600)
                            except:
                                return None
                        
                        lat = _deg(g.get('GPSLatitude'), g.get('GPSLatitudeRef')) if 'GPSLatitude' in g and 'GPSLatitudeRef' in g else None
                        lon = _deg(g.get('GPSLongitude'), g.get('GPSLongitudeRef')) if 'GPSLongitude' in g and 'GPSLongitudeRef' in g else None
                        
                        if lat is not None and lon is not None:
                            out['gps_lat'] = float(f'{lat:.8f}')
                            out['gps_lon'] = float(f'{lon:.8f}')
        except Exception:
            pass
        
        # Fallback to exifread if GPS not found
        if (out['gps_lat'] is None or out['gps_lon'] is None) and EXIFREAD_OK:
            try:
                with p.open('rb') as f:
                    tags = exifread.process_file(f, details=False)
                
                lat_ref = str(tags.get('GPS GPSLatitudeRef', '')).strip()
                lon_ref = str(tags.get('GPS GPSLongitudeRef', '')).strip()
                lat_vals = tags.get('GPS GPSLatitude')
                lon_vals = tags.get('GPS GPSLongitude')
                
                def _ratlist_to_deg(v):
                    parts = []
                    for part in str(v).strip('[]').split(','):
                        part = part.strip()
                        if not part:
                            continue
                        if '/' in part:
                            a, b = part.split('/', 1)
                            parts.append(float(a) / float(b))
                        else:
                            parts.append(float(part))
                    if not parts:
                        return None
                    d, m, s = (parts + [0, 0, 0])[:3]
                    return d + m/60 + s/3600
                
                if lat_vals and lon_vals and lat_ref and lon_ref:
                    lat = _ratlist_to_deg(lat_vals)
                    lon = _ratlist_to_deg(lon_vals)
                    if lat is not None and lon is not None:
                        if lat_ref.upper() == 'S':
                            lat = -lat
                        if lon_ref.upper() == 'W':
                            lon = -lon
                        out['gps_lat'] = float(f'{lat:.8f}')
                        out['gps_lon'] = float(f'{lon:.8f}')
                
                # Fill missing EXIF data
                if not out['exif_datetime_original']:
                    out['exif_datetime_original'] = str(tags.get('EXIF DateTimeOriginal', ''))
                if not out['exif_make']:
                    out['exif_make'] = str(tags.get('Image Make', ''))
                if not out['exif_model']:
                    out['exif_model'] = str(tags.get('Image Model', ''))
            except Exception:
                pass
        
        return out
    
    def _parse_exif_datetime(self, dt_str: str) -> str:
        """Parse EXIF datetime string to standard format."""
        if not dt_str:
            return ''
        try:
            # Replace colon in date part with hyphen
            if ':' in dt_str[:10]:
                dt_str = dt_str.replace(':', '-', 2)
            from datetime import datetime
            for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d'):
                try:
                    return datetime.strptime(dt_str, fmt).isoformat()
                except:
                    continue
        except:
            pass
        return dt_str