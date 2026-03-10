"""
Vision dashboard generator - creates visualizations for image analysis results.
"""
import json
import csv
from pathlib import Path
from typing import List, Dict, Any, Optional
from collections import Counter
from ..core.utils import html_escape

def generate_vision_report(vision_results: Dict[str, Any], output_dir: Path, 
                          title: str = "Vision Analysis Report") -> Path:
    """
    Generate an HTML report for vision analysis results.
    
    Args:
        vision_results: Results dictionary from vision_processor.process_vision_files()
        output_dir: Directory to write the HTML report
        title: Report title
    
    Returns:
        Path to the generated HTML file
    """
    html_path = output_dir / "vision_report.html"
    
    # Calculate statistics
    total_files = vision_results.get('total_files', 0)
    successful = vision_results.get('successful', 0)
    failed = vision_results.get('failed', 0)
    captions_success = vision_results.get('captions_success', 0)
    captions_failed = vision_results.get('captions_failed', 0)
    
    # Collect detection statistics
    all_detections = []
    all_identifiers = []
    
    for result in vision_results.get('results', []):
        if result.get('status') == 'success':
            all_identifiers.append(result.get('identifier', 'unknown'))
            for det in result.get('detections', []):
                all_detections.append(det.get('label', 'unknown'))
    
    # Top identifiers
    identifier_counts = Counter(all_identifiers)
    top_identifiers = identifier_counts.most_common(10)
    
    # Top detections
    detection_counts = Counter(all_detections)
    top_detections = detection_counts.most_common(10)
    
    # Generate table rows
    table_rows = []
    for i, result in enumerate(vision_results.get('results', []), 1):
        if result.get('status') != 'success':
            continue
        
        status_class = "success" if result.get('caption_status') == 'SUCCESS' else "failed"
        status_icon = "✓" if result.get('caption_status') == 'SUCCESS' else "✗"
        
        file_name = Path(result.get('file', '')).name
        identifier = result.get('identifier', 'unknown')
        confidence = result.get('confidence', 0.0)
        caption = result.get('caption', '')
        caption_display = caption[:80] + "..." if len(caption) > 80 else caption
        
        # Detection summary
        detections = result.get('detections', [])
        det_summary = ", ".join([f"{d['label']}({d['confidence']:.2f})" for d in detections[:3]])
        if len(detections) > 3:
            det_summary += f" +{len(detections)-3} more"
        
        # OCR preview
        ocr_text = result.get('ocr_text', '')
        ocr_preview = ocr_text[:100] + "..." if len(ocr_text) > 100 else ocr_text
        
        # Output links
        output_links = []
        outputs = result.get('output_files', {})
        if outputs.get('annotated'):
            ann_name = Path(outputs['annotated']).name
            output_links.append(f"<a href='annotated/{ann_name}'>Annotated</a>")
        if outputs.get('json'):
            json_name = Path(outputs['json']).name
            output_links.append(f"<a href='json/{json_name}'>JSON</a>")
        
        links_html = " | ".join(output_links) if output_links else "—"
        
        table_rows.append(f'''
<tr class="{status_class}">
    <td>{i}</td>
    <td>{status_icon}</td>
    <td>{html_escape(file_name)}</td>
    <td><strong>{html_escape(identifier)}</strong><br><span class="muted">conf {confidence:.2f}</span></td>
    <td class="caption-cell">{html_escape(caption_display)}</td>
    <td class="det-cell">{html_escape(det_summary)}</td>
    <td class="ocr-cell">{html_escape(ocr_preview)}</td>
    <td>{links_html}</td>
</tr>''')
    
    # Generate HTML
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html_escape(title)}</title>
    <style>
        :root {{
            --bg: #fafafa;
            --card: #ffffff;
            --success: #10b981;
            --success-bg: #d1fae5;
            --failed: #ef4444;
            --failed-bg: #fee2e2;
            --border: #e5e7eb;
            --text: #111827;
            --text-muted: #6b7280;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: var(--bg);
            color: var(--text);
            margin: 0;
            padding: 20px;
            line-height: 1.5;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        
        h1 {{
            font-size: 2em;
            margin-bottom: 0.5em;
        }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }}
        
        .stat-card {{
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        
        .stat-value {{
            font-size: 2.2em;
            font-weight: 600;
            color: var(--text);
        }}
        
        .stat-label {{
            color: var(--text-muted);
            font-size: 0.9em;
            margin-top: 5px;
        }}
        
        .charts-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }}
        
        .chart-card {{
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 20px;
        }}
        
        .chart-card h3 {{
            margin-top: 0;
            margin-bottom: 15px;
            color: var(--text-muted);
            font-size: 1.1em;
        }}
        
        .stat-list {{
            list-style: none;
            padding: 0;
            margin: 0;
        }}
        
        .stat-list li {{
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid var(--border);
        }}
        
        .stat-list li:last-child {{
            border-bottom: none;
        }}
        
        .stat-list .count {{
            font-weight: 600;
            color: var(--text);
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 12px;
            overflow: hidden;
            margin-top: 20px;
            font-size: 14px;
        }}
        
        th, td {{
            padding: 12px 10px;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }}
        
        th {{
            background: #f8fafc;
            font-weight: 600;
            color: var(--text-muted);
            position: sticky;
            top: 0;
        }}
        
        tr.success td {{
            background-color: var(--success-bg);
        }}
        
        tr.failed td {{
            background-color: var(--failed-bg);
        }}
        
        .caption-cell {{
            max-width: 250px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        
        .det-cell {{
            max-width: 200px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        
        .ocr-cell {{
            max-width: 200px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            font-family: monospace;
            font-size: 12px;
        }}
        
        .badge {{
            display: inline-block;
            padding: 4px 8px;
            border-radius: 9999px;
            font-size: 0.85em;
            font-weight: 500;
        }}
        
        .badge.success {{
            background: var(--success-bg);
            color: #065f46;
        }}
        
        .badge.failed {{
            background: var(--failed-bg);
            color: #991b1b;
        }}
        
        .muted {{
            color: var(--text-muted);
            font-size: 0.9em;
        }}
        
        a {{
            color: #2563eb;
            text-decoration: none;
        }}
        
        a:hover {{
            text-decoration: underline;
        }}
        
        .footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid var(--border);
            color: var(--text-muted);
            font-size: 0.9em;
            text-align: center;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{html_escape(title)}</h1>
        <p>Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value">{total_files}</div>
                <div class="stat-label">Total Images</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{successful}</div>
                <div class="stat-label">Successfully Processed</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{failed}</div>
                <div class="stat-label">Failed</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{captions_success}</div>
                <div class="stat-label">Captions Generated</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{captions_failed}</div>
                <div class="stat-label">Captions Failed</div>
            </div>
        </div>
        
        <div class="charts-grid">
            <div class="chart-card">
                <h3>Top Identifiers</h3>
                <ul class="stat-list">
                    {''.join(f'<li><span>{html_escape(k)}</span> <span class="count">{v}</span></li>' 
                            for k, v in top_identifiers)}
                    {'' if top_identifiers else '<li class="muted">No identifiers found</li>'}
                </ul>
            </div>
            <div class="chart-card">
                <h3>Top Detections</h3>
                <ul class="stat-list">
                    {''.join(f'<li><span>{html_escape(k)}</span> <span class="count">{v}</span></li>' 
                            for k, v in top_detections)}
                    {'' if top_detections else '<li class="muted">No detections found</li>'}
                </ul>
            </div>
        </div>
        
        <h2>Detailed Results</h2>
        <div style="overflow-x: auto;">
            <table>
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Status</th>
                        <th>File</th>
                        <th>Identifier</th>
                        <th>Caption</th>
                        <th>Detections</th>
                        <th>OCR Preview</th>
                        <th>Outputs</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(table_rows) if table_rows else '<tr><td colspan="8" style="text-align: center;">No results available</td></tr>'}
                </tbody>
            </table>
        </div>
        
        <div class="footer">
            Generated by Forensic Toolkit Vision Analyzer<br>
            Model: {vision_results.get('model', {}).get('yolo', 'unknown')}
        </div>
    </div>
</body>
</html>'''
    
    html_path.write_text(html, encoding="utf-8")
    return html_path

def write_vision_summary_csv(vision_results: Dict[str, Any], csv_path: Path) -> None:
    """
    Write a CSV summary of vision analysis results.
    
    Args:
        vision_results: Results dictionary from vision_processor.process_vision_files()
        csv_path: Path to write the CSV file
    """
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["File", "Status", "Identifier", "Confidence", "Caption", 
                        "Caption_Status", "Detection_Count", "OCR_Length", "Annotated", "JSON"])
        
        for result in vision_results.get('results', []):
            if result.get('status') != 'success':
                continue
            
            outputs = result.get('output_files', {})
            writer.writerow([
                result.get('file', ''),
                result.get('status', ''),
                result.get('identifier', ''),
                f"{result.get('confidence', 0):.4f}",
                result.get('caption', ''),
                result.get('caption_status', ''),
                len(result.get('detections', [])),
                len(result.get('ocr_text', '')),
                outputs.get('annotated', ''),
                outputs.get('json', '')
            ])

def generate_vision_dashboard(vision_results: Dict[str, Any], output_dir: Path) -> Dict[str, Path]:
    """
    Generate all vision dashboard outputs.
    
    Args:
        vision_results: Results dictionary from vision_processor.process_vision_files()
        output_dir: Directory to write the outputs
    
    Returns:
        Dictionary mapping output types to file paths
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    outputs = {}
    
    # Generate HTML report
    html_path = generate_vision_report(vision_results, output_dir)
    outputs['html'] = html_path
    
    # Generate CSV summary
    csv_path = output_dir / "vision_summary.csv"
    write_vision_summary_csv(vision_results, csv_path)
    outputs['csv'] = csv_path
    
    return outputs