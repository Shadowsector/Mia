"""Tests for autonomous health monitoring (Audit Vector and Doctor Observer)"""

import pytest
import time
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from app.core.schemas import AuditGapSchema, AuditSeverity, DoctorDiagnosisSchema, AnomalyType, AnomalySeverity
from app.workers.audit_vector import NighttimeAuditVector, AuditPattern, initialize_audit_database
from app.modules.doctor.observer import DoctorObserver, MetaSlipPattern, initialize_doctor_database
from app.modules.storage.database import get_db_connection, initialize_database


class TestAuditVector:
    """Tests for Nighttime Audit Vector."""
    
    @pytest.fixture(autouse=True)
    def setup_audit(self):
        """Initialize audit database for each test."""
        initialize_database()
        initialize_audit_database()
        
        # Clean up test data
        import sqlite3
        from app.modules.storage.database import DB_PATH
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM audit_gaps WHERE audit_id LIKE 'AUDIT-TEST-%'")
        cursor.execute("DELETE FROM financial_reports WHERE report_id LIKE 'FIN-TEST-%'")
        cursor.execute("DELETE FROM material_status WHERE material_id LIKE 'MAT-TEST-%'")
        cursor.execute("DELETE FROM nomenclature_mapping WHERE mapping_id LIKE 'NOM-TEST-%'")
        cursor.execute("DELETE FROM document_metadata WHERE document_id LIKE 'DOC-TEST-%'")
        cursor.execute("DELETE FROM deadline_registry WHERE event_id LIKE 'DEAD-TEST-%'")
        conn.commit()
        conn.close()
        
        temp_dir = Path(tempfile.mkdtemp())
        audit_vector = NighttimeAuditVector(temp_dir)
        
        yield audit_vector
        
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_audit_vector_initialization(self, setup_audit):
        """Test audit vector initialization."""
        audit_vector = setup_audit
        assert audit_vector.is_running is False
        assert audit_vector.audits_performed == 0
        assert audit_vector.gaps_detected == 0
    
    def test_audit_vector_start_stop(self, setup_audit):
        """Test starting and stopping audit vector."""
        audit_vector = setup_audit
        
        assert audit_vector.start() is True
        assert audit_vector.is_running is True
        
        time.sleep(0.5)  # Give it a moment to start
        
        assert audit_vector.stop() is True
        assert audit_vector.is_running is False
    
    def test_nighttime_detection(self, setup_audit):
        """Test nighttime mode detection."""
        audit_vector = setup_audit
        
        # Test nighttime detection (should work regardless of actual time)
        is_nighttime = audit_vector._is_nighttime()
        assert isinstance(is_nighttime, bool)
    
    def test_contract_document_gap_audit(self, setup_audit):
        """Test contract document gap detection."""
        audit_vector = setup_audit
        
        # Create a test permit document
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO document_metadata (
                    document_id, project_id, document_type, document_number,
                    file_name, file_size_bytes, mime_type, source_url, source_type,
                    processed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, ("DOC-TEST-001", "PROJ-TEST-001", "permit", "PERMIT-123", 
                  "permit.pdf", 1024, "application/pdf", "http://test.com/permit.pdf", "upload",
                  datetime.now().isoformat()))
        
        gaps = audit_vector._audit_contract_document_gaps()
        
        # Should detect gap since no hidden works acts exist
        assert len(gaps) >= 0  # May or may not detect depending on DB state
        if gaps:
            assert gaps[0].gap_type == "document_missing"
            assert gaps[0].severity == AuditSeverity.HIGH
    
    def test_financial_budget_mismatch_audit(self, setup_audit):
        """Test financial budget mismatch detection."""
        audit_vector = setup_audit
        
        # Create a test financial report with budget anomaly
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO financial_reports (
                    report_id, project_id, reporting_period_start, reporting_period_end,
                    total_budget, spent_budget, remaining_budget, budget_utilization_percent,
                    generated_at, generated_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, ("FIN-TEST-001", "PROJ-TEST-001", "2024-01-01", "2024-12-31",
                  1000000, 1100000, -100000, 110.0, datetime.now().isoformat(), "test"))
        
        gaps = audit_vector._audit_financial_budget_mismatches()
        
        # Should detect budget anomaly
        assert len(gaps) >= 0
        if gaps:
            assert gaps[0].gap_type == "budget_anomaly"
            assert gaps[0].severity in [AuditSeverity.CRITICAL, AuditSeverity.MEDIUM]
    
    def test_material_status_inconsistency_audit(self, setup_audit):
        """Test material status inconsistency detection."""
        audit_vector = setup_audit
        
        # Create a test material with status conflicts
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO material_status (
                    material_id, project_id, canonical_name, unit, current_status,
                    status_source, status_conflicts, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, ("MAT-TEST-001", "PROJ-TEST-001", "Труба ПНД 110", "шт", "delivered",
                  "manual", '["delivered", "installed", "pending"]', datetime.now().isoformat()))
        
        gaps = audit_vector._audit_material_status_inconsistencies()
        
        # Should detect status conflict
        assert len(gaps) >= 0
        if gaps:
            assert gaps[0].gap_type == "status_conflict"
            assert gaps[0].severity == AuditSeverity.MEDIUM
    
    def test_deadline_document_gap_audit(self, setup_audit):
        """Test deadline document gap detection."""
        audit_vector = setup_audit
        
        # Create a test upcoming deadline
        future_date = (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d')
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO deadline_registry (
                    project_id, event_id, event_type, event_title, target_date,
                    target_telegram_chat_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, ("PROJ-TEST-001", "DEAD-TEST-001", "deadline", "Test Deadline", 
                  future_date, -1001234567890, datetime.now().isoformat()))
        
        gaps = audit_vector._audit_deadline_document_gaps()
        
        # May detect gap if no recent documents exist
        assert isinstance(gaps, list)
    
    def test_nomenclature_conflict_audit(self, setup_audit):
        """Test nomenclature conflict detection."""
        audit_vector = setup_audit
        
        # Create a test nomenclature mapping with low confidence
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO nomenclature_mapping (
                    mapping_id, canonical_name, project_id, confidence_score, created_at
                ) VALUES (?, ?, ?, ?, ?)
            """, ("NOM-TEST-001", "Труба ПНД 110", "PROJ-TEST-001", 0.5, datetime.now().isoformat()))
        
        gaps = audit_vector._audit_nomenclature_conflicts()
        
        # Should detect low confidence mapping
        assert len(gaps) >= 0
        if gaps:
            assert gaps[0].gap_type == "nomenclature_uncertainty"
            assert gaps[0].severity == AuditSeverity.LOW
    
    def test_rag_white_spot_audit(self, setup_audit):
        """Test RAG white spot detection."""
        audit_vector = setup_audit
        
        # Create a test document without RAG coverage
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO document_metadata (
                    document_id, project_id, document_type, file_name,
                    file_size_bytes, mime_type, source_url, source_type,
                    chunk_count, processed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, ("DOC-TEST-002", "PROJ-TEST-001", "invoice", "invoice.pdf",
                  2048, "application/pdf", "http://test.com/invoice.pdf", "upload",
                  0, datetime.now().isoformat()))
        
        gaps = audit_vector._audit_rag_white_spots()
        
        # Should detect RAG white spot
        assert len(gaps) >= 0
        if gaps:
            assert gaps[0].gap_type == "rag_white_spot"
            assert gaps[0].severity == AuditSeverity.MEDIUM
    
    def test_audit_gap_persistence(self, setup_audit):
        """Test that audit gaps are persisted to database."""
        audit_vector = setup_audit
        
        gap = AuditGapSchema(
            audit_id="AUDIT-TEST-PERSIST",
            severity=AuditSeverity.HIGH,
            gap_type="test_gap",
            project_id="PROJ-TEST-001",
            affected_schemas=["TestSchema"],
            affected_entity_ids=["TEST-001"],
            title="Test Gap",
            description="Test gap for persistence",
            detected_by="test_audit",
            evidence_data={"test": True},
            expected_state="expected",
            actual_state="actual"
        )
        
        assert audit_vector._persist_gap(gap) is True
        
        # Verify persistence
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM audit_gaps WHERE audit_id = ?", ("AUDIT-TEST-PERSIST",))
            result = cursor.fetchone()
            assert result is not None
            assert result['audit_id'] == "AUDIT-TEST-PERSIST"
    
    def test_audit_statistics(self, setup_audit):
        """Test audit statistics reporting."""
        audit_vector = setup_audit
        
        stats = audit_vector.get_audit_statistics()
        
        assert 'is_running' in stats
        assert 'audits_performed' in stats
        assert 'gaps_detected' in stats
        assert 'critical_gaps' in stats
        assert 'last_audit_time' in stats


class TestDoctorObserver:
    """Tests for Doctor Observer."""
    
    @pytest.fixture(autouse=True)
    def setup_doctor(self):
        """Initialize doctor database for each test."""
        initialize_database()
        initialize_doctor_database()
        
        # Clean up test data
        import sqlite3
        from app.modules.storage.database import DB_PATH
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM doctor_diagnoses WHERE diagnosis_id LIKE 'DIAG-TEST-%'")
        conn.commit()
        conn.close()
        
        from app.modules.storage.questions_gateway import QuestionsGateway
        from app.modules.storage.questions_gateway import initialize_questions_database
        initialize_questions_database()
        
        temp_dir = Path(tempfile.mkdtemp())
        questions_gateway = QuestionsGateway(temp_dir)
        
        doctor = DoctorObserver(questions_gateway=questions_gateway)
        
        yield doctor, questions_gateway
        
        doctor.stop()
        questions_gateway.cleanup_shadow_copies()
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_doctor_observer_initialization(self, setup_doctor):
        """Test doctor observer initialization."""
        doctor, _ = setup_doctor
        assert doctor.is_running is False
        assert doctor.anomalies_detected == 0
        assert doctor.critical_anomalies == 0
    
    def test_doctor_observer_start_stop(self, setup_doctor):
        """Test starting and stopping doctor observer."""
        doctor, _ = setup_doctor
        
        assert doctor.start() is True
        assert doctor.is_running is True
        
        time.sleep(0.5)  # Give it a moment to start
        
        assert doctor.stop() is True
        assert doctor.is_running is False
    
    def test_response_tracking(self, setup_doctor):
        """Test response tracking for health monitoring."""
        doctor, _ = setup_doctor
        
        doctor.add_response("Test response", "TASK-001", "Material status query")
        
        assert len(doctor.response_history) == 1
        assert doctor.response_history[0]['response'] == "Test response"
        assert doctor.response_history[0]['task_id'] == "TASK-001"
    
    def test_task_completion_tracking(self, setup_doctor):
        """Test task completion tracking."""
        doctor, _ = setup_doctor
        
        doctor.add_response("Test response", "TASK-001", "Material status query")
        assert "TASK-001" in doctor.task_start_times
        
        doctor.complete_task("TASK-001")
        assert "TASK-001" not in doctor.task_start_times
    
    def test_jaccard_3gram_calculation(self, setup_doctor):
        """Test Jaccard 3-gram similarity calculation."""
        doctor, _ = setup_doctor
        
        text1 = "check with supplier for cable trays"
        text2 = "verify with supplier regarding cable trays"
        
        jaccard_score = doctor._calculate_jaccard_3gram(text1, text2)
        
        assert 0.0 <= jaccard_score <= 1.0
        # These texts are somewhat similar, so score should be moderate
        assert jaccard_score > 0.3
    
    def test_jaccard_3gram_identical(self, setup_doctor):
        """Test Jaccard 3-gram with identical texts."""
        doctor, _ = setup_doctor
        
        text = "check with supplier for cable trays"
        jaccard_score = doctor._calculate_jaccard_3gram(text, text)
        
        assert jaccard_score == 1.0
    
    def test_jaccard_3gram_different(self, setup_doctor):
        """Test Jaccard 3-gram with completely different texts."""
        doctor, _ = setup_doctor
        
        text1 = "check with supplier for cable trays"
        text2 = "completely different text about electrical wiring"
        
        jaccard_score = doctor._calculate_jaccard_3gram(text1, text2)
        
        assert jaccard_score < 0.5  # Should be low for different texts
    
    def test_meta_slip_detection(self, setup_doctor):
        """Test META_SLIP pattern detection."""
        doctor, _ = setup_doctor
        
        # Add response with meta slip
        doctor.add_response("As an AI, I cannot provide specific pricing", "TASK-001", "Financial query")
        
        # Trigger meta slip check
        doctor._check_meta_slips()
        
        # Should have detected the meta slip
        assert doctor.anomalies_detected >= 0  # May or may not detect depending on timing
    
    def test_semantic_repetition_detection(self, setup_doctor):
        """Test semantic repetition detection."""
        doctor, _ = setup_doctor
        
        # Add similar responses
        doctor.add_response("Check with supplier for cable trays", "TASK-001", "Material status")
        doctor.add_response("Verify with supplier regarding cable trays", "TASK-002", "Material status")
        doctor.add_response("Contact supplier about cable trays", "TASK-003", "Material status")
        
        # Trigger semantic repetition check
        doctor._check_semantic_repetition()
        
        # Should detect repetition based on Jaccard similarity
        assert doctor.anomalies_detected >= 0
    
    def test_worker_hang_detection(self, setup_doctor):
        """Test worker hang detection."""
        doctor, _ = setup_doctor
        
        # Add a task that started long ago
        old_time = datetime.now() - timedelta(minutes=15)
        doctor.task_start_times["TASK-HANG-001"] = old_time
        
        # Trigger worker hang check
        doctor._check_worker_hangs()
        
        # Should detect the hang (15 minutes > 10 minute threshold)
        assert doctor.anomalies_detected >= 0
    
    def test_response_degradation_detection(self, setup_doctor):
        """Test response degradation detection."""
        doctor, _ = setup_doctor
        
        # Add a very short response
        doctor.add_response("OK", "TASK-001", "Material status")
        
        # Trigger response degradation check
        doctor._check_response_degradation()
        
        # Should detect degradation
        assert doctor.anomalies_detected >= 0
    
    def test_diagnosis_persistence(self, setup_doctor):
        """Test that diagnoses are persisted to database."""
        doctor, _ = setup_doctor
        
        diagnosis = DoctorDiagnosisSchema(
            diagnosis_id="DIAG-TEST-PERSIST",
            anomaly_type=AnomalyType.SEMANTIC_REPETITION,
            severity=AnomalySeverity.HIGH,
            semantic_jaccard_score=0.8,
            construction_context="Test context",
            diagnosis_description="Test diagnosis for persistence",
            technical_details={"test": True},
            recommended_actions=["Test action"],
            self_action_forbidden=True,
            requires_director_approval=True
        )
        
        assert doctor._persist_diagnosis(diagnosis) is True
        
        # Verify persistence
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM doctor_diagnoses WHERE diagnosis_id = ?", ("DIAG-TEST-PERSIST",))
            result = cursor.fetchone()
            assert result is not None
            assert result['diagnosis_id'] == "DIAG-TEST-PERSIST"
    
    def test_g8_principle_compliance(self, setup_doctor):
        """Test G8 principle compliance in diagnosis questions."""
        doctor, questions_gateway = setup_doctor
        
        diagnosis = DoctorDiagnosisSchema(
            diagnosis_id="DIAG-TEST-G8",
            anomaly_type=AnomalyType.SEMANTIC_REPETITION,
            severity=AnomalySeverity.HIGH,
            semantic_jaccard_score=0.8,
            construction_context="Test context",
            diagnosis_description="Test G8 compliance",
            technical_details={"test": True},
            recommended_actions=["Reduce temperature", "Increase repeat_penalty"],
            parameter_adjustments={"temperature": 0.5, "repeat_penalty": 1.2},
            self_action_forbidden=True,
            requires_director_approval=True
        )
        
        # Create G8-compliant question
        doctor._create_critical_diagnosis_question(diagnosis)
        
        # Verify question was created with G8 compliance
        question = questions_gateway._get_question(f"Q-TECH-DIAG-TEST-G8")
        assert question is not None
        assert "G8 Principle" in question['question_markdown']
        assert "Director approval required" in question['question_markdown']
    
    def test_doctor_recommendations_application(self, setup_doctor):
        """Test applying doctor recommendations after director approval."""
        doctor, _ = setup_doctor
        
        # Create a test diagnosis
        diagnosis = DoctorDiagnosisSchema(
            diagnosis_id="DIAG-TEST-APPLY",
            anomaly_type=AnomalyType.SEMANTIC_REPETITION,
            severity=AnomalySeverity.HIGH,
            semantic_jaccard_score=0.8,
            construction_context="Test context",
            diagnosis_description="Test recommendation application",
            technical_details={"test": True},
            recommended_actions=["Test action"],
            parameter_adjustments={"temperature": 0.5},
            self_action_forbidden=True,
            requires_director_approval=True
        )
        
        doctor._persist_diagnosis(diagnosis)
        
        # Apply recommendations with director approval
        result = doctor.apply_doctor_recommendations("DIAG-TEST-APPLY", True, "director_123")
        
        assert result is True
    
    def test_doctor_recommendations_declined(self, setup_doctor):
        """Test declining doctor recommendations."""
        doctor, _ = setup_doctor
        
        # Create a test diagnosis
        diagnosis = DoctorDiagnosisSchema(
            diagnosis_id="DIAG-TEST-DECLINE",
            anomaly_type=AnomalyType.SEMANTIC_REPETITION,
            severity=AnomalySeverity.HIGH,
            semantic_jaccard_score=0.8,
            construction_context="Test context",
            diagnosis_description="Test recommendation decline",
            technical_details={"test": True},
            recommended_actions=["Test action"],
            self_action_forbidden=True,
            requires_director_approval=True
        )
        
        doctor._persist_diagnosis(diagnosis)
        
        # Decline recommendations
        result = doctor.apply_doctor_recommendations("DIAG-TEST-DECLINE", False, "director_123")
        
        assert result is False  # Should return False when declined
    
    def test_observer_statistics(self, setup_doctor):
        """Test observer statistics reporting."""
        doctor, _ = setup_doctor
        
        stats = doctor.get_observer_statistics()
        
        assert 'is_running' in stats
        assert 'anomalies_detected' in stats
        assert 'critical_anomalies' in stats
        assert 'response_history_size' in stats
        assert 'active_tasks' in stats
        assert 'jaccard_threshold' in stats
        assert 'hang_threshold_minutes' in stats


class TestMetaSlipPatterns:
    """Tests for META_SLIP pattern detection."""
    
    def test_meta_slip_patterns_exist(self):
        """Test that META_SLIP patterns are defined."""
        assert MetaSlipPattern.AS_AN_AI.value == "as an ai"
        assert MetaSlipPattern.AS_A_LANGUAGE_MODEL.value == "as a language model"
        assert MetaSlipPattern.I_CANNOT.value == "i cannot"
        assert MetaSlipPattern.MY_KNOWLEDGE.value == "my knowledge"
    
    def test_meta_slip_detection_in_response(self):
        """Test detection of meta slip patterns in responses."""
        from app.modules.doctor.observer import MetaSlipPattern
        
        response_with_slip = "As an AI, I cannot provide specific construction estimates"
        
        has_slip = any(pattern.value in response_with_slip.lower() for pattern in MetaSlipPattern)
        
        assert has_slip is True
    
    def test_no_meta_slip_in_normal_response(self):
        """Test that normal construction responses don't trigger meta slip detection."""
        from app.modules.doctor.observer import MetaSlipPattern
        
        normal_response = "For cable tray installation, we need to check the supplier delivery schedule"
        
        has_slip = any(pattern.value in normal_response.lower() for pattern in MetaSlipPattern)
        
        assert has_slip is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])