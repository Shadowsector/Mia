"""Google Drive file downloader for Mia PM OS

This module provides functionality to download files from Google Drive
and process them with document parsers.
"""

import os
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
import json

try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GOOGLE_DRIVE_AVAILABLE = True
except ImportError:
    GOOGLE_DRIVE_AVAILABLE = False

logger = logging.getLogger(__name__)


class GoogleDriveDownloader:
    """Downloader for Google Drive files"""
    
    SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
    TOKEN_FILE = 'config/google_drive_token.json'
    SUPPORTS_ALL_DRIVES = True
    
    def __init__(self, credentials_path: str):
        self.credentials_path = credentials_path
        self.service = None
        self.authenticated = False
    
    def authenticate(self) -> bool:
        """Authenticate with Google Drive API using OAuth 2.0"""
        if not GOOGLE_DRIVE_AVAILABLE:
            logger.error("Google Drive libraries not available")
            return False
        
        try:
            creds = None
            
            # Load existing token if available
            if os.path.exists(self.TOKEN_FILE):
                try:
                    with open(self.TOKEN_FILE, 'r') as token:
                        creds = Credentials.from_authorized_user_info(json.load(token))
                    if creds and creds.expired and creds.refresh_token:
                        creds.refresh(Request())
                except Exception as e:
                    logger.warning(f"Could not load token: {e}")
                    creds = None
            
            if creds and creds.valid:
                self.service = build('drive', 'v3', credentials=creds)
                self.authenticated = True
                logger.info("Successfully authenticated with Google Drive")
                return True
            else:
                logger.error("No valid credentials found. Run OAuth authentication first.")
                return False
                
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return False
    
    def download_file(self, file_id: str, output_path: Path, file_name: str) -> Dict[str, Any]:
        """Download a file from Google Drive"""
        if not self.authenticated:
            return {
                'success': False,
                'error': 'Not authenticated'
            }
        
        try:
            # Create output directory if it doesn't exist
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Get file metadata
            file_metadata = self.service.files().get(
                fileId=file_id,
                supportsAllDrives=self.SUPPORTS_ALL_DRIVES
            ).execute()
            
            mime_type = file_metadata.get('mimeType', '')
            
            # Check if it's a Google Docs file that needs export
            if mime_type.startswith('application/vnd.google-apps'):
                return self.export_file(file_id, output_path, file_name, mime_type)
            
            # Download binary file content
            request = self.service.files().get_media(
                fileId=file_id,
                supportsAllDrives=self.SUPPORTS_ALL_DRIVES
            )
            
            # Download file using MediaIoBaseDownload
            import io
            from googleapiclient.http import MediaIoBaseDownload
            
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()
            
            # Write to file
            with open(output_path, 'wb') as f:
                f.write(fh.getvalue())
            
            return {
                'success': True,
                'file_path': str(output_path),
                'file_name': file_name,
                'file_id': file_id,
                'metadata': file_metadata,
                'exported': False
            }
            
        except HttpError as e:
            logger.error(f"Error downloading file {file_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
        except Exception as e:
            logger.error(f"Unexpected error downloading file {file_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def export_file(self, file_id: str, output_path: Path, file_name: str, mime_type: str) -> Dict[str, Any]:
        """Export Google Docs file to appropriate format"""
        try:
            # Determine export MIME type based on Google Docs type
            export_mime_types = {
                'application/vnd.google-apps.document': 'application/pdf',
                'application/vnd.google-apps.spreadsheet': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'application/vnd.google-apps.presentation': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
                'application/vnd.google-apps.drawing': 'application/pdf',
            }
            
            export_mime = export_mime_types.get(mime_type, 'application/pdf')
            
            # Adjust output extension based on export type
            if export_mime == 'application/pdf':
                output_path = output_path.with_suffix('.pdf')
            elif export_mime == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':
                output_path = output_path.with_suffix('.xlsx')
            elif export_mime == 'application/vnd.openxmlformats-officedocument.presentationml.presentation':
                output_path = output_path.with_suffix('.pptx')
            
            # Export file
            request = self.service.files().export_media(
                fileId=file_id,
                mimeType=export_mime
            )
            
            # Download using MediaIoBaseDownload
            import io
            from googleapiclient.http import MediaIoBaseDownload
            
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()
            
            # Write to file
            with open(output_path, 'wb') as f:
                f.write(fh.getvalue())
            
            return {
                'success': True,
                'file_path': str(output_path),
                'file_name': output_path.name,
                'file_id': file_id,
                'exported': True,
                'export_mime_type': export_mime,
                'original_mime_type': mime_type
            }
            
        except HttpError as e:
            logger.error(f"Error exporting file {file_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
        except Exception as e:
            logger.error(f"Unexpected error exporting file {file_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def download_files_batch(self, file_ids: List[str], output_dir: Path, 
                            file_names: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Download multiple files in batch"""
        results = []
        
        for i, file_id in enumerate(file_ids):
            file_name = file_names[i] if file_names and i < len(file_names) else f"file_{i}"
            output_path = output_dir / file_name
            
            result = self.download_file(file_id, output_path, file_name)
            results.append(result)
            
            logger.info(f"Downloaded {file_name}: {result['success']}")
        
        return results


class DocumentProcessor:
    """Processor for downloading and parsing Google Drive documents"""
    
    def __init__(self, credentials_path: str, download_dir: Path):
        self.downloader = GoogleDriveDownloader(credentials_path)
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        
        # Import document parser
        from app.modules.document_parser import DocumentParserFactory
        self.parser_factory = DocumentParserFactory()
    
    def authenticate(self) -> bool:
        """Authenticate with Google Drive"""
        return self.downloader.authenticate()
    
    def process_file(self, file_id: str, file_name: str, 
                    subfolder: Optional[str] = None) -> Dict[str, Any]:
        """Download and process a single file"""
        # Create output path
        if subfolder:
            output_path = self.download_dir / subfolder / file_name
        else:
            output_path = self.download_dir / file_name
        
        # Download file
        download_result = self.downloader.download_file(file_id, output_path, file_name)
        
        if not download_result['success']:
            return {
                'success': False,
                'error': f"Download failed: {download_result['error']}",
                'file_id': file_id,
                'file_name': file_name
            }
        
        # Use the actual downloaded file path (may have different extension if exported)
        actual_file_path = Path(download_result['file_path'])
        actual_file_name = download_result['file_name']
        
        # Parse file
        parse_result = self.parser_factory.parse_document(actual_file_path)
        
        return {
            'success': True,
            'file_id': file_id,
            'file_name': file_name,
            'actual_file_name': actual_file_name,
            'file_path': str(actual_file_path),
            'download_result': download_result,
            'parse_result': parse_result
        }
    
    def process_files_batch(self, files: List[Dict[str, str]], 
                           subfolder: Optional[str] = None) -> List[Dict[str, Any]]:
        """Process multiple files in batch"""
        results = []
        
        for file_info in files:
            file_id = file_info['id']
            file_name = file_info['name']
            
            result = self.process_file(file_id, file_name, subfolder)
            results.append(result)
            
            logger.info(f"Processed {file_name}: {result['success']}")
        
        return results
    
    def process_scan_result(self, scan_result_file: str, 
                           max_files: int = 10, 
                           skip_dwg: bool = True) -> Dict[str, Any]:
        """Process files from scan result JSON"""
        # Load scan result
        with open(scan_result_file, 'r', encoding='utf-8') as f:
            scan_result = json.load(f)
        
        # Collect files to process
        files_to_process = []
        
        def collect_files(folder):
            for file in folder.get('files', []):
                file_name = file['name']
                file_id = file['id']
                file_ext = Path(file_name).suffix.lower()
                
                # Skip DWG files if requested
                if skip_dwg and file_ext in ['.dwg', '.dxf', '.dwf']:
                    continue
                
                files_to_process.append({
                    'id': file_id,
                    'name': file_name,
                    'path': file.get('path', ''),
                    'file_type_category': file.get('file_type_category', ''),
                    'document_type': file.get('document_type', '')
                })
            
            for subfolder in folder.get('subfolders', []):
                collect_files(subfolder)
        
        collect_files(scan_result['folder_structure'])
        
        # Limit number of files to process
        if max_files > 0:
            files_to_process = files_to_process[:max_files]
        
        logger.info(f"Found {len(files_to_process)} files to process")
        
        # Process files
        results = []
        for i, file_info in enumerate(files_to_process):
            logger.info(f"Processing file {i+1}/{len(files_to_process)}: {file_info['name']}")
            
            result = self.process_file(
                file_info['id'],
                file_info['name'],
                subfolder=str(Path(file_info['path']).parent)
            )
            
            result['scan_info'] = file_info
            results.append(result)
        
        # Generate summary
        successful = sum(1 for r in results if r['success'])
        failed = len(results) - successful
        
        return {
            'total_files': len(files_to_process),
            'successful': successful,
            'failed': failed,
            'results': results
        }


def test_document_processor():
    """Test document processor"""
    from dotenv import load_dotenv
    import os
    
    load_dotenv()
    
    credentials_path = os.getenv('GOOGLE_DRIVE_OAUTH_CREDENTIALS_PATH', 'config/oauth_credentials.json')
    download_dir = Path('downloaded_documents')
    
    processor = DocumentProcessor(credentials_path, download_dir)
    
    if not processor.authenticate():
        print("Authentication failed")
        return
    
    # Process a small batch of files from scan result
    scan_result_file = 'google_drive_scan_result_reclassified.json'
    
    if not Path(scan_result_file).exists():
        print(f"Scan result file not found: {scan_result_file}")
        return
    
    print(f"Processing files from {scan_result_file}...")
    result = processor.process_scan_result(scan_result_file, max_files=5, skip_dwg=True)
    
    print(f"\nProcessing summary:")
    print(f"  Total files: {result['total_files']}")
    print(f"  Successful: {result['successful']}")
    print(f"  Failed: {result['failed']}")
    
    for r in result['results']:
        if r['success']:
            print(f"\n  {r['file_name']}:")
            print(f"    Actual file: {r['actual_file_name']}")
            print(f"    Exported: {r['download_result'].get('exported', False)}")
            print(f"    Text length: {len(r['parse_result']['text'])} characters")
            print(f"    Parse success: {r['parse_result']['success']}")
            if r['parse_result']['success']:
                # Show file type and metadata
                file_path = Path(r['file_path'])
                print(f"    File extension: {file_path.suffix}")
                if 'metadata' in r['parse_result']:
                    metadata = r['parse_result']['metadata']
                    if 'page_count' in metadata:
                        print(f"    Pages: {metadata['page_count']}")
                    if 'sheet_count' in metadata:
                        print(f"    Sheets: {metadata['sheet_count']}")
                    if 'paragraph_count' in metadata:
                        print(f"    Paragraphs: {metadata['paragraph_count']}")
            else:
                print(f"    Parse error: {r['parse_result'].get('error', 'Unknown')}")
        else:
            print(f"\n  {r['file_name']}: FAILED - {r['error']}")


if __name__ == "__main__":
    test_document_processor()