class CoreEngineError(Exception):
    """Base exception for all core engine errors."""


class LLMError(CoreEngineError):
    """Base exception for LLM related errors."""


class LLMNetworkError(LLMError):
    """Raised when an LLM network request fails."""


class LLMFormatError(LLMError):
    """Raised when an LLM response does not match the expected schema or format."""


class GameLogicError(CoreEngineError):
    """Raised when game rules or logic validations fail."""
