"""Google Drive Scanner for Document Structure Analysis"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from collections import defaultdict

try:
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GOOGLE_DRIVE_AVAILABLE = True
except ImportError:
    GOOGLE_DRIVE_AVAILABLE = False

logger = logging.getLogger(__name__)


class GoogleDriveScanner:
    """Scanner for Google Drive folder structure analysis"""
    
    FILE_TYPE_CATEGORIES = {
        'office_documents': ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx'],
        'cad_drawings': ['.dwg', '.dxf', '.dwf'],
        'images': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff'],
        'archives': ['.zip', '.rar', '.7z', '.tar', '.gz'],
        'text': ['.txt', '.csv', '.json', '.xml'],
        'other': []
    }
    
    DOCUMENT_TYPE_KEYWORDS = {
        'invoice': ['накладная', 'накл', 'акт'],
        'passport': ['паспорт', 'пасп'],
        'project': ['проект', 'project', 'чертеж'],
        'contract': ['договор', 'contract', 'соглашение'],
        'estimate': ['смета', 'estimate']
    }
    
    def __init__(self, credentials_path: str, target_folder_id: str):
        self.credentials_path = credentials_path
        self.target_folder_id = target_folder_id
        self.service = None
        self.stats = {
            'folders_scanned': 0,
            'files_analyzed': 0,
            'api_calls': 0,
            'errors': 0
        }
        
    def authenticate(self) -> bool:
        """Authenticate with Google Drive API using service account"""
        if not GOOGLE_DRIVE_AVAILABLE:
            logger.error("Google Drive libraries not available")
            return False
        
        try:
            credentials = Credentials.from_service_account_file(
                self.credentials_path,
                scopes=['https://www.googleapis.com/auth/drive.readonly']
            )
            
            self.service = build('drive', 'v3', credentials=credentials)
            logger.info("Successfully authenticated with Google Drive API")
            return True
            
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            return False
    
    def list_accessible_folders(self) -> List[Dict[str, Any]]:
        """List all accessible folders"""
        try:
            self.stats['api_calls'] += 1
            results = self.service.files().list(
                q="mimeType='application/vnd.google-apps.folder'",
                fields='files(id,name)',
                pageSize=100
            ).execute()
            
            return results.get('files', [])
            
        except HttpError as e:
            logger.error(f"Error listing accessible folders: {e}")
            self.stats['errors'] += 1
            return []
    
    def find_folder_by_name(self, folder_name: str) -> Optional[str]:
        """Find folder ID by name"""
        try:
            self.stats['api_calls'] += 1
            results = self.service.files().list(
                q=f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}'",
                fields='files(id,name)',
                pageSize=10
            ).execute()
            
            folders = results.get('files', [])
            if folders:
                return folders[0]['id']
            return None
            
        except HttpError as e:
            logger.error(f"Error finding folder by name: {e}")
            self.stats['errors'] += 1
            return None
    
    def get_folder_info(self, folder_id: str) -> Optional[Dict[str, Any]]:
        """Get folder metadata"""
        try:
            self.stats['api_calls'] += 1
            folder = self.service.files().get(
                fileId=folder_id,
                fields='id,name,createdTime,modifiedTime,size'
            ).execute()
            
            return {
                'id': folder['id'],
                'name': folder['name'],
                'created_time': folder.get('createdTime'),
                'modified_time': folder.get('modifiedTime'),
                'size': folder.get('size', 0)
            }
        except HttpError as e:
            logger.error(f"Error getting folder info: {e}")
            self.stats['errors'] += 1
            return None
    
    def list_subfolders(self, folder_id: str) -> List[Dict[str, Any]]:
        """List subfolders in a folder"""
        try:
            self.stats['api_calls'] += 1
            results = self.service.files().list(
                q=f"'{folder_id}' in parents and mimeType='application/vnd.google-apps.folder'",
                fields='files(id,name,createdTime,modifiedTime,size)',
                pageSize=100
            ).execute()
            
            self.stats['folders_scanned'] += len(results.get('files', []))
            return results.get('files', [])
            
        except HttpError as e:
            logger.error(f"Error listing subfolders: {e}")
            self.stats['errors'] += 1
            return []
    
    def list_all_files(self, limit: int = 10) -> List[Dict[str, Any]]:
        """List all accessible files (for debugging)"""
        try:
            self.stats['api_calls'] += 1
            results = self.service.files().list(
                q="trashed=false",
                fields='files(id,name,mimeType)',
                pageSize=limit
            ).execute()
            
            return results.get('files', [])
            
        except HttpError as e:
            logger.error(f"Error listing all files: {e}")
            self.stats['errors'] += 1
            return []
    
    def list_files(self, folder_id: str) -> List[Dict[str, Any]]:
        """List files in a folder"""
        try:
            self.stats['api_calls'] += 1
            results = self.service.files().list(
                q=f"'{folder_id}' in parents and mimeType!='application/vnd.google-apps.folder'",
                fields='files(id,name,mimeType,createdTime,modifiedTime,size,version)',
                pageSize=100
            ).execute()
            
            self.stats['files_analyzed'] += len(results.get('files', []))
            return results.get('files', [])
            
        except HttpError as e:
            logger.error(f"Error listing files: {e}")
            self.stats['errors'] += 1
            return []
        """List all accessible files (for debugging)"""
        try:
            self.stats['api_calls'] += 1
            results = self.service.files().list(
                q="trashed=false",
                fields='files(id,name,mimeType)',
                pageSize=limit
            ).execute()
            
            return results.get('files', [])
            
        except HttpError as e:
            logger.error(f"Error listing all files: {e}")
            self.stats['errors'] += 1
            return []
        """List files in a folder"""
        try:
            self.stats['api_calls'] += 1
            results = self.service.files().list(
                q=f"'{folder_id}' in parents and mimeType!='application/vnd.google-apps.folder'",
                fields='files(id,name,mimeType,createdTime,modifiedTime,size,version)',
                pageSize=100
            ).execute()
            
            self.stats['files_analyzed'] += len(results.get('files', []))
            return results.get('files', [])
            
        except HttpError as e:
            logger.error(f"Error listing files: {e}")
            self.stats['errors'] += 1
            return []
    
    def categorize_file_type(self, filename: str, mime_type: str) -> str:
        """Categorize file by type"""
        filename_lower = filename.lower()
        ext = Path(filename).suffix.lower()
        
        for category, extensions in self.FILE_TYPE_CATEGORIES.items():
            if ext in extensions:
                return category
        
        return 'other'
    
    def infer_document_type(self, filename: str) -> str:
        """Infer document type from filename"""
        filename_lower = filename.lower()
        
        for doc_type, keywords in self.DOCUMENT_TYPE_KEYWORDS.items():
            if any(keyword in filename_lower for keyword in keywords):
                return doc_type
        
        return 'unknown'
    
    def analyze_file(self, file_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze file metadata"""
        filename = file_metadata['name']
        mime_type = file_metadata['mimeType']
        
        return {
            'id': file_metadata['id'],
            'name': filename,
            'mime_type': mime_type,
            'file_type_category': self.categorize_file_type(filename, mime_type),
            'document_type': self.infer_document_type(filename),
            'size': file_metadata.get('size', 0),
            'created_time': file_metadata.get('createdTime'),
            'modified_time': file_metadata.get('modifiedTime'),
            'has_version': file_metadata.get('version') is not None
        }
    
    def scan_folder_structure(self, folder_id: Optional[str] = None, 
                             current_path: str = "") -> Dict[str, Any]:
        """Recursively scan folder structure"""
        if folder_id is None:
            folder_id = self.target_folder_id
        
        # Get folder info
        folder_info = self.get_folder_info(folder_id)
        if not folder_info:
            return {
                'error': f"Could not access folder {folder_id}",
                'folder_id': folder_id
            }
        
        current_path = f"{current_path}/{folder_info['name']}" if current_path else folder_info['name']
        
        result = {
            'folder_id': folder_id,
            'name': folder_info['name'],
            'path': current_path,
            'created_time': folder_info['created_time'],
            'modified_time': folder_info['modified_time'],
            'subfolders': [],
            'files': [],
            'file_count': 0,
            'total_size': 0
        }
        
        # List and scan subfolders
        subfolders = self.list_subfolders(folder_id)
        for subfolder in subfolders:
            subfolder_result = self.scan_folder_structure(subfolder['id'], current_path)
            result['subfolders'].append(subfolder_result)
            result['file_count'] += subfolder_result['file_count']
            result['total_size'] += subfolder_result['total_size']
        
        # List and analyze files
        files = self.list_files(folder_id)
        for file in files:
            file_analysis = self.analyze_file(file)
            result['files'].append(file_analysis)
            result['file_count'] += 1
            result['total_size'] += file_analysis['size']
        
        return result
    
    def get_statistics(self, scan_result: Dict[str, Any]) -> Dict[str, Any]:
        """Generate statistics from scan results"""
        file_types = defaultdict(int)
        document_types = defaultdict(int)
        file_sizes = []
        total_files = 0
        total_size = 0
        
        def process_folder(folder):
            nonlocal total_files, total_size
            
            for file in folder.get('files', []):
                file_types[file['file_type_category']] += 1
                document_types[file['document_type']] += 1
                file_sizes.append(file['size'])
                total_files += 1
                total_size += file['size']
            
            for subfolder in folder.get('subfolders', []):
                process_folder(subfolder)
        
        process_folder(scan_result)
        
        return {
            'total_files': total_files,
            'total_size': total_size,
            'files_by_type': dict(file_types),
            'documents_by_type': dict(document_types),
            'average_file_size': sum(file_sizes) / len(file_sizes) if file_sizes else 0,
            'largest_file': max(file_sizes) if file_sizes else 0,
            'smallest_file': min(file_sizes) if file_sizes else 0
        }


def test_google_drive_access():
    """Test Google Drive access to target folder"""
    from dotenv import load_dotenv
    import os
    
    load_dotenv()
    
    credentials_path = os.getenv('GOOGLE_DRIVE_CREDENTIALS_PATH')
    target_folder_id = os.getenv('GOOGLE_DRIVE_TARGET_FOLDER_ID')
    target_folder_name = os.getenv('GOOGLE_DRIVE_TARGET_FOLDER_NAME')
    
    if not credentials_path:
        print("Error: GOOGLE_DRIVE_CREDENTIALS_PATH not set in .env")
        return False
    
    scanner = GoogleDriveScanner(credentials_path, target_folder_id or "")
    
    if not scanner.authenticate():
        print("Error: Authentication failed")
        return False
    
    print("Authentication successful!")
    print(f"Service account email: {os.getenv('GOOGLE_DRIVE_SERVICE_ACCOUNT_EMAIL')}")
    
    # Try to list all files to see if service account has any access
    print("\nListing first 10 accessible files for debugging...")
    all_files = scanner.list_all_files(10)
    print(f"Accessible files: {len(all_files)}")
    
    if all_files:
        print("First 10 accessible files:")
        for i, file in enumerate(all_files):
            print(f"  {i+1}. {file['name']} ({file['mimeType']})")
    else:
        print("No files accessible at all - service account may have no access to your Drive")
    
    # Try to list accessible folders
    print("\nListing accessible folders...")
    folders = scanner.list_accessible_folders()
    print(f"Accessible folders: {len(folders)}")
    
    if folders:
        print("First 10 accessible folders:")
        for i, folder in enumerate(folders[:10]):
            print(f"  {i+1}. {folder['name']} (ID: {folder['id']})")
    
    # Try to find folder by name first
    if target_folder_name:
        print(f"\nTrying to find folder by name: {target_folder_name}")
        found_id = scanner.find_folder_by_name(target_folder_name)
        
        if found_id:
            print(f"Found folder with ID: {found_id}")
            target_folder_id = found_id
            print(f"Using folder ID: {target_folder_id}")
        else:
            print(f"Could not find folder with name: {target_folder_name}")
    
    # Try to access target folder
    if target_folder_id:
        print(f"\nTrying to access target folder ID: {target_folder_id}")
        folder_info = scanner.get_folder_info(target_folder_id)
        
        if folder_info:
            print(f"Successfully accessed target folder!")
            print(f"   Folder Name: {folder_info['name']}")
            print(f"   Folder ID: {folder_info['id']}")
            print(f"   Created: {folder_info['created_time']}")
            print(f"   Modified: {folder_info['modified_time']}")
            
            # Test listing subfolders
            subfolders = scanner.list_subfolders(target_folder_id)
            print(f"   Subfolders found: {len(subfolders)}")
            
            # Test listing files
            files = scanner.list_files(target_folder_id)
            print(f"   Files found: {len(files)}")
            
            if subfolders:
                print(f"   First subfolder: {subfolders[0]['name']}")
            
            if files:
                print(f"   First file: {files[0]['name']}")
            
            return True
        else:
            print("Error: Could not access target folder with provided ID")
    else:
        print("No target folder ID provided")
    
    return False


if __name__ == "__main__":
    test_google_drive_access()