"""LLM Module - RFC v1.9"""

from .ollama_client import OllamaClient, PromptTemplates
from .llama_cpp_manager import LlamaCppManager, RECOMMENDED_MODELS, download_model
from .llama_cpp_client import LlamaCppClient, LlamaCppError

__all__ = [
    'OllamaClient',
    'PromptTemplates',
    'LlamaCppManager',
    'RECOMMENDED_MODELS',
    'download_model',
    'LlamaCppClient',
    'LlamaCppError',
]
