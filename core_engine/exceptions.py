class CoreEngineError(Exception):
    """Base exception for all core engine errors."""
    pass

class LLMError(CoreEngineError):
    """Base exception for LLM related errors."""
    pass

class LLMNetworkError(LLMError):
    """Raised when an LLM network request fails."""
    pass

class LLMFormatError(LLMError):
    """Raised when an LLM response does not match the expected schema or format."""
    pass

class GameLogicError(CoreEngineError):
    """Raised when game rules or logic validations fail."""
    pass
