"""Contract Analyzer - Analyze contract text with citation tracking.

This module analyzes contract documents and extracts key information
with proper citation tracking for verification.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path
import re

from app.modules.document_parser import DocumentParserFactory

logger = logging.getLogger(__name__)


class ContractAnalyzer:
    """
    Analyze contract documents with citation tracking.
    
    Extracts key contract information and provides citations
    for verification of extracted data.
    """
    
    def __init__(self):
        """Initialize Contract Analyzer."""
        self.document_parser = DocumentParserFactory()
    
    def analyze_contract(self, file_path: str) -> Dict[str, Any]:
        """
        Analyze a contract document.
        
        Args:
            file_path: Path to contract file
            
        Returns:
            Contract analysis with citations
        """
        file_path = Path(file_path)
        if not file_path.exists():
            return {'success': False, 'error': 'File not found'}
        
        # Parse document
        try:
            parsed = self.document_parser.parse_document(str(file_path))
            text = parsed.get('text', '')
            
            if not text:
                return {'success': False, 'error': 'No text extracted'}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
        
        # Extract contract number with citation
        contract_number, cn_citation = self._extract_with_citation(
            text,
            r'(?:договор|контракт|contract)[№\s-]*(\d+[/\-A-Za-zА-Яа-яЁё\d]*)'
        )
        
        # Extract contract date with citation
        contract_date, cd_citation = self._extract_with_citation(
            text,
            r'\d{1,2}\.\d{1,2}\.\d{4}'
        )
        
        # Extract contract amount with citation
        contract_amount, ca_citation = self._extract_with_citation(
            text,
            r'(\d[\d\s,.]*[.,]\d+)\s*(?:руб|р\.|₽)'
        )
        
        # Extract customer with citation
        customer, cust_citation = self._extract_with_citation(
            text,
            r'(?:заказчик|customer|client)[:\s]+([А-Яа-яA-Za-z\s&]+)'
        )
        
        # Extract contractor with citation
        contractor, cont_citation = self._extract_with_citation(
            text,
            r'(?:подрядчик|contractor|исполнитель)[:\s]+([А-Яа-яA-Za-z\s&]+)'
        )
        
        analysis = {
            'success': True,
            'file_path': str(file_path),
            'file_name': file_path.name,
            'contract_number': contract_number,
            'contract_date': contract_date,
            'contract_amount': contract_amount,
            'customer': customer,
            'contractor': contractor,
            'citations': {
                'contract_number': cn_citation,
                'contract_date': cd_citation,
                'contract_amount': ca_citation,
                'customer': cust_citation,
                'contractor': cont_citation
            },
            'analyzed_at': datetime.now().isoformat()
        }
        
        logger.info(f"Analyzed contract {file_path.name}")
        return analysis
    
    def _extract_with_citation(self, text: str, pattern: str) -> tuple:
        """
        Extract value with surrounding citation text.
        
        Args:
            text: Document text
            pattern: Regex pattern
            
        Returns:
            Tuple of (value, citation_text)
        """
        match = re.search(pattern, text, re.IGNORECASE)
        
        if not match:
            return None, None
        
        value = match.group(1) if match.groups() else match.group(0)
        
        # Extract surrounding text as citation (50 chars before and after)
        start = max(0, match.start() - 50)
        end = min(len(text), match.end() + 50)
        citation = text[start:end].strip()
        
        return value, citation
    
    def extract_key_clauses(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract key contract clauses.
        
        Args:
            text: Contract text
            
        Returns:
            List of key clauses with citations
        """
        clauses = []
        
        # Key clause patterns
        clause_patterns = {
            'payment_terms': [
                r'(?:условия оплаты|payment terms)[:\s\n]+([^.]+)\.',
                r'(?:срок оплаты|payment deadline)[:\s\n]+([^.]+)\.'
            ],
            'delivery_terms': [
                r'(?:условия поставки|delivery terms)[:\s\n]+([^.]+)\.',
                r'(?:срок поставки|delivery deadline)[:\s\n]+([^.]+)\.'
            ],
            'liability': [
                r'(?:ответственность|liability)[:\s\n]+([^.]+)\.',
                r'(?:пени|penalty)[:\s\n]+([^.]+)\.'
            ],
            'termination': [
                r'(?:расторжение|termination)[:\s\n]+([^.]+)\.',
                r'(?:прекращение|cancellation)[:\s\n]+([^.]+)\.'
            ]
        }
        
        for clause_type, patterns in clause_patterns.items():
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    clause_text = match.group(1) if match.groups() else match.group(0)
                    
                    # Extract citation
                    start = max(0, match.start() - 30)
                    end = min(len(text), match.end() + 30)
                    citation = text[start:end].strip()
                    
                    clauses.append({
                        'clause_type': clause_type,
                        'text': clause_text,
                        'citation': citation
                    })
                    break  # Only take first match per clause type
        
        return clauses
    
    def generate_contract_summary(self, analysis: Dict[str, Any]) -> str:
        """
        Generate human-readable contract summary.
        
        Args:
            analysis: Contract analysis result
            
        Returns:
            Text summary
        """
        if not analysis['success']:
            return f"Analysis failed: {analysis.get('error', 'Unknown error')}"
        
        summary_parts = [
            f"Договор: {analysis['contract_number'] or 'N/A'}",
            f"Дата: {analysis['contract_date'] or 'N/A'}",
            f"Сумма: {analysis['contract_amount'] or 'N/A'}",
            f"Заказчик: {analysis['customer'] or 'N/A'}",
            f"Подрядчик: {analysis['contractor'] or 'N/A'}"
        ]
        
        return "\n".join(summary_parts)


if __name__ == "__main__":
    # Test Contract Analyzer
    logging.basicConfig(level=logging.INFO)
    
    analyzer = ContractAnalyzer()
    
    # Test with sample text
    test_text = """
    Договор №123-456 от 15.03.2024
    Сумма: 1,500,000.50 руб.
    Заказчик: ООО СтройСервис
    Подрядчик: ООО МонтажПро
    """
    
    # Would need actual file for full analysis
    print("Contract Analyzer initialized")
