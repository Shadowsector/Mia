"""Audit Logger - Tracking system changes for reproducibility and compliance.

This module provides centralized audit logging for all system operations,
tracking origin, approvals, and maintaining traceability.
"""

import logging
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime
from pathlib import Path

from app.core.schemas import AuditLogSchema

logger = logging.getLogger(__name__)


class AuditLogger:
    """
    Centralized audit logger for system operations.
    
    Tracks all changes to ensure reproducibility, traceability,
    and compliance with G8 principles.
    """
    
    def __init__(self, log_file: str = "C:/mia/audit.log"):
        """
        Initialize Audit Logger.
        
        Args:
            log_file: Path to audit log file
        """
        self.log_file = Path(log_file)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # In-memory trace cache for idempotency
        self._trace_cache: Dict[str, datetime] = {}
        
        logger.info(f"AuditLogger initialized with log_file={log_file}")
    
    def _generate_trace_id(self) -> str:
        """Generate unique trace ID for operation chain."""
        return f"TRACE-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}"
    
    def _write_log(self, log_entry: AuditLogSchema):
        """Write log entry to file."""
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(log_entry.model_dump_json() + "\n")
            logger.debug(f"Audit log written: {log_entry.trace_id}")
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")
    
    def log_change(
        self,
        actor: str,
        action: str,
        entity_type: str,
        entity_id: str,
        old_value: Optional[Dict[str, Any]] = None,
        new_value: Optional[Dict[str, Any]] = None,
        origin: str = "manual",
        trace_id: Optional[str] = None
    ) -> str:
        """
        Log a change to an entity.
        
        Args:
            actor: Who performed the action
            action: Action type (create, update, delete)
            entity_type: Type of entity
            entity_id: ID of entity
            old_value: Previous value
            new_value: New value
            origin: Origin of change (manual, llm_generated, automated)
            trace_id: Trace ID for operation chain (auto-generated if None)
        
        Returns:
            Trace ID of the operation
        """
        if trace_id is None:
            trace_id = self._generate_trace_id()
        
        # Check idempotency
        if trace_id in self._trace_cache:
            logger.warning(f"Duplicate trace_id detected: {trace_id}, skipping")
            return trace_id
        
        log_entry = AuditLogSchema(
            timestamp=datetime.now(),
            actor=actor,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            old_value=old_value,
            new_value=new_value,
            origin=origin,
            trace_id=trace_id
        )
        
        self._write_log(log_entry)
        self._trace_cache[trace_id] = datetime.now()
        
        return trace_id
    
    def log_approval(
        self,
        actor: str,
        entity_type: str,
        entity_id: str,
        decision: str,
        trace_id: Optional[str] = None
    ) -> str:
        """
        Log an approval decision.
        
        Args:
            actor: Who approved
            entity_type: Type of entity
            entity_id: ID of entity
            decision: Decision (approve, reject)
            trace_id: Trace ID of related operation
        
        Returns:
            Trace ID
        """
        if trace_id is None:
            trace_id = self._generate_trace_id()
        
        log_entry = AuditLogSchema(
            timestamp=datetime.now(),
            actor=actor,
            action=decision,
            entity_type=entity_type,
            entity_id=entity_id,
            origin="manual",
            trace_id=trace_id
        )
        
        self._write_log(log_entry)
        return trace_id
    
    def get_history(self, entity_type: str, entity_id: str) -> List[AuditLogSchema]:
        """
        Get audit history for a specific entity.
        
        Args:
            entity_type: Type of entity
            entity_id: ID of entity
        
        Returns:
            List of audit log entries
        """
        history = []
        
        if not self.log_file.exists():
            return history
        
        try:
            with open(self.log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        entry_data = eval(line.strip())
                        if entry_data.get("entity_type") == entity_type and entry_data.get("entity_id") == entity_id:
                            entry = AuditLogSchema(**entry_data)
                            history.append(entry)
                    except Exception as e:
                        logger.error(f"Error parsing audit log line: {e}")
        except Exception as e:
            logger.error(f"Error reading audit log: {e}")
        
        return history
    
    def get_trace(self, trace_id: str) -> List[AuditLogSchema]:
        """
        Get all operations in a trace chain.
        
        Args:
            trace_id: Trace ID to look up
        
        Returns:
            List of audit log entries in the trace
        """
        trace_operations = []
        
        if not self.log_file.exists():
            return trace_operations
        
        try:
            with open(self.log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        entry_data = eval(line.strip())
                        if entry_data.get("trace_id") == trace_id:
                            entry = AuditLogSchema(**entry_data)
                            trace_operations.append(entry)
                    except Exception as e:
                        logger.error(f"Error parsing audit log line: {e}")
        except Exception as e:
            logger.error(f"Error reading audit log: {e}")
        
        return trace_operations


# Global audit logger instance
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get global audit logger instance."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger


if __name__ == "__main__":
    # Test Audit Logger
    logging.basicConfig(level=logging.INFO)
    
    logger = AuditLogger()
    
    # Test log change
    trace_id = logger.log_change(
        actor="test_user",
        action="create",
        entity_type="object_diary",
        entity_id="TEST-001",
        new_value={"status": "pending"},
        origin="manual"
    )
    
    print(f"Logged change with trace_id: {trace_id}")
    
    # Test get history
    history = logger.get_history("object_diary", "TEST-001")
    print(f"History entries: {len(history)}")
    
    # Test get trace
    trace = logger.get_trace(trace_id)
    print(f"Trace entries: {len(trace)}")
