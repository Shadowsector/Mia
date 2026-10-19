"""Ollama Client with Caching and Retry Logic - RFC v1.9"""

from typing import Optional, Dict, Any, List
from datetime import datetime
import hashlib
import json
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import ollama
from pathlib import Path


class OllamaClient:
    """Ollama клиент с кэшированием, retry логикой и форматом JSON"""
    
    def __init__(self, base_url: str = "http://localhost:11434"):
        """Инициализация Ollama клиента"""
        self.base_url = base_url
        self.client = ollama.Client(host=base_url)
        
        # Семафор для ограничения VRAM (asyncio.Semaphore(1))
        self.semaphore = asyncio.Semaphore(1)
        
        # Кэш результатов по SHA-256 хэшу
        self.cache_dir = Path("./data/llm_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Модели по RFC v1.9
        self.models = {
            "classification": "mistral:7b-instruct-v0.3",
            "analysis": "qwen2.5:14b-instruct-q4_K_M",
            "embedding": "nomic-embed-text"
        }
        
        # Бюджет токенов и времени
        self.max_tokens_per_request = 4000
        self.max_time_per_request = 30  # seconds
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((ConnectionError, TimeoutError))
    )
    async def generate(
        self,
        prompt: str,
        model: str = "mistral:7b-instruct-v0.3",
        format_type: Optional[str] = None,  # "json" для Pydantic валидации
        temperature: float = 0.7,
        num_predict: int = 1000,
        cache_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Генерация текста с retry логикой и кэшированием"""
        
        # Проверка кэша
        if cache_key:
            cached_result = self._get_from_cache(cache_key)
            if cached_result:
                return cached_result
        
        # Ограничение семафором (монопольный доступ)
        async with self.semaphore:
            try:
                result = self.client.generate(
                    model=model,
                    prompt=prompt,
                    format=format_type,
                    options={
                        "temperature": temperature,
                        "num_predict": min(num_predict, self.max_tokens_per_request),
                        "num_ctx": 4096
                    }
                )
                
                # Сохранение в кэш
                if cache_key:
                    self._save_to_cache(cache_key, result)
                
                return result
                
            except Exception as e:
                print(f"Ollama generation error: {e}")
                raise
    
    async def generate_json(
        self,
        prompt: str,
        model: str = "mistral:7b-instruct-v0.3",
        schema_hint: Optional[str] = None
    ) -> Dict[str, Any]:
        """Генерация JSON с форматом для Pydantic валидации"""
        
        # Добавляем подсказку схемы в промпт
        if schema_hint:
            prompt = f"{prompt}\n\nJSON Schema (strictly follow):\n{schema_hint}"
        
        result = await self.generate(
            prompt=prompt,
            model=model,
            format_type="json",
            temperature=0.3  # Ниже температура для более детерминированного JSON
        )
        
        try:
            return json.loads(result['response'])
        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {e}")
            return {"error": "Failed to parse JSON", "raw_response": result['response']}
    
    def get_embedding(self, text: str, model: str = "nomic-embed-text") -> List[float]:
        """Получить embedding для текста"""
        try:
            result = self.client.embed(model=model, input=text)
            return result['embeddings'][0]
        except Exception as e:
            print(f"Embedding error: {e}")
            return []
    
    def _generate_cache_key(
        self,
        prompt: str,
        model: str,
        format_type: Optional[str]
    ) -> str:
        """Генерация SHA-256 хэша для кэша"""
        cache_string = f"{prompt}_{model}_{format_type}"
        return hashlib.sha256(cache_string.encode()).hexdigest()
    
    def _get_from_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Получить результат из кэша"""
        cache_file = self.cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Cache read error: {e}")
        return None
    
    def _save_to_cache(self, cache_key: str, result: Dict[str, Any]):
        """Сохранить результат в кэш"""
        cache_file = self.cache_dir / f"{cache_key}.json"
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Cache write error: {e}")
    
    def clear_cache(self):
        """Очистить кэш"""
        for cache_file in self.cache_dir.glob("*.json"):
            cache_file.unlink()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Получить статистику кэша"""
        cache_files = list(self.cache_dir.glob("*.json"))
        total_size = sum(f.stat().st_size for f in cache_files)
        return {
            "cache_dir": str(self.cache_dir),
            "cached_requests": len(cache_files),
            "total_size_bytes": total_size,
            "total_size_mb": total_size / (1024 * 1024)
        }


class PromptTemplates:
    """Базовые промпты для разных задач"""
    
    @staticmethod
    def intent_classifier_prompt(message: str, context: str) -> str:
        """Промпт для классификации намерений (Intent Classifier)"""
        return f"""
You are a construction domain intent classifier. Classify the following message into domain intents.

Message: "{message}"
Context: {context}

Available intents:
- MOVE_MATERIAL: Movement of materials between locations
- SCHEDULE_CHANGE: Changes to project schedule or deadlines
- APPROVAL_REQUEST: Request for approval or sign-off
- DELIVERY_CONFIRMATION: Confirmation of material delivery
- TECHNICAL_QUESTION: Question about technical specifications
- OTHER: Any other intent

Return JSON:
{{
    "domain_intent": "MOVE_MATERIAL",
    "material_concept": "well_rings_or_chambers",
    "source_location_raw": "Location",
    "target_location_raw": "Location",
    "confidence": 0.92
}}
"""
    
    @staticmethod
    def contract_extraction_prompt(text: str) -> str:
        """Промпт для извлечения данных из договоров"""
        return f"""
Extract structured information from the following contract text.

Contract text:
{text}

Return JSON:
{{
    "customer": "Company name",
    "contract_date": "YYYY-MM-DD",
    "contract_amount": 1000000.0,
    "contract_number": "Number",
    "entities": ["Company A", "Company B"],
    "confidence": 0.95
}}
"""
    
    @staticmethod
    def temporal_context_prompt(current_time: datetime) -> str:
        """Промпт для Absolute Time Injection"""
        return f"""
[ SYSTEM CONTEXT ]
Current Absolute Time: {current_time.strftime('%Y-%m-%d %H:%M:%S')}
Current Day of Week: {current_time.strftime('%A')}
Relative Translation Map:
- "Сегодня" = {current_time.strftime('%Y-%m-%d')}
- "Завтра" = {(current_time.replace(day=current_time.day + 1)).strftime('%Y-%m-%d')}
- "Вчера" = {(current_time.replace(day=current_time.day - 1)).strftime('%Y-%m-%d')}
- "Позавчера" = {(current_time.replace(day=current_time.day - 2)).strftime('%Y-%m-%d')}
[ END SYSTEM CONTEXT ]

Process the user's request with awareness of the current time and relative date mappings.
"""
    
    @staticmethod
    def few_shot_rag_prompt(
        spec_text: str,
        relevant_lessons: List[str]
    ) -> str:
        """Промпт для Few-Shot RAG с уроками эксперта"""
        lessons_text = "\n\n".join(relevant_lessons)
        
        return f"""
You are analyzing a technical specification for construction compliance.

Expert Lessons (past violations and corrections):
{lessons_text}

Current Specification:
{spec_text}

Identify any violations or missing requirements based on the expert lessons.

Return JSON:
{{
    "violations": [
        {{
            "type": "missing_cable_marking",
            "description": "Cable lacks HF marking required by Rostelecom",
            "severity": "CRITICAL",
            "confidence": 0.92
        }}
    ],
    "compliance_score": 0.75
}}
"""
