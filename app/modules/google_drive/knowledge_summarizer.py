"""Knowledge Summarizer - Generate summaries for construction objects.

This module aggregates information from contracts, documents, and diary entries
to generate comprehensive knowledge summaries for each construction object.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path

from app.modules.storage.database import get_db_connection
from app.modules.rag.document_ingestor import DocumentIngestor
from app.modules.google_drive.contract_linker import ContractLinker

logger = logging.getLogger(__name__)


class KnowledgeSummarizer:
    """
    Generate knowledge summaries for construction objects.
    
    Aggregates information from multiple sources:
    - Object diary entries
    - Linked contracts
    - Ingested documents
    - Financial data
    """
    
    def __init__(self):
        """Initialize Knowledge Summarizer."""
        self.document_ingestor = DocumentIngestor()
        self.contract_linker = ContractLinker()
    
    def generate_object_summary(self, object_id: str) -> Dict[str, Any]:
        """
        Generate comprehensive summary for a construction object.
        
        Args:
            object_id: Object ID
            
        Returns:
            Object summary with all available information
        """
        summary = {
            'object_id': object_id,
            'generated_at': datetime.now().isoformat(),
            'basic_info': self._get_basic_info(object_id),
            'contracts': self._get_contracts(object_id),
            'documents': self._get_documents(object_id),
            'financials': self._get_financials(object_id),
            'timeline': self._get_timeline(object_id),
            'key_events': self._get_key_events(object_id)
        }
        
        return summary
    
    def _get_basic_info(self, object_id: str) -> Dict[str, Any]:
        """Get basic object information from database."""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT object_id, object_name, customer, customer_company,
                           contract_date, contract_amount, contract_number,
                           has_proposal, proposal_date, proposal_amount,
                           converted_to_contract
                    FROM objects WHERE object_id = ?
                """, (object_id,))
                
                row = cursor.fetchone()
                if row:
                    return {
                        'object_name': row['object_name'],
                        'customer': row['customer'],
                        'customer_company': row['customer_company'],
                        'contract_date': row['contract_date'],
                        'contract_amount': float(row['contract_amount']) if row['contract_amount'] else 0,
                        'contract_number': row['contract_number'],
                        'has_proposal': bool(row['has_proposal']),
                        'proposal_date': row['proposal_date'],
                        'proposal_amount': float(row['proposal_amount']) if row['proposal_amount'] else 0,
                        'converted_to_contract': bool(row['converted_to_contract'])
                    }
        except Exception as e:
            logger.error(f"Error getting basic info for {object_id}: {e}")
        
        return {}
    
    def _get_contracts(self, object_id: str) -> List[Dict[str, Any]]:
        """Get linked contracts for the object."""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT contract_id, contract_name, confidence, linked_at, verified_by
                    FROM contract_links WHERE object_id = ?
                    ORDER BY linked_at DESC
                """, (object_id,))
                
                contracts = []
                for row in cursor.fetchall():
                    contracts.append({
                        'contract_id': row['contract_id'],
                        'contract_name': row['contract_name'],
                        'confidence': row['confidence'],
                        'linked_at': row['linked_at'],
                        'verified_by': row['verified_by']
                    })
                
                return contracts
        except Exception as e:
            logger.error(f"Error getting contracts for {object_id}: {e}")
        
        return []
    
    def _get_documents(self, object_id: str) -> List[Dict[str, Any]]:
        """Get ingested documents for the object from RAG."""
        try:
            # Query ChromaDB for documents with this object_id
            results = self.document_ingestor.search_similar_documents(
                query="",  # Empty query to get all
                n_results=100,
                object_id=object_id
            )
            
            # Group by source file
            documents = {}
            for result in results:
                metadata = result.get('metadata', {})
                source_file = metadata.get('source_file', 'unknown')
                
                if source_file not in documents:
                    documents[source_file] = {
                        'file_name': metadata.get('file_name', source_file),
                        'document_type': metadata.get('document_type', 'unknown'),
                        'chunk_count': metadata.get('chunk_total', 0),
                        'ingested_at': metadata.get('ingested_at', 'unknown')
                    }
            
            return list(documents.values())
            
        except Exception as e:
            logger.error(f"Error getting documents for {object_id}: {e}")
        
        return []
    
    def _get_financials(self, object_id: str) -> Dict[str, Any]:
        """Get financial data for the object."""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Get budget info
                cursor.execute("""
                    SELECT contract_amount, proposal_amount
                    FROM objects WHERE object_id = ?
                """, (object_id,))
                
                row = cursor.fetchone()
                if row:
                    contract_amount = float(row['contract_amount']) if row['contract_amount'] else 0
                    proposal_amount = float(row['proposal_amount']) if row['proposal_amount'] else 0
                else:
                    contract_amount = 0
                    proposal_amount = 0
                
                # Get invoice data (if available)
                cursor.execute("""
                    SELECT COUNT(*) as count, SUM(amount) as total
                    FROM invoices WHERE object_id = ?
                """, (object_id,))
                
                invoice_row = cursor.fetchone()
                invoice_count = invoice_row['count'] if invoice_row else 0
                invoice_total = float(invoice_row['total']) if invoice_row and invoice_row['total'] else 0
                
                return {
                    'contract_amount': contract_amount,
                    'proposal_amount': proposal_amount,
                    'invoice_count': invoice_count,
                    'invoice_total': invoice_total,
                    'remaining_budget': contract_amount - invoice_total if contract_amount > 0 else 0
                }
                
        except Exception as e:
            logger.error(f"Error getting financials for {object_id}: {e}")
        
        return {}
    
    def _get_timeline(self, object_id: str) -> List[Dict[str, Any]]:
        """Get timeline events for the object."""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT event_date, event_type, description, metadata
                    FROM object_events
                    WHERE object_id = ?
                    ORDER BY event_date DESC
                    LIMIT 20
                """, (object_id,))
                
                events = []
                for row in cursor.fetchall():
                    events.append({
                        'event_date': row['event_date'],
                        'event_type': row['event_type'],
                        'description': row['description'],
                        'metadata': row['metadata']
                    })
                
                return events
        except Exception as e:
            logger.error(f"Error getting timeline for {object_id}: {e}")
        
        return []
    
    def _get_key_events(self, object_id: str) -> List[str]:
        """Extract key events from timeline."""
        timeline = self._get_timeline(object_id)
        
        key_events = []
        for event in timeline:
            event_type = event.get('event_type', '')
            description = event.get('description', '')
            
            # Focus on important event types
            if event_type in ['contract_signed', 'work_started', 'milestone', 'completion']:
                key_events.append(f"{event['event_date']}: {description}")
        
        return key_events
    
    def generate_text_summary(self, object_id: str) -> str:
        """
        Generate human-readable text summary.
        
        Args:
            object_id: Object ID
            
        Returns:
            Text summary
        """
        summary = self.generate_object_summary(object_id)
        
        # Build text summary
        text_parts = []
        
        # Basic info
        basic = summary.get('basic_info', {})
        text_parts.append(f"Объект: {basic.get('object_name', 'N/A')}")
        text_parts.append(f"Заказчик: {basic.get('customer', 'N/A')}")
        text_parts.append(f"Сумма контракта: {basic.get('contract_amount', 0):,.2f} руб.")
        
        # Contracts
        contracts = summary.get('contracts', [])
        if contracts:
            text_parts.append(f"\nСвязанные контракты: {len(contracts)}")
            for contract in contracts[:5]:  # Show first 5
                text_parts.append(f"  - {contract['contract_name']}")
        
        # Financials
        financials = summary.get('financials', {})
        if financials:
            text_parts.append(f"\nФинансы:")
            text_parts.append(f"  Оплачено: {financials.get('invoice_total', 0):,.2f} руб.")
            text_parts.append(f"  Остаток: {financials.get('remaining_budget', 0):,.2f} руб.")
        
        # Key events
        key_events = summary.get('key_events', [])
        if key_events:
            text_parts.append(f"\nКлючевые события:")
            for event in key_events[:5]:
                text_parts.append(f"  - {event}")
        
        return "\n".join(text_parts)
    
    def generate_all_summaries(self) -> Dict[str, Dict[str, Any]]:
        """
        Generate summaries for all objects.
        
        Returns:
            Dictionary mapping object_id to summary
        """
        summaries = {}
        
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT object_id FROM objects")
                
                for row in cursor.fetchall():
                    object_id = row['object_id']
                    summary = self.generate_object_summary(object_id)
                    summaries[object_id] = summary
                    
                    logger.info(f"Generated summary for {object_id}")
                    
        except Exception as e:
            logger.error(f"Error generating all summaries: {e}")
        
        return summaries


if __name__ == "__main__":
    # Test knowledge summarizer
    logging.basicConfig(level=logging.INFO)
    
    summarizer = KnowledgeSummarizer()
    
    # Test with a specific object (would need actual data)
    # summary = summarizer.generate_object_summary("TEST-001")
    # print(summary)
    
    # Test text summary
    # text_summary = summarizer.generate_text_summary("TEST-001")
    # print(text_summary)
