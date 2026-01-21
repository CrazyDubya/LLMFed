"""
Tests for LLM abstraction layer.

Tests provider abstraction, fallback logic, and standardized interfaces.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from llm_abstraction import (
    LLMAbstraction,
    LLMMessage,
    LLMResponse,
    OpenAIProvider,
    OllamaProvider,
    get_llm
)


class TestLLMMessage:
    """Tests for LLMMessage model."""
    
    def test_create_llm_message(self):
        """Test creating LLM messages."""
        msg = LLMMessage(role="user", content="Hello")
        
        assert msg.role == "user"
        assert msg.content == "Hello"
    
    def test_system_message(self):
        """Test system message."""
        msg = LLMMessage(role="system", content="You are a helpful assistant")
        
        assert msg.role == "system"
        assert msg.content == "You are a helpful assistant"


class TestLLMResponse:
    """Tests for LLMResponse model."""
    
    def test_create_llm_response(self):
        """Test creating LLM response."""
        response = LLMResponse(
            content="Hello, I'm an AI assistant",
            model="gpt-3.5-turbo",
            usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            finish_reason="stop"
        )
        
        assert response.content == "Hello, I'm an AI assistant"
        assert response.model == "gpt-3.5-turbo"
        assert response.usage["total_tokens"] == 30
        assert response.finish_reason == "stop"
    
    def test_minimal_response(self):
        """Test minimal response without optional fields."""
        response = LLMResponse(
            content="Test response",
            model="test-model"
        )
        
        assert response.content == "Test response"
        assert response.usage is None
        assert response.finish_reason is None


class TestOpenAIProvider:
    """Tests for OpenAI provider."""
    
    def test_provider_initialization(self):
        """Test OpenAI provider initialization."""
        provider = OpenAIProvider(model="gpt-3.5-turbo", api_key="test-key")
        
        assert provider.model == "gpt-3.5-turbo"
        assert provider.api_key == "test-key"
    
    def test_provider_validation(self):
        """Test provider configuration validation."""
        provider = OpenAIProvider(model="gpt-3.5-turbo", api_key="test-key")
        assert provider.validate_config() is True
        
        provider_no_key = OpenAIProvider(model="gpt-3.5-turbo")
        # Should still validate if no API key (might use env var)
        # This depends on whether OPENAI_API_KEY env var is set
    
    @patch('openai.OpenAI')
    def test_generate_completion(self, mock_openai_class):
        """Test generating completion with OpenAI."""
        # Mock the OpenAI client
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        # Mock the completion response
        mock_choice = Mock()
        mock_choice.message.content = "Test response"
        mock_choice.finish_reason = "stop"
        
        mock_response = Mock()
        mock_response.choices = [mock_choice]
        mock_response.model = "gpt-3.5-turbo"
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 20
        mock_response.usage.total_tokens = 30
        
        mock_client.chat.completions.create.return_value = mock_response
        
        # Test generation
        provider = OpenAIProvider(model="gpt-3.5-turbo", api_key="test-key")
        messages = [LLMMessage(role="user", content="Hello")]
        
        response = provider.generate(messages, temperature=0.7)
        
        assert response.content == "Test response"
        assert response.model == "gpt-3.5-turbo"
        assert response.usage["total_tokens"] == 30


class TestOllamaProvider:
    """Tests for Ollama provider."""
    
    def test_provider_initialization(self):
        """Test Ollama provider initialization."""
        provider = OllamaProvider(model="long-gemma")
        
        assert provider.model == "long-gemma"
        assert "127.0.0.1" in provider.api_base or "localhost" in provider.api_base
    
    @patch('httpx.get')
    def test_provider_validation(self, mock_get):
        """Test Ollama provider validation."""
        # Mock successful connection
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        provider = OllamaProvider(model="long-gemma")
        assert provider.validate_config() is True
        
        # Mock failed connection
        mock_get.side_effect = Exception("Connection failed")
        assert provider.validate_config() is False
    
    @patch('httpx.post')
    def test_generate_completion(self, mock_post):
        """Test generating completion with Ollama."""
        # Mock the Ollama response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": "Test response from Ollama",
            "model": "long-gemma"
        }
        mock_post.return_value = mock_response
        
        # Test generation
        provider = OllamaProvider(model="long-gemma")
        messages = [LLMMessage(role="user", content="Hello")]
        
        response = provider.generate(messages, temperature=0.7)
        
        assert response.content == "Test response from Ollama"
        assert response.model == "long-gemma"
        assert response.finish_reason == "stop"


class TestLLMAbstraction:
    """Tests for LLM abstraction layer."""
    
    def test_abstraction_initialization(self):
        """Test LLM abstraction initialization."""
        llm = LLMAbstraction(provider="openai", model="gpt-3.5-turbo")
        
        assert llm.provider_name == "openai"
        assert llm.model == "gpt-3.5-turbo"
    
    def test_auto_provider_selection(self):
        """Test automatic provider selection."""
        # This test depends on available providers
        # In a real environment, it would try providers in order
        with patch.object(OllamaProvider, 'validate_config', return_value=True):
            llm = LLMAbstraction(provider="auto", fallback_providers=["ollama"])
            assert llm.provider is not None
    
    def test_generate_with_prompt(self):
        """Test simple prompt generation."""
        with patch('llm_abstraction.provider.OpenAIProvider.generate') as mock_generate:
            mock_generate.return_value = LLMResponse(
                content="Test response",
                model="gpt-3.5-turbo"
            )
            
            llm = LLMAbstraction(provider="openai", model="gpt-3.5-turbo")
            response = llm.generate(
                prompt="Hello, world!",
                system_message="You are helpful",
                temperature=0.7
            )
            
            assert response.content == "Test response"
            assert mock_generate.called
    
    def test_generate_with_messages(self):
        """Test generation with message history."""
        with patch('llm_abstraction.provider.OpenAIProvider.generate') as mock_generate:
            mock_generate.return_value = LLMResponse(
                content="Response to conversation",
                model="gpt-3.5-turbo"
            )
            
            llm = LLMAbstraction(provider="openai", model="gpt-3.5-turbo")
            messages = [
                LLMMessage(role="system", content="You are helpful"),
                LLMMessage(role="user", content="Hello"),
                LLMMessage(role="assistant", content="Hi there!"),
                LLMMessage(role="user", content="How are you?")
            ]
            
            response = llm.generate_with_messages(messages, temperature=0.7)
            
            assert response.content == "Response to conversation"
            assert mock_generate.called


class TestGetLLMSingleton:
    """Tests for get_llm() singleton function."""
    
    def test_get_llm_returns_instance(self):
        """Test that get_llm returns an LLMAbstraction instance."""
        llm = get_llm()
        
        assert isinstance(llm, LLMAbstraction)
    
    def test_get_llm_singleton_behavior(self):
        """Test that get_llm returns the same instance."""
        llm1 = get_llm()
        llm2 = get_llm()
        
        assert llm1 is llm2


class TestProviderFallback:
    """Tests for provider fallback logic."""
    
    def test_fallback_to_second_provider(self):
        """Test fallback when first provider fails."""
        with patch.object(OllamaProvider, 'validate_config', return_value=False), \
             patch.object(OpenAIProvider, 'validate_config', return_value=True):
            
            llm = LLMAbstraction(
                provider="auto",
                fallback_providers=["ollama", "openai"]
            )
            
            # Should have fallen back to OpenAI
            assert isinstance(llm.provider, OpenAIProvider)
    
    def test_no_provider_available(self):
        """Test when no provider is available."""
        with patch.object(OllamaProvider, 'validate_config', return_value=False), \
             patch.object(OpenAIProvider, 'validate_config', return_value=False):
            
            with pytest.raises(RuntimeError, match="No LLM provider could be initialized"):
                LLMAbstraction(
                    provider="auto",
                    fallback_providers=["ollama", "openai"]
                )


class TestErrorHandling:
    """Tests for error handling in LLM abstraction."""
    
    def test_invalid_provider_name(self):
        """Test with invalid provider name."""
        with pytest.raises(ValueError, match="Unknown provider"):
            LLMAbstraction(provider="invalid_provider")
    
    @patch('llm_abstraction.provider.OpenAIProvider.generate')
    def test_generation_error_handling(self, mock_generate):
        """Test error handling during generation."""
        mock_generate.side_effect = Exception("API Error")
        
        llm = LLMAbstraction(provider="openai", model="gpt-3.5-turbo")
        
        with pytest.raises(Exception, match="API Error"):
            llm.generate("Test prompt")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
