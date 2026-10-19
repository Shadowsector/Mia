"""Constraint Manager - Network of Constraints and Limitations.

This module implements the Constraint Management pattern from Lean Construction:
- Track constraints for each object
- Validate if all blocking constraints are lifted
- Support dynamic constraint resolution

Storage schema (see app/modules/storage/database.py):
    constraints(
        constraint_id, object_id, constraint_type, constraint_name,
        description, required_for_actions, status, satisfied_at, deadline,
        source_document_id, severity_level, bypass_strict_rule,
        bypass_reason, bypass_expiry, created_at, updated_at
    )
"""

import json
import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

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
    """Constraint status (matches DB values)."""
    NOT_SATISFIED = "NOT_SATISFIED"  # Blocks action
    SATISFIED = "SATISFIED"  # No longer blocks
    WAIVED = "WAIVED"  # Deliberately bypassed

    # Backwards-compatible aliases
    BLOCKING = "NOT_SATISFIED"
    RESOLVED = "SATISFIED"
    IGNORED = "WAIVED"


class ConstraintSeverity(str, Enum):
    """Constraint severity (matches DB values)."""
    CRITICAL = "CRITICAL"
    MAJOR = "MAJOR"
    MINOR = "MINOR"


class ConstraintManager:
    """
    Manage constraints for construction objects.

    Implements the Constraint Management pattern from Lean Construction:
    - Each object has a pool of constraints
    - Actions can only proceed when all blocking constraints are resolved
    - Constraints can be added, resolved, or waived
    """

    def __init__(self):
        """Initialize Constraint Manager."""
        self._ensure_tables()

    def _ensure_tables(self):
        """Create necessary database tables."""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS constraints (
                        constraint_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        object_id TEXT NOT NULL,
                        constraint_type TEXT NOT NULL,
                        constraint_name TEXT NOT NULL,
                        description TEXT NOT NULL,
                        required_for_actions TEXT DEFAULT '[]',
                        status TEXT DEFAULT 'NOT_SATISFIED',
                        satisfied_at TIMESTAMP,
                        deadline TIMESTAMP,
                        source_document_id TEXT,
                        severity_level TEXT DEFAULT 'MAJOR',
                        bypass_strict_rule BOOLEAN DEFAULT 0,
                        bypass_reason TEXT,
                        bypass_expiry TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

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
        metadata: Optional[Dict[str, Any]] = None,
        constraint_name: Optional[str] = None,
        severity: ConstraintSeverity = ConstraintSeverity.MAJOR,
    ) -> int:
        """
        Add a new constraint.

        Args:
            object_id: Object ID
            constraint_type: Type of constraint
            description: Constraint description
            required_for: Action this constraint blocks
            metadata: Additional metadata (unused, kept for API compatibility)
            constraint_name: Short name (defaults to description)
            severity: Severity level

        Returns:
            Constraint ID
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO constraints (
                        object_id, constraint_type, constraint_name, description,
                        required_for_actions, status, severity_level
                    ) VALUES (?, ?, ?, ?, ?, 'NOT_SATISFIED', ?)
                """, (
                    object_id,
                    constraint_type.value,
                    constraint_name or description,
                    description,
                    json.dumps([required_for]),
                    severity.value,
                ))

                constraint_id = cursor.lastrowid
                logger.info(
                    f"Added constraint {constraint_id} for {object_id}: {constraint_type}"
                )
                return constraint_id

        except Exception as e:
            logger.error(f"Error adding constraint: {e}")
            return -1

    def _set_status(
        self,
        constraint_id: int,
        status: ConstraintStatus,
        actor: Optional[str],
        notes: Optional[str],
        action: str,
        extra_sql: str = "",
        extra_params: tuple = (),
    ) -> bool:
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f"""
                    UPDATE constraints
                    SET status = ?, updated_at = CURRENT_TIMESTAMP{extra_sql}
                    WHERE constraint_id = ?
                """, (status.value, *extra_params, constraint_id))

                cursor.execute("""
                    INSERT INTO constraint_history (constraint_id, action, actor, notes)
                    VALUES (?, ?, ?, ?)
                """, (constraint_id, action, actor, notes))

                logger.info(f"Constraint {constraint_id}: {action} by {actor}")
                return True

        except Exception as e:
            logger.error(f"Error updating constraint {constraint_id}: {e}")
            return False

    def resolve_constraint(
        self,
        constraint_id: int,
        resolved_by: str,
        notes: Optional[str] = None,
    ) -> bool:
        """Resolve (satisfy) a constraint."""
        return self._set_status(
            constraint_id,
            ConstraintStatus.SATISFIED,
            resolved_by,
            notes,
            action="resolved",
            extra_sql=", satisfied_at = CURRENT_TIMESTAMP",
        )

    def ignore_constraint(
        self,
        constraint_id: int,
        ignored_by: str,
        reason: str,
    ) -> bool:
        """Waive a constraint (deliberately bypass)."""
        return self._set_status(
            constraint_id,
            ConstraintStatus.WAIVED,
            ignored_by,
            reason,
            action="waived",
            extra_sql=", bypass_strict_rule = 1, bypass_reason = ?",
            extra_params=(reason,),
        )

    @staticmethod
    def _required_actions(raw: Optional[str]) -> List[str]:
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError):
            return [raw]
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
        return [str(parsed)]

    def get_object_constraints(
        self,
        object_id: str,
        status: Optional[ConstraintStatus] = None,
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
                        'id': row['constraint_id'],
                        'constraint_id': row['constraint_id'],
                        'object_id': row['object_id'],
                        'constraint_type': row['constraint_type'],
                        'constraint_name': row['constraint_name'],
                        'description': row['description'],
                        'status': row['status'],
                        'required_for': self._required_actions(
                            row['required_for_actions']
                        ),
                        'required_for_actions': self._required_actions(
                            row['required_for_actions']
                        ),
                        'severity_level': row['severity_level'],
                        'deadline': row['deadline'],
                        'satisfied_at': row['satisfied_at'],
                        'bypass_strict_rule': row['bypass_strict_rule'],
                        'bypass_reason': row['bypass_reason'],
                        'created_at': row['created_at'],
                        'updated_at': row['updated_at'],
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

        blocking = [
            c for c in constraints
            if c['status'] == ConstraintStatus.NOT_SATISFIED.value
            and action in c['required_for']
        ]

        if not blocking:
            return {
                'can_proceed': True,
                'blocking_constraints': [],
                'message': f"All constraints resolved for {action}",
            }

        return {
            'can_proceed': False,
            'blocking_constraints': blocking,
            'message': (
                f"Cannot proceed with {action}: "
                f"{len(blocking)} blocking constraints"
            ),
        }

    def get_constraint_summary(self, object_id: str) -> Dict[str, Any]:
        """Get constraint summary for an object."""
        constraints = self.get_object_constraints(object_id)

        summary = {
            'total': len(constraints),
            'blocking': 0,
            'resolved': 0,
            'ignored': 0,
            'by_type': {},
            'blocking_by_type': {},
        }

        for constraint in constraints:
            c_type = constraint['constraint_type']
            summary['by_type'][c_type] = summary['by_type'].get(c_type, 0) + 1

            status = constraint['status']
            if status == ConstraintStatus.NOT_SATISFIED.value:
                summary['blocking'] += 1
                summary['blocking_by_type'][c_type] = (
                    summary['blocking_by_type'].get(c_type, 0) + 1
                )
            elif status == ConstraintStatus.SATISFIED.value:
                summary['resolved'] += 1
            elif status == ConstraintStatus.WAIVED.value:
                summary['ignored'] += 1

        return summary
