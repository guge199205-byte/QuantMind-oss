"""
Reuse the consolidated notification router to avoid logic drift.
"""

from backend.services.api.routers.notifications import router

__all__ = ["router"]
