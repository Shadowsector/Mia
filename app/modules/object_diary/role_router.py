"""Role Router - Address-based Human-in-the-loop routing.

This module implements intelligent routing for human-in-the-loop cases,
routing questions to the appropriate person based on role and expertise.
"""

import logging
from typing import Dict, List, Any, Optional
from enum import Enum

from app.modules.storage.database import get_db_connection

logger = logging.getLogger(__name__)


class Role(str, Enum):
    """Roles in the organization."""
    FINANCE = "finance"
    TECHNICAL = "technical"
    LEGAL = "legal"
    PROJECT_MANAGER = "project_manager"
    EXECUTIVE = "executive"


class RoleRouter:
    """
    Intelligent router for human-in-the-loop cases.
    
    Routes questions and verification requests to the appropriate person
    based on their role, expertise, and availability.
    """
    
    def __init__(self):
        """Initialize Role Router."""
        self._ensure_tables()
    
    def _ensure_tables(self):
        """Create necessary database tables."""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Role routing table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS role_routing (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        question_id TEXT NOT NULL,
                        question_type TEXT NOT NULL,
                        urgency TEXT DEFAULT 'normal',
                        assigned_role TEXT NOT NULL,
                        assigned_to TEXT,
                        assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        answered_at TIMESTAMP,
                        answer TEXT,
                        confidence REAL DEFAULT 0.5,
                        metadata TEXT DEFAULT '{}'
                    )
                """)
                
                logger.info("Role Router tables initialized")
                
        except Exception as e:
            logger.error(f"Error creating Role Router tables: {e}")
    
    def route_question(
        self,
        question_id: str,
        question_type: str,
        question_text: str,
        urgency: str = "normal"
    ) -> Dict[str, Any]:
        """
        Route a question to the appropriate role.
        
        Args:
            question_id: Question ID
            question_type: Type of question
            question_text: Question text
            urgency: Urgency level
            
        Returns:
            Routing result
        """
        # Determine appropriate role based on question type
        role_mapping = {
            'financial': Role.FINANCE,
            'budget': Role.FINANCE,
            'payment': Role.FINANCE,
            'technical': Role.TECHNICAL,
            'specification': Role.TECHNICAL,
            'legal': Role.LEGAL,
            'permit': Role.LEGAL,
            'contract': Role.LEGAL,
            'schedule': Role.PROJECT_MANAGER,
            'deadline': Role.PROJECT_MANAGER,
            'approval': Role.EXECUTIVE
        }
        
        # Check for keywords in question text
        question_lower = question_text.lower()
        
        assigned_role = Role.PROJECT_MANAGER  # Default
        
        for keyword, role in role_mapping.items():
            if keyword in question_lower:
                assigned_role = role
                break
        
        # Assign to a person with that role
        assigned_to = self._find_person_by_role(assigned_role.value)
        
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO role_routing (
                        question_id, question_type, urgency, assigned_role, assigned_to
                    ) VALUES (?, ?, ?, ?, ?)
                """, (question_id, question_type, urgency, assigned_role.value, assigned_to))
                
                routing_id = cursor.lastrowid
                logger.info(f"Routed question {question_id} to {assigned_role} ({assigned_to})")
                
                return {
                    'success': True,
                    'routing_id': routing_id,
                    'assigned_role': assigned_role.value,
                    'assigned_to': assigned_to
                }
                
        except Exception as e:
            logger.error(f"Error routing question: {e}")
            return {'success': False, 'error': str(e)}
    
    def _find_person_by_role(self, role: str) -> str:
        """Find a person with the specified role."""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT username FROM employees
                    WHERE role = ? AND active = TRUE
                    LIMIT 1
                """, (role,))
                
                row = cursor.fetchone()
                return row['username'] if row else "unassigned"
                
        except Exception as e:
            logger.error(f"Error finding person by role: {e}")
            return "unassigned"
    
    def get_routing_for_question(self, question_id: str) -> Optional[Dict[str, Any]]:
        """Get routing information for a question."""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM role_routing
                    WHERE question_id = ?
                """, (question_id,))
                
                row = cursor.fetchone()
                if row:
                    return {
                        'id': row['id'],
                        'question_id': row['question_id'],
                        'question_type': row['question_type'],
                        'urgency': row['urgency'],
                        'assigned_role': row['assigned_role'],
                        'assigned_to': row['assigned_to'],
                        'assigned_at': row['assigned_at'],
                        'answered_at': row['answered_at'],
                        'answer': row['answer'],
                        'confidence': row['confidence']
                    }
                
                return None
                
        except Exception as e:
            logger.error(f"Error getting routing: {e}")
            return None


if __name__ == "__main__":
    # Test Role Router
    logging.basicConfig(level=logging.INFO)
    
    router = RoleRouter()
    
    # Test routing
    result = router.route_question(
        question_id="Q-001",
        question_type="budget",
        question_text="Need approval for budget increase",
        urgency="high"
    )
    
    print(f"Routing result: {result}")
