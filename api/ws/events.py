# api/ws/events.py
"""
WebSocket Event Bus for real-time events
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import WebSocket, WebSocketDisconnect
from starlette.routing import Route
from utils.feature_logs import get_feature_logger

logger = logging.getLogger(__name__)
ws_log = get_feature_logger("ws")


class ConnectionManager:
    """Manages WebSocket connections"""

    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        """Accept and register a new WebSocket connection"""
        await websocket.accept()
        async with self._lock:
            self.active_connections.append(websocket)
        logger.info(f"[WS] Client connected. Total: {len(self.active_connections)}")
        ws_log.info(f"client_connected total={len(self.active_connections)}")

    async def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection"""
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
        logger.info(f"[WS] Client disconnected. Total: {len(self.active_connections)}")
        ws_log.info(f"client_disconnected total={len(self.active_connections)}")

    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast a message to all connected clients"""
        async with self._lock:
            disconnected = []
            for connection in self.active_connections:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.warning(f"[WS] Failed to send to client: {e}")
                    ws_log.warning(f"send_failed error={type(e).__name__}: {e}")
                    disconnected.append(connection)

            # Clean up disconnected clients
            for conn in disconnected:
                if conn in self.active_connections:
                    self.active_connections.remove(conn)

    @property
    def connection_count(self) -> int:
        return len(self.active_connections)


class EventBus:
    """
    Simple event bus for broadcasting system events to WebSocket clients.

    Events are pushed to all connected WebSocket clients in real-time.
    """

    def __init__(self, manager: ConnectionManager):
        self._manager = manager
        self._subscribers: List[asyncio.Queue] = []
        self._lock = asyncio.Lock()

    async def publish(self, event_type: str, data: Any):
        """Publish an event to all subscribers"""
        event = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
        }
        await self._manager.broadcast(event)

    async def subscribe(self) -> asyncio.Queue:
        """Subscribe to events (returns a queue)"""
        queue = asyncio.Queue()
        async with self._lock:
            self._subscribers.append(queue)
        return queue

    async def unsubscribe(self, queue: asyncio.Queue):
        """Unsubscribe from events"""
        async with self._lock:
            if queue in self._subscribers:
                self._subscribers.remove(queue)


# Global event bus instance
manager = ConnectionManager()
event_bus = EventBus(manager)


# Event types
async def publish_agent_status(agent_id: str, status: str, current_task: str = None):
    """Publish agent status change event"""
    await event_bus.publish(
        "agent_status_changed",
        {
            "agent_id": agent_id,
            "status": status,
            "current_task": current_task,
        },
    )


async def publish_approval_created(
    approval_id: str, agent_id: str, skill_id: str, reason: str
):
    """Publish new approval created event"""
    await event_bus.publish(
        "approval_created",
        {
            "approval_id": approval_id,
            "agent_id": agent_id,
            "skill_id": skill_id,
            "reason": reason,
            "status": "pending",
        },
    )


async def publish_approval_completed(approval_id: str, status: str):
    """Publish approval completed event"""
    await event_bus.publish(
        "approval_completed",
        {
            "approval_id": approval_id,
            "status": status,
        },
    )


async def publish_task_progress(task_id: str, progress: float, message: str):
    """Publish task progress event"""
    await event_bus.publish(
        "task_progress",
        {
            "task_id": task_id,
            "progress": progress,
            "message": message,
        },
    )


async def publish_memory_updated(owner: str, memory_id: str):
    """Publish memory updated event"""
    await event_bus.publish(
        "memory_updated",
        {
            "owner": owner,
            "memory_id": memory_id,
        },
    )


async def publish_session_updated(session_id: str, event: str):
    """Publish session updated event"""
    await event_bus.publish(
        "session_updated",
        {
            "session_id": session_id,
            "event": event,
        },
    )


# ─── Bio Workflow Stage Events ───────────────────────────────────────────────


async def publish_bio_stage_pending(
    stage: str,
    agent_id: str,
    trace_id: str,
    session_id: str,
):
    """Publish a bio workflow stage is about to start"""
    await event_bus.publish(
        "bio_stage_pending",
        {
            "stage": stage,
            "agent_id": agent_id,
            "trace_id": trace_id,
            "session_id": session_id,
        },
    )


async def publish_bio_stage_running(
    stage: str,
    agent_id: str,
    trace_id: str,
    session_id: str,
):
    """Publish a bio workflow stage is running"""
    await event_bus.publish(
        "bio_stage_running",
        {
            "stage": stage,
            "agent_id": agent_id,
            "trace_id": trace_id,
            "session_id": session_id,
        },
    )


async def publish_bio_stage_done(
    stage: str,
    agent_id: str,
    trace_id: str,
    session_id: str,
    status: str,
    elapsed_ms: int,
    output: str,
    error: str = None,
):
    """Publish a bio workflow stage has completed"""
    await event_bus.publish(
        "bio_stage_done",
        {
            "stage": stage,
            "agent_id": agent_id,
            "trace_id": trace_id,
            "session_id": session_id,
            "status": status,
            "elapsed_ms": elapsed_ms,
            "output": output,
            "error": error,
        },
    )


async def publish_bio_workflow_start(
    session_id: str,
    trace_id: str,
    goal: str,
):
    """Publish bio workflow has started"""
    await event_bus.publish(
        "bio_workflow_start",
        {
            "session_id": session_id,
            "trace_id": trace_id,
            "goal": goal,
        },
    )


async def publish_bio_workflow_done(
    session_id: str,
    trace_id: str,
    success: bool,
    status: str,
    total_stages: int,
    failed_stages: int,
):
    """Publish bio workflow has finished"""
    await event_bus.publish(
        "bio_workflow_done",
        {
            "session_id": session_id,
            "trace_id": trace_id,
            "success": success,
            "status": status,
            "total_stages": total_stages,
            "failed_stages": failed_stages,
        },
    )


async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time event streaming.

    Clients connect to /ws/events to receive system events.
    """
    await manager.connect(websocket)
    ws_log.info("websocket_endpoint_opened")
    try:
        while True:
            # Keep connection alive, handle incoming messages
            try:
                data = await websocket.receive_text()
                # Handle ping/pong or other client messages
                if data == "ping":
                    await websocket.send_text("pong")
                    ws_log.info("ping_pong")
            except WebSocketDisconnect:
                break
    except Exception as e:
        logger.error(f"[WS] Connection error: {e}")
        ws_log.error(f"connection_error error={type(e).__name__}: {e}")
    finally:
        await manager.disconnect(websocket)
        ws_log.info("websocket_endpoint_closed")
