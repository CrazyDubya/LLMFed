"""
Enhanced structured logging configuration for LLMFed API.

Provides JSON logging, request tracking, and performance monitoring.
"""

import logging
import time
import json
import uuid
from typing import Any, Dict, Optional
from datetime import datetime
from fastapi import Request
import sys


class StructuredFormatter(logging.Formatter):
    """
    Structured JSON formatter for logging.
    
    Formats log records as JSON for easy parsing and analysis.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add extra fields if present
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_data["duration_ms"] = record.duration_ms
        
        if hasattr(record, "status_code"):
            log_data["status_code"] = record.status_code
        
        if hasattr(record, "path"):
            log_data["path"] = record.path
        
        if hasattr(record, "method"):
            log_data["method"] = record.method
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add any additional extra data
        if hasattr(record, "extra_data"):
            log_data["extra"] = record.extra_data
        
        return json.dumps(log_data)


def setup_logging(log_level: str = "INFO", use_json: bool = False):
    """
    Setup application logging configuration.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        use_json: Whether to use JSON formatted logging
    """
    level = getattr(logging, log_level.upper())
    
    # Remove existing handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create handler
    handler = logging.StreamHandler(sys.stdout)
    
    if use_json:
        # Use structured JSON logging
        formatter = StructuredFormatter()
    else:
        # Use standard formatting
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
    root_logger.setLevel(level)
    
    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("fastapi").setLevel(logging.WARNING)


class RequestLogger:
    """
    Request logging utility with performance tracking.
    """
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
    
    def log_request_start(self, request: Request, request_id: str):
        """Log the start of a request."""
        self.logger.info(
            f"Request started: {request.method} {request.url.path}",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "client_host": request.client.host if request.client else None
            }
        )
    
    def log_request_end(
        self,
        request: Request,
        request_id: str,
        status_code: int,
        duration_ms: float
    ):
        """Log the end of a request with performance metrics."""
        level = logging.INFO
        
        # Use different log levels based on status code
        if status_code >= 500:
            level = logging.ERROR
        elif status_code >= 400:
            level = logging.WARNING
        
        self.logger.log(
            level,
            f"Request completed: {request.method} {request.url.path} - {status_code} ({duration_ms:.2f}ms)",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": status_code,
                "duration_ms": duration_ms
            }
        )
    
    def log_error(
        self,
        request: Request,
        request_id: str,
        error: Exception,
        duration_ms: float
    ):
        """Log an error that occurred during request processing."""
        self.logger.error(
            f"Request failed: {request.method} {request.url.path} - {type(error).__name__}: {str(error)}",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "error_type": type(error).__name__,
                "duration_ms": duration_ms
            },
            exc_info=True
        )


def get_request_id(request: Request) -> str:
    """
    Get or generate a unique request ID.
    
    Checks for X-Request-ID header first, generates new UUID if not present.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Request ID string
    """
    request_id = request.headers.get("X-Request-ID")
    if not request_id:
        request_id = str(uuid.uuid4())
    return request_id


class PerformanceMonitor:
    """Simple performance monitoring for API endpoints.

    Caps tracked endpoints at MAX_ENDPOINTS to prevent unbounded growth (Rule 7, Rule 8).
    """

    MAX_ENDPOINTS = 10_000

    def __init__(self):
        self.metrics: Dict[str, Dict[str, Any]] = {}

    def record_request(self, method: str, path: str, duration_ms: float, status_code: int):
        """Record metrics for a request."""
        key = f"{method} {path}"

        if key not in self.metrics:
            if len(self.metrics) >= self.MAX_ENDPOINTS:
                return  # Refuse to grow past cap
            self.metrics[key] = {
                "count": 0,
                "total_duration_ms": 0.0,
                "min_duration_ms": float('inf'),
                "max_duration_ms": 0.0,
                "error_count": 0,
            }

        metrics = self.metrics[key]
        metrics["count"] += 1
        metrics["total_duration_ms"] += duration_ms
        metrics["min_duration_ms"] = min(metrics["min_duration_ms"], duration_ms)
        metrics["max_duration_ms"] = max(metrics["max_duration_ms"], duration_ms)

        if status_code >= 400:
            metrics["error_count"] += 1
    
    def get_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get current performance metrics."""
        result = {}
        for endpoint, metrics in self.metrics.items():
            result[endpoint] = {
                **metrics,
                "avg_duration_ms": metrics["total_duration_ms"] / metrics["count"] if metrics["count"] > 0 else 0,
                "error_rate": metrics["error_count"] / metrics["count"] if metrics["count"] > 0 else 0
            }
        return result
    
    def reset_metrics(self):
        """Reset all metrics."""
        self.metrics.clear()


# Global performance monitor instance
performance_monitor = PerformanceMonitor()


async def logging_middleware(request: Request, call_next):
    """
    Middleware for logging all requests with performance tracking.
    
    Args:
        request: FastAPI request
        call_next: Next middleware/endpoint
        
    Returns:
        Response with added headers
    """
    request_id = get_request_id(request)
    start_time = time.time()
    
    # Add request ID to request state for access in endpoints
    request.state.request_id = request_id
    
    try:
        # Process request
        response = await call_next(request)
        
        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000
        
        # Add request ID header to response
        response.headers["X-Request-ID"] = request_id
        
        # Record metrics
        performance_monitor.record_request(
            request.method,
            request.url.path,
            duration_ms,
            response.status_code
        )
        
        # Log request
        logger = logging.getLogger("api")
        request_logger = RequestLogger(logger)
        request_logger.log_request_end(request, request_id, response.status_code, duration_ms)
        
        return response
        
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        
        # Log error
        logger = logging.getLogger("api")
        request_logger = RequestLogger(logger)
        request_logger.log_error(request, request_id, e, duration_ms)
        
        raise
