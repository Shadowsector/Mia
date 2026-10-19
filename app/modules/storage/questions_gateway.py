"""Questions Gateway for human intervention with safety mechanisms"""

import re
import logging
import shutil
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List
from enum import Enum
import threading

from app.core.schemas import QuestionGatewaySchema, QuestionStatus, QuestionPriority
from app.modules.storage.database import get_db_connection

logger = logging.getLogger(__name__)


class QuestionsGateway:
    """
    Questions Gateway for human intervention in construction workflows.
    
    Prevents local Qwen deadlocks at logical impasses by providing
    structured human intervention through QUESTIONS.md and Telegram.
    """
    
    def __init__(self, project_root: Path):
        """
        Initialize Questions Gateway.
        
        Args:
            project_root: Root directory where QUESTIONS.md will be created
        """
        self.project_root = project_root
        self.questions_file = project_root / "QUESTIONS.md"
        self._lock = threading.Lock()
        
        # Safety configuration
        self.min_mtime_stability_seconds = 2
        self.shadow_copy_enabled = True
        self.integrity_check_enabled = True
        
        # Markdown block regex patterns for integrity validation
        self.block_patterns = {
            'question_header': r'^# [A-Z].+$',
            'options_section': r'^## Options:$',
            'option_a': r'^\*\*\(a\)\*\* .+$',
            'option_b': r'^\*\*\(b\)\*\* .+$',
            'option_c': r'^\*\*\(c\)\*\* .+$',
            'metadata': r'^---$'
        }
        
        logger.info(f"Questions Gateway initialized at {self.questions_file}")
    
    def ask_human(self, question_data: Dict[str, Any]) -> str:
        """
        Create a human intervention question.
        
        Args:
            question_data: Question data matching QuestionGatewaySchema
            
        Returns:
            Question ID
        """
        question_id = question_data.get('question_id', f"Q-{datetime.now().strftime('%Y%m%d%H%M%S')}")
        
        # Validate question data
        schema = QuestionGatewaySchema(**question_data)
        
        # Create shadow copy for safe reading
        shadow_path = self._create_shadow_copy()
        question_data['shadow_file_path'] = str(shadow_path)
        
        # Record file mtime for stability check
        if shadow_path.exists():
            question_data['file_mtime'] = datetime.fromtimestamp(shadow_path.stat().st_mtime)
        
        # Validate block integrity
        integrity_ok = self._validate_block_integrity(question_data['question_markdown'])
        question_data['integrity_regex_match'] = integrity_ok
        
        if not integrity_ok:
            logger.warning(f"Question {question_id} failed integrity validation")
            question_data['status'] = QuestionStatus.INVALID
        else:
            question_data['status'] = QuestionStatus.OPEN
        
        # Re-create schema with updated status
        schema = QuestionGatewaySchema(**question_data)
        
        # Add to QUESTIONS.md (only if valid)
        if integrity_ok:
            self._append_to_questions_md(schema)
        
        # Persist to database
        self._persist_question(schema)
        
        # Suspend related task if specified
        if schema.suspended_task_id:
            self._suspend_task(schema.suspended_task_id, question_id)
        
        logger.info(f"Question {question_id} created with status {schema.status}")
        return question_id
    
    def answer_question(self, question_id: str, answer: str, user_id: str, 
                       notes: Optional[str] = None) -> bool:
        """
        Answer a question with human input.
        
        Args:
            question_id: Question ID to answer
            answer: Chosen option ('a', 'b', or 'c')
            user_id: Telegram user ID who answered
            notes: Additional resolution notes
            
        Returns:
            True if answer accepted, False if rejected
        """
        with self._lock:
            # Verify file stability
            if not self._verify_file_stability():
                logger.warning(f"File stability check failed for question {question_id}")
                return False
            
            # Get question from database
            question = self._get_question(question_id)
            if not question:
                logger.error(f"Question {question_id} not found")
                return False
            
            # Validate answer
            if answer not in ['a', 'b', 'c']:
                logger.error(f"Invalid answer {answer} for question {question_id}")
                return False
            
            # Check if option C exists
            if answer == 'c' and not question.get('option_c'):
                logger.error(f"Option C not available for question {question_id}")
                return False
            
            # Update question status
            success = self._update_question_status(
                question_id, 
                QuestionStatus.ANSWERED,
                resolved_by=user_id,
                resolved_option=answer,
                resolution_notes=notes
            )
            
            if success:
                # Resume suspended task
                if question.get('suspended_task_id'):
                    self._resume_task(question['suspended_task_id'], question_id, answer)
                
                # Update QUESTIONS.md
                self._mark_question_answered(question_id, answer, user_id)
                
                logger.info(f"Question {question_id} answered with option {answer}")
            
            return success
    
    def _create_shadow_copy(self) -> Path:
        """Create a shadow copy of QUESTIONS.md for safe reading."""
        if not self.shadow_copy_enabled:
            return self.questions_file
        
        shadow_path = self.questions_file.with_suffix('.md.shadow')
        
        try:
            if self.questions_file.exists():
                shutil.copy2(self.questions_file, shadow_path)
            else:
                # Create empty shadow file
                shadow_path.touch()
            
            logger.debug(f"Shadow copy created at {shadow_path}")
            return shadow_path
            
        except Exception as e:
            logger.error(f"Failed to create shadow copy: {e}")
            return self.questions_file
    
    def _verify_file_stability(self) -> bool:
        """Verify file has been stable for at least min_mtime_stability_seconds."""
        if not self.questions_file.exists():
            return True
        
        mtime = self.questions_file.stat().st_mtime
        current_time = datetime.now().timestamp()
        age_seconds = current_time - mtime
        
        if age_seconds < self.min_mtime_stability_seconds:
            logger.warning(f"File too recent ({age_seconds:.1f}s < {self.min_mtime_stability_seconds}s)")
            return False
        
        return True
    
    def _validate_block_integrity(self, markdown: str) -> bool:
        """Validate markdown block structure using regex patterns."""
        if not self.integrity_check_enabled:
            return True
        
        required_patterns = [
            self.block_patterns['question_header'],
            self.block_patterns['options_section'],
            self.block_patterns['option_a'],
            self.block_patterns['option_b']
        ]
        
        lines = markdown.split('\n')
        for pattern in required_patterns:
            if not any(re.match(pattern, line) for line in lines):
                logger.warning(f"Missing required pattern: {pattern}")
                return False
        
        return True
    
    def _append_to_questions_md(self, question: QuestionGatewaySchema):
        """Append question to QUESTIONS.md file."""
        try:
            # Create file if it doesn't exist
            if not self.questions_file.exists():
                self.questions_file.write_text("# QUESTIONS Gateway\n\nQuestions requiring human intervention.\n\n")
            
            # Append question block
            with open(self.questions_file, 'a', encoding='utf-8') as f:
                f.write(f"## Question: {question.question_id}\n\n")
                f.write(f"**Type:** {question.question_type}\n")
                f.write(f"**Priority:** {question.priority.value}\n")
                f.write(f"**Project:** {question.project_id}\n")
                f.write(f"**Schema:** {question.related_schema_type}\n\n")
                f.write(f"{question.question_markdown}\n\n")
                f.write(f"**Status:** {question.status.value}\n")
                f.write(f"**Created:** {question.created_at.isoformat()}\n")
                f.write("---\n\n")
            
            logger.debug(f"Question {question.question_id} appended to QUESTIONS.md")
            
        except Exception as e:
            logger.error(f"Failed to append to QUESTIONS.md: {e}")
    
    def _mark_question_answered(self, question_id: str, answer: str, user_id: str):
        """Mark question as answered in QUESTIONS.md."""
        try:
            with open(self.questions_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Simple replacement (in production, use more sophisticated parsing)
            status_marker = f"**Status:** {QuestionStatus.OPEN.value}"
            answered_marker = f"**Status:** {QuestionStatus.ANSWERED.value} (answered by {user_id} with option {answer})"
            
            # Replace only for this specific question
            content = content.replace(
                f"## Question: {question_id}\n\n",
                f"## Question: {question_id} (ANSWERED)\n\n"
            )
            
            content = content.replace(status_marker, answered_marker)
            
            with open(self.questions_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logger.debug(f"Question {question_id} marked as answered in QUESTIONS.md")
            
        except Exception as e:
            logger.error(f"Failed to mark question as answered: {e}")
    
    def _persist_question(self, question: QuestionGatewaySchema) -> bool:
        """Persist question to database."""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO questions_gateway (
                        question_id, question_type, status, priority,
                        project_id, related_schema_type, related_entity_id,
                        question_markdown, option_a, option_b, option_c,
                        suspended_task_id, suspended_task_type,
                        shadow_file_path, file_mtime, integrity_regex_match,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    question.question_id,
                    question.question_type,
                    question.status.value,
                    question.priority.value,
                    question.project_id,
                    question.related_schema_type,
                    question.related_entity_id,
                    question.question_markdown,
                    question.option_a,
                    question.option_b,
                    question.option_c,
                    question.suspended_task_id,
                    question.suspended_task_type,
                    question.shadow_file_path,
                    question.file_mtime.isoformat() if question.file_mtime else None,
                    question.integrity_regex_match,
                    question.created_at.isoformat()
                ))
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to persist question: {e}")
            return False
    
    def _get_question(self, question_id: str) -> Optional[Dict[str, Any]]:
        """Get question from database."""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM questions_gateway WHERE question_id = ?
                """, (question_id,))
                row = cursor.fetchone()
                if row:
                    return dict(row)
                return None
                
        except Exception as e:
            logger.error(f"Failed to get question: {e}")
            return None
    
    def _update_question_status(self, question_id: str, status: QuestionStatus,
                                 resolved_by: Optional[str] = None,
                                 resolved_option: Optional[str] = None,
                                 resolution_notes: Optional[str] = None) -> bool:
        """Update question status in database."""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE questions_gateway 
                    SET status = ?, resolved_by = ?, resolved_option = ?, 
                        resolution_notes = ?, answered_at = CURRENT_TIMESTAMP
                    WHERE question_id = ?
                """, (
                    status.value,
                    resolved_by,
                    resolved_option,
                    resolution_notes,
                    question_id
                ))
                
            return True
            
        except Exception as e:
            logger.error(f"Failed to update question status: {e}")
            return False
    
    def _suspend_task(self, task_id: str, question_id: str):
        """Suspend a task while waiting for human answer."""
        try:
            from app.modules.storage.database import update_task_status
            update_task_status(task_id, 'waiting_human')
            logger.info(f"Task {task_id} suspended for question {question_id}")
            
        except Exception as e:
            logger.error(f"Failed to suspend task: {e}")
    
    def _resume_task(self, task_id: str, question_id: str, answer: str):
        """Resume a task after human answer."""
        try:
            from app.modules.storage.database import update_task_status
            update_task_status(
                task_id, 
                'pending',
                result=f"Human answered question {question_id} with option {answer}"
            )
            logger.info(f"Task {task_id} resumed after question {question_id} answered")
            
        except Exception as e:
            logger.error(f"Failed to resume task: {e}")
    
    def get_open_questions(self, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all open questions, optionally filtered by project."""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                if project_id:
                    cursor.execute("""
                        SELECT * FROM questions_gateway 
                        WHERE status = 'open' AND project_id = ?
                        ORDER BY priority DESC, created_at ASC
                    """, (project_id,))
                else:
                    cursor.execute("""
                        SELECT * FROM questions_gateway 
                        WHERE status = 'open'
                        ORDER BY priority DESC, created_at ASC
                    """)
                
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            logger.error(f"Failed to get open questions: {e}")
            return []
    
    def cleanup_shadow_copies(self):
        """Clean up shadow copy files."""
        try:
            shadow_file = self.questions_file.with_suffix('.md.shadow')
            if shadow_file.exists():
                shadow_file.unlink()
                logger.debug("Shadow copy cleaned up")
                
        except Exception as e:
            logger.error(f"Failed to cleanup shadow copy: {e}")


def initialize_questions_database():
    """Initialize questions gateway table in database."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS questions_gateway (
                    question_id TEXT PRIMARY KEY,
                    question_type TEXT NOT NULL,
                    status TEXT DEFAULT 'open',
                    priority TEXT DEFAULT 'normal',
                    project_id TEXT NOT NULL,
                    related_schema_type TEXT NOT NULL,
                    related_entity_id TEXT NOT NULL,
                    question_markdown TEXT NOT NULL,
                    option_a TEXT NOT NULL,
                    option_b TEXT NOT NULL,
                    option_c TEXT,
                    suspended_task_id TEXT,
                    suspended_task_type TEXT,
                    shadow_file_path TEXT,
                    file_mtime TEXT,
                    integrity_regex_match BOOLEAN DEFAULT 1,
                    resolved_by TEXT,
                    resolved_option TEXT,
                    resolution_notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    answered_at TIMESTAMP
                )
            """)
            
            # Create indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_questions_status 
                ON questions_gateway(status, priority)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_questions_project 
                ON questions_gateway(project_id)
            """)
            
        logger.info("Questions gateway database initialized")
        
    except Exception as e:
        logger.error(f"Failed to initialize questions database: {e}")


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)
    
    # Initialize database
    initialize_questions_database()
    
    # Create gateway
    gateway = QuestionsGateway(Path(__file__).parent.parent.parent)
    
    # Ask a question
    question_data = {
        "question_id": "Q-TEST-001",
        "question_type": "budget_conflict",
        "priority": "critical",
        "project_id": "PROJ-2024-001",
        "related_schema_type": "FinancialReportSchema",
        "related_entity_id": "FIN-2024-0892",
        "question_markdown": "# Budget Conflict\n\nKS-2 shows 500k but schema shows 450k.\n\n## Options:\n**(a)** Use KS-2 amount\n**(b)** Use schema amount",
        "option_a": "Use KS-2 amount (500,000 RUB)",
        "option_b": "Use schema amount (450,000 RUB)",
        "suspended_task_id": "TASK-2024-1234"
    }
    
    question_id = gateway.ask_human(question_data)
    print(f"Created question: {question_id}")
    
    # Clean up
    gateway.cleanup_shadow_copies()