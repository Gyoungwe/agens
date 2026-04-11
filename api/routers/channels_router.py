import os
import logging
import uuid
import json
from typing import Any, Dict, Optional, Callable

from fastapi import APIRouter, Request, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/channels", tags=["channels"])

_orch_getter: Optional[Callable[[], Any]] = None
_session_manager: Any = None
_channel_session_map: Dict[str, str] = {}
_runtime_channel_config: Dict[str, str] = {
    "wecom_bot_token": os.getenv("WECOM_BOT_TOKEN", ""),
    "feishu_bot_app_id": os.getenv("FEISHU_BOT_APP_ID", ""),
}


def set_runtime(orch_getter: Callable[[], Any], session_manager: Any):
    global _orch_getter, _session_manager
    _orch_getter = orch_getter
    _session_manager = session_manager


def _mask_secret(v: str) -> str:
    if not v:
        return ""
    if len(v) <= 6:
        return "*" * len(v)
    return f"{v[:3]}{'*' * (len(v) - 6)}{v[-3:]}"


def _extract_text(payload: Dict[str, Any]) -> str:
    # WeCom text payloads
    if isinstance(payload.get("text"), dict):
        text = payload.get("text", {}).get("content")
        if text:
            return str(text)
    # Feishu event payloads
    event = payload.get("event", {}) if isinstance(payload.get("event"), dict) else {}
    message = event.get("message", {}) if isinstance(event.get("message"), dict) else {}
    if isinstance(message.get("content"), str):
        content = message.get("content")
        if content:
            # Feishu message.content is often a JSON string like {"text":"..."}
            try:
                decoded = json.loads(content)
                if isinstance(decoded, dict) and isinstance(decoded.get("text"), str):
                    return decoded["text"]
            except Exception:
                pass
            return content
    # Generic fallback
    if isinstance(payload.get("content"), str):
        return payload.get("content")
    return ""


def _extract_user_key(channel: str, payload: Dict[str, Any]) -> str:
    # WeCom common fields
    if isinstance(payload.get("from"), dict):
        uid = payload.get("from", {}).get("user_id") or payload.get("from", {}).get(
            "id"
        )
        if uid:
            return f"{channel}:{uid}"
    if isinstance(payload.get("sender"), dict):
        uid = payload.get("sender", {}).get("user_id") or payload.get("sender", {}).get(
            "id"
        )
        if uid:
            return f"{channel}:{uid}"
    # Feishu event shape
    event = payload.get("event", {}) if isinstance(payload.get("event"), dict) else {}
    sender = event.get("sender", {}) if isinstance(event.get("sender"), dict) else {}
    sender_id = (
        sender.get("sender_id", {}) if isinstance(sender.get("sender_id"), dict) else {}
    )
    uid = sender_id.get("open_id") or sender_id.get("user_id")
    if uid:
        return f"{channel}:{uid}"
    return f"{channel}:anonymous"


async def _run_channel_chat(channel: str, text: str, user_key: str) -> str:
    if not text.strip():
        return "收到空消息。"
    if not _orch_getter or not _session_manager:
        return "系统未初始化，稍后再试。"

    orch = _orch_getter()
    if not orch:
        return "系统未初始化，稍后再试。"
    session_id = _channel_session_map.get(user_key)
    if not session_id:
        session_id = _session_manager.new_session(title=f"{channel}:{user_key[-12:]}")
        _channel_session_map[user_key] = session_id

    trace_id = str(uuid.uuid4())
    try:
        result = await orch.run(
            user_input=text,
            session_id=session_id,
            trace_id=trace_id,
            memory_scope="global",
        )
        return str(result or "")[:2000]
    except Exception as e:
        logger.error(f"channel_bridge_run_failed channel={channel} error={e}")
        return f"处理失败：{type(e).__name__}: {e}"


@router.get("/status")
async def channels_status():
    wecom_token = _runtime_channel_config.get("wecom_bot_token") or os.getenv(
        "WECOM_BOT_TOKEN", ""
    )
    feishu_app_id = _runtime_channel_config.get("feishu_bot_app_id") or os.getenv(
        "FEISHU_BOT_APP_ID", ""
    )
    return {
        "wecom_enabled": bool(wecom_token),
        "feishu_enabled": bool(feishu_app_id),
        "runtime_ready": bool(_orch_getter and _session_manager),
        "active_channel_sessions": len(_channel_session_map),
        "wecom_webhook": "/api/channels/wecom/webhook",
        "feishu_webhook": "/api/channels/feishu/webhook",
    }


@router.get("/config")
async def get_channels_config():
    wecom_token = _runtime_channel_config.get("wecom_bot_token") or os.getenv(
        "WECOM_BOT_TOKEN", ""
    )
    feishu_app_id = _runtime_channel_config.get("feishu_bot_app_id") or os.getenv(
        "FEISHU_BOT_APP_ID", ""
    )
    return {
        "wecom": {
            "configured": bool(wecom_token),
            "token_masked": _mask_secret(wecom_token),
        },
        "feishu": {
            "configured": bool(feishu_app_id),
            "app_id_masked": _mask_secret(feishu_app_id),
        },
    }


@router.put("/config")
async def set_channels_config(request: Request):
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid config payload")

    wecom = payload.get("wecom") if isinstance(payload.get("wecom"), dict) else {}
    feishu = payload.get("feishu") if isinstance(payload.get("feishu"), dict) else {}

    wecom_token = str(wecom.get("bot_token", "")).strip()
    feishu_app_id = str(feishu.get("bot_app_id", "")).strip()

    if wecom_token:
        _runtime_channel_config["wecom_bot_token"] = wecom_token
    if feishu_app_id:
        _runtime_channel_config["feishu_bot_app_id"] = feishu_app_id

    return {
        "success": True,
        "message": "Channel pairing config updated.",
        "wecom_configured": bool(_runtime_channel_config.get("wecom_bot_token")),
        "feishu_configured": bool(_runtime_channel_config.get("feishu_bot_app_id")),
    }


@router.post("/wecom/webhook")
async def wecom_webhook(request: Request):
    payload = await request.json()
    token = _runtime_channel_config.get("wecom_bot_token") or os.getenv(
        "WECOM_BOT_TOKEN", ""
    )
    req_token = request.headers.get("X-WECOM-TOKEN", "")
    if token and req_token != token:
        raise HTTPException(status_code=401, detail="Invalid WeCom token")

    text = _extract_text(payload)
    user_key = _extract_user_key("wecom", payload)
    logger.info(f"wecom_webhook_received len={len(text)} user_key={user_key}")
    reply = await _run_channel_chat("wecom", text, user_key)
    return {"ok": True, "received": bool(text), "reply": reply}


@router.post("/feishu/webhook")
async def feishu_webhook(request: Request):
    payload = await request.json()
    verify = payload.get("challenge")
    if verify:
        return {"challenge": verify}

    app_id = _runtime_channel_config.get("feishu_bot_app_id") or os.getenv(
        "FEISHU_BOT_APP_ID", ""
    )
    req_app = request.headers.get("X-Feishu-App-Id", "")
    if app_id and req_app and req_app != app_id:
        raise HTTPException(status_code=401, detail="Invalid Feishu app id")

    text = _extract_text(payload)
    user_key = _extract_user_key("feishu", payload)
    logger.info(f"feishu_webhook_received len={len(text)} user_key={user_key}")
    reply = await _run_channel_chat("feishu", text, user_key)
    return {"ok": True, "received": bool(text), "reply": reply}
