"""Scan the Договоры folder from Google Drive."""

import sys
import os
import json
from pathlib import Path
from datetime import datetime

# Fix Windows console encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

from app.modules.google_drive.oauth_scanner import OAuthDriveScanner

print("=" * 60)
print("Scanning Договоры Folder from Google Drive")
print("=" * 60)

# Credentials path from environment
credentials_path = os.getenv('GOOGLE_DRIVE_CREDENTIALS_PATH', 'config/google_drive_credentials.json')

# Target folder ID from user
contracts_folder_id = "1-QyyTdw8HCf7e3s5UPVjeAWkLr6AhVRx"

# Initialize scanner
scanner = OAuthDriveScanner(credentials_path=credentials_path, target_folder_id=contracts_folder_id)

print(f"\n📂 Target folder ID: {contracts_folder_id}")
print("🔗 URL: https://drive.google.com/drive/folders/1-QyyTdw8HCf7e3s5UPVjeAWkLr6AhVRx?usp=drive_link")

try:
    # Authenticate
    print("\n🔐 Authenticating with Google Drive...")
    if not scanner.authenticate():
        print("❌ Authentication failed")
        sys.exit(1)
    
    print("✅ Authentication successful")
    
    # Scan the contracts folder recursively
    print("\n🔍 Starting scan...")
    
    def scan_folder_structure(scanner, folder_id, current_path=""):
        """Recursively scan folder structure"""
        try:
            folder_info = scanner.get_folder_info(folder_id)
            if not folder_info:
                return {
                    'error': f"Could not access folder {folder_id}",
                    'folder_id': folder_id,
                    'name': 'Unknown',
                    'path': current_path,
                    'subfolders': [],
                    'files': [],
                    'file_count': 0,
                    'total_size': 0
                }
        except Exception as e:
            print(f"Error accessing folder {folder_id}: {e}")
            return {
                'error': str(e),
                'folder_id': folder_id,
                'name': 'Unknown',
                'path': current_path,
                'subfolders': [],
                'files': [],
                'file_count': 0,
                'total_size': 0
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
        
        # Handle folder size conversion
        folder_size = folder_info.get('size', 0)
        if isinstance(folder_size, str):
            try:
                folder_size = int(folder_size)
            except:
                folder_size = 0
        result['total_size'] = folder_size
        
        # List and scan subfolders
        try:
            subfolders = scanner.list_subfolders(folder_id)
            print(f"Scanning folder: {folder_info['name']} - {len(subfolders)} subfolders")
            
            for subfolder in subfolders:
                subfolder_result = scan_folder_structure(scanner, subfolder['id'], current_path)
                result['subfolders'].append(subfolder_result)
                result['file_count'] += subfolder_result.get('file_count', 0)
                # Handle size conversion
                subfolder_size = subfolder_result.get('total_size', 0)
                if isinstance(subfolder_size, str):
                    try:
                        subfolder_size = int(subfolder_size)
                    except:
                        subfolder_size = 0
                result['total_size'] += subfolder_size
        except Exception as e:
            print(f"Error listing subfolders for {folder_info['name']}: {e}")
        
        # List and analyze files
        try:
            files = scanner.list_files(folder_id)
            print(f"  Found {len(files)} files")
            
            for file in files:
                file_analysis = scanner.analyze_file(file)
                result['files'].append(file_analysis)
                result['file_count'] += 1
                # Handle size conversion
                file_size = file_analysis['size']
                if isinstance(file_size, str):
                    try:
                        file_size = int(file_size)
                    except:
                        file_size = 0
                result['total_size'] += file_size
        except Exception as e:
            print(f"Error listing files for {folder_info['name']}: {e}")
        
        return result
    
    # Perform the scan
    folder_structure = scan_folder_structure(scanner, contracts_folder_id)
    
    # Generate statistics using a class to avoid nonlocal issues
    class Statistics:
        def __init__(self):
            self.file_types = {}
            self.document_types = {}
            self.total_files = 0
            self.total_size = 0
            self.total_folders = 0
        
        def process_folder(self, folder):
            self.total_folders += 1
            
            for file in folder.get('files', []):
                file_type = file['file_type_category']
                doc_type = file['document_type']
                
                self.file_types[file_type] = self.file_types.get(file_type, 0) + 1
                self.document_types[doc_type] = self.document_types.get(doc_type, 0) + 1
                
                # Handle size conversion
                file_size = file['size']
                if isinstance(file_size, str):
                    try:
                        file_size = int(file_size)
                    except:
                        file_size = 0
                
                self.total_files += 1
                self.total_size += file_size
            
            for subfolder in folder.get('subfolders', []):
                self.process_folder(subfolder)
    
    stats = Statistics()
    stats.process_folder(folder_structure)
    
    file_types = stats.file_types
    document_types = stats.document_types
    total_files = stats.total_files
    total_size = stats.total_size
    total_folders = stats.total_folders
    
    # Build scan result
    scan_result = {
        'scan_metadata': {
            'scan_timestamp': datetime.now().isoformat(),
            'target_folder_id': contracts_folder_id,
            'target_folder_name': folder_structure['name'],
            'total_folders_scanned': total_folders,
            'total_files_analyzed': total_files,
            'total_size_bytes': total_size,
            'total_size_mb': total_size / (1024 * 1024),
            'api_calls': scanner.stats['api_calls'],
            'errors': scanner.stats['errors']
        },
        'folder_structure': folder_structure,
        'file_statistics': file_types,
        'document_statistics': document_types
    }
    
    # Save scan result
    output_file = project_root / "google_drive_contracts_scan.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(scan_result, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Scan completed successfully!")
    print(f"📄 Results saved to: {output_file}")
    
    # Print summary
    scan_metadata = scan_result.get('scan_metadata', {})
    print(f"\n📊 Scan Summary:")
    print(f"   Total folders scanned: {scan_metadata.get('total_folders_scanned', 0)}")
    print(f"   Total files analyzed: {scan_metadata.get('total_files_analyzed', 0)}")
    print(f"   Total size: {scan_metadata.get('total_size_mb', 0):.2f} MB")
    print(f"   API calls made: {scan_metadata.get('api_calls', 0)}")
    print(f"   Errors encountered: {scan_metadata.get('errors', 0)}")
    
    # Print file statistics
    file_stats = scan_result.get('file_statistics', {})
    print(f"\n📁 File Statistics:")
    for ext, count in sorted(file_stats.items()):
        print(f"   {ext}: {count}")
    
    # Print document statistics
    doc_stats = scan_result.get('document_statistics', {})
    print(f"\n📄 Document Statistics:")
    for doc_type, count in sorted(doc_stats.items(), key=lambda x: x[1], reverse=True)[:20]:
        print(f"   {doc_type}: {count}")
    
    # Print folder structure overview
    folder_structure = scan_result.get('folder_structure', {})
    print(f"\n🗂️ Folder Structure:")
    print(f"   Root folder: {folder_structure.get('name', 'Unknown')}")
    print(f"   Direct subfolders: {len(folder_structure.get('subfolders', []))}")
    
    # Show top-level subfolders
    print(f"\n   Top-level subfolders:")
    for subfolder in folder_structure.get('subfolders', [])[:20]:
        print(f"   - {subfolder.get('name', 'Unknown')} (ID: {subfolder.get('id', 'Unknown')})")
    
    if len(folder_structure.get('subfolders', [])) > 20:
        print(f"   ... and {len(folder_structure.get('subfolders', [])) - 20} more")
    
except Exception as e:
    print(f"\n❌ Error during scan: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
