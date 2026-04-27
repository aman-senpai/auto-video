from typing import Any, Protocol, runtime_checkable

@runtime_checkable
class LLMProvider(Protocol):
    """Interface for LLM providers."""
    
    def generate_json(
        self, 
        prompt: str, 
        system_instruction: str | None = None,
        model: str | None = None
    ) -> dict[str, Any]:
        """Generate JSON response."""
        ...

    def generate_text(
        self, 
        prompt: str, 
        system_instruction: str | None = None,
        model: str | None = None
    ) -> str:
        """Generate plain text response."""
        ...
