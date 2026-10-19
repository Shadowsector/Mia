"""LLM Module - RFC v1.9"""

from .ollama_client import OllamaClient, PromptTemplates
from .llama_cpp_manager import LlamaCppManager, RECOMMENDED_MODELS, download_model

__all__ = ['OllamaClient', 'PromptTemplates', 'LlamaCppManager', 'RECOMMENDED_MODELS', 'download_model']
