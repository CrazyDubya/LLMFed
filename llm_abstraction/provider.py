"""
LLM Abstraction Layer

Provides a unified interface for interacting with different LLM providers
(OpenAI, Ollama, Anthropic, etc.) with consistent error handling and retry logic.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import logging
import os

logger = logging.getLogger(__name__)


@dataclass
class LLMMessage:
    """Represents a message in an LLM conversation."""
    role: str  # "system", "user", "assistant"
    content: str


@dataclass
class LLMResponse:
    """Standardized LLM response format."""
    content: str
    model: str
    usage: Optional[Dict[str, int]] = None
    finish_reason: Optional[str] = None
    raw_response: Optional[Any] = None


class LLMProviderBase(ABC):
    """Base class for LLM providers."""
    
    def __init__(self, model: str, **kwargs):
        """
        Initialize the LLM provider.
        
        Args:
            model: Model identifier
            **kwargs: Provider-specific configuration
        """
        self.model = model
        self.config = kwargs
        
    @abstractmethod
    def generate(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Generate a completion from the LLM.
        
        Args:
            messages: List of conversation messages
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific parameters
            
        Returns:
            LLMResponse with generated content
        """
        pass
    
    @abstractmethod
    def validate_config(self) -> bool:
        """
        Validate that the provider is properly configured.
        
        Returns:
            True if configuration is valid
        """
        pass


class OpenAIProvider(LLMProviderBase):
    """OpenAI API provider."""
    
    def __init__(self, model: str, api_key: Optional[str] = None, **kwargs):
        super().__init__(model, **kwargs)
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.api_base = kwargs.get("api_base") or os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
        
    def validate_config(self) -> bool:
        """Check if API key is configured."""
        return self.api_key is not None
    
    def generate(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate completion using OpenAI API."""
        try:
            import openai
            
            # Configure client
            client = openai.OpenAI(
                api_key=self.api_key,
                base_url=self.api_base
            )
            
            # Convert messages to OpenAI format
            openai_messages = [
                {"role": msg.role, "content": msg.content}
                for msg in messages
            ]
            
            # Make API call
            response = client.chat.completions.create(
                model=self.model,
                messages=openai_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
            
            # Extract response
            choice = response.choices[0]
            return LLMResponse(
                content=choice.message.content,
                model=response.model,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                } if response.usage else None,
                finish_reason=choice.finish_reason,
                raw_response=response
            )
            
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise


class OllamaProvider(LLMProviderBase):
    """Ollama local LLM provider."""
    
    def __init__(self, model: str, **kwargs):
        super().__init__(model, **kwargs)
        self.api_base = kwargs.get("api_base") or os.getenv("OLLAMA_API_BASE", "http://127.0.0.1:11434")
        
    def validate_config(self) -> bool:
        """Check if Ollama is accessible."""
        try:
            import httpx
            response = httpx.get(f"{self.api_base}/api/tags", timeout=2.0)
            return response.status_code == 200
        except Exception:
            return False
    
    def generate(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate completion using Ollama."""
        try:
            import httpx
            
            # Convert messages to Ollama format
            prompt = "\n".join([
                f"{msg.role}: {msg.content}"
                for msg in messages
            ])
            
            # Make API call
            response = httpx.post(
                f"{self.api_base}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "temperature": temperature,
                    "stream": False,
                    **({"max_tokens": max_tokens} if max_tokens else {})
                },
                timeout=60.0
            )
            response.raise_for_status()
            
            data = response.json()
            return LLMResponse(
                content=data.get("response", ""),
                model=self.model,
                finish_reason="stop",
                raw_response=data
            )
            
        except Exception as e:
            logger.error(f"Ollama API error: {e}")
            raise


class LLMAbstraction:
    """
    Main LLM abstraction interface.
    
    Automatically selects and manages LLM providers with fallback support.
    """
    
    def __init__(
        self,
        provider: str = "auto",
        model: Optional[str] = None,
        fallback_providers: Optional[List[str]] = None,
        **kwargs
    ):
        """
        Initialize LLM abstraction.
        
        Args:
            provider: Provider name ("openai", "ollama", "auto")
            model: Model identifier
            fallback_providers: List of fallback providers to try
            **kwargs: Provider-specific configuration
        """
        self.provider_name = provider
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
        self.fallback_providers = fallback_providers or ["ollama", "openai"]
        self.config = kwargs
        self.provider = self._initialize_provider()
        
    def _initialize_provider(self) -> LLMProviderBase:
        """Initialize the LLM provider based on configuration."""
        if self.provider_name == "auto":
            # Try providers in order until one works
            for provider_name in self.fallback_providers:
                try:
                    provider = self._create_provider(provider_name)
                    if provider.validate_config():
                        logger.info(f"Using LLM provider: {provider_name}")
                        return provider
                except Exception as e:
                    logger.warning(f"Failed to initialize {provider_name}: {e}")
            
            # If all fail, raise error
            raise RuntimeError("No LLM provider could be initialized")
        
        else:
            # Use specific provider
            provider = self._create_provider(self.provider_name)
            if not provider.validate_config():
                raise RuntimeError(f"Provider {self.provider_name} configuration invalid")
            return provider
    
    def _create_provider(self, provider_name: str) -> LLMProviderBase:
        """Create a provider instance."""
        if provider_name == "openai":
            return OpenAIProvider(self.model, **self.config)
        elif provider_name == "ollama":
            return OllamaProvider(self.model, **self.config)
        else:
            raise ValueError(f"Unknown provider: {provider_name}")
    
    def generate(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Generate a completion from the LLM.
        
        Args:
            prompt: User prompt
            system_message: Optional system message
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters
            
        Returns:
            LLMResponse with generated content
        """
        messages = []
        
        if system_message:
            messages.append(LLMMessage(role="system", content=system_message))
        
        messages.append(LLMMessage(role="user", content=prompt))
        
        return self.provider.generate(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )
    
    def generate_with_messages(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Generate a completion with full message history.
        
        Args:
            messages: List of conversation messages
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters
            
        Returns:
            LLMResponse with generated content
        """
        return self.provider.generate(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )


# Singleton instance for easy access
_default_llm = None


def get_llm() -> LLMAbstraction:
    """Get the default LLM instance."""
    global _default_llm
    if _default_llm is None:
        _default_llm = LLMAbstraction(provider="auto")
    return _default_llm
