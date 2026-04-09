# dashboard/components/apple_style.py

import streamlit as st

MINIMAL_CSS = """
<style>
    :root {
        --bg-primary: #0f0f23;
        --bg-secondary: #1a1a2e;
        --bg-card: rgba(30, 30, 50, 0.8);
        --text-primary: #ffffff;
        --text-secondary: rgba(255, 255, 255, 0.7);
        --accent: #4fc8ff;
        --accent-hover: #3ab8ff;
        --border: rgba(255, 255, 255, 0.1);
        --radius: 12px;
    }
    
    .stApp {
        background: var(--bg-primary);
        color: var(--text-primary);
    }
    
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%);
        border-right: 1px solid var(--border);
    }
    
    div[data-testid="stExpander"] {
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: var(--radius);
    }
    
    .stButton > button {
        border-radius: 8px;
        border: none;
        font-weight: 500;
        transition: all 0.2s;
    }
    
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea {
        background: var(--bg-secondary);
        border: 1px solid var(--border);
        border-radius: 8px;
        color: var(--text-primary);
    }
    
    .stTabs [data-baseweb="tab-list"] {
        background: var(--bg-secondary);
        padding: 4px;
        border-radius: 8px;
        gap: 4px;
    }
    
    .stTabs [aria-selected="true"] {
        background: var(--accent) !important;
        color: white !important;
        border-radius: 6px;
    }
    
    .info-box {
        background: rgba(79, 140, 255, 0.1);
        border: 1px solid rgba(79, 140, 255, 0.3);
        border-radius: var(--radius);
        padding: 12px 16px;
        color: var(--text-primary);
    }
    
    .success-box {
        background: rgba(52, 199, 89, 0.1);
        border: 1px solid rgba(52, 199, 89, 0.3);
        border-radius: var(--radius);
        padding: 12px 16px;
        color: var(--text-primary);
    }
    
    .warning-box {
        background: rgba(255, 149, 0, 0.1);
        border: 1px solid rgba(255, 149, 0, 0.3);
        border-radius: var(--radius);
        padding: 12px 16px;
        color: var(--text-primary);
    }
    
    .metric-card {
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 16px;
        text-align: center;
    }
    
    .stMetric {
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 15px;
    }
</style>
"""


def apply_apple_style():
    """应用简洁现代风格"""
    st.markdown(MINIMAL_CSS, unsafe_allow_html=True)


def metric_card(label: str, value: str | int):
    """指标卡片"""
    st.markdown(
        f"""
    <div class="metric-card">
        <div style="font-size: 28px; font-weight: 700; color: white;">{value}</div>
        <div style="font-size: 13px; color: rgba(255,255,255,0.6); margin-top: 4px;">{label}</div>
    </div>
    """,
        unsafe_allow_html=True,
    )


def status_badge(status: str):
    """状态徽章"""
    status_map = {
        "active": ("🟢", "活跃"),
        "running": ("🔵", "运行中"),
        "pending": ("🟡", "待处理"),
        "approved": ("✅", "已批准"),
        "rejected": ("❌", "已拒绝"),
        "installed": ("📦", "已安装"),
        "error": ("❌", "错误"),
        "disabled": ("🔴", "禁用"),
    }
    icon, text = status_map.get(status.lower(), ("⚪", status))
    st.markdown(f"{icon} {text}")


def info_box(message: str):
    """信息框"""
    st.markdown(f'<div class="info-box">{message}</div>', unsafe_allow_html=True)


def success_box(message: str):
    """成功框"""
    st.markdown(f'<div class="success-box">{message}</div>', unsafe_allow_html=True)


def warning_box(message: str):
    """警告框"""
    st.markdown(f'<div class="warning-box">{message}</div>', unsafe_allow_html=True)
