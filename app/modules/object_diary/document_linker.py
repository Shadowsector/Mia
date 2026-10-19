"""Document Linker - Isolated pipeline for linking documents to objects.

This module provides an isolated pipeline for automatically linking
documents to construction objects based on content analysis.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path

from app.modules.storage.database import get_db_connection
from app.modules.document_info_extractor import DocumentInfoExtractor

logger = logging.getLogger(__name__)


class DocumentLinker:
    """
    Isolated pipeline for document linking.
    
    Analyzes document content and automatically links to construction objects
    with proper citation tracking and confidence scoring.
    """
    
    def __init__(self):
        """Initialize Document Linker."""
        self.info_extractor = DocumentInfoExtractor()
        self._ensure_tables()
    
    def _ensure_tables(self):
        """Create necessary database tables."""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Document links table with citation tracking
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS document_links (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        document_id TEXT NOT NULL,
                        document_name TEXT NOT NULL,
                        object_id TEXT NOT NULL,
                        link_type TEXT,
                        confidence REAL DEFAULT 0.5,
                        citation_text TEXT,
                        citation_page INTEGER,
                        citation_bbox TEXT,
                        linked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        verified_by TEXT,
                        verification_status TEXT DEFAULT 'AUTO_VERIFIED'
                    )
                """)
                
                logger.info("Document Linker tables initialized")
                
        except Exception as e:
            logger.error(f"Error creating Document Linker tables: {e}")
    
    def analyze_and_link(
        self,
        file_path: str,
        object_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze document and link to object.
        
        Args:
            file_path: Path to document
            object_id: Specific object ID (optional)
            
        Returns:
            Link result
        """
        # Extract information
        extraction = self.info_extractor.extract_all(file_path)
        
        if not extraction['success']:
            return extraction
        
        # Extract contract info
        contract_info = extraction['contract']
        
        # Determine object ID
        if object_id:
            target_object_id = object_id
        elif contract_info.get('object_name'):
            # Try to find object by name
            target_object_id = self._find_object_by_name(contract_info['object_name'])
        else:
            target_object_id = None
        
        if not target_object_id:
            return {
                'success': False,
                'error': 'Could not determine target object'
            }
        
        # Extract citation text (first 200 chars for context)
        citation_text = extraction.get('raw_text', '')[:200] if 'raw_text' in extraction else ''
        
        # Calculate confidence based on match quality
        confidence = 0.7 if object_id else 0.5
        
        # Save link
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO document_links (
                        document_id, document_name, object_id, link_type,
                        confidence, citation_text, linked_at
                    ) VALUES (?, ?, ?, 'content_match', ?, ?, CURRENT_TIMESTAMP)
                """, (
                    extraction['file_name'],
                    extraction['file_name'],
                    target_object_id,
                    confidence,
                    citation_text
                ))
                
                link_id = cursor.lastrowid
                logger.info(f"Linked document {extraction['file_name']} to {target_object_id}")
                
                return {
                    'success': True,
                    'link_id': link_id,
                    'object_id': target_object_id,
                    'confidence': confidence
                }
                
        except Exception as e:
            logger.error(f"Error saving document link: {e}")
            return {'success': False, 'error': str(e)}
    
    def _find_object_by_name(self, name: str) -> Optional[str]:
        """Find object ID by name."""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT object_id FROM objects
                    WHERE object_name LIKE ?
                """, (f"%{name}%",))
                
                row = cursor.fetchone()
                return row['object_id'] if row else None
                
        except Exception as e:
            logger.error(f"Error finding object by name: {e}")
            return None
    
    def get_document_links(self, object_id: str) -> List[Dict[str, Any]]:
        """Get all documents linked to an object."""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM document_links
                    WHERE object_id = ?
                    ORDER BY linked_at DESC
                """, (object_id,))
                
                links = []
                for row in cursor.fetchall():
                    links.append({
                        'id': row['id'],
                        'document_id': row['document_id'],
                        'document_name': row['document_name'],
                        'object_id': row['object_id'],
                        'link_type': row['link_type'],
                        'confidence': row['confidence'],
                        'citation_text': row['citation_text'],
                        'linked_at': row['linked_at'],
                        'verification_status': row['verification_status']
                    })
                
                return links
                
        except Exception as e:
            logger.error(f"Error getting document links: {e}")
            return []


if __name__ == "__main__":
    # Test Document Linker
    logging.basicConfig(level=logging.INFO)
    
    linker = DocumentLinker()
    
    # Test with a document (would need actual file)
    # result = linker.analyze_and_link("test.pdf", "TEST-001")
    # print(result)
