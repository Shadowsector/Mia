"""Virtual Documents - Track missing/phantom documents.

This module tracks documents that are referenced but missing,
providing a way to account for phantom documents in the system.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum

from app.modules.storage.database import get_db_connection

logger = logging.getLogger(__name__)


class VirtualDocumentStatus(str, Enum):
    """Status of virtual documents."""
    EXPECTED = "expected"  # Document should exist
    MISSING = "missing"  # Document referenced but not found
    PHANTOM = "phantom"  # Document may not exist
    OBSOLETE = "obsolete"  # Document reference is outdated


class VirtualDocumentManager:
    """
    Track virtual (missing/phantom) documents.
    
    Maintains a registry of documents that are referenced in the system
    but not yet physically present, allowing for proper tracking and follow-up.
    """
    
    def __init__(self):
        """Initialize Virtual Document Manager."""
        self._ensure_tables()
    
    def _ensure_tables(self):
        """Create necessary database tables."""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Virtual documents table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS virtual_documents (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        doc_id TEXT NOT NULL,
                        doc_name TEXT NOT NULL,
                        doc_type TEXT,
                        expected_location TEXT,
                        status TEXT DEFAULT 'expected',
                        referenced_in TEXT,
                        reference_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        found_date TIMESTAMP,
                        notes TEXT,
                        metadata TEXT DEFAULT '{}'
                    )
                """)
                
                logger.info("Virtual Document Manager tables initialized")
                
        except Exception as e:
            logger.error(f"Error creating Virtual Document tables: {e}")
    
    def register_virtual_document(
        self,
        doc_id: str,
        doc_name: str,
        doc_type: str,
        expected_location: str,
        referenced_in: str,
        status: VirtualDocumentStatus = VirtualDocumentStatus.EXPECTED
    ) -> int:
        """
        Register a virtual document.
        
        Args:
            doc_id: Document ID
            doc_name: Document name
            doc_type: Document type
            expected_location: Where the document should be
            referenced_in: Where this document was referenced
            status: Initial status
            
        Returns:
            Virtual document ID
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO virtual_documents (
                        doc_id, doc_name, doc_type, expected_location,
                        referenced_in, status
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (doc_id, doc_name, doc_type, expected_location, referenced_in, status.value))
                
                virtual_id = cursor.lastrowid
                logger.info(f"Registered virtual document {doc_id}")
                return virtual_id
                
        except Exception as e:
            logger.error(f"Error registering virtual document: {e}")
            return -1
    
    def mark_as_found(self, doc_id: str, found_date: str, notes: str) -> bool:
        """
        Mark a virtual document as found.
        
        Args:
            doc_id: Document ID
            found_date: Date when document was found
            notes: Notes about finding
            
        Returns:
            True if successful
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE virtual_documents
                    SET status = 'found', found_date = ?, notes = ?
                    WHERE doc_id = ?
                """, (found_date, notes, doc_id))
                
                logger.info(f"Marked virtual document {doc_id} as found")
                return True
                
        except Exception as e:
            logger.error(f"Error marking document as found: {e}")
            return False
    
    def mark_as_missing(self, doc_id: str, notes: str) -> bool:
        """
        Mark a virtual document as missing.
        
        Args:
            doc_id: Document ID
            notes: Notes about why it's missing
            
        Returns:
            True if successful
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE virtual_documents
                    SET status = 'missing', notes = ?
                    WHERE doc_id = ?
                """, (notes, doc_id))
                
                logger.warning(f"Marked virtual document {doc_id} as missing")
                return True
                
        except Exception as e:
            logger.error(f"Error marking document as missing: {e}")
            return False
    
    def get_missing_documents(self) -> List[Dict[str, Any]]:
        """
        Get all missing virtual documents.
        
        Returns:
            List of missing documents
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM virtual_documents
                    WHERE status IN ('missing', 'expected')
                    ORDER BY reference_date DESC
                """)
                
                docs = []
                for row in cursor.fetchall():
                    docs.append({
                        'id': row['id'],
                        'doc_id': row['doc_id'],
                        'doc_name': row['doc_name'],
                        'doc_type': row['doc_type'],
                        'expected_location': row['expected_location'],
                        'status': row['status'],
                        'referenced_in': row['referenced_in'],
                        'reference_date': row['reference_date']
                    })
                
                return docs
                
        except Exception as e:
            logger.error(f"Error getting missing documents: {e}")
            return []
    
    def get_virtual_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific virtual document.
        
        Args:
            doc_id: Document ID
            
        Returns:
            Virtual document dict or None
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM virtual_documents
                    WHERE doc_id = ?
                """, (doc_id,))
                
                row = cursor.fetchone()
                if row:
                    return {
                        'id': row['id'],
                        'doc_id': row['doc_id'],
                        'doc_name': row['doc_name'],
                        'doc_type': row['doc_type'],
                        'expected_location': row['expected_location'],
                        'status': row['status'],
                        'referenced_in': row['referenced_in'],
                        'reference_date': row['reference_date'],
                        'found_date': row['found_date'],
                        'notes': row['notes']
                    }
                
                return None
                
        except Exception as e:
            logger.error(f"Error getting virtual document: {e}")
            return None


if __name__ == "__main__":
    # Test Virtual Document Manager
    logging.basicConfig(level=logging.INFO)
    
    manager = VirtualDocumentManager()
    
    # Register test virtual document
    virtual_id = manager.register_virtual_document(
        doc_id="DOC-EXPECTED-001",
        doc_name="Договор OBJ-123",
        doc_type="contract",
        expected_location="Google Drive/Договоры",
        referenced_in="Contract Linker"
    )
    
    print(f"Registered virtual document with ID: {virtual_id}")
    
    # Get missing documents
    missing = manager.get_missing_documents()
    print(f"Missing documents: {len(missing)}")
