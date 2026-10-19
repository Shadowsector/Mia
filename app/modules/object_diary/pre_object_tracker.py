"""Pre-Object Tracker - Track Commercial Proposal (КП) to Contract conversion.

This module tracks the lifecycle from commercial proposals to contracts,
ensuring continuity and proper versioning.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

from app.modules.storage.database import get_db_connection

logger = logging.getLogger(__name__)


class PreObjectTracker:
    """
    Track КП (Commercial Proposal) to Contract conversion.
    
    Maintains the relationship between proposals and their resulting contracts,
    tracking conversion status and preserving proposal history.
    """
    
    def __init__(self):
        """Initialize Pre-Object Tracker."""
        self._ensure_tables()
    
    def _ensure_tables(self):
        """Create necessary database tables."""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Proposal tracking table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS proposal_tracking (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        proposal_id TEXT NOT NULL,
                        proposal_date DATE,
                        proposal_amount REAL,
                        proposal_name TEXT,
                        status TEXT DEFAULT 'pending',
                        converted_to_contract_id TEXT,
                        contract_id TEXT,
                        conversion_date DATE,
                        conversion_notes TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                logger.info("Pre-Object Tracker tables initialized")
                
        except Exception as e:
            logger.error(f"Error creating Pre-Object Tracker tables: {e}")
    
    def register_proposal(
        self,
        proposal_id: str,
        proposal_date: str,
        proposal_amount: float,
        proposal_name: str
    ) -> int:
        """
        Register a new commercial proposal.
        
        Args:
            proposal_id: Proposal identifier
            proposal_date: Proposal date
            proposal_amount: Proposal amount
            proposal_name: Proposal name
            
        Returns:
            Tracking ID
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO proposal_tracking (
                        proposal_id, proposal_date, proposal_amount, proposal_name, status
                    ) VALUES (?, ?, ?, ?, 'pending')
                """, (proposal_id, proposal_date, proposal_amount, proposal_name))
                
                tracking_id = cursor.lastrowid
                logger.info(f"Registered proposal {proposal_id}")
                return tracking_id
                
        except Exception as e:
            logger.error(f"Error registering proposal: {e}")
            return -1
    
    def convert_to_contract(
        self,
        proposal_id: str,
        contract_id: str,
        conversion_date: str,
        notes: Optional[str] = None
    ) -> bool:
        """
        Mark a proposal as converted to contract.
        
        Args:
            proposal_id: Proposal ID
            contract_id: Contract ID
            conversion_date: Conversion date
            notes: Conversion notes
            
        Returns:
            True if successful
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE proposal_tracking
                    SET status = 'converted',
                        converted_to_contract_id = ?,
                        contract_id = ?,
                        conversion_date = ?,
                        conversion_notes = ?
                    WHERE proposal_id = ?
                """, (contract_id, contract_id, conversion_date, notes, proposal_id))
                
                logger.info(f"Converted proposal {proposal_id} to contract {contract_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error converting proposal to contract: {e}")
            return False
    
    def get_proposal_status(self, proposal_id: str) -> Optional[Dict[str, Any]]:
        """
        Get status of a proposal.
        
        Args:
            proposal_id: Proposal ID
            
        Returns:
            Proposal status dict or None
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM proposal_tracking
                    WHERE proposal_id = ?
                """, (proposal_id,))
                
                row = cursor.fetchone()
                if row:
                    return {
                        'id': row['id'],
                        'proposal_id': row['proposal_id'],
                        'proposal_date': row['proposal_date'],
                        'proposal_amount': row['proposal_amount'],
                        'proposal_name': row['proposal_name'],
                        'status': row['status'],
                        'converted_to_contract_id': row['converted_to_contract_id'],
                        'contract_id': row['contract_id'],
                        'conversion_date': row['conversion_date'],
                        'conversion_notes': row['conversion_notes'],
                        'created_at': row['created_at']
                    }
                
                return None
                
        except Exception as e:
            logger.error(f"Error getting proposal status: {e}")
            return None
    
    def get_pending_proposals(self) -> List[Dict[str, Any]]:
        """
        Get all pending proposals.
        
        Returns:
            List of pending proposals
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM proposal_tracking
                    WHERE status = 'pending'
                    ORDER BY proposal_date DESC
                """)
                
                proposals = []
                for row in cursor.fetchall():
                    proposals.append({
                        'id': row['id'],
                        'proposal_id': row['proposal_id'],
                        'proposal_date': row['proposal_date'],
                        'proposal_amount': row['proposal_amount'],
                        'proposal_name': row['proposal_name'],
                        'status': row['status']
                    })
                
                return proposals
                
        except Exception as e:
            logger.error(f"Error getting pending proposals: {e}")
            return []
    
    def get_conversion_history(self) -> List[Dict[str, Any]]:
        """
        Get history of proposal to contract conversions.
        
        Returns:
            List of conversions
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM proposal_tracking
                    WHERE status = 'converted'
                    ORDER BY conversion_date DESC
                """)
                
                conversions = []
                for row in cursor.fetchall():
                    conversions.append({
                        'proposal_id': row['proposal_id'],
                        'proposal_amount': row['proposal_amount'],
                        'contract_id': row['contract_id'],
                        'conversion_date': row['conversion_date'],
                        'conversion_notes': row['conversion_notes']
                    })
                
                return conversions
                
        except Exception as e:
            logger.error(f"Error getting conversion history: {e}")
            return []


if __name__ == "__main__":
    # Test Pre-Object Tracker
    logging.basicConfig(level=logging.INFO)
    
    tracker = PreObjectTracker()
    
    # Register test proposal
    tracking_id = tracker.register_proposal(
        proposal_id="KP-2024-001",
        proposal_date="2024-03-01",
        proposal_amount=1500000.0,
        proposal_name="КП на строительство ККС"
    )
    
    print(f"Registered proposal with tracking ID: {tracking_id}")
    
    # Get pending proposals
    pending = tracker.get_pending_proposals()
    print(f"Pending proposals: {len(pending)}")
