"""
Audio dashboard generator - creates visualizations and summaries for transcribed audio.
"""
import json
import csv
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from ..core.utils import html_escape

def generate_audio_report(audio_results: Dict[str, Any], output_dir: Path, title: str = "Audio Transcription Report") -> Path:
    """
    Generate an HTML report for audio transcription results.
    
    Args:
        audio_results: Results dictionary from audio_processor.process_audio_files()
        output_dir: Directory to write the HTML report
        title: Report title
    
    Returns:
        Path to the generated HTML file
    """
    html_path = output_dir / "audio_report.html"
    
    # Calculate statistics
    total_files = audio_results.get('total_files', 0)
    successful = audio_results.get('successful', 0)
    failed = audio_results.get('failed', 0)
    
    # Collect language statistics
    languages = {}
    for result in audio_results.get('results', []):
        if result.get('status') == 'success' and result.get('language'):
            lang = result['language']
            languages[lang] = languages.get(lang, 0) + 1
    
    # Generate table rows
    table_rows = []
    for result in audio_results.get('results', []):
        status_class = "success" if result.get('status') == 'success' else "failed"
        status_text = "✓" if result.get('status') == 'success' else "✗"
        
        file_name = Path(result.get('file', '')).name
        language = result.get('language', '')
        probability = result.get('language_probability', 0)
        duration = result.get('duration', 0)
        
        # Format duration as MM:SS
        if duration:
            minutes = int(duration // 60)
            seconds = int(duration % 60)
            duration_str = f"{minutes}:{seconds:02d}"
        else:
            duration_str = ""
        
        # Get output file links
        output_links = []
        outputs = result.get('output_files', {})
        if outputs.get('txt'):
            output_links.append(f"<a href='{Path(outputs['txt']).name}'>TXT</a>")
        if outputs.get('json'):
            output_links.append(f"<a href='{Path(outputs['json']).name}'>JSON</a>")
        
        links_html = " | ".join(output_links) if output_links else "—"
        
        table_rows.append(f"""
<tr class="{status_class}">
    <td>{status_text}</td>
    <td>{html_escape(file_name)}</td>
    <td>{html_escape(language)}</td>
    <td>{probability:.2f}</td>
    <td>{duration_str}</td>
    <td>{links_html}</td>
</tr>""")
    
    # Language distribution chart data (JSON for potential charting library)
    lang_data = [{"language": lang, "count": count} for lang, count in languages.items()]
    
    # Language grid HTML
    language_grid_html = ""
    if languages:
        language_items = []
        for lang, count in languages.items():
            language_items.append(f"""
                <div class="language-item">
                    <span class="language-name">{html_escape(lang)}</span>
                    <span class="language-count">{count}</span>
                </div>
            """)
        language_grid_html = f"""
        <div class="language-stats">
            <h2>Language Distribution</h2>
            <div class="language-grid">
                {''.join(language_items)}
            </div>
        </div>
        """
    
    html = f"""<!DOCTYPE html>
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
            max-width: 1200px;
            margin: 0 auto;
        }}
        
        h1 {{
            font-size: 2em;
            margin-bottom: 0.5em;
        }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
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
            font-size: 2.5em;
            font-weight: 600;
            color: var(--text);
        }}
        
        .stat-label {{
            color: var(--text-muted);
            font-size: 0.9em;
            margin-top: 5px;
        }}
        
        .language-stats {{
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 20px;
            margin: 30px 0;
        }}
        
        .language-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin-top: 15px;
        }}
        
        .language-item {{
            display: flex;
            justify-content: space-between;
            padding: 8px 12px;
            background: var(--bg);
            border-radius: 8px;
        }}
        
        .language-name {{
            font-weight: 500;
        }}
        
        .language-count {{
            color: var(--text-muted);
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 12px;
            overflow: hidden;
        }}
        
        th, td {{
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }}
        
        th {{
            background: #f8fafc;
            font-weight: 600;
            color: var(--text-muted);
        }}
        
        tr.success td {{
            background-color: var(--success-bg);
        }}
        
        tr.failed td {{
            background-color: var(--failed-bg);
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
                <div class="stat-label">Total Files</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{successful}</div>
                <div class="stat-label">Successfully Transcribed</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{failed}</div>
                <div class="stat-label">Failed</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{len(languages)}</div>
                <div class="stat-label">Languages Detected</div>
            </div>
        </div>
        
        {language_grid_html}
        
        <h2>Transcription Results</h2>
        <table>
            <thead>
                <tr>
                    <th>Status</th>
                    <th>File</th>
                    <th>Language</th>
                    <th>Confidence</th>
                    <th>Duration</th>
                    <th>Outputs</th>
                </tr>
            </thead>
            <tbody>
                {''.join(table_rows) if table_rows else '<tr><td colspan="6" style="text-align: center;">No results available</td></tr>'}
            </tbody>
        </table>
        
        <div class="footer">
            Generated by Forensic Toolkit Audio Transcriber<br>
            Model: {audio_results.get('model', 'unknown')}
        </div>
    </div>
</body>
</html>"""
    
    html_path.write_text(html, encoding="utf-8")
    return html_path

def write_audio_summary_csv(audio_results: Dict[str, Any], csv_path: Path) -> None:
    """
    Write a CSV summary of audio transcription results.
    
    Args:
        audio_results: Results dictionary from audio_processor.process_audio_files()
        csv_path: Path to write the CSV file
    """
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["File", "Status", "Language", "Confidence", "Duration", "Output_TXT", "Output_JSON"])
        
        for result in audio_results.get('results', []):
            outputs = result.get('output_files', {})
            writer.writerow([
                result.get('file', ''),
                result.get('status', ''),
                result.get('language', ''),
                f"{result.get('language_probability', 0):.3f}" if result.get('language_probability') else '',
                result.get('duration', ''),
                outputs.get('txt', ''),
                outputs.get('json', '')
            ])

def generate_audio_dashboard(audio_results: Dict[str, Any], output_dir: Path) -> Dict[str, Path]:
    """
    Generate all audio dashboard outputs.
    
    Args:
        audio_results: Results dictionary from audio_processor.process_audio_files()
        output_dir: Directory to write the outputs
    
    Returns:
        Dictionary mapping output types to file paths
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    outputs = {}
    
    # Generate HTML report
    html_path = generate_audio_report(audio_results, output_dir)
    outputs['html'] = html_path
    
    # Generate CSV summary
    csv_path = output_dir / "audio_summary.csv"
    write_audio_summary_csv(audio_results, csv_path)
    outputs['csv'] = csv_path
    
    return outputs