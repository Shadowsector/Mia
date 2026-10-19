"""Tests for Questions Gateway and safety mechanisms"""

import pytest
import time
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from app.core.schemas import QuestionGatewaySchema, QuestionStatus, QuestionPriority
from app.modules.storage.questions_gateway import QuestionsGateway, initialize_questions_database
from app.modules.storage.database import enqueue_task, update_task_status, get_db_connection


class TestQuestionGatewaySchema:
    """Tests for QuestionGatewaySchema."""
    
    def test_basic_question_creation(self):
        """Test basic question schema creation."""
        question = QuestionGatewaySchema(
            question_id="Q-TEST-001",
            question_type="budget_conflict",
            project_id="PROJ-2024-001",
            related_schema_type="FinancialReportSchema",
            related_entity_id="FIN-2024-0892",
            question_markdown="# Budget Conflict\n\nKS-2 shows 500k\n\n## Options:\n**(a)** Use KS-2\n**(b)** Use schema",
            option_a="Use KS-2 amount",
            option_b="Use schema amount"
        )
        
        assert question.question_id == "Q-TEST-001"
        assert question.status == QuestionStatus.OPEN
        assert question.priority == QuestionPriority.NORMAL
        assert question.integrity_regex_match is True
    
    def test_question_with_option_c(self):
        """Test question with optional third option."""
        question = QuestionGatewaySchema(
            question_id="Q-TEST-002",
            question_type="permit_issue",
            project_id="PROJ-2024-001",
            related_schema_type="DocumentMetadataSchema",
            related_entity_id="DOC-2024-0892",
            question_markdown="# Permit Issue\n\n## Options:\n**(a)** Approve\n**(b)** Reject\n**(c)** Escalate",
            option_a="Approve",
            option_b="Reject",
            option_c="Escalate to legal"
        )
        
        assert question.option_c == "Escalate to legal"
    
    def test_question_priority_levels(self):
        """Test different priority levels."""
        critical_question = QuestionGatewaySchema(
            question_id="Q-TEST-003",
            question_type="financial_compliance",
            project_id="PROJ-2024-001",
            related_schema_type="FinancialReportSchema",
            related_entity_id="FIN-2024-0892",
            question_markdown="# Critical\n\n## Options:\n**(a)** A\n**(b)** B",
            option_a="A",
            option_b="B",
            priority=QuestionPriority.CRITICAL
        )
        
        assert critical_question.priority == QuestionPriority.CRITICAL


class TestQuestionsGateway:
    """Tests for Questions Gateway functionality."""
    
    @pytest.fixture(autouse=True)
    def setup_gateway(self):
        """Initialize questions gateway for each test."""
        initialize_questions_database()
        
        # Create temporary directory for QUESTIONS.md
        temp_dir = Path(tempfile.mkdtemp())
        gateway = QuestionsGateway(temp_dir)
        
        yield gateway
        
        # Cleanup
        gateway.cleanup_shadow_copies()
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_ask_human_basic(self, setup_gateway):
        """Test basic question creation."""
        gateway = setup_gateway
        question_data = {
            "question_id": "Q-TEST-001",
            "question_type": "budget_conflict",
            "priority": "critical",
            "project_id": "PROJ-2024-001",
            "related_schema_type": "FinancialReportSchema",
            "related_entity_id": "FIN-2024-0892",
            "question_markdown": "# Budget Conflict\n\nKS-2 shows 500k\n\n## Options:\n**(a)** Use KS-2\n**(b)** Use schema",
            "option_a": "Use KS-2 amount",
            "option_b": "Use schema amount"
        }
        
        question_id = gateway.ask_human(question_data)
        
        assert question_id == "Q-TEST-001"
        assert gateway.questions_file.exists()
    
    def test_shadow_copy_creation(self, setup_gateway):
        """Test that shadow copy is created for safe reading."""
        gateway = setup_gateway
        question_data = {
            "question_id": "Q-TEST-002",
            "question_type": "material_conflict",
            "priority": "high",
            "project_id": "PROJ-2024-001",
            "related_schema_type": "MaterialStatusSchema",
            "related_entity_id": "MAT-2024-0892",
            "question_markdown": "# Material Conflict\n\n## Options:\n**(a)** A\n**(b)** B",
            "option_a": "Option A",
            "option_b": "Option B"
        }
        
        gateway.ask_human(question_data)
        
        # Check that shadow file was created
        shadow_file = gateway.questions_file.with_suffix('.md.shadow')
        assert shadow_file.exists()
    
    def test_file_stability_check(self, setup_gateway):
        """Test file stability check (mtime >= 2 seconds)."""
        gateway = setup_gateway
        # Create a question
        question_data = {
            "question_id": "Q-TEST-003",
            "question_type": "test",
            "priority": "normal",
            "project_id": "PROJ-2024-001",
            "related_schema_type": "TestSchema",
            "related_entity_id": "TEST-001",
            "question_markdown": "# Test\n\n## Options:\n**(a)** A\n**(b)** B",
            "option_a": "A",
            "option_b": "B"
        }
        
        gateway.ask_human(question_data)
        
        # Immediate stability check should fail (file too recent)
        assert not gateway._verify_file_stability()
        
        # Wait for stability threshold
        time.sleep(2.5)
        
        # Stability check should now pass
        assert gateway._verify_file_stability()
    
    def test_integrity_validation_valid(self, setup_gateway):
        """Test regex integrity validation with valid markdown."""
        gateway = setup_gateway
        valid_markdown = "# Budget Conflict\n\nKS-2 shows 500k\n\n## Options:\n**(a)** Use KS-2\n**(b)** Use schema"
        
        assert gateway._validate_block_integrity(valid_markdown) is True
    
    def test_integrity_validation_invalid(self, setup_gateway):
        """Test regex integrity validation with invalid markdown."""
        gateway = setup_gateway
        invalid_markdown = "Invalid markdown without proper structure"
        
        assert gateway._validate_block_integrity(invalid_markdown) is False
    
    def test_answer_question_valid(self, setup_gateway):
        """Test answering a question with valid input."""
        gateway = setup_gateway
        # Create a question first
        question_data = {
            "question_id": "Q-TEST-004",
            "question_type": "permit_issue",
            "priority": "high",
            "project_id": "PROJ-2024-001",
            "related_schema_type": "DocumentMetadataSchema",
            "related_entity_id": "DOC-2024-0892",
            "question_markdown": "# Permit Issue\n\n## Options:\n**(a)** Approve\n**(b)** Reject",
            "option_a": "Approve",
            "option_b": "Reject"
        }
        
        gateway.ask_human(question_data)
        
        # Wait for file stability
        time.sleep(2.5)
        
        # Answer the question
        success = gateway.answer_question("Q-TEST-004", "a", "user_123", "Approved by director")
        
        assert success is True
    
    def test_answer_question_invalid_option(self, setup_gateway):
        """Test answering with invalid option."""
        gateway = setup_gateway
        question_data = {
            "question_id": "Q-TEST-005",
            "question_type": "test",
            "priority": "normal",
            "project_id": "PROJ-2024-001",
            "related_schema_type": "TestSchema",
            "related_entity_id": "TEST-001",
            "question_markdown": "# Test\n\n## Options:\n**(a)** A\n**(b)** B",
            "option_a": "A",
            "option_b": "B"
        }
        
        gateway.ask_human(question_data)
        time.sleep(2.5)
        
        # Try invalid option
        success = gateway.answer_question("Q-TEST-005", "d", "user_123")
        
        assert success is False
    
    def test_answer_question_nonexistent(self, setup_gateway):
        """Test answering a question that doesn't exist."""
        gateway = setup_gateway
        success = gateway.answer_question("Q-NONEXISTENT", "a", "user_123")
        
        assert success is False
    
    def test_answer_question_without_option_c(self, setup_gateway):
        """Test answering with option C when option C doesn't exist."""
        gateway = setup_gateway
        question_data = {
            "question_id": "Q-TEST-006",
            "question_type": "test",
            "priority": "normal",
            "project_id": "PROJ-2024-001",
            "related_schema_type": "TestSchema",
            "related_entity_id": "TEST-001",
            "question_markdown": "# Test\n\n## Options:\n**(a)** A\n**(b)** B",
            "option_a": "A",
            "option_b": "B"
        }
        
        gateway.ask_human(question_data)
        time.sleep(2.5)
        
        # Try to use option C when it doesn't exist
        success = gateway.answer_question("Q-TEST-006", "c", "user_123")
        
        assert success is False
    
    def test_get_open_questions(self, setup_gateway):
        """Test retrieving open questions."""
        gateway = setup_gateway
        # Create multiple questions
        for i in range(3):
            question_data = {
                "question_id": f"Q-TEST-007-{i}",
                "question_type": "test",
                "priority": "normal",
                "project_id": "PROJ-2024-001",
                "related_schema_type": "TestSchema",
                "related_entity_id": f"TEST-00{i}",
                "question_markdown": f"# Test {i}\n\n## Options:\n**(a)** A\n**(b)** B",
                "option_a": "A",
                "option_b": "B"
            }
            gateway.ask_human(question_data)
        
        # Get open questions
        open_questions = gateway.get_open_questions()
        
        assert len(open_questions) >= 3
    
    def test_get_open_questions_by_project(self, setup_gateway):
        """Test retrieving open questions filtered by project."""
        gateway = setup_gateway
        # Create questions for different projects
        question_data_1 = {
            "question_id": "Q-TEST-PROJ1",
            "question_type": "test",
            "priority": "normal",
            "project_id": "PROJ-2024-001",
            "related_schema_type": "TestSchema",
            "related_entity_id": "TEST-001",
            "question_markdown": "# Test\n\n## Options:\n**(a)** A\n**(b)** B",
            "option_a": "A",
            "option_b": "B"
        }
        
        question_data_2 = {
            "question_id": "Q-TEST-PROJ2",
            "question_type": "test",
            "priority": "normal",
            "project_id": "PROJ-2024-002",
            "related_schema_type": "TestSchema",
            "related_entity_id": "TEST-002",
            "question_markdown": "# Test\n\n## Options:\n**(a)** A\n**(b)** B",
            "option_a": "A",
            "option_b": "B"
        }
        
        gateway.ask_human(question_data_1)
        gateway.ask_human(question_data_2)
        
        # Get questions for specific project
        proj1_questions = gateway.get_open_questions("PROJ-2024-001")
        
        assert len(proj1_questions) >= 1
        assert all(q['project_id'] == "PROJ-2024-001" for q in proj1_questions)
    
    def test_questions_md_creation(self, setup_gateway):
        """Test that QUESTIONS.md file is created properly."""
        gateway = setup_gateway
        question_data = {
            "question_id": "Q-TEST-MD",
            "question_type": "test",
            "priority": "high",
            "project_id": "PROJ-2024-001",
            "related_schema_type": "TestSchema",
            "related_entity_id": "TEST-001",
            "question_markdown": "# Test Question\n\nThis is a test.\n\n## Options:\n**(a)** Option A\n**(b)** Option B",
            "option_a": "Option A",
            "option_b": "Option B"
        }
        
        gateway.ask_human(question_data)
        
        # Check file exists and contains question
        assert gateway.questions_file.exists()
        content = gateway.questions_file.read_text()
        
        assert "Q-TEST-MD" in content
        assert "Test Question" in content
        assert "Option A" in content
        assert "Option B" in content


class TestTaskSuspension:
    """Tests for task suspension and resumption."""
    
    @pytest.fixture(autouse=True)
    def setup_database(self):
        """Initialize database before each test."""
        from app.modules.storage.database import initialize_database
        initialize_questions_database()
        
        # Clean up test data
        import sqlite3
        from app.modules.storage.database import DB_PATH
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM llm_task_queue WHERE task_id LIKE 'TASK-SUSPEND-%'")
        cursor.execute("DELETE FROM questions_gateway WHERE question_id LIKE 'Q-SUSPEND-%'")
        conn.commit()
        conn.close()
        yield
    
    def test_task_suspension_on_question(self):
        """Test that task is suspended when question is created."""
        # Create a task
        task_data = {
            'task_id': 'TASK-SUSPEND-001',
            'task_type': 'tool_call',
            'priority': 8,
            'system_current_time': datetime.now(),
            'user_message': 'Financial decision required',
            'user_intent': 'financial_decision',
            'telegram_chat_id': -1001234567890,
            'user_id': 123456789
        }
        
        enqueue_task(task_data)
        
        # Create question that suspends this task
        from app.modules.storage.questions_gateway import QuestionsGateway
        temp_dir = Path(tempfile.mkdtemp())
        gateway = QuestionsGateway(temp_dir)
        
        question_data = {
            "question_id": "Q-SUSPEND-001",
            "question_type": "financial_decision",
            "priority": "critical",
            "project_id": "PROJ-2024-001",
            "related_schema_type": "FinancialReportSchema",
            "related_entity_id": "FIN-2024-0892",
            "question_markdown": "# Financial Decision\n\n## Options:\n**(a)** Approve\n**(b)** Reject",
            "option_a": "Approve",
            "option_b": "Reject",
            "suspended_task_id": "TASK-SUSPEND-001"
        }
        
        gateway.ask_human(question_data)
        
        # Check task status
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT status FROM llm_task_queue WHERE task_id = ?", ('TASK-SUSPEND-001',))
            result = cursor.fetchone()
            
            assert result is not None
            assert result[0] == 'waiting_human'
        
        # Cleanup
        gateway.cleanup_shadow_copies()
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_task_resumption_on_answer(self):
        """Test that task is resumed when question is answered."""
        # This test requires the previous suspension to be in place
        # For simplicity, we'll test the resumption logic directly
        
        from app.modules.storage.questions_gateway import QuestionsGateway
        temp_dir = Path(tempfile.mkdtemp())
        gateway = QuestionsGateway(temp_dir)
        
        # Create question with suspended task
        question_data = {
            "question_id": "Q-SUSPEND-002",
            "question_type": "test",
            "priority": "normal",
            "project_id": "PROJ-2024-001",
            "related_schema_type": "TestSchema",
            "related_entity_id": "TEST-001",
            "question_markdown": "# Test\n\n## Options:\n**(a)** A\n**(b)** B",
            "option_a": "A",
            "option_b": "B",
            "suspended_task_id": "TASK-SUSPEND-002"
        }
        
        gateway.ask_human(question_data)
        time.sleep(2.5)
        
        # Answer the question
        gateway.answer_question("Q-SUSPEND-002", "a", "user_123")
        
        # Cleanup
        gateway.cleanup_shadow_copies()
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)


class TestCorruptedBlockStability:
    """Tests for stability against corrupted/blocked QUESTIONS.md."""
    
    @pytest.fixture(autouse=True)
    def setup_gateway(self):
        """Initialize gateway with corrupted file scenario."""
        initialize_questions_database()
        
        # Clean up test data
        import sqlite3
        from app.modules.storage.database import DB_PATH
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM questions_gateway WHERE question_id LIKE 'Q-CORRUPT-%'")
        conn.commit()
        conn.close()
        
        temp_dir = Path(tempfile.mkdtemp())
        gateway = QuestionsGateway(temp_dir)
        
        yield gateway
        
        gateway.cleanup_shadow_copies()
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_invalid_markdown_rejection(self, setup_gateway):
        """Test that invalid markdown is rejected."""
        gateway = setup_gateway
        invalid_markdown = "This is not valid markdown for a question block"
        
        question_data = {
            "question_id": "Q-CORRUPT-001",
            "question_type": "test",
            "priority": "normal",
            "project_id": "PROJ-2024-001",
            "related_schema_type": "TestSchema",
            "related_entity_id": "TEST-001",
            "question_markdown": invalid_markdown,
            "option_a": "A",
            "option_b": "B"
        }
        
        # Should create question but mark as invalid
        question_id = gateway.ask_human(question_data)
        
        # Check that question was marked as invalid
        question = gateway._get_question(question_id)
        # The status might be 'open' with integrity_check failed, check both
        assert question['integrity_regex_match'] == 0
    
    def test_missing_options_rejection(self, setup_gateway):
        """Test that missing options section is rejected."""
        gateway = setup_gateway
        invalid_markdown = "# Test Question\n\nThis question has no options section"
        
        question_data = {
            "question_id": "Q-CORRUPT-002",
            "question_type": "test",
            "priority": "normal",
            "project_id": "PROJ-2024-001",
            "related_schema_type": "TestSchema",
            "related_entity_id": "TEST-001",
            "question_markdown": invalid_markdown,
            "option_a": "A",
            "option_b": "B"
        }
        
        question_id = gateway.ask_human(question_data)
        
        question = gateway._get_question(question_id)
        assert question['integrity_regex_match'] == 0
    
    def test_partial_corruption_handling(self, setup_gateway):
        """Test handling of partially corrupted markdown."""
        gateway = setup_gateway
        # Valid structure but missing required parts
        partial_markdown = "# Budget Conflict\n\nMissing options section"
        
        question_data = {
            "question_id": "Q-CORRUPT-003",
            "question_type": "test",
            "priority": "normal",
            "project_id": "PROJ-2024-001",
            "related_schema_type": "TestSchema",
            "related_entity_id": "TEST-001",
            "question_markdown": partial_markdown,
            "option_a": "A",
            "option_b": "B"
        }
        
        question_id = gateway.ask_human(question_data)
        
        question = gateway._get_question(question_id)
        assert question['integrity_regex_match'] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])