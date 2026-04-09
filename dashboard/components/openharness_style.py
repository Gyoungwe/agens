# dashboard/components/openharness_style.py

import streamlit as st


def apply_theme(is_dark=True):
    if is_dark:
        bg_primary = "#0d1117"
        bg_secondary = "#161b22"
        bg_tertiary = "#21262d"
        bg_elevated = "#30363d"
        text_primary = "#e6edf3"
        text_secondary = "#8b949e"
        text_muted = "#6e7681"
        accent_blue = "#58a6ff"
        accent_green = "#3fb950"
        accent_purple = "#a371f7"
        accent_orange = "#d29922"
        accent_red = "#f85149"
        accent_cyan = "#39c5cf"
        border = "#30363d"
        shadow = "rgba(0,0,0,0.4)"
    else:
        bg_primary = "#ffffff"
        bg_secondary = "#f6f8fa"
        bg_tertiary = "#eaeef2"
        bg_elevated = "#ffffff"
        text_primary = "#1f2328"
        text_secondary = "#656d76"
        text_muted = "#8c959f"
        accent_blue = "#0969da"
        accent_green = "#1a7f37"
        accent_purple = "#8250df"
        accent_orange = "#9a6700"
        accent_red = "#cf222e"
        accent_cyan = "#0598bc"
        border = "#d0d7de"
        shadow = "rgba(0,0,0,0.1)"

    st.session_state["theme"] = {
        "is_dark": is_dark,
        "bg_primary": bg_primary,
        "bg_secondary": bg_secondary,
        "bg_tertiary": bg_tertiary,
        "bg_elevated": bg_elevated,
        "text_primary": text_primary,
        "text_secondary": text_secondary,
        "text_muted": text_muted,
        "accent_blue": accent_blue,
        "accent_green": accent_green,
        "accent_purple": accent_purple,
        "accent_orange": accent_orange,
        "accent_red": accent_red,
        "accent_cyan": accent_cyan,
        "border": border,
        "shadow": shadow,
    }


def get_theme():
    if "theme" not in st.session_state:
        apply_theme(is_dark=True)
    return st.session_state["theme"]


def render_theme_css():
    t = get_theme()

    CSS = f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

    * {{
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        box-sizing: border-box;
    }}

    .stApp {{
        background: {t["bg_primary"]};
        color: {t["text_primary"]};
        min-height: 100vh;
    }}

    /* Sidebar */
    [data-testid="stSidebar"] {{
        background: {t["bg_secondary"]};
        border-right: 1px solid {t["border"]};
        width: 220px;
    }}

    .sidebar-header {{
        padding: 16px;
        border-bottom: 1px solid {t["border"]};
        display: flex;
        align-items: center;
        justify-content: space-between;
    }}

    .sidebar-logo {{
        font-size: 16px;
        font-weight: 700;
        color: {t["text_primary"]};
        font-family: 'JetBrains Mono', monospace;
    }}

    .sidebar-logo span {{
        color: {t["accent_blue"]};
    }}

    .nav-section {{
        padding: 12px 8px;
    }}

    .nav-section-title {{
        font-size: 11px;
        font-weight: 600;
        color: {t["text_muted"]};
        text-transform: uppercase;
        letter-spacing: 0.5px;
        padding: 8px 12px 4px;
    }}

    .nav-item {{
        display: flex;
        align-items: center;
        padding: 8px 12px;
        margin: 2px 4px;
        border-radius: 6px;
        color: {t["text_secondary"]};
        font-size: 13px;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.15s ease;
    }}

    .nav-item:hover {{
        background: {t["bg_tertiary"]};
        color: {t["text_primary"]};
    }}

    .nav-item.active {{
        background: {t["accent_blue"]}15;
        color: {t["accent_blue"]};
    }}

    .nav-item-icon {{
        width: 18px;
        margin-right: 10px;
        font-size: 14px;
    }}

    .nav-item-badge {{
        margin-left: auto;
        background: {t["accent_red"]};
        color: white;
        font-size: 10px;
        font-weight: 600;
        padding: 2px 6px;
        border-radius: 10px;
        min-width: 18px;
        text-align: center;
    }}

    /* Main content */
    .main-header {{
        padding: 20px 24px;
        border-bottom: 1px solid {t["border"]};
        background: {t["bg_secondary"]};
    }}

    .header-title {{
        font-size: 20px;
        font-weight: 700;
        color: {t["text_primary"]};
        font-family: 'JetBrains Mono', monospace;
        margin: 0;
    }}

    .header-subtitle {{
        font-size: 13px;
        color: {t["text_muted"]};
        margin-top: 4px;
    }}

    .main-content {{
        padding: 24px;
        max-width: 1400px;
    }}

    /* Cards */
    .card {{
        background: {t["bg_secondary"]};
        border: 1px solid {t["border"]};
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 16px;
    }}

    .card-header {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 12px;
        padding-bottom: 12px;
        border-bottom: 1px solid {t["border"]};
    }}

    .card-title {{
        font-size: 14px;
        font-weight: 600;
        color: {t["text_primary"]};
        font-family: 'JetBrains Mono', monospace;
    }}

    /* Metric cards */
    .metric-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
        gap: 12px;
        margin-bottom: 20px;
    }}

    .metric-card {{
        background: {t["bg_secondary"]};
        border: 1px solid {t["border"]};
        border-radius: 8px;
        padding: 16px;
        transition: all 0.2s ease;
    }}

    .metric-card:hover {{
        border-color: {t["accent_blue"]};
        box-shadow: 0 2px 8px {t["shadow"]};
    }}

    .metric-value {{
        font-size: 28px;
        font-weight: 700;
        color: {t["accent_blue"]};
        font-family: 'JetBrains Mono', monospace;
    }}

    .metric-label {{
        font-size: 12px;
        color: {t["text_muted"]};
        margin-top: 4px;
        font-weight: 500;
    }}

    /* Status badges */
    .status-badge {{
        display: inline-flex;
        align-items: center;
        padding: 3px 8px;
        border-radius: 12px;
        font-size: 11px;
        font-weight: 600;
    }}

    .status-running {{
        background: {t["accent_blue"]}20;
        color: {t["accent_blue"]};
    }}

    .status-success, .status-online {{
        background: {t["accent_green"]}20;
        color: {t["accent_green"]};
    }}

    .status-pending, .status-warning {{
        background: {t["accent_orange"]}20;
        color: {t["accent_orange"]};
    }}

    .status-error, .status-offline {{
        background: {t["accent_red"]}20;
        color: {t["accent_red"]};
    }}

    /* Agent cards */
    .agent-list {{
        display: flex;
        flex-direction: column;
        gap: 8px;
    }}

    .agent-card {{
        background: {t["bg_tertiary"]};
        border: 1px solid {t["border"]};
        border-radius: 8px;
        padding: 12px 16px;
        display: flex;
        align-items: center;
        gap: 12px;
        transition: all 0.2s ease;
    }}

    .agent-card:hover {{
        border-color: {t["accent_blue"]};
    }}

    .agent-card.active {{
        border-color: {t["accent_blue"]};
        background: {t["accent_blue"]}10;
    }}

    .agent-icon {{
        width: 36px;
        height: 36px;
        border-radius: 8px;
        background: {t["accent_blue"]}20;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 16px;
    }}

    .agent-info {{
        flex: 1;
    }}

    .agent-name {{
        font-size: 13px;
        font-weight: 600;
        color: {t["text_primary"]};
        font-family: 'JetBrains Mono', monospace;
    }}

    .agent-status {{
        font-size: 11px;
        color: {t["text_muted"]};
        margin-top: 2px;
    }}

    /* Step tracker */
    .step-tracker {{
        display: flex;
        flex-direction: column;
        gap: 0;
    }}

    .step-item {{
        display: flex;
        gap: 12px;
        padding: 12px 0;
        position: relative;
    }}

    .step-item:not(:last-child)::before {{
        content: '';
        position: absolute;
        left: 15px;
        top: 44px;
        bottom: 0;
        width: 2px;
        background: {t["border"]};
    }}

    .step-item.completed:not(:last-child)::before {{
        background: {t["accent_green"]};
    }}

    .step-icon {{
        width: 32px;
        height: 32px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 14px;
        flex-shrink: 0;
        z-index: 1;
    }}

    .step-icon.pending {{
        background: {t["bg_tertiary"]};
        border: 2px solid {t["border"]};
    }}

    .step-icon.running {{
        background: {t["accent_blue"]};
        color: white;
        animation: pulse 1.5s infinite;
    }}

    .step-icon.completed {{
        background: {t["accent_green"]};
        color: white;
    }}

    .step-icon.error {{
        background: {t["accent_red"]};
        color: white;
    }}

    .step-content {{
        flex: 1;
        padding-bottom: 12px;
    }}

    .step-title {{
        font-size: 13px;
        font-weight: 600;
        color: {t["text_primary"]};
    }}

    .step-description {{
        font-size: 12px;
        color: {t["text_muted"]};
        margin-top: 2px;
    }}

    .step-result {{
        margin-top: 8px;
        padding: 10px 12px;
        background: {t["bg_primary"]};
        border: 1px solid {t["border"]};
        border-radius: 6px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 12px;
        color: {t["text_secondary"]};
        max-height: 150px;
        overflow-y: auto;
    }}

    /* Code blocks */
    .code-block {{
        background: {t["bg_primary"]};
        border: 1px solid {t["border"]};
        border-radius: 6px;
        padding: 12px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 12px;
        color: {t["accent_green"]};
        overflow-x: auto;
    }}

    /* Chat messages */
    .chat-container {{
        display: flex;
        flex-direction: column;
        gap: 16px;
        height: 400px;
        overflow-y: auto;
        padding: 16px;
        background: {t["bg_primary"]};
        border: 1px solid {t["border"]};
        border-radius: 8px;
    }}

    .chat-message {{
        max-width: 80%;
        padding: 12px 16px;
        border-radius: 12px;
        font-size: 13px;
        line-height: 1.5;
    }}

    .chat-message.user {{
        align-self: flex-end;
        background: {t["accent_blue"]};
        color: white;
        border-bottom-right-radius: 4px;
    }}

    .chat-message.assistant {{
        align-self: flex-start;
        background: {t["bg_tertiary"]};
        color: {t["text_primary"]};
        border-bottom-left-radius: 4px;
    }}

    /* Input styling */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea {{
        background: {t["bg_tertiary"]};
        border: 1px solid {t["border"]};
        border-radius: 6px;
        color: {t["text_primary"]};
        font-size: 13px;
    }}

    .stTextInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus {{
        border-color: {t["accent_blue"]};
        box-shadow: 0 0 0 2px {t["accent_blue"]}20;
    }}

    .stSelectbox > div > div {{
        background: {t["bg_tertiary"]};
        border: 1px solid {t["border"]};
        border-radius: 6px;
    }}

    /* Buttons */
    .stButton > button {{
        border-radius: 6px;
        font-weight: 500;
        font-size: 13px;
        border: 1px solid {t["border"]};
        background: {t["bg_tertiary"]};
        color: {t["text_primary"]};
        transition: all 0.15s ease;
    }}

    .stButton > button:hover {{
        border-color: {t["accent_blue"]};
        color: {t["accent_blue"]};
    }}

    .stButton > button[data-baseweb="button"] {{
        background: {t["accent_blue"]};
        color: white;
        border: none;
    }}

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 8px;
        border-bottom: 1px solid {t["border"]};
    }}

    .stTabs [data-baseweb="tab"] {{
        background: transparent;
        color: {t["text_secondary"]};
        border: none;
        border-bottom: 2px solid transparent;
        padding: 8px 16px;
        font-weight: 500;
        font-size: 13px;
    }}

    .stTabs [data-baseweb="tab"]:hover {{
        color: {t["text_primary"]};
    }}

    .stTabs [data-baseweb="tab"][aria-selected="true"] {{
        color: {t["accent_blue"]};
        border-bottom-color: {t["accent_blue"]};
    }}

    /* Divider */
    hr {{
        border: none;
        height: 1px;
        background: {t["border"]};
        margin: 20px 0;
    }}

    /* Theme toggle */
    .theme-toggle {{
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 8px 12px;
        background: {t["bg_tertiary"]};
        border-radius: 6px;
        cursor: pointer;
    }}

    /* Expander */
    .streamlit-expander {{
        background: {t["bg_secondary"]};
        border: 1px solid {t["border"]};
        border-radius: 8px;
    }}

    /* Progress bar */
    .stProgress > div > div > div {{
        background: {t["accent_blue"]};
    }}

    /* Scrollbar */
    ::-webkit-scrollbar {{
        width: 8px;
        height: 8px;
    }}

    ::-webkit-scrollbar-track {{
        background: {t["bg_primary"]};
    }}

    ::-webkit-scrollbar-thumb {{
        background: {t["bg_elevated"]};
        border-radius: 4px;
    }}

    ::-webkit-scrollbar-thumb:hover {{
        background: {t["text_muted"]};
    }}

    @keyframes pulse {{
        0%, 100% {{ opacity: 1; }}
        50% {{ opacity: 0.6; }}
    }}

    @keyframes spin {{
        from {{ transform: rotate(0deg); }}
        to {{ transform: rotate(360deg); }}
    }}
    </style>
    """
    st.markdown(CSS, unsafe_allow_html=True)
