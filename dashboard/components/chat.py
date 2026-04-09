# dashboard/components/chat.py

import asyncio
import streamlit as st
from typing import AsyncIterator, List

from providers.base_provider import ChatMessage


def render_chat_message(role: str, content: str):
    """渲染单条聊天消息"""
    if role == "user":
        st.markdown(
            f"""
        <div style="display: flex; justify-content: flex-end; margin: 12px 0;">
            <div style="background: #007AFF; color: white; padding: 12px 16px; 
                        border-radius: 18px 18px 4px 18px; max-width: 70%;
                        font-size: 14px; line-height: 1.5;">
                {content}
            </div>
        </div>
        """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"""
        <div style="display: flex; justify-content: flex-start; margin: 12px 0;">
            <div style="background: #E9E9EB; color: #1D1D1F; padding: 12px 16px;
                        border-radius: 18px 18px 18px 4px; max-width: 70%;
                        font-size: 14px; line-height: 1.5;">
                {content}
            </div>
        </div>
        """,
            unsafe_allow_html=True,
        )


def render_chat_history(messages: List[dict]):
    """渲染完整聊天历史"""
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        render_chat_message(role, content)


async def stream_chat_response(
    orchestrator,
    user_input: str,
    session_id: str = None,
) -> AsyncIterator[str]:
    """流式获取聊天响应"""
    if hasattr(orchestrator, "run_stream"):
        async for chunk in orchestrator.run_stream(user_input, session_id):
            yield chunk
    else:
        result = await orchestrator.run(user_input, session_id)
        yield result


def chat_input_container():
    """聊天输入框容器"""
    return st.container()


def render_chat_input(placeholder: str = "输入消息..."):
    """渲染聊天输入框"""
    return st.chat_input(placeholder)
