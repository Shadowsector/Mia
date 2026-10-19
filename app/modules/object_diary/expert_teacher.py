"""Expert Teacher - Interactive learning module for Living Ontology.

This module implements the Expert Teacher pattern for interactive learning
from user feedback, building a living ontology of construction domain knowledge.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path

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
                
                # Expert lessons table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS expert_lessons (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        lesson_type TEXT NOT NULL,
                        concept TEXT NOT NULL,
                        lesson_text TEXT NOT NULL,
                        source TEXT,
                        confidence REAL DEFAULT 0.5,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        verified_by TEXT,
                        is_active BOOLEAN DEFAULT TRUE
                    )
                """)
                
                # Ontology relations table
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
    
    def add_lesson(
        self,
        lesson_type: str,
        concept: str,
        lesson_text: str,
        source: str = "user",
        confidence: float = 0.5
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
                        lesson_type, concept, lesson_text, source, confidence
                    ) VALUES (?, ?, ?, ?, ?)
                """, (lesson_type, concept, lesson_text, source, confidence))
                
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
        confidence: float = 0.5
    ) -> int:
        """
        Add a relation between concepts.
        
        Args:
            concept_a: First concept
            relation_type: Type of relation (is_a, part_of, requires, etc.)
            concept_b: Second concept
            confidence: Confidence in the relation (0-1)
            
        Returns:
            Relation ID
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO ontology_relations (
                        concept_a, relation_type, concept_b, confidence
                    ) VALUES (?, ?, ?, ?)
                """, (concept_a, relation_type, concept_b, confidence))
                
                relation_id = cursor.lastrowid
                logger.info(f"Added relation {relation_id}: {concept_a} {relation_type} {concept_b}")
                return relation_id
                
        except Exception as e:
            logger.error(f"Error adding relation: {e}")
            return -1
    
    def get_lessons(self, concept: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get expert lessons.
        
        Args:
            concept: Filter by concept (optional)
            limit: Maximum number of lessons
            
        Returns:
            List of lessons
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                if concept:
                    cursor.execute("""
                        SELECT * FROM expert_lessons
                        WHERE concept = ? AND is_active = TRUE
                        ORDER BY created_at DESC
                        LIMIT ?
                    """, (concept, limit))
                else:
                    cursor.execute("""
                        SELECT * FROM expert_lessons
                        WHERE is_active = TRUE
                        ORDER BY created_at DESC
                        LIMIT ?
                    """, (limit,))
                
                lessons = []
                for row in cursor.fetchall():
                    lessons.append({
                        'id': row['id'],
                        'lesson_type': row['lesson_type'],
                        'concept': row['concept'],
                        'lesson_text': row['lesson_text'],
                        'source': row['source'],
                        'confidence': row['confidence'],
                        'created_at': row['created_at'],
                        'verified_by': row['verified_by']
                    })
                
                return lessons
                
        except Exception as e:
            logger.error(f"Error getting lessons: {e}")
            return []
    
    def get_relations(self, concept: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get ontology relations.
        
        Args:
            concept: Filter by concept (optional)
            
        Returns:
            List of relations
        """
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
                
                relations = []
                for row in cursor.fetchall():
                    relations.append({
                        'id': row['id'],
                        'concept_a': row['concept_a'],
                        'relation_type': row['relation_type'],
                        'concept_b': row['concept_b'],
                        'confidence': row['confidence'],
                        'created_at': row['created_at']
                    })
                
                return relations
                
        except Exception as e:
            logger.error(f"Error getting relations: {e}")
            return []
    
    def verify_lesson(self, lesson_id: int, verifier: str) -> bool:
        """
        Mark a lesson as verified by an expert.
        
        Args:
            lesson_id: Lesson ID
            verifier: Verifier identifier
            
        Returns:
            True if successful
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE expert_lessons
                    SET verified_by = ?, confidence = 1.0
                    WHERE id = ?
                """, (verifier, lesson_id))
                
                logger.info(f"Verified lesson {lesson_id} by {verifier}")
                return True
                
        except Exception as e:
            logger.error(f"Error verifying lesson: {e}")
            return False
    
    def get_ontology_graph(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get the complete ontology graph.
        
        Returns:
            Dictionary mapping concepts to their relations
        """
        relations = self.get_relations()
        
        graph = {}
        
        for relation in relations:
            concept_a = relation['concept_a']
            concept_b = relation['concept_b']
            
            if concept_a not in graph:
                graph[concept_a] = []
            
            graph[concept_a].append({
                'relation': relation['relation_type'],
                'target': concept_b,
                'confidence': relation['confidence']
            })
        
        return graph


if __name__ == "__main__":
    # Test Expert Teacher
    logging.basicConfig(level=logging.INFO)
    
    teacher = ExpertTeacher()
    
    # Add test lesson
    lesson_id = teacher.add_lesson(
        lesson_type="correction",
        concept="кабельная канализация",
        lesson_text="ККС должна быть заложена на глубине не менее 0.7 м для защиты от механических повреждений",
        source="expert_feedback",
        confidence=0.9
    )
    
    print(f"Added lesson {lesson_id}")
    
    # Add test relation
    relation_id = teacher.add_relation(
        concept_a="кабельная канализация",
        relation_type="part_of",
        concept_b="строительный объект",
        confidence=0.95
    )
    
    print(f"Added relation {relation_id}")
    
    # Get lessons
    lessons = teacher.get_lessons()
    print(f"Lessons: {len(lessons)}")
    
    # Get ontology graph
    graph = teacher.get_ontology_graph()
    print(f"Ontology graph: {graph}")
