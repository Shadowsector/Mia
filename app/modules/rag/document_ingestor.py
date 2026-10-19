"""Document Ingestor - Ingest processed documents into RAG system.

This module takes processed documents from the document parser,
chunks them, and adds them to ChromaDB for semantic search.
"""

import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime

from app.modules.rag.chroma_manager import ChromaManager
from app.modules.document_parser import DocumentParserFactory

logger = logging.getLogger(__name__)


class DocumentIngestor:
    """
    Ingest documents into RAG system.
    
    Chunks documents and adds them to ChromaDB with proper metadata.
    """
    
    def __init__(self, chroma_manager: Optional[ChromaManager] = None):
        """
        Initialize Document Ingestor.
        
        Args:
            chroma_manager: ChromaManager instance (creates default if None)
        """
        self.chroma_manager = chroma_manager or ChromaManager()
        self.document_parser = DocumentParserFactory()
        
        # Chunk size in characters
        self.chunk_size = 1000
        self.chunk_overlap = 200
    
    def chunk_text(self, text: str) -> List[str]:
        """
        Split text into chunks for embedding.
        
        Args:
            text: Text to chunk
            
        Returns:
            List of text chunks
        """
        if not text:
            return []
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + self.chunk_size
            
            # Try to break at sentence boundary
            if end < len(text):
                # Look for sentence ending punctuation
                for delimiter in ['.', '!', '?', '\n']:
                    last_delim = text.rfind(delimiter, start, end)
                    if last_delim > start:
                        end = last_delim + 1
                        break
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            start = end - self.chunk_overlap
        
        return chunks
    
    def ingest_document(
        self,
        file_path: str,
        object_id: Optional[str] = None,
        document_type: str = "general",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Ingest a single document into RAG.
        
        Args:
            file_path: Path to document file
            object_id: Associated object ID (optional)
            document_type: Type of document (contract, invoice, estimate, etc.)
            metadata: Additional metadata
            
        Returns:
            Summary of ingestion results
        """
        file_path = Path(file_path)
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return {'success': False, 'error': 'File not found'}
        
        # Parse document
        try:
            parsed = self.document_parser.parse_document(str(file_path))
            text = parsed.get('text', '')
            
            if not text:
                logger.warning(f"No text extracted from {file_path}")
                return {'success': False, 'error': 'No text extracted'}
            
        except Exception as e:
            logger.error(f"Error parsing document {file_path}: {e}")
            return {'success': False, 'error': str(e)}
        
        # Chunk text
        chunks = self.chunk_text(text)
        
        if not chunks:
            logger.warning(f"No chunks generated from {file_path}")
            return {'success': False, 'error': 'No chunks generated'}
        
        # Prepare metadata for each chunk
        base_metadata = {
            'source_file': str(file_path),
            'file_name': file_path.name,
            'document_type': document_type,
            'ingested_at': datetime.now().isoformat(),
            'chunk_count': len(chunks)
        }
        
        if object_id:
            base_metadata['object_id'] = object_id
        
        if metadata:
            base_metadata.update(metadata)
        
        # Add chunks to ChromaDB
        try:
            ids = []
            documents = []
            metadatas = []
            
            for i, chunk in enumerate(chunks):
                chunk_id = f"{file_path.stem}_chunk_{i}"
                chunk_metadata = base_metadata.copy()
                chunk_metadata['chunk_index'] = i
                chunk_metadata['chunk_total'] = len(chunks)
                
                ids.append(chunk_id)
                documents.append(chunk)
                metadatas.append(chunk_metadata)
            
            self.chroma_manager.collection.add(
                ids=ids,
                documents=documents,
                metadatas=metadatas
            )
            
            logger.info(f"Ingested {len(chunks)} chunks from {file_path}")
            
            return {
                'success': True,
                'chunks_added': len(chunks),
                'file_path': str(file_path),
                'object_id': object_id
            }
            
        except Exception as e:
            logger.error(f"Error adding chunks to ChromaDB: {e}")
            return {'success': False, 'error': str(e)}
    
    def ingest_directory(
        self,
        directory: str,
        object_id: Optional[str] = None,
        file_patterns: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Ingest all documents from a directory.
        
        Args:
            directory: Directory path
            object_id: Associated object ID (optional)
            file_patterns: File patterns to match (e.g., ['*.pdf', '*.docx'])
            
        Returns:
            Summary of ingestion results
        """
        directory = Path(directory)
        if not directory.exists():
            logger.error(f"Directory not found: {directory}")
            return {'success': False, 'error': 'Directory not found'}
        
        if file_patterns is None:
            file_patterns = ['*.pdf', '*.docx', '*.doc', '*.txt']
        
        results = {
            'success': True,
            'total_files': 0,
            'successful': 0,
            'failed': 0,
            'files': []
        }
        
        for pattern in file_patterns:
            for file_path in directory.glob(pattern):
                results['total_files'] += 1
                
                # Determine document type from filename
                filename_lower = file_path.name.lower()
                if 'договор' in filename_lower or 'contract' in filename_lower:
                    doc_type = 'contract'
                elif 'смета' in filename_lower or 'estimate' in filename_lower:
                    doc_type = 'estimate'
                elif 'накладная' in filename_lower or 'invoice' in filename_lower:
                    doc_type = 'invoice'
                else:
                    doc_type = 'general'
                
                # Ingest file
                result = self.ingest_document(
                    file_path=str(file_path),
                    object_id=object_id,
                    document_type=doc_type
                )
                
                if result['success']:
                    results['successful'] += 1
                    results['files'].append({
                        'file': str(file_path),
                        'status': 'success',
                        'chunks': result['chunks_added']
                    })
                else:
                    results['failed'] += 1
                    results['files'].append({
                        'file': str(file_path),
                        'status': 'failed',
                        'error': result.get('error', 'Unknown error')
                    })
        
        logger.info(f"Ingestion complete: {results['successful']}/{results['total_files']} successful")
        return results
    
    def search_similar_documents(
        self,
        query: str,
        n_results: int = 5,
        object_id: Optional[str] = None,
        document_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar documents in RAG.
        
        Args:
            query: Search query
            n_results: Number of results to return
            object_id: Filter by object ID (optional)
            document_type: Filter by document type (optional)
            
        Returns:
            List of similar document chunks with metadata
        """
        # Build filter
        where_filter = {}
        if object_id:
            where_filter['object_id'] = object_id
        if document_type:
            where_filter['document_type'] = document_type
        
        # Query ChromaDB
        try:
            results = self.chroma_manager.collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where_filter if where_filter else None
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
            logger.error(f"Error querying ChromaDB: {e}")
            return []


if __name__ == "__main__":
    # Test document ingestor
    logging.basicConfig(level=logging.INFO)
    
    ingestor = DocumentIngestor()
    
    # Test chunking
    test_text = "Это тестовый текст для проверки разбиения на чанки. " * 20
    chunks = ingestor.chunk_text(test_text)
    print(f"Generated {len(chunks)} chunks")
    
    # Test ingestion (would need actual file)
    # result = ingestor.ingest_document("test.pdf")
    # print(result)
