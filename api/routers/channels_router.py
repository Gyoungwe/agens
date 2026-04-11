import os
import logging
from typing import Any, Dict

from fastapi import APIRouter, Request, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/channels", tags=["channels"])


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
        return message.get("content")
    # Generic fallback
    if isinstance(payload.get("content"), str):
        return payload.get("content")
    return ""


@router.get("/status")
async def channels_status():
    return {
        "wecom_enabled": bool(os.getenv("WECOM_BOT_TOKEN")),
        "feishu_enabled": bool(os.getenv("FEISHU_BOT_APP_ID")),
        "wecom_webhook": "/api/channels/wecom/webhook",
        "feishu_webhook": "/api/channels/feishu/webhook",
    }


@router.post("/wecom/webhook")
async def wecom_webhook(request: Request):
    payload = await request.json()
    token = os.getenv("WECOM_BOT_TOKEN", "")
    req_token = request.headers.get("X-WECOM-TOKEN", "")
    if token and req_token != token:
        raise HTTPException(status_code=401, detail="Invalid WeCom token")

    text = _extract_text(payload)
    logger.info(f"wecom_webhook_received len={len(text)}")
    return {"ok": True, "received": bool(text)}


@router.post("/feishu/webhook")
async def feishu_webhook(request: Request):
    payload = await request.json()
    verify = payload.get("challenge")
    if verify:
        return {"challenge": verify}

    app_id = os.getenv("FEISHU_BOT_APP_ID", "")
    req_app = request.headers.get("X-Feishu-App-Id", "")
    if app_id and req_app and req_app != app_id:
        raise HTTPException(status_code=401, detail="Invalid Feishu app id")

    text = _extract_text(payload)
    logger.info(f"feishu_webhook_received len={len(text)}")
    return {"ok": True, "received": bool(text)}
