"""Temporary File Processor - downloads, processes, adds to RAG, then deletes.

This module implements the workflow:
1. Download file to temporary location
2. Parse/extract content
3. Add to RAG (ChromaDB)
4. Delete temporary file
5. Save only metadata/reference
"""

import tempfile
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
import hashlib

from app.modules.document_parser import DocumentParserFactory
from app.modules.storage.database import get_db_connection

logger = logging.getLogger(__name__)


class TempFileProcessor:
    """Processes files temporarily without permanent storage."""
    
    def __init__(self, temp_dir: Optional[Path] = None):
        """Initialize with temporary directory (default: system temp)."""
        if temp_dir is None:
            temp_dir = Path(tempfile.gettempdir()) / "mia_temp_processing"
        self.temp_dir = temp_dir
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.parser_factory = DocumentParserFactory()
    
    def _get_temp_path(self, file_name: str) -> Path:
        """Generate a unique temporary file path."""
        # Add timestamp to avoid conflicts
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = file_name.replace("/", "_").replace("\\", "_")
        return self.temp_dir / f"{timestamp}_{safe_name}"
    
    def process_google_drive_file(
        self,
        file_id: str,
        file_name: str,
        downloader,  # GoogleDriveDownloader instance
        rag_client,  # RAG client (ChromaDB wrapper)
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Process a Google Drive file temporarily.
        
        Workflow:
        1. Download to temp location
        2. Parse content
        3. Add to RAG
        4. Delete temp file
        5. Return metadata reference
        
        Returns:
            {
                'success': bool,
                'file_reference': {...},
                'processed': {...},
                'error': str if failed
            }
        """
        temp_path = None
        try:
            # Step 1: Download to temp location
            temp_path = self._get_temp_path(file_name)
            download_result = downloader.download_file(file_id, temp_path, file_name)
            
            if not download_result['success']:
                return {
                    'success': False,
                    'error': f"Download failed: {download_result['error']}",
                    'file_reference': None
                }
            
            # Step 2: Parse content
            parse_result = self.parser_factory.parse_document(temp_path)
            
            if not parse_result['success']:
                return {
                    'success': False,
                    'error': f"Parse failed: {parse_result.get('error', 'Unknown')}",
                    'file_reference': None
                }
            
            # Step 3: Add to RAG
            rag_added = False
            if parse_result['text'] and len(parse_result['text']) > 0:
                try:
                    # Create document ID from file metadata
                    doc_id = hashlib.md5(f"{file_id}_{file_name}".encode()).hexdigest()
                    
                    # Add to RAG with metadata
                    rag_client.add_document(
                        doc_id=doc_id,
                        text=parse_result['text'],
                        metadata={
                            'source': 'google_drive',
                            'file_id': file_id,
                            'file_name': file_name,
                            'source_url': f"https://drive.google.com/file/d/{file_id}",
                            'processed_at': datetime.now().isoformat(),
                            **(metadata or {})
                        }
                    )
                    rag_added = True
                except Exception as e:
                    logger.warning(f"Failed to add to RAG: {e}")
            
            # Step 4: Create file reference (not the file itself)
            file_reference = {
                'source': 'google_drive',
                'source_id': file_id,
                'source_url': f"https://drive.google.com/file/d/{file_id}",
                'file_name': file_name,
                'added_at': datetime.now().isoformat(),
                'rag_added': rag_added,
                'text_length': len(parse_result['text']),
                'metadata': metadata or {},
                'parse_metadata': parse_result.get('metadata', {})
            }
            
            # Step 5: Delete temp file
            if temp_path.exists():
                temp_path.unlink()
                logger.info(f"Deleted temp file: {temp_path}")
            
            return {
                'success': True,
                'file_reference': file_reference,
                'processed': parse_result
            }
            
        except Exception as e:
            logger.exception(f"Error processing file {file_name}: {e}")
            
            # Cleanup on error
            if temp_path and temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass
            
            return {
                'success': False,
                'error': str(e),
                'file_reference': None
            }
    
    def process_telegram_file(
        self,
        file_path: Path,
        file_name: str,
        chat_title: str,
        user_name: str,
        message_id: int,
        rag_client,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Process a Telegram file temporarily.
        
        Workflow:
        1. Parse content (file already downloaded by Telegram)
        2. Add to RAG
        3. Delete if it was a temp copy
        4. Return metadata reference
        
        Returns:
            {
                'success': bool,
                'file_reference': {...},
                'processed': {...},
                'error': str if failed
            }
        """
        try:
            # Step 1: Parse content
            parse_result = self.parser_factory.parse_document(file_path)
            
            if not parse_result['success']:
                return {
                    'success': False,
                    'error': f"Parse failed: {parse_result.get('error', 'Unknown')}",
                    'file_reference': None
                }
            
            # Step 2: Add to RAG
            rag_added = False
            if parse_result['text'] and len(parse_result['text']) > 0:
                try:
                    # Create document ID from message metadata
                    doc_id = hashlib.md5(f"telegram_{message_id}_{file_name}".encode()).hexdigest()
                    
                    # Add to RAG with metadata
                    rag_client.add_document(
                        doc_id=doc_id,
                        text=parse_result['text'],
                        metadata={
                            'source': 'telegram',
                            'message_id': message_id,
                            'file_name': file_name,
                            'chat_title': chat_title,
                            'user_name': user_name,
                            'reference': f"{user_name} скинул {datetime.now().strftime('%d.%m.%Y')} в чате {chat_title}",
                            'processed_at': datetime.now().isoformat(),
                            **(metadata or {})
                        }
                    )
                    rag_added = True
                except Exception as e:
                    logger.warning(f"Failed to add to RAG: {e}")
            
            # Step 3: Create file reference
            file_reference = {
                'source': 'telegram',
                'source_id': str(message_id),
                'source_url': f"Telegram message {message_id} in {chat_title}",
                'file_name': file_name,
                'added_at': datetime.now().isoformat(),
                'rag_added': rag_added,
                'text_length': len(parse_result['text']),
                'metadata': metadata or {},
                'parse_metadata': parse_result.get('metadata', {}),
                'reference': f"{user_name} скинул {datetime.now().strftime('%d.%m.%Y')} в чате {chat_title}"
            }
            
            # Note: We don't delete the original Telegram file - it's managed by Telegram
            # We only store the reference
            
            return {
                'success': True,
                'file_reference': file_reference,
                'processed': parse_result
            }
            
        except Exception as e:
            logger.exception(f"Error processing Telegram file {file_name}: {e}")
            
            return {
                'success': False,
                'error': str(e),
                'file_reference': None
            }
    
    def cleanup_temp_files(self, max_age_hours: int = 24):
        """Clean up old temporary files."""
        import time
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        
        for temp_file in self.temp_dir.iterdir():
            if temp_file.is_file():
                file_age = current_time - temp_file.stat().st_mtime
                if file_age > max_age_seconds:
                    try:
                        temp_file.unlink()
                        logger.info(f"Cleaned up old temp file: {temp_file}")
                    except Exception as e:
                        logger.warning(f"Failed to cleanup {temp_file}: {e}")
