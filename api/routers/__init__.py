# api/routers/__init__.py
from .skill_router import router as skill_router
from .agent_router import router as agent_router
from .soul_router import router as soul_router
from .evolution_router import router as evolution_router

__all__ = ["skill_router", "agent_router", "soul_router", "evolution_router"]
