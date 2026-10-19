"""Implicit Override Detection - Detect document overrides based on structure.

This module detects when uploaded documents are overrides of existing documents
(e.g., "Смета_правленная_последняя.xlsx" vs "Смета_ИТОГ.xlsx") and automatically
marks old documents as DEPRECATED.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import hashlib

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("pandas not available, override detection limited")

logger = logging.getLogger(__name__)


class OverrideDetector:
    """
    Detect document overrides based on structure and content.
    
    Compares document structures to identify when a new document
    is an override of an existing document.
    """
    
    def __init__(self):
        """Initialize Override Detector."""
        self.override_patterns = [
            r'правленная',
            r'исправленная',
            r'обновленная',
            r'итог',
            r'final',
            r'последняя',
            r'latest',
            r'v2',
            r'version_2',
            r'_new',
            r'_actual'
        ]
    
    def extract_structure_hash(self, file_path: str) -> Optional[str]:
        """
        Extract structure hash from a file.
        
        For Excel files: hash of column names and row count
        For other files: hash of file content
        
        Args:
            file_path: Path to file
            
        Returns:
            Structure hash or None
        """
        file_path = Path(file_path)
        if not file_path.exists():
            return None
        
        try:
            if file_path.suffix.lower() in ['.xlsx', '.xls']:
                if not PANDAS_AVAILABLE:
                    return None
                
                # Read Excel and extract structure
                excel_file = pd.ExcelFile(file_path)
                structure_info = []
                
                for sheet_name in excel_file.sheet_names:
                    df = pd.read_excel(file_path, sheet_name=sheet_name)
                    cols = tuple(sorted(df.columns.tolist()))
                    rows = len(df)
                    structure_info.append(f"{sheet_name}:{cols}:{rows}")
                
                # Hash structure info
                structure_str = "|".join(structure_info)
                return hashlib.md5(structure_str.encode()).hexdigest()
            
            else:
                # For other files, hash the content
                with open(file_path, 'rb') as f:
                    content = f.read()
                return hashlib.md5(content).hexdigest()
                
        except Exception as e:
            logger.error(f"Error extracting structure hash from {file_path}: {e}")
            return None
    
    def calculate_structure_similarity(self, hash1: str, hash2: str) -> float:
        """
        Calculate similarity between two structure hashes.
        
        Args:
            hash1: First hash
            hash2: Second hash
            
        Returns:
            Similarity score (0-1)
        """
        if hash1 == hash2:
            return 1.0
        
        # For MD5 hashes, we can't calculate partial similarity
        # So we either return 0 (different) or 1 (same)
        return 0.0
    
    def detect_override_candidate(self, file_name: str) -> bool:
        """
        Check if file name suggests it's an override.
        
        Args:
            file_name: File name
            
        Returns:
            True if file name suggests override
        """
        file_name_lower = file_name.lower()
        
        for pattern in self.override_patterns:
            if pattern in file_name_lower:
                return True
        
        return False
    
    def find_potential_overrides(
        self,
        new_file_path: str,
        existing_files: List[str],
        similarity_threshold: float = 0.9
    ) -> List[Dict[str, Any]]:
        """
        Find potential overrides of a new file among existing files.
        
        Args:
            new_file_path: Path to new file
            existing_files: List of existing file paths
            similarity_threshold: Minimum similarity to consider as override
            
        Returns:
            List of potential overrides
        """
        new_hash = self.extract_structure_hash(new_file_path)
        if not new_hash:
            return []
        
        potential_overrides = []
        
        for existing_file in existing_files:
            existing_hash = self.extract_structure_hash(existing_file)
            if not existing_hash:
                continue
            
            # For Excel files, we need more sophisticated comparison
            # For now, use exact hash match
            if new_hash == existing_hash:
                potential_overrides.append({
                    'existing_file': existing_file,
                    'new_file': new_file_path,
                    'similarity': 1.0,
                    'reason': 'exact_structure_match'
                })
        
        return potential_overrides
    
    def compare_excel_structures(self, file1: str, file2: str) -> Dict[str, Any]:
        """
        Compare two Excel files in detail.
        
        Args:
            file1: First file path
            file2: Second file path
            
        Returns:
            Comparison result
        """
        if not PANDAS_AVAILABLE:
            return {'error': 'pandas not available'}
        
        try:
            excel1 = pd.ExcelFile(file1)
            excel2 = pd.ExcelFile(file2)
            
            # Compare sheet names
            sheets1 = set(excel1.sheet_names)
            sheets2 = set(excel2.sheet_names)
            
            common_sheets = sheets1 & sheets2
            only_in_1 = sheets1 - sheets2
            only_in_2 = sheets2 - sheets1
            
            # Compare structure for common sheets
            sheet_comparisons = {}
            for sheet in common_sheets:
                df1 = pd.read_excel(file1, sheet_name=sheet)
                df2 = pd.read_excel(file2, sheet_name=sheet)
                
                cols1 = set(df1.columns.tolist())
                cols2 = set(df2.columns.tolist())
                
                common_cols = cols1 & cols2
                only_in_cols1 = cols1 - cols2
                only_in_cols2 = cols2 - cols1
                
                sheet_comparisons[sheet] = {
                    'rows1': len(df1),
                    'rows2': len(df2),
                    'common_columns': len(common_cols),
                    'only_in_file1': list(only_in_cols1),
                    'only_in_file2': list(only_in_cols2),
                    'column_similarity': len(common_cols) / max(len(cols1), len(cols2)) if cols1 or cols2 else 0
                }
            
            return {
                'sheet_similarity': len(common_sheets) / max(len(sheets1), len(sheets2)) if sheets1 or sheets2 else 0,
                'common_sheets': list(common_sheets),
                'only_in_file1': list(only_in_1),
                'only_in_file2': list(only_in_2),
                'sheet_comparisons': sheet_comparisons
            }
            
        except Exception as e:
            logger.error(f"Error comparing Excel structures: {e}")
            return {'error': str(e)}
    
    def detect_override_by_name_pattern(self, file_name: str) -> Optional[str]:
        """
        Detect base document name from override file name.
        
        Args:
            file_name: Override file name (e.g., "Смета_правленная_последняя.xlsx")
            
        Returns:
            Base document name (e.g., "Смета.xlsx") or None
        """
        import re
        
        # Remove override patterns
        base_name = file_name
        for pattern in self.override_patterns:
            base_name = re.sub(pattern, '', base_name, flags=re.IGNORECASE)
        
        # Clean up
        base_name = re.sub(r'[_-]+', '_', base_name).strip('_-')
        
        if base_name != file_name:
            return base_name
        
        return None


class DocumentOverrideManager:
    """
    Manage document overrides in the system.
    
    Tracks overrides and marks old documents as DEPRECATED.
    """
    
    def __init__(self):
        """Initialize Document Override Manager."""
        self.detector = OverrideDetector()
        self._ensure_tables()
    
    def _ensure_tables(self):
        """Create necessary database tables."""
        try:
            from app.modules.storage.database import get_db_connection
            
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Document overrides table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS document_overrides (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        base_document_id TEXT NOT NULL,
                        override_document_id TEXT NOT NULL,
                        override_version INTEGER,
                        override_detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        similarity_score REAL,
                        detection_method TEXT,
                        metadata TEXT DEFAULT '{}'
                    )
                """)
                
                logger.info("Document overrides table initialized")
                
        except Exception as e:
            logger.error(f"Error creating document overrides table: {e}")
    
    def register_override(
        self,
        base_document_id: str,
        override_document_id: str,
        override_version: int,
        similarity_score: float,
        detection_method: str
    ) -> int:
        """
        Register a document override.
        
        Args:
            base_document_id: Base document ID
            override_document_id: Override document ID
            override_version: Override version number
            similarity_score: Similarity score
            detection_method: Detection method
            
        Returns:
            Override ID
        """
        try:
            from app.modules.storage.database import get_db_connection
            
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO document_overrides (
                        base_document_id, override_document_id, override_version,
                        similarity_score, detection_method
                    ) VALUES (?, ?, ?, ?, ?)
                """, (base_document_id, override_document_id, override_version, 
                      similarity_score, detection_method))
                
                override_id = cursor.lastrowid
                logger.info(f"Registered override: {base_document_id} -> {override_document_id}")
                return override_id
                
        except Exception as e:
            logger.error(f"Error registering override: {e}")
            return -1
    
    def mark_document_deprecated(self, document_id: str, override_document_id: str) -> bool:
        """
        Mark a document as DEPRECATED.
        
        Args:
            document_id: Document ID to mark as deprecated
            override_document_id: Document that overrides it
            
        Returns:
            True if successful
        """
        try:
            from app.modules.storage.database import get_db_connection
            
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Update document status
                cursor.execute("""
                    UPDATE document_links
                    SET status = 'deprecated', deprecated_by = ?
                    WHERE document_id = ?
                """, (override_document_id, document_id))
                
                logger.info(f"Marked document {document_id} as deprecated (overridden by {override_document_id})")
                return True
                
        except Exception as e:
            logger.error(f"Error marking document deprecated: {e}")
            return False
    
    def get_override_chain(self, document_id: str) -> List[Dict[str, Any]]:
        """
        Get the override chain for a document.
        
        Args:
            document_id: Document ID
            
        Returns:
            List of overrides in chain
        """
        try:
            from app.modules.storage.database import get_db_connection
            
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM document_overrides
                    WHERE base_document_id = ?
                    ORDER BY override_version ASC
                """, (document_id,))
                
                overrides = []
                for row in cursor.fetchall():
                    overrides.append({
                        'id': row['id'],
                        'base_document_id': row['base_document_id'],
                        'override_document_id': row['override_document_id'],
                        'override_version': row['override_version'],
                        'similarity_score': row['similarity_score'],
                        'detection_method': row['detection_method'],
                        'detected_at': row['override_detected_at']
                    })
                
                return overrides
                
        except Exception as e:
            logger.error(f"Error getting override chain: {e}")
            return []


if __name__ == "__main__":
    # Test Override Detector
    logging.basicConfig(level=logging.INFO)
    
    detector = OverrideDetector()
    
    # Test override detection by name
    override_candidate = detector.detect_override_candidate("Смета_правленная_последняя.xlsx")
    print(f"Override candidate: {override_candidate}")
    
    # Test base name extraction
    base_name = detector.detect_override_by_name_pattern("Смета_правленная_последняя.xlsx")
    print(f"Base name: {base_name}")
