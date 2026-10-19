"""Nighttime audit vector for detecting construction data gaps and inconsistencies"""

import logging
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from enum import Enum
import threading

from app.core.schemas import AuditGapSchema, AuditSeverity
from app.modules.storage.database import get_db_connection
from app.modules.storage.questions_gateway import QuestionsGateway

logger = logging.getLogger(__name__)


class AuditPattern(str, Enum):
    """Types of audit patterns for construction data gaps."""
    CONTRACT_DOCUMENT_GAP = "contract_document_gap_audit"
    FINANCIAL_BUDGET_MISMATCH = "financial_budget_mismatch_audit"
    MATERIAL_STATUS_INCONSISTENCY = "material_status_inconsistency_audit"
    DEADLINE_DOCUMENT_GAP = "deadline_document_gap_audit"
    NAMENCLATURE_CONFLICT = "nomenclature_conflict_audit"
    RAG_WHITE_SPOT = "rag_white_spot_audit"


class NighttimeAuditVector:
    """
    Nighttime audit vector for detecting construction data gaps.
    
    Runs during nighttime mode (19:00-07:00) to perform background
    consistency checks across all schemas and identify white spots
    in documentation.
    """
    
    def __init__(self, project_root_path, questions_gateway: Optional[QuestionsGateway] = None):
        """
        Initialize the nighttime audit vector.
        
        Args:
            project_root_path: Path to project root for QUESTIONS.md access
            questions_gateway: Questions Gateway for critical gap notifications
        """
        self.project_root_path = project_root_path
        self.questions_gateway = questions_gateway
        
        self.is_running = False
        self.audit_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        
        # Audit statistics
        self.audits_performed = 0
        self.gaps_detected = 0
        self.critical_gaps = 0
        self.last_audit_time: Optional[datetime] = None
        
        logger.info("Nighttime Audit Vector initialized")
    
    def start(self):
        """Start the nighttime audit process."""
        if self.is_running:
            logger.warning("Audit vector already running")
            return False
        
        self.is_running = True
        self.stop_event.clear()
        
        self.audit_thread = threading.Thread(target=self._audit_loop, daemon=True)
        self.audit_thread.start()
        
        logger.info("Nighttime Audit Vector started")
        return True
    
    def stop(self):
        """Stop the nighttime audit process."""
        if not self.is_running:
            logger.warning("Audit vector not running")
            return False
        
        logger.info("Stopping Nighttime Audit Vector")
        self.stop_event.set()
        self.is_running = False
        
        if self.audit_thread:
            self.audit_thread.join(timeout=30)
        
        logger.info("Nighttime Audit Vector stopped")
        return True
    
    def _audit_loop(self):
        """Main audit loop that runs during nighttime hours."""
        logger.info("Audit loop started")
        
        while not self.stop_event.is_set():
            try:
                # Check if we're in nighttime mode (19:00-07:00)
                if not self._is_nighttime():
                    logger.debug("Daytime mode - audit paused")
                    time.sleep(300)  # Check every 5 minutes
                    continue
                
                # Perform audit cycle
                self._perform_audit_cycle()
                
                # Wait before next audit cycle (check every hour)
                time.sleep(3600)
                
            except Exception as e:
                logger.error(f"Error in audit loop: {e}")
                time.sleep(60)  # Wait 1 minute before retry
        
        logger.info("Audit loop stopped")
    
    def _is_nighttime(self) -> bool:
        """Check if current time is in nighttime mode (19:00-07:00)."""
        now = datetime.now().time()
        morning = datetime.strptime("07:00", "%H:%M").time()
        evening = datetime.strptime("19:00", "%H:%M").time()
        
        return not (morning <= now < evening)
    
    def _perform_audit_cycle(self):
        """Perform a full audit cycle across all patterns."""
        logger.info("Starting audit cycle")
        self.last_audit_time = datetime.now()
        
        try:
            # Run all audit patterns
            gaps = []
            
            gaps.extend(self._audit_contract_document_gaps())
            gaps.extend(self._audit_financial_budget_mismatches())
            gaps.extend(self._audit_material_status_inconsistencies())
            gaps.extend(self._audit_deadline_document_gaps())
            gaps.extend(self._audit_nomenclature_conflicts())
            gaps.extend(self._audit_rag_white_spots())
            
            # Process detected gaps
            for gap in gaps:
                self._process_detected_gap(gap)
            
            self.audits_performed += 1
            self.gaps_detected += len(gaps)
            self.critical_gaps += sum(1 for g in gaps if g.severity == AuditSeverity.CRITICAL)
            
            logger.info(f"Audit cycle completed: {len(gaps)} gaps detected")
            
        except Exception as e:
            logger.error(f"Error in audit cycle: {e}")
    
    def _audit_contract_document_gaps(self) -> List[AuditGapSchema]:
        """Audit for gaps between contracts and related documents."""
        gaps = []
        
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Find permits without corresponding hidden works acts
                cursor.execute("""
                    SELECT d.document_id, d.project_id, d.document_type, d.document_number
                    FROM document_metadata d
                    WHERE d.document_type = 'permit'
                    AND d.document_id NOT IN (
                        SELECT document_id FROM document_metadata 
                        WHERE document_type = 'hidden_works_act'
                    )
                """)
                
                for row in cursor.fetchall():
                    gap = AuditGapSchema(
                        audit_id=f"AUDIT-CONTRACT-{datetime.now().strftime('%Y%m%d%H%M%S')}-{row['document_id']}",
                        severity=AuditSeverity.HIGH,
                        gap_type="document_missing",
                        project_id=row['project_id'],
                        affected_schemas=["DocumentMetadataSchema"],
                        affected_entity_ids=[row['document_id']],
                        title=f"Missing Hidden Works Act for Permit {row['document_number']}",
                        description=f"Permit {row['document_number']} exists but no corresponding acts of hidden works found in DocumentMetadataSchema.",
                        detected_by=AuditPattern.CONTRACT_DOCUMENT_GAP.value,
                        evidence_data={
                            "permit_found": True,
                            "permit_type": row['document_type'],
                            "hidden_works_acts": 0
                        },
                        expected_state="At least one act of hidden works for each permit",
                        actual_state="No acts of hidden works found",
                        rag_performed=False,
                        manual_action_required=True
                    )
                    gaps.append(gap)
                
        except Exception as e:
            logger.error(f"Error in contract document audit: {e}")
        
        return gaps
    
    def _audit_financial_budget_mismatches(self) -> List[AuditGapSchema]:
        """Audit for mismatches between budget reports and financial records."""
        gaps = []
        
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Find budget utilization anomalies
                cursor.execute("""
                    SELECT report_id, project_id, total_budget, spent_budget, budget_utilization_percent
                    FROM financial_reports
                    WHERE budget_utilization_percent > 110 OR budget_utilization_percent < 0
                """)
                
                for row in cursor.fetchall():
                    severity = AuditSeverity.CRITICAL if row['budget_utilization_percent'] > 110 else AuditSeverity.MEDIUM
                    
                    gap = AuditGapSchema(
                        audit_id=f"AUDIT-FINANCE-{datetime.now().strftime('%Y%m%d%H%M%S')}-{row['report_id']}",
                        severity=severity,
                        gap_type="budget_anomaly",
                        project_id=row['project_id'],
                        affected_schemas=["FinancialReportSchema"],
                        affected_entity_ids=[row['report_id']],
                        title=f"Budget Utilization Anomaly: {row['budget_utilization_percent']:.1f}%",
                        description=f"Financial report shows unusual budget utilization: {row['budget_utilization_percent']:.1f}% (spent: {row['spent_budget']}, total: {row['total_budget']}).",
                        detected_by=AuditPattern.FINANCIAL_BUDGET_MISMATCH.value,
                        evidence_data={
                            "total_budget": float(row['total_budget']),
                            "spent_budget": float(row['spent_budget']),
                            "utilization_percent": float(row['budget_utilization_percent'])
                        },
                        expected_state="Budget utilization between 0% and 100%",
                        actual_state=f"Budget utilization at {row['budget_utilization_percent']:.1f}%",
                        rag_performed=False,
                        manual_action_required=True
                    )
                    gaps.append(gap)
                
        except Exception as e:
            logger.error(f"Error in financial budget audit: {e}")
        
        return gaps
    
    def _audit_material_status_inconsistencies(self) -> List[AuditGapSchema]:
        """Audit for inconsistencies in material status across sources."""
        gaps = []
        
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Find materials with status conflicts
                cursor.execute("""
                    SELECT material_id, project_id, canonical_name, current_status, status_conflicts
                    FROM material_status
                    WHERE status_conflicts != '[]'
                """)
                
                for row in cursor.fetchall():
                    gap = AuditGapSchema(
                        audit_id=f"AUDIT-MATERIAL-{datetime.now().strftime('%Y%m%d%H%M%S')}-{row['material_id']}",
                        severity=AuditSeverity.MEDIUM,
                        gap_type="status_conflict",
                        project_id=row['project_id'],
                        affected_schemas=["MaterialStatusSchema"],
                        affected_entity_ids=[row['material_id']],
                        title=f"Material Status Conflict: {row['canonical_name']}",
                        description=f"Material {row['canonical_name']} has conflicting status information: {row['status_conflicts']}.",
                        detected_by=AuditPattern.MATERIAL_STATUS_INCONSISTENCY.value,
                        evidence_data={
                            "current_status": row['current_status'],
                            "status_conflicts": row['status_conflicts']
                        },
                        expected_state="Consistent material status across all sources",
                        actual_state=f"Conflicting statuses: {row['status_conflicts']}",
                        rag_performed=False,
                        manual_action_required=True
                    )
                    gaps.append(gap)
                
        except Exception as e:
            logger.error(f"Error in material status audit: {e}")
        
        return gaps
    
    def _audit_deadline_document_gaps(self) -> List[AuditGapSchema]:
        """Audit for gaps between deadlines and supporting documents."""
        gaps = []
        
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Find upcoming deadlines without supporting documents
                cursor.execute("""
                    SELECT id, project_id, event_id, event_title, target_date
                    FROM deadline_registry
                    WHERE event_status = 'upcoming'
                    AND target_date <= date('now', '+7 days')
                """)
                
                for row in cursor.fetchall():
                    # Check if there are related documents
                    cursor.execute("""
                        SELECT COUNT(*) as doc_count
                        FROM document_metadata
                        WHERE project_id = ?
                        AND document_date >= date('now', '-30 days')
                    """, (row['project_id'],))
                    
                    doc_count = cursor.fetchone()['doc_count']
                    
                    if doc_count == 0:
                        gap = AuditGapSchema(
                            audit_id=f"AUDIT-DEADLINE-{datetime.now().strftime('%Y%m%d%H%M%S')}-{row['event_id']}",
                            severity=AuditSeverity.HIGH,
                            gap_type="document_missing",
                            project_id=row['project_id'],
                            affected_schemas=["DeadlineRegistrySchema", "DocumentMetadataSchema"],
                            affected_entity_ids=[row['event_id']],
                            title=f"Upcoming Deadline Without Documents: {row['event_title']}",
                            description=f"Deadline {row['event_title']} is approaching ({row['target_date']}) but no recent documents found in the last 30 days.",
                            detected_by=AuditPattern.DEADLINE_DOCUMENT_GAP.value,
                            evidence_data={
                                "target_date": row['target_date'],
                                "days_until_deadline": (datetime.strptime(row['target_date'], '%Y-%m-%d') - datetime.now()).days,
                                "recent_documents": doc_count
                            },
                            expected_state="Supporting documents available for upcoming deadlines",
                            actual_state=f"No documents found in last 30 days for deadline in {(datetime.strptime(row['target_date'], '%Y-%m-%d') - datetime.now()).days} days",
                            rag_performed=False,
                            manual_action_required=True
                        )
                        gaps.append(gap)
                
        except Exception as e:
            logger.error(f"Error in deadline document audit: {e}")
        
        return gaps
    
    def _audit_nomenclature_conflicts(self) -> List[AuditGapSchema]:
        """Audit for conflicts in material nomenclature mappings."""
        gaps = []
        
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Find nomenclature mappings with low confidence
                cursor.execute("""
                    SELECT mapping_id, project_id, canonical_name, confidence_score
                    FROM nomenclature_mapping
                    WHERE confidence_score < 0.7
                """)
                
                for row in cursor.fetchall():
                    gap = AuditGapSchema(
                        audit_id=f"AUDIT-NOMENCLATURE-{datetime.now().strftime('%Y%m%d%H%M%S')}-{row['mapping_id']}",
                        severity=AuditSeverity.LOW,
                        gap_type="nomenclature_uncertainty",
                        project_id=row['project_id'],
                        affected_schemas=["NomenclatureMapping"],
                        affected_entity_ids=[row['mapping_id']],
                        title=f"Low Confidence Nomenclature: {row['canonical_name']}",
                        description=f"Nomenclature mapping for {row['canonical_name']} has low confidence score: {row['confidence_score']:.2f}. Manual verification recommended.",
                        detected_by=AuditPattern.NAMENCLATURE_CONFLICT.value,
                        evidence_data={
                            "confidence_score": float(row['confidence_score']),
                            "canonical_name": row['canonical_name']
                        },
                        expected_state="High confidence nomenclature mappings (>0.7)",
                        actual_state=f"Low confidence mapping: {row['confidence_score']:.2f}",
                        rag_performed=False,
                        manual_action_required=False
                    )
                    gaps.append(gap)
                
        except Exception as e:
            logger.error(f"Error in nomenclature conflict audit: {e}")
        
        return gaps
    
    def _audit_rag_white_spots(self) -> List[AuditGapSchema]:
        """Audit for white spots in RAG coverage."""
        gaps = []
        
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Find documents without RAG coverage
                cursor.execute("""
                    SELECT document_id, project_id, document_type, file_name
                    FROM document_metadata
                    WHERE chunk_count = 0 OR chunk_ids = '[]'
                """)
                
                for row in cursor.fetchall():
                    gap = AuditGapSchema(
                        audit_id=f"AUDIT-RAG-{datetime.now().strftime('%Y%m%d%H%M%S')}-{row['document_id']}",
                        severity=AuditSeverity.MEDIUM,
                        gap_type="rag_white_spot",
                        project_id=row['project_id'],
                        affected_schemas=["DocumentMetadataSchema"],
                        affected_entity_ids=[row['document_id']],
                        title=f"RAG White Spot: {row['file_name']}",
                        description=f"Document {row['file_name']} ({row['document_type']}) has no RAG coverage (chunk_count=0). Not available for semantic search.",
                        detected_by=AuditPattern.RAG_WHITE_SPOT.value,
                        evidence_data={
                            "document_type": row['document_type'],
                            "chunk_count": 0,
                            "rag_coverage": False
                        },
                        expected_state="All documents processed for RAG search",
                        actual_state="Document not chunked or indexed for RAG",
                        rag_performed=False,
                        manual_action_required=True
                    )
                    gaps.append(gap)
                
        except Exception as e:
            logger.error(f"Error in RAG white spot audit: {e}")
        
        return gaps
    
    def _process_detected_gap(self, gap: AuditGapSchema):
        """Process a detected audit gap."""
        try:
            # Persist gap to database
            self._persist_gap(gap)
            
            # For critical gaps, create question via Questions Gateway
            if gap.severity == AuditSeverity.CRITICAL and self.questions_gateway:
                self._create_critical_gap_question(gap)
            
            logger.info(f"Processed audit gap: {gap.audit_id} ({gap.severity.value})")
            
        except Exception as e:
            logger.error(f"Error processing gap {gap.audit_id}: {e}")
    
    def _persist_gap(self, gap: AuditGapSchema) -> bool:
        """Persist audit gap to database."""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO audit_gaps (
                        audit_id, severity, gap_type, project_id,
                        affected_schemas, affected_entity_ids, title, description,
                        detected_by, evidence_data, expected_state, actual_state,
                        rag_performed, rag_results, documents_found,
                        auto_resolution_attempted, auto_resolution_successful,
                        manual_action_required, question_gateway_id, checklist_item,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    gap.audit_id,
                    gap.severity.value,
                    gap.gap_type,
                    gap.project_id,
                    str(gap.affected_schemas),
                    str(gap.affected_entity_ids),
                    gap.title,
                    gap.description,
                    gap.detected_by,
                    str(gap.evidence_data),
                    gap.expected_state,
                    gap.actual_state,
                    gap.rag_performed,
                    str(gap.rag_results),
                    gap.documents_found,
                    gap.auto_resolution_attempted,
                    gap.auto_resolution_successful,
                    gap.manual_action_required,
                    gap.question_gateway_id,
                    gap.checklist_item,
                    gap.created_at.isoformat()
                ))
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to persist audit gap: {e}")
            return False
    
    def _create_critical_gap_question(self, gap: AuditGapSchema):
        """Create a question for critical audit gaps."""
        try:
            question_data = {
                "question_id": f"Q-CRITICAL-{gap.audit_id}",
                "question_type": f"audit_{gap.gap_type}",
                "priority": "critical",
                "project_id": gap.project_id,
                "related_schema_type": ",".join(gap.affected_schemas),
                "related_entity_id": gap.affected_entity_ids[0] if gap.affected_entity_ids else "",
                "question_markdown": f"# Critical Audit Gap Detected\n\n{gap.title}\n\n{gap.description}\n\n## Options:\n**(a)** Investigate and resolve immediately\n**(b)** Schedule for next morning review\n**(c)** Request additional information",
                "option_a": "Investigate and resolve immediately",
                "option_b": "Schedule for next morning review",
                "option_c": "Request additional information"
            }
            
            question_id = self.questions_gateway.ask_human(question_data)
            
            # Link question to gap
            gap.question_gateway_id = question_id
            self._persist_gap(gap)
            
            logger.info(f"Created critical gap question: {question_id}")
            
        except Exception as e:
            logger.error(f"Failed to create critical gap question: {e}")
    
    def get_audit_statistics(self) -> Dict[str, Any]:
        """Get audit statistics."""
        return {
            "is_running": self.is_running,
            "audits_performed": self.audits_performed,
            "gaps_detected": self.gaps_detected,
            "critical_gaps": self.critical_gaps,
            "last_audit_time": self.last_audit_time.isoformat() if self.last_audit_time else None
        }


def initialize_audit_database():
    """Initialize audit gaps table in database."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_gaps (
                    audit_id TEXT PRIMARY KEY,
                    severity TEXT NOT NULL,
                    gap_type TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    affected_schemas TEXT NOT NULL,
                    affected_entity_ids TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    detected_by TEXT NOT NULL,
                    evidence_data TEXT DEFAULT '{}',
                    expected_state TEXT NOT NULL,
                    actual_state TEXT NOT NULL,
                    rag_performed BOOLEAN DEFAULT 0,
                    rag_results TEXT DEFAULT '[]',
                    documents_found BOOLEAN DEFAULT 0,
                    auto_resolution_attempted BOOLEAN DEFAULT 0,
                    auto_resolution_successful BOOLEAN DEFAULT 0,
                    manual_action_required BOOLEAN DEFAULT 1,
                    question_gateway_id TEXT,
                    checklist_item TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    resolved_at TIMESTAMP
                )
            """)
            
            # Create indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_severity 
                ON audit_gaps(severity, created_at)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_project 
                ON audit_gaps(project_id, gap_type)
            """)
            
        logger.info("Audit gaps database initialized")
        
    except Exception as e:
        logger.error(f"Failed to initialize audit database: {e}")



if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)
    
    # Initialize database
    initialize_audit_database()
    
    # Create audit vector
    from pathlib import Path
    audit_vector = NighttimeAuditVector(Path(__file__).parent.parent.parent)
    
    # Start audit
    audit_vector.start()
    
    # Check statistics
    stats = audit_vector.get_audit_statistics()
    print(f"Audit statistics: {stats}")
    
    # Let it run briefly
    time.sleep(5)
    
    # Stop audit
    audit_vector.stop()