"""
Simulation API dependencies adapter.
Re-exports deps from trade service for simulation history router compatibility.
"""

from backend.services.trade.deps import AuthContext, get_auth_context, get_db

__all__ = [
    "AuthContext",
    "get_auth_context",
    "get_db",
]
