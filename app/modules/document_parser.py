"""Document parsers for Mia PM OS

This module provides parsers for various document types to extract
text and structured information for RAG and summarization.
"""

import os
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
import json

logger = logging.getLogger(__name__)

class DocumentParser:
    """Base class for document parsers"""
    
    def __init__(self):
        self.supported_extensions = []
        self.parser_name = "base"
    
    def can_parse(self, file_path: Union[str, Path]) -> bool:
        """Check if this parser can handle the file"""
        file_path = Path(file_path)
        return file_path.suffix.lower() in self.supported_extensions
    
    def parse(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """Parse document and return structured data"""
        raise NotImplementedError("Subclasses must implement parse method")
    
    def extract_text(self, file_path: Union[str, Path]) -> str:
        """Extract plain text from document"""
        raise NotImplementedError("Subclasses must implement extract_text method")


class PDFParser(DocumentParser):
    """Parser for PDF documents using PyMuPDF"""
    
    def __init__(self):
        super().__init__()
        self.supported_extensions = ['.pdf']
        self.parser_name = "pdf"
        self.pymupdf_available = False
        self._check_pymupdf()
    
    def _check_pymupdf(self):
        """Check if PyMuPDF is available"""
        try:
            import fitz  # PyMuPDF
            self.pymupdf_available = True
            logger.info("PyMuPDF is available for PDF parsing")
        except ImportError:
            logger.warning("PyMuPDF not available. Install with: pip install pymupdf")
    
    def parse(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """Parse PDF document and return structured data"""
        if not self.pymupdf_available:
            return {
                'success': False,
                'error': 'PyMuPDF not available',
                'text': '',
                'metadata': {}
            }
        
        try:
            import fitz  # PyMuPDF
            
            file_path = Path(file_path)
            doc = fitz.open(str(file_path))
            
            # Extract text from all pages
            text_content = []
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text()
                text_content.append({
                    'page': page_num + 1,
                    'text': text
                })
            
            # Extract metadata
            metadata = {
                'page_count': len(doc),
                'title': doc.metadata.get('title', ''),
                'author': doc.metadata.get('author', ''),
                'subject': doc.metadata.get('subject', ''),
                'keywords': doc.metadata.get('keywords', ''),
                'creator': doc.metadata.get('creator', ''),
                'producer': doc.metadata.get('producer', ''),
                'creation_date': doc.metadata.get('creationDate', ''),
                'modification_date': doc.metadata.get('modDate', ''),
            }
            
            doc.close()
            
            return {
                'success': True,
                'text': '\n\n'.join([page['text'] for page in text_content]),
                'pages': text_content,
                'metadata': metadata,
                'file_size': file_path.stat().st_size if file_path.exists() else 0
            }
            
        except Exception as e:
            logger.error(f"Error parsing PDF {file_path}: {e}")
            return {
                'success': False,
                'error': str(e),
                'text': '',
                'metadata': {}
            }
    
    def extract_text(self, file_path: Union[str, Path]) -> str:
        """Extract plain text from PDF"""
        result = self.parse(file_path)
        return result.get('text', '')


class WordParser(DocumentParser):
    """Parser for Word documents using python-docx"""
    
    def __init__(self):
        super().__init__()
        self.supported_extensions = ['.docx', '.doc']
        self.parser_name = "word"
        self.docx_available = False
        self._check_docx()
    
    def _check_docx(self):
        """Check if python-docx is available"""
        try:
            from docx import Document
            self.docx_available = True
            logger.info("python-docx is available for Word parsing")
        except ImportError:
            logger.warning("python-docx not available. Install with: pip install python-docx")
    
    def parse(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """Parse Word document and return structured data"""
        if not self.docx_available:
            return {
                'success': False,
                'error': 'python-docx not available',
                'text': '',
                'metadata': {}
            }
        
        try:
            from docx import Document
            
            file_path = Path(file_path)
            doc = Document(str(file_path))
            
            # Extract text from paragraphs
            paragraphs = []
            for para in doc.paragraphs:
                if para.text.strip():
                    paragraphs.append({
                        'text': para.text,
                        'style': para.style.name if para.style else ''
                    })
            
            # Extract text from tables
            tables = []
            for table in doc.tables:
                table_data = []
                for row in table.rows:
                    row_data = []
                    for cell in row.cells:
                        row_data.append(cell.text.strip())
                    table_data.append(row_data)
                tables.append(table_data)
            
            # Extract metadata
            metadata = {
                'paragraph_count': len(doc.paragraphs),
                'table_count': len(doc.tables),
                'title': doc.core_properties.title or '',
                'author': doc.core_properties.author or '',
                'subject': doc.core_properties.subject or '',
                'keywords': doc.core_properties.keywords or '',
                'created': doc.core_properties.created or '',
                'modified': doc.core_properties.modified or '',
                'last_modified_by': doc.core_properties.last_modified_by or '',
            }
            
            return {
                'success': True,
                'text': '\n\n'.join([para['text'] for para in paragraphs]),
                'paragraphs': paragraphs,
                'tables': tables,
                'metadata': metadata,
                'file_size': file_path.stat().st_size if file_path.exists() else 0
            }
            
        except Exception as e:
            logger.error(f"Error parsing Word document {file_path}: {e}")
            return {
                'success': False,
                'error': str(e),
                'text': '',
                'metadata': {}
            }
    
    def extract_text(self, file_path: Union[str, Path]) -> str:
        """Extract plain text from Word document"""
        result = self.parse(file_path)
        return result.get('text', '')


class ExcelParser(DocumentParser):
    """Parser for Excel documents using openpyxl"""
    
    def __init__(self):
        super().__init__()
        self.supported_extensions = ['.xlsx', '.xls']
        self.parser_name = "excel"
        self.openpyxl_available = False
        self._check_openpyxl()
    
    def _check_openpyxl(self):
        """Check if openpyxl is available"""
        try:
            import openpyxl
            self.openpyxl_available = True
            logger.info("openpyxl is available for Excel parsing")
        except ImportError:
            logger.warning("openpyxl not available. Install with: pip install openpyxl")
    
    def parse(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """Parse Excel document and return structured data"""
        if not self.openpyxl_available:
            return {
                'success': False,
                'error': 'openpyxl not available',
                'text': '',
                'metadata': {}
            }
        
        try:
            import openpyxl
            
            file_path = Path(file_path)
            workbook = openpyxl.load_workbook(str(file_path), data_only=True)
            
            # Extract data from all sheets
            sheets = []
            text_content = []
            
            for sheet_name in workbook.sheetnames:
                sheet = workbook[sheet_name]
                sheet_data = []
                
                for row in sheet.iter_rows(values_only=True):
                    row_data = [str(cell) if cell is not None else '' for cell in row]
                    sheet_data.append(row_data)
                    # Add non-empty rows to text content
                    if any(cell.strip() for cell in row_data):
                        text_content.append(' | '.join(row_data))
                
                sheets.append({
                    'name': sheet_name,
                    'data': sheet_data,
                    'row_count': len(sheet_data),
                    'column_count': len(sheet_data[0]) if sheet_data else 0
                })
            
            # Extract metadata
            metadata = {
                'sheet_count': len(workbook.sheetnames),
                'sheet_names': workbook.sheetnames,
                'title': workbook.properties.title or '',
                'author': workbook.properties.creator or '',
                'created': workbook.properties.created or '',
                'modified': workbook.properties.modified or '',
            }
            
            workbook.close()
            
            return {
                'success': True,
                'text': '\n\n'.join(text_content),
                'sheets': sheets,
                'metadata': metadata,
                'file_size': file_path.stat().st_size if file_path.exists() else 0
            }
            
        except Exception as e:
            logger.error(f"Error parsing Excel document {file_path}: {e}")
            return {
                'success': False,
                'error': str(e),
                'text': '',
                'metadata': {}
            }
    
    def extract_text(self, file_path: Union[str, Path]) -> str:
        """Extract plain text from Excel document"""
        result = self.parse(file_path)
        return result.get('text', '')


class ImageParser(DocumentParser):
    """Parser for image documents using OCR (Tesseract)"""
    
    def __init__(self):
        super().__init__()
        self.supported_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff']
        self.parser_name = "image"
        self.tesseract_available = False
        self._check_tesseract()
    
    def _check_tesseract(self):
        """Check if Tesseract OCR is available"""
        try:
            import pytesseract
            from PIL import Image
            self.tesseract_available = True
            logger.info("Tesseract OCR is available for image parsing")
        except ImportError:
            logger.warning("Tesseract OCR not available. Install with: pip install pytesseract pillow")
    
    def parse(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """Parse image document using OCR and return structured data"""
        if not self.tesseract_available:
            return {
                'success': False,
                'error': 'Tesseract OCR not available',
                'text': '',
                'metadata': {}
            }
        
        try:
            import pytesseract
            from PIL import Image
            
            file_path = Path(file_path)
            image = Image.open(str(file_path))
            
            # Extract text using OCR
            text = pytesseract.image_to_string(image, lang='rus+eng')
            
            # Extract metadata
            metadata = {
                'format': image.format,
                'mode': image.mode,
                'size': image.size,
                'width': image.width,
                'height': image.height,
            }
            
            return {
                'success': True,
                'text': text,
                'metadata': metadata,
                'file_size': file_path.stat().st_size if file_path.exists() else 0
            }
            
        except Exception as e:
            logger.error(f"Error parsing image {file_path}: {e}")
            return {
                'success': False,
                'error': str(e),
                'text': '',
                'metadata': {}
            }
    
    def extract_text(self, file_path: Union[str, Path]) -> str:
        """Extract plain text from image using OCR"""
        result = self.parse(file_path)
        return result.get('text', '')


class TextParser(DocumentParser):
    """Parser for plain text documents"""
    
    def __init__(self):
        super().__init__()
        self.supported_extensions = ['.txt', '.csv', '.json', '.xml', '.log', '.md']
        self.parser_name = "text"
    
    def parse(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """Parse text document and return structured data"""
        try:
            file_path = Path(file_path)
            
            # Read file with UTF-8 encoding
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read()
            
            # Extract metadata
            metadata = {
                'line_count': len(text.split('\n')),
                'char_count': len(text),
                'encoding': 'utf-8',
            }
            
            return {
                'success': True,
                'text': text,
                'metadata': metadata,
                'file_size': file_path.stat().st_size if file_path.exists() else 0
            }
            
        except Exception as e:
            logger.error(f"Error parsing text file {file_path}: {e}")
            return {
                'success': False,
                'error': str(e),
                'text': '',
                'metadata': {}
            }
    
    def extract_text(self, file_path: Union[str, Path]) -> str:
        """Extract plain text from text file"""
        result = self.parse(file_path)
        return result.get('text', '')


class DocumentParserFactory:
    """Factory for creating appropriate document parsers"""
    
    def __init__(self):
        self.parsers = [
            PDFParser(),
            WordParser(),
            ExcelParser(),
            ImageParser(),
            TextParser(),
        ]
    
    def get_parser(self, file_path: Union[str, Path]) -> Optional[DocumentParser]:
        """Get appropriate parser for file"""
        file_path = Path(file_path)
        
        for parser in self.parsers:
            if parser.can_parse(file_path):
                return parser
        
        logger.warning(f"No parser found for file: {file_path}")
        return None
    
    def parse_document(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """Parse document using appropriate parser"""
        parser = self.get_parser(file_path)
        
        if parser is None:
            return {
                'success': False,
                'error': f'No parser available for file: {file_path}',
                'text': '',
                'metadata': {}
            }
        
        return parser.parse(file_path)
    
    def extract_text(self, file_path: Union[str, Path]) -> str:
        """Extract text from document using appropriate parser"""
        parser = self.get_parser(file_path)
        
        if parser is None:
            return ''
        
        return parser.extract_text(file_path)


# Convenience function
def parse_document(file_path: Union[str, Path]) -> Dict[str, Any]:
    """Parse document using appropriate parser"""
    factory = DocumentParserFactory()
    return factory.parse_document(file_path)


def extract_text(file_path: Union[str, Path]) -> str:
    """Extract text from document using appropriate parser"""
    factory = DocumentParserFactory()
    return factory.extract_text(file_path)