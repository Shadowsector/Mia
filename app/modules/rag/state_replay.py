"""Chronological State Replay Engine - Replay project ledger state with versioning.

This module implements versioning for document chunks in ChromaDB,
ensuring latest revisions block obsolete text chunks during RAG searches.
"""

import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path

try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
logger = logging.getLogger(__name__)


def _scalar_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Flatten metadata to ChromaDB-compatible scalar values (dicts/lists → JSON)."""
    flat: Dict[str, Any] = {}
    for key, value in metadata.items():
        if value is None or isinstance(value, (str, int, float, bool)):
            flat[key] = value
        else:
            flat[key] = json.dumps(value, ensure_ascii=False, default=str)
    return flat
    logger.warning("chromadb not available, State Replay Engine disabled")

logger = logging.getLogger(__name__)


class StateReplayEngine:
    """
    Replay project ledger state up to current date.
    
    Ensures latest document revisions block obsolete chunks
    during vector/RAG searches.
    """
    
    def __init__(self, persist_directory: str = "./chroma_db"):
        """
        Initialize State Replay Engine.
        
        Args:
            persist_directory: ChromaDB persist directory
        """
        if not CHROMADB_AVAILABLE:
            logger.error("chromadb not available")
            return
        
        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        
        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=str(self.persist_directory),
            settings=Settings(anonymized_telemetry=False, allow_reset=True)
        )
        
        # Versioning collection
        self.collection_name = "document_versions"
        self.collection = None
        self._initialize_collection()
        
        logger.info("State Replay Engine initialized")
    
    def _initialize_collection(self):
        """Initialize document versions collection."""
        try:
            self.collection = self.client.get_collection(name=self.collection_name)
        except:
            self.collection = self.client.create_collection(
                name=self.collection_name,
                metadata={"description": "Document version tracking for state replay"}
            )
    
    def register_document_version(
        self,
        document_id: str,
        document_name: str,
        revision_index: int,
        object_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Register a new document version.
        
        Args:
            document_id: Document identifier
            document_name: Document name
            revision_index: Revision number (0, 1, 2, ...)
            object_id: Associated object ID
            metadata: Additional metadata
            
        Returns:
            Version ID
        """
        version_id = f"{document_id}_rev_{revision_index}"
        
        # Mark previous versions as obsolete
        self._mark_previous_versions_obsolete(document_id, revision_index)
        
        # Add new version
        # ChromaDB metadata values must be scalars — serialize nested dicts to JSON
        version_data = {
            'version_id': version_id,
            'document_id': document_id,
            'document_name': document_name,
            'revision_index': revision_index,
            'object_id': object_id or '',
            'status': 'actual',
            'created_at': datetime.now().isoformat(),
            'metadata': json.dumps(metadata or {}, ensure_ascii=False, default=str)
        }
        
        try:
            self.collection.add(
                ids=[version_id],
                documents=[f"Document version: {document_name} rev {revision_index}"],
                metadatas=[version_data]
            )
            
            logger.info(f"Registered document version {version_id}")
            return version_id
            
        except Exception as e:
            logger.error(f"Error registering document version: {e}")
            return ""
    
    def _mark_previous_versions_obsolete(self, document_id: str, current_revision: int):
        """Mark previous document versions as obsolete."""
        try:
            # Get all versions of this document
            results = self.collection.get(
                where={'document_id': document_id}
            )
            
            if results and results['ids']:
                for i, version_id in enumerate(results['ids']):
                    metadata = results['metadatas'][i]
                    revision = metadata.get('revision_index', 0)
                    
                    if revision < current_revision:
                        # Update metadata to mark as obsolete
                        self.collection.update(
                            ids=[version_id],
                            metadatas=[{**metadata, 'status': 'obsolete'}]
                        )
                        logger.debug(f"Marked version {version_id} as obsolete")
            
        except Exception as e:
            logger.error(f"Error marking previous versions obsolete: {e}")
    
    def get_actual_version(self, document_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the actual (latest) version of a document.
        
        Args:
            document_id: Document ID
            
        Returns:
            Version metadata or None
        """
        try:
            results = self.collection.get(
                where={'$and': [
                    {'document_id': document_id},
                    {'status': 'actual'},
                ]}
            )
            
            if results and results['ids']:
                # Return the version with highest revision_index
                versions = []
                for i, version_id in enumerate(results['ids']):
                    metadata = results['metadatas'][i]
                    versions.append(metadata)
                
                # Sort by revision_index (descending)
                versions.sort(key=lambda x: x.get('revision_index', 0), reverse=True)
                
                return versions[0] if versions else None
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting actual version: {e}")
            return None
    
    def replay_state(self, object_id: str, target_date: datetime) -> Dict[str, Any]:
        """
        Replay project ledger state up to target date.
        
        Args:
            object_id: Object ID
            target_date: Target date for replay
            
        Returns:
            State at target date
        """
        try:
            # Get all document versions for this object
            results = self.collection.get(
                where={'object_id': object_id}
            )
            
            if not results or not results['ids']:
                return {
                    'object_id': object_id,
                    'target_date': target_date.isoformat(),
                    'state': {},
                    'message': 'No versions found'
                }
            
            # Filter versions created before or on target date
            target_date_str = target_date.isoformat()
            valid_versions = []
            
            for i, version_id in enumerate(results['ids']):
                metadata = results['metadatas'][i]
                created_at = metadata.get('created_at', '')
                
                if created_at <= target_date_str:
                    valid_versions.append(metadata)
            
            # Group by document_id and keep latest version before target date
            state = {}
            for version in valid_versions:
                doc_id = version['document_id']
                revision = version.get('revision_index', 0)
                
                if doc_id not in state or revision > state[doc_id].get('revision_index', 0):
                    state[doc_id] = version
            
            return {
                'object_id': object_id,
                'target_date': target_date.isoformat(),
                'state': state,
                'version_count': len(state)
            }
            
        except Exception as e:
            logger.error(f"Error replaying state: {e}")
            return {
                'object_id': object_id,
                'target_date': target_date.isoformat(),
                'state': {},
                'error': str(e)
            }
    
    def get_version_history(self, document_id: str) -> List[Dict[str, Any]]:
        """
        Get version history for a document.
        
        Args:
            document_id: Document ID
            
        Returns:
            List of versions
        """
        try:
            results = self.collection.get(
                where={'document_id': document_id}
            )
            
            if not results or not results['ids']:
                return []
            
            versions = []
            for i, version_id in enumerate(results['ids']):
                metadata = results['metadatas'][i]
                versions.append(metadata)
            
            # Sort by revision_index (descending)
            versions.sort(key=lambda x: x.get('revision_index', 0), reverse=True)
            
            return versions
            
        except Exception as e:
            logger.error(f"Error getting version history: {e}")
            return []


class ChunkVersionManager:
    """
    Manage chunk versioning in ChromaDB RAG.
    
    Ensures that during RAG searches, only actual chunks
    from the latest document revision are returned.
    """
    
    def __init__(self, chroma_manager, state_replay: StateReplayEngine):
        """
        Initialize Chunk Version Manager.
        
        Args:
            chroma_manager: ChromaDB manager instance
            state_replay: State Replay Engine instance
        """
        self.chroma_manager = chroma_manager
        self.state_replay = state_replay
    
    def add_versioned_chunks(
        self,
        document_id: str,
        document_name: str,
        revision_index: int,
        chunks: List[Dict[str, Any]],
        object_id: Optional[str] = None
    ) -> bool:
        """
        Add chunks with version tracking.
        
        Args:
            document_id: Document ID
            document_name: Document name
            revision_index: Revision number
            chunks: List of chunks to add
            object_id: Object ID
            
        Returns:
            True if successful
        """
        # Register document version
        version_id = self.state_replay.register_document_version(
            document_id=document_id,
            document_name=document_name,
            revision_index=revision_index,
            object_id=object_id
        )
        
        if not version_id:
            return False
        
        # Block obsolete chunks from previous revisions
        self.mark_chunks_obsolete(document_id, revision_index)
        
        # Add chunks to main collection with version metadata
        ids = []
        documents = []
        metadatas = []
        
        for i, chunk in enumerate(chunks):
            chunk_id = f"{document_id}_rev_{revision_index}_chunk_{i}"
            
            metadata = chunk.get('metadata', {}).copy()
            metadata.update({
                'document_id': document_id,
                'revision_index': revision_index,
                'version_id': version_id,
                'status': 'actual'
            })
            
            if object_id:
                metadata['object_id'] = object_id
            
            ids.append(chunk_id)
            documents.append(chunk.get('text', ''))
            metadatas.append(_scalar_metadata(metadata))
        
        try:
            self.chroma_manager.collection.add(
                ids=ids,
                documents=documents,
                metadatas=metadatas
            )
            
            logger.info(f"Added {len(chunks)} versioned chunks for {document_id} rev {revision_index}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding versioned chunks: {e}")
            return False
    
    def mark_chunks_obsolete(self, document_id: str, revision_index: int):
        """Mark chunks from previous revision as obsolete."""
        try:
            # Get chunks with this document_id and lower revision
            results = self.chroma_manager.collection.get(
                where={'$and': [
                    {'document_id': document_id},
                    {'revision_index': {'$lt': revision_index}},
                ]}
            )
            
            if results and results['ids']:
                for i, chunk_id in enumerate(results['ids']):
                    metadata = results['metadatas'][i]
                    # Update status to obsolete
                    self.chroma_manager.collection.update(
                        ids=[chunk_id],
                        metadatas=[{**metadata, 'status': 'obsolete'}]
                    )
                
                logger.info(f"Marked {len(results['ids'])} chunks as obsolete for {document_id}")
            
        except Exception as e:
            logger.error(f"Error marking chunks obsolete: {e}")
    
    def query_actual_chunks(self, query: str, object_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Query only actual chunks (latest revision).
        
        Args:
            query: Search query
            object_id: Object ID filter
            
        Returns:
            List of actual chunks
        """
        # Build filter - only actual chunks
        clauses = [{'status': 'actual'}]
        if object_id:
            clauses.append({'object_id': object_id})
        where_filter = clauses[0] if len(clauses) == 1 else {'$and': clauses}
        
        try:
            results = self.chroma_manager.collection.query(
                query_texts=[query],
                n_results=10,
                where=where_filter
            )
            
            # Format results
            formatted_results = []
            if results['documents'] and results['documents'][0]:
                for i, doc in enumerate(results['documents'][0]):
                    formatted_results.append({
                        'text': doc,
                        'metadata': results['metadatas'][0][i] if results['metadatas'] else {},
                        'distance': results['distances'][0][i] if results['distances'] else None
                    })
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Error querying actual chunks: {e}")
            return []


if __name__ == "__main__":
    # Test State Replay Engine
    logging.basicConfig(level=logging.INFO)
    
    replay_engine = StateReplayEngine()
    
    # Test version registration
    version_id = replay_engine.register_document_version(
        document_id="DOC-001",
        document_name="Смета_объект_123.xlsx",
        revision_index=0,
        object_id="OBJ-123"
    )
    
    print(f"Registered version: {version_id}")
    
    # Test version history
    history = replay_engine.get_version_history("DOC-001")
    print(f"Version history: {len(history)} versions")
