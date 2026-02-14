"""
Tests for input validation.

Tests validation functions and models for API inputs.
"""

import pytest
from api_gateway.validation import (
    validate_agent_name,
    validate_user_id,
    validate_federation_name,
    validate_temperature,
    validate_max_tokens,
    sanitize_string,
    validate_pagination_params,
    ValidationError,
    EnhancedAgentCreateData,
    EnhancedFederationCreateData
)
from fastapi import HTTPException


class TestAgentNameValidation:
    """Tests for agent name validation."""
    
    def test_valid_agent_name(self):
        """Test valid agent names."""
        assert validate_agent_name("The Wrestler") == "The Wrestler"
        assert validate_agent_name("Agent_123") == "Agent_123"
        assert validate_agent_name("Test-Agent") == "Test-Agent"
    
    def test_agent_name_too_short(self):
        """Test agent name too short."""
        with pytest.raises(ValidationError, match="at least 3 characters"):
            validate_agent_name("AB")
    
    def test_agent_name_too_long(self):
        """Test agent name too long."""
        long_name = "A" * 51
        with pytest.raises(ValidationError, match="must not exceed 50 characters"):
            validate_agent_name(long_name)
    
    def test_agent_name_invalid_characters(self):
        """Test agent name with invalid characters."""
        with pytest.raises(ValidationError, match="can only contain"):
            validate_agent_name("Agent@123")
        
        with pytest.raises(ValidationError):
            validate_agent_name("Agent<script>")
    
    def test_agent_name_strips_whitespace(self):
        """Test that agent name strips whitespace."""
        assert validate_agent_name("  Agent Name  ") == "Agent Name"
    
    def test_agent_name_empty(self):
        """Test empty agent name."""
        with pytest.raises(ValidationError, match="required"):
            validate_agent_name("")


class TestUserIdValidation:
    """Tests for user ID validation."""
    
    def test_valid_user_id(self):
        """Test valid user IDs."""
        assert validate_user_id("user123") == "user123"
        assert validate_user_id("test_user") == "test_user"
        assert validate_user_id("user-123") == "user-123"
    
    def test_user_id_too_short(self):
        """Test user ID too short."""
        with pytest.raises(ValidationError, match="at least 3 characters"):
            validate_user_id("ab")
    
    def test_user_id_too_long(self):
        """Test user ID too long."""
        long_id = "u" * 101
        with pytest.raises(ValidationError, match="must not exceed 100 characters"):
            validate_user_id(long_id)
    
    def test_user_id_no_spaces(self):
        """Test user ID cannot contain spaces."""
        with pytest.raises(ValidationError, match="can only contain"):
            validate_user_id("user 123")
    
    def test_user_id_no_special_chars(self):
        """Test user ID cannot contain special characters."""
        with pytest.raises(ValidationError):
            validate_user_id("user@123")


class TestTemperatureValidation:
    """Tests for temperature validation."""
    
    def test_valid_temperature(self):
        """Test valid temperature values."""
        assert validate_temperature(0.0) == 0.0
        assert validate_temperature(0.7) == 0.7
        assert validate_temperature(1.5) == 1.5
        assert validate_temperature(2.0) == 2.0
    
    def test_temperature_out_of_range(self):
        """Test temperature out of valid range."""
        with pytest.raises(ValidationError, match="between 0.0 and 2.0"):
            validate_temperature(-0.1)
        
        with pytest.raises(ValidationError, match="between 0.0 and 2.0"):
            validate_temperature(2.1)
    
    def test_temperature_wrong_type(self):
        """Test temperature with wrong type."""
        with pytest.raises(ValidationError, match="must be a number"):
            validate_temperature("0.7")


class TestMaxTokensValidation:
    """Tests for max_tokens validation."""
    
    def test_valid_max_tokens(self):
        """Test valid max_tokens values."""
        assert validate_max_tokens(100) == 100
        assert validate_max_tokens(1000) == 1000
        assert validate_max_tokens(None) is None
    
    def test_max_tokens_negative(self):
        """Test negative max_tokens."""
        with pytest.raises(ValidationError, match="must be positive"):
            validate_max_tokens(-1)
        
        with pytest.raises(ValidationError):
            validate_max_tokens(0)
    
    def test_max_tokens_exceeds_limit(self):
        """Test max_tokens exceeds limit."""
        with pytest.raises(ValidationError, match="must not exceed 4096"):
            validate_max_tokens(5000)


class TestSanitizeString:
    """Tests for string sanitization."""
    
    def test_sanitize_normal_string(self):
        """Test sanitizing normal strings."""
        assert sanitize_string("Hello World") == "Hello World"
    
    def test_sanitize_removes_null_bytes(self):
        """Test that null bytes are removed."""
        assert sanitize_string("Hello\x00World") == "HelloWorld"
    
    def test_sanitize_exceeds_length(self):
        """Test string exceeding maximum length."""
        long_string = "A" * 1001
        with pytest.raises(ValidationError, match="exceeds maximum length"):
            sanitize_string(long_string, max_length=1000)
    
    def test_sanitize_custom_max_length(self):
        """Test custom maximum length."""
        assert sanitize_string("Test", max_length=10) == "Test"
        
        with pytest.raises(ValidationError):
            sanitize_string("Test String", max_length=5)


class TestPaginationValidation:
    """Tests for pagination parameter validation."""
    
    def test_valid_pagination(self):
        """Test valid pagination parameters."""
        page, per_page = validate_pagination_params(1, 30)
        assert page == 1
        assert per_page == 30
    
    def test_invalid_page_number(self):
        """Test invalid page number."""
        with pytest.raises(HTTPException) as exc_info:
            validate_pagination_params(0, 30)
        
        assert exc_info.value.status_code == 400
        assert "at least 1" in exc_info.value.detail
    
    def test_invalid_per_page(self):
        """Test invalid per_page values."""
        with pytest.raises(HTTPException) as exc_info:
            validate_pagination_params(1, 0)
        
        assert exc_info.value.status_code == 400
        
        with pytest.raises(HTTPException) as exc_info:
            validate_pagination_params(1, 101)
        
        assert exc_info.value.status_code == 400


class TestEnhancedAgentCreateData:
    """Tests for EnhancedAgentCreateData model."""
    
    def test_valid_agent_data(self):
        """Test valid agent creation data."""
        data = EnhancedAgentCreateData(
            user_id="test_user",
            name="Test Agent",
            role="participant",
            gimmick_description="A test wrestler",
            llm_config={"model": "gpt-3.5-turbo", "temperature": 0.7},
            federation_id="fed123"
        )
        
        assert data.user_id == "test_user"
        assert data.name == "Test Agent"
        assert data.role == "participant"
    
    def test_invalid_role(self):
        """Test invalid role value."""
        with pytest.raises(ValueError):
            EnhancedAgentCreateData(
                user_id="test_user",
                name="Test Agent",
                role="invalid_role",
                llm_config={"model": "gpt-3.5-turbo"}
            )
    
    def test_llm_config_validation(self):
        """Test LLM config validation."""
        data = EnhancedAgentCreateData(
            user_id="test_user",
            name="Test Agent",
            role="participant",
            llm_config={"temperature": 0.5, "max_tokens": 150}
        )
        
        assert data.llm_config["temperature"] == 0.5
        assert data.llm_config["max_tokens"] == 150
        assert "model" in data.llm_config  # Default model added
    
    def test_invalid_temperature_in_config(self):
        """Test invalid temperature in LLM config."""
        with pytest.raises(Exception):
            EnhancedAgentCreateData(
                user_id="test_user",
                name="Test Agent",
                role="participant",
                llm_config={"temperature": 3.0}  # Out of range
            )


class TestEnhancedFederationCreateData:
    """Tests for EnhancedFederationCreateData model."""
    
    def test_valid_federation_data(self):
        """Test valid federation creation data."""
        data = EnhancedFederationCreateData(
            name="Test Federation",
            description="A test wrestling federation",
            tier=2,
            owner_user_id="owner123"
        )
        
        assert data.name == "Test Federation"
        assert data.tier == 2
        assert data.owner_user_id == "owner123"
    
    def test_tier_validation(self):
        """Test tier validation."""
        # Valid tiers
        for tier in [1, 2, 3, 4, 5]:
            data = EnhancedFederationCreateData(
                name="Test Fed",
                tier=tier,
                owner_user_id="owner123"
            )
            assert data.tier == tier
        
        # Invalid tiers
        with pytest.raises(ValueError):
            EnhancedFederationCreateData(
                name="Test Fed",
                tier=0,
                owner_user_id="owner123"
            )
        
        with pytest.raises(ValueError):
            EnhancedFederationCreateData(
                name="Test Fed",
                tier=6,
                owner_user_id="owner123"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
