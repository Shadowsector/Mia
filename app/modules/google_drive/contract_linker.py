"""Contract Linker - Link contracts from Google Drive to construction objects.

This module automatically links contract documents from the "Договоры" folder
to construction objects based on name matching and pattern recognition.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import re

from app.modules.storage.database import get_db_connection
from app.modules.google_drive.scanner import GoogleDriveScanner

logger = logging.getLogger(__name__)


class ContractLinker:
    """
    Links contract documents to construction objects.
    
    Uses pattern matching on contract filenames to find corresponding objects.
    """
    
    # Patterns for extracting object IDs/names from contract filenames
    CONTRACT_PATTERNS = [
        r'объект[_\s-]*(\d+)',  # "объект 123" or "объект_123"
        r'OBJ[_\s-]*(\d+)',  # "OBJ 123" or "OBJ-123"
        r'Сектор[_\s-]*(\d+)',  # "Сектор 7"
        r'Участок[_\s-]*(\d+)',  # "Участок 5"
        r'(\d{4,6})[_\s-]*договор',  # "12345 договор"
    ]
    
    def __init__(self, scanner: Optional[GoogleDriveScanner] = None):
        """
        Initialize Contract Linker.
        
        Args:
            scanner: GoogleDriveScanner instance (optional for testing)
        """
        self.scanner = scanner
        self.objects_cache: Dict[str, Dict[str, Any]] = {}
        self._load_objects()
    
    def _load_objects(self):
        """Load all construction objects from database."""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, object_id, object_name, customer FROM objects")
                for row in cursor.fetchall():
                    self.objects_cache[row['object_id']] = {
                        'id': row['id'],
                        'object_id': row['object_id'],
                        'object_name': row['object_name'],
                        'customer': row['customer']
                    }
            logger.info(f"Loaded {len(self.objects_cache)} objects from database")
        except Exception as e:
            logger.error(f"Error loading objects: {e}")
    
    def extract_object_reference(self, filename: str) -> Optional[str]:
        """
        Extract object reference from contract filename.
        
        Args:
            filename: Contract filename
            
        Returns:
            Object ID or None if not found
        """
        filename_lower = filename.lower()
        
        # Try each pattern
        for pattern in self.CONTRACT_PATTERNS:
            match = re.search(pattern, filename_lower, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    def find_best_match(self, filename: str) -> Optional[Dict[str, Any]]:
        """
        Find the best matching object for a contract filename.
        
        Args:
            filename: Contract filename
            
        Returns:
            Object dict or None if no match found
        """
        # Extract object reference from filename
        object_ref = self.extract_object_reference(filename)
        if object_ref:
            # Direct ID match
            if object_ref in self.objects_cache:
                return self.objects_cache[object_ref]
            
            # Partial name match
            for obj_id, obj_data in self.objects_cache.items():
                if object_ref in obj_data['object_name'].lower():
                    return obj_data
        
        # Try fuzzy matching on object names
        filename_words = set(re.findall(r'\w+', filename.lower()))
        best_match = None
        best_score = 0
        
        for obj_id, obj_data in self.objects_cache.items():
            obj_words = set(re.findall(r'\w+', obj_data['object_name'].lower()))
            
            # Calculate intersection score
            intersection = filename_words & obj_words
            score = len(intersection)
            
            if score > best_score and score >= 2:  # At least 2 matching words
                best_score = score
                best_match = obj_data
        
        return best_match
    
    def link_contracts(self, contracts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Link contracts to objects.
        
        Args:
            contracts: List of contract documents from Google Drive
            
        Returns:
            Summary of linking results
        """
        results = {
            'total_contracts': len(contracts),
            'linked': 0,
            'unlinked': 0,
            'links': []
        }
        
        for contract in contracts:
            filename = contract.get('name', '')
            file_id = contract.get('id', '')
            
            # Find matching object
            match = self.find_best_match(filename)
            
            if match:
                # Save link to database
                self._save_contract_link(
                    contract_id=file_id,
                    contract_name=filename,
                    object_id=match['object_id'],
                    confidence='high' if self.extract_object_reference(filename) else 'medium'
                )
                
                results['linked'] += 1
                results['links'].append({
                    'contract': filename,
                    'object': match['object_name'],
                    'object_id': match['object_id']
                })
                logger.info(f"Linked contract '{filename}' to object '{match['object_name']}'")
            else:
                results['unlinked'] += 1
                logger.warning(f"Could not link contract '{filename}' to any object")
        
        return results
    
    def _save_contract_link(self, contract_id: str, contract_name: str, 
                           object_id: str, confidence: str):
        """Save contract-object link to database."""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Check if link already exists
                cursor.execute("""
                    SELECT id FROM contract_links 
                    WHERE contract_id = ? AND object_id = ?
                """, (contract_id, object_id))
                
                if cursor.fetchone():
                    logger.debug(f"Link already exists: {contract_id} -> {object_id}")
                    return
                
                # Insert new link
                cursor.execute("""
                    INSERT INTO contract_links (
                        contract_id, contract_name, object_id, 
                        confidence, linked_at
                    ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (contract_id, contract_name, object_id, confidence))
                
                logger.info(f"Saved contract link: {contract_id} -> {object_id}")
                
        except Exception as e:
            logger.error(f"Error saving contract link: {e}")
    
    def get_unlinked_contracts(self) -> List[Dict[str, Any]]:
        """
        Get contracts that couldn't be automatically linked.
        
        Returns:
            List of unlinked contracts
        """
        # This would require reading from Google Drive or database
        # For now, return empty list
        return []


def create_contract_links_table():
    """Create contract_links table if it doesn't exist."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS contract_links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    contract_id TEXT NOT NULL,
                    contract_name TEXT NOT NULL,
                    object_id TEXT NOT NULL,
                    confidence TEXT DEFAULT 'medium',
                    linked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    verified_by TEXT,
                    FOREIGN KEY (object_id) REFERENCES objects(object_id)
                )
            """)
            
            # Create index for quick lookups
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_contract_links_object 
                ON contract_links(object_id)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_contract_links_contract 
                ON contract_links(contract_id)
            """)
            
            logger.info("Contract links table created successfully")
            
    except Exception as e:
        logger.error(f"Error creating contract_links table: {e}")


if __name__ == "__main__":
    # Test contract linker
    logging.basicConfig(level=logging.INFO)
    
    # Create table
    create_contract_links_table()
    
    # Test linker
    linker = ContractLinker()
    
    # Test patterns
    test_filenames = [
        "Договор объект 123.docx",
        "OBJ-456 договор.pdf",
        "Сектор 7 строительные работы.doc",
        "Участок 5 ККС.pdf",
        "12345 договор на строительство.docx"
    ]
    
    for filename in test_filenames:
        match = linker.find_best_match(filename)
        if match:
            print(f"'{filename}' -> {match['object_name']} ({match['object_id']})")
        else:
            print(f"'{filename}' -> NO MATCH")
