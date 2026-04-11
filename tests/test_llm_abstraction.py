"""
Tests for LLM abstraction layer.

Tests provider abstraction, fallback logic, circuit breaker, retry,
token budget, streaming, and standardized interfaces.
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from llm_abstraction import (
    LLMAbstraction,
    LLMMessage,
    LLMResponse,
    OpenAIProvider,
    OllamaProvider,
    AnthropicProvider,
    GeminiProvider,
    StreamChunk,
    CircuitBreaker,
    TokenBudget,
    estimate_cost,
    get_llm,
    reset_llm,
)


class TestLLMMessage:
    """Tests for LLMMessage model."""

    def test_create_llm_message(self):
        msg = LLMMessage(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_system_message(self):
        msg = LLMMessage(role="system", content="You are a helpful assistant")
        assert msg.role == "system"
        assert msg.content == "You are a helpful assistant"


class TestLLMResponse:
    """Tests for LLMResponse model."""

    def test_create_llm_response(self):
        response = LLMResponse(
            content="Hello, I'm an AI assistant",
            model="gpt-3.5-turbo",
            usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            finish_reason="stop",
            cost_usd=0.0025,
            latency_ms=150.0,
        )
        assert response.content == "Hello, I'm an AI assistant"
        assert response.model == "gpt-3.5-turbo"
        assert response.usage["total_tokens"] == 30
        assert response.finish_reason == "stop"
        assert response.cost_usd == 0.0025
        assert response.latency_ms == 150.0
        assert response.cached is False

    def test_minimal_response(self):
        response = LLMResponse(content="Test response", model="test-model")
        assert response.content == "Test response"
        assert response.usage is None
        assert response.finish_reason is None
        assert response.cost_usd == 0.0


class TestOpenAIProvider:
    """Tests for OpenAI provider."""

    def test_provider_initialization(self):
        provider = OpenAIProvider(model="gpt-3.5-turbo", api_key="test-key")
        assert provider.model == "gpt-3.5-turbo"
        assert provider.api_key == "test-key"

    def test_provider_validation(self):
        provider = OpenAIProvider(model="gpt-3.5-turbo", api_key="test-key")
        assert provider.validate_config() is True

    def test_generate_completion(self):
        mock_client = MagicMock()

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

        with patch("openai.OpenAI", return_value=mock_client):
            provider = OpenAIProvider(model="gpt-3.5-turbo", api_key="test-key")
            messages = [LLMMessage(role="user", content="Hello")]
            response = provider.generate(messages, temperature=0.7)

        assert response.content == "Test response"
        assert response.model == "gpt-3.5-turbo"
        assert response.usage["total_tokens"] == 30
        assert response.latency_ms > 0

    def test_circuit_breaker_blocks_when_open(self):
        from llm_abstraction.provider import LLMCircuitOpenError
        provider = OpenAIProvider(
            model="gpt-3.5-turbo", api_key="test-key", circuit_threshold=1
        )
        provider.circuit.record_failure()
        assert provider.circuit.is_open is True
        with pytest.raises(LLMCircuitOpenError, match="circuit breaker is open"):
            provider.generate([LLMMessage(role="user", content="Hi")])


class TestOllamaProvider:
    """Tests for Ollama provider."""

    def test_provider_initialization(self):
        provider = OllamaProvider(model="long-gemma")
        assert provider.model == "long-gemma"
        assert "127.0.0.1" in provider.api_base or "localhost" in provider.api_base

    @patch("httpx.get")
    def test_provider_validation(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        provider = OllamaProvider(model="long-gemma")
        assert provider.validate_config() is True

        mock_get.side_effect = Exception("Connection failed")
        assert provider.validate_config() is False

    @patch("httpx.post")
    def test_generate_completion(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": "Test response from Ollama",
            "model": "long-gemma",
        }
        mock_post.return_value = mock_response

        provider = OllamaProvider(model="long-gemma")
        messages = [LLMMessage(role="user", content="Hello")]
        response = provider.generate(messages, temperature=0.7)

        assert response.content == "Test response from Ollama"
        assert response.model == "long-gemma"
        assert response.finish_reason == "stop"
        assert response.latency_ms > 0


class TestAnthropicProvider:
    """Tests for Anthropic Claude provider."""

    def test_provider_initialization(self):
        provider = AnthropicProvider(model="claude-sonnet-4-20250514", api_key="test-key")
        assert provider.model == "claude-sonnet-4-20250514"
        assert provider.api_key == "test-key"

    def test_provider_validation(self):
        provider = AnthropicProvider(model="claude-sonnet-4-20250514", api_key="test-key")
        assert provider.validate_config() is True

        provider_no_key = AnthropicProvider(model="claude-sonnet-4-20250514")
        if not provider_no_key.api_key:
            assert provider_no_key.validate_config() is False

    def test_generate_completion(self):
        mock_client = MagicMock()

        mock_block = Mock()
        mock_block.text = "Hello from Claude"
        mock_response = Mock()
        mock_response.content = [mock_block]
        mock_response.model = "claude-sonnet-4-20250514"
        mock_response.usage.input_tokens = 15
        mock_response.usage.output_tokens = 25
        mock_response.stop_reason = "end_turn"

        mock_client.messages.create.return_value = mock_response

        with patch("anthropic.Anthropic", return_value=mock_client):
            provider = AnthropicProvider(model="claude-sonnet-4-20250514", api_key="test-key")
            messages = [
                LLMMessage(role="system", content="You are helpful"),
                LLMMessage(role="user", content="Hello"),
            ]
            response = provider.generate(messages, temperature=0.7)

        assert response.content == "Hello from Claude"
        assert response.model == "claude-sonnet-4-20250514"
        assert response.usage["prompt_tokens"] == 15
        assert response.usage["completion_tokens"] == 25
        assert response.latency_ms > 0


class TestGeminiProvider:
    """Tests for Google Gemini provider."""

    def test_provider_initialization(self):
        provider = GeminiProvider(model="gemini-2.0-flash", api_key="test-key")
        assert provider.model == "gemini-2.0-flash"
        assert provider.api_key == "test-key"

    def test_provider_validation(self):
        provider = GeminiProvider(model="gemini-2.0-flash", api_key="test-key")
        assert provider.validate_config() is True

        provider_no_key = GeminiProvider(model="gemini-2.0-flash")
        if not provider_no_key.api_key:
            assert provider_no_key.validate_config() is False

    def test_generate_completion(self):
        try:
            import google.genai  # noqa: F401
        except BaseException:
            pytest.skip("google-genai not usable in this environment")

        mock_client = MagicMock()

        mock_response = Mock()
        mock_response.text = "Hello from Gemini"
        mock_response.usage_metadata.prompt_token_count = 12
        mock_response.usage_metadata.candidates_token_count = 18

        mock_client.models.generate_content.return_value = mock_response

        with patch("google.genai.Client", return_value=mock_client):
            provider = GeminiProvider(model="gemini-2.0-flash", api_key="test-key")
            messages = [LLMMessage(role="user", content="Hello")]
            response = provider.generate(messages, temperature=0.7)

        assert response.content == "Hello from Gemini"
        assert response.model == "gemini-2.0-flash"
        assert response.usage["prompt_tokens"] == 12
        assert response.usage["completion_tokens"] == 18
        assert response.latency_ms > 0


class TestCircuitBreaker:
    """Tests for circuit breaker logic."""

    def test_starts_closed(self):
        cb = CircuitBreaker(threshold=3, cooldown_seconds=60.0)
        assert cb.is_open is False

    def test_opens_after_threshold_failures(self):
        cb = CircuitBreaker(threshold=2, cooldown_seconds=60.0)
        cb.record_failure()
        assert cb.is_open is False
        cb.record_failure()
        assert cb.is_open is True

    def test_success_resets_failures(self):
        cb = CircuitBreaker(threshold=2, cooldown_seconds=60.0)
        cb.record_failure()
        cb.record_success()
        cb.record_failure()
        # Only 1 failure since reset, should still be closed
        assert cb.is_open is False

    def test_cooldown_allows_probe(self):
        cb = CircuitBreaker(threshold=1, cooldown_seconds=0.01)
        cb.record_failure()
        assert cb.is_open is True
        time.sleep(0.02)
        # After cooldown, half-open allows probe
        assert cb.is_open is False


class TestTokenBudget:
    """Tests for token budget tracking."""

    def test_empty_budget(self):
        budget = TokenBudget()
        assert budget.total_tokens == 0
        assert budget.total_cost_usd == 0.0
        assert budget.request_count == 0

    def test_record_responses(self):
        budget = TokenBudget()
        r1 = LLMResponse(
            content="a",
            model="gpt-4o",
            usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            cost_usd=0.001,
        )
        r2 = LLMResponse(
            content="b",
            model="gpt-4o",
            usage={"prompt_tokens": 200, "completion_tokens": 100, "total_tokens": 300},
            cost_usd=0.002,
        )
        budget.record(r1)
        budget.record(r2)

        assert budget.request_count == 2
        assert budget.total_prompt_tokens == 300
        assert budget.total_completion_tokens == 150
        assert budget.total_tokens == 450
        assert budget.total_cost_usd == pytest.approx(0.003)

    def test_summary(self):
        budget = TokenBudget()
        summary = budget.summary()
        assert "request_count" in summary
        assert "total_tokens" in summary
        assert "total_cost_usd" in summary


class TestEstimateCost:
    """Tests for cost estimation."""

    def test_known_model(self):
        cost = estimate_cost("gpt-4", prompt_tokens=1000, completion_tokens=500)
        # gpt-4: 0.03/1K prompt + 0.06/1K completion
        assert cost == pytest.approx(0.03 + 0.03)

    def test_unknown_model(self):
        cost = estimate_cost("unknown-model", prompt_tokens=1000, completion_tokens=500)
        assert cost == 0.0

    def test_prefix_matching(self):
        cost = estimate_cost(
            "gpt-4o-2025-01-01", prompt_tokens=1000, completion_tokens=1000
        )
        # Should match gpt-4o prefix
        assert cost > 0.0


class TestLLMAbstraction:
    """Tests for LLM abstraction layer."""

    def test_abstraction_initialization(self):
        # Pass api_key so validate_config passes in test env
        llm = LLMAbstraction(
            provider="openai", model="gpt-3.5-turbo", api_key="test-key"
        )
        assert llm.provider_name == "openai"
        assert llm.model == "gpt-3.5-turbo"

    def test_auto_provider_selection(self):
        with patch.object(OllamaProvider, "validate_config", return_value=True):
            llm = LLMAbstraction(provider="auto", fallback_providers=["ollama"])
            assert llm.provider is not None

    def test_generate_with_prompt(self):
        with patch.object(OpenAIProvider, "generate") as mock_generate:
            mock_generate.return_value = LLMResponse(
                content="Test response", model="gpt-3.5-turbo"
            )
            llm = LLMAbstraction(
                provider="openai", model="gpt-3.5-turbo", api_key="test-key"
            )
            response = llm.generate(
                prompt="Hello, world!",
                system_message="You are helpful",
                temperature=0.7,
            )
            assert response.content == "Test response"
            assert mock_generate.called

    def test_generate_with_messages(self):
        with patch.object(OpenAIProvider, "generate") as mock_generate:
            mock_generate.return_value = LLMResponse(
                content="Response to conversation", model="gpt-3.5-turbo"
            )
            llm = LLMAbstraction(
                provider="openai", model="gpt-3.5-turbo", api_key="test-key"
            )
            messages = [
                LLMMessage(role="system", content="You are helpful"),
                LLMMessage(role="user", content="Hello"),
                LLMMessage(role="assistant", content="Hi there!"),
                LLMMessage(role="user", content="How are you?"),
            ]
            response = llm.generate_with_messages(messages, temperature=0.7)
            assert response.content == "Response to conversation"
            assert mock_generate.called

    def test_budget_tracking(self):
        with patch.object(OpenAIProvider, "generate") as mock_generate:
            mock_generate.return_value = LLMResponse(
                content="ok",
                model="gpt-3.5-turbo",
                usage={
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "total_tokens": 15,
                },
                cost_usd=0.001,
            )
            llm = LLMAbstraction(
                provider="openai", model="gpt-3.5-turbo", api_key="test-key"
            )
            llm.generate("Hello")
            llm.generate("World")

            summary = llm.get_budget_summary()
            assert summary["request_count"] == 2
            assert summary["total_tokens"] == 30


class TestGetLLMSingleton:
    """Tests for get_llm() singleton function."""

    def setup_method(self):
        reset_llm()

    def test_get_llm_returns_instance(self):
        with patch.object(OllamaProvider, "validate_config", return_value=True):
            llm = get_llm()
            assert isinstance(llm, LLMAbstraction)

    def test_get_llm_singleton_behavior(self):
        with patch.object(OllamaProvider, "validate_config", return_value=True):
            llm1 = get_llm()
            llm2 = get_llm()
            assert llm1 is llm2

    def test_reset_llm(self):
        with patch.object(OllamaProvider, "validate_config", return_value=True):
            llm1 = get_llm()
            reset_llm()
            llm2 = get_llm()
            assert llm1 is not llm2

    def teardown_method(self):
        reset_llm()


class TestProviderFallback:
    """Tests for provider fallback logic."""

    def test_fallback_to_second_provider(self):
        with patch.object(
            OllamaProvider, "validate_config", return_value=False
        ), patch.object(OpenAIProvider, "validate_config", return_value=True):
            llm = LLMAbstraction(
                provider="auto", fallback_providers=["ollama", "openai"]
            )
            assert isinstance(llm.provider, OpenAIProvider)

    def test_no_provider_available(self):
        with patch.object(
            OllamaProvider, "validate_config", return_value=False
        ), patch.object(OpenAIProvider, "validate_config", return_value=False):
            with pytest.raises(
                RuntimeError, match="No LLM provider could be initialized"
            ):
                LLMAbstraction(
                    provider="auto", fallback_providers=["ollama", "openai"]
                )

    def test_anthropic_in_fallback_chain(self):
        with patch.object(
            OllamaProvider, "validate_config", return_value=False
        ), patch.object(
            OpenAIProvider, "validate_config", return_value=False
        ), patch.object(
            AnthropicProvider, "validate_config", return_value=True
        ):
            llm = LLMAbstraction(
                provider="auto",
                fallback_providers=["ollama", "openai", "anthropic"],
            )
            assert isinstance(llm.provider, AnthropicProvider)


class TestErrorHandling:
    """Tests for error handling in LLM abstraction."""

    def test_invalid_provider_name(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            LLMAbstraction(provider="invalid_provider")

    def test_generation_error_handling(self):
        with patch.object(OpenAIProvider, "generate") as mock_generate:
            mock_generate.side_effect = Exception("API Error")
            llm = LLMAbstraction(
                provider="openai", model="gpt-3.5-turbo", api_key="test-key"
            )
            with pytest.raises(Exception, match="API Error"):
                llm.generate("Test prompt")


class TestStreamChunk:
    """Tests for StreamChunk model."""

    def test_create_chunk(self):
        chunk = StreamChunk(content="Hello", finish_reason=None, model="gpt-4")
        assert chunk.content == "Hello"
        assert chunk.finish_reason is None
        assert chunk.model == "gpt-4"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
