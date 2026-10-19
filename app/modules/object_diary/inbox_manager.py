"""Inbox Manager - Human-in-the-loop for ambiguous cases.

This module manages cases that require human intervention or verification,
providing an inbox for unresolved items and tracking their resolution.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum

from app.modules.storage.database import get_db_connection

logger = logging.getLogger(__name__)


class InboxItemType(str, Enum):
    """Types of inbox items."""
    VERIFICATION_REQUIRED = "verification_required"
    CONFLICT_DETECTED = "conflict_detected"
    MISSING_INFORMATION = "missing_information"
    AMBIGUOUS_LINK = "ambiguous_link"
    HIGH_RISK_ACTION = "high_risk_action"


class InboxItemStatus(str, Enum):
    """Status of inbox items."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    REJECTED = "rejected"
    ESCALATED = "escalated"


class InboxManager:
    """
    Manage inbox for human-in-the-loop cases.
    
    Provides centralized tracking of items requiring human intervention,
    with status tracking and resolution history.
    """
    
    def __init__(self):
        """Initialize Inbox Manager."""
        self._ensure_tables()
    
    def _ensure_tables(self):
        """Create necessary database tables."""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Inbox items table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS inbox_items (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        item_type TEXT NOT NULL,
                        title TEXT NOT NULL,
                        description TEXT,
                        source_type TEXT,
                        source_id TEXT,
                        related_object_id TEXT,
                        priority INTEGER DEFAULT 5,
                        status TEXT DEFAULT 'pending',
                        assigned_to TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        resolved_at TIMESTAMP,
                        resolution_notes TEXT,
                        metadata TEXT DEFAULT '{}'
                    )
                """)
                
                # Inbox history table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS inbox_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        item_id INTEGER NOT NULL,
                        action TEXT NOT NULL,
                        actor TEXT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        notes TEXT
                    )
                """)
                
                logger.info("Inbox Manager tables initialized")
                
        except Exception as e:
            logger.error(f"Error creating Inbox Manager tables: {e}")
    
    def create_item(
        self,
        item_type: InboxItemType,
        title: str,
        description: str,
        source_type: str,
        source_id: str,
        related_object_id: Optional[str] = None,
        priority: int = 5,
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Create a new inbox item.
        
        Args:
            item_type: Type of item
            title: Item title
            description: Item description
            source_type: Type of source (document_link, contract_analysis, etc.)
            source_id: ID of the source item
            related_object_id: Related object ID (optional)
            priority: Priority (1-10, higher = more urgent)
            metadata: Additional metadata
            
        Returns:
            Item ID
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO inbox_items (
                        item_type, title, description, source_type, source_id,
                        related_object_id, priority, status, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)
                """, (
                    item_type.value,
                    title,
                    description,
                    source_type,
                    source_id,
                    related_object_id,
                    priority,
                    str(metadata or {})
                ))
                
                item_id = cursor.lastrowid
                logger.info(f"Created inbox item {item_id}: {title}")
                return item_id
                
        except Exception as e:
            logger.error(f"Error creating inbox item: {e}")
            return -1
    
    def assign_item(self, item_id: int, assigned_to: str) -> bool:
        """
        Assign an inbox item to a person.
        
        Args:
            item_id: Item ID
            assigned_to: Person to assign to
            
        Returns:
            True if successful
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE inbox_items
                    SET assigned_to = ?, status = 'in_progress'
                    WHERE id = ?
                """, (assigned_to, item_id))
                
                # Add to history
                cursor.execute("""
                    INSERT INTO inbox_history (item_id, action, actor, notes)
                    VALUES (?, 'assigned', ?, ?)
                """, (item_id, assigned_to, f"Assigned to {assigned_to}"))
                
                logger.info(f"Assigned item {item_id} to {assigned_to}")
                return True
                
        except Exception as e:
            logger.error(f"Error assigning item: {e}")
            return False
    
    def resolve_item(
        self,
        item_id: int,
        resolved_by: str,
        resolution_notes: str,
        status: InboxItemStatus = InboxItemStatus.RESOLVED
    ) -> bool:
        """
        Resolve an inbox item.
        
        Args:
            item_id: Item ID
            resolved_by: Who resolved it
            resolution_notes: Resolution notes
            status: Final status
            
        Returns:
            True if successful
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE inbox_items
                    SET status = ?, resolved_at = CURRENT_TIMESTAMP,
                        resolution_notes = ?
                    WHERE id = ?
                """, (status.value, resolution_notes, item_id))
                
                # Add to history
                cursor.execute("""
                    INSERT INTO inbox_history (item_id, action, actor, notes)
                    VALUES (?, 'resolved', ?, ?)
                """, (item_id, resolved_by, resolution_notes))
                
                logger.info(f"Resolved item {item_id} with status {status.value}")
                return True
                
        except Exception as e:
            logger.error(f"Error resolving item: {e}")
            return False
    
    def get_pending_items(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get pending inbox items.
        
        Args:
            limit: Maximum number of items
            
        Returns:
            List of pending items
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM inbox_items
                    WHERE status IN ('pending', 'in_progress')
                    ORDER BY priority DESC, created_at ASC
                    LIMIT ?
                """, (limit,))
                
                items = []
                for row in cursor.fetchall():
                    items.append({
                        'id': row['id'],
                        'item_type': row['item_type'],
                        'title': row['title'],
                        'description': row['description'],
                        'source_type': row['source_type'],
                        'source_id': row['source_id'],
                        'related_object_id': row['related_object_id'],
                        'priority': row['priority'],
                        'status': row['status'],
                        'assigned_to': row['assigned_to'],
                        'created_at': row['created_at']
                    })
                
                return items
                
        except Exception as e:
            logger.error(f"Error getting pending items: {e}")
            return []
    
    def get_items_by_object(self, object_id: str) -> List[Dict[str, Any]]:
        """
        Get inbox items for a specific object.
        
        Args:
            object_id: Object ID
            
        Returns:
            List of items for that object
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM inbox_items
                    WHERE related_object_id = ?
                    ORDER BY created_at DESC
                """, (object_id,))
                
                items = []
                for row in cursor.fetchall():
                    items.append({
                        'id': row['id'],
                        'item_type': row['item_type'],
                        'title': row['title'],
                        'description': row['description'],
                        'status': row['status'],
                        'priority': row['priority'],
                        'created_at': row['created_at']
                    })
                
                return items
                
        except Exception as e:
            logger.error(f"Error getting items by object: {e}")
            return []


if __name__ == "__main__":
    # Test Inbox Manager
    logging.basicConfig(level=logging.INFO)
    
    inbox = InboxManager()
    
    # Create test item
    item_id = inbox.create_item(
        item_type=InboxItemType.VERIFICATION_REQUIRED,
        title="Contract link verification",
        description="Contract 123 linked to object OBJ-001 needs verification",
        source_type="document_link",
        source_id="LINK-001",
        related_object_id="OBJ-001",
        priority=8
    )
    
    print(f"Created inbox item {item_id}")
    
    # Get pending items
    pending = inbox.get_pending_items()
    print(f"Pending items: {len(pending)}")
