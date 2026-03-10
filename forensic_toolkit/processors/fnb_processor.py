"""
FNB bank statement processor - handles database operations and analysis.
"""
import os
import sqlite3
import json
import csv
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from collections import Counter
from ..core.custody import chain_log


class FNBProcessor:
    """Processes FNB bank statement data for analysis and visualization."""
    
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path
        
    def create_database(self, db_path: str):
        """Create the SQLite database and tables if they don't exist."""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create transactions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS fnb_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                txn_date TEXT NOT NULL,
                description TEXT NOT NULL,
                debit REAL,
                credit REAL,
                balance REAL,
                balance_type TEXT,
                source_file TEXT NOT NULL,
                file_hash TEXT NOT NULL,
                statement_date TEXT NOT NULL,
                category TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_txn_date ON fnb_transactions(txn_date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_description ON fnb_transactions(description)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_source_file ON fnb_transactions(source_file)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_file_hash ON fnb_transactions(file_hash)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_category ON fnb_transactions(category)')
        
        # Create processed files tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS processed_files (
                file_hash TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                statement_date TEXT NOT NULL,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                transaction_count INTEGER,
                first_txn_date TEXT,
                last_txn_date TEXT
            )
        ''')
        
        # Create categories table for spending analysis
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transaction_categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern TEXT NOT NULL,
                category TEXT NOT NULL,
                is_regex BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Insert default categories
        default_categories = [
            ('PAYMENT', 'Payment', 0),
            ('DEBIT', 'Debit Order', 0),
            ('CARD', 'Card Purchase', 0),
            ('ATM', 'Cash Withdrawal', 0),
            ('SALARY', 'Salary', 0),
            ('INTEREST', 'Interest', 0),
            ('FEE', 'Bank Fees', 0),
            ('TRANSFER', 'Transfer', 0),
        ]
        
        for pattern, category, is_regex in default_categories:
            cursor.execute('''
                INSERT OR IGNORE INTO transaction_categories (pattern, category, is_regex)
                VALUES (?, ?, ?)
            ''', (pattern, category, is_regex))
        
        conn.commit()
        conn.close()
    
    def save_transactions(self, db_path: str, records: List[Dict[str, Any]]):
        """Save transactions to SQLite database."""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        for record in records:
            cursor.execute('''
                INSERT INTO fnb_transactions 
                (txn_date, description, debit, credit, balance, balance_type,
                 source_file, file_hash, statement_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                record['txn_date'],
                record['description'],
                record.get('debit'),
                record.get('credit'),
                record.get('balance'),
                record.get('balance_type'),
                record['filename'],
                record['file_hash'],
                record['statement_date']
            ))
        
        conn.commit()
        conn.close()
    
    def mark_file_processed(self, db_path: str, filename: str, file_hash: str, 
                           statement_date: str, txn_count: int, 
                           first_date: str, last_date: str):
        """Mark a file as processed."""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO processed_files 
            (file_hash, filename, statement_date, transaction_count, first_txn_date, last_txn_date)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (file_hash, filename, statement_date, txn_count, first_date, last_date))
        conn.commit()
        conn.close()
    
    def is_file_processed(self, db_path: str, file_hash: str) -> bool:
        """Check if a file has been processed."""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT 1 FROM processed_files WHERE file_hash = ?', (file_hash,))
        result = cursor.fetchone() is not None
        conn.close()
        return result
    
    def categorize_transactions(self, db_path: str):
        """Categorize transactions based on description patterns."""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all uncategorized transactions
        cursor.execute('''
            SELECT id, description FROM fnb_transactions 
            WHERE category IS NULL
        ''')
        
        transactions = cursor.fetchall()
        
        # Get categories
        cursor.execute('SELECT pattern, category FROM transaction_categories')
        categories = cursor.fetchall()
        
        for txn_id, description in transactions:
            desc_upper = description.upper()
            category = 'Other'
            
            for pattern, cat in categories:
                if pattern in desc_upper:
                    category = cat
                    break
            
            cursor.execute('''
                UPDATE fnb_transactions SET category = ? WHERE id = ?
            ''', (category, txn_id))
        
        conn.commit()
        conn.close()
    
    def generate_statistics(self, db_path: str) -> Dict[str, Any]:
        """Generate statistics from the database."""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        stats = {}
        
        # Basic counts
        cursor.execute('SELECT COUNT(*) FROM fnb_transactions')
        stats['total_transactions'] = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(DISTINCT source_file) FROM fnb_transactions')
        stats['total_statements'] = cursor.fetchone()[0]
        
        # Date range
        cursor.execute('SELECT MIN(txn_date), MAX(txn_date) FROM fnb_transactions')
        min_date, max_date = cursor.fetchone()
        stats['first_date'] = min_date
        stats['last_date'] = max_date
        
        # Financial summary
        cursor.execute('SELECT SUM(debit) FROM fnb_transactions WHERE debit IS NOT NULL')
        stats['total_debits'] = cursor.fetchone()[0] or 0
        
        cursor.execute('SELECT SUM(credit) FROM fnb_transactions WHERE credit IS NOT NULL')
        stats['total_credits'] = cursor.fetchone()[0] or 0
        
        stats['net_flow'] = stats['total_credits'] - stats['total_debits']
        
        # Monthly summary
        cursor.execute('''
            SELECT strftime('%Y-%m', txn_date) as month,
                   COUNT(*) as txns,
                   SUM(debit) as spent,
                   SUM(credit) as received
            FROM fnb_transactions
            GROUP BY month
            ORDER BY month DESC
            LIMIT 12
        ''')
        stats['monthly_summary'] = [
            {'month': r[0], 'transactions': r[1], 'spent': r[2] or 0, 'received': r[3] or 0}
            for r in cursor.fetchall()
        ]
        
        # Category summary
        cursor.execute('''
            SELECT category, COUNT(*) as count, SUM(debit) as total
            FROM fnb_transactions
            WHERE debit IS NOT NULL
            GROUP BY category
            ORDER BY total DESC
        ''')
        stats['spending_by_category'] = [
            {'category': r[0], 'count': r[1], 'total': r[2] or 0}
            for r in cursor.fetchall()
        ]
        
        # Top merchants
        cursor.execute('''
            SELECT description, COUNT(*) as count, SUM(debit) as total
            FROM fnb_transactions
            WHERE debit IS NOT NULL
            GROUP BY description
            ORDER BY total DESC
            LIMIT 20
        ''')
        stats['top_merchants'] = [
            {'merchant': r[0], 'count': r[1], 'total': r[2] or 0}
            for r in cursor.fetchall()
        ]
        
        conn.close()
        return stats
    
    def export_to_csv(self, db_path: str, output_path: Path):
        """Export transactions to CSV."""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT txn_date, description, debit, credit, balance, 
                   balance_type, category, source_file
            FROM fnb_transactions
            ORDER BY txn_date DESC
        ''')
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Date', 'Description', 'Debit', 'Credit', 
                           'Balance', 'Balance Type', 'Category', 'Source File'])
            
            for row in cursor.fetchall():
                writer.writerow(row)
        
        conn.close()
    
    def process_records(self, records: List[Dict[str, Any]], db_path: str, 
                       output_dir: Path, quiet: bool = False) -> Dict[str, Any]:
        """
        Process FNB transaction records and generate outputs.
        """
        def logprint(msg: str):
            if not quiet:
                print(msg, flush=True)
        
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create/update database
        self.create_database(db_path)
        
        # Group records by file hash to avoid duplicates
        files_processed = set()
        new_records = []
        
        for record in records:
            file_hash = record['file_hash']
            if not self.is_file_processed(db_path, file_hash):
                if file_hash not in files_processed:
                    files_processed.add(file_hash)
                    new_records.append(record)
        
        if new_records:
            logprint(f"Processing {len(new_records)} new transactions...")
            
            # Save to database
            self.save_transactions(db_path, new_records)
            
            # Categorize transactions
            self.categorize_transactions(db_path)
            
            # Mark files as processed
            for record in records:
                if record['file_hash'] in files_processed:
                    # Get date range for this file
                    file_records = [r for r in records if r['file_hash'] == record['file_hash']]
                    dates = [r['txn_date'] for r in file_records if r.get('txn_date')]
                    first_date = min(dates) if dates else record['statement_date']
                    last_date = max(dates) if dates else record['statement_date']
                    
                    self.mark_file_processed(
                        db_path,
                        record['filename'],
                        record['file_hash'],
                        record['statement_date'],
                        len(file_records),
                        first_date,
                        last_date
                    )
        
        # Generate statistics
        stats = self.generate_statistics(db_path)
        
        # Export to CSV
        csv_path = output_dir / "fnb_transactions.csv"
        self.export_to_csv(db_path, csv_path)
        
        # Generate HTML dashboard
        self._generate_dashboard(stats, output_dir / "fnb_dashboard.html")
        
        logprint(f"\n📊 FNB Processing Complete:")
        logprint(f"  Total transactions: {stats['total_transactions']}")
        logprint(f"  Date range: {stats['first_date']} to {stats['last_date']}")
        logprint(f"  Net flow: R{stats['net_flow']:,.2f}")
        logprint(f"  CSV export: {csv_path}")
        
        return stats
    
    def _generate_dashboard(self, stats: Dict[str, Any], html_path: Path):
        """Generate HTML dashboard for FNB transactions."""
        
        # Format monthly data for charts
        months_json = json.dumps([
            {
                'month': m['month'],
                'transactions': m['transactions'],
                'spent': m['spent'],
                'received': m['received']
            }
            for m in stats.get('monthly_summary', [])
        ])
        
        categories_json = json.dumps([
            {
                'category': c['category'],
                'count': c['count'],
                'total': c['total']
            }
            for c in stats.get('spending_by_category', [])
        ])
        
        merchants_json = json.dumps([
            {
                'merchant': m['merchant'],
                'count': m['count'],
                'total': m['total']
            }
            for m in stats.get('top_merchants', [])
        ])
        
        # Build top merchants table rows
        merchants_rows = []
        for m in stats.get('top_merchants', [])[:10]:
            merchants_rows.append(f"""
                        <tr>
                            <td>{m['merchant']}</td>
                            <td>{m['count']}</td>
                            <td class="amount negative">R{m['total']:,.2f}</td>
                        </tr>""")
        
        html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FNB Bank Statement Analysis</title>
    <script src="https://www.gstatic.com/charts/loader.js"></script>
    <style>
        :root {{
            --bg: #fafafa;
            --card: #ffffff;
            --border: #e5e7eb;
            --text: #111827;
            --text-muted: #6b7280;
            --primary: #2563eb;
            --success: #10b981;
            --danger: #ef4444;
            --warning: #f59e0b;
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
        
        .stat-value.positive {{ color: var(--success); }}
        .stat-value.negative {{ color: var(--danger); }}
        
        .charts-grid {{
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
        
        .card h3 {{
            margin-top: 0;
            margin-bottom: 15px;
            color: var(--text-muted);
        }}
        
        .chart {{
            width: 100%;
            height: 300px;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
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
        
        .amount {{
            font-family: monospace;
            text-align: right;
        }}
        
        .amount.positive {{ color: var(--success); }}
        .amount.negative {{ color: var(--danger); }}
        
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
        <h1>🏦 FNB Bank Statement Analysis</h1>
        <p>Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value">{stats.get('total_transactions', 0):,}</div>
                <div class="stat-label">Total Transactions</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{stats.get('total_statements', 0)}</div>
                <div class="stat-label">Statements Processed</div>
            </div>
            <div class="stat-card">
                <div class="stat-value positive">R{stats.get('total_credits', 0):,.2f}</div>
                <div class="stat-label">Total Credits (In)</div>
            </div>
            <div class="stat-card">
                <div class="stat-value negative">R{stats.get('total_debits', 0):,.2f}</div>
                <div class="stat-label">Total Debits (Out)</div>
            </div>
            <div class="stat-card">
                <div class="stat-value {'positive' if stats.get('net_flow', 0) >= 0 else 'negative'}">
                    R{stats.get('net_flow', 0):,.2f}
                </div>
                <div class="stat-label">Net Flow</div>
            </div>
        </div>
        
        <div class="charts-grid">
            <div class="card">
                <h3>Monthly Summary</h3>
                <div id="monthly_chart" class="chart"></div>
            </div>
            <div class="card">
                <h3>Spending by Category</h3>
                <div id="category_chart" class="chart"></div>
            </div>
        </div>
        
        <div class="card">
            <h3>Top Merchants</h3>
            <div style="overflow-x: auto;">
                <table>
                    <thead>
                        <tr>
                            <th>Merchant</th>
                            <th>Transactions</th>
                            <th>Total Spent</th>
                        </tr>
                    </thead>
                    <tbody>
                        {''.join(merchants_rows) if merchants_rows else '<tr><td colspan="3" style="text-align: center;">No merchant data available</td></tr>'}
                    </tbody>
                </table>
            </div>
        </div>
        
        <div class="footer">
            <p>Database: {os.path.basename(self.db_path) if self.db_path else 'fnb_statements.db'}</p>
            <p>Generated by Forensic Toolkit FNB Analyzer</p>
        </div>
    </div>
    
    <script>
        google.charts.load('current', {{'packages':['corechart']}});
        google.charts.setOnLoadCallback(drawCharts);
        
        function drawCharts() {{
            // Monthly chart
            var monthlyData = {months_json};
            var monthlyTable = new google.visualization.DataTable();
            monthlyTable.addColumn('string', 'Month');
            monthlyTable.addColumn('number', 'Spent');
            monthlyTable.addColumn('number', 'Received');
            
            monthlyData.forEach(function(row) {{
                monthlyTable.addRow([row.month, row.spent, row.received]);
            }});
            
            var monthlyOptions = {{
                legend: {{ position: 'top' }},
                colors: ['#ef4444', '#10b981'],
                chartArea: {{ width: '80%', height: '70%' }},
                vAxis: {{ format: 'currency' }},
                backgroundColor: 'transparent'
            }};
            
            var monthlyChart = new google.visualization.ColumnChart(
                document.getElementById('monthly_chart')
            );
            monthlyChart.draw(monthlyTable, monthlyOptions);
            
            // Category chart
            var categoryData = {categories_json};
            var categoryTable = new google.visualization.DataTable();
            categoryTable.addColumn('string', 'Category');
            categoryTable.addColumn('number', 'Amount');
            
            categoryData.forEach(function(row) {{
                categoryTable.addRow([row.category, row.total]);
            }});
            
            var categoryOptions = {{
                legend: {{ position: 'none' }},
                colors: ['#2563eb'],
                chartArea: {{ width: '70%', height: '70%' }},
                vAxis: {{ format: 'currency' }},
                backgroundColor: 'transparent'
            }};
            
            var categoryChart = new google.visualization.ColumnChart(
                document.getElementById('category_chart')
            );
            categoryChart.draw(categoryTable, categoryOptions);
        }}
    </script>
</body>
</html>'''
        
        html_path.write_text(html, encoding='utf-8')