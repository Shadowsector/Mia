---
agent: devin-local
session: wide-ursinia
created: 2026-08-17T13:22:58Z
---
# Mia Construction Project Management OS - Enterprise Architecture RFC

## Executive Summary

Mia is a local AI-driven Construction Project Management Operating System designed for utility & civil construction companies specializing in underground cable duct construction, fiber optic (ВОЛС) relocation, cable tray installations, and municipal utility networks. This architecture specification is optimized for implementation by smaller local LLMs (Gemma 3 12B / Qwen 3 Coder 14B running via Ollama) and provides 100% deterministic technical specifications using strict Pydantic v2 schemas, abstract base classes, and fully typed interfaces.

**Design Philosophy**: Every module must be implementable by a smaller LLM without ambiguity. All data contracts are explicit, all interfaces are strictly typed, and all boundaries are clearly defined with mock implementations.

---

## 1. Architecture Schematic

### 1.1 System Overview Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              EXTERNAL DATA SOURCES                            │
├──────────────────┬──────────────────┬──────────────────┬────────────────────┤
│  Google Drive    │   IMAP Mailbox   │  Telegram Chats  │   Voice Messages   │
│  (Object Folders)│  (Project Mail)  │  (Site Updates)  │   (Worker Audio)   │
└────────┬─────────┴────────┬─────────┴────────┬─────────┴────────┬───────────┘
         │                  │                  │                  │
         ▼                  ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        MODULE 1: INGESTION MANAGER                           │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐          │
│  │ Drive Ingester   │  │  IMAP Ingester   │  │  STT Router      │          │
│  │  (Scheduled)     │  │  (Scheduled)     │  │  (On-demand)     │          │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘          │
└───────────┼────────────────────┼────────────────────┼──────────────────────┘
            │                    │                    │
            ▼                    ▼                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CENTRAL MESSAGE QUEUE                                │
│                    (Redis / SQLite-backed Queue)                             │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
            ┌─────────────────┼─────────────────┐
            ▼                 ▼                 ▼
┌─────────────────────┐ ┌─────────────────────┐ ┌─────────────────────┐
│  DAYTIME PROCESSING │ │  NIGHT PROCESSING   │ │  REAL-TIME EVENTS   │
│  (Lightweight)      │ │  (Heavy Vision)     │ │  (Telegram Chat)    │
└──────────┬──────────┘ └──────────┬──────────┘ └──────────┬──────────┘
           │                       │                       │
           ▼                       ▼                       ▼
┌─────────────────────┐ ┌─────────────────────┐ ┌─────────────────────┐
│  MODULE 2:          │ │  MODULE 3:          │ │  MODULE 6:          │
│  Telegram Interaction│ │  Night Vision       │ │  RBAC Access Guard  │
│  & STT Router       │ │  Parser & PDF       │ │  (Security Layer)   │
└──────────┬──────────┘ └──────────┬──────────┘ └──────────┬──────────┘
           │                       │                       │
           └───────────────────────┼───────────────────────┘
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MODULE 4: CONFLICT RESOLVER                               │
│              (Ambiguity Detection & Nomenclature Mapping)                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                   MODULE 5: HYBRID RAG STORAGE ENGINE                        │
│  ┌──────────────────────┐              ┌──────────────────────┐            │
│  │  SQLite (Structured) │              │  ChromaDB (Unstructured)│           │
│  │  - Projects          │              │  - Document Chunks    │            │
│  │  - Users/RBAC        │              │  - Chat Logs          │            │
│  │  - Financial Data    │              │  - Cross-Chat KB      │            │
│  │  - Deadlines         │              │  - Precedent Mapping  │            │
│  │  - Conflicts         │              │  - Embeddings         │            │
│  └──────────────────────┘              └──────────────────────┘            │
└─────────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MODULE 7: CENTRAL SCHEDULER                               │
│              (APS/Cron Orchestrator + Deadline Ticker)                       │
└─────────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                   HYBRID RAG ROUTER & QUERY ENGINE                           │
│  ┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────┐  │
│  │  SQL Query Router    │  │  Vector DB Router    │  │  Joint Retrieval │  │
│  │  (Structured Data)   │  │  (Semantic Search)   │  │  (Unified)       │  │
│  └──────────┬───────────┘  └──────────┬───────────┘  └────────┬─────────┘  │
└─────────────┼────────────────────────┼────────────────────────┼────────────┘
              │                        │                        │
              └────────────────────────┼────────────────────────┘
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      LOCAL OLLAMA INFERENCE ENGINE                            │
│              (Gemma 3 12B / Qwen 3 Coder 14B)                                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      RESPONSE ORCHESTRATION LAYER                             │
│              (Conflict Attribution + Source Citation)                         │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         TELEGRAM RESPONSE OUTPUT                              │
│                   (RBAC-filtered, @Mia-tagged only)                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Asynchronous Data Flow Specification

**Ingestion Phase (07:00 - 19:00, every 10 minutes):**
1. Central Scheduler triggers Ingestion Manager
2. Drive Ingester scans Google Drive object folders, extracts metadata, queues for processing
3. IMAP Ingester fetches mailbox, classifies emails by project context, queues for processing
4. All ingested items enter Central Message Queue with ProjectContext binding

**Real-Time Phase (Continuous):**
1. Telegram Monitor passively logs all chat messages (no filtering)
2. Voice messages trigger STT Router → Whisper transcription → queue
3. All chat data is tagged with Construction Object ID and timestamp

**Night Processing Phase (02:00 - 06:00):**
1. Night Vision Parser processes queued PDFs/drawings
2. Vision-multimodal analysis via Ollama for stamps, signatures, dates
3. PDF chunking with hierarchy preservation
4. Version comparison against existing RAG entries
5. Results stored in Hybrid RAG Storage Engine

**Query Phase (On-demand, @Mia-tagged):**
1. RBAC Access Guard validates user permissions
2. Hybrid RAG Router determines query type (SQL/Vector/Joint)
3. Local Ollama processes with re-ranked context (10-20 chunks)
4. Response Orchestrator adds source attribution
5. Conflicting facts are presented with source citations

**Proactive Phase (Scheduled):**
1. Deadline Ticker queries DeadlineRegistryTable every 10 minutes
2. Events approaching threshold trigger Ollama notification drafting
3. Notifications pushed to respective Telegram chats without @Mia tag

---

## 2. Core Pydantic Schemas (V2)

### 2.1 Project Context Schema

```python
from pydantic import BaseModel, Field, HttpUrl
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
    """Binds Telegram Chat ID, Google Drive Folder ID, and Email Filters to a specific Construction Object."""
    
    project_id: str = Field(..., description="Unique project identifier (e.g., 'PROJ-2024-001')")
    project_name: str = Field(..., description="Human-readable project name")
    telegram_chat_id: int = Field(..., description="Telegram group chat ID for this construction object")
    google_drive_folder_id: str = Field(..., description="Google Drive folder ID containing project documents")
    email_filters: List[str] = Field(default_factory=list, description="Email subject/pattern filters for automatic classification")
    status: ProjectStatus = Field(default=ProjectStatus.PLANNING, description="Current project status")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Project creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    metadata: Optional[dict] = Field(default_factory=dict, description="Additional project-specific metadata")
    
    class Config:
        json_schema_extra = {
            "example": {
                "project_id": "PROJ-2024-001",
                "project_name": "Fiber Optic Relocation - Sector 7",
                "telegram_chat_id": -1001234567890,
                "google_drive_folder_id": "1AbCdEfGhIjKlMnOpQrStUvWxYz",
                "email_filters": ["*Sector 7*", "*PROJ-2024-001*", "*fiber optic*"],
                "status": "active",
                "metadata": {"client": "City Municipality", "budget": 5000000}
            }
        }
```

### 2.2 Ambiguity Issue Schema

```python
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class ConflictSeverity(str, Enum):
    LOW = "low"  # Nomenclature mismatch, minor data discrepancy
    MEDIUM = "medium"  # Quantitative disagreement (e.g., quantities)
    HIGH = "high"  # Financial conflict, safety-related contradiction
    CRITICAL = "critical"  # Legal/compliance conflict, requires immediate admin attention

class ConflictSource(str, Enum):
    GOOGLE_DRIVE = "google_drive"
    TELEGRAM_CHAT = "telegram_chat"
    EMAIL = "email"
    MANUAL_ENTRY = "manual_entry"
    SYSTEM_INFERENCE = "system_inference"

class AmbiguityIssueSchema(BaseModel):
    """Structures unresolved conflicts (item names, data contradictions) for human review."""
    
    conflict_id: str = Field(..., description="Unique conflict identifier")
    project_id: str = Field(..., description="Associated project ID")
    conflict_type: str = Field(..., description="Type of conflict: 'nomenclature', 'quantitative', 'financial', 'status'")
    severity: ConflictSeverity = Field(..., description="Conflict severity level")
    
    # Conflicting facts
    fact_a_value: Any = Field(..., description="First conflicting fact value")
    fact_a_source: ConflictSource = Field(..., description="Source of first fact")
    fact_a_timestamp: datetime = Field(..., description="Timestamp of first fact")
    fact_a_reference: Optional[str] = Field(None, description="Reference URL/ID for first fact")
    
    fact_b_value: Any = Field(..., description="Second conflicting fact value")
    fact_b_source: ConflictSource = Field(..., description="Source of second fact")
    fact_b_timestamp: datetime = Field(..., description="Timestamp of second fact")
    fact_b_reference: Optional[str] = Field(None, description="Reference URL/ID for second fact")
    
    # Resolution tracking
    resolution_status: str = Field(default="unresolved", description="Status: 'unresolved', 'pending_review', 'resolved'")
    resolved_value: Optional[Any] = Field(None, description="Admin-confirmed resolved value")
    resolved_by: Optional[str] = Field(None, description="Telegram user ID who resolved conflict")
    resolved_at: Optional[datetime] = Field(None, description="Resolution timestamp")
    resolution_notes: Optional[str] = Field(None, description="Admin notes on resolution")
    
    # Nomenclature mapping (if applicable)
    canonical_name: Optional[str] = Field(None, description="Canonical item name if nomenclature conflict")
    alias_names: List[str] = Field(default_factory=list, description="List of alias names mapped to canonical")
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Conflict detection timestamp")
    auto_escalated: bool = Field(default=False, description="Whether system auto-escalated this conflict")
    escalation_reason: Optional[str] = Field(None, description="Reason for auto-escalation")
    
    class Config:
        json_schema_extra = {
            "example": {
                "conflict_id": "CONF-2024-0892",
                "project_id": "PROJ-2024-001",
                "conflict_type": "quantitative",
                "severity": "high",
                "fact_a_value": "100% cable trays purchased",
                "fact_a_source": "google_drive",
                "fact_a_timestamp": "2024-08-15T10:30:00Z",
                "fact_a_reference": "https://docs.google.com/spreadsheets/d/1AbC...",
                "fact_b_value": "No trays on site, delayed",
                "fact_b_source": "telegram_chat",
                "fact_b_timestamp": "2024-08-15T14:22:00Z",
                "fact_b_reference": "telegram_message_id:45678",
                "resolution_status": "unresolved",
                "auto_escalated": True,
                "escalation_reason": "Material delivery critical path"
            }
        }
```

### 2.3 Financial Report Schema

```python
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict
from datetime import datetime
from decimal import Decimal

class KS2DocumentReference(BaseModel):
    """Reference to KS-2 executive document."""
    document_id: str = Field(..., description="KS-2 document identifier")
    document_url: Optional[str] = Field(None, description="Document URL if available")
    acceptance_date: Optional[datetime] = Field(None, description="Document acceptance date")
    amount: Decimal = Field(..., description="Amount in KS-2 document")
    verified: bool = Field(default=False, description="Whether Mia has verified this document")

class FinancialReportSchema(BaseModel):
    """Tailored for construction financial tracking (KS-2/KS-3, spent budget, invoices)."""
    
    report_id: str = Field(..., description="Unique financial report identifier")
    project_id: str = Field(..., description="Associated project ID")
    reporting_period_start: datetime = Field(..., description="Period start date")
    reporting_period_end: datetime = Field(..., description="Period end date")
    
    # Budget tracking
    total_budget: Decimal = Field(..., description="Total project budget")
    spent_budget: Decimal = Field(default=Decimal("0"), description="Total amount spent")
    remaining_budget: Decimal = Field(default=Decimal("0"), description="Remaining budget")
    budget utilization_percent: float = Field(default=0.0, description="Budget utilization percentage")
    
    # KS-2 documents (executive acts)
    ks2_documents: List[KS2DocumentReference] = Field(default_factory=list, description="List of KS-2 documents")
    ks2_total_amount: Decimal = Field(default=Decimal("0"), description="Total amount from KS-2 documents")
    
    # KS-3 documents (payment certificates)
    ks3_document_count: int = Field(default=0, description="Number of KS-3 documents")
    ks3_total_amount: Decimal = Field(default=Decimal("0"), description="Total amount from KS-3 documents")
    
    # Invoice tracking
    invoice_count: int = Field(default=0, description="Total number of invoices")
    invoice_total_amount: Decimal = Field(default=Decimal("0"), description="Total invoice amount")
    pending_invoices: int = Field(default=0, description="Number of pending invoices")
    pending_invoice_amount: Decimal = Field(default=Decimal("0"), description="Total pending invoice amount")
    
    # Material costs breakdown
    material_costs: Dict[str, Decimal] = Field(default_factory=dict, description="Material category costs")
    labor_costs: Decimal = Field(default=Decimal("0"), description="Total labor costs")
    equipment_costs: Decimal = Field(default=Decimal("0"), description="Total equipment costs")
    overhead_costs: Decimal = Field(default=Decimal("0"), description="Total overhead costs")
    
    # Metadata
    generated_at: datetime = Field(default_factory=datetime.utcnow, description="Report generation timestamp")
    generated_by: str = Field(..., description="System or user who generated report")
    data_sources: List[str] = Field(default_factory=list, description="Data sources used for report")
    
    @validator('budget_utilization_percent')
    def calculate_utilization(cls, v, values):
        if 'spent_budget' in values and 'total_budget' in values:
            if values['total_budget'] > 0:
                return float(values['spent_budget'] / values['total_budget'] * 100)
        return v
    
    @validator('remaining_budget')
    def calculate_remaining(cls, v, values):
        if 'total_budget' in values and 'spent_budget' in values:
            return values['total_budget'] - values['spent_budget']
        return v
    
    class Config:
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

### 2.4 Material Status Schema

```python
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict
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
    """Tailored for construction material tracking with units, quantities, and delivery status."""
    
    material_id: str = Field(..., description="Unique material identifier")
    project_id: str = Field(..., description="Associated project ID")
    canonical_name: str = Field(..., description="Canonical material name")
    alias_names: List[str] = Field(default_factory=list, description="Alternative names for this material")
    
    # Quantitative specifications
    unit: MaterialUnit = Field(..., description="Unit of measurement")
    total_ordered: Decimal = Field(default=Decimal("0"), description="Total quantity ordered")
    total_delivered: Decimal = Field(default=Decimal("0"), description="Total quantity delivered to site")
    total_installed: Decimal = Field(default=Decimal("0"), description="Total quantity installed")
    remaining_required: Decimal = Field(default=Decimal("0"), description="Remaining quantity required")
    
    # Status tracking
    current_status: MaterialStatus = Field(default=MaterialStatus.UNKNOWN, description="Current material status")
    status_last_updated: datetime = Field(default_factory=datetime.utcnow, description="Last status update timestamp")
    status_source: str = Field(..., description="Source of status information")
    
    # Delivery information
    supplier_name: Optional[str] = Field(None, description="Material supplier name")
    expected_delivery_date: Optional[datetime] = Field(None, description="Expected delivery date")
    actual_delivery_date: Optional[datetime] = Field(None, description="Actual delivery date")
    delivery_reference: Optional[str] = Field(None, description="Delivery reference number/invoice")
    
    # Technical specifications
    technical_specifications: Dict[str, str] = Field(default_factory=dict, description="Technical specs (diameter, length, grade, etc.)")
    material_spec_url: Optional[str] = Field(None, description="URL to technical specification document")
    
    # Cost tracking
    unit_cost: Optional[Decimal] = Field(None, description="Cost per unit")
    total_cost: Optional[Decimal] = Field(None, description="Total cost for this material")
    
    # Conflict tracking
    status_conflicts: List[str] = Field(default_factory=list, description="IDs of related conflict records")
    last_conflict_check: Optional[datetime] = Field(None, description="Last conflict check timestamp")
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Record creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    notes: Optional[str] = Field(None, description="Additional notes")
    
    @validator('remaining_required')
    def calculate_remaining(cls, v, values):
        if 'total_ordered' in values and 'total_installed' in values:
            return values['total_ordered'] - values['total_installed']
        return v
    
    @validator('total_cost')
    def calculate_total_cost(cls, v, values):
        if 'unit_cost' in values and 'total_ordered' in values:
            if values['unit_cost'] is not None:
                return values['unit_cost'] * values['total_ordered']
        return v
    
    class Config:
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

### 2.5 Document Metadata Schema

```python
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime
from enum import Enum

class DocumentType(str, Enum):
    TECHNICAL_SPECIFICATION = "technical_specification"  # ТУ
    PERMIT_GATI = "permit_gati"  # ГАТИ
    PERMIT_OATI = "permit_oati"  # ОАТИ
    EXECUTIVE_BLUEPRINT = "executive_blueprint"  # РД
    PROJECT_BLUEPRINT = "project_blueprint"  # ПД
    INVOICE = "invoice"
    CORPORATE_ACT_KS2 = "corporate_act_ks2"  # КС-2
    CORPORATE_ACT_KS3 = "corporate_act_ks3"  # КС-3
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
    """Extracted during night vision processing (Stamps, versions, issuing authority)."""
    
    document_id: str = Field(..., description="Unique document identifier")
    project_id: str = Field(..., description="Associated project ID")
    document_type: DocumentType = Field(..., description="Type of document")
    
    # Source information
    source_url: str = Field(..., description="Source URL (Google Drive, email, etc.)")
    source_type: str = Field(..., description="Source system: 'google_drive', 'email', 'telegram'")
    file_name: str = Field(..., description="Original file name")
    file_size_bytes: int = Field(..., description="File size in bytes")
    mime_type: Optional[str] = Field(None, description="File MIME type")
    
    # Version control
    version_index: int = Field(default=1, description="Document version number")
    is_latest_version: bool = Field(default=True, description="Whether this is the latest version")
    previous_version_id: Optional[str] = Field(None, description="ID of previous version")
    next_version_id: Optional[str] = Field(None, description="ID of next version")
    version_conflict_detected: bool = Field(default=False, description="Whether version conflict was detected")
    
    # Vision processing results
    stamps_present: bool = Field(default=False, description="Whether physical stamps were detected")
    stamp_verification_status: StampVerificationStatus = Field(default=StampVerificationStatus.NOT_CHECKED, description="Stamp verification status")
    detected_stamps: List[str] = Field(default_factory=list, description="List of detected stamp descriptions")
    
    signatures_present: bool = Field(default=False, description="Whether signatures were detected")
    signature_verification_status: StampVerificationStatus = Field(default=StampVerificationStatus.NOT_CHECKED, description="Signature verification status")
    detected_signatures: List[str] = Field(default_factory=list, description="List of detected signature descriptions")
    
    # Document content metadata
    issuing_authority: Optional[str] = Field(None, description="Organization that issued the document")
    document_date: Optional[datetime] = Field(None, description="Date on the document")
    valid_from: Optional[datetime] = Field(None, description="Document validity start date")
    valid_until: Optional[datetime] = Field(None, description="Document validity end date")
    document_number: Optional[str] = Field(None, description="Document number/identifier")
    
    # Processing metadata
    processed_at: datetime = Field(default_factory=datetime.utcnow, description="Vision processing timestamp")
    processing_status: str = Field(default="pending", description="Processing status: 'pending', 'processing', 'completed', 'failed'")
    processing_errors: List[str] = Field(default_factory=list, description="Processing error messages")
    
    # Content extraction
    extracted_text_summary: Optional[str] = Field(None, description="Brief summary of extracted text")
    key_entities: List[str] = Field(default_factory=list, description="Key entities mentioned in document")
    monetary_amounts: List[float] = Field(default_factory=list, description="Monetary amounts found in document")
    dates_mentioned: List[str] = Field(default_factory=list, description="Dates mentioned in document")
    
    # Chunking information (for RAG)
    chunk_count: int = Field(default=0, description="Number of chunks created for RAG")
    chunk_ids: List[str] = Field(default_factory=list, description="IDs of chunks in vector database")
    
    # Cross-references
    related_document_ids: List[str] = Field(default_factory=list, description="IDs of related documents")
    referenced_in_chat_ids: List[str] = Field(default_factory=list, description="Chat messages referencing this document")
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Record creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    metadata: Dict[str, str] = Field(default_factory=dict, description="Additional metadata")
    
    class Config:
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

### 2.6 Extracted Event Schema (Chronological Resolution)

```python
from pydantic import BaseModel, Field, validator
from typing import Optional, List
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
    EXPLICIT_DATE = "explicit_date"  # "2024-08-20"
    RELATIVE_PHRASE = "relative_phrase"  # "next Thursday at 2 PM"
    DURATION_FROM_DATE = "duration_from_date"  # "valid for 3 years starting from 12.04.2024"
    INFERRED = "inferred"  # Contextually inferred
    MANUAL = "manual"  # Manually entered

class ExtractedEventSchema(BaseModel):
    """Explicit schema for event extraction with strict date parsing and normalization."""
    
    event_id: str = Field(..., description="Unique event identifier")
    project_id: str = Field(..., description="Associated project ID")
    event_type: EventType = Field(..., description="Type of event")
    
    # Raw extraction data
    raw_text: str = Field(..., description="Original text containing the event information")
    source_document_id: Optional[str] = Field(None, description="ID of document where event was found")
    source_chat_message_id: Optional[str] = Field(None, description="ID of chat message where event was found")
    source_type: str = Field(..., description="Source type: 'document', 'chat', 'email', 'manual'")
    
    # Date extraction and normalization
    original_date_phrase: str = Field(..., description="Original date phrase as found in text")
    extraction_method: DateExtractionMethod = Field(..., description="Method used for date extraction")
    extraction_confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence in extraction (0-1)")
    
    # Normalized ISO 8601 dates
    target_date: datetime = Field(..., description="Normalized target date in ISO 8601 format")
    target_date_timezone: str = Field(default="UTC", description="Timezone for target date")
    
    # Duration-based events
    is_duration_based: bool = Field(default=False, description="Whether event is based on a duration")
    duration_start_date: Optional[datetime] = Field(None, description="Start date for duration-based events")
    duration_value: Optional[int] = Field(None, description="Duration value (number of units)")
    duration_unit: Optional[str] = Field(None, description="Duration unit: 'days', 'months', 'years'")
    
    # Event details
    event_title: str = Field(..., description="Human-readable event title")
    event_description: Optional[str] = Field(None, description="Detailed event description")
    location: Optional[str] = Field(None, description="Event location (if applicable)")
    participants: List[str] = Field(default_factory=list, description="List of participants/attendees")
    
    # Importance and notifications
    importance_level: str = Field(default="medium", description="Importance: 'low', 'medium', 'high', 'critical'")
    notification_threshold_days: int = Field(default=30, description="Days before event to start notifications")
    notification_threshold_hours: Optional[int] = Field(None, description="Hours before event for immediate notifications")
    
    # Reference information
    reference_url: Optional[str] = Field(None, description="URL to source document/reference")
    reference_text: Optional[str] = Field(None, description="Contextual text around the event mention")
    
    # Processing metadata
    extracted_at: datetime = Field(default_factory=datetime.utcnow, description="Event extraction timestamp")
    extracted_by: str = Field(..., description="System or user who extracted the event")
    verified: bool = Field(default=False, description="Whether event has been verified by human")
    verified_by: Optional[str] = Field(None, description="User ID who verified the event")
    verified_at: Optional[datetime] = Field(None, description="Verification timestamp")
    
    # Status tracking
    event_status: str = Field(default="upcoming", description="Status: 'upcoming', 'in_progress', 'completed', 'cancelled', 'missed'")
    completed_at: Optional[datetime] = Field(None, description="Actual completion timestamp")
    completion_notes: Optional[str] = Field(None, description="Notes on event completion")
    
    # Cross-references
    related_conflict_ids: List[str] = Field(default_factory=list, description "IDs of related conflicts")
    related_material_ids: List[str] = Field(default_factory=list, description="IDs of related materials")
    
    @validator('target_date')
    def validate_iso8601(cls, v):
        """Ensure target_date is in ISO 8601 format."""
        if not isinstance(v, datetime):
            raise ValueError('target_date must be a datetime object')
        return v
    
    @validator('extraction_confidence')
    def validate_confidence(cls, v):
        """Ensure confidence is between 0 and 1."""
        if not 0.0 <= v <= 1.0:
            raise ValueError('extraction_confidence must be between 0 and 1')
        return v
    
    class Config:
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

### 2.7 Deadline Registry Schema

```python
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum

class NotificationStatus(str, Enum):
    NOT_NOTIFIED = "not_notified"
    SCHEDULED = "scheduled"
    NOTIFIED = "notified"
    ACKNOWLEDGED = "acknowledged"
    FAILED = "failed"

class DeadlineRegistrySchema(BaseModel):
    """SQLite table schema for deadline tracking and proactive notifications."""
    
    id: int = Field(..., description="Auto-incrementing primary key")
    project_id: str = Field(..., description="Associated project ID")
    event_id: str = Field(..., description="Reference to ExtractedEventSchema.event_id")
    
    # Event details
    event_type: str = Field(..., description="Type of event (permit_expiration, client_meeting, etc.)")
    event_title: str = Field(..., description="Human-readable event title")
    target_date: datetime = Field(..., description="Target date for the event")
    
    # Notification targets
    target_telegram_chat_id: int = Field(..., description="Telegram chat ID to send notifications to")
    additional_notify_user_ids: list = Field(default_factory=list, description="Additional specific user IDs to notify")
    
    # Notification configuration
    notification_threshold_days: int = Field(default=30, description="Days before event to notify")
    notification_threshold_hours: Optional[int] = Field(None, description="Hours before event for urgent notifications")
    
    # Reference information
    source_reference_url: Optional[str] = Field(None, description="URL to source document")
    source_reference_id: Optional[str] = Field(None, description="ID of source document/message")
    
    # Notification tracking
    notified_status: NotificationStatus = Field(default=NotificationStatus.NOT_NOTIFIED, description="Current notification status")
    first_notification_sent_at: Optional[datetime] = Field(None, description="Timestamp of first notification")
    last_notification_sent_at: Optional[datetime] = Field(None, description="Timestamp of most recent notification")
    notification_count: int = Field(default=0, description="Number of notifications sent")
    notification_error_message: Optional[str] = Field(None, description="Error message if notification failed")
    
    # Event status
    event_status: str = Field(default="upcoming", description="Event status: 'upcoming', 'completed', 'cancelled', 'missed'")
    event_completed_at: Optional[datetime] = Field(None, description="Actual event completion timestamp")
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Record creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    notes: Optional[str] = Field(None, description="Additional notes")
    
    class Config:
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

---

## 3. Hybrid RAG Router Interface

### 3.1 Query Type Classification

The Hybrid RAG Router must determine the optimal retrieval strategy based on query characteristics:

```python
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union
from enum import Enum

class QueryType(str, Enum):
    SQL_ONLY = "sql_only"  # Pure structured data query (e.g., "How much money spent?")
    VECTOR_ONLY = "vector_only"  # Pure semantic search (e.g., "What are our project risks?")
    JOINT_RETRIEVAL = "joint_retrieval"  # Combined SQL + Vector (e.g., "Show me material delays for Project X")
    UNSUPPORTED = "unsupported"  # Query outside system capabilities

class QueryIntent(str, Enum):
    FINANCIAL_SUMMARY = "financial_summary"
    MATERIAL_STATUS = "material_status"
    DOCUMENT_SEARCH = "document_search"
    RISK_ANALYSIS = "risk_analysis"
    DEADLINE_CHECK = "deadline_check"
    CONFLICT_RESOLUTION = "conflict_resolution"
    GENERAL_KNOWLEDGE = "general_knowledge"
    CROSS_PROJECT_ANALOGY = "cross_project_analogy"

class RAGQueryRequest(BaseModel):
    """Input schema for RAG Router."""
    
    query_text: str = Field(..., description="User's natural language query")
    project_id: Optional[str] = Field(None, description="Project ID to scope query (None for global)")
    user_id: int = Field(..., description="Telegram user ID making the query")
    user_role: str = Field(..., description="User role for RBAC: 'admin', 'site_manager', 'worker'")
    chat_id: int = Field(..., description="Telegram chat ID where query originated")
    
    # Query context
    conversation_history: List[Dict[str, str]] = Field(default_factory=list, description="Recent conversation for context")
    mentioned_entities: List[str] = Field(default_factory=list, description="Entities mentioned in query")
    
    class Config:
        json_schema_extra = {
            "example": {
                "query_text": "How much have we spent on cable trays for Sector 7?",
                "project_id": "PROJ-2024-001",
                "user_id": 123456789,
                "user_role": "admin",
                "chat_id": -1001234567890,
                "conversation_history": [],
                "mentioned_entities": ["cable trays", "Sector 7"]
            }
        }

class RAGQueryRouting(BaseModel):
    """Router decision output."""
    
    query_type: QueryType = Field(..., description="Determined query type")
    query_intent: QueryIntent = Field(..., description="Determined query intent")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in routing decision")
    
    # SQL query components (if applicable)
    sql_query: Optional[str] = Field(None, description="Generated SQL query")
    sql_tables: List[str] = Field(default_factory=list, description="Tables to query")
    sql_aggregations: List[str] = Field(default_factory=list, description="Aggregation functions to apply")
    
    # Vector query components (if applicable)
    vector_search_query: Optional[str] = Field(None, description="Optimized query for vector search")
    vector_collections: List[str] = Field(default_factory=list, description="ChromaDB collections to search")
    vector_filters: Dict[str, Any] = Field(default_factory=dict, description="Metadata filters for vector search")
    top_k: int = Field(default=15, description="Number of chunks to retrieve")
    
    # Joint retrieval configuration
    re_rank_strategy: str = Field(default="semantic_similarity", description="Re-ranking strategy")
    context_window_size: int = Field(default=20, description="Number of chunks in final context")
    
    # Cross-project search
    enable_cross_project_search: bool = Field(default=False, description="Whether to search across all projects")
    cross_project_limit: int = Field(default=5, description="Max results from other projects")
    
    class Config:
        json_schema_extra = {
            "example": {
                "query_type": "joint_retrieval",
                "query_intent": "material_status",
                "confidence": 0.92,
                "sql_query": "SELECT SUM(unit_cost * total_ordered) FROM materials WHERE project_id = 'PROJ-2024-001' AND canonical_name LIKE '%cable tray%'",
                "sql_tables": ["materials", "financial_reports"],
                "sql_aggregations": ["SUM", "COUNT"],
                "vector_search_query": "cable trays delivery status delays Sector 7",
                "vector_collections": ["document_chunks", "chat_logs"],
                "vector_filters": {"project_id": "PROJ-2024-001"},
                "top_k": 15,
                "re_rank_strategy": "semantic_similarity",
                "context_window_size": 20,
                "enable_cross_project_search": False,
                "cross_project_limit": 5
            }
        }
```

### 3.2 Router Decision Logic

The router must implement the following decision tree:

```
QUERY INPUT
    │
    ├─ Contains financial keywords? (spent, budget, cost, invoice, KS-2, KS-3)
    │   └─ YES → SQL_ONLY or JOINT_RETRIEVAL
    │       ├─ Simple aggregation? → SQL_ONLY
    │       └─ Needs context/explanation? → JOINT_RETRIEVAL
    │
    ├─ Contains status/count keywords? (how many, status, delivered, installed)
    │   └─ YES → SQL_ONLY or JOINT_RETRIEVAL
    │       ├─ Direct status query? → SQL_ONLY
    │       └─ Status with explanation? → JOINT_RETRIEVAL
    │
    ├─ Contains semantic keywords? (risks, issues, problems, why, how, context)
    │   └─ YES → VECTOR_ONLY or JOINT_RETRIEVAL
    │       ├─ Pure semantic search? → VECTOR_ONLY
    │       └─ Semantic + structured data? → JOINT_RETRIEVAL
    │
    ├─ Contains deadline/temporal keywords? (when, deadline, expiration, meeting)
    │   └─ YES → JOINT_RETRIEVAL (SQL for dates + Vector for context)
    │
    ├─ Contains cross-project intent? (other projects, similar cases, precedent)
    │   └─ YES → VECTOR_ONLY with enable_cross_project_search=True
    │
    └─ Fallback → VECTOR_ONLY with re-ranking
```

### 3.3 Abstract Router Interface

```python
from abc import ABC, abstractmethod
from typing import Optional

class HybridRAGRouterInterface(ABC):
    """Abstract interface for Hybrid RAG Router implementation."""
    
    @abstractmethod
    async def classify_query(self, request: RAGQueryRequest) -> RAGQueryRouting:
        """
        Classify query and determine optimal retrieval strategy.
        
        Args:
            request: The incoming query request
            
        Returns:
            RAGQueryRouting with routing decision and query components
        """
        pass
    
    @abstractmethod
    async def execute_sql_query(self, routing: RAGQueryRouting) -> Dict[str, Any]:
        """
        Execute SQL query based on routing decision.
        
        Args:
            routing: The routing decision with SQL components
            
        Returns:
            Dictionary with query results and metadata
        """
        pass
    
    @abstractmethod
    async def execute_vector_search(self, routing: RAGQueryRouting) -> List[Dict[str, Any]]:
        """
        Execute vector search based on routing decision.
        
        Args:
            routing: The routing decision with vector components
            
        Returns:
            List of retrieved chunks with metadata
        """
        pass
    
    @abstractmethod
    async def re_rank_results(self, sql_results: Dict[str, Any], 
                              vector_results: List[Dict[str, Any]], 
                              routing: RAGQueryRouting) -> List[Dict[str, Any]]:
        """
        Re-rank and merge SQL and vector results for joint retrieval.
        
        Args:
            sql_results: Results from SQL query
            vector_results: Results from vector search
            routing: The routing decision
            
        Returns:
            Merged and re-ranked results
        """
        pass
    
    @abstractmethod
    async def format_context(self, results: List[Dict[str, Any]], 
                             routing: RAGQueryRouting) -> str:
        """
        Format retrieved results into context for LLM.
        
        Args:
            results: Merged results from retrieval
            routing: The routing decision
            
        Returns:
            Formatted context string for LLM prompt
        """
        pass
```

---

## 4. Step-by-Step Decoupled Module Specification

### Module 1: Ingestion Manager (Drive + IMAP)

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel

class IngestionItem(BaseModel):
    """Schema for items ingested from external sources."""
    
    item_id: str
    source_type: str  # 'google_drive', 'imap', 'telegram'
    project_id: str
    raw_content: Optional[str] = None
    metadata: Dict[str, Any] = {}
    source_url: str
    ingested_at: datetime
    processing_priority: int = 0  # Higher = more urgent
    requires_vision_processing: bool = False

class IngestionResult(BaseModel):
    """Result of ingestion operation."""
    
    success: bool
    items_ingested: List[str]
    errors: List[str]
    processing_time_seconds: float

class IngestionManagerInterface(ABC):
    """Abstract interface for Ingestion Manager."""
    
    @abstractmethod
    async def schedule_drive_ingestion(self, project_id: str) -> IngestionResult:
        """
        Schedule Google Drive ingestion for a specific project.
        
        Args:
            project_id: Project to ingest Drive data for
            
        Returns:
            IngestionResult with status and item IDs
        """
        pass
    
    @abstractmethod
    async def schedule_imap_ingestion(self, project_id: str) -> IngestionResult:
        """
        Schedule IMAP email ingestion for a specific project.
        
        Args:
            project_id: Project to ingest emails for
            
        Returns:
            IngestionResult with status and item IDs
        """
        pass
    
    @abstractmethod
    async def classify_email_project(self, email_content: str, 
                                   email_subject: str,
                                   available_projects: List[str]) -> Optional[str]:
        """
        Classify which project an email belongs to based on content.
        
        Args:
            email_content: Email body text
            email_subject: Email subject line
            available_projects: List of available project IDs
            
        Returns:
            Project ID if classified, None if unclassifiable
        """
        pass
    
    @abstractmethod
    async def queue_for_processing(self, item: IngestionItem) -> bool:
        """
        Queue an ingested item for processing.
        
        Args:
            item: The item to queue
            
        Returns:
            True if queued successfully
        """
        pass
    
    @abstractmethod
    async def get_ingestion_status(self, project_id: str) -> Dict[str, Any]:
        """
        Get current ingestion status for a project.
        
        Args:
            project_id: Project to check status for
            
        Returns:
            Status dictionary with ingestion metrics
        """
        pass
```

### Module 2: Telegram Interaction & STT Router

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel

class TelegramMessage(BaseModel):
    """Schema for Telegram messages."""
    
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

class STTRequest(BaseModel):
    """Schema for speech-to-text requests."""
    
    voice_file_id: str
    chat_id: int
    user_id: int
    message_id: int
    language: str = "ru"  # Default to Russian
    use_gpu: bool = True

class STTResult(BaseModel):
    """Result of speech-to-text processing."""
    
    success: bool
    transcribed_text: Optional[str]
    confidence: float
    processing_time_seconds: float
    error_message: Optional[str]

class MiaResponse(BaseModel):
    """Schema for Mia's responses."""
    
    response_text: str
    source_attributions: List[Dict[str, str]]
    conflict_notices: List[Dict[str, Any]]
    confidence: float
    requires_admin_confirmation: bool

class TelegramInteractionInterface(ABC):
    """Abstract interface for Telegram Interaction & STT Router."""
    
    @abstractmethod
    async def monitor_chat(self, chat_id: int) -> None:
        """
        Start monitoring a Telegram chat for messages.
        
        Args:
            chat_id: Telegram chat ID to monitor
        """
        pass
    
    @abstractmethod
    async def process_message(self, message: TelegramMessage) -> None:
        """
        Process an incoming Telegram message.
        
        Args:
            message: The message to process
        """
        pass
    
    @abstractmethod
    async def handle_voice_message(self, request: STTRequest) -> STTResult:
        """
        Handle voice message transcription.
        
        Args:
            request: STT request with voice file details
            
        Returns:
            STTResult with transcribed text
        """
        pass
    
    @abstractmethod
    async def check_mentions_mia(self, message: TelegramMessage) -> bool:
        """
        Check if message mentions Mia (@Mia).
        
        Args:
            message: The message to check
            
        Returns:
            True if Mia is mentioned
        """
        pass
    
    @abstractmethod
    async def send_response(self, chat_id: int, response: MiaResponse) -> bool:
        """
        Send Mia's response to a Telegram chat.
        
        Args:
            chat_id: Target chat ID
            response: Mia's response
            
        Returns:
            True if sent successfully
        """
        pass
    
    @abstractmethod
    async def log_message_to_rag(self, message: TelegramMessage) -> bool:
        """
        Log message to RAG system for context.
        
        Args:
            message: The message to log
            
        Returns:
            True if logged successfully
        """
        pass
    
    @abstractmethod
    async def detect_hardware_acceleration(self) -> bool:
        """
        Detect if GPU acceleration is available for Whisper.
        
        Returns:
            True if CUDA GPU is available
        """
        pass
```

### Module 3: Night Vision Parser & PDF Chunker

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel

class PDFChunk(BaseModel):
    """Schema for PDF document chunks."""
    
    chunk_id: str
    document_id: str
    project_id: str
    chunk_index: int
    content: str
    page_number: Optional[int] = None
    hierarchy_level: int = 0  # 0 = document root, 1 = section, 2 = subsection
    parent_chunk_id: Optional[str] = None
    child_chunk_ids: List[str] = []
    metadata: Dict[str, Any] = {}

class VisionProcessingRequest(BaseModel):
    """Schema for vision processing requests."""
    
    document_id: str
    file_path: str
    document_type: str
    project_id: str
    processing_options: Dict[str, Any] = {}

class VisionProcessingResult(BaseModel):
    """Result of vision processing."""
    
    success: bool
    document_metadata: Optional[DocumentMetadataSchema]
    chunks: List[PDFChunk]
    processing_time_seconds: float
    errors: List[str]

class VersionComparisonResult(BaseModel):
    """Result of document version comparison."""
    
    document_id: str
    current_version: int
    previous_version_id: Optional[str]
    differences_detected: bool
    difference_summary: Optional[str]
    is_latest_version: bool
    action_required: bool

class NightVisionParserInterface(ABC):
    """Abstract interface for Night Vision Parser & PDF Chunker."""
    
    @abstractmethod
    async def process_pdf_document(self, request: VisionProcessingRequest) -> VisionProcessingResult:
        """
        Process a PDF document with vision analysis.
        
        Args:
            request: Vision processing request
            
        Returns:
            VisionProcessingResult with metadata and chunks
        """
        pass
    
    @abstractmethod
    async def detect_stamps_and_signatures(self, file_path: str) -> Dict[str, Any]:
        """
        Detect physical stamps and signatures in document.
        
        Args:
            file_path: Path to document file
            
        Returns:
            Dictionary with detection results
        """
        pass
    
    @abstractmethod
    async def chunk_pdf_hierarchy(self, document_id: str, 
                                 file_path: str,
                                 project_id: str) -> List[PDFChunk]:
        """
        Chunk PDF document preserving hierarchy.
        
        Args:
            document_id: Document identifier
            file_path: Path to PDF file
            project_id: Associated project ID
            
        Returns:
            List of PDF chunks with hierarchy
        """
        pass
    
    @abstractmethod
    async def compare_document_versions(self, document_id: str, 
                                       new_version_metadata: DocumentMetadataSchema) -> VersionComparisonResult:
        """
        Compare new document version against existing versions.
        
        Args:
            document_id: Document identifier
            new_version_metadata: New version metadata
            
        Returns:
            VersionComparisonResult with comparison details
        """
        pass
    
    @abstractmethod
    async def extract_structured_data(self, document_id: str) -> Dict[str, Any]:
        """
        Extract structured data from processed document.
        
        Args:
            document_id: Document identifier
            
        Returns:
            Dictionary with extracted structured data
        """
        pass
    
    @abstractmethod
    async def schedule_night_processing(self) -> None:
        """
        Schedule night processing window (02:00 - 06:00).
        """
        pass
```

### Module 4: Conflict Resolver & Nomenclature Mapper

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel

class ConflictDetectionRequest(BaseModel):
    """Schema for conflict detection requests."""
    
    project_id: str
    new_fact: Any
    new_fact_source: str
    new_fact_timestamp: datetime
    new_fact_reference: Optional[str] = None
    fact_type: str  # 'nomenclature', 'quantitative', 'financial', 'status'

class ConflictDetectionResult(BaseModel):
    """Result of conflict detection."""
    
    conflict_detected: bool
    conflict_id: Optional[str]
    existing_conflicts: List[str]
    auto_escalated: bool
    escalation_reason: Optional[str]

class NomenclatureMapping(BaseModel):
    """Schema for nomenclature name mapping."""
    
    canonical_name: str
    alias_names: List[str]
    project_id: str
    material_category: Optional[str]
    confidence_score: float
    created_at: datetime
    verified_by: Optional[str] = None

class ConflictResolutionSuggestion(BaseModel):
    """Suggested resolution for a conflict."""
    
    conflict_id: str
    suggested_value: Any
    suggested_source: str
    confidence: float
    reasoning: str

class ConflictResolverInterface(ABC):
    """Abstract interface for Conflict Resolver & Nomenclature Mapper."""
    
    @abstractmethod
    async def detect_conflict(self, request: ConflictDetectionRequest) -> ConflictDetectionResult:
        """
        Detect if new fact conflicts with existing data.
        
        Args:
            request: Conflict detection request
            
        Returns:
            ConflictDetectionResult with detection status
        """
        pass
    
    @abstractmethod
    async def create_conflict_record(self, conflict_data: AmbiguityIssueSchema) -> str:
        """
        Create a new conflict record in the system.
        
        Args:
            conflict_data: Conflict data
            
        Returns:
            Conflict ID
        """
        pass
    
    @abstractmethod
    async def resolve_nomenclature_conflict(self, 
                                          name_a: str, 
                                          name_b: str,
                                          project_id: str) -> Optional[NomenclatureMapping]:
        """
        Attempt to resolve nomenclature conflict by mapping to canonical name.
        
        Args:
            name_a: First name variant
            name_b: Second name variant
            project_id: Project ID
            
        Returns:
            NomenclatureMapping if resolved, None otherwise
        """
        pass
    
    @abstractmethod
    async def get_unresolved_conflicts(self, project_id: Optional[str] = None) -> List[AmbiguityIssueSchema]:
        """
        Get list of unresolved conflicts.
        
        Args:
            project_id: Optional project ID to filter by
            
        Returns:
            List of unresolved conflicts
        """
        pass
    
    @abstractmethod
    async def escalate_critical_conflict(self, conflict_id: str) -> bool:
        """
        Immediately escalate a critical conflict to admins.
        
        Args:
            conflict_id: Conflict to escalate
            
        Returns:
            True if escalated successfully
        """
        pass
    
    @abstractmethod
    async def generate_conflict_summary(self, project_id: str) -> str:
        """
        Generate human-readable summary of conflicts for admin review.
        
        Args:
            project_id: Project ID
            
        Returns:
            Formatted conflict summary
        """
        pass
    
    @abstractmethod
    async def suggest_resolution(self, conflict_id: str) -> Optional[ConflictResolutionSuggestion]:
        """
        Suggest resolution for a conflict using LLM.
        
        Args:
            conflict_id: Conflict to analyze
            
        Returns:
            Resolution suggestion if available
        """
        pass
```

### Module 5: Hybrid RAG Storage Engine (SQLite + Vector)

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
from pydantic import BaseModel

class SQLQueryResult(BaseModel):
    """Result of SQL query execution."""
    
    success: bool
    rows: List[Dict[str, Any]]
    columns: List[str]
    execution_time_seconds: float
    error_message: Optional[str]

class VectorSearchResult(BaseModel):
    """Result of vector search."""
    
    chunk_id: str
    content: str
    similarity_score: float
    metadata: Dict[str, Any]
    document_id: Optional[str]

class StorageOperation(BaseModel):
    """Generic storage operation result."""
    
    success: bool
    operation_id: Optional[str]
    error_message: Optional[str]
    execution_time_seconds: float

class HybridRAGStorageInterface(ABC):
    """Abstract interface for Hybrid RAG Storage Engine."""
    
    # SQLite Operations
    @abstractmethod
    async def execute_sql_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> SQLQueryResult:
        """
        Execute SQL query on SQLite database.
        
        Args:
            query: SQL query string
            params: Query parameters
            
        Returns:
            SQLQueryResult with data
        """
        pass
    
    @abstractmethod
    async def insert_project_context(self, context: ProjectContextSchema) -> StorageOperation:
        """
        Insert project context into SQLite.
        
        Args:
            context: Project context data
            
        Returns:
            StorageOperation result
        """
        pass
    
    @abstractmethod
    async def insert_financial_report(self, report: FinancialReportSchema) -> StorageOperation:
        """
        Insert financial report into SQLite.
        
        Args:
            report: Financial report data
            
        Returns:
            StorageOperation result
        """
        pass
    
    @abstractmethod
    async def insert_material_status(self, material: MaterialStatusSchema) -> StorageOperation:
        """
        Insert material status into SQLite.
        
        Args:
            material: Material status data
            
        Returns:
            StorageOperation result
        """
        pass
    
    @abstractmethod
    async def insert_ambiguity_issue(self, issue: AmbiguityIssueSchema) -> StorageOperation:
        """
        Insert ambiguity issue into SQLite.
        
        Args:
            issue: Ambiguity issue data
            
        Returns:
            StorageOperation result
        """
        pass
    
    @abstractmethod
    async def insert_deadline_registry(self, deadline: DeadlineRegistrySchema) -> StorageOperation:
        """
        Insert deadline into registry table.
        
        Args:
            deadline: Deadline registry data
            
        Returns:
            StorageOperation result
        """
        pass
    
    # ChromaDB Operations
    @abstractmethod
    async def add_document_chunks(self, chunks: List[PDFChunk]) -> StorageOperation:
        """
        Add document chunks to ChromaDB.
        
        Args:
            chunks: List of chunks to add
            
        Returns:
            StorageOperation result
        """
        pass
    
    @abstractmethod
    async def add_chat_log(self, message: TelegramMessage, project_id: str) -> StorageOperation:
        """
        Add chat log to ChromaDB.
        
        Args:
            message: Telegram message
            project_id: Associated project ID
            
        Returns:
            StorageOperation result
        """
        pass
    
    @abstractmethod
    async def vector_search(self, 
                          query_text: str,
                          collection_name: str,
                          top_k: int = 15,
                          filters: Optional[Dict[str, Any]] = None) -> List[VectorSearchResult]:
        """
        Perform vector similarity search.
        
        Args:
            query_text: Query text
            collection_name: ChromaDB collection name
            top_k: Number of results to return
            filters: Metadata filters
            
        Returns:
            List of VectorSearchResult
        """
        pass
    
    @abstractmethod
    async def cross_project_search(self,
                                  query_text: str,
                                  exclude_project_id: str,
                                  top_k: int = 5) -> List[VectorSearchResult]:
        """
        Search across all projects excluding the current one.
        
        Args:
            query_text: Query text
            exclude_project_id: Project ID to exclude
            top_k: Number of results to return
            
        Returns:
            List of VectorSearchResult from other projects
        """
        pass
    
    # Cross-Project Precedent Mapping
    @abstractmethod
    async def add_precedent(self, 
                           project_id: str,
                           precedent_type: str,
                           description: str,
                           solution: str,
                           metadata: Dict[str, Any]) -> StorageOperation:
        """
        Add a precedent to the global knowledge base.
        
        Args:
            project_id: Source project ID
            precedent_type: Type of precedent (e.g., 'material_substitution')
            description: Problem description
            solution: Solution applied
            metadata: Additional metadata
            
        Returns:
            StorageOperation result
        """
        pass
    
    @abstractmethod
    async def search_precedents(self,
                               query_text: str,
                               precedent_type: Optional[str] = None) -> List[VectorSearchResult]:
        """
        Search for relevant precedents.
        
        Args:
            query_text: Query text
            precedent_type: Optional type filter
            
        Returns:
            List of relevant precedents
        """
        pass
```

### Module 6: RBAC Access Guard

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

class UserRole(str, Enum):
    ADMIN = "admin"
    SITE_MANAGER = "site_manager"
    WORKER = "worker"
    READ_ONLY = "read_only"

class Permission(str, Enum):
    VIEW_FINANCIAL_DATA = "view_financial_data"
    VIEW_MATERIAL_STATUS = "view_material_status"
    VIEW_DOCUMENTS = "view_documents"
    VIEW_CONFLICTS = "view_conflicts"
    RESOLVE_CONFLICTS = "resolve_conflicts"
    MANAGE_PROJECTS = "manage_projects"
    VIEW_ALL_PROJECTS = "view_all_projects"
    EDIT_METADATA = "edit_metadata"

class AccessRequest(BaseModel):
    """Schema for access control requests."""
    
    user_id: int
    telegram_username: Optional[str]
    project_id: Optional[str]
    requested_permission: Permission
    context: Dict[str, Any] = {}

class AccessDecision(BaseModel):
    """Result of access control decision."""
    
    granted: bool
    user_role: UserRole
    denied_reason: Optional[str]
    granted_permissions: List[Permission]

class User(BaseModel):
    """User schema for RBAC."""
    
    user_id: int
    telegram_username: str
    role: UserRole
    project_access: List[str]  # List of project IDs user can access
    created_at: datetime
    is_active: bool = True

class RBACAccessGuardInterface(ABC):
    """Abstract interface for RBAC Access Guard."""
    
    @abstractmethod
    async def verify_user(self, user_id: int, telegram_username: Optional[str]) -> Optional[User]:
        """
        Verify user identity and retrieve user data.
        
        Args:
            user_id: Telegram user ID
            telegram_username: Optional Telegram username
            
        Returns:
            User data if verified, None otherwise
        """
        pass
    
    @abstractmethod
    async def check_permission(self, request: AccessRequest) -> AccessDecision:
        """
        Check if user has permission for requested action.
        
        Args:
            request: Access request details
            
        Returns:
            AccessDecision with grant/deny result
        """
        pass
    
    @abstractmethod
    async def has_project_access(self, user_id: int, project_id: str) -> bool:
        """
        Check if user has access to specific project.
        
        Args:
            user_id: Telegram user ID
            project_id: Project ID
            
        Returns:
            True if user has access
        """
        pass
    
    @abstractmethod
    async def can_view_financial_data(self, user_id: int, project_id: str) -> bool:
        """
        Check if user can view financial data (KS-2/KS-3).
        
        Args:
            user_id: Telegram user ID
            project_id: Project ID
            
        Returns:
            True if user has financial data access
        """
        pass
    
    @abstractmethod
    async def can_resolve_conflicts(self, user_id: int) -> bool:
        """
        Check if user can resolve conflicts.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            True if user can resolve conflicts
        """
        pass
    
    @abstractmethod
    async def register_user(self, user_id: int, 
                           telegram_username: str,
                           role: UserRole,
                           project_access: List[str]) -> bool:
        """
        Register a new user in the system.
        
        Args:
            user_id: Telegram user ID
            telegram_username: Telegram username
            role: User role
            project_access: List of accessible project IDs
            
        Returns:
            True if registered successfully
        """
        pass
    
    @abstractmethod
    async def filter_response_by_permissions(self, 
                                            user_id: int,
                                            response_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Filter response data based on user permissions.
        
        Args:
            user_id: Telegram user ID
            response_data: Full response data
            
        Returns:
            Filtered response data
        """
        pass
```

---

## 5. Global Cross-Chat Intelligence Engine

### 5.1 Architecture Overview

The Global Cross-Chat Intelligence Engine enables knowledge sharing across different construction projects while maintaining data isolation at the storage level. This is implemented through:

1. **Unified Vector Storage**: All projects' chat logs, document chunks, and precedents are stored in ChromaDB with project_id metadata tags
2. **Metadata-Driven Retrieval**: Vector searches can be scoped to single projects or expanded globally
3. **Precedent Categorization**: Solutions and insights are tagged with semantic metadata for cross-project discovery
4. **Analogy Mapping Engine**: LLM-powered analysis identifies similar situations across projects

### 5.2 Precedent Schema

```python
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class PrecedentCategory(str, Enum):
    MATERIAL_SUBSTITUTION = "material_substitution"
    TECHNICAL_SOLUTION = "technical_solution"
    PROBLEM_RESOLUTION = "problem_resolution"
    PROCESS_IMPROVEMENT = "process_improVEMENT"
    RISK_MITIGATION = "risk_mitigation"
    STAKEHOLDER_MANAGEMENT = "stakeholder_management"
    REGULATORY_COMPLIANCE = "regulatory_compliance"
    OTHER = "other"

class PrecedentSchema(BaseModel):
    """Schema for cross-project precedent storage."""
    
    precedent_id: str = Field(..., description="Unique precedent identifier")
    source_project_id: str = Field(..., description="Project where precedent originated")
    source_chat_id: int = Field(..., description="Telegram chat where precedent was discussed")
    source_message_ids: List[str] = Field(default_factory=list, description="Related message IDs")
    
    # Precedent classification
    category: PrecedentCategory = Field(..., description="Precedent category")
    title: str = Field(..., description="Human-readable precedent title")
    problem_description: str = Field(..., description="Description of the original problem")
    solution_description: str = Field(..., description="Solution that was applied")
    
    # Outcome tracking
    outcome_status: str = Field(..., description="Outcome: 'successful', 'partial', 'failed'")
    outcome_notes: Optional[str] = Field(None, description="Notes on the outcome")
    
    # Applicability metadata
    applicable_contexts: List[str] = Field(default_factory=list, description="Contexts where this applies")
    constraints: List[str] = Field(default_factory=list, description="Constraints or limitations")
    material_mentions: List[str] = Field(default_factory=list, description="Materials mentioned")
    technical_specifications: Dict[str, str] = Field(default_factory=dict, description="Relevant technical specs")
    
    # Cross-reference
    related_document_ids: List[str] = Field(default_factory=list, description="Related documents")
    related_conflict_ids: List[str] = Field(default_factory=list, description="Related conflicts")
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Precedent creation timestamp")
    created_by: str = Field(..., description="System or user who created precedent")
    verified: bool = Field(default=False, description="Whether precedent has been verified")
    verified_by: Optional[str] = Field(None, description="User who verified precedent")
    usage_count: int = Field(default=0, description="Number of times this precedent was referenced")
    
    class Config:
        json_schema_extra = {
            "example": {
                "precedent_id": "PREC-2024-0892",
                "source_project_id": "PROJ-2024-001",
                "source_chat_id": -1001234567890,
                "source_message_ids": ["msg_456", "msg_457"],
                "category": "material_substitution",
                "title": "Cable Type Substitution - Sector 7",
                "problem_description": "Original cable type X unavailable due to supply chain issues",
                "solution_description": "Substituted with cable type Y after confirming technical compatibility with client",
                "outcome_status": "successful",
                "outcome_notes": "Client approved, no performance issues",
                "applicable_contexts": ["underground_cable", "fiber_optic", "supply_chain_backup"],
                "constraints": ["Requires client approval", "Must meet technical specifications"],
                "material_mentions": ["cable_type_x", "cable_type_y"],
                "created_at": "2024-08-17T10:30:00Z",
                "created_by": "mia_precedent_extractor",
                "verified": True,
                "verified_by": "admin_123",
                "usage_count": 3
            }
        }
```

### 5.3 Cross-Project Search Interface

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class CrossProjectSearchRequest(BaseModel):
    """Schema for cross-project search requests."""
    
    query_text: str
    current_project_id: str
    search_categories: Optional[List[PrecedentCategory]] = None
    exclude_current_project: bool = True
    max_results: int = 5
    min_similarity_score: float = 0.7

class CrossProjectSearchResult(BaseModel):
    """Result of cross-project search."""
    
    precedent_id: str
    source_project_id: str
    source_project_name: str
    similarity_score: float
    relevance_explanation: str
    precedent_data: PrecedentSchema

class CrossProjectIntelligenceInterface(ABC):
    """Abstract interface for Cross-Project Intelligence Engine."""
    
    @abstractmethod
    async def extract_precedent_from_chat(self, 
                                         project_id: str,
                                         chat_id: int,
                                         message_ids: List[str]) -> Optional[PrecedentSchema]:
        """
        Analyze chat messages to extract potential precedents.
        
        Args:
            project_id: Source project ID
            chat_id: Source chat ID
            message_ids: Message IDs to analyze
            
        Returns:
            PrecedentSchema if precedent extracted, None otherwise
        """
        pass
    
    @abstractmethod
    async def store_precedent(self, precedent: PrecedentSchema) -> bool:
        """
        Store precedent in global knowledge base.
        
        Args:
            precedent: Precedent to store
            
        Returns:
            True if stored successfully
        """
        pass
    
    @abstractmethod
    async def search_cross_project(self, request: CrossProjectSearchRequest) -> List[CrossProjectSearchResult]:
        """
        Search for relevant precedents across all projects.
        
        Args:
            request: Search request parameters
            
        Returns:
            List of relevant precedents from other projects
        """
        pass
    
    @abstractmethod
    async def find_analogous_situations(self, 
                                       current_problem: str,
                                       current_project_id: str) -> List[CrossProjectSearchResult]:
        """
        Find analogous situations from other projects.
        
        Args:
            current_problem: Description of current problem
            current_project_id: Current project ID to exclude
            
        Returns:
            List of analogous precedents
        """
        pass
    
    @abstractmethod
    async def update_precedent_usage(self, precedent_id: str) -> bool:
        """
        Update usage count for a precedent.
        
        Args:
            precedent_id: Precedent to update
            
        Returns:
            True if updated successfully
        """
        pass
```

---

## 6. Proactive Event Engine & Timeout Resolver

### 6.1 Architecture Overview

The Proactive Event Engine operates as a standalone asynchronous service that:

1. **Monitors Deadline Registry**: Queries the DeadlineRegistryTable at configurable intervals
2. **Evaluates Thresholds**: Checks if events are approaching notification thresholds
3. **Drafts Notifications**: Uses Ollama to generate context-aware, polite notifications
4. **Pushes Proactively**: Sends notifications to Telegram chats without @Mia tag requirement
5. **Tracks Notifications**: Maintains notification history and status

### 6.2 Scheduler Interface

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel

class ScheduledTask(BaseModel):
    """Schema for scheduled tasks."""
    
    task_id: str
    task_type: str  # 'ingestion', 'night_processing', 'deadline_check'
    schedule_expression: str  # Cron expression
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    is_active: bool = True
    task_params: Dict[str, Any] = {}

class TaskExecutionResult(BaseModel):
    """Result of task execution."""
    
    task_id: str
    success: bool
    execution_time_seconds: float
    error_message: Optional[str]
    result_data: Optional[Dict[str, Any]]

class NotificationDraft(BaseModel):
    """Drafted notification for proactive sending."""
    
    deadline_id: int
    project_id: str
    target_chat_id: int
    event_title: str
    days_until_event: int
    urgency_level: str
    drafted_message: str
    draft_confidence: float
    suggested_actions: List[str]

class SchedulerInterface(ABC):
    """Abstract interface for Central Scheduler."""
    
    @abstractmethod
    async def schedule_task(self, task: ScheduledTask) -> bool:
        """
        Schedule a new task.
        
        Args:
            task: Task to schedule
            
        Returns:
            True if scheduled successfully
        """
        pass
    
    @abstractmethod
    async def execute_task(self, task_id: str) -> TaskExecutionResult:
        """
        Execute a scheduled task.
        
        Args:
            task_id: Task to execute
            
        Returns:
            TaskExecutionResult
        """
        pass
    
    @abstractmethod
    async def check_deadlines(self) -> List[int]:
        """
        Check for deadlines approaching notification threshold.
        
        Returns:
            List of deadline IDs requiring notification
        """
        pass
    
    @abstractmethod
    async def draft_notification(self, deadline_id: int) -> Optional[NotificationDraft]:
        """
        Draft context-aware notification using Ollama.
        
        Args:
            deadline_id: Deadline to draft notification for
            
        Returns:
            NotificationDraft if drafted successfully
        """
        pass
    
    @abstractmethod
    async def send_proactive_notification(self, draft: NotificationDraft) -> bool:
        """
        Send proactive notification to Telegram chat.
        
        Args:
            draft: Notification draft to send
            
        Returns:
            True if sent successfully
        """
        pass
    
    @abstractmethod
    async def update_notification_status(self, 
                                        deadline_id: int,
                                        status: NotificationStatus,
                                        error_message: Optional[str] = None) -> bool:
        """
        Update notification status in deadline registry.
        
        Args:
            deadline_id: Deadline to update
            status: New notification status
            error_message: Optional error message
            
        Returns:
            True if updated successfully
        """
        pass
    
    @abstractmethod
    async def get_schedule_status(self) -> Dict[str, Any]:
        """
        Get current scheduler status.
        
        Returns:
            Dictionary with scheduler status
        """
        pass
```

### 6.3 Deadline Processing Logic

```
DEADLINE CHECK INTERVAL (every 10 minutes)
    │
    ├─ Query DeadlineRegistryTable for active events
    │   WHERE event_status = 'upcoming'
    │   AND notified_status IN ('not_notified', 'scheduled')
    │
    ├─ For each deadline:
    │   ├─ Calculate days_remaining = target_date - current_datetime
    │   ├─ Check if days_remaining <= notification_threshold_days
    │   ├─ If threshold crossed:
    │   │   ├─ Draft notification using Ollama
    │   │   ├─ Include: event context, urgency, suggested actions
    │   │   ├─ Send to target_telegram_chat_id
    │   │   └─ Update notified_status = 'notified'
    │   └─ If hours_threshold exists and hours_remaining <= hours_threshold:
    │       ├─ Send urgent notification
    │       └─ Update notification_count
    │
    └─ Log execution metrics
```

---

## 7. Integration and Data Flow

### 7.1 Complete Request Flow

```
USER QUERY (@Mia tag in Telegram)
    │
    ├─ Module 6: RBAC Access Guard
    │   ├─ Verify user identity
    │   ├─ Check project access
    │   └─ Determine permissions
    │
    ├─ Module 5: Hybrid RAG Router
    │   ├─ Classify query type (SQL/Vector/Joint)
    │   ├─ Generate SQL query if needed
    │   ├─ Generate vector search query if needed
    │   └─ Determine cross-project search needs
    │
    ├─ Module 5: Hybrid RAG Storage Engine
    │   ├─ Execute SQL query (SQLite)
    │   ├─ Execute vector search (ChromaDB)
    │   ├─ Perform cross-project precedent search if needed
    │   └─ Return structured results
    │
    ├─ Hybrid RAG Router
    │   ├─ Re-rank results (10-20 chunks)
    │   ├─ Merge SQL and vector results
    │   ├─ Format context for LLM
    │   └─ Check for conflicts in results
    │
    ├─ Local Ollama Inference
    │   ├─ Process query with re-ranked context
    │   ├─ Generate response
    │   └─ Include source attributions
    │
    ├─ Module 4: Conflict Resolver
    │   ├─ Check response for conflicting facts
    │   ├─ Add source citations for conflicts
    │   └─ Flag unresolved conflicts
    │
    ├─ Module 6: RBAC Access Guard
    │   └─ Filter response based on user permissions
    │
    └─ Module 2: Telegram Interaction
        └─ Send formatted response to chat
```

### 7.2 Night Processing Flow

```
NIGHT PROCESSING WINDOW (02:00 - 06:00)
    │
    ├─ Module 7: Central Scheduler triggers night processing
    │
    ├─ Module 1: Ingestion Manager
    │   ├─ Queue accumulated PDFs and drawings
    │   └─ Prioritize vision processing tasks
    │
    ├─ Module 3: Night Vision Parser
    │   ├─ Process queued documents
    │   ├─ Detect stamps and signatures
    │   ├─ Extract document metadata
    │   ├─ Chunk documents with hierarchy
    │   └─ Compare versions
    │
    ├─ Module 5: Hybrid RAG Storage Engine
    │   ├─ Store document metadata (SQLite)
    │   ├─ Store document chunks (ChromaDB)
    │   └─ Update version control
    │
    ├─ Module 4: Conflict Resolver
    │   ├─ Detect conflicts in new data
    │   ├─ Auto-escalate critical conflicts
    │   └─ Update conflict registry
    │
    ├─ Cross-Project Intelligence Engine
    │   ├─ Analyze chat logs for precedents
    │   ├─ Extract and categorize precedents
    │   └─ Update global knowledge base
    │
    └─ Module 5: Event Extraction
        ├─ Extract events from documents
        ├─ Normalize dates to ISO 8601
        └─ Update DeadlineRegistryTable
```

---

## 8. Implementation Constraints & Guidelines

### 8.1 Deterministic Implementation Requirements

1. **No Ambiguous Implementations**: All abstract methods must have clear input/output contracts
2. **Strict Type Hints**: All parameters and return values must be fully typed
3. **Pydantic Validation**: All data structures must use Pydantic v2 schemas
4. **Error Handling**: All methods must define clear error states and return types
5. **Mock Boundaries**: All external dependencies (Ollama, Google Drive, Telegram) must have clear interface boundaries

### 8.2 Local LLM Optimization

1. **Context Window Management**: Limit context to 10-20 chunks for smaller LLMs
2. **Prompt Determinism**: Use structured prompts with clear formatting requirements
3. **Output Parsing**: Define strict output formats for LLM responses
4. **Fallback Strategies**: Implement graceful degradation when LLM fails
5. **Caching**: Cache LLM responses where appropriate to reduce inference load

### 8.3 Performance Considerations

1. **Asynchronous Operations**: All I/O operations must be async
2. **Queue Management**: Implement proper backpressure for message queues
3. **Batch Processing**: Batch vector embeddings and database operations
4. **Resource Limits**: Implement memory and CPU limits for Ollama calls
5. **Connection Pooling**: Use connection pooling for SQLite and ChromaDB

### 8.4 Security Requirements

1. **RBAC Enforcement**: All data access must go through RBAC module
2. **Data Isolation**: Project data must be isolated at database level
3. **Audit Logging**: All administrative actions must be logged
4. **Secrets Management**: Never log or expose API keys or credentials
5. **Input Validation**: All user inputs must be validated before processing

---

## 9. Testing Strategy

### 9.1 Unit Testing

- Test each Pydantic schema with valid and invalid data
- Test abstract interface implementations with mock dependencies
- Test conflict detection logic with known conflict scenarios
- Test RBAC permission checks with various user roles

### 9.2 Integration Testing

- Test end-to-end ingestion flow from Drive to RAG
- Test query flow from Telegram to response
- Test cross-project search functionality
- Test deadline notification triggers

### 9.3 LLM Testing

- Test Ollama integration with various prompt templates
- Test STT transcription accuracy
- Test vision processing with sample documents
- Test precedent extraction from chat logs

---

## 10. Deployment Architecture

### 10.1 System Requirements

- **OS**: Linux (Ubuntu 22.04 LTS recommended) or Windows with WSL2
- **CPU**: 8+ cores for concurrent processing
- **RAM**: 32GB+ (16GB for Ollama, 8GB for ChromaDB, 8GB for system)
- **GPU**: NVIDIA GPU with 8GB+ VRAM (optional but recommended for Whisper)
- **Storage**: 500GB+ SSD for vector database and document storage

### 10.2 Service Architecture

```
SYSTEM SERVICES
├─ Redis (Message Queue & Caching)
├─ SQLite (Structured Data Storage)
├─ ChromaDB (Vector Database)
├─ Ollama (Local LLM Inference)
├─ Whisper (STT Engine)
└─ Mia Application (Python 3.11+)
    ├─ Ingestion Manager Service
    ├─ Telegram Bot Service
    ├─ Night Processing Service
    ├─ Scheduler Service
    └─ API Service (if needed)
```

### 10.3 Environment Configuration

```yaml
# config.yaml example
mia:
  environment: production
  log_level: INFO
  
ollama:
  base_url: "http://localhost:11434"
  model: "gemma:7b"  # or "qwen2.5-coder:7b"
  timeout: 300
  max_context_tokens: 4096

databases:
  sqlite:
    path: "/var/lib/mia/mia.db"
  chromadb:
    path: "/var/lib/mia/chroma"
  
telegram:
  bot_token: "${TELEGRAM_BOT_TOKEN}"
  api_timeout: 30
  
google_drive:
  credentials_path: "/etc/mia/gdrive_credentials.json"
  
scheduler:
  timezone: "Europe/Moscow"
  ingestion_interval: "*/10 7-19 * * *"  # Every 10 mins, 7AM-7PM
  night_processing: "0 2 * * *"  # 2 AM daily
  deadline_check: "*/10 * * * *"  # Every 10 mins
  
whisper:
  model_size: "base"  # or "small", "medium"
  use_gpu: true
  language: "ru"
```

---

## 11. Future Extensibility

### 11.1 Planned Enhancements

1. **Multi-Modal RAG**: Add image search capabilities to vector database
2. **Advanced Analytics**: Build dashboards for project insights
3. **Mobile App**: Develop mobile interface for field workers
4. **Integration Hub**: Add API for third-party system integrations
5. **ML Models**: Train custom models for construction-specific tasks

### 11.2 Scalability Considerations

1. **Horizontal Scaling**: Design for multiple worker processes
2. **Database Sharding**: Plan for ChromaDB scaling at 100+ projects
3. **Load Balancing**: Add load balancer for Telegram bot instances
4. **Caching Layer**: Implement Redis caching for frequent queries
5. **Monitoring**: Add comprehensive metrics and alerting

---

## Conclusion

This architecture provides a comprehensive, deterministic specification for Mia - an AI-driven Construction Project Management OS optimized for implementation by smaller local LLMs. The modular design with strict interfaces and Pydantic schemas ensures that each component can be implemented independently while maintaining system coherence.

The architecture addresses all core requirements:
- Multi-source data ingestion (Drive, IMAP, Telegram)
- Hybrid RAG with SQL and vector search
- Conflict resolution with source attribution
- Cross-project knowledge sharing
- Proactive deadline notifications
- RBAC security
- Night vision processing for documents
- Local deployment with Ollama integration

The specification is 100% deterministic, providing clear implementation guidance for Gemma 3 12B or Qwen 3 Coder 14B via Ollama, ensuring reproducible and maintainable code generation.
