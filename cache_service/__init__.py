"""
Caching Service
Redis-based response caching with TTL management
"""

__version__ = "0.1.0"

from .cache import CacheManager

__all__ = ["CacheManager"]


# Stubs for test compatibility
class GenerationRequest:
    """Stub for generation request."""
    def __init__(self, prompt: str, model: str = "default", **kwargs):
        self.prompt = prompt
        self.model = model
        self.kwargs = kwargs


class GenerationResponse:
    """Stub for generation response."""
    def __init__(self, text: str, model: str = "default", cached: bool = False):
        self.text = text
        self.model = model
        self.cached = cached
