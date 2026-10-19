"""Tests for Pydantic v2 Schemas"""

import pytest
from datetime import datetime
from decimal import Decimal
from pydantic import field_validator, ValidationError
from app.core.schemas import (
    TaskPriority, AgentTaskType, LLMTaskSchema,
    TelegramMessage, ProjectStatus, ProjectContextSchema,
    KS2DocumentReference, FinancialReportSchema,
    MaterialUnit, MaterialStatus, MaterialStatusSchema,
    DocumentType, StampVerificationStatus, DocumentMetadataSchema,
    NotificationStatus, DeadlineRegistrySchema,
    EventType, DateExtractionMethod, ExtractedEventSchema,
    NomenclatureMapping
)


class TestLLMTaskSchema:
    """Tests for LLMTaskSchema"""
    
    def test_basic_task_creation(self):
        """Test basic task creation with required fields"""
        task = LLMTaskSchema(
            task_id="TASK-2024-001",
            task_type=AgentTaskType.TOOL_CALL,
            priority=TaskPriority.HIGH,
            system_current_time=datetime.now(),
            user_message="Check material status",
            telegram_chat_id=-1001234567890,
            user_id=123456789
        )
        assert task.task_id == "TASK-2024-001"
        assert task.priority == TaskPriority.HIGH
        assert task.status == "pending"
    
    def test_priority_values(self):
        """Test priority enum values"""
        assert TaskPriority.CRITICAL == 10
        assert TaskPriority.HIGH == 8
        assert TaskPriority.NORMAL == 5
        assert TaskPriority.LOW == 3
        assert TaskPriority.BACKGROUND == 1
    
    def test_task_with_context(self):
        """Test task with context window"""
        task = LLMTaskSchema(
            task_id="TASK-2024-002",
            task_type=AgentTaskType.MULTI_STEP_REASONING,
            priority=TaskPriority.NORMAL,
            system_current_time=datetime.now(),
            conversation_context=[
                {"message_id": 1, "text": "First message"},
                {"message_id": 2, "text": "Second message"}
            ],
            parent_thread_id=455,
            user_message="Continue the conversation",
            telegram_chat_id=-1001234567890,
            user_id=123456789
        )
        assert len(task.conversation_context) == 2
        assert task.parent_thread_id == 455


class TestTelegramMessage:
    """Tests for TelegramMessage schema"""
    
    def test_basic_message(self):
        """Test basic message creation"""
        msg = TelegramMessage(
            message_id=458,
            chat_id=-1001234567890,
            user_id=123456789,
            username="site_manager",
            text="Mia, check materials",
            timestamp=datetime.now()
        )
        assert msg.message_id == 458
        assert msg.mentions_mia == False
        assert msg.is_summarized == False
    
    def test_message_with_context(self):
        """Test message with parent thread context"""
        msg = TelegramMessage(
            message_id=458,
            chat_id=-1001234567890,
            user_id=123456789,
            username="site_manager",
            text="Mia, check materials",
            timestamp=datetime.now(),
            is_reply=True,
            reply_to_message_id=455,
            mentions_mia=True,
            parent_thread_context=[
                {"message_id": 455, "text": "We need materials", "user": "foreman"}
            ],
            sliding_window_context=[
                {"message_id": 450, "text": "Morning check", "user": "foreman"}
            ]
        )
        assert msg.is_reply == True
        assert msg.reply_to_message_id == 455
        assert msg.mentions_mia == True
        assert len(msg.parent_thread_context) == 1


class TestProjectContextSchema:
    """Tests for ProjectContextSchema"""
    
    def test_project_creation(self):
        """Test basic project creation"""
        project = ProjectContextSchema(
            project_id="PROJ-2024-001",
            project_name="Fiber Optic Relocation",
            telegram_chat_id=-1001234567890,
            google_drive_folder_id="1AbCdEfGhIjKlMnOpQrStUvWxYz"
        )
        assert project.project_id == "PROJ-2024-001"
        assert project.status == ProjectStatus.PLANNING
        assert len(project.email_filters) == 0
    
    def test_project_with_filters(self):
        """Test project with email filters"""
        project = ProjectContextSchema(
            project_id="PROJ-2024-001",
            project_name="Fiber Optic Relocation",
            telegram_chat_id=-1001234567890,
            google_drive_folder_id="1AbCdEfGhIjKlMnOpQrStUvWxYz",
            email_filters=["*Sector 7*", "*fiber optic*"],
            status=ProjectStatus.ACTIVE
        )
        assert len(project.email_filters) == 2
        assert project.status == ProjectStatus.ACTIVE


class TestFinancialReportSchema:
    """Tests for FinancialReportSchema"""
    
    def test_basic_report(self):
        """Test basic financial report creation"""
        report = FinancialReportSchema(
            report_id="FIN-2024-001",
            project_id="PROJ-2024-001",
            reporting_period_start=datetime(2024, 8, 1),
            reporting_period_end=datetime(2024, 8, 31),
            total_budget=Decimal("5000000.00"),
            generated_by="mia_system"
        )
        assert report.report_id == "FIN-2024-001"
        assert report.spent_budget == Decimal("0")
        assert report.budget_utilization_percent == 0.0
    
    def test_budget_calculations(self):
        """Test automatic budget calculations"""
        report = FinancialReportSchema(
            report_id="FIN-2024-002",
            project_id="PROJ-2024-001",
            reporting_period_start=datetime(2024, 8, 1),
            reporting_period_end=datetime(2024, 8, 31),
            total_budget=Decimal("5000000.00"),
            spent_budget=Decimal("1250000.00"),
            generated_by="mia_system"
        )
        assert report.calculated_remaining_budget == Decimal("3750000.00")
        assert report.calculated_utilization_percent == 25.0
    
    def test_ks2_documents(self):
        """Test KS-2 document references"""
        ks2_ref = KS2DocumentReference(
            document_id="KS2-2024-045",
            amount=Decimal("500000.00"),
            verified=True
        )
        report = FinancialReportSchema(
            report_id="FIN-2024-003",
            project_id="PROJ-2024-001",
            reporting_period_start=datetime(2024, 8, 1),
            reporting_period_end=datetime(2024, 8, 31),
            total_budget=Decimal("5000000.00"),
            ks2_documents=[ks2_ref],
            generated_by="mia_system"
        )
        assert len(report.ks2_documents) == 1
        assert report.calculated_ks2_total_amount == Decimal("500000.00")


class TestMaterialStatusSchema:
    """Tests for MaterialStatusSchema"""
    
    def test_basic_material(self):
        """Test basic material status creation"""
        material = MaterialStatusSchema(
            material_id="MAT-2024-001",
            project_id="PROJ-2024-001",
            canonical_name="Труба ПНД 110",
            unit=MaterialUnit.METERS,
            status_source="telegram_chat"
        )
        assert material.material_id == "MAT-2024-001"
        assert material.unit == MaterialUnit.METERS
        assert material.current_status == MaterialStatus.UNKNOWN
    
    def test_material_calculations(self):
        """Test automatic material calculations"""
        material = MaterialStatusSchema(
            material_id="MAT-2024-002",
            project_id="PROJ-2024-001",
            canonical_name="Труба ПНД 110",
            unit=MaterialUnit.METERS,
            total_ordered=Decimal("5000.0"),
            total_installed=Decimal("1500.0"),
            unit_cost=Decimal("150.00"),
            status_source="telegram_chat"
        )
        assert material.calculated_remaining_required == Decimal("3500.0")
        assert material.calculated_total_cost == Decimal("750000.00")
    
    def test_material_with_aliases(self):
        """Test material with alias names"""
        material = MaterialStatusSchema(
            material_id="MAT-2024-003",
            project_id="PROJ-2024-001",
            canonical_name="Труба ПНД 110",
            alias_names=["сотка пндшка", "пнд 110мм"],
            unit=MaterialUnit.METERS,
            status_source="telegram_chat"
        )
        assert len(material.alias_names) == 2
        assert "сотка пндшка" in material.alias_names


class TestDocumentMetadataSchema:
    """Tests for DocumentMetadataSchema"""
    
    def test_basic_document(self):
        """Test basic document creation"""
        doc = DocumentMetadataSchema(
            document_id="DOC-2024-001",
            project_id="PROJ-2024-001",
            document_type=DocumentType.TECHNICAL_SPECIFICATION,
            source_url="https://drive.google.com/file/d/1xyz",
            source_type="google_drive",
            file_name="specification.pdf",
            file_size_bytes=2456789
        )
        assert doc.document_id == "DOC-2024-001"
        assert doc.version_index == 1
        assert doc.is_latest_version == True
    
    def test_document_with_stamps(self):
        """Test document with stamp verification"""
        doc = DocumentMetadataSchema(
            document_id="DOC-2024-002",
            project_id="PROJ-2024-001",
            document_type=DocumentType.PERMIT_GATI,
            source_url="https://drive.google.com/file/d/1xyz",
            source_type="google_drive",
            file_name="ГАТИ_Разрешение.pdf",
            file_size_bytes=2456789,
            stamps_present=True,
            stamp_verification_status=StampVerificationStatus.VERIFIED_PRESENT,
            detected_stamps=["City Administration Stamp"]
        )
        assert doc.stamps_present == True
        assert doc.stamp_verification_status == StampVerificationStatus.VERIFIED_PRESENT
        assert len(doc.detected_stamps) == 1
    
    def test_document_versioning(self):
        """Test document version control"""
        doc = DocumentMetadataSchema(
            document_id="DOC-2024-003",
            project_id="PROJ-2024-001",
            document_type=DocumentType.EXECUTIVE_BLUEPRINT,
            source_url="https://drive.google.com/file/d/1xyz",
            source_type="google_drive",
            file_name="blueprint_v2.pdf",
            file_size_bytes=3456789,
            version_index=2,
            previous_version_id="DOC-2024-002",
            version_conflict_detected=False
        )
        assert doc.version_index == 2
        assert doc.previous_version_id == "DOC-2024-002"
        assert doc.version_conflict_detected == False


class TestDeadlineRegistrySchema:
    """Tests for DeadlineRegistrySchema"""
    
    def test_basic_deadline(self):
        """Test basic deadline creation"""
        deadline = DeadlineRegistrySchema(
            id=1,
            project_id="PROJ-2024-001",
            event_id="EVENT-2024-001",
            event_type="permit_expiration",
            event_title="ГАТИ Permit Expiration",
            target_date=datetime(2027, 4, 12),
            target_telegram_chat_id=-1001234567890
        )
        assert deadline.id == 1
        assert deadline.notified_status == NotificationStatus.NOT_NOTIFIED
        assert deadline.notification_count == 0
    
    def test_deadline_with_notifications(self):
        """Test deadline with user notifications"""
        deadline = DeadlineRegistrySchema(
            id=2,
            project_id="PROJ-2024-001",
            event_id="EVENT-2024-002",
            event_type="client_meeting",
            event_title="Client Meeting",
            target_date=datetime(2024, 9, 15),
            target_telegram_chat_id=-1001234567890,
            additional_notify_user_ids=[123456789, 987654321],
            notification_threshold_days=7
        )
        assert len(deadline.additional_notify_user_ids) == 2
        assert deadline.notification_threshold_days == 7


class TestExtractedEventSchema:
    """Tests for ExtractedEventSchema"""
    
    def test_basic_event(self):
        """Test basic event extraction"""
        event = ExtractedEventSchema(
            event_id="EVENT-2024-001",
            project_id="PROJ-2024-001",
            event_type=EventType.PERMIT_EXPIRATION,
            raw_text="Permit expires on 2027-04-12",
            source_type="document",
            original_date_phrase="2027-04-12",
            extraction_method=DateExtractionMethod.EXPLICIT_DATE,
            target_date=datetime(2027, 4, 12),
            event_title="Permit Expiration",
            extracted_by="mia_system"
        )
        assert event.event_id == "EVENT-2024-001"
        assert event.extraction_confidence == 1.0
        assert event.verified == False
    
    def test_event_validation(self):
        """Test event validation"""
        # Test confidence validation
        with pytest.raises(ValueError):
            ExtractedEventSchema(
                event_id="EVENT-2024-002",
                project_id="PROJ-2024-001",
                event_type=EventType.DEADLINE,
                raw_text="Due date next week",
                source_type="chat",
                original_date_phrase="next week",
                extraction_method=DateExtractionMethod.RELATIVE_PHRASE,
                extraction_confidence=1.5,  # Invalid: > 1.0
                target_date=datetime.now(),
                event_title="Task Deadline",
                extracted_by="mia_system"
            )
    
    def test_duration_based_event(self):
        """Test duration-based event extraction"""
        event = ExtractedEventSchema(
            event_id="EVENT-2024-003",
            project_id="PROJ-2024-001",
            event_type=EventType.MILESTONE,
            raw_text="Valid for 3 years starting from 2024-04-12",
            source_type="document",
            original_date_phrase="3 years starting from 2024-04-12",
            extraction_method=DateExtractionMethod.DURATION_FROM_DATE,
            target_date=datetime(2027, 4, 12),
            is_duration_based=True,
            duration_start_date=datetime(2024, 4, 12),
            duration_value=3,
            duration_unit="years",
            event_title="Contract Validity",
            extracted_by="mia_system"
        )
        assert event.is_duration_based == True
        assert event.duration_value == 3
        assert event.duration_unit == "years"


class TestNomenclatureMapping:
    """Tests for NomenclatureMapping schema"""
    
    def test_basic_mapping(self):
        """Test basic nomenclature mapping"""
        mapping = NomenclatureMapping(
            mapping_id="NOM-2024-001",
            canonical_name="Труба ПНД 110",
            project_id="PROJ-2024-001",
            confidence_score=0.95
        )
        assert mapping.mapping_id == "NOM-2024-001"
        assert mapping.usage_count == 0
        assert mapping.verified_at is None
    
    def test_mapping_with_aliases(self):
        """Test mapping with multiple aliases"""
        mapping = NomenclatureMapping(
            mapping_id="NOM-2024-002",
            canonical_name="Труба ПНД 110",
            alias_names=["сотка пндшка", "пнд 110мм", "polyethylene pipe 110"],
            project_id="PROJ-2024-001",
            material_category="pipes",
            confidence_score=0.90
        )
        assert len(mapping.alias_names) == 3
        assert mapping.material_category == "pipes"
    
    def test_mapping_validation(self):
        """Test confidence score validation"""
        with pytest.raises(ValueError):
            NomenclatureMapping(
                mapping_id="NOM-2024-003",
                canonical_name="Труба ПНД 110",
                project_id="PROJ-2024-001",
                confidence_score=1.5  # Invalid: > 1.0
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])