# dashboard/components/auth.py

import os
import streamlit as st
import hashlib

ADMIN_PASSWORD_HASH = hashlib.sha256(
    os.getenv("DASHBOARD_PASSWORD", "admin123").encode()
).hexdigest()


def require_login():
    """登录验证，未登录则显示登录表单并 st.stop()"""
    if st.session_state.get("authenticated"):
        return

    st.set_page_config(page_title="登录", page_icon="🔐", layout="centered")

    st.markdown(
        """
    <style>
        .login-container {
            max-width: 400px;
            margin: 100px auto;
            padding: 30px;
            background: rgba(30, 30, 50, 0.9);
            border-radius: 16px;
            border: 1px solid rgba(255,255,255,0.1);
            text-align: center;
        }
        .login-title {
            color: white;
            font-size: 28px;
            margin-bottom: 30px;
        }
    </style>
    """,
        unsafe_allow_html=True,
    )

    st.markdown('<p class="login-title">🔐 管理面板登录</p>', unsafe_allow_html=True)

    password = st.text_input(
        "密码", type="password", label_visibility="collapsed", placeholder="输入密码..."
    )

    if password:
        if hashlib.sha256(password.encode()).hexdigest() == ADMIN_PASSWORD_HASH:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("密码错误")

    st.stop()
