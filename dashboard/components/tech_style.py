# dashboard/components/tech_style.py

import streamlit as st


def apply_tech_style():
    st.set_page_config(
        page_title="Multi-Agent System",
        page_icon="🤖",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    CSS = """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

    :root {
        --bg-primary: #0F172A;
        --bg-secondary: #1E293B;
        --bg-tertiary: #334155;
        --accent-cyan: #06B6D4;
        --accent-green: #22C55E;
        --accent-purple: #A855F7;
        --text-primary: #F8FAFC;
        --text-secondary: #94A3B8;
        --text-muted: #64748B;
        --border: #334155;
        --glow-cyan: 0 0 20px rgba(6, 182, 212, 0.3);
        --glow-green: 0 0 20px rgba(34, 197, 94, 0.3);
    }

    * {
        font-family: 'IBM Plex Sans', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    .stApp {
        background: var(--bg-primary);
        color: var(--text-primary);
    }

    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, var(--bg-secondary) 0%, var(--bg-primary) 100%);
        border-right: 1px solid var(--border);
        width: 260px;
    }

    .sidebar-header {
        padding: 24px 20px;
        border-bottom: 1px solid var(--border);
        background: linear-gradient(90deg, rgba(6,182,212,0.1) 0%, transparent 100%);
    }

    .sidebar-title {
        color: var(--text-primary);
        font-size: 20px;
        font-weight: 700;
        font-family: 'JetBrains Mono', monospace;
        display: flex;
        align-items: center;
        gap: 12px;
    }

    .sidebar-title .accent {
        color: var(--accent-cyan);
        text-shadow: var(--glow-cyan);
    }

    .sidebar-nav {
        padding: 16px 12px;
    }

    .nav-item {
        display: flex;
        align-items: center;
        padding: 12px 16px;
        margin: 6px 0;
        border-radius: 8px;
        color: var(--text-secondary);
        text-decoration: none;
        font-size: 14px;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.2s ease;
        border: 1px solid transparent;
    }

    .nav-item:hover {
        background: rgba(6, 182, 212, 0.1);
        color: var(--accent-cyan);
        border-color: rgba(6, 182, 212, 0.2);
    }

    .nav-item.active {
        background: linear-gradient(90deg, rgba(6,182,212,0.15) 0%, rgba(6,182,212,0.05) 100%);
        color: var(--accent-cyan);
        border: 1px solid rgba(6, 182, 212, 0.3);
        box-shadow: var(--glow-cyan);
    }

    .nav-icon {
        width: 20px;
        margin-right: 12px;
        font-size: 16px;
    }

    .main-content {
        padding: 32px 40px;
        max-width: 1600px;
        margin: 0 auto;
    }

    .page-header {
        margin-bottom: 32px;
        padding-bottom: 20px;
        border-bottom: 1px solid var(--border);
    }

    .page-title {
        color: var(--text-primary);
        font-size: 28px;
        font-weight: 700;
        font-family: 'JetBrains Mono', monospace;
        margin: 0 0 8px 0;
    }

    .page-subtitle {
        color: var(--text-muted);
        font-size: 14px;
        margin: 0;
    }

    .metric-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 20px;
        margin-bottom: 32px;
    }

    .metric-card {
        background: linear-gradient(135deg, var(--bg-secondary) 0%, var(--bg-tertiary) 100%);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 24px;
        position: relative;
        overflow: hidden;
        transition: all 0.3s ease;
    }

    .metric-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 3px;
        background: linear-gradient(90deg, var(--accent-cyan), var(--accent-green));
    }

    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        border-color: var(--accent-cyan);
    }

    .metric-value {
        font-size: 36px;
        font-weight: 700;
        font-family: 'JetBrains Mono', monospace;
        color: var(--accent-cyan);
        text-shadow: var(--glow-cyan);
        margin-bottom: 8px;
    }

    .metric-label {
        color: var(--text-secondary);
        font-size: 13px;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    .card {
        background: var(--bg-secondary);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 20px;
        transition: all 0.2s ease;
    }

    .card:hover {
        border-color: rgba(6, 182, 212, 0.3);
    }

    .card-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 16px;
        padding-bottom: 12px;
        border-bottom: 1px solid var(--border);
    }

    .card-title {
        color: var(--text-primary);
        font-size: 16px;
        font-weight: 600;
        margin: 0;
        font-family: 'JetBrains Mono', monospace;
    }

    .status-badge {
        display: inline-flex;
        align-items: center;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    .status-online {
        background: rgba(34, 197, 94, 0.15);
        color: var(--accent-green);
        border: 1px solid rgba(34, 197, 94, 0.3);
        box-shadow: var(--glow-green);
    }

    .status-running {
        background: rgba(6, 182, 212, 0.15);
        color: var(--accent-cyan);
        border: 1px solid rgba(6, 182, 212, 0.3);
    }

    .status-offline {
        background: rgba(239, 68, 68, 0.15);
        color: #EF4444;
        border: 1px solid rgba(239, 68, 68, 0.3);
    }

    .status-pending {
        background: rgba(251, 191, 36, 0.15);
        color: #FBBF24;
        border: 1px solid rgba(251, 191, 36, 0.3);
    }

    .agent-card {
        background: var(--bg-tertiary);
        border: 1px solid var(--border);
        border-radius: 10px;
        padding: 16px;
        margin: 10px 0;
        display: flex;
        align-items: center;
        gap: 16px;
        transition: all 0.2s ease;
    }

    .agent-card:hover {
        background: rgba(6, 182, 212, 0.05);
        border-color: var(--accent-cyan);
    }

    .agent-icon {
        width: 44px;
        height: 44px;
        border-radius: 10px;
        background: linear-gradient(135deg, var(--accent-cyan), var(--accent-purple));
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 20px;
        box-shadow: var(--glow-cyan);
    }

    .agent-info {
        flex: 1;
    }

    .agent-name {
        color: var(--text-primary);
        font-size: 15px;
        font-weight: 600;
        font-family: 'JetBrains Mono', monospace;
    }

    .agent-meta {
        color: var(--text-muted);
        font-size: 12px;
        margin-top: 4px;
    }

    .btn-primary {
        background: linear-gradient(135deg, var(--accent-cyan), var(--accent-green));
        color: var(--bg-primary);
        border: none;
        padding: 12px 24px;
        border-radius: 8px;
        font-weight: 600;
        font-size: 14px;
        cursor: pointer;
        transition: all 0.2s ease;
        box-shadow: var(--glow-cyan);
    }

    .btn-primary:hover {
        transform: translateY(-1px);
        box-shadow: 0 0 30px rgba(6, 182, 212, 0.5);
    }

    .stButton > button {
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.2s ease;
        border: 1px solid var(--border);
        background: var(--bg-secondary);
        color: var(--text-primary);
    }

    .stButton > button:hover {
        border-color: var(--accent-cyan);
        background: rgba(6, 182, 212, 0.1);
        color: var(--accent-cyan);
    }

    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea {
        background: var(--bg-tertiary);
        border: 1px solid var(--border);
        border-radius: 8px;
        color: var(--text-primary);
    }

    .stTextInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus {
        border-color: var(--accent-cyan);
        box-shadow: 0 0 0 2px rgba(6, 182, 212, 0.2);
    }

    .stSelectbox > div > div {
        background: var(--bg-tertiary);
        border: 1px solid var(--border);
        border-radius: 8px;
    }

    .st-expander {
        background: var(--bg-secondary);
        border: 1px solid var(--border);
        border-radius: 10px;
    }

    .stMetric {
        background: transparent;
    }

    .stMetric label {
        color: var(--text-secondary);
    }

    .stMetric [data-testid="stMetricValue"] {
        color: var(--accent-cyan);
        font-family: 'JetBrains Mono', monospace;
    }

    .code-block {
        background: var(--bg-primary);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 16px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 13px;
        color: var(--accent-green);
    }

    .divider {
        border: none;
        height: 1px;
        background: linear-gradient(90deg, transparent, var(--border), transparent);
        margin: 24px 0;
    }

    .glow-text {
        color: var(--accent-cyan);
        text-shadow: var(--glow-cyan);
    }

    .tech-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
        gap: 20px;
    }

    .status-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        display: inline-block;
        margin-right: 8px;
    }

    .status-dot.online {
        background: var(--accent-green);
        box-shadow: 0 0 8px var(--accent-green);
    }

    .status-dot.offline {
        background: #EF4444;
    }

    .status-dot.running {
        background: var(--accent-cyan);
        animation: pulse 1.5s infinite;
    }

    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
    }

    @keyframes glow {
        0%, 100% { box-shadow: var(--glow-cyan); }
        50% { box-shadow: 0 0 30px rgba(6, 182, 212, 0.6); }
    }

    .glow-animation {
        animation: glow 2s ease-in-out infinite;
    }

    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }

    ::-webkit-scrollbar-track {
        background: var(--bg-primary);
    }

    ::-webkit-scrollbar-thumb {
        background: var(--bg-tertiary);
        border-radius: 4px;
    }

    ::-webkit-scrollbar-thumb:hover {
        background: var(--accent-cyan);
    }
    </style>
    """

    st.markdown(CSS, unsafe_allow_html=True)
