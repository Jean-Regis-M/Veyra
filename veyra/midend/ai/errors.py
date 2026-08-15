"""AI Provider exception hierarchy."""

class AIProviderError(Exception):
    """Base exception for AI provider errors."""
    pass


class AIProviderNotConfiguredError(AIProviderError):
    """Raised only when an AI operation is requested without an API key."""

    code = "ai_provider_not_configured"

    def __init__(self):
        super().__init__(
            "AI provider is not configured. Configure it through: "
            "midend ai configure or POST /ai/config"
        )


class AIAuthenticationError(AIProviderError):
    """Raised when authentication with AI provider fails (e.g. invalid API key)."""
    pass


class AITimeoutError(AIProviderError):
    """Raised when AI generation request times out."""
    def __init__(self, timeout: float):
        self.timeout = timeout
        super().__init__(f"AI Provider request timed out after {timeout} seconds")
