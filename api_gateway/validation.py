"""
Input validation utilities for the LLMFed API.

Provides validation functions and decorators for request data.
"""

import re
from typing import Optional, List
from pydantic import BaseModel, field_validator, Field
from fastapi import HTTPException, status


class ValidationError(Exception):
    """Custom validation error."""
    pass


def validate_agent_name(name: str) -> str:
    """
    Validate agent name.
    
    Rules:
    - Must be 3-50 characters
    - Can contain letters, numbers, spaces, hyphens, underscores
    - Cannot start or end with whitespace
    
    Args:
        name: Agent name to validate
        
    Returns:
        Validated name (stripped)
        
    Raises:
        ValidationError: If validation fails
    """
    if not name or not isinstance(name, str):
        raise ValidationError("Agent name is required")
    
    name = name.strip()
    
    if len(name) < 3:
        raise ValidationError("Agent name must be at least 3 characters")
    
    if len(name) > 50:
        raise ValidationError("Agent name must not exceed 50 characters")
    
    if not re.match(r'^[a-zA-Z0-9\s\-_]+$', name):
        raise ValidationError("Agent name can only contain letters, numbers, spaces, hyphens, and underscores")
    
    return name


def validate_user_id(user_id: str) -> str:
    """
    Validate user ID.
    
    Rules:
    - Must be 3-100 characters
    - Can contain letters, numbers, hyphens, underscores
    - No special characters or spaces
    
    Args:
        user_id: User ID to validate
        
    Returns:
        Validated user ID
        
    Raises:
        ValidationError: If validation fails
    """
    if not user_id or not isinstance(user_id, str):
        raise ValidationError("User ID is required")
    
    user_id = user_id.strip()
    
    if len(user_id) < 3:
        raise ValidationError("User ID must be at least 3 characters")
    
    if len(user_id) > 100:
        raise ValidationError("User ID must not exceed 100 characters")
    
    if not re.match(r'^[a-zA-Z0-9\-_]+$', user_id):
        raise ValidationError("User ID can only contain letters, numbers, hyphens, and underscores")
    
    return user_id


def validate_federation_name(name: str) -> str:
    """
    Validate federation name.
    
    Rules:
    - Must be 3-100 characters
    - Can contain letters, numbers, spaces, hyphens, underscores
    - Cannot start or end with whitespace
    
    Args:
        name: Federation name to validate
        
    Returns:
        Validated name (stripped)
        
    Raises:
        ValidationError: If validation fails
    """
    if not name or not isinstance(name, str):
        raise ValidationError("Federation name is required")
    
    name = name.strip()
    
    if len(name) < 3:
        raise ValidationError("Federation name must be at least 3 characters")
    
    if len(name) > 100:
        raise ValidationError("Federation name must not exceed 100 characters")
    
    if not re.match(r'^[a-zA-Z0-9\s\-_]+$', name):
        raise ValidationError("Federation name can only contain letters, numbers, spaces, hyphens, and underscores")
    
    return name


def validate_temperature(temperature: float) -> float:
    """
    Validate LLM temperature parameter.
    
    Rules:
    - Must be between 0.0 and 2.0
    
    Args:
        temperature: Temperature value
        
    Returns:
        Validated temperature
        
    Raises:
        ValidationError: If validation fails
    """
    if not isinstance(temperature, (int, float)):
        raise ValidationError("Temperature must be a number")
    
    if temperature < 0.0 or temperature > 2.0:
        raise ValidationError("Temperature must be between 0.0 and 2.0")
    
    return float(temperature)


def validate_max_tokens(max_tokens: Optional[int]) -> Optional[int]:
    """
    Validate max_tokens parameter.
    
    Rules:
    - Must be positive if provided
    - Maximum of 4096
    
    Args:
        max_tokens: Max tokens value
        
    Returns:
        Validated max_tokens
        
    Raises:
        ValidationError: If validation fails
    """
    if max_tokens is None:
        return None
    
    if not isinstance(max_tokens, int):
        raise ValidationError("Max tokens must be an integer")
    
    if max_tokens < 1:
        raise ValidationError("Max tokens must be positive")
    
    if max_tokens > 4096:
        raise ValidationError("Max tokens must not exceed 4096")
    
    return max_tokens


def sanitize_string(text: str, max_length: int = 1000) -> str:
    """
    Sanitize string input to prevent injection attacks.
    
    Args:
        text: Text to sanitize
        max_length: Maximum allowed length
        
    Returns:
        Sanitized text
        
    Raises:
        ValidationError: If validation fails
    """
    if not isinstance(text, str):
        raise ValidationError("Input must be a string")
    
    # Remove null bytes
    text = text.replace('\x00', '')
    
    # Limit length
    if len(text) > max_length:
        raise ValidationError(f"Input exceeds maximum length of {max_length} characters")
    
    return text


def validate_pagination_params(page: int = 1, per_page: int = 30) -> tuple:
    """
    Validate pagination parameters.
    
    Args:
        page: Page number (1-indexed)
        per_page: Items per page
        
    Returns:
        Tuple of (page, per_page)
        
    Raises:
        HTTPException: If validation fails
    """
    if page < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Page number must be at least 1"
        )
    
    if per_page < 1 or per_page > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Per page must be between 1 and 100"
        )
    
    return page, per_page


class EnhancedAgentCreateData(BaseModel):
    """Enhanced agent creation data with validation."""
    user_id: str = Field(..., min_length=3, max_length=100)
    name: str = Field(..., min_length=3, max_length=50)
    role: str = Field(..., pattern="^(participant|referee|crowd|announcer|promoter|backstage)$")
    gimmick_description: Optional[str] = Field(None, max_length=500)
    llm_config: dict
    federation_id: Optional[str] = Field(None, max_length=100)
    
    @field_validator('user_id')
    @classmethod
    def validate_user_id_field(cls, v):
        """Validate user ID format."""
        return validate_user_id(v)
    
    @field_validator('name')
    @classmethod
    def validate_name_field(cls, v):
        """Validate agent name format."""
        return validate_agent_name(v)
    
    @field_validator('gimmick_description')
    @classmethod
    def validate_gimmick(cls, v):
        """Validate gimmick description."""
        if v:
            return sanitize_string(v, max_length=500)
        return v
    
    @field_validator('llm_config')
    @classmethod
    def validate_llm_config_field(cls, v):
        """Validate LLM config structure."""
        if not isinstance(v, dict):
            raise ValueError("LLM config must be a dictionary")
        
        # Validate temperature if present
        if 'temperature' in v:
            v['temperature'] = validate_temperature(v['temperature'])
        
        # Validate max_tokens if present
        if 'max_tokens' in v:
            v['max_tokens'] = validate_max_tokens(v['max_tokens'])
        
        # Ensure model is present
        if 'model' not in v:
            v['model'] = 'long-gemma'  # Default model
        
        return v


class EnhancedFederationCreateData(BaseModel):
    """Enhanced federation creation data with validation."""
    name: str = Field(..., min_length=3, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    tier: int = Field(default=1, ge=1, le=5)
    owner_user_id: str = Field(..., min_length=3, max_length=100)
    
    @field_validator('name')
    @classmethod
    def validate_name_field(cls, v):
        """Validate federation name format."""
        return validate_federation_name(v)
    
    @field_validator('description')
    @classmethod
    def validate_description_field(cls, v):
        """Validate description."""
        if v:
            return sanitize_string(v, max_length=1000)
        return v
    
    @field_validator('owner_user_id')
    @classmethod
    def validate_owner_field(cls, v):
        """Validate owner user ID."""
        return validate_user_id(v)
