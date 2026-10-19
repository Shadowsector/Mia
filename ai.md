# Mia Construction Project Management OS - Agentic Tool-Calling Architecture

## Executive Summary

**UPGRADE STRATEGY**: This RFC is designed as a comprehensive upgrade to the existing Mia project located at `C:\mia\`. The current implementation (Stage 0) provides a solid foundation with Telegram bot, SQLite + ChromaDB memory, and Ollama integration. This specification defines the architectural evolution to an autonomous, agentic system with enhanced capabilities while preserving the proven foundation.

Mia is an autonomous AI agent for construction project management that operates through native Tool Calling (Function Calling) capabilities. Unlike traditional command-based systems, Mia uses natural language understanding to autonomously decide which tools to invoke based on context and intent. This architecture is optimized for local deployment on single-GPU systems (RTX 5060) with smaller LLMs (Gemma 3 12B / Qwen 3 Coder 14B via Ollama).

**Design Philosophy**: Mia runs as an autonomous Agent Loop that can invoke tools dynamically based on cognitive decision-making. No slash commands, no rigid routing - just natural language understanding and intelligent tool selection.

---

## Upgrade Roadmap from Existing Mia (C:\mia\)

### Current Foundation (What Works Well)
✅ **Telegram Bot**: python-telegram-bot 21.6+ with message handling  
✅ **Storage**: SQLite + ChromaDB with bge-m3 embeddings  
✅ **Ollama Integration**: Native API for chat and embeddings  
✅ **Cross-Chat Memory**: Remembers information sources and connects insights  
✅ **Document Ingestion**: docx, xlsx, xls, pdf with OCR capability  
✅ **Configurator**: Tkinter GUI for model management and updates  
✅ **Timezone Support**: Europe/Moscow timezone handling  
✅ **Authoritative Sources**: User credibility tracking system  

### Strategic Upgrades Required

**1. FROM: Command-Based → TO: Agentic Tool-Calling**
- **Current**: Fixed intent detection with hardcoded responses
- **Upgrade**: Autonomous Agent Loop with dynamic tool selection
- **Benefit**: Mia can intelligently decide which tools to use based on context

**2. FROM: AnythingLLM RAG → TO: Hybrid RAG**
- **Current**: External AnythingLLM dependency for document queries
- **Upgrade**: Built-in Hybrid RAG (SQL + Vector + Joint retrieval)
- **Benefit**: Single codebase, no external dependencies, better control

**3. FROM: Basic Memory → TO: Structured Schema System**
- **Current**: Simple message storage and vector search
- **Upgrade**: Full Pydantic v2 schemas (Financial, Material, Document, Deadline, Event, Nomenclature)
- **Benefit**: Type-safe data management, automated validation, complex queries

**4. FROM: Single-Threaded Blocking → TO: Priority-Based Task Queue**
- **Current**: Synchronous LLM calls blocking telegram event loop
- **Upgrade**: SQLite-backed priority queue with single-threaded worker
- **Benefit**: Non-blocking UI, proper VRAM management on RTX 5060

**5. FROM: Manual Vision → TO: Unified Multimodal Model**
- **Current**: Separate vision model (qwen2.5vl:7b) causing VRAM swapping
- **Upgrade**: Single multimodal model (gemma3:12b or qwen2.5-coder:14b)
- **Benefit**: Zero VRAM collisions, simplified deployment

**6. FROM: Informal Trust → TO: Formal RBAC System**
- **Current**: Basic `is_authoritative` flag
- **Upgrade**: Full Role-Based Access Control with permission matrices
- **Benefit**: Granular financial data access, proper security boundaries

### Preservation Strategy
**Keep These Components**:
- `mia/core/llm.py` - Ollama client structure (add runtime model switching)
- `mia/memory/database.py` - SQLite schema (extend with new tables)
- `mia/memory/vector_store.py` - ChromaDB integration (enhance with Hybrid RAG)
- `configurator/` - GUI framework (extend with new configuration options)
- Telegram message handling pattern (upgrade to agent-based responses)

**Refactor These Components**:
- `mia/assistant/service.py` - Replace with Agent Loop orchestration
- `mia/bot/handlers/` - Upgrade to context-building and tool calling
- Schema definitions - Migrate to comprehensive Pydantic v2 system
- Document processing - Integrate with structured extraction pipeline

### Additional Improvement Recommendations

**1. Enhanced Context Building**
- Add parent thread capture (reply_to_message_id) as per current system
- Implement sliding window of last 10 messages for pronoun resolution
- Add `system_current_time` injection for relative date calculations

**2. Safe Tool Interfaces**
- Replace any potential SQL generation with safe semantic tools
- Implement automated tool schema generation from function signatures
- Add permission-aware tool execution with RBAC integration

**3. Vision and OCR Integration**
- Integrate existing OCR capability with structured document analysis
- Add stamp/signature verification for permits and contracts
- Implement version conflict detection for document revisions

**4. Registry and Reporting**
- Enhance existing xlsx summary generation with structured schemas
- Add deadline registry with automatic notification system
- Implement cross-project precedent intelligence

**5. Nomenclature Mapping**
- Formalize the existing material name aliases into persistent storage
- Add confidence scoring and usage tracking
- Integrate with conflict resolution system

**6. Runtime Configuration**
- Preserve runtime.json for hot model switching
- Add unified multimodal model configuration
- Extend configurator with new tool management interface

---

## 1. Agentic Architecture Overview

### 1.1 Agent Loop Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         MIA AGENT LOOP CORE                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  INPUT: Natural Language Message (Telegram)                                  │
│           │                                                                  │
│           ▼                                                                  │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  CONTEXT BUILDER                                                      │  │
│  │  - Capture parent thread (reply_to_message_id)                         │  │
│  │  - Sliding window of last 10 messages for pronoun resolution           │  │
│  │  - Inject system_current_time for chronological awareness              │  │
│  │  - RBAC verification                                                   │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│           │                                                                  │
│           ▼                                                                  │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  TOOL CALLING ENGINE (Autonomous Decision)                            │  │
│  │  - Analyze intent using natural language understanding                │  │
│  │  - Select appropriate tools dynamically                              │  │
│  │  - Generate tool calls with parameters                               │  │
│  │  - Handle multi-step reasoning chains                               │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│           │                                                                  │
│           ▼                                                                  │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  TOOL EXECUTION LAYER                                                 │  │
│  │  Available Tools:                                                      │  │
│  │  - bind_project_to_chat()                                             │  │
│  │  - get_project_financials() (safe semantic method)                                              │  │
│  │  - search_vector_rag()                                               │  │
│  │  - register_deadline()                                                │  │
│  │  - resolve_nomenclature_alias()                                      │  │
│  │  - process_chat_summary()                                            │  │
│  │  - analyze_document_vision()                                          │  │
│  │  - check_project_status()                                            │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│           │                                                                  │
│           ▼                                                                  │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  UNIFIED TASK QUEUE (SQLite)                                          │  │
│  │  Priority Matrix:                                                      │  │
│  │  - Priority 10: Real-time admin tags (immediate)                       │  │
│  │  - Priority 8: User queries (high)                                    │  │
│  │  - Priority 5: Chat summarization (normal)                            │  │
│  │  - Priority 3: Document analysis (low)                                │  │
│  │  - Priority 1: Night vision chunking (background)                     │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│           │                                                                  │
│           ▼                                                                  │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  SINGLE-THREADED WORKER POOL (Zero VRAM Collisions)                 │  │
│  │  - One active LLM inference at a time                                │  │
│  │  - Priority-based task scheduling                                   │  │
│  │  - Direct response delivery on completion                            │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│           │                                                                  │
│           ▼                                                                  │
│  RESPONSE: Natural Language Response with Tool Results                      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Key Architectural Principles

1. **No Slash Commands**: Mia understands natural language requests like "Bind this chat to the Sector 7 project" instead of `/bind_project`
2. **Autonomous Tool Selection**: Mia decides which tools to call based on context, not rigid routing
3. **Unified Task Queue**: All LLM operations go through one priority-based queue
4. **Single-Threaded Execution**: Prevents VRAM collisions on RTX 5060
5. **Context Awareness**: Thread context and temporal awareness for accurate responses
6. **Natural Language First**: Construction teams communicate naturally, not with commands

---

## 2. Core Pydantic Schemas (Agentic)

### 2.1 Enhanced LLM Task Schema

```python
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum

class LedgerEntityType(str, Enum):
    DOCUMENT = "document"
    CHAT_FACT = "chat_fact"
    FINANCIAL = "financial"
    MATERIAL = "material"

class LedgerEventSchema(BaseModel):
    model_config = ConfigDict(use_enum_values=True)
    
    ledger_id: Optional[int] = None
    project_id: str
    event_timestamp: datetime = Field(..., description="Chronological date when this statement became true")
    entity_type: LedgerEntityType
    entity_id: str
    revision_index: int = Field(default=0)
    overrides_ledger_id: Optional[int] = Field(default=None)
    summary_delta: str = Field(..., description="Short explanation of what explicitly changed/overrode old data")
    metadata: Dict[str, Any] = Field(default_factory=dict)

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
    
    # FIX 2: Chronological Awareness
    system_current_time: datetime = Field(..., description="Current system time for relative date calculations")
    user_timezone: Optional[str] = Field(default="UTC", description="User's timezone for context")
    
    # FIX 3: Context Window
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
    
    # Results
    tool_results: List[Dict[str, Any]] = Field(default_factory=list, description="Results from tool executions")
    final_response: Optional[str] = Field(None, description="Agent's final response")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Agent confidence in response")
    
    # Error Handling
    error_message: Optional[str] = Field(None, description="Error if task failed")
    retry_count: int = Field(default=0, description="Number of retries")
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    
    model_config = ConfigDict(
        json_schema_extra = {
            "example": {
                "task_id": "AGENT-TASK-2024-0892",
                "task_type": "tool_call",
                "priority": 8,
                "system_current_time": "2024-08-17T14:30:00Z",
                "user_timezone": "Europe/Moscow",
                "conversation_context": [
                    {"role": "user", "content": "Check the cable tray status", "message_id": 456},
                    {"role": "assistant", "content": "I'll check the current status...", "message_id": 457}
                ],
                "parent_thread_id": 455,
                "user_message": "Mia, check if the cable trays have arrived for Sector 7",
                "user_intent": "check_material_status",
                "entities_detected": {"material": "cable trays", "project": "Sector 7"},
                "project_id": "PROJ-2024-001",
                "telegram_chat_id": -1001234567890,
                "user_id": 123456789,
                "username": "site_manager",
                "agent_reasoning": "User wants to check material status. I should query structured DB and search RAG for recent updates.",
                "selected_tools": ["get_project_financials", "search_vector_rag"],
                "tool_call_sequence": [
                    {"tool": "get_project_financials", "params": {"sql_query": "SELECT * FROM materials WHERE canonical_name LIKE '%cable tray%'"}},
                    {"tool": "search_vector_rag", "params": {"semantic_query": "cable tray delivery status Sector 7", "project_id": "PROJ-2024-001"}}
                ]
            }
        }
```

### 2.2 Enhanced Telegram Message Schema

```python
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime

class TelegramMessage(BaseModel):
    """Enhanced schema with context awareness for agentic processing."""
    
    message_id: int
    chat_id: int
    user_id: int
    username: Optional[str]
    text: Optional[str]
    voice_note_file_id: Optional[str]
    timestamp: datetime
    is_reply: bool = False
    reply_to_message_id: Optional[int] = None
    mentions_mia: bool = False
    
    # FIX 3: Context Capture
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
    
    model_config = ConfigDict(
        json_schema_extra = {
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
                    {"message_id": 450, "text": "Morning check complete", "user": "foreman"},
                    # ... up to 10 messages
                ],
                "extracted_entities": {"material": "cable trays", "time_reference": "last week", "project": "Sector 7"},
                "detected_intent": "check_material_delivery_status",
                "requires_agent_action": True
            }
        }
```

### 2.3 Project Context Schema (Simplified)

```python
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime
from enum import Enum

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
    
    model_config = ConfigDict(
        json_schema_extra = {
            "example": {
                "project_id": "PROJ-2024-001",
                "project_name": "Fiber Optic Relocation - Sector 7",
                "telegram_chat_id": -1001234567890,
                "google_drive_folder_id": "1AbCdEfGhIjKlMnOpQrStUvWxYz",
                "email_filters": ["*Sector 7*", "*fiber optic*"],
                "status": "active"
            }
        }
```

### 2.4 Financial Report Schema

```python
from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal

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
    
    @field_validator('budget_utilization_percent')
    @classmethod
    def calculate_utilization(cls, v, info):
        if 'spent_budget' in info.data and 'total_budget' in info.data:
            if info.data['total_budget'] > 0:
                return float(info.data['spent_budget'] / info.data['total_budget'] * 100)
        return v
    
    @field_validator('remaining_budget')
    @classmethod
    def calculate_remaining(cls, v, info):
        if 'total_budget' in info.data and 'spent_budget' in info.data:
            return info.data['total_budget'] - info.data['spent_budget']
        return v
    
    model_config = ConfigDict(
        json_schema_extra = {
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
        }
```

### 2.5 Material Status Schema

```python
from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal
from enum import Enum

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
    
    @field_validator('remaining_required')
    @classmethod
    def calculate_remaining(cls, v, info):
        if 'total_ordered' in info.data and 'total_installed' in info.data:
            return info.data['total_ordered'] - info.data['total_installed']
        return v
    
    @field_validator('total_cost')
    @classmethod
    def calculate_total_cost(cls, v, info):
        if 'unit_cost' in info.data and 'total_ordered' in info.data:
            if info.data['unit_cost'] is not None:
                return info.data['unit_cost'] * info.data['total_ordered']
        return v
    
    model_config = ConfigDict(
        json_schema_extra = {
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
        }
```

### 2.6 Document Metadata Schema

```python
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict
from datetime import datetime
from enum import Enum

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
    
    model_config = ConfigDict(
        json_schema_extra = {
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
        }
```

### 2.7 Deadline Registry Schema

```python
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime
from enum import Enum

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
    
    model_config = ConfigDict(
        json_schema_extra = {
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
        }
```

### 2.8 Extracted Event Schema

```python
from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

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
    
    model_config = ConfigDict(
        json_schema_extra = {
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
        }
```

### 2.9 Nomenclature Mapping Schema

```python
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime

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
    
    model_config = ConfigDict(
        json_schema_extra = {
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
        }
```

---

## 3. Native Tool Calling Interface

### 3.1 Tool Definitions (Open Python)

```python
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Callable
from pydantic import BaseModel, create_model
from functools import wraps
import inspect

class ToolResult(BaseModel):
    """Standard result format for all tool executions."""
    success: bool
    data: Any
    error_message: Optional[str] = None
    execution_time_seconds: float
    requires_followup: bool = False
    followup_suggestions: List[str] = []

# FIX 4: Automated Tool Schema Generation
def tool_function(func: Callable) -> Callable:
    """
    Decorator for automatic tool schema generation from function signatures.
    Prevents LLM from hallucinating JSON brackets by using Pydantic.
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        return await func(*args, **kwargs)
    
    # Mark as tool function for schema generation
    wrapper._is_tool_function = True
    return wrapper

def generate_tool_schema_from_function(func: Callable) -> Dict[str, Any]:
    """
    Automatically generate JSON schema from function signature and docstring.
    This prevents LLM from hallucinating JSON structure.
    """
    sig = inspect.signature(func)
    docstring = inspect.getdoc(func) or ""
    
    properties = {}
    required = []
    
    for param_name, param in sig.parameters.items():
        param_type = param.annotation
        if param_type == inspect.Parameter.empty:
            param_type = str
        
        # Build JSON schema for parameter
        param_schema = {"type": "string"}  # Default to string for LLM safety
        
        if param.default != inspect.Parameter.empty:
            param_schema["default"] = param.default
        else:
            required.append(param_name)
        
        # Try to infer more specific types
        if param_type == int:
            param_schema["type"] = "integer"
        elif param_type == float:
            param_schema["type"] = "number"
        elif param_type == bool:
            param_schema["type"] = "boolean"
        elif hasattr(param_type, "__origin__") and param_type.__origin__ is list:
            param_schema["type"] = "array"
        
        properties[param_name] = param_schema
    
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "description": docstring
    }

class MiaTool(ABC):
    """Base class for all Mia tools with automated schema generation."""
    
    @property
    @abstractmethod
    def tool_name(self) -> str:
        """Name of the tool for agent reference."""
        pass
    
    @property
    @abstractmethod
    def tool_description(self) -> str:
        """Description of what this tool does for agent understanding."""
        pass
    
    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """Execute the tool with given parameters."""
        pass
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        """
        Generate JSON schema automatically from execute method signature.
        FIX 4: Prevents LLM from hallucinating JSON brackets.
        """
        return generate_tool_schema_from_function(self.execute)
```

### 3.2 Core Tool Implementations

```python
class BindProjectToChatTool(MiaTool):
    """Tool for binding a project to a Telegram chat via natural language."""
    
    @property
    def tool_name(self) -> str:
        return "bind_project_to_chat"
    
    @property
    def tool_description(self) -> str:
        return "Binds a construction project to the current Telegram chat. Use when user wants to connect a chat to a specific project for tracking."
    
    @tool_function
    async def execute(self, project_name: str, drive_folder_id: str) -> ToolResult:
        """
        Bind project to chat with validation.
        
        Args:
            project_name: Human-readable name of the project (e.g., 'Fiber Optic Relocation - Sector 7')
            drive_folder_id: Google Drive folder ID containing project documents
        
        Returns:
            ToolResult with binding status and natural language explanation
        """
        # Implementation checks for UNIQUE constraint on telegram_chat_id
        # Validates folder_id accessibility
        # Creates ProjectContextSchema entry
        # Returns success/failure with natural language explanation
        pass

# FIX 3: Safe Semantic Tools (Replace unsafe SQL generation)
class GetProjectFinancialsTool(MiaTool):
    """Safe tool for retrieving project financial data."""
    
    @property
    def tool_name(self) -> str:
        return "get_project_financials"
    
    @property
    def tool_description(self) -> str:
        return "Retrieves financial information for a project including budget spent, remaining budget, KS-2/KS-3 documents, and invoice status. Use when user asks about money, costs, or financial status."
    
    @tool_function
    async def execute(self, project_id: str, include_ks2: bool = True, include_ks3: bool = True) -> ToolResult:
        """
        Retrieve project financial data safely without SQL generation.
        
        Args:
            project_id: Project ID to retrieve financial data for
            include_ks2: Whether to include KS-2 document information
            include_ks3: Whether to include KS-3 document information
        
        Returns:
            ToolResult with FinancialReportSchema data
        """
        # Safe parameterized query internally
        # Returns structured financial data
        pass

class GetMaterialStatusTool(MiaTool):
    """Safe tool for retrieving material status information."""
    
    @property
    def tool_name(self) -> str:
        return "get_material_status"
    
    @property
    def tool_description(self) -> str:
        return "Retrieves material status information including quantities, delivery status, and location. Use when user asks about materials, supplies, deliveries, or inventory."
    
    @tool_function
    async def execute(self, project_id: str, material_name: Optional[str] = None, status_filter: Optional[str] = None) -> ToolResult:
        """
        Retrieve material status safely without SQL generation.
        
        Args:
            project_id: Project ID to retrieve material data for
            material_name: Optional specific material name to filter by
            status_filter: Optional status filter (e.g., 'delayed', 'on_site')
        
        Returns:
            ToolResult with MaterialStatusSchema data
        """
        # Safe parameterized query internally
        # Returns structured material status data
        pass

class GetProjectDeadlinesTool(MiaTool):
    """Safe tool for retrieving project deadline and event information."""
    
    @property
    def tool_name(self) -> str:
        return "get_project_deadlines"
    
    @property
    def tool_description(self) -> str:
        return "Retrieves project deadlines, events, and time-sensitive information. Use when user asks about deadlines, meetings, permit expirations, or schedules."
    
    @tool_function
    async def execute(self, project_id: str, upcoming_only: bool = True, days_ahead: int = 30) -> ToolResult:
        """
        Retrieve project deadlines safely without SQL generation.
        
        Args:
            project_id: Project ID to retrieve deadline data for
            upcoming_only: Whether to only return upcoming deadlines
            days_ahead: Number of days ahead to include (default: 30)
        
        Returns:
            ToolResult with deadline and event data
        """
        # Safe parameterized query internally
        # Returns structured deadline data
        pass

class SearchVectorRAGTool(MiaTool):
    """Tool for semantic search in ChromaDB."""
    
    @property
    def tool_name(self) -> str:
        return "search_vector_rag"
    
    @property
    def tool_description(self) -> str:
        return "Performs semantic search in the vector database. Use for finding relevant document chunks, chat summaries, precedents, and other unstructured information."
    
    @tool_function
    async def execute(self, semantic_query: str, project_id: Optional[str] = None, top_k: int = 10) -> ToolResult:
        """
        Perform semantic vector search.
        
        Args:
            semantic_query: Natural language query for semantic search
            project_id: Project ID to scope search (optional for cross-project search)
            top_k: Number of results to return (default: 10)
        
        Returns:
            ToolResult with ranked vector search results
        """
        # Generates embedding for query
        # Searches ChromaDB with filters
        # Returns ranked results with similarity scores
        pass

class RegisterDeadlineTool(MiaTool):
    """Tool for registering deadlines and events."""
    
    @property
    def tool_name(self) -> str:
        return "register_deadline"
    
    @property
    def tool_description(self) -> str:
        return "Registers a deadline or event in the system. Use when user mentions deadlines, meetings, permit expirations, or other time-sensitive events."
    
    @tool_function
    async def execute(self, event_title: str, target_iso_date: str, event_type: str = "deadline", importance: str = "medium") -> ToolResult:
        """
        Register deadline with automatic notification setup.
        
        Args:
            event_title: Title of the event or deadline
            target_iso_date: Target date in ISO 8601 format (e.g., '2024-08-20T14:00:00Z')
            event_type: Type of event: 'deadline', 'meeting', 'permit_expiration', 'delivery', etc.
            importance: Importance level: 'low', 'medium', 'high', 'critical'
        
        Returns:
            ToolResult with deadline registration status
        """
        # Parses and validates ISO date
        # Creates deadline registry entry
        # Sets up notification thresholds
        # Passes context (system_current_time) for relative date calculations
        pass

class ResolveNomenclatureAliasTool(MiaTool):
    """Tool for resolving material name aliases."""
    
    @property
    def tool_name(self) -> str:
        return "resolve_nomenclature_alias"
    
    @property
    def tool_description(self) -> str:
        return "Resolves material name aliases to canonical names. Use when encountering different names for the same material (e.g., 'сотка пндшка' -> 'Труба ПНД 110')."
    
    @tool_function
    async def execute(self, raw_name: str, canonical_name: Optional[str] = None, project_id: Optional[str] = None) -> ToolResult:
        """
        Resolve or create nomenclature mapping.
        
        Args:
            raw_name: Raw material name as mentioned in conversation
            canonical_name: Canonical name to map to (if known)
            project_id: Project ID for project-specific mappings
        
        Returns:
            ToolResult with mapping resolution or creation status
        """
        # Searches existing mappings
        # Creates new mapping if canonical_name provided
        # Returns confidence score and alternatives
        pass

class ProcessChatSummaryTool(MiaTool):
    """Tool for processing chat messages into structured facts."""
    
    @property
    def tool_name(self) -> str:
        return "process_chat_summary"
    
    @property
    def tool_description(self) -> str:
        return "Processes chat messages into structured facts for RAG. Use periodically to summarize conversations and extract actionable information."
    
    @tool_function
    async def execute(self, project_id: str, telegram_chat_id: int, batch_size: int = 25) -> ToolResult:
        """
        Process chat batch with transaction management.
        
        Args:
            project_id: Project ID to process
            telegram_chat_id: Telegram chat ID to process
            batch_size: Number of messages to process (default: 25)
        
        Returns:
            ToolResult with summarization status and extracted facts
        """
        # Gets unsummarized messages
        # Extracts structured facts
        # Marks messages as summarized (atomic operation)
        # Stores facts in ChromaDB
        pass

class AnalyzeDocumentVisionTool(MiaTool):
    """Tool for vision-based document analysis."""
    
    @property
    def tool_name(self) -> str:
        return "analyze_document_vision"
    
    @property
    def tool_description(self) -> str:
        return "Analyzes documents (PDFs, images) using vision capabilities. Use for extracting stamps, signatures, dates, and understanding technical drawings."
    
    @tool_function
    async def execute(self, document_id: str, analysis_type: str = "stamps_signatures") -> ToolResult:
        """
        Perform vision analysis on document.
        
        Args:
            document_id: Document ID to analyze
            analysis_type: Type of analysis: 'stamps_signatures', 'technical_content', 'version_comparison'
        
        Returns:
            ToolResult with vision analysis results
        """
        # Loads document
        # Runs vision model analysis
        # Extracts metadata and content
        # Chunks document for RAG
        pass

class CheckProjectStatusTool(MiaTool):
    """Tool for checking overall project status."""
    
    @property
    def tool_name(self) -> str:
        return "check_project_status"
    
    @property
    def tool_description(self) -> str:
        return "Provides overall project status summary. Use when user asks for project overview, progress updates, or general status information."
    
    @tool_function
    async def execute(self, project_id: Optional[str] = None, status_type: str = "overall") -> ToolResult:
        """
        Get comprehensive project status.
        
        Args:
            project_id: Project ID to check (optional if chat is bound)
            status_type: Type of status: 'overall', 'financial', 'materials', 'deadlines', 'risks'
        
        Returns:
            ToolResult with comprehensive project status
        """
        # Aggregates data from multiple sources
        # Provides structured summary
        # Highlights issues and risks
        pass
```

### 3.3 Tool Registry

```python
class ToolRegistry:
    """Registry of available tools for agent access."""
    
    def __init__(self):
        self._tools: Dict[str, MiaTool] = {}
        self._register_core_tools()
    
    def _register_core_tools(self):
        """Register all core tools."""
        tools = [
            BindProjectToChatTool(),
            GetProjectFinancialsTool(),  # Safe replacement for QueryStructuredDBTool
            GetMaterialStatusTool(),     # Safe replacement for QueryStructuredDBTool
            GetProjectDeadlinesTool(),   # Safe replacement for QueryStructuredDBTool
            SearchVectorRAGTool(),
            RegisterDeadlineTool(),
            ResolveNomenclatureAliasTool(),
            ProcessChatSummaryTool(),
            AnalyzeDocumentVisionTool(),
            CheckProjectStatusTool()
        ]
        
        for tool in tools:
            self._tools[tool.tool_name] = tool
    
    def get_tool(self, tool_name: str) -> Optional[MiaTool]:
        """Get tool by name."""
        return self._tools.get(tool_name)
    
    def get_all_tools(self) -> List[MiaTool]:
        """Get all registered tools."""
        return list(self._tools.values())
    
    def get_tools_schema(self) -> Dict[str, Any]:
        """Get JSON schema for all tools (for LLM function calling)."""
        return {
            "tools": [
                {
                    "name": tool.tool_name,
                    "description": tool.tool_description,
                    "parameters": tool.get_parameters_schema()
                }
                for tool in self._tools.values()
            ]
        }
```

---

## 4. Agent Loop Implementation

### 4.1 Context Builder

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class ContextBuilderInterface(ABC):
    """Interface for building agent context."""
    
    @abstractmethod
    async def build_context(self, message: TelegramMessage) -> Dict[str, Any]:
        """
        Build complete context for agent processing.
        
        FIX 3: Captures parent thread and sliding window for pronoun resolution.
        FIX 2: Injects system_current_time for chronological awareness.
        """
        pass
    
    @abstractmethod
    async def capture_parent_thread(self, message_id: int, chat_id: int) -> List[Dict[str, Any]]:
        """Capture parent thread context starting from message."""
        pass
    
    @abstractmethod
    async def get_sliding_window(self, chat_id: int, window_size: int = 10) -> List[Dict[str, Any]]:
        """Get sliding window of recent messages."""
        pass
    
    @abstractmethod
    async def extract_entities(self, text: str) -> Dict[str, Any]:
        """Extract entities from message text."""
        pass
    
    @abstractmethod
    async def detect_intent(self, text: str, context: Dict[str, Any]) -> Optional[str]:
        """Detect user intent from message and context."""
        pass
```

### 4.2 Tool Calling Engine

```python
class ToolCallingEngine:
    """Engine for autonomous tool selection and execution."""
    
    def __init__(self, tool_registry: ToolRegistry, ollama_client):
        self.tool_registry = tool_registry
        self.ollama_client = ollama_client
    
    async def decide_tools(self, user_message: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Use LLM to autonomously decide which tools to call.
        
        This replaces the rigid Hybrid RAG Router with intelligent tool selection.
        """
        tools_schema = self.tool_registry.get_tools_schema()
        
        prompt = f"""
        You are Mia, an AI construction project assistant. Analyze the user's request and decide which tools to call.
        
        User Message: {user_message}
        Context: {context}
        System Time: {context.get('system_current_time')}
        
        Available Tools:
        {tools_schema}
        
        Respond with a JSON array of tool calls in the format:
        [
            {{
                "tool": "tool_name",
                "parameters": {{...}},
                "reasoning": "why this tool is needed"
            }}
        ]
        
        If no tools are needed, respond with an empty array.
        """
        
        response = await self.ollama_client.generate(prompt)
        return self._parse_tool_calls(response)
    
    def _parse_tool_calls(self, response: str) -> List[Dict[str, Any]]:
        """Parse LLM response into tool calls."""
        # Parse JSON response
        # Validate tool names and parameters
        # Return structured tool call sequence
        pass
    
    async def execute_tool_sequence(self, tool_calls: List[Dict[str, Any]]) -> List[ToolResult]:
        """Execute sequence of tool calls."""
        results = []
        for tool_call in tool_calls:
            tool = self.tool_registry.get_tool(tool_call["tool"])
            if tool:
                result = await tool.execute(**tool_call["parameters"])
                results.append(result)
        return results
```

### 4.3 Unified Task Queue Interface

```python
class UnifiedTaskQueueInterface(ABC):
    """Interface for unified priority-based task queue."""
    
    @abstractmethod
    async def enqueue_task(self, task: LLMTaskSchema) -> bool:
        """
        Enqueue task with priority-based scheduling.
        
        FIX 4: All tasks go through this unified queue.
        Priority matrix ensures proper execution order.
        """
        pass
    
    @abstractmethod
    async def dequeue_task(self) -> Optional[LLMTaskSchema]:
        """
        Dequeue highest priority task.
        
        Single-threaded worker ensures zero VRAM collisions.
        """
        pass
    
    @abstractmethod
    async def update_task_status(self, task_id: str, status: str, **kwargs) -> bool:
        """Update task status and results."""
        pass
    
    @abstractmethod
    async def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status and statistics."""
        pass
```

### 4.4 Single-Threaded Worker Pool

```python
class SingleThreadedWorkerPool:
    """
    Single-threaded worker pool for LLM execution.
    
    FIX 4: Ensures zero VRAM collisions on RTX 5060 by running
    one LLM inference at a time with priority-based scheduling.
    """
    
    def __init__(self, task_queue: UnifiedTaskQueueInterface, tool_engine: ToolCallingEngine):
        self.task_queue = task_queue
        self.tool_engine = tool_engine
        self.is_running = False
    
    async def start(self):
        """Start the worker loop."""
        self.is_running = True
        while self.is_running:
            task = await self.task_queue.dequeue_task()
            if task:
                await self._process_task(task)
            else:
                await asyncio.sleep(1)  # Brief pause if no tasks
    
    async def _process_task(self, task: LLMTaskSchema):
        """Process a single task with full context."""
        try:
            # Update status to processing
            await self.task_queue.update_task_status(task.task_id, "processing", started_at=datetime.now())
            
            # Execute tool calling sequence
            if task.tool_call_sequence:
                results = await self.tool_engine.execute_tool_sequence(task.tool_call_sequence)
            else:
                # Let LLM decide tools
                tool_calls = await self.tool_engine.decide_tools(task.user_message, {
                    "system_current_time": task.system_current_time,
                    "conversation_context": task.conversation_context,
                    "entities_detected": task.entities_detected
                })
                results = await self.tool_engine.execute_tool_sequence(tool_calls)
            
            # Generate final response
            final_response = await self._generate_response(task, results)
            
            # Update task with results
            await self.task_queue.update_task_status(
                task.task_id, 
                "completed",
                completed_at=datetime.now(),
                tool_results=results,
                final_response=final_response
            )
            
            # Deliver response directly to Telegram
            if task.telegram_chat_id:
                await self._deliver_response(task.telegram_chat_id, final_response)
                
        except Exception as e:
            await self.task_queue.update_task_status(
                task.task_id,
                "failed",
                error_message=str(e),
                retry_count=task.retry_count + 1
            )
    
    async def _generate_response(self, task: LLMTaskSchema, tool_results: List[ToolResult]) -> str:
        """Generate natural language response from tool results."""
        # Use LLM to synthesize tool results into natural language
        # Include source attributions
        # Handle conflicting information
        pass
    
    async def _deliver_response(self, chat_id: int, response: str):
        """Deliver response to Telegram chat."""
        # Direct response delivery (no polling)
        pass
    
    async def stop(self):
        """Stop the worker loop."""
        self.is_running = False
```

---

## 5. Configuration

```yaml
# config.yaml - Agentic Architecture
mia:
  environment: production
  log_level: INFO
  
ollama:
  base_url: "http://localhost:11434"
  # FIX 2: Single Multimodal Model Architecture
  # Using one multimodal model for text, reasoning, and vision
  # Prevents VRAM swapping on RTX 5060
  model: "gemma3:12b"  # or "qwen2.5-coder:14b" - single multimodal model
  timeout: 300
  max_context_tokens: 4096
  # Vision capabilities embedded in the same model
  enable_vision: true
  multimodal_mode: "unified"  # Single model handles all modalities

databases:
  sqlite:
    path: "/var/lib/mia/mia.db"
    enable_foreign_keys: true
    enable_unique_constraints: true
    transaction_isolation_level: "SERIALIZABLE"
  chromadb:
    path: "/var/lib/mia/chroma"
  
telegram:
  bot_token: "${TELEGRAM_BOT_TOKEN}"
  api_timeout: 30
  
google_drive:
  credentials_path: "/etc/mia/gdrive_credentials.json"

# FIX 4: Unified Task Queue Configuration
unified_task_queue:
  enabled: true
  # Single-threaded worker for zero VRAM collisions
  worker_mode: "single_threaded"
  max_concurrent_workers: 1
  
  # Priority Matrix
  priority_matrix:
    critical:
      value: 10
      description: "Real-time admin tags, immediate response"
      max_queue_size: 5
    high:
      value: 8
      description: "User queries, urgent requests"
      max_queue_size: 20
    normal:
      value: 5
      description: "Chat summarization, routine operations"
      max_queue_size: 50
    low:
      value: 3
      description: "Document analysis, background processing"
      max_queue_size: 100
    background:
      value: 1
      description: "Night vision chunking, lowest priority"
      max_queue_size: 200
  
  # Task Scheduling
  queue_poll_interval_seconds: 1
  task_timeout_seconds: 300
  max_retries: 3
  retry_backoff_seconds: 5

# FIX 2: Chronological Awareness
temporal_context:
  enabled: true
  default_timezone: "Europe/Moscow"
  enable_relative_date_calculation: true
  date_formats:
    - "%Y-%m-%d"
    - "%d.%m.%Y"
    - "%d/%m/%Y"
  relative_phrases:
    - "next week"
    - "next month"
    - "in 3 days"
    - "by Friday"
    - "this quarter"

# FIX 3: Context Building
context_builder:
  enabled: true
  sliding_window_size: 10
  max_thread_depth: 5
  enable_pronoun_resolution: true
  enable_entity_extraction: true
  enable_intent_detection: true

# Tool Calling Configuration
tool_calling:
  enabled: true
  max_tool_calls_per_request: 5
  enable_multi_step_reasoning: true
  reasoning_temperature: 0.7
  tool_execution_timeout: 60
  
  # Tool-specific settings
  tools:
    bind_project_to_chat:
      enabled: true
      require_verification: true
    # FIX 3: Safe semantic tools (replaced unsafe get_project_financials)
    get_project_financials:
      enabled: true
      cache_ttl_seconds: 300
      include_ks2_by_default: true
      include_ks3_by_default: true
    get_material_status:
      enabled: true
      cache_ttl_seconds: 180
      enable_status_filtering: true
    get_project_deadlines:
      enabled: true
      cache_ttl_seconds: 120
      default_days_ahead: 30
    search_vector_rag:
      enabled: true
      default_top_k: 10
      # FIX 2: Use same multimodal model for embeddings
      embedding_mode: "integrated"  # Same model handles embeddings
    register_deadline:
      enabled: true
      default_notification_days: 30
    resolve_nomenclature_alias:
      enabled: true
      confidence_threshold: 0.7
    process_chat_summary:
      enabled: true
      batch_size: 25
      priority: 5
    analyze_document_vision:
      enabled: true
      priority: 3
      # FIX 2: Use same multimodal model for vision
      vision_mode: "integrated"  # Same model handles vision
    check_project_status:
      enabled: true
      cache_ttl_seconds: 300
```

---

## 7. Advanced Agent Patterns for Construction Domain

### 7.1 Pattern: Questions Gateway (QUESTIONS.md)

**Integration with Construction Logic**: When Mia encounters logical deadlocks in construction workflows (contradictory cost estimates, unknown material types, pricing conflicts), it triggers a human intervention pattern.

**Construction-Specific Triggers**:
- Budget conflicts between KS-2 acts and FinancialReportSchema estimates
- Material naming conflicts in NomenclatureMappingSchema with multiple high-confidence candidates
- Document version conflicts in DocumentMetadataSchema with no clear resolution
- Deadline conflicts in DeadlineRegistrySchema requiring executive decision

**Implementation with Unified Task Queue**:

```python
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime
from enum import Enum

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
    
    model_config = ConfigDict(
        json_schema_extra = {
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
        }
```

**Task Queue Integration**:
- Questions trigger `TaskPriority.CRITICAL` tasks in unified queue
- Worker suspends related tasks with `suspended_task_id` reference
- Resolution automatically unblocks suspended tasks with updated context

**Safety Mechanisms**:
- **Shadow Reading**: Copy QUESTIONS.md to temporary file before reading to avoid race conditions
- **Stability Check**: Verify file mtime >= 2 seconds before status transition OPEN → ANSWERED
- **Integrity Validation**: Regex validation of Markdown block structure before processing
- **Telegram Integration**: Duplicate questions as interactive buttons in director's private chat

### 7.2 Pattern: Audit Vector (Instead of Curiosity Vector)

**Integration with Construction Logic**: Night-cycle autonomous "white spot" detection in construction documentation, identifying gaps between contracts, schedules, and actual progress.

**Construction-Specific Audit Patterns**:
- **Contract-Document Gap**: Permit exists but no corresponding acts of hidden works
- **Material-Expense Mismatch**: 15% concrete overuse relative to estimate
- **Schedule-Progress Discrepancy**: Permit expiring in 30 days but no inspection acts
- **Financial-Physical Inconsistency**: Invoice count doesn't match material delivery status

**Integration with Unified Task Queue**:

```python
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class AuditSeverity(str, Enum):
    CRITICAL = "critical"  # Legal compliance, financial risks
    HIGH = "high"        # Timeline risks, major inconsistencies
    MEDIUM = "medium"    # Documentation gaps, minor discrepancies
    LOW = "low"          // Informational, optimization opportunities

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
    
    model_config = ConfigDict(
        json_schema_extra = {
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
        }
```

**Task Queue Integration**:
- Night-cycle tasks with `TaskPriority.BACKGROUND` (priority=1)
- Scheduled via existing night processing mechanism
- Generates targeted RAG searches against ChromaDB
- Auto-creates QuestionGateway entries for critical gaps

**Construction Domain Benefits**:
- Proactive compliance risk detection (permit expiry before completion)
- Financial anomaly detection (material overuse vs estimates)
- Documentation completeness verification (acts vs contracts)
- Timeline risk identification (schedule vs actual progress)

### 7.3 Pattern: Strict VRAM Discipline for Task Queue

**Integration with Construction Logic**: Prevents OOM and hangs on RTX 5060 by strictly separating day/night modes and model priorities based on construction urgency.

**VRAM Management Strategy**:

```python
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum

class ExecutionMode(str, Enum):
    DAYTIME = "daytime"      # 07:00-19:00: Focus on real-time user interaction
    NIGHTTIME = "nighttime"  # 19:00-07:00: Focus on batch processing and vision

class ModelSlot(str, Enum):
    CHAT_MODEL = "chat_model"       # Primary chat model (qwen3:14b)
    VISION_MODEL = "vision_model"   # Multimodal model (qwen2.5-vl:7b)
    HEAVY_VISION = "heavy_vision"   # Monopoly slot for night vision
    NONE = "none"                   # No model loaded

class VRAMManagementPolicy(BaseModel):
    execution_mode: ExecutionMode = Field(..., description="Current execution mode")
    current_loaded_models: Dict[ModelSlot, str] = Field(default_factory=dict, description="Models currently loaded")
    
    # Daytime Configuration
    daytime_primary_model: str = Field(default="qwen3:14b", description="Primary chat model for daytime")
    daytime_max_context_tokens: int = Field(default=4096, description="Max context for daytime")
    daytime_temperature: float = Field(default=0.7, description="Temperature for daytime responses")
    
    # Nighttime Configuration
    nighttime_primary_model: str = Field(default="qwen3:14b", description="Primary model for nighttime")
    nighttime_vision_model: str = Field(default="qwen2.5-vl:7b", description="Vision model for nighttime OCR")
    nighttime_vision_monopoly: bool = Field(default=True, description="Vision model gets monopoly slot")
    nighttime_batch_size: int = Field(default=10, description="Batch size for nighttime vision processing")
    
    # VRAM Constraints
    max_concurrent_models: int = Field(default=1, description="Maximum models loaded simultaneously")
    model_switch_cooldown_seconds: int = Field(default=30, description="Cooldown between model switches")
    vision_model_unload_threshold_hours: int = Field(default=6, description="Hours to keep vision loaded after use")
    
    # Construction Priority Mapping
    priority_execution_policy: Dict[int, str] = Field(default_factory=dict, description="Which model for each priority")
    
    last_mode_switch: Optional[datetime] = Field(None, description="Last execution mode switch time")
    current_vram_usage_mb: Optional[int] = Field(None, description="Current VRAM usage in MB")
    
    model_config = ConfigDict(
        json_schema_extra = {
            "example": {
                "execution_mode": "daytime",
                "current_loaded_models": {
                    "chat_model": "qwen3:14b"
                },
                "daytime_primary_model": "qwen3:14b",
                "nighttime_primary_model": "qwen3:14b",
                "nighttime_vision_model": "qwen2.5-vl:7b",
                "nighttime_vision_monopoly": True,
                "priority_execution_policy": {
                    "10": "chat_model",  # Real-time admin tags → chat model
                    "8": "chat_model",   # User queries → chat model
                    "5": "chat_model",   # Summarization → chat model
                    "3": "vision_model", # Document analysis → vision (nighttime only)
                    "1": "heavy_vision"  # Night vision → monopoly slot
                },
                "max_concurrent_models": 1,
                "current_vram_usage_mb": 8192
            }
        }
```

**Task Queue Integration**:
- Worker checks VRAM policy before task execution
- Daytime: Prioritize chat model for ConstructionStatusSchema queries, MaterialStatusSchema checks
- Nighttime: Transition to vision model monopoly for DocumentMetadataSchema OCR, blueprint analysis
- Model switch with cooldown to prevent thrashing
- Automatic unload of vision model after inactivity threshold

**Construction-Specific Benefits**:
- **Daytime**: Instant responses to "check material status", "financial status", "deadline queries"
- **Nighttime**: Batch OCR of invoices, acts, blueprints without blocking real-time queries
- **VRAM Safety**: Guaranteed single-model execution prevents OOM on RTX 5060
- **Priority Respect**: Construction admin tags (priority=10) always get chat model priority

### 7.4 Pattern: Doctor Agent Observer

**Integration with Construction Logic**: Lightweight background process monitoring Mia's technical health and detecting deviant behavior in construction-specific contexts.

**Construction-Specific Health Metrics**:

```python
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

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
    
    model_config = ConfigDict(
        json_schema_extra = {
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
        }
```

**Task Queue Integration**:
- Doctor runs as separate lightweight process (no LLM in hot cycle)
- Monitors task queue status and worker health
- Critical anomalies trigger `TaskPriority.CRITICAL` in QUESTIONS.md (TECH category)
- Director approval required for any process restarts (G8 principle)

**Construction-Specific Monitoring**:
- **Semantic Repetition**: Monitor material status, financial queries for construction fixation
- **Meta Slips**: Regex for "as an AI", "as a language model" in construction advice
- **Worker Health**: Monitor `Processing` status > 10 min for document OCR tasks
- **VRAM Monitoring**: Detect unusual VRAM growth during blueprint analysis
- **Response Quality**: Track construction advice consistency over time

**G8 Principle Enforcement**:
- Doctor can only diagnose and recommend
- Cannot self-restart processes or modify parameters
- All remediation requires director approval via QUESTIONS.md/Telegram
- Prevents autonomous system modifications in critical construction context

---

## 8. Implementation Guidelines

### 8.1 Development Phase Strategy

### 6.1 Agent Loop Best Practices

1. **Natural Language First**: Always respond to natural language, never expect commands
2. **Context Awareness**: Always build full context before tool selection
3. **Autonomous Decision-Making**: Let the LLM decide which tools to use
4. **Graceful Degradation**: If tool fails, continue with alternative approaches
5. **Transparent Reasoning**: Include reasoning in responses for user understanding

### 6.2 Tool Implementation Guidelines

1. **Clear Descriptions**: Tool descriptions must be clear for LLM understanding
2. **Type Safety**: Use Pydantic schemas for all parameters
3. **Error Handling**: Always return ToolResult with success/failure status
4. **Idempotency**: Tools should be safe to call multiple times
5. **Security**: Validate all inputs, especially for database operations

### 6.3 Single-GPU Optimization

1. **Single-Threaded Execution**: One LLM inference at a time prevents VRAM collisions
2. **Priority-Based Scheduling**: Critical tasks get immediate attention
3. **Efficient Context Management**: Reuse context where possible
4. **Model Selection**: Use appropriate model size for task complexity
5. **Memory Management**: Clear GPU memory between tasks

---

## Conclusion

This agentic architecture transforms Mia from a command-based system to an intelligent agent that:

- **Understands Natural Language**: No slash commands, just natural conversation
- **Autonomous Tool Selection**: LLM decides which tools to use based on context
- **Context-Aware**: Captures thread context and temporal awareness
- **Unified Execution**: Single priority-based queue for all LLM operations
- **GPU-Efficient**: Single-threaded worker prevents VRAM collisions
- **Construction-Ready**: Designed for how construction teams actually work

The specification is 100% deterministic and optimized for local LLM implementation on single-GPU systems, providing a truly agentic experience for construction project management.
