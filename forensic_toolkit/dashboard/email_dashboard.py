"""
Email dashboard generator - creates visualizations for email analysis.
"""
import json
import csv
from pathlib import Path
from typing import Dict, Any, Optional
from ..core.utils import html_escape

def generate_email_dashboard(email_results: Dict[str, Any], output_dir: Path, 
                            title: str = "Email Analysis Dashboard") -> Path:
    """
    Generate an HTML dashboard for email analysis results.
    
    Args:
        email_results: Results dictionary from email_processor.process_emails()
        output_dir: Directory to write the HTML report
        title: Report title
    
    Returns:
        Path to the generated HTML file
    """
    html_path = output_dir / "email_dashboard.html"
    
    # Extract statistics
    stats = email_results.get('statistics', {})
    networks = email_results.get('networks', {})
    entities = email_results.get('entities', {})
    timeline = email_results.get('timeline', [])
    
    # Format timeline
    timeline_rows = []
    for item in timeline[:100]:
        timeline_rows.append(f'''
<tr>
    <td>{html_escape(item.get('date', ''))}</td>
    <td>{html_escape(item.get('sender', ''))}</td>
    <td>{html_escape(item.get('subject', ''))}</td>
    <td>{'✓' if item.get('has_attachments') else ''}</td>
</tr>''')
    
    # Format top senders
    sender_rows = []
    for sender, count in stats.get('top_senders', []):
        sender_rows.append(f'''
<li><span class="entity-name">{html_escape(sender)}</span> <span class="count">{count}</span></li>''')
    
    # Format top domains
    domain_rows = []
    for domain, count in stats.get('top_domains', []):
        domain_rows.append(f'''
<li><span class="entity-name">{html_escape(domain)}</span> <span class="count">{count}</span></li>''')
    
    # Format entities
    email_rows = []
    for email, count in entities.get('emails', []):
        email_rows.append(f'''
<li><span class="entity-name">{html_escape(email)}</span> <span class="count">{count}</span></li>''')
    
    url_rows = []
    for url, count in entities.get('urls', []):
        url_rows.append(f'''
<li><span class="entity-name">{html_escape(url[:50])}</span> <span class="count">{count}</span></li>''')
    
    phone_rows = []
    for phone, count in entities.get('phones', []):
        phone_rows.append(f'''
<li><span class="entity-name">{html_escape(phone)}</span> <span class="count">{count}</span></li>''')
    
    # Calculate date range display
    date_range = stats.get('date_range', {})
    start_date = date_range.get('start', 'N/A')
    end_date = date_range.get('end', 'N/A')
    
    # Calculate duration
    duration = 'N/A'
    if start_date != 'N/A' and end_date != 'N/A':
        try:
            from datetime import datetime
            start = datetime.strptime(start_date, "%Y-%m-%d %H:%M:%S")
            end = datetime.strptime(end_date, "%Y-%m-%d %H:%M:%S")
            days = (end - start).days
            duration = f"{days} days"
        except:
            pass
    
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
            --border: #e5e7eb;
            --text: #111827;
            --text-muted: #6b7280;
            --primary: #2563eb;
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
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
        
        h1 {{ font-size: 2em; margin-bottom: 0.5em; }}
        h2 {{ font-size: 1.5em; margin: 20px 0 10px; color: var(--text-muted); }}
        
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
            font-size: 2.2em;
            font-weight: 600;
            color: var(--primary);
        }}
        
        .stat-label {{
            color: var(--text-muted);
            font-size: 0.9em;
            margin-top: 5px;
        }}
        
        .dashboard-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        
        .card {{
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 20px;
        }}
        
        .card h3 {{
            margin-top: 0;
            margin-bottom: 15px;
            color: var(--text-muted);
            font-size: 1.1em;
        }}
        
        .entity-list {{
            list-style: none;
            padding: 0;
            margin: 0;
            max-height: 300px;
            overflow-y: auto;
        }}
        
        .entity-list li {{
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid var(--border);
            font-size: 13px;
        }}
        
        .entity-list li:last-child {{
            border-bottom: none;
        }}
        
        .entity-name {{
            font-family: monospace;
            color: var(--text);
            word-break: break-all;
        }}
        
        .count {{
            background: var(--primary);
            color: white;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
            white-space: nowrap;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 12px;
            overflow: hidden;
        }}
        
        th, td {{
            padding: 12px 10px;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }}
        
        th {{
            background: #f8fafc;
            color: var(--text-muted);
            font-weight: 600;
            font-size: 12px;
        }}
        
        tr:hover {{
            background: #f9fafb;
        }}
        
        .badge {{
            display: inline-block;
            padding: 4px 8px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 500;
        }}
        
        .badge.success {{ background: #d1fae5; color: #065f46; }}
        .badge.warning {{ background: #fed7aa; color: #92400e; }}
        
        .footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid var(--border);
            color: var(--text-muted);
            text-align: center;
            font-size: 12px;
        }}
        
        .empty-state {{
            color: var(--text-muted);
            font-style: italic;
            text-align: center;
            padding: 20px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📧 {html_escape(title)}</h1>
        <p>Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value">{stats.get('total_emails', 0):,}</div>
                <div class="stat-label">Total Emails</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{stats.get('unique_senders', 0):,}</div>
                <div class="stat-label">Unique Senders</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{stats.get('unique_recipients', 0):,}</div>
                <div class="stat-label">Unique Recipients</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{stats.get('unique_domains', 0):,}</div>
                <div class="stat-label">Email Domains</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{stats.get('has_attachments', 0):,}</div>
                <div class="stat-label">With Attachments</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{stats.get('total_attachments', 0):,}</div>
                <div class="stat-label">Total Attachments</div>
            </div>
        </div>
        
        <div class="dashboard-grid">
            <div class="card">
                <h3>📊 Date Range</h3>
                <p><strong>Start:</strong> {html_escape(start_date)}</p>
                <p><strong>End:</strong> {html_escape(end_date)}</p>
                <p><strong>Duration:</strong> {duration}</p>
                <p><strong>Avg. Attachments:</strong> {stats.get('avg_attachments', 0):.2f}</p>
            </div>
            
            <div class="card">
                <h3>📨 Top Senders</h3>
                <ul class="entity-list">
                    {''.join(sender_rows) if sender_rows else '<li class="empty-state">No sender data</li>'}
                </ul>
            </div>
            
            <div class="card">
                <h3>🏢 Top Domains</h3>
                <ul class="entity-list">
                    {''.join(domain_rows) if domain_rows else '<li class="empty-state">No domain data</li>'}
                </ul>
            </div>
        </div>
        
        <div class="dashboard-grid">
            <div class="card">
                <h3>📧 Email Addresses in Body</h3>
                <ul class="entity-list">
                    {''.join(email_rows) if email_rows else '<li class="empty-state">No emails found</li>'}
                </ul>
            </div>
            
            <div class="card">
                <h3>🔗 URLs in Body</h3>
                <ul class="entity-list">
                    {''.join(url_rows) if url_rows else '<li class="empty-state">No URLs found</li>'}
                </ul>
            </div>
            
            <div class="card">
                <h3>📱 Phone Numbers in Body</h3>
                <ul class="entity-list">
                    {''.join(phone_rows) if phone_rows else '<li class="empty-state">No phone numbers found</li>'}
                </ul>
            </div>
        </div>
        
        <h2>📅 Recent Emails</h2>
        <div style="overflow-x: auto; margin-top: 20px;">
            <table>
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Sender</th>
                        <th>Subject</th>
                        <th style="width: 80px;">Attachments</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(timeline_rows) if timeline_rows else '<tr><td colspan="4" class="empty-state">No emails in timeline</td></tr>'}
                </tbody>
            </table>
        </div>
        
        <div class="footer">
            <p>Network: {networks.get('node_count', 0):,} nodes, {networks.get('edge_count', 0):,} edges</p>
            <p>Total entities extracted: {entities.get('total', 0):,}</p>
            <p>Generated by Forensic Toolkit Email Analyzer</p>
        </div>
    </div>
</body>
</html>'''
    
    html_path.write_text(html, encoding='utf-8')
    return html_path

def write_email_summary_csv(email_results: Dict[str, Any], csv_path: Path) -> None:
    """
    Write a CSV summary of email analysis results.
    
    Args:
        email_results: Results dictionary from email_processor.process_emails()
        csv_path: Path to write the CSV file
    """
    stats = email_results.get('statistics', {})
    
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        # Write basic stats
        writer.writerow(["Metric", "Value"])
        writer.writerow(["Total Emails", stats.get('total_emails', 0)])
        writer.writerow(["Unique Senders", stats.get('unique_senders', 0)])
        writer.writerow(["Unique Recipients", stats.get('unique_recipients', 0)])
        writer.writerow(["Unique Domains", stats.get('unique_domains', 0)])
        writer.writerow(["With Attachments", stats.get('has_attachments', 0)])
        writer.writerow(["Total Attachments", stats.get('total_attachments', 0)])
        writer.writerow([])
        
        # Write top senders
        writer.writerow(["Top Senders", "Count"])
        for sender, count in stats.get('top_senders', []):
            writer.writerow([sender, count])
        writer.writerow([])
        
        # Write top domains
        writer.writerow(["Top Domains", "Count"])
        for domain, count in stats.get('top_domains', []):
            writer.writerow([domain, count])

def generate_email_network_csv(email_results: Dict[str, Any], csv_path: Path) -> None:
    """
    Write email communication network as CSV for Gephi/etc.
    
    Args:
        email_results: Results dictionary from email_processor.process_emails()
        csv_path: Path to write the CSV file
    """
    networks = email_results.get('networks', {})
    
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["Source", "Target", "Type", "Weight"])
        
        for edge in networks.get('edges', []):
            writer.writerow([
                edge.get('source', ''),
                edge.get('target', ''),
                edge.get('type', ''),
                edge.get('weight', 1)
            ])