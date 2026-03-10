"""
Email processing module - handles email extraction and analysis.
"""
import os
import csv
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from collections import Counter
from datetime import datetime
from ..core.custody import chain_log

class EmailProcessor:
    """Processes email data for analysis and visualization."""
    
    def __init__(self):
        self.email_pattern = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
        self.url_pattern = re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+')
        self.phone_pattern = re.compile(r'\b(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b')
    
    def process_emails(self, email_records: List[Dict[str, Any]], output_dir: Path, 
                       quiet: bool = False) -> Dict[str, Any]:
        """
        Process email records and generate analysis outputs.
        
        Args:
            email_records: List of email records from parser
            output_dir: Directory to write outputs
            quiet: Suppress console output
        
        Returns:
            Dictionary with processing results
        """
        def logprint(msg: str):
            if not quiet:
                print(msg, flush=True)
        
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        logprint(f"Processing {len(email_records)} email records...")
        
        # Basic statistics
        stats = self._calculate_stats(email_records)
        
        # Extract communication networks
        networks = self._extract_networks(email_records)
        
        # Extract entities (emails, URLs, phones)
        entities = self._extract_entities(email_records)
        
        # Timeline analysis
        timeline = self._build_timeline(email_records)
        
        # Write outputs
        self._write_csv(email_records, output_dir / "emails.csv")
        self._write_stats_json(stats, networks, entities, timeline, output_dir / "email_stats.json")
        self._write_network_csv(networks, output_dir / "email_network.csv")
        self._write_entities_csv(entities, output_dir / "extracted_entities.csv")
        
        # Generate HTML dashboard
        html_path = self._generate_html_dashboard(
            stats, networks, entities, timeline, 
            email_records, output_dir / "email_dashboard.html"
        )
        
        logprint(f"Email processing complete: {stats['total_emails']} emails, "
                 f"{stats['unique_senders']} unique senders")
        
        return {
            "total_emails": stats['total_emails'],
            "unique_senders": stats['unique_senders'],
            "unique_recipients": stats['unique_recipients'],
            "date_range": stats['date_range'],
            "has_attachments": stats['has_attachments'],
            "entities": entities['total'],
            "dashboard": str(html_path)
        }
    
    def _calculate_stats(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate basic statistics from email records."""
        if not records:
            return {
                "total_emails": 0,
                "unique_senders": 0,
                "unique_recipients": 0,
                "unique_domains": 0,
                "date_range": {"start": None, "end": None},
                "has_attachments": 0,
                "total_attachments": 0,
                "avg_attachments": 0,
                "top_senders": [],
                "top_recipients": [],
                "top_domains": [],
            }
        
        # Collect data
        senders = []
        recipients = []
        domains = []
        dates = []
        attachment_counts = []
        
        for r in records:
            # Sender
            sender = r.get('from_address') or r.get('sender_address') or r.get('from', '')
            if sender:
                senders.append(sender)
                if '@' in sender:
                    domain = sender.split('@')[-1].lower()
                    domains.append(domain)
            
            # Recipients
            for addr in r.get('to_addresses', []):
                if addr.get('address'):
                    recipients.append(addr['address'])
                    if '@' in addr['address']:
                        domain = addr['address'].split('@')[-1].lower()
                        domains.append(domain)
            
            # Date
            if r.get('date'):
                dates.append(r['date'])
            
            # Attachments
            if r.get('has_attachments'):
                attachment_counts.append(r.get('attachment_count', 0))
        
        # Calculate date range
        date_range = {"start": None, "end": None}
        if dates:
            try:
                date_range["start"] = min(dates)
                date_range["end"] = max(dates)
            except:
                pass
        
        return {
            "total_emails": len(records),
            "unique_senders": len(set(senders)),
            "unique_recipients": len(set(recipients)),
            "unique_domains": len(set(domains)),
            "date_range": date_range,
            "has_attachments": len([r for r in records if r.get('has_attachments')]),
            "total_attachments": sum(r.get('attachment_count', 0) for r in records),
            "avg_attachments": sum(attachment_counts) / len(attachment_counts) if attachment_counts else 0,
            "top_senders": Counter(senders).most_common(10),
            "top_recipients": Counter(recipients).most_common(10),
            "top_domains": Counter(domains).most_common(10),
        }
    
    def _extract_networks(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract communication networks between senders and recipients."""
        edges = []
        nodes = set()
        
        for r in records:
            sender = r.get('from_address') or r.get('sender_address') or r.get('from', '')
            if not sender:
                continue
            
            nodes.add(sender)
            
            # Add edges to recipients
            for addr in r.get('to_addresses', []):
                recipient = addr.get('address')
                if recipient:
                    nodes.add(recipient)
                    edges.append({
                        "source": sender,
                        "target": recipient,
                        "type": "to",
                        "count": 1
                    })
            
            # Add CC edges
            if r.get('cc'):
                for addr in r['cc'].split(','):
                    _, recipient = self._parse_email_address(addr)
                    if recipient:
                        nodes.add(recipient)
                        edges.append({
                            "source": sender,
                            "target": recipient,
                            "type": "cc",
                            "count": 1
                        })
        
        # Aggregate edges
        edge_counts = {}
        for e in edges:
            key = f"{e['source']}|{e['target']}|{e['type']}"
            edge_counts[key] = edge_counts.get(key, 0) + 1
        
        aggregated_edges = []
        for key, count in edge_counts.items():
            source, target, etype = key.split('|')
            aggregated_edges.append({
                "source": source,
                "target": target,
                "type": etype,
                "weight": count
            })
        
        return {
            "nodes": list(nodes),
            "node_count": len(nodes),
            "edges": aggregated_edges,
            "edge_count": len(aggregated_edges)
        }
    
    def _extract_entities(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract email addresses, URLs, and phone numbers from email bodies."""
        emails = []
        urls = []
        phones = []
        
        for r in records:
            body = r.get('body', '') or r.get('html_body', '') or ''
            
            # Extract emails
            emails.extend(self.email_pattern.findall(body))
            
            # Extract URLs
            urls.extend(self.url_pattern.findall(body))
            
            # Extract phone numbers
            phones.extend(self.phone_pattern.findall(body))
        
        return {
            "emails": Counter(emails).most_common(20),
            "urls": Counter(urls).most_common(20),
            "phones": Counter(phones).most_common(20),
            "total": len(emails) + len(urls) + len(phones)
        }
    
    def _build_timeline(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Build timeline of email activity."""
        timeline = []
        
        for r in records:
            if r.get('date'):
                timeline.append({
                    "date": r['date'],
                    "sender": r.get('from_address') or r.get('from', ''),
                    "subject": r.get('subject', '')[:100],
                    "has_attachments": r.get('has_attachments', False)
                })
        
        # Sort by date
        timeline.sort(key=lambda x: x.get('date', ''))
        
        return timeline
    
    def _parse_email_address(self, addr_str: str) -> tuple:
        """Parse email address into name and address."""
        if not addr_str:
            return "", ""
        
        import email.utils
        name, addr = email.utils.parseaddr(addr_str)
        return name or "", addr or ""
    
    def _write_csv(self, records: List[Dict[str, Any]], csv_path: Path):
        """Write email records to CSV."""
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Write header
            writer.writerow([
                "Date", "From_Name", "From_Address", "To", "Subject", 
                "Has_Attachments", "Attachment_Count", "Message_ID", "Source"
            ])
            
            for r in records:
                writer.writerow([
                    r.get('date', ''),
                    r.get('from_name', ''),
                    r.get('from_address', '') or r.get('sender_address', ''),
                    r.get('to', ''),
                    r.get('subject', ''),
                    r.get('has_attachments', False),
                    r.get('attachment_count', 0),
                    r.get('message_id', ''),
                    os.path.basename(r.get('source_file', ''))
                ])
    
    def _write_stats_json(self, stats: Dict, networks: Dict, entities: Dict, 
                          timeline: List, json_path: Path):
        """Write statistics to JSON."""
        output = {
            "statistics": stats,
            "networks": networks,
            "entities": entities,
            "timeline": timeline[:1000]  # Limit timeline size
        }
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, default=str)
    
    def _write_network_csv(self, networks: Dict, csv_path: Path):
        """Write network edges to CSV."""
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["Source", "Target", "Type", "Weight"])
            
            for edge in networks.get('edges', []):
                writer.writerow([
                    edge['source'],
                    edge['target'],
                    edge['type'],
                    edge['weight']
                ])
    
    def _write_entities_csv(self, entities: Dict, csv_path: Path):
        """Write extracted entities to CSV."""
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            writer.writerow(["Type", "Value", "Count"])
            
            for email, count in entities.get('emails', []):
                writer.writerow(["email", email, count])
            
            for url, count in entities.get('urls', []):
                writer.writerow(["url", url, count])
            
            for phone, count in entities.get('phones', []):
                writer.writerow(["phone", phone, count])
    
    def _generate_html_dashboard(self, stats: Dict, networks: Dict, entities: Dict,
                                 timeline: List, records: List, html_path: Path) -> Path:
        """Generate HTML dashboard for email analysis."""
        
        # Format timeline for display
        timeline_rows = []
        for item in timeline[:100]:  # Show last 100
            timeline_rows.append(f'''
<tr>
    <td>{item.get('date', '')}</td>
    <td>{item.get('sender', '')}</td>
    <td>{item.get('subject', '')}</td>
    <td>{'✓' if item.get('has_attachments') else ''}</td>
</tr>''')
        
        # Format top senders
        sender_rows = []
        for sender, count in stats.get('top_senders', []):
            sender_rows.append(f'''
<li><span class="entity-name">{sender}</span> <span class="count">{count}</span></li>''')
        
        # Format top domains
        domain_rows = []
        for domain, count in stats.get('top_domains', []):
            domain_rows.append(f'''
<li><span class="entity-name">{domain}</span> <span class="count">{count}</span></li>''')
        
        # Format extracted entities
        email_rows = []
        for email, count in entities.get('emails', []):
            email_rows.append(f'''
<li><span class="entity-name">{email}</span> <span class="count">{count}</span></li>''')
        
        url_rows = []
        for url, count in entities.get('urls', []):
            url_rows.append(f'''
<li><span class="entity-name">{url[:50]}</span> <span class="count">{count}</span></li>''')
        
        phone_rows = []
        for phone, count in entities.get('phones', []):
            phone_rows.append(f'''
<li><span class="entity-name">{phone}</span> <span class="count">{count}</span></li>''')
        
        html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Email Analysis Dashboard</title>
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
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        
        .card {{
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 20px;
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
        }}
        
        .entity-list li:last-child {{
            border-bottom: none;
        }}
        
        .entity-name {{
            font-family: monospace;
            font-size: 12px;
            color: var(--text);
        }}
        
        .count {{
            background: var(--primary);
            color: white;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 12px;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }}
        
        th, td {{
            padding: 10px;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }}
        
        th {{
            background: #f8fafc;
            color: var(--text-muted);
            font-weight: 600;
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
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📧 Email Analysis Dashboard</h1>
        <p>Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value">{stats.get('total_emails', 0)}</div>
                <div class="stat-label">Total Emails</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{stats.get('unique_senders', 0)}</div>
                <div class="stat-label">Unique Senders</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{stats.get('unique_recipients', 0)}</div>
                <div class="stat-label">Unique Recipients</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{stats.get('unique_domains', 0)}</div>
                <div class="stat-label">Domains</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{stats.get('has_attachments', 0)}</div>
                <div class="stat-label">With Attachments</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{stats.get('total_attachments', 0)}</div>
                <div class="stat-label">Total Attachments</div>
            </div>
        </div>
        
        <div class="dashboard-grid">
            <div class="card">
                <h3>📊 Date Range</h3>
                <p><strong>Start:</strong> {stats.get('date_range', {}).get('start', 'N/A')}</p>
                <p><strong>End:</strong> {stats.get('date_range', {}).get('end', 'N/A')}</p>
                <p><strong>Duration:</strong> {
                    (lambda s,e: 'N/A' if not s or not e else 
                     f"{(datetime.strptime(e,'%Y-%m-%d %H:%M:%S') - datetime.strptime(s,'%Y-%m-%d %H:%M:%S')).days} days")
                    (stats.get('date_range', {}).get('start'), stats.get('date_range', {}).get('end'))
                }</p>
            </div>
            
            <div class="card">
                <h3>📨 Top Senders</h3>
                <ul class="entity-list">
                    {''.join(sender_rows) if sender_rows else '<li>No data</li>'}
                </ul>
            </div>
            
            <div class="card">
                <h3>🏢 Top Domains</h3>
                <ul class="entity-list">
                    {''.join(domain_rows) if domain_rows else '<li>No data</li>'}
                </ul>
            </div>
        </div>
        
        <div class="dashboard-grid">
            <div class="card">
                <h3>📧 Extracted Email Addresses</h3>
                <ul class="entity-list">
                    {''.join(email_rows) if email_rows else '<li>No emails found</li>'}
                </ul>
            </div>
            
            <div class="card">
                <h3>🔗 Extracted URLs</h3>
                <ul class="entity-list">
                    {''.join(url_rows) if url_rows else '<li>No URLs found</li>'}
                </ul>
            </div>
            
            <div class="card">
                <h3>📱 Extracted Phone Numbers</h3>
                <ul class="entity-list">
                    {''.join(phone_rows) if phone_rows else '<li>No phone numbers found</li>'}
                </ul>
            </div>
        </div>
        
        <h2>📅 Recent Emails</h2>
        <div style="overflow-x: auto;">
            <table>
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Sender</th>
                        <th>Subject</th>
                        <th>Attachments</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(timeline_rows) if timeline_rows else '<tr><td colspan="4">No emails found</td></tr>'}
                </tbody>
            </table>
        </div>
        
        <div class="footer">
            Network statistics: {networks.get('node_count', 0)} nodes, {networks.get('edge_count', 0)} edges<br>
            Total entities extracted: {entities.get('total', 0)}
        </div>
    </div>
</body>
</html>'''
        
        html_path.write_text(html, encoding='utf-8')
        return html_path