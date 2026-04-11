"""
Centralized error handling for the LLMFed API.

Provides consistent error responses and exception handlers.
"""

import logging
from typing import Union
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from api_gateway.validation import ValidationError

logger = logging.getLogger(__name__)


class APIError(Exception):
    """Base class for API errors."""
    
    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: dict = None
    ):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class ResourceNotFoundError(APIError):
    """Raised when a requested resource is not found."""
    
    def __init__(self, resource_type: str, resource_id: str):
        super().__init__(
            message=f"{resource_type} not found",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"resource_type": resource_type, "resource_id": resource_id}
        )


class ResourceAlreadyExistsError(APIError):
    """Raised when trying to create a resource that already exists."""
    
    def __init__(self, resource_type: str, identifier: str):
        super().__init__(
            message=f"{resource_type} already exists",
            status_code=status.HTTP_409_CONFLICT,
            details={"resource_type": resource_type, "identifier": identifier}
        )


class UnauthorizedError(APIError):
    """Raised when authentication fails."""
    
    def __init__(self, message: str = "Authentication required"):
        super().__init__(
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED
        )


class ForbiddenError(APIError):
    """Raised when user doesn't have permission."""
    
    def __init__(self, message: str = "Permission denied"):
        super().__init__(
            message=message,
            status_code=status.HTTP_403_FORBIDDEN
        )


class ServiceUnavailableError(APIError):
    """Raised when a required service is unavailable."""
    
    def __init__(self, service: str, details: str = None):
        super().__init__(
            message=f"Service unavailable: {service}",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details={"service": service, "details": details}
        )


def create_error_response(
    message: str,
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
    details: dict = None,
    error_code: str = None
) -> JSONResponse:
    """
    Create a standardized error response.
    
    Args:
        message: Error message
        status_code: HTTP status code
        details: Additional error details
        error_code: Internal error code for tracking
        
    Returns:
        JSONResponse with error details
    """
    response_data = {
        "error": True,
        "message": message,
        "status_code": status_code
    }
    
    if details:
        response_data["details"] = details
    
    if error_code:
        response_data["error_code"] = error_code
    
    return JSONResponse(
        status_code=status_code,
        content=response_data
    )


async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    """Handler for APIError exceptions."""
    logger.error(
        f"API Error: {exc.message}",
        extra={
            "status_code": exc.status_code,
            "details": exc.details,
            "path": request.url.path
        }
    )
    
    return create_error_response(
        message=exc.message,
        status_code=exc.status_code,
        details=exc.details
    )


async def validation_error_handler(
    request: Request,
    exc: Union[RequestValidationError, PydanticValidationError, ValidationError]
) -> JSONResponse:
    """Handler for validation errors."""
    logger.warning(
        f"Validation error on {request.url.path}",
        extra={"errors": str(exc)}
    )
    
    if isinstance(exc, RequestValidationError):
        errors = exc.errors()
        details = {
            "validation_errors": [
                {
                    "field": ".".join(str(loc) for loc in error["loc"]),
                    "message": error["msg"],
                    "type": error["type"]
                }
                for error in errors
            ]
        }
        message = "Request validation failed"
    elif isinstance(exc, ValidationError):
        details = {"message": str(exc)}
        message = str(exc)
    else:
        details = {"message": str(exc)}
        message = "Validation error"
    
    return create_error_response(
        message=message,
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        details=details,
        error_code="VALIDATION_ERROR"
    )


async def database_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    """Handler for database errors."""
    logger.error(
        f"Database error on {request.url.path}: {str(exc)}",
        exc_info=True
    )
    
    if isinstance(exc, IntegrityError):
        # Handle constraint violations
        message = "Database constraint violation"
        details = {"error": "The operation violates a database constraint"}
        status_code = status.HTTP_409_CONFLICT
    else:
        # Generic database error
        message = "Database operation failed"
        details = {"error": "An error occurred while accessing the database"}
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    
    return create_error_response(
        message=message,
        status_code=status_code,
        details=details,
        error_code="DATABASE_ERROR"
    )


async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException
) -> JSONResponse:
    """Handler for HTTP exceptions."""
    logger.warning(
        f"HTTP {exc.status_code} on {request.url.path}: {exc.detail}"
    )
    
    return create_error_response(
        message=str(exc.detail),
        status_code=exc.status_code,
        error_code=f"HTTP_{exc.status_code}"
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handler for uncaught exceptions."""
    logger.error(
        f"Unhandled exception on {request.url.path}: {str(exc)}",
        exc_info=True
    )
    
    # In production, don't expose internal error details
    import os
    debug_mode = os.getenv("DEBUG_MODE", "false").lower() == "true"
    
    if debug_mode:
        import re
        exc_msg = str(exc)
        # Redact patterns that may contain secrets
        exc_msg = re.sub(
            r'(?i)(api[_-]?key|password|token|secret)[\s=:]+\S+',
            r'\1=***REDACTED***',
            exc_msg,
        )
        details = {
            "exception_type": type(exc).__name__,
            "exception_message": exc_msg,
        }
    else:
        details = None
    
    return create_error_response(
        message="An internal server error occurred",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        details=details,
        error_code="INTERNAL_SERVER_ERROR"
    )


def register_error_handlers(app):
    """
    Register all error handlers with the FastAPI application.
    
    Args:
        app: FastAPI application instance
    """
    app.add_exception_handler(APIError, api_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(ValidationError, validation_error_handler)
    app.add_exception_handler(SQLAlchemyError, database_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
    
    logger.info("Error handlers registered")
