"""ChromaDB Manager for RAG System - RFC v1.9"""

from typing import Optional, List, Dict, Any
from pathlib import Path
import json
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions


def get_default_embedding_function():
    """Embedding-функция по умолчанию.

    `EMBED_BACKEND=llama` (по умолчанию) — llama.cpp `/v1/embeddings`
    (отдельный сервер, bge-m3). `EMBED_BACKEND=ollama` — легаси Ollama.
    """
    from config import settings

    backend = getattr(settings, "EMBED_BACKEND", "llama").lower()
    if backend == "ollama":
        return embedding_functions.OllamaEmbeddingFunction(
            model_name=getattr(settings, "EMBED_MODEL", "bge-m3"),
            url=getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434"),
        )

    from app.modules.rag.llama_embeddings import LlamaCppEmbeddingFunction

    return LlamaCppEmbeddingFunction()


class ChromaManager:
    """Менеджер ChromaDB для RAG системы (PersistentClient, коллекция, метаданные чанков)"""
    
    def __init__(self, persist_directory: str = "./chroma_db", embedding_function=None):
        """Инициализация PersistentClient"""
        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        
        # Инициализация PersistentClient
        self.client = chromadb.PersistentClient(
            path=str(self.persist_directory),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # Коллекция чанков
        self.collection_name = "object_diary_chunks"
        self.collection = None
        
        # Embedding функция (llama.cpp по умолчанию, см. get_default_embedding_function)
        self.embedding_function = embedding_function or get_default_embedding_function()
        
        self._initialize_collection()
    
    def _initialize_collection(self):
        """Инициализация единой коллекции object_diary_chunks"""
        try:
            self.collection = self.client.get_collection(
                name=self.collection_name,
                embedding_function=self.embedding_function
            )
        except:
            # Если коллекция не существует, создаем новую
            self.collection = self.client.create_collection(
                name=self.collection_name,
                embedding_function=self.embedding_function,
                metadata={"description": "Unified collection for object diary chunks"}
            )
    
    def add_chunk(
        self,
        chunk_text: str,
        object_id: str,
        doc_id: str,
        doc_category: str,
        is_current: bool = True,
        doc_date_timestamp: Optional[str] = None,
        chunk_index: int = 0,
        legal_entities: Optional[List[str]] = None,
        additional_metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Добавить чанк в коллекцию с метаданными"""
        
        # Обязательные метаданные по RFC v1.9
        metadata = {
            "object_id": object_id,
            "doc_id": doc_id,
            "doc_category": doc_category,
            "is_current": 1 if is_current else 0,
            "chunk_index": chunk_index
        }
        
        # Опциональные метаданные
        if doc_date_timestamp:
            metadata["doc_date_timestamp"] = doc_date_timestamp
        
        if legal_entities:
            metadata["legal_entities"] = json.dumps(legal_entities, ensure_ascii=False)
        
        if additional_metadata:
            metadata.update(additional_metadata)
        
        # Генерация уникального ID чанка
        chunk_id = f"{doc_id}_chunk_{chunk_index}"
        
        self.collection.add(
            documents=[chunk_text],
            metadatas=[metadata],
            ids=[chunk_id]
        )
        
        return chunk_id
    
    def search_within_object(
        self,
        query_text: str,
        object_id: str,
        n_results: int = 10,
        only_current: bool = True
    ) -> List[Dict[str, Any]]:
        """Поиск внутри объекта (жесткая фильтрация по object_id и is_current)"""
        
        conditions = [{"object_id": object_id}]
        
        if only_current:
            conditions.append({"is_current": 1})
        
        where_filters = conditions[0] if len(conditions) == 1 else {"$and": conditions}
        
        results = self.collection.query(
            query_texts=[query_text],
            where=where_filters,
            n_results=n_results
        )
        
        return self._format_results(results)
    
    def search_between_objects(
        self,
        query_text: str,
        filters: Optional[Dict[str, Any]] = None,
        n_results: int = 20
    ) -> List[Dict[str, Any]]:
        """Поиск между объектами (с фильтрами по метаданным)"""
        
        where_filters = filters if filters else None
        
        results = self.collection.query(
            query_texts=[query_text],
            where=where_filters,
            n_results=n_results
        )
        
        return self._format_results(results)
    
    def search_with_rrf(
        self,
        query_text: str,
        object_id: Optional[str] = None,
        category_weights: Optional[Dict[str, float]] = None,
        n_results: int = 20
    ) -> List[Dict[str, Any]]:
        """Поиск с Reciprocal Rank Fusion (RRF) и весами по типам документов"""
        
        # Веса по умолчанию по RFC v1.9
        default_weights = {
            "CONTRACT": 1.0,
            "ADDENDUM": 1.0,
            "FINANCIAL": 0.8,
            "PROPOSAL": 0.5,
            "REFERENCE": 0.3
        }
        
        if category_weights:
            default_weights.update(category_weights)
        
        where_filters = None
        if object_id:
            where_filters = {"object_id": object_id}
        
        results = self.collection.query(
            query_texts=[query_text],
            where=where_filters,
            n_results=n_results * 2  # Берем больше для RRF
        )
        
        # Применяем RRF
        ranked_results = self._apply_rrf(results, default_weights)
        
        return ranked_results[:n_results]
    
    def update_chunk_metadata(
        self,
        chunk_id: str,
        metadata_updates: Dict[str, Any]
    ) -> bool:
        """Обновить метаданные чанка"""
        try:
            existing = self.collection.get(ids=[chunk_id])
            if not existing.get('ids'):
                return False

            self.collection.update(
                ids=[chunk_id],
                metadatas=[metadata_updates]
            )
            return True
        except Exception as e:
            print(f"Error updating chunk metadata: {e}")
            return False
    
    def delete_chunks_by_doc(self, doc_id: str) -> int:
        """Удалить все чанки документа"""
        # Сначала получаем ID чанков
        results = self.collection.get(
            where={"doc_id": doc_id},
            limit=1000
        )
        
        if results['ids']:
            self.collection.delete(ids=results['ids'])
            return len(results['ids'])
        
        return 0
    
    def delete_chunks_by_object(self, object_id: str) -> int:
        """Удалить все чанки объекта"""
        results = self.collection.get(
            where={"object_id": object_id},
            limit=10000
        )
        
        if results['ids']:
            self.collection.delete(ids=results['ids'])
            return len(results['ids'])
        
        return 0
    
    def _format_results(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Форматирование результатов ChromaDB"""
        formatted = []
        
        if not results['ids']:
            return formatted
        
        for i in range(len(results['ids'][0])):
            formatted.append({
                'chunk_id': results['ids'][0][i],
                'text': results['documents'][0][i],
                'metadata': results['metadatas'][0][i],
                'distance': results['distances'][0][i] if 'distances' in results else None
            })
        
        return formatted
    
    def _apply_rrf(
        self,
        results: Dict[str, Any],
        weights: Dict[str, float]
    ) -> List[Dict[str, Any]]:
        """Применение Reciprocal Rank Fusion"""
        
        formatted = self._format_results(results)
        
        # Сортируем по RRF скору
        rrf_scores = {}
        k = 60  # Константа для RRF
        
        for i, result in enumerate(formatted):
            doc_category = result['metadata'].get('doc_category', 'OTHER')
            weight = weights.get(doc_category, 0.3)
            
            # RRF формула: 1 / (k + rank)
            rrf_score = weight / (k + i + 1)
            rrf_scores[result['chunk_id']] = rrf_score
        
        # Сортируем по RRF скору
        formatted.sort(key=lambda x: rrf_scores.get(x['chunk_id'], 0), reverse=True)
        
        return formatted
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """Получить статистику коллекции"""
        count = self.collection.count()
        return {
            "collection_name": self.collection_name,
            "total_chunks": count,
            "persist_directory": str(self.persist_directory)
        }
