"""Constraint Manager - Network of Constraints and Limitations.

This module implements the Constraint Management pattern from Lean Construction:
- Track constraints for each object
- Validate if all blocking constraints are lifted
- Support dynamic constraint resolution
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum

from app.modules.storage.database import get_db_connection

logger = logging.getLogger(__name__)


class ConstraintType(str, Enum):
    """Types of constraints."""
    LEGAL = "legal"  # Permits, approvals
    FINANCIAL = "financial"  # Budget, payments
    TECHNICAL = "technical"  # Technical requirements
    SCHEDULE = "schedule"  # Deadlines, dependencies
    MATERIAL = "material"  # Material availability
    PERSONNEL = "personnel"  # Staff availability


class ConstraintStatus(str, Enum):
    """Constraint status."""
    BLOCKING = "blocking"  # Blocks action
    WARNING = "warning"  # Caution required
    RESOLVED = "resolved"  # No longer blocks
    IGNORED = "ignored"  # Deliberately ignored


class ConstraintManager:
    """
    Manage constraints for construction objects.
    
    Implements the Constraint Management pattern from Lean Construction:
    - Each object has a pool of constraints
    - Actions can only proceed when all blocking constraints are resolved
    - Constraints can be added, resolved, or ignored
    """
    
    def __init__(self):
        """Initialize Constraint Manager."""
        self._ensure_tables()
    
    def _ensure_tables(self):
        """Create necessary database tables."""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Constraints table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS constraints (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        object_id TEXT NOT NULL,
                        constraint_type TEXT NOT NULL,
                        description TEXT NOT NULL,
                        status TEXT DEFAULT 'blocking',
                        required_for TEXT,
                        resolved_at TIMESTAMP,
                        resolved_by TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        metadata TEXT DEFAULT '{}'
                    )
                """)
                
                # Constraint history table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS constraint_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        constraint_id INTEGER NOT NULL,
                        action TEXT NOT NULL,
                        actor TEXT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        notes TEXT
                    )
                """)
                
                logger.info("Constraint Manager tables initialized")
                
        except Exception as e:
            logger.error(f"Error creating Constraint Manager tables: {e}")
    
    def add_constraint(
        self,
        object_id: str,
        constraint_type: ConstraintType,
        description: str,
        required_for: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Add a new constraint.
        
        Args:
            object_id: Object ID
            constraint_type: Type of constraint
            description: Constraint description
            required_for: What action this constraint blocks
            metadata: Additional metadata
            
        Returns:
            Constraint ID
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO constraints (
                        object_id, constraint_type, description, status, required_for, metadata
                    ) VALUES (?, ?, ?, 'blocking', ?, ?)
                """, (
                    object_id,
                    constraint_type.value,
                    description,
                    required_for,
                    str(metadata or {})
                ))
                
                constraint_id = cursor.lastrowid
                logger.info(f"Added constraint {constraint_id} for {object_id}: {constraint_type}")
                return constraint_id
                
        except Exception as e:
            logger.error(f"Error adding constraint: {e}")
            return -1
    
    def resolve_constraint(
        self,
        constraint_id: int,
        resolved_by: str,
        notes: Optional[str] = None
    ) -> bool:
        """
        Resolve a constraint.
        
        Args:
            constraint_id: Constraint ID
            resolved_by: Who resolved it
            notes: Resolution notes
            
        Returns:
            True if successful
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Update constraint status
                cursor.execute("""
                    UPDATE constraints
                    SET status = 'resolved', resolved_at = CURRENT_TIMESTAMP, resolved_by = ?
                    WHERE id = ?
                """, (resolved_by, constraint_id))
                
                # Add to history
                cursor.execute("""
                    INSERT INTO constraint_history (constraint_id, action, actor, notes)
                    VALUES (?, 'resolved', ?, ?)
                """, (constraint_id, resolved_by, notes))
                
                logger.info(f"Resolved constraint {constraint_id} by {resolved_by}")
                return True
                
        except Exception as e:
            logger.error(f"Error resolving constraint: {e}")
            return False
    
    def ignore_constraint(
        self,
        constraint_id: int,
        ignored_by: str,
        reason: str
    ) -> bool:
        """
        Ignore a constraint (deliberately bypass).
        
        Args:
            constraint_id: Constraint ID
            ignored_by: Who ignored it
            reason: Reason for ignoring
            
        Returns:
            True if successful
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Update constraint status
                cursor.execute("""
                    UPDATE constraints
                    SET status = 'ignored'
                    WHERE id = ?
                """, (constraint_id,))
                
                # Add to history
                cursor.execute("""
                    INSERT INTO constraint_history (constraint_id, action, actor, notes)
                    VALUES (?, 'ignored', ?, ?)
                """, (constraint_id, ignored_by, reason))
                
                logger.warning(f"Ignored constraint {constraint_id} by {ignored_by}: {reason}")
                return True
                
        except Exception as e:
            logger.error(f"Error ignoring constraint: {e}")
            return False
    
    def get_object_constraints(
        self,
        object_id: str,
        status: Optional[ConstraintStatus] = None
    ) -> List[Dict[str, Any]]:
        """
        Get constraints for an object.
        
        Args:
            object_id: Object ID
            status: Filter by status (optional)
            
        Returns:
            List of constraints
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                if status:
                    cursor.execute("""
                        SELECT * FROM constraints
                        WHERE object_id = ? AND status = ?
                        ORDER BY created_at DESC
                    """, (object_id, status.value))
                else:
                    cursor.execute("""
                        SELECT * FROM constraints
                        WHERE object_id = ?
                        ORDER BY created_at DESC
                    """, (object_id,))
                
                constraints = []
                for row in cursor.fetchall():
                    constraints.append({
                        'id': row['id'],
                        'object_id': row['object_id'],
                        'constraint_type': row['constraint_type'],
                        'description': row['description'],
                        'status': row['status'],
                        'required_for': row['required_for'],
                        'resolved_at': row['resolved_at'],
                        'resolved_by': row['resolved_by'],
                        'created_at': row['created_at'],
                        'metadata': row['metadata']
                    })
                
                return constraints
                
        except Exception as e:
            logger.error(f"Error getting constraints for {object_id}: {e}")
            return []
    
    def can_proceed(self, object_id: str, action: str) -> Dict[str, Any]:
        """
        Check if an action can proceed (all blocking constraints resolved).
        
        Args:
            object_id: Object ID
            action: Action to check
            
        Returns:
            Feasibility assessment
        """
        constraints = self.get_object_constraints(object_id)
        
        # Filter blocking constraints for this action
        blocking = [
            c for c in constraints
            if c['status'] == 'blocking' and c['required_for'] == action
        ]
        
        if not blocking:
            return {
                'can_proceed': True,
                'blocking_constraints': [],
                'message': f"All constraints resolved for {action}"
            }
        else:
            return {
                'can_proceed': False,
                'blocking_constraints': blocking,
                'message': f"Cannot proceed with {action}: {len(blocking)} blocking constraints"
            }
    
    def get_constraint_summary(self, object_id: str) -> Dict[str, Any]:
        """
        Get constraint summary for an object.
        
        Args:
            object_id: Object ID
            
        Returns:
            Constraint summary
        """
        constraints = self.get_object_constraints(object_id)
        
        summary = {
            'total': len(constraints),
            'blocking': len([c for c in constraints if c['status'] == 'blocking']),
            'resolved': len([c for c in constraints if c['status'] == 'resolved']),
            'ignored': len([c for c in constraints if c['status'] == 'ignored']),
            'by_type': {},
            'blocking_by_type': {}
        }
        
        for constraint in constraints:
            c_type = constraint['constraint_type']
            
            if c_type not in summary['by_type']:
                summary['by_type'][c_type] = 0
            summary['by_type'][c_type] += 1
            
            if constraint['status'] == 'blocking':
                if c_type not in summary['blocking_by_type']:
                    summary['blocking_by_type'][c_type] = 0
                summary['blocking_by_type'][c_type] += 1
        
        return summary


if __name__ == "__main__":
    # Test Constraint Manager
    logging.basicConfig(level=logging.INFO)
    
    manager = ConstraintManager()
    
    # Add test constraint
    constraint_id = manager.add_constraint(
        object_id="TEST-001",
        constraint_type=ConstraintType.LEGAL,
        description="Ожидание разрешения МПТЦ",
        required_for="excavation"
    )
    
    print(f"Added constraint {constraint_id}")
    
    # Check if can proceed
    feasibility = manager.can_proceed("TEST-001", "excavation")
    print(f"Can proceed: {feasibility}")
    
    # Get summary
    summary = manager.get_constraint_summary("TEST-001")
    print(f"Constraint summary: {summary}")
