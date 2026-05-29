"""Database adaptation for Community App."""

from backend.services.api.community_app.models import Base
from backend.shared.database_manager_v2 import get_session

# This is required by schema_registry for metadata discovery
__all__ = ["Base", "get_session"]
