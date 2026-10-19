"""Document Information Extractor - Extract structured data from construction documents.

This module extracts key information from construction documents:
- Financial data (amounts, budgets, payments)
- Dates and deadlines
- Materials and equipment
- Contract terms and conditions
"""

import logging
import re
from typing import Dict, List, Any, Optional
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from app.modules.document_parser import DocumentParserFactory

logger = logging.getLogger(__name__)


class DocumentInfoExtractor:
    """
    Extract structured information from construction documents.
    
    Uses pattern matching and NLP to extract:
    - Financial amounts
    - Dates and deadlines
    - Materials and quantities
    - Contract numbers and references
    """
    
    # Patterns for financial amounts
    AMOUNT_PATTERNS = [
        r'(\d+[.,]\d+)\s*(?:руб|р\.|₽)',  # "1000.50 руб"
        r'(\d+[.,]\d+)\s*(?:USD|\$)',  # "1000.50 USD"
        r'(\d+[.,]\d+)\s*(?:EUR|€)',  # "1000.50 EUR"
        r'сумма[:\s]+(\d+[.,]\d+)',  # "сумма: 1000.50"
        r'итого[:\s]+(\d+[.,]\d+)',  # "итого: 1000.50"
        r'всего[:\s]+(\d+[.,]\d+)',  # "всего: 1000.50"
    ]
    
    # Patterns for dates
    DATE_PATTERNS = [
        r'(\d{1,2})\.(\d{1,2})\.(\d{4})',  # DD.MM.YYYY
        r'(\d{4})-(\d{1,2})-(\d{1,2})',  # YYYY-MM-DD
        r'(\d{1,2})\s+января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря\s+(\d{4})',
    ]
    
    # Patterns for materials
    MATERIAL_PATTERNS = [
        r'кабель\s+([А-Яа-я\w\d-]+)',
        r'труба\s+([А-Яа-я\w\d-]+)',
        r'провод\s+([А-Яа-я\w\d-]+)',
        r'(\d+)\s*(?:м|шт|кг|т)\s+(?:кабель|труба|провод)',
    ]
    
    def __init__(self):
        """Initialize Document Info Extractor."""
        self.document_parser = DocumentParserFactory()
    
    def extract_financials(self, text: str) -> Dict[str, Any]:
        """
        Extract financial information from document text.
        
        Args:
            text: Document text
            
        Returns:
            Dictionary with financial data
        """
        financials = {
            'amounts': [],
            'total_amount': None,
            'currency': 'RUB',
            'vat_included': False
        }
        
        # Extract amounts
        for pattern in self.AMOUNT_PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                amount_str = match.group(1).replace(',', '.')
                try:
                    amount = float(amount_str)
                    financials['amounts'].append(amount)
                except ValueError:
                    continue
        
        # Determine total (last amount or max)
        if financials['amounts']:
            financials['total_amount'] = max(financials['amounts'])
        
        # Detect VAT
        if 'ндс' in text.lower() or 'vat' in text.lower():
            financials['vat_included'] = True
        
        return financials
    
    def extract_dates(self, text: str) -> Dict[str, Any]:
        """
        Extract dates and deadlines from document text.
        
        Args:
            text: Document text
            
        Returns:
            Dictionary with date data
        """
        dates = {
            'dates_found': [],
            'deadlines': [],
            'contract_date': None,
            'completion_date': None
        }
        
        # Extract dates
        for pattern in self.DATE_PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    if pattern.startswith(r'(\d{1,2})\.'):
                        # DD.MM.YYYY format
                        day, month, year = match.groups()
                        date_obj = datetime(int(year), int(month), int(day))
                    elif pattern.startswith(r'(\d{4})'):
                        # YYYY-MM-DD format
                        year, month, day = match.groups()
                        date_obj = datetime(int(year), int(month), int(day))
                    else:
                        continue
                    
                    dates['dates_found'].append(date_obj.isoformat())
                except (ValueError, IndexError):
                    continue
        
        # Detect contract date
        for date_str in dates['dates_found']:
            context_match = re.search(
                rf'(?:дата договора|дата контракта|contract date)[:\s]+{date_str[:10]}',
                text,
                re.IGNORECASE
            )
            if context_match:
                dates['contract_date'] = date_str
                break
        
        # Detect completion date
        for date_str in dates['dates_found']:
            context_match = re.search(
                rf'(?:срок выполнения|дата завершения|completion date|deadline)[:\s]+{date_str[:10]}',
                text,
                re.IGNORECASE
            )
            if context_match:
                dates['completion_date'] = date_str
                dates['deadlines'].append(date_str)
                break
        
        return dates
    
    def extract_materials(self, text: str) -> Dict[str, Any]:
        """
        Extract materials and quantities from document text.
        
        Args:
            text: Document text
            
        Returns:
            Dictionary with material data
        """
        materials = {
            'items': [],
            'total_items': 0
        }
        
        # Extract materials
        for pattern in self.MATERIAL_PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                material_name = match.group(1) if match.groups() else match.group(0)
                
                # Try to extract quantity
                quantity_match = re.search(r'(\d+)\s*(?:шт|м|кг|т)', match.group(0))
                quantity = int(quantity_match.group(1)) if quantity_match else 1
                
                materials['items'].append({
                    'name': material_name,
                    'quantity': quantity
                })
        
        materials['total_items'] = len(materials['items'])
        
        return materials
    
    def extract_contract_info(self, text: str) -> Dict[str, Any]:
        """
        Extract contract information from document text.
        
        Args:
            text: Document text
            
        Returns:
            Dictionary with contract data
        """
        contract = {
            'contract_number': None,
            'customer': None,
            'contractor': None,
            'object_name': None
        }
        
        # Extract contract number
        contract_match = re.search(
            r'(?:договор|контракт|contract)[№\s-]*(\d+[/\-A-Za-z\d]*)',
            text,
            re.IGNORECASE
        )
        if contract_match:
            contract['contract_number'] = contract_match.group(1)
        
        # Extract customer
        customer_match = re.search(
            r'(?:заказчик|customer|client)[:\s]+([А-Яа-яA-Za-z\s&]+)',
            text,
            re.IGNORECASE
        )
        if customer_match:
            contract['customer'] = customer_match.group(1).strip()
        
        # Extract contractor
        contractor_match = re.search(
            r'(?:подрядчик|contractor|исполнитель)[:\s]+([А-Яа-яA-Za-z\s&]+)',
            text,
            re.IGNORECASE
        )
        if contractor_match:
            contract['contractor'] = contractor_match.group(1).strip()
        
        # Extract object name
        object_match = re.search(
            r'(?:объект|object|строительный объект)[:\s]+([А-Яа-яA-Za-z\d\s\-]+)',
            text,
            re.IGNORECASE
        )
        if object_match:
            contract['object_name'] = object_match.group(1).strip()
        
        return contract
    
    def extract_all(self, file_path: str) -> Dict[str, Any]:
        """
        Extract all information from a document.
        
        Args:
            file_path: Path to document file
            
        Returns:
            Complete extracted information
        """
        file_path = Path(file_path)
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return {'success': False, 'error': 'File not found'}
        
        # Parse document
        try:
            parsed = self.document_parser.parse_document(str(file_path))
            text = parsed.get('text', '')
            
            if not text:
                logger.warning(f"No text extracted from {file_path}")
                return {'success': False, 'error': 'No text extracted'}
            
        except Exception as e:
            logger.error(f"Error parsing document {file_path}: {e}")
            return {'success': False, 'error': str(e)}
        
        # Extract all information
        result = {
            'success': True,
            'file_path': str(file_path),
            'file_name': file_path.name,
            'raw_text': text,
            'financials': self.extract_financials(text),
            'dates': self.extract_dates(text),
            'materials': self.extract_materials(text),
            'contract': self.extract_contract_info(text),
            'extracted_at': datetime.now().isoformat()
        }
        
        logger.info(f"Extracted information from {file_path}")
        return result
    
    def extract_from_directory(self, directory: str) -> Dict[str, Any]:
        """
        Extract information from all documents in a directory.
        
        Args:
            directory: Directory path
            
        Returns:
            Summary of extraction results
        """
        directory = Path(directory)
        if not directory.exists():
            logger.error(f"Directory not found: {directory}")
            return {'success': False, 'error': 'Directory not found'}
        
        results = {
            'success': True,
            'total_files': 0,
            'successful': 0,
            'failed': 0,
            'extracted_data': []
        }
        
        # Process PDF, DOCX, DOC files
        for pattern in ['*.pdf', '*.docx', '*.doc']:
            for file_path in directory.glob(pattern):
                results['total_files'] += 1
                
                extraction = self.extract_all(str(file_path))
                
                if extraction['success']:
                    results['successful'] += 1
                    results['extracted_data'].append(extraction)
                else:
                    results['failed'] += 1
        
        logger.info(f"Extraction complete: {results['successful']}/{results['total_files']} successful")
        return results


if __name__ == "__main__":
    # Test document info extractor
    logging.basicConfig(level=logging.INFO)
    
    extractor = DocumentInfoExtractor()
    
    # Test financial extraction
    test_text = """
    Договор №123-456 от 15.03.2024
    Сумма: 1,500,000.50 руб.
    Срок выполнения: 30.09.2024
    Кабель ВВГнг 3x2.5 - 500 м
    """
    
    financials = extractor.extract_financials(test_text)
    print("Financials:", financials)
    
    dates = extractor.extract_dates(test_text)
    print("Dates:", dates)
    
    materials = extractor.extract_materials(test_text)
    print("Materials:", materials)
    
    contract = extractor.extract_contract_info(test_text)
    print("Contract:", contract)
