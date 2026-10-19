"""Virtual Documents - Track missing/phantom documents.

This module tracks documents that are referenced but missing,
providing a way to account for phantom documents in the system.

Storage schema (see app/modules/storage/database.py):
    virtual_documents(
        virtual_doc_id, diary_id, doc_type, doc_name, status,
        expected_deadline, expected_source, actual_doc_id,
        actual_received_at, created_at, updated_at
    )
"""

import logging
from enum import Enum
from typing import Any, Dict, List, Optional

from app.modules.storage.database import get_db_connection

logger = logging.getLogger(__name__)


class VirtualDocumentStatus(str, Enum):
    """Status of virtual documents (matches DB values)."""
    EXPECTED = "EXPECTED"  # Document should exist
    MISSING = "MISSING"  # Document referenced but not found
    PHANTOM = "PHANTOM"  # Document may not exist
    OBSOLETE = "OBSOLETE"  # Document reference is outdated
    FOUND = "FOUND"  # Document was located


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

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS virtual_documents (
                        virtual_doc_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        diary_id INTEGER NOT NULL,
                        doc_type TEXT NOT NULL,
                        doc_name TEXT NOT NULL,
                        status TEXT DEFAULT 'MISSING',
                        expected_deadline TIMESTAMP,
                        expected_source TEXT,
                        actual_doc_id TEXT,
                        actual_received_at TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
        status: VirtualDocumentStatus = VirtualDocumentStatus.EXPECTED,
        diary_id: int = 0,
        expected_deadline: Optional[str] = None,
    ) -> int:
        """
        Register a virtual document.

        Args:
            doc_id: Document ID (stored in actual_doc_id as the reference key)
            doc_name: Document name
            doc_type: Document type
            expected_location: Where the document should be
            referenced_in: Where this document was referenced
            status: Initial status
            diary_id: Owning diary (0 = unassigned)
            expected_deadline: Optional deadline for receiving the document

        Returns:
            Virtual document ID
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO virtual_documents (
                        diary_id, doc_type, doc_name, status,
                        expected_deadline, expected_source, actual_doc_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    diary_id,
                    doc_type,
                    doc_name,
                    status.value,
                    expected_deadline,
                    f"{expected_location} | referenced_in={referenced_in}",
                    doc_id,
                ))

                virtual_id = cursor.lastrowid
                logger.info(f"Registered virtual document {doc_id}")
                return virtual_id

        except Exception as e:
            logger.error(f"Error registering virtual document: {e}")
            return -1

    def mark_as_found(self, doc_id: str, found_date: str, notes: str) -> bool:
        """Mark a virtual document as found."""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE virtual_documents
                    SET status = 'FOUND', actual_received_at = ?,
                        expected_source = expected_source || ' | notes=' || ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE actual_doc_id = ?
                """, (found_date, notes, doc_id))

                logger.info(f"Marked virtual document {doc_id} as found")
                return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"Error marking document as found: {e}")
            return False

    def mark_as_missing(self, doc_id: str, notes: str) -> bool:
        """Mark a virtual document as missing."""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE virtual_documents
                    SET status = 'MISSING',
                        expected_source = expected_source || ' | notes=' || ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE actual_doc_id = ?
                """, (notes, doc_id))

                logger.warning(f"Marked virtual document {doc_id} as missing")
                return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"Error marking document as missing: {e}")
            return False

    @staticmethod
    def _row_to_dict(row) -> Dict[str, Any]:
        return {
            'id': row['virtual_doc_id'],
            'virtual_doc_id': row['virtual_doc_id'],
            'diary_id': row['diary_id'],
            'doc_id': row['actual_doc_id'],
            'doc_name': row['doc_name'],
            'doc_type': row['doc_type'],
            'status': row['status'],
            'expected_deadline': row['expected_deadline'],
            'expected_location': row['expected_source'],
            'referenced_in': row['expected_source'],
            'found_date': row['actual_received_at'],
            'created_at': row['created_at'],
        }

    def get_missing_documents(self) -> List[Dict[str, Any]]:
        """Get all missing/expected virtual documents."""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM virtual_documents
                    WHERE status IN ('MISSING', 'EXPECTED')
                    ORDER BY created_at DESC
                """)
                return [self._row_to_dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Error getting missing documents: {e}")
            return []

    def get_virtual_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific virtual document."""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM virtual_documents
                    WHERE actual_doc_id = ?
                """, (doc_id,))

                row = cursor.fetchone()
                return self._row_to_dict(row) if row else None

        except Exception as e:
            logger.error(f"Error getting virtual document: {e}")
            return None
