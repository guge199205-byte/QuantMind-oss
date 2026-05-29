"""
Error Handler Middleware
"""

import logging

from fastapi import Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


async def error_handler_middleware(request: Request, call_next):
    """Global error handler"""
    try:
        return await call_next(request)
    except SQLAlchemyError as e:
        logger.error(f"Database error: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Database error occurred"},
        )
    except ValueError as e:
        logger.warning(f"Validation error: {e}")
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"detail": str(e)})
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
        )
