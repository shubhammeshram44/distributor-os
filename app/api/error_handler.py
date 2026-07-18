"""
Global error handling utilities for FastAPI
"""

from fastapi import HTTPException, status
from pydantic import BaseModel
from typing import Optional, Any, Dict

class ApiError(BaseModel):
    """Standard API error response"""
    status_code: int
    message: str
    detail: Optional[str] = None
    code: Optional[str] = None
    field: Optional[str] = None

class ValidationErrorResponse(BaseModel):
    """Validation error response"""
    status_code: int = 422
    message: str = "Validation error"
    errors: list[Dict[str, Any]]

def bad_request(detail: str, field: str = None, code: str = None) -> HTTPException:
    """Return 400 Bad Request"""
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=detail
    )

def unauthorized(detail: str = "Unauthorized") -> HTTPException:
    """Return 401 Unauthorized"""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"}
    )

def forbidden(detail: str = "Forbidden") -> HTTPException:
    """Return 403 Forbidden"""
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=detail
    )

def not_found(resource: str = "Resource") -> HTTPException:
    """Return 404 Not Found"""
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"{resource} not found"
    )

def conflict(detail: str) -> HTTPException:
    """Return 409 Conflict"""
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=detail
    )

def validation_error(message: str, errors: list = None) -> HTTPException:
    """Return 422 Validation Error"""
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=message
    )

def server_error(detail: str = "Internal server error") -> HTTPException:
    """Return 500 Internal Server Error"""
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=detail
    )

class ApiErrorHandler:
    """Helper class for consistent error responses"""
    
    @staticmethod
    def handle_db_error(error: Exception) -> HTTPException:
        """Handle database errors"""
        error_msg = str(error)
        if "duplicate" in error_msg.lower():
            return conflict("Resource already exists")
        if "foreign key" in error_msg.lower():
            return bad_request("Invalid reference to another resource")
        return server_error("Database error occurred")

    @staticmethod
    def handle_validation_error(error: Exception) -> HTTPException:
        """Handle validation errors"""
        return validation_error(str(error))

    @staticmethod
    def handle_permission_error(resource: str = "resource") -> HTTPException:
        """Handle permission errors"""
        return forbidden(f"You don't have permission to access this {resource}")

def success_response(data: Any, status_code: int = 200, message: str = "Success"):
    """Return success response"""
    return {
        "status": "success",
        "message": message,
        "data": data,
        "code": status_code
    }
