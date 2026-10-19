"""Expert Teacher - Interactive learning module for Living Ontology.

This module implements the Expert Teacher pattern for interactive learning
from user feedback, building a living ontology of construction domain knowledge.

Storage schema (see app/modules/storage/database.py):
    expert_lessons(
        lesson_id, doc_category, context_tags, raw_page_text,
        anchor_text_embedding_id, expert_commentary, applicability_scope,
        created_at, verified_by_human
    )
    ontology_relations(id, concept_a, relation_type, concept_b,
                       confidence, created_at)
"""

import json
import logging
from typing import Any, Dict, List, Optional

from app.modules.storage.database import get_db_connection

logger = logging.getLogger(__name__)


class ExpertTeacher:
    """
    Expert Teacher for interactive learning.

    Maintains a living ontology of construction domain knowledge
    through user feedback and expert lessons.
    """

    def __init__(self):
        """Initialize Expert Teacher."""
        self._ensure_tables()

    def _ensure_tables(self):
        """Create necessary database tables."""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS expert_lessons (
                        lesson_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        doc_category TEXT NOT NULL,
                        context_tags TEXT DEFAULT '[]',
                        raw_page_text TEXT NOT NULL,
                        anchor_text_embedding_id TEXT NOT NULL,
                        expert_commentary TEXT NOT NULL,
                        applicability_scope TEXT DEFAULT '{}',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        verified_by_human BOOLEAN DEFAULT 0
                    )
                """)

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS ontology_relations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        concept_a TEXT NOT NULL,
                        relation_type TEXT NOT NULL,
                        concept_b TEXT NOT NULL,
                        confidence REAL DEFAULT 0.5,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                logger.info("Expert Teacher tables initialized")

        except Exception as e:
            logger.error(f"Error creating Expert Teacher tables: {e}")

    @staticmethod
    def _scope(confidence: float, source: str) -> str:
        return json.dumps({"confidence": confidence, "source": source})

    @staticmethod
    def _read_scope(raw: Optional[str]) -> Dict[str, Any]:
        try:
            parsed = json.loads(raw) if raw else {}
        except (TypeError, ValueError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def add_lesson(
        self,
        lesson_type: str,
        concept: str,
        lesson_text: str,
        source: str = "user",
        confidence: float = 0.5,
    ) -> int:
        """
        Add a new expert lesson.

        Args:
            lesson_type: Type of lesson (correction, new_concept, relation)
            concept: Main concept involved
            lesson_text: Lesson content
            source: Source of the lesson
            confidence: Confidence in the lesson (0-1)

        Returns:
            Lesson ID
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO expert_lessons (
                        doc_category, context_tags, raw_page_text,
                        anchor_text_embedding_id, expert_commentary,
                        applicability_scope
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    lesson_type,
                    json.dumps([concept], ensure_ascii=False),
                    lesson_text,
                    source,
                    lesson_text,
                    self._scope(confidence, source),
                ))

                lesson_id = cursor.lastrowid
                logger.info(f"Added lesson {lesson_id}: {concept} - {lesson_type}")
                return lesson_id

        except Exception as e:
            logger.error(f"Error adding lesson: {e}")
            return -1

    def add_relation(
        self,
        concept_a: str,
        relation_type: str,
        concept_b: str,
        confidence: float = 0.5,
    ) -> int:
        """Add a relation between concepts."""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO ontology_relations (
                        concept_a, relation_type, concept_b, confidence
                    ) VALUES (?, ?, ?, ?)
                """, (concept_a, relation_type, concept_b, confidence))

                relation_id = cursor.lastrowid
                logger.info(
                    f"Added relation {relation_id}: "
                    f"{concept_a} {relation_type} {concept_b}"
                )
                return relation_id

        except Exception as e:
            logger.error(f"Error adding relation: {e}")
            return -1

    @staticmethod
    def _row_to_lesson(row) -> Dict[str, Any]:
        scope = ExpertTeacher._read_scope(row['applicability_scope'])
        try:
            tags = json.loads(row['context_tags']) if row['context_tags'] else []
        except (TypeError, ValueError):
            tags = []
        return {
            'id': row['lesson_id'],
            'lesson_id': row['lesson_id'],
            'lesson_type': row['doc_category'],
            'concept': tags[0] if tags else None,
            'lesson_text': row['raw_page_text'],
            'source': row['anchor_text_embedding_id'],
            'confidence': scope.get('confidence', 1.0 if row['verified_by_human'] else 0.5),
            'verified_by': 'human' if row['verified_by_human'] else None,
            'created_at': row['created_at'],
        }

    def get_lessons(
        self,
        concept: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get expert lessons, optionally filtered by concept."""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()

                if concept:
                    # context_tags stores a JSON list; match the serialized concept
                    cursor.execute("""
                        SELECT * FROM expert_lessons
                        WHERE context_tags LIKE ?
                        ORDER BY created_at DESC
                        LIMIT ?
                    """, (f'%"{concept}"%', limit))
                else:
                    cursor.execute("""
                        SELECT * FROM expert_lessons
                        ORDER BY created_at DESC
                        LIMIT ?
                    """, (limit,))

                return [self._row_to_lesson(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Error getting lessons: {e}")
            return []

    def get_relations(self, concept: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get ontology relations."""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()

                if concept:
                    cursor.execute("""
                        SELECT * FROM ontology_relations
                        WHERE concept_a = ? OR concept_b = ?
                        ORDER BY confidence DESC
                    """, (concept, concept))
                else:
                    cursor.execute("""
                        SELECT * FROM ontology_relations
                        ORDER BY confidence DESC
                    """)

                return [
                    {
                        'id': row['id'],
                        'concept_a': row['concept_a'],
                        'relation_type': row['relation_type'],
                        'concept_b': row['concept_b'],
                        'confidence': row['confidence'],
                        'created_at': row['created_at'],
                    }
                    for row in cursor.fetchall()
                ]

        except Exception as e:
            logger.error(f"Error getting relations: {e}")
            return []

    def verify_lesson(self, lesson_id: int, verifier: str) -> bool:
        """Mark a lesson as verified by an expert."""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT applicability_scope FROM expert_lessons
                    WHERE lesson_id = ?
                """, (lesson_id,))
                row = cursor.fetchone()
                if not row:
                    return False

                scope = self._read_scope(row['applicability_scope'])
                scope['confidence'] = 1.0
                scope['verified_by'] = verifier

                cursor.execute("""
                    UPDATE expert_lessons
                    SET verified_by_human = 1, applicability_scope = ?
                    WHERE lesson_id = ?
                """, (json.dumps(scope, ensure_ascii=False), lesson_id))

                logger.info(f"Verified lesson {lesson_id} by {verifier}")
                return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"Error verifying lesson: {e}")
            return False

    def get_ontology_graph(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get the complete ontology graph."""
        graph: Dict[str, List[Dict[str, Any]]] = {}

        for relation in self.get_relations():
            graph.setdefault(relation['concept_a'], []).append({
                'relation': relation['relation_type'],
                'target': relation['concept_b'],
                'confidence': relation['confidence'],
            })

        return graph
