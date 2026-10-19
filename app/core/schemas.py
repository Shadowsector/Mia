"""Core Pydantic v2 Schemas for Mia PM OS"""

from pydantic import BaseModel, Field, computed_field, ConfigDict, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal
from enum import Enum


class TaskPriority(int, Enum):
    CRITICAL = 10  # Real-time admin tags, immediate response required
    HIGH = 8      # User queries, urgent requests
    NORMAL = 5    # Chat summarization, routine operations
    LOW = 3       # Document analysis, background processing
    BACKGROUND = 1 # Night vision chunking, lowest priority


class AgentTaskType(str, Enum):
    TOOL_CALL = "tool_call"
    MULTI_STEP_REASONING = "multi_step_reasoning"
    CONTEXT_BUILDING = "context_building"
    RESPONSE_GENERATION = "response_generation"


class LLMTaskSchema(BaseModel):
    """Schema for unified LLM task queue with chronological awareness."""
    
    task_id: str = Field(..., description="Unique task identifier")
    task_type: AgentTaskType = Field(..., description="Type of agent task")
    priority: TaskPriority = Field(..., description="Task priority for execution ordering")
    
    # Chronological Awareness
    system_current_time: datetime = Field(..., description="Current system time for relative date calculations")
    user_timezone: Optional[str] = Field(default="UTC", description="User's timezone for context")
    
    # Context Window
    conversation_context: List[Dict[str, Any]] = Field(default_factory=list, description="Sliding window of recent messages")
    parent_thread_id: Optional[int] = Field(None, description="Parent message ID for thread context")
    reply_chain: List[int] = Field(default_factory=list, description="Chain of reply message IDs")
    
    # Agent State
    agent_reasoning: Optional[str] = Field(None, description="Agent's reasoning for tool selection")
    selected_tools: List[str] = Field(default_factory=list, description="Tools agent decided to use")
    tool_call_sequence: List[Dict[str, Any]] = Field(default_factory=list, description="Sequence of tool calls")
    
    # Task Input
    user_message: str = Field(..., description="Original user message")
    user_intent: Optional[str] = Field(None, description="Detected user intent")
    entities_detected: Dict[str, Any] = Field(default_factory=dict, description="Entities extracted from message")
    
    # Project Context
    project_id: Optional[str] = Field(None, description="Associated project ID")
    telegram_chat_id: int = Field(..., description="Source Telegram chat ID")
    user_id: int = Field(..., description="User who sent the message")
    username: Optional[str] = Field(None, description="Username")
    
    # Processing
    status: str = Field(default="pending", description="Task status")
    queued_at: datetime = Field(default_factory=datetime.now, description="Queue timestamp")
    started_at: Optional[datetime] = Field(None, description="Processing start")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")
    result: Optional[Dict[str, Any]] = Field(None, description="Task result")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "task_id": "TASK-2024-0892",
            "task_type": "tool_call",
            "priority": 8,
            "system_current_time": "2024-08-18T10:30:00Z",
            "user_timezone": "Europe/Moscow",
            "conversation_context": [
                {"message_id": 455, "text": "We need cable trays", "user": "foreman"},
                {"message_id": 456, "text": "Ordered last week", "user": "supply_manager"}
            ],
            "parent_thread_id": 455,
            "reply_chain": [455, 456],
            "user_message": "Mia, check if the cable trays have arrived",
            "user_intent": "check_material_delivery_status",
            "entities_detected": {"material": "cable trays", "time_reference": "last week"},
            "project_id": "PROJ-2024-001",
            "telegram_chat_id": -1001234567890,
            "user_id": 123456789,
            "username": "site_manager",
            "status": "pending"
        }
    })


class TelegramMessage(BaseModel):
    """Enhanced Telegram message schema with context capture."""
    
    message_id: int
    chat_id: int
    user_id: int
    username: Optional[str]
    text: Optional[str]
    voice_note_file_id: Optional[str] = Field(None, description="Voice note file ID")
    timestamp: datetime
    is_reply: bool = False
    reply_to_message_id: Optional[int] = None
    mentions_mia: bool = False
    
    # Context Capture
    parent_thread_context: Optional[List[Dict[str, Any]]] = Field(None, description="Parent thread messages for context")
    sliding_window_context: Optional[List[Dict[str, Any]]] = Field(None, description="Last 10 messages for pronoun resolution")
    conversation_summary: Optional[str] = Field(None, description="Summary of recent conversation context")
    
    # Processing State
    is_summarized: bool = Field(default=False, description="Whether processed by summarization worker")
    summarized_at: Optional[datetime] = Field(None, description="Summarization timestamp")
    summary_batch_id: Optional[str] = Field(None, description="Summary batch ID")
    
    # Entity Extraction
    extracted_entities: Dict[str, Any] = Field(default_factory=dict, description="Entities extracted from message")
    detected_intent: Optional[str] = Field(None, description="Detected user intent")
    requires_agent_action: bool = Field(default=False, description="Whether message requires agent intervention")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "message_id": 458,
            "chat_id": -1001234567890,
            "user_id": 123456789,
            "username": "site_manager",
            "text": "Mia, check if the cable trays have arrived. They were supposed to be here last week.",
            "timestamp": "2024-08-17T14:30:00Z",
            "is_reply": True,
            "reply_to_message_id": 455,
            "mentions_mia": True,
            "parent_thread_context": [
                {"message_id": 455, "text": "We need cable trays for Sector 7", "user": "foreman"},
                {"message_id": 456, "text": "Ordered last week, expected delivery Monday", "user": "supply_manager"}
            ],
            "sliding_window_context": [
                {"message_id": 450, "text": "Morning check complete", "user": "foreman"}
            ],
            "extracted_entities": {"material": "cable trays", "time_reference": "last week", "project": "Sector 7"},
            "detected_intent": "check_material_delivery_status",
            "requires_agent_action": True
        }
    })


class ProjectStatus(str, Enum):
    PLANNING = "planning"
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ProjectContextSchema(BaseModel):
    """Simplified project context for agentic binding."""
    
    project_id: str = Field(..., description="Unique project identifier")
    project_name: str = Field(..., description="Human-readable project name")
    telegram_chat_id: int = Field(..., description="Telegram chat ID (UNIQUE constraint)")
    google_drive_folder_id: str = Field(..., description="Google Drive folder ID")
    email_filters: List[str] = Field(default_factory=list, description="Email classification filters")
    status: ProjectStatus = Field(default=ProjectStatus.PLANNING)
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    metadata: Optional[dict] = Field(default_factory=dict)
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "project_id": "PROJ-2024-001",
            "project_name": "Fiber Optic Relocation - Sector 7",
            "telegram_chat_id": -1001234567890,
            "google_drive_folder_id": "1AbCdEfGhIjKlMnOpQrStUvWxYz",
            "email_filters": ["*Sector 7*", "*fiber optic*"],
            "status": "active"
        }
    })


# Heavy Domain Schemas

class KS2DocumentReference(BaseModel):
    document_id: str = Field(..., description="KS-2 document identifier")
    document_url: Optional[str] = Field(None, description="Document URL if available")
    acceptance_date: Optional[datetime] = Field(None, description="Document acceptance date")
    amount: Decimal = Field(..., description="Amount in KS-2 document")
    verified: bool = Field(default=False, description="Whether Mia has verified this document")


class FinancialReportSchema(BaseModel):
    report_id: str = Field(..., description="Unique financial report identifier")
    project_id: str = Field(..., description="Associated project ID")
    reporting_period_start: datetime = Field(..., description="Period start date")
    reporting_period_end: datetime = Field(..., description="Period end date")
    
    total_budget: Decimal = Field(..., description="Total project budget")
    spent_budget: Decimal = Field(default=Decimal("0"), description="Total amount spent")
    remaining_budget: Decimal = Field(default=Decimal("0"), description="Remaining budget")
    budget_utilization_percent: float = Field(default=0.0, description="Budget utilization percentage")
    
    ks2_documents: List[KS2DocumentReference] = Field(default_factory=list, description="List of KS-2 documents")
    ks2_total_amount: Decimal = Field(default=Decimal("0"), description="Total amount from KS-2 documents")
    
    ks3_document_count: int = Field(default=0, description="Number of KS-3 documents")
    ks3_total_amount: Decimal = Field(default=Decimal("0"), description="Total amount from KS-3 documents")
    
    invoice_count: int = Field(default=0, description="Total number of invoices")
    invoice_total_amount: Decimal = Field(default=Decimal("0"), description="Total invoice amount")
    pending_invoices: int = Field(default=0, description="Number of pending invoices")
    pending_invoice_amount: Decimal = Field(default=Decimal("0"), description="Total pending invoice amount")
    
    material_costs: Dict[str, Decimal] = Field(default_factory=dict, description="Material category costs")
    labor_costs: Decimal = Field(default=Decimal("0"), description="Total labor costs")
    equipment_costs: Decimal = Field(default=Decimal("0"), description="Total equipment costs")
    overhead_costs: Decimal = Field(default=Decimal("0"), description="Total overhead costs")
    
    generated_at: datetime = Field(default_factory=datetime.now, description="Report generation timestamp")
    generated_by: str = Field(..., description="System or user who generated report")
    data_sources: List[str] = Field(default_factory=list, description="Data sources used for report")
    
    @computed_field
    @property
    def calculated_remaining_budget(self) -> Decimal:
        """Calculate remaining budget based on spent budget."""
        return self.total_budget - self.spent_budget
    
    @computed_field
    @property
    def calculated_utilization_percent(self) -> float:
        """Calculate budget utilization percentage."""
        if self.total_budget > 0:
            return float(self.spent_budget / self.total_budget * 100)
        return 0.0
    
    @computed_field
    @property
    def calculated_ks2_total_amount(self) -> Decimal:
        """Calculate total amount from KS-2 documents."""
        if self.ks2_documents:
            return sum(doc.amount for doc in self.ks2_documents)
        return Decimal("0")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "report_id": "FIN-2024-0892",
            "project_id": "PROJ-2024-001",
            "reporting_period_start": "2024-08-01T00:00:00Z",
            "reporting_period_end": "2024-08-31T23:59:59Z",
            "total_budget": 5000000.00,
            "spent_budget": 1250000.00,
            "remaining_budget": 3750000.00,
            "budget_utilization_percent": 25.0,
            "ks2_documents": [
                {
                    "document_id": "KS2-2024-045",
                    "document_url": "https://drive.google.com/file/d/1xyz...",
                    "acceptance_date": "2024-08-15T00:00:00Z",
                    "amount": 500000.00,
                    "verified": True
                }
            ],
            "ks2_total_amount": 500000.00,
            "material_costs": {
                "cable_trays": 200000.00,
                "fiber_optic": 300000.00,
                "conduit": 150000.00
            }
        }
    })


class MaterialUnit(str, Enum):
    PIECES = "pieces"
    METERS = "meters"
    KILOGRAMS = "kilograms"
    TONS = "tons"
    SQUARE_METERS = "square_meters"
    CUBIC_METERS = "cubic_meters"
    ROLLS = "rolls"
    BOXES = "boxes"
    PACKS = "packs"
    UNITS = "units"


class MaterialStatus(str, Enum):
    ORDERED = "ordered"
    IN_TRANSIT = "in_transit"
    ON_SITE = "on_site"
    INSTALLED = "installed"
    DELAYED = "delayed"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


class MaterialStatusSchema(BaseModel):
    material_id: str = Field(..., description="Unique material identifier")
    project_id: str = Field(..., description="Associated project ID")
    canonical_name: str = Field(..., description="Canonical material name")
    alias_names: List[str] = Field(default_factory=list, description="Alternative names for this material")
    
    unit: MaterialUnit = Field(..., description="Unit of measurement")
    total_ordered: Decimal = Field(default=Decimal("0"), description="Total quantity ordered")
    total_delivered: Decimal = Field(default=Decimal("0"), description="Total quantity delivered to site")
    total_installed: Decimal = Field(default=Decimal("0"), description="Total quantity installed")
    remaining_required: Decimal = Field(default=Decimal("0"), description="Remaining quantity required")
    
    current_status: MaterialStatus = Field(default=MaterialStatus.UNKNOWN, description="Current material status")
    status_last_updated: datetime = Field(default_factory=datetime.now, description="Last status update timestamp")
    status_source: str = Field(..., description="Source of status information")
    
    supplier_name: Optional[str] = Field(None, description="Material supplier name")
    expected_delivery_date: Optional[datetime] = Field(None, description="Expected delivery date")
    actual_delivery_date: Optional[datetime] = Field(None, description="Actual delivery date")
    delivery_reference: Optional[str] = Field(None, description="Delivery reference number/invoice")
    
    technical_specifications: Dict[str, Any] = Field(default_factory=dict, description="Technical specs")
    material_spec_url: Optional[str] = Field(None, description="URL to technical specification document")
    
    unit_cost: Optional[Decimal] = Field(None, description="Cost per unit")
    total_cost: Optional[Decimal] = Field(None, description="Total cost for this material")
    
    status_conflicts: List[str] = Field(default_factory=list, description="IDs of related conflict records")
    last_conflict_check: Optional[datetime] = Field(None, description="Last conflict check timestamp")
    
    created_at: datetime = Field(default_factory=datetime.now, description="Record creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.now, description="Last update timestamp")
    notes: Optional[str] = Field(None, description="Additional notes")
    
    @computed_field
    @property
    def calculated_remaining_required(self) -> Decimal:
        """Calculate remaining required based on ordered and installed."""
        return self.total_ordered - self.total_installed
    
    @computed_field
    @property
    def calculated_total_cost(self) -> Optional[Decimal]:
        """Calculate total cost based on unit cost and ordered quantity."""
        if self.unit_cost is not None:
            return self.unit_cost * self.total_ordered
        return None
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "material_id": "MAT-2024-0892",
            "project_id": "PROJ-2024-001",
            "canonical_name": "Труба ПНД 110",
            "alias_names": ["сотка пндшка", "пнд 110мм", "polyethylene pipe 110"],
            "unit": "meters",
            "total_ordered": 5000.0,
            "total_delivered": 3000.0,
            "total_installed": 1500.0,
            "remaining_required": 3500.0,
            "current_status": "on_site",
            "status_source": "telegram_chat",
            "supplier_name": "СтройМатериалы ООО",
            "expected_delivery_date": "2024-08-20T00:00:00Z",
            "actual_delivery_date": "2024-08-18T00:00:00Z",
            "delivery_reference": "INV-2024-0456",
            "technical_specifications": {
                "diameter": "110mm",
                "pressure_rating": "PN16",
                "wall_thickness": "8.1mm",
                "standard": "GOST 18599-2001"
            },
            "unit_cost": 150.00,
            "total_cost": 750000.00
        }
    })


class DocumentType(str, Enum):
    TECHNICAL_SPECIFICATION = "technical_specification"
    PERMIT_GATI = "permit_gati"
    PERMIT_OATI = "permit_oati"
    EXECUTIVE_BLUEPRINT = "executive_blueprint"
    PROJECT_BLUEPRINT = "project_blueprint"
    INVOICE = "invoice"
    CORPORATE_ACT_KS2 = "corporate_act_ks2"
    CORPORATE_ACT_KS3 = "corporate_act_ks3"
    CONTRACT = "contract"
    EMAIL = "email"
    CHAT_LOG = "chat_log"
    VOICE_TRANSCRIPT = "voice_transcript"
    OTHER = "other"


class StampVerificationStatus(str, Enum):
    NOT_CHECKED = "not_checked"
    VERIFIED_PRESENT = "verified_present"
    VERIFIED_ABSENT = "verified_absent"
    UNCERTAIN = "uncertain"


class DocumentMetadataSchema(BaseModel):
    document_id: str = Field(..., description="Unique document identifier")
    project_id: str = Field(..., description="Associated project ID")
    document_type: DocumentType = Field(..., description="Type of document")
    
    source_url: str = Field(..., description="Source URL")
    source_type: str = Field(..., description="Source system: 'google_drive', 'email', 'telegram'")
    file_name: str = Field(..., description="Original file name")
    file_size_bytes: int = Field(..., description="File size in bytes")
    mime_type: Optional[str] = Field(None, description="File MIME type")
    
    version_index: int = Field(default=1, description="Document version number")
    is_latest_version: bool = Field(default=True, description="Whether this is the latest version")
    previous_version_id: Optional[str] = Field(None, description="ID of previous version")
    next_version_id: Optional[str] = Field(None, description="ID of next version")
    version_conflict_detected: bool = Field(default=False, description="Whether version conflict was detected")
    
    stamps_present: bool = Field(default=False, description="Whether physical stamps were detected")
    stamp_verification_status: StampVerificationStatus = Field(default=StampVerificationStatus.NOT_CHECKED)
    detected_stamps: List[str] = Field(default_factory=list, description="List of detected stamp descriptions")
    
    signatures_present: bool = Field(default=False, description="Whether signatures were detected")
    signature_verification_status: StampVerificationStatus = Field(default=StampVerificationStatus.NOT_CHECKED)
    detected_signatures: List[str] = Field(default_factory=list, description="List of detected signature descriptions")
    
    issuing_authority: Optional[str] = Field(None, description="Organization that issued the document")
    document_date: Optional[datetime] = Field(None, description="Date on the document")


# Object Diary Schemas (RFC v1.9)

class ObjectDiarySchema(BaseModel):
    """Schema for Object Diary (Дневник Объекта) - RFC v1.9"""
    model_config = ConfigDict(use_enum_values=True)
    
    diary_id: Optional[int] = None
    object_name: str
    object_id: str  # Google Drive folder ID
    
    # Информация о заказчике
    customer: Optional[str] = None
    customer_company: Optional[str] = None
    
    # Договорная информация
    contract_date: Optional[datetime] = None
    contract_amount: Optional[float] = None
    contract_number: Optional[str] = None
    
    # Субподрядчики
    subcontractors: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Связи с другими договорами
    parent_contract_id: Optional[str] = None
    sub_contracts: List[str] = Field(default_factory=list)
    
    # Префаза - КП
    has_proposal: bool = False
    proposal_date: Optional[datetime] = None
    proposal_amount: Optional[float] = None
    converted_to_contract: bool = False
    
    # Расширяемые поля
    custom_fields: Dict[str, Any] = Field(default_factory=dict)
    
    # Временная шкала
    events: List["DiaryEventSchema"] = Field(default_factory=list)
    
    # Метаданные
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    # Метаданные для RAG
    rag_metadata: Dict[str, Any] = Field(default_factory=dict)


class DiaryEventSchema(BaseModel):
    """Schema for Diary Event (Событие в дневнике) - RFC v1.9"""
    model_config = ConfigDict(use_enum_values=True)
    
    event_id: Optional[int] = None
    event_type: str  # contract_created, proposal_sent, document_added, etc.
    event_timestamp: datetime
    entity_type: str  # document, contract, payment, etc.
    entity_id: str
    summary: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Версионирование
    overrides_event_id: Optional[int] = None
    is_current: bool = True
    
    # Защита от галлюцинаций - цитирование
    citation_text: Optional[str] = None  # Строка из текста, на основе которой принято решение
    citation_page: Optional[int] = None  # Номер страницы в документе
    citation_bbox: Optional[Dict[str, float]] = None  # Координаты для подсветки (x0, y0, x1, y1)
    citation_confidence: Optional[float] = None  # Уверенность модели (0-1)
    
    # Статус связывания
    requires_verification: bool = False  # Требует ручной проверки
    verification_status: Optional[str] = None  # AUTO_VERIFIED, HUMAN_VERIFIED, CONFLICT
    
    # Темпоральный контекст
    temporal_context: Optional[Dict[str, Any]] = None  # Абсолютное время, относительные переводы


class TemporalContextSchema(BaseModel):
    """Schema for Temporal Context (Темпоральный контекст) - RFC v1.9"""
    model_config = ConfigDict(use_enum_values=True)
    
    current_absolute_time: datetime
    current_day_of_week: str
    relative_translation_map: Dict[str, str] = Field(default_factory=dict)
    # Пример: {"Сегодня": "2026-09-20", "Завтра": "2026-09-21", "Вчера": "2026-09-19"}


class IntentSchema(BaseModel):
    """Schema for Intent (Намерение) - RFC v1.9"""
    model_config = ConfigDict(use_enum_values=True)
    
    intent_id: Optional[int] = None
    domain_intent: str  # MOVE_MATERIAL, SCHEDULE_CHANGE, APPROVAL_REQUEST, etc.
    material_concept: Optional[str] = None  # well_rings_or_chambers, cable, etc.
    source_location_raw: Optional[str] = None
    target_location_raw: Optional[str] = None
    confidence: float
    source_message_id: str  # ID сообщения в Telegram
    extracted_at: datetime = Field(default_factory=datetime.now)


class ConstraintSchema(BaseModel):
    """Schema for Constraint (Ограничение) - RFC v1.9"""
    model_config = ConfigDict(use_enum_values=True)
    
    constraint_id: Optional[int] = None
    object_id: str
    constraint_type: str  # TELCO_APPROVAL, STAMP_OPS, OATI_NOTIFICATION, etc.
    constraint_name: str
    description: str
    required_for_actions: List[str] = Field(default_factory=list)  # Какие действия требуют этого ограничения
    status: str = "NOT_SATISFIED"  # NOT_SATISFIED, SATISFIED, WAIVED
    satisfied_at: Optional[datetime] = None
    deadline: Optional[datetime] = None
    source_document_id: Optional[str] = None
    severity_level: str = "MAJOR"  # CRITICAL, MAJOR, MINOR - цена нарушения ограничений
    bypass_strict_rule: bool = False  # Флаг "Пакта о помиловании" от Метода 3
    bypass_reason: Optional[str] = None  # Причина обхода строгого правила (устное согласование)
    bypass_expiry: Optional[datetime] = None  # Когда истекает действие обхода


class HealthScoreSchema(BaseModel):
    """Schema for Health Score (Индекс Здоровья Объекта) - RFC v1.9"""
    model_config = ConfigDict(use_enum_values=True)
    
    score_id: Optional[int] = None
    object_id: str
    score: float  # 0-100
    zone: str  # GREEN, YELLOW, RED
    calculated_at: datetime = Field(default_factory=datetime.now)
    contributing_events: List[Dict[str, Any]] = Field(default_factory=list)
    risk_factors: List[str] = Field(default_factory=list)  # Описание факторов риска


class ExpertLessonSchema(BaseModel):
    """Schema for Expert Lesson (Экспертный урок) - RFC v1.9"""
    model_config = ConfigDict(use_enum_values=True)
    
    lesson_id: Optional[int] = None
    doc_category: str  # TECHNICAL_PROJECT, SPECIFICATION, ESTIMATE
    
    # Смысловые якоря (Теги интерфейса: "Ростелеком", "Канализация КК", "МГГТ")
    context_tags: List[str] = Field(default_factory=list)
    
    # Текстовый слепок и вектор страницы для RAG
    raw_page_text: str
    anchor_text_embedding_id: str
    
    # Суть урока и комментарий инженера
    expert_commentary: str  # Пример: "Ростелеком требует кабель с пометкой HF"
    
    # Граница применимости девиации (Выводится Девином автоматически)
    applicability_scope: Dict[str, Any] = Field(default_factory=dict)
    # Пример: {"customer": "Ростелеком", "work_type": "канализация", "component": "кабель"}
    
    created_at: datetime = Field(default_factory=datetime.now)
    verified_by_human: bool = False


class DelegationRequestSchema(BaseModel):
    """Schema for Delegation Request (Запрос делегирования) - RFC v1.9"""
    model_config = ConfigDict(use_enum_values=True)
    
    request_id: Optional[int] = None
    requester_id: str  # Кто делегирует
    target_name: str  # Кого делегируем (например, "Света")
    question_context: str  # Контекст вопроса
    object_id: str  # Объект, к которому относится вопрос
    created_at: datetime = Field(default_factory=datetime.now)
    status: str = "PENDING"  # PENDING, DELEGATED, ANSWERED


class DelegatedQuestionSchema(BaseModel):
    """Schema for Delegated Question (Делегированный вопрос) - RFC v1.9"""
    model_config = ConfigDict(use_enum_values=True)
    
    question_id: Optional[int] = None
    original_request_id: int
    assigned_user_id: str  # Кому делегирован
    assigned_user_role: str  # PURCHASING, LEGAL, etc.
    communication_channel: str  # PRIVATE (ЛС) or PUBLIC (общий чат)
    message_sent: bool = False
    answer_received: bool = False
    answer_text: Optional[str] = None
    answer_timestamp: Optional[datetime] = None
    deadline_for_reply: Optional[datetime] = None  # Дедлайн для ответа
    reminder_count: int = 0  # Количество напоминаний
    escalation_status: str = "NONE"  # NONE, REMINDED, ESCALATED
    escalated_to_user_id: Optional[str] = None  # Кому эскалирован (если не ответили)
    escalation_timestamp: Optional[datetime] = None


# CodeCandidate and Security Schemas (RFC-032)

class CodeCandidateSchema(BaseModel):
    """Schema for Code Candidate (Кандидат кода) - RFC-032"""
    model_config = ConfigDict(use_enum_values=True)
    
    candidate_id: Optional[int] = None
    candidate_type: str  # CODE, SQL_QUERY, PROMPT
    source_model: str  # gemma-3-12b, qwen-3-coder-14b
    generated_code: str
    target_module: str  # diary_manager, constraint_manager, etc.
    source_context: str  # Контекст генерации (какой запрос пользователя)
    status: str = "PENDING"  # PENDING, APPROVED, REJECTED, BLOCKED
    sha256_hash: str  # Хэш для допуска
    smoke_test_result: Optional[str] = None  # SMOKE_OK, SMOKE_FAILED
    created_at: datetime = Field(default_factory=datetime.now)
    approved_at: Optional[datetime] = None
    approved_by: Optional[str] = None  # "devin" или архитектор


class HashBoundSchema(BaseModel):
    """Schema for Hash-Bound Resource (Подписанный ресурс) - RFC-032"""
    model_config = ConfigDict(use_enum_values=True)
    
    hash_id: Optional[int] = None
    resource_type: str  # PROMPT, SQL_TEMPLATE, VALIDATION_RULE
    resource_path: str  # Путь к файлу в системе
    sha256_hash: str
    resource_content: str
    status: str = "ACTIVE"  # ACTIVE, BLOCKED, REVOKED
    created_at: datetime = Field(default_factory=datetime.now)
    last_verified: datetime = Field(default_factory=datetime.now)
    verified_by: str  # "devin" или архитектor
    valid_from: Optional[datetime] = Field(None, description="Document validity start date")
    valid_until: Optional[datetime] = Field(None, description="Document validity end date")
    document_number: Optional[str] = Field(None, description="Document number/identifier")
    
    processed_at: datetime = Field(default_factory=datetime.now, description="Vision processing timestamp")
    processing_status: str = Field(default="pending", description="Processing status")
    processing_errors: List[str] = Field(default_factory=list, description="Processing error messages")
    
    extracted_text_summary: Optional[str] = Field(None, description="Brief summary of extracted text")
    key_entities: List[str] = Field(default_factory=list, description="Key entities mentioned in document")
    monetary_amounts: List[float] = Field(default_factory=list, description="Monetary amounts found in document")
    dates_mentioned: List[str] = Field(default_factory=list, description="Dates mentioned in document")
    
    chunk_count: int = Field(default=0, description="Number of chunks created for RAG")
    chunk_ids: List[str] = Field(default_factory=list, description="IDs of chunks in vector database")
    
    related_document_ids: List[str] = Field(default_factory=list, description="IDs of related documents")
    referenced_in_chat_ids: List[str] = Field(default_factory=list, description="Chat messages referencing this document")
    
    created_at: datetime = Field(default_factory=datetime.now, description="Record creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.now, description="Last update timestamp")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "document_id": "DOC-2024-0892",
            "project_id": "PROJ-2024-001",
            "document_type": "permit_gati",
            "source_url": "https://drive.google.com/file/d/1AbCdEfGhIjKlMnOpQrStUvWxYz",
            "source_type": "google_drive",
            "file_name": "ГАТИ_Разрешение_Сектор7_2024.pdf",
            "file_size_bytes": 2456789,
            "mime_type": "application/pdf",
            "version_index": 2,
            "is_latest_version": True,
            "previous_version_id": "DOC-2024-0891",
            "stamps_present": True,
            "stamp_verification_status": "verified_present",
            "detected_stamps": ["City Administration Stamp", "GATI Approval Stamp"],
            "signatures_present": True,
            "signature_verification_status": "verified_present",
            "detected_signatures": ["Chief Engineer Signature", "Director Signature"],
            "issuing_authority": "City Administration - GATI Department",
            "document_date": "2024-08-01T00:00:00Z",
            "valid_from": "2024-08-01T00:00:00Z",
            "valid_until": "2025-08-01T00:00:00Z",
            "document_number": "ГАТИ-2024-0456",
            "processed_at": "2024-08-17T03:30:00Z",
            "processing_status": "completed",
            "extracted_text_summary": "Permit for underground cable duct construction in Sector 7...",
            "key_entities": ["City Administration", "Sector 7", "Cable Duct Construction"],
            "monetary_amounts": [5000000.0],
            "chunk_count": 15,
            "chunk_ids": ["CHUNK-DOC-2024-0892-001", "CHUNK-DOC-2024-0892-002"]
        }
    })


class NotificationStatus(str, Enum):
    NOT_NOTIFIED = "not_notified"
    SCHEDULED = "scheduled"
    NOTIFIED = "notified"
    ACKNOWLEDGED = "acknowledged"
    FAILED = "failed"


class DeadlineRegistrySchema(BaseModel):
    id: int = Field(..., description="Auto-incrementing primary key")
    project_id: str = Field(..., description="Associated project ID")
    event_id: str = Field(..., description="Reference to ExtractedEventSchema.event_id")
    
    event_type: str = Field(..., description="Type of event")
    event_title: str = Field(..., description="Human-readable event title")
    target_date: datetime = Field(..., description="Target date for the event")
    
    target_telegram_chat_id: int = Field(..., description="Telegram chat ID to send notifications to")
    additional_notify_user_ids: List[int] = Field(default_factory=list, description="Additional specific user IDs to notify")
    
    notification_threshold_days: int = Field(default=30, description="Days before event to notify")
    notification_threshold_hours: Optional[int] = Field(None, description="Hours before event for urgent notifications")
    
    source_reference_url: Optional[str] = Field(None, description="URL to source document")
    source_reference_id: Optional[str] = Field(None, description="ID of source document/message")
    
    notified_status: NotificationStatus = Field(default=NotificationStatus.NOT_NOTIFIED)
    first_notification_sent_at: Optional[datetime] = Field(None, description="Timestamp of first notification")
    last_notification_sent_at: Optional[datetime] = Field(None, description="Timestamp of most recent notification")
    notification_count: int = Field(default=0, description="Number of notifications sent")
    notification_error_message: Optional[str] = Field(None, description="Error message if notification failed")
    
    event_status: str = Field(default="upcoming", description="Event status")
    event_completed_at: Optional[datetime] = Field(None, description="Actual event completion timestamp")
    
    created_at: datetime = Field(default_factory=datetime.now, description="Record creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.now, description="Last update timestamp")
    notes: Optional[str] = Field(None, description="Additional notes")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "id": 1,
            "project_id": "PROJ-2024-001",
            "event_id": "EVENT-2024-0892",
            "event_type": "permit_expiration",
            "event_title": "ГАТИ Permit Expiration",
            "target_date": "2027-04-12T00:00:00Z",
            "target_telegram_chat_id": -1001234567890,
            "additional_notify_user_ids": [123456789, 987654321],
            "notification_threshold_days": 30,
            "notification_threshold_hours": None,
            "source_reference_url": "https://drive.google.com/file/d/1AbCdEfGhIjKlMnOpQrStUvWxYz",
            "source_reference_id": "DOC-2024-0892",
            "notified_status": "not_notified",
            "first_notification_sent_at": None,
            "last_notification_sent_at": None,
            "notification_count": 0,
            "notification_error_message": None,
            "event_status": "upcoming",
            "event_completed_at": None,
            "created_at": "2024-08-17T10:30:00Z",
            "updated_at": "2024-08-17T10:30:00Z"
        }
    })


class EventType(str, Enum):
    PERMIT_EXPIRATION = "permit_expiration"
    CLIENT_MEETING = "client_meeting"
    MATERIAL_DELIVERY = "material_delivery"
    INSPECTION = "inspection"
    DEADLINE = "deadline"
    MILESTONE = "milestone"
    PAYMENT_DUE = "payment_due"
    CONTRACT_RENEWAL = "contract_renewal"
    OTHER = "other"


class DateExtractionMethod(str, Enum):
    EXPLICIT_DATE = "explicit_date"
    RELATIVE_PHRASE = "relative_phrase"
    DURATION_FROM_DATE = "duration_from_date"
    INFERRED = "inferred"
    MANUAL = "manual"


class ExtractedEventSchema(BaseModel):
    event_id: str = Field(..., description="Unique event identifier")
    project_id: str = Field(..., description="Associated project ID")
    event_type: EventType = Field(..., description="Type of event")
    
    raw_text: str = Field(..., description="Original text containing the event information")
    source_document_id: Optional[str] = Field(None, description="ID of document where event was found")
    source_chat_message_id: Optional[str] = Field(None, description="ID of chat message where event was found")
    source_type: str = Field(..., description="Source type: 'document', 'chat', 'email', 'manual'")
    
    original_date_phrase: str = Field(..., description="Original date phrase as found in text")
    extraction_method: DateExtractionMethod = Field(..., description="Method used for date extraction")
    extraction_confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence in extraction (0-1)")
    
    target_date: datetime = Field(..., description="Normalized target date in ISO 8601 format")
    target_date_timezone: str = Field(default="UTC", description="Timezone for target date")
    
    is_duration_based: bool = Field(default=False, description="Whether event is based on a duration")
    duration_start_date: Optional[datetime] = Field(None, description="Start date for duration-based events")
    duration_value: Optional[int] = Field(None, description="Duration value (number of units)")
    duration_unit: Optional[str] = Field(None, description="Duration unit: 'days', 'months', 'years'")
    
    event_title: str = Field(..., description="Human-readable event title")
    event_description: Optional[str] = Field(None, description="Detailed event description")
    location: Optional[str] = Field(None, description="Event location (if applicable)")
    participants: List[str] = Field(default_factory=list, description="List of participants/attendees")
    
    importance_level: str = Field(default="medium", description="Importance: 'low', 'medium', 'high', 'critical'")
    notification_threshold_days: int = Field(default=30, description="Days before event to start notifications")
    notification_threshold_hours: Optional[int] = Field(None, description="Hours before event for immediate notifications")
    
    reference_url: Optional[str] = Field(None, description="URL to source document/reference")
    reference_text: Optional[str] = Field(None, description="Contextual text around the event mention")
    
    extracted_at: datetime = Field(default_factory=datetime.now, description="Event extraction timestamp")
    extracted_by: str = Field(..., description="System or user who extracted the event")
    verified: bool = Field(default=False, description="Whether event has been verified by human")
    verified_by: Optional[str] = Field(None, description="User ID who verified the event")
    verified_at: Optional[datetime] = Field(None, description="Verification timestamp")
    
    event_status: str = Field(default="upcoming", description="Status: 'upcoming', 'in_progress', 'completed', 'cancelled', 'missed'")
    completed_at: Optional[datetime] = Field(None, description="Actual completion timestamp")
    completion_notes: Optional[str] = Field(None, description="Notes on event completion")
    
    related_conflict_ids: List[str] = Field(default_factory=list, description="IDs of related conflicts")
    related_material_ids: List[str] = Field(default_factory=list, description="IDs of related materials")
    
    @field_validator('target_date')
    @classmethod
    def validate_iso8601(cls, v):
        if not isinstance(v, datetime):
            raise ValueError('target_date must be a datetime object')
        return v
    
    @field_validator('extraction_confidence')
    @classmethod
    def validate_confidence(cls, v):
        if not 0.0 <= v <= 1.0:
            raise ValueError('extraction_confidence must be between 0 and 1')
        return v
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "event_id": "EVENT-2024-0892",
            "project_id": "PROJ-2024-001",
            "event_type": "permit_expiration",
            "raw_text": "Разрешение ГАТИ действительно в течение 3 лет начиная с 12.04.2024",
            "source_document_id": "DOC-2024-0892",
            "source_type": "document",
            "original_date_phrase": "в течение 3 лет начиная с 12.04.2024",
            "extraction_method": "duration_from_date",
            "extraction_confidence": 0.95,
            "target_date": "2027-04-12T00:00:00Z",
            "target_date_timezone": "UTC",
            "is_duration_based": True,
            "duration_start_date": "2024-04-12T00:00:00Z",
            "duration_value": 3,
            "duration_unit": "years",
            "event_title": "ГАТИ Permit Expiration",
            "event_description": "GATI permit for Sector 7 construction expires",
            "importance_level": "critical",
            "notification_threshold_days": 30,
            "reference_url": "https://drive.google.com/file/d/1AbCdEfGhIjKlMnOpQrStUvWxYz",
            "extracted_at": "2024-08-17T10:30:00Z",
            "extracted_by": "mia_night_processor",
            "verified": False,
            "event_status": "upcoming"
        }
    })


class NomenclatureMapping(BaseModel):
    """Schema for nomenclature name mapping with persistence support."""
    
    mapping_id: str = Field(..., description="Unique mapping identifier")
    canonical_name: str = Field(..., description="Canonical item name")
    alias_names: List[str] = Field(default_factory=list, description="List of alias names mapped to canonical")
    project_id: str = Field(..., description="Associated project ID")
    material_category: Optional[str] = Field(None, description="Material category")
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence in mapping accuracy")
    created_at: datetime = Field(default_factory=datetime.now, description="Mapping creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.now, description="Last update timestamp")
    verified_by: Optional[str] = Field(None, description="User ID who verified the mapping")
    verified_at: Optional[datetime] = Field(None, description="Verification timestamp")
    usage_count: int = Field(default=0, description="Number of times this mapping was used")
    
    @field_validator('confidence_score')
    @classmethod
    def validate_confidence(cls, v):
        if not 0.0 <= v <= 1.0:
            raise ValueError('confidence_score must be between 0 and 1')
        return v
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "mapping_id": "NOM-2024-0892",
            "canonical_name": "Труба ПНД 110",
            "alias_names": ["сотка пндшка", "пнд 110мм", "polyethylene pipe 110"],
            "project_id": "PROJ-2024-001",
            "material_category": "pipes",
            "confidence_score": 0.95,
            "verified_by": "admin_123",
            "usage_count": 15
        }
    })


# Questions Gateway Schema

class QuestionStatus(str, Enum):
    OPEN = "open"
    ANSWERED = "answered"
    DEFERRED = "deferred"
    INVALID = "invalid"


class QuestionPriority(str, Enum):
    CRITICAL = "critical"  # Financial decisions, legal compliance
    HIGH = "high"        # Material sourcing, permit issues
    NORMAL = "normal"    # Scheduling conflicts
    LOW = "low"          # Informational clarifications


class QuestionGatewaySchema(BaseModel):
    question_id: str = Field(..., description="Unique question identifier")
    question_type: str = Field(..., description="Type of construction question")
    status: QuestionStatus = Field(default=QuestionStatus.OPEN)
    priority: QuestionPriority = Field(default=QuestionPriority.NORMAL)
    
    # Construction Context
    project_id: str = Field(..., description="Associated project ID")
    related_schema_type: str = Field(..., description="Schema that triggered the question")
    related_entity_id: str = Field(..., description="Entity ID requiring clarification")
    
    # Question Content
    question_markdown: str = Field(..., description="Human-readable question in Markdown")
    option_a: str = Field(..., description="Option A (e.g., 'Use higher estimate')")
    option_b: str = Field(..., description="Option B (e.g., 'Request clarification')")
    option_c: Optional[str] = Field(None, description="Optional third option")
    
    # Task Suspension
    suspended_task_id: Optional[str] = Field(None, description="LLM task ID put on pause")
    suspended_task_type: Optional[str] = Field(None, description="Type of suspended task")
    
    # Safety & Integrity
    shadow_file_path: Optional[str] = Field(None, description="Path to shadow copy for safe reading")
    file_mtime: Optional[datetime] = Field(None, description="File modification time for stability check")
    integrity_regex_match: bool = Field(default=True, description="Regex validation of block integrity")
    
    # Resolution
    resolved_by: Optional[str] = Field(None, description="Telegram user ID who resolved")
    resolved_option: Optional[str] = Field(None, description="Which option was chosen")
    resolution_notes: Optional[str] = Field(None, description="Additional notes on resolution")
    
    created_at: datetime = Field(default_factory=datetime.now)
    answered_at: Optional[datetime] = Field(None)
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "question_id": "Q-2024-0892",
            "question_type": "budget_conflict",
            "status": "open",
            "priority": "critical",
            "project_id": "PROJ-2024-001",
            "related_schema_type": "FinancialReportSchema",
            "related_entity_id": "FIN-2024-0892",
            "question_markdown": "# Budget Conflict Resolution\n\nKS-2 act #456 shows 500,000 RUB for cable trays, but FinancialReportSchema shows 450,000 RUB.\n\n## Options:\n**(a)** Use KS-2 amount (higher estimate, conservative approach)\n**(b)** Use FinancialReportSchema amount (requires investigation)",
            "option_a": "Use KS-2 amount (500,000 RUB)",
            "option_b": "Use FinancialReportSchema amount (450,000 RUB)",
            "suspended_task_id": "TASK-2024-1234",
            "suspended_task_type": "analyze_document_vision"
        }
    })


# Audit Gap Schema

class AuditSeverity(str, Enum):
    CRITICAL = "critical"  # Legal compliance, financial risks
    HIGH = "high"        # Timeline risks, major inconsistencies
    MEDIUM = "medium"    # Documentation gaps, minor discrepancies
    LOW = "low"          # Informational, optimization opportunities


class AuditGapSchema(BaseModel):
    audit_id: str = Field(..., description="Unique audit identifier")
    severity: AuditSeverity = Field(..., description="Risk level of identified gap")
    gap_type: str = Field(..., description="Type of construction gap")
    
    # Affected Entities
    project_id: str = Field(..., description="Associated project ID")
    affected_schemas: List[str] = Field(..., description="Schemas involved in the gap")
    affected_entity_ids: List[str] = Field(..., description="Entity IDs with conflicts")
    
    # Gap Description
    title: str = Field(..., description="Human-readable gap title")
    description: str = Field(..., description="Detailed gap description")
    detected_by: str = Field(..., description="Audit pattern that detected this gap")
    
    # Evidence from Schemas
    evidence_data: Dict[str, Any] = Field(default_factory=dict, description="Evidence from schema queries")
    expected_state: str = Field(..., description="What the state should be")
    actual_state: str = Field(..., description="What the state actually is")
    
    # RAG Investigation
    rag_performed: bool = Field(default=False, description="Whether RAG search was performed")
    rag_results: List[str] = Field(default_factory=list, description="Relevant document references")
    documents_found: bool = Field(default=False, description="Whether supporting documents exist")
    
    # Resolution Tracking
    auto_resolution_attempted: bool = Field(default=False, description="Whether auto-resolution was tried")
    auto_resolution_successful: bool = Field(default=False, description="Whether auto-resolution succeeded")
    manual_action_required: bool = Field(default=True, description="Whether human intervention needed")
    
    # Integration with Questions Gateway
    question_gateway_id: Optional[str] = Field(None, description="Linked question if auto-created")
    checklist_item: Optional[str] = Field(None, description="Morning checklist item if needed")
    
    created_at: datetime = Field(default_factory=datetime.now)
    resolved_at: Optional[datetime] = Field(None)
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "audit_id": "AUDIT-2024-0892",
            "severity": "high",
            "gap_type": "document_missing",
            "project_id": "PROJ-2024-001",
            "affected_schemas": ["DocumentMetadataSchema", "DeadlineRegistrySchema"],
            "affected_entity_ids": ["DOC-2024-0892", "DEAD-2024-0456"],
            "title": "Missing Act of Hidden Works for Ventilation Permit",
            "description": "Permit GATI-2024-0456 exists for ventilation installation, but no corresponding acts of hidden works found in DocumentMetadataSchema for air duct installation.",
            "detected_by": "contract_document_gap_audit",
            "evidence_data": {
                "permit_found": True,
                "permit_expiry": "2027-04-12",
                "hidden_works_acts": 0,
                "ventilation_related_docs": 1
            },
            "expected_state": "Multiple acts of hidden works for air duct installation",
            "actual_state": "No acts of hidden works found",
            "rag_performed": True,
            "rag_results": ["VENT-2024-001", "VENT-2024-002"],
            "documents_found": False,
            "manual_action_required": True,
            "checklist_item": "Verify ventilation installation progress and missing documentation"
        }
    })


# Doctor Diagnosis Schema

class AnomalyType(str, Enum):
    SEMANTIC_REPETITION = "semantic_repetition"  # Construction assistant fixation
    META_SLIP = "meta_slip"                      # "As an AI" slip in construction context
    WORKER_HANG = "worker_hang"                  # Task stuck in processing > 10 min
    VRAM_LEAK = "vram_leak"                      # Unusual VRAM growth pattern
    RESPONSE_DEGRADATION = "response_degradation"  # Quality drop in construction advice


class AnomalySeverity(str, Enum):
    CRITICAL = "critical"  # Immediate intervention required
    HIGH = "high"        # Director notification required
    MEDIUM = "medium"    # Logging and monitoring
    LOW = "low"          # Informational only


class DoctorDiagnosisSchema(BaseModel):
    diagnosis_id: str = Field(..., description="Unique diagnosis identifier")
    anomaly_type: AnomalyType = Field(..., description="Type of anomaly detected")
    severity: AnomalySeverity = Field(..., description="Severity level")
    
    # Health Metrics
    semantic_jaccard_score: Optional[float] = Field(None, description="Jaccard similarity (3-grams)")
    meta_slip_pattern: Optional[str] = Field(None, description="Detected meta slip phrase")
    worker_hang_duration_minutes: Optional[int] = Field(None, description="Task stuck duration")
    vram_growth_mb: Optional[int] = Field(None, description="VRAM growth anomaly")
    response_quality_score: Optional[float] = Field(None, description="Response quality metric")
    
    # Construction Context
    construction_context: str = Field(..., description="Construction scenario where anomaly occurred")
    related_project_id: Optional[str] = Field(None, description="Project context if applicable")
    affected_task_type: Optional[str] = Field(None, description="Task type affected")
    
    # Diagnosis Details
    diagnosis_description: str = Field(..., description="Human-readable diagnosis")
    technical_details: Dict[str, Any] = Field(default_factory=dict, description="Technical evidence")
    
    # Recommended Actions
    recommended_actions: List[str] = Field(..., description="Recommended remediation steps")
    parameter_adjustments: Optional[Dict[str, Any]] = Field(None, description="Suggested parameter changes")
    
    # G8 Principle Integration
    self_action_forbidden: bool = Field(default=True, description="Doctor cannot self-restart processes")
    requires_director_approval: bool = Field(default=True, description="Director approval required")
    
    # Questions Gateway Integration
    question_gateway_id: Optional[str] = Field(None, description="Auto-created TECH question")
    telegram_notification_sent: bool = Field(default=False, description="Director notified via Telegram")
    
    detected_at: datetime = Field(default_factory=datetime.now)
    resolved_at: Optional[datetime] = Field(None)
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "diagnosis_id": "DIAG-2024-0892",
            "anomaly_type": "semantic_repetition",
            "severity": "high",
            "semantic_jaccard_score": 0.52,
            "construction_context": "Material status query for cable trays",
            "related_project_id": "PROJ-2024-001",
            "affected_task_type": "get_material_status",
            "diagnosis_description": "Detected semantic repetition in material status responses. Assistant appears stuck in paraphrase loop, repeatedly suggesting 'check with supplier' without processing actual data.",
            "technical_details": {
                "last_5_responses": ["Check with supplier", "Supplier should confirm", "Verify with supplier", "Contact supplier", "Supplier confirmation needed"],
                "jaccard_3gram_scores": [0.48, 0.52, 0.51, 0.49, 0.52],
                "schema_access_count": 12,
                "actual_schema_queries": 0
            },
            "recommended_actions": [
                "Reduce temperature from 0.7 to 0.5",
                "Increase repeat_penalty from 1.0 to 1.2",
                "Soft restart of material status tool execution"
            ],
            "parameter_adjustments": {
                "temperature": 0.5,
                "repeat_penalty": 1.2
            },
            "self_action_forbidden": True,
            "requires_director_approval": True
        }
    })


class AuditLogSchema(BaseModel):
    """Schema for audit log tracking system changes."""
    
    audit_id: Optional[int] = Field(None, description="Unique audit log ID")
    timestamp: datetime = Field(default_factory=datetime.now, description="When the action occurred")
    actor: str = Field(..., description="Who performed the action (user_id or 'system')")
    action: str = Field(..., description="Action type (create, update, delete, approve, reject)")
    entity_type: str = Field(..., description="Type of entity (object_diary, document, contract, etc.)")
    entity_id: str = Field(..., description="ID of the affected entity")
    old_value: Optional[Dict[str, Any]] = Field(None, description="Previous value (before change)")
    new_value: Optional[Dict[str, Any]] = Field(None, description="New value (after change)")
    approval_chain: List[str] = Field(default_factory=list, description="Who approved this change")
    origin: str = Field(..., description="Origin of change (manual, llm_generated, automated)")
    trace_id: str = Field(..., description="Trace ID for linking related operations")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "audit_id": 1,
            "timestamp": "2024-10-05T15:30:00Z",
            "actor": "user_123456789",
            "action": "update",
            "entity_type": "object_diary",
            "entity_id": "DIARY-2024-001",
            "old_value": {"status": "pending", "confidence": 0.75},
            "new_value": {"status": "approved", "confidence": 0.92},
            "approval_chain": ["denis_kuleshov", "alexey_kalachev"],
            "origin": "llm_generated",
            "trace_id": "TRACE-2024-0892"
        }
    })


class ComponentStatusSchema(BaseModel):
    """Schema for system component status tracking."""
    
    component_name: str = Field(..., description="Component identifier (telegram_bot, worker_pool, llm_server, etc.)")
    status: str = Field(..., description="Component status (running, stopped, error, starting, stopping)")
    pid: Optional[int] = Field(None, description="Process ID if running")
    uptime: Optional[float] = Field(None, description="Uptime in seconds")
    last_heartbeat: Optional[datetime] = Field(None, description="Last heartbeat timestamp")
    error_message: Optional[str] = Field(None, description="Error message if in error state")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "component_name": "telegram_bot",
            "status": "running",
            "pid": 12345,
            "uptime": 7200.5,
            "last_heartbeat": "2024-10-05T15:30:00Z",
            "error_message": None
        }
    })