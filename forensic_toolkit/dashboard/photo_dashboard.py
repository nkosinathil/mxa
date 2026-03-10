"""
Photo dashboard generator - creates map visualizations and photo tables.
"""
import json
import csv
from pathlib import Path
from typing import List, Dict, Any
from ..core.utils import html_escape

def write_photo_csv(records: List[Dict[str, Any]], csv_path: Path):
    """Write photo inventory to CSV."""
    cols = ['file_path', 'filename', 'size_bytes', 'sha256', 'timestamp', 
            'exif_make', 'exif_model', 'gps_lat', 'gps_lon', 'has_gps']
    
    with csv_path.open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL,
                       escapechar='\\', doublequote=True, lineterminator='\n')
        w.writerow(cols)
        for r in records:
            w.writerow([str(r.get(c, '')) for c in cols])

def write_photo_geojson(records: List[Dict[str, Any]], geojson_path: Path):
    """Write GPS-tagged photos as GeoJSON."""
    features = []
    for r in records:
        if r.get('gps_lat') is not None and r.get('gps_lon') is not None:
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [r['gps_lon'], r['gps_lat']]
                },
                "properties": {
                    "file_path": r['file_path'],
                    "filename": r['filename'],
                    "timestamp": r.get('timestamp', ''),
                    "make": r.get('exif_make', ''),
                    "model": r.get('exif_model', ''),
                }
            })
    
    data = {"type": "FeatureCollection", "features": features}
    geojson_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

def write_photo_table(records: List[Dict[str, Any]], html_path: Path, title: str = "Photo Inventory"):
    """Generate HTML table of photos."""
    rows_html = []
    for r in records:
        gps_str = f"{r.get('gps_lat', 'N/A'):.6f}, {r.get('gps_lon', 'N/A'):.6f}" if r.get('gps_lat') else "No GPS"
        
        rows_html.append(f"""
<tr>
  <td>{html_escape(r['filename'])}</td>
  <td>{html_escape(r.get('timestamp', ''))}</td>
  <td>{html_escape(r.get('exif_make', ''))} {html_escape(r.get('exif_model', ''))}</td>
  <td>{html_escape(gps_str)}</td>
  <td><span class="badge {'gps-yes' if r.get('gps_lat') else 'gps-no'}">{'Yes' if r.get('gps_lat') else 'No'}</span></td>
</tr>""")
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{html_escape(title)}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #fafafa; }}
        h1 {{ color: #111827; }}
        table {{ width: 100%; border-collapse: collapse; background: white; }}
        th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #e5e7eb; }}
        th {{ background: #f3f4f6; }}
        .badge {{ padding: 4px 8px; border-radius: 12px; font-size: 12px; }}
        .gps-yes {{ background: #d1fae5; color: #065f46; }}
        .gps-no {{ background: #fee2e2; color: #991b1b; }}
        .stats {{ margin: 20px 0; padding: 15px; background: white; border-radius: 8px; }}
    </style>
</head>
<body>
    <h1>{html_escape(title)}</h1>
    <div class="stats">
        <strong>Total Photos:</strong> {len(records)} | 
        <strong>GPS-Tagged:</strong> {sum(1 for r in records if r.get('gps_lat'))}
    </div>
    <table>
        <thead>
            <tr>
                <th>Filename</th>
                <th>Date Taken</th>
                <th>Camera</th>
                <th>GPS Coordinates</th>
                <th>Has GPS</th>
            </tr>
        </thead>
        <tbody>
            {''.join(rows_html)}
        </tbody>
    </table>
</body>
</html>"""
    
    html_path.write_text(html, encoding='utf-8')

def write_photo_map(records: List[Dict[str, Any]], map_path: Path, title: str = "Photo Map"):
    """Generate Leaflet map of GPS-tagged photos."""
    gps_records = [r for r in records if r.get('gps_lat') is not None and r.get('gps_lon') is not None]
    
    if gps_records:
        lat = sum(r['gps_lat'] for r in gps_records) / len(gps_records)
        lon = sum(r['gps_lon'] for r in gps_records) / len(gps_records)
        zoom = 12
    else:
        lat, lon, zoom = 0.0, 0.0, 2
    
    markers = []
    for r in gps_records:
        popup = f"""
<div style="min-width:200px">
    <strong>{html_escape(r['filename'])}</strong><br>
    {html_escape(r.get('timestamp', ''))}<br>
    {html_escape(r.get('exif_make', ''))} {html_escape(r.get('exif_model', ''))}<br>
    {r['gps_lat']:.6f}, {r['gps_lon']:.6f}
</div>""".strip()
        markers.append(f"L.marker([{r['gps_lat']:.6f}, {r['gps_lon']:.6f}]).addTo(map).bindPopup({json.dumps(popup)});")
    
    note = "" if gps_records else "<p>No GPS-tagged photos found.</p>"
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{html_escape(title)}</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        body {{ margin: 0; padding: 20px; font-family: Arial, sans-serif; }}
        #map {{ height: calc(100vh - 100px); border-radius: 8px; }}
        h1 {{ margin-top: 0; }}
    </style>
</head>
<body>
    <h1>{html_escape(title)}</h1>
    {note}
    <div id="map"></div>
    <script>
        var map = L.map('map').setView([{lat:.6f}, {lon:.6f}], {zoom});
        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            attribution: '&copy; OpenStreetMap contributors'
        }}).addTo(map);
        {''.join(markers)}
    </script>
</body>
</html>"""
    
    map_path.write_text(html, encoding='utf-8')