import json
from pathlib import Path
from typing import List, Dict, Any

class DashboardBuilder:
    def __init__(self, insights: List[Dict[str, Any]], spec_name: str):
        self.insights = insights
        self.spec_name = spec_name
        
    def build_html(self) -> str:
        # Separate insights by severity
        critical = [i for i in self.insights if i.get('severity') == 'critical']
        warnings = [i for i in self.insights if i.get('severity') == 'warning']
        info = [i for i in self.insights if i.get('severity') == 'info']
        
        # Prepare charts data (funnel)
        funnel_labels = []
        funnel_data = []
        for i in self.insights:
            if "funnel" in i.get('tags', []) and "drop_off" not in i.get('tags', []):
                val = i.get('value', {})
                if isinstance(val, dict):
                    for step, count in val.items():
                        funnel_labels.append(step)
                        funnel_data.append(count)
        
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Analytics Dashboard - {self.spec_name}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-color: #f8fafc;
            --card-bg: rgba(255, 255, 255, 0.7);
            --text-main: #0f172a;
            --text-muted: #64748b;
            --border-color: rgba(255, 255, 255, 0.4);
            --accent-blue: #3b82f6;
            --warning-color: #f59e0b;
            --critical-color: #ef4444;
            --info-color: #10b981;
        }}
        
        body {{
            font-family: 'Inter', sans-serif;
            background: var(--bg-color);
            background-image: radial-gradient(at 40% 20%, hsla(210,100%,74%,0.2) 0px, transparent 50%),
                              radial-gradient(at 80% 0%, hsla(189,100%,56%,0.2) 0px, transparent 50%),
                              radial-gradient(at 0% 50%, hsla(355,100%,93%,0.3) 0px, transparent 50%);
            color: var(--text-main);
            margin: 0;
            padding: 2rem;
            min-height: 100vh;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        
        header {{
            margin-bottom: 3rem;
            text-align: center;
        }}
        
        h1 {{
            font-size: 2.5rem;
            font-weight: 700;
            background: linear-gradient(90deg, #1e3a8a, #3b82f6);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.5rem;
        }}
        
        .glass-card {{
            background: var(--card-bg);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 1.5rem;
            box-shadow: 0 4px 30px rgba(0, 0, 0, 0.05);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }}
        
        .glass-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.1);
        }}
        
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }}
        
        .dashboard-section {{
            margin-bottom: 3rem;
        }}
        
        .dashboard-section h2 {{
            font-size: 1.5rem;
            margin-bottom: 1.5rem;
            border-bottom: 2px solid rgba(59, 130, 246, 0.2);
            padding-bottom: 0.5rem;
            display: inline-block;
        }}
        
        .insight-title {{
            font-weight: 600;
            font-size: 1.1rem;
            margin-bottom: 0.5rem;
        }}
        
        .insight-desc {{
            color: var(--text-muted);
            font-size: 0.95rem;
            line-height: 1.5;
        }}
        
        .badge {{
            display: inline-block;
            padding: 0.25rem 0.75rem;
            border-radius: 999px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 1rem;
        }}
        
        .badge.critical {{ background: rgba(239, 68, 68, 0.1); color: var(--critical-color); border: 1px solid rgba(239, 68, 68, 0.2); }}
        .badge.warning {{ background: rgba(245, 158, 11, 0.1); color: var(--warning-color); border: 1px solid rgba(245, 158, 11, 0.2); }}
        .badge.info {{ background: rgba(16, 185, 129, 0.1); color: var(--info-color); border: 1px solid rgba(16, 185, 129, 0.2); }}
        
        .chart-container {{
            width: 100%;
            height: 400px;
            margin: 0 auto;
        }}
        
        .metric-value {{
            font-size: 2rem;
            font-weight: 700;
            color: var(--accent-blue);
            margin-top: 1rem;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Analytics Dashboard</h1>
            <p style="color: var(--text-muted); font-size: 1.1rem;">Feature Spec: <strong>{self.spec_name}</strong></p>
        </header>
        
        <div class="dashboard-section">
            <h2>Conversion Funnel</h2>
            <div class="glass-card">
                <div class="chart-container">
                    <canvas id="funnelChart"></canvas>
                </div>
            </div>
        </div>
        
        <div class="dashboard-section">
            <h2>Critical & Warning Insights</h2>
            <div class="grid">
                {"".join(self._build_card(i) for i in critical + warnings)}
            </div>
        </div>
        
        <div class="dashboard-section">
            <h2>General Insights</h2>
            <div class="grid">
                {"".join(self._build_card(i) for i in info)}
            </div>
        </div>
    </div>
    
    <script>
        document.addEventListener('DOMContentLoaded', function() {{
            const ctx = document.getElementById('funnelChart').getContext('2d');
            const funnelLabels = {json.dumps(funnel_labels)};
            const funnelData = {json.dumps(funnel_data)};
            
            if (funnelLabels.length > 0) {{
                new Chart(ctx, {{
                    type: 'bar',
                    data: {{
                        labels: funnelLabels,
                        datasets: [{{
                            label: 'Users at Step',
                            data: funnelData,
                            backgroundColor: 'rgba(59, 130, 246, 0.5)',
                            borderColor: 'rgba(59, 130, 246, 1)',
                            borderWidth: 2,
                            borderRadius: 8,
                        }}]
                    }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {{
                            legend: {{ display: false }},
                            tooltip: {{
                                backgroundColor: 'rgba(15, 23, 42, 0.9)',
                                titleFont: {{ family: 'Inter', size: 14 }},
                                bodyFont: {{ family: 'Inter', size: 14 }},
                                padding: 12,
                                cornerRadius: 8
                            }}
                        }},
                        scales: {{
                            y: {{ beginAtZero: true, grid: {{ color: 'rgba(0,0,0,0.05)' }} }},
                            x: {{ grid: {{ display: false }} }}
                        }}
                    }}
                }});
            }}
        }});
    </script>
</body>
</html>"""
        return html
        
    def _build_card(self, insight: Dict) -> str:
        severity = insight.get('severity', 'info')
        val_str = ""
        val = insight.get('value')
        if isinstance(val, (int, float)) and "rate" in insight.get('metric', ''):
            val_str = f"<div class='metric-value'>{val:.1f}%</div>"
            
        return f"""
        <div class="glass-card">
            <span class="badge {severity}">{severity}</span>
            <div class="insight-title">{insight.get('title', 'Insight')}</div>
            <div class="insight-desc">{insight.get('description', '')}</div>
            {val_str}
        </div>
        """
