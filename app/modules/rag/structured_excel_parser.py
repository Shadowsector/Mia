"""Structured Excel Parser - Parse Excel/estimate files into structured data.

This module provides structured parsing for Excel files and construction estimates,
converting them to JSON/Markdown tables for accurate RAG retrieval.
"""

import logging
from typing import Dict, List, Any, Optional
from pathlib import Path
import json

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("pandas not available, Excel parsing disabled")

logger = logging.getLogger(__name__)


class StructuredExcelParser:
    """
    Parse Excel files into structured data for RAG.
    
    Converts Excel tables to JSON/Markdown format to preserve
    numerical relationships and prevent RAG hallucinations.
    """
    
    def __init__(self):
        """Initialize Structured Excel Parser."""
        if not PANDAS_AVAILABLE:
            logger.error("pandas not installed, Excel parsing will not work")
    
    def parse_excel_file(self, file_path: str) -> Dict[str, Any]:
        """
        Parse an Excel file into structured data.
        
        Args:
            file_path: Path to Excel file
            
        Returns:
            Structured data with tables and metadata
        """
        if not PANDAS_AVAILABLE:
            return {
                'success': False,
                'error': 'pandas not available'
            }
        
        file_path = Path(file_path)
        if not file_path.exists():
            return {
                'success': False,
                'error': 'File not found'
            }
        
        try:
            # Read all sheets
            excel_file = pd.ExcelFile(file_path)
            
            result = {
                'success': True,
                'file_path': str(file_path),
                'file_name': file_path.name,
                'sheets': {},
                'total_sheets': len(excel_file.sheet_names)
            }
            
            for sheet_name in excel_file.sheet_names:
                # Read sheet
                df = pd.read_excel(file_path, sheet_name=sheet_name)
                
                # Convert to structured format
                sheet_data = self._convert_dataframe_to_structured(df, sheet_name)
                result['sheets'][sheet_name] = sheet_data
            
            logger.info(f"Parsed Excel file {file_path.name}: {len(excel_file.sheet_names)} sheets")
            return result
            
        except Exception as e:
            logger.error(f"Error parsing Excel file {file_path}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _convert_dataframe_to_structured(self, df: pd.DataFrame, sheet_name: str) -> Dict[str, Any]:
        """
        Convert pandas DataFrame to structured format.
        
        Args:
            df: DataFrame to convert
            sheet_name: Sheet name
            
        Returns:
            Structured data
        """
        # Get basic info
        rows, cols = df.shape
        
        # Convert to records (list of dicts)
        records = df.to_dict('records')
        
        # Clean records (remove NaN values)
        cleaned_records = []
        for record in records:
            cleaned = {k: v for k, v in record.items() if pd.notna(v)}
            cleaned_records.append(cleaned)
        
        # Convert to markdown table
        try:
            markdown_table = df.to_markdown(index=False)
        except ImportError:
            # tabulate is optional; build a simple markdown table manually
            markdown_table = self._dataframe_to_markdown(df)
        
        # Extract numeric columns for metadata
        numeric_columns = df.select_dtypes(include=['number']).columns.tolist()
        
        # Calculate column statistics for numeric columns
        column_stats = {}
        for col in numeric_columns:
            column_stats[col] = {
                'min': float(df[col].min()) if not df[col].empty else None,
                'max': float(df[col].max()) if not df[col].empty else None,
                'sum': float(df[col].sum()) if not df[col].empty else None,
                'mean': float(df[col].mean()) if not df[col].empty else None
            }
        
        return {
            'sheet_name': sheet_name,
            'rows': rows,
            'columns': cols,
            'column_names': df.columns.tolist(),
            'numeric_columns': numeric_columns,
            'column_statistics': column_stats,
            'records': cleaned_records,
            'markdown_table': markdown_table,
            'json_data': json.dumps(cleaned_records, ensure_ascii=False, default=str)
        }
    
    @staticmethod
    def _dataframe_to_markdown(df: "pd.DataFrame") -> str:
        """Render a DataFrame as a markdown table without the tabulate dependency."""
        columns = [str(c) for c in df.columns]

        def cell(value):
            if pd.isna(value):
                return ""
            return str(value).replace("|", "\\|").replace("\n", " ")

        lines = [
            "| " + " | ".join(columns) + " |",
            "| " + " | ".join("---" for _ in columns) + " |",
        ]
        for _, row in df.iterrows():
            lines.append("| " + " | ".join(cell(v) for v in row.tolist()) + " |")
        return "\n".join(lines)

    def extract_estimate_summary(self, structured_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract summary from estimate data.
        
        Args:
            structured_data: Structured Excel data
            
        Returns:
            Estimate summary
        """
        if not structured_data.get('success'):
            return {'error': 'Invalid structured data'}
        
        summary = {
            'total_items': 0,
            'total_amount': 0.0,
            'material_cost': 0.0,
            'labor_cost': 0.0,
            'items': []
        }
        
        for sheet_name, sheet_data in structured_data['sheets'].items():
            # Look for numeric columns that might be costs
            numeric_cols = sheet_data.get('numeric_columns', [])
            
            for col in numeric_cols:
                stats = sheet_data['column_statistics'].get(col, {})
                col_sum = stats.get('sum', 0)
                
                # Try to identify total/итого column
                if any(keyword in col.lower() for keyword in ['итого', 'total', 'сумма', 'sum']):
                    summary['total_amount'] = col_sum
                    break
            
            # Count items
            summary['total_items'] += sheet_data['rows']
        
        return summary
    
    def to_rag_chunks(self, structured_data: Dict[str, Any], chunk_size: int = 500) -> List[Dict[str, Any]]:
        """
        Convert structured data to RAG chunks.
        
        Args:
            structured_data: Structured Excel data
            chunk_size: Max rows per chunk
            
        Returns:
            List of RAG chunks
        """
        if not structured_data.get('success'):
            return []
        
        chunks = []
        
        for sheet_name, sheet_data in structured_data['sheets'].items():
            records = sheet_data['records']
            
            # Split records into chunks
            for i in range(0, len(records), chunk_size):
                chunk_records = records[i:i + chunk_size]
                
                chunk = {
                    'chunk_id': f"{structured_data['file_name']}_{sheet_name}_chunk_{i // chunk_size}",
                    'sheet_name': sheet_name,
                    'chunk_index': i // chunk_size,
                    'total_chunks': (len(records) + chunk_size - 1) // chunk_size,
                    'records': chunk_records,
                    'json_data': json.dumps(chunk_records, ensure_ascii=False, default=str),
                    'column_names': sheet_data['column_names'],
                    'numeric_columns': sheet_data['numeric_columns'],
                    'metadata': {
                        'source_file': structured_data['file_name'],
                        'sheet_name': sheet_name,
                        'chunk_type': 'structured_excel',
                        'row_count': len(chunk_records)
                    }
                }
                
                chunks.append(chunk)
        
        logger.info(f"Generated {len(chunks)} RAG chunks from {structured_data['file_name']}")
        return chunks


class HybridRAG:
    """
    Hybrid RAG system combining vector search and structured data.
    
    Uses vector search for text queries and SQL/structured search
    for numerical data queries.
    """
    
    def __init__(self):
        """Initialize Hybrid RAG."""
        self.excel_parser = StructuredExcelParser()
    
    def ingest_excel_file(self, file_path: str, object_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Ingest an Excel file into RAG system.
        
        Args:
            file_path: Path to Excel file
            object_id: Associated object ID
            
        Returns:
            Ingestion result
        """
        # Parse Excel file
        structured_data = self.excel_parser.parse_excel_file(file_path)
        
        if not structured_data['success']:
            return structured_data
        
        # Generate RAG chunks
        chunks = self.excel_parser.to_rag_chunks(structured_data)
        
        # Add to ChromaDB
        from app.modules.rag.chroma_manager import ChromaManager
        chroma_manager = ChromaManager()
        
        ids = []
        documents = []
        metadatas = []
        
        for chunk in chunks:
            chunk_id = chunk['chunk_id']
            
            # Create document text (JSON + key numeric info)
            document_text = f"Excel chunk from {chunk['sheet_name']}\n"
            document_text += f"Columns: {', '.join(chunk['column_names'])}\n"
            document_text += f"Numeric columns: {', '.join(chunk['numeric_columns'])}\n"
            document_text += f"Data (JSON): {chunk['json_data']}"
            
            metadata = chunk['metadata'].copy()
            if object_id:
                metadata['object_id'] = object_id
            
            ids.append(chunk_id)
            documents.append(document_text)
            metadatas.append(metadata)
        
        try:
            chroma_manager.collection.add(
                ids=ids,
                documents=documents,
                metadatas=metadatas
            )
            
            logger.info(f"Ingested {len(chunks)} chunks from {file_path}")
            
            return {
                'success': True,
                'chunks_added': len(chunks),
                'file_path': file_path,
                'object_id': object_id
            }
            
        except Exception as e:
            logger.error(f"Error adding chunks to ChromaDB: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def query_structured_data(self, query: str, object_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Query structured data (Excel estimates).
        
        Args:
            query: Query text
            object_id: Object ID filter
            
        Returns:
            Query results
        """
        from app.modules.rag.chroma_manager import ChromaManager
        chroma_manager = ChromaManager()
        
        # Build filter
        where_filter = {'chunk_type': 'structured_excel'}
        if object_id:
            where_filter['object_id'] = object_id
        
        # Query ChromaDB
        try:
            results = chroma_manager.collection.query(
                query_texts=[query],
                n_results=10,
                where=where_filter
            )
            
            # Format results
            formatted_results = []
            if results['documents'] and results['documents'][0]:
                for i, doc in enumerate(results['documents'][0]):
                    formatted_results.append({
                        'text': doc,
                        'metadata': results['metadatas'][0][i] if results['metadatas'] else {},
                        'distance': results['distances'][0][i] if results['distances'] else None
                    })
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Error querying structured data: {e}")
            return []


if __name__ == "__main__":
    # Test Structured Excel Parser
    logging.basicConfig(level=logging.INFO)
    
    parser = StructuredExcelParser()
    
    # Test with a sample Excel file (would need actual file)
    # result = parser.parse_excel_file("test.xlsx")
    # print(result)
    
    # Test Hybrid RAG
    hybrid_rag = HybridRAG()
    print("Hybrid RAG initialized")
