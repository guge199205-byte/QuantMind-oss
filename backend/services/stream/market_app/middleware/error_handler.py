"""Error handler middleware"""

import logging

from fastapi import Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Global error handler"""

    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response

        except SQLAlchemyError as e:
            logger.error(f"Database error: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": "Database error",
                    "detail": "An error occurred while accessing the database",
                },
            )

        except ValueError as e:
            logger.error(f"Validation error: {e}")
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "error": "Validation error",
                    "detail": str(e),
                },
            )

        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": "Internal server error",
                    "detail": "An unexpected error occurred",
                },
            )
