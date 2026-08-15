"""Abstract base class for AI Providers."""

from abc import ABC, abstractmethod
from typing import AsyncGenerator, Optional
try:
    from .models import AIMessage, AIResponse, StreamChunk
except ImportError:  # pragma: no cover
    from ai.models import AIMessage, AIResponse, StreamChunk


class AIProvider(ABC):
    """Abstraction for AI model providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass

    @abstractmethod
    async def generate(
        self,
        messages: list[AIMessage],
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
    ) -> AIResponse:
        """Generate response from LLM."""
        pass

    @abstractmethod
    async def stream(
        self,
        messages: list[AIMessage],
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[StreamChunk, None]:
        """Stream response chunks from LLM."""
        pass
