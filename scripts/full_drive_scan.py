"""Full scan of Google Drive folder structure"""

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

def generate_statistics(scan_result):
    """Generate statistics from scan results"""
    file_types = {}
    document_types = {}
    file_sizes = []
    total_files = 0
    total_size = 0
    
    def process_folder(folder):
        nonlocal total_files, total_size
        
        for file in folder.get('files', []):
            file_type = file['file_type_category']
            doc_type = file['document_type']
            
            file_types[file_type] = file_types.get(file_type, 0) + 1
            document_types[doc_type] = document_types.get(doc_type, 0) + 1
            
            # Handle size conversion
            file_size = file['size']
            if isinstance(file_size, str):
                try:
                    file_size = int(file_size)
                except:
                    file_size = 0
            
            file_sizes.append(file_size)
            total_files += 1
            total_size += file_size
        
        for subfolder in folder.get('subfolders', []):
            process_folder(subfolder)
    
    process_folder(scan_result)
    
    return {
        'total_files': total_files,
        'total_size': total_size,
        'files_by_type': file_types,
        'documents_by_type': document_types,
        'average_file_size': sum(file_sizes) / len(file_sizes) if file_sizes else 0,
        'largest_file': max(file_sizes) if file_sizes else 0,
        'smallest_file': min(file_sizes) if file_sizes else 0
    }

def main():
    credentials_path = os.getenv('GOOGLE_DRIVE_OAUTH_CREDENTIALS_PATH', 'config/oauth_credentials.json')
    target_folder_id = os.getenv('GOOGLE_DRIVE_TARGET_FOLDER_ID', '1LXFAfJ7K7uwNfSaTGxMFf2hF9osn_WBv')
    
    scanner = OAuthDriveScanner(credentials_path, target_folder_id)
    
    print("Starting OAuth authentication...")
    print("A browser window will open. Please authorize the application.")
    
    if not scanner.authenticate():
        print("Error: OAuth authentication failed")
        return
    
    print("OAuth authentication successful!")
    print(f"\nStarting full scan of folder: {target_folder_id}")
    print("This may take several minutes depending on the number of files...")
    
    scan_start = datetime.now()
    
    # Perform full scan
    scan_result = scan_folder_structure(scanner, target_folder_id)
    
    scan_end = datetime.now()
    scan_duration = (scan_end - scan_start).total_seconds()
    
    # Generate statistics
    statistics = generate_statistics(scan_result)
    
    # Prepare final result
    final_result = {
        'scan_metadata': {
            'scan_timestamp': scan_start.isoformat(),
            'scan_duration_seconds': scan_duration,
            'target_folder_id': target_folder_id,
            'total_folders_scanned': scanner.stats['folders_scanned'],
            'total_files_analyzed': scanner.stats['files_analyzed'],
            'api_calls': scanner.stats['api_calls'],
            'errors': scanner.stats['errors']
        },
        'folder_structure': scan_result,
        'file_statistics': statistics
    }
    
    # Save results to JSON file
    output_file = Path('google_drive_scan_result.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(final_result, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*60}")
    print("SCAN COMPLETE")
    print(f"{'='*60}")
    print(f"Scan duration: {scan_duration:.2f} seconds")
    print(f"Total folders: {scanner.stats['folders_scanned']}")
    print(f"Total files: {scanner.stats['files_analyzed']}")
    print(f"API calls: {scanner.stats['api_calls']}")
    print(f"Errors: {scanner.stats['errors']}")
    print(f"\nFile statistics:")
    print(f"  Total files: {statistics['total_files']}")
    print(f"  Total size: {statistics['total_size']:,} bytes")
    print(f"  Average file size: {statistics['average_file_size']:,.0f} bytes")
    print(f"\nFiles by type:")
    for file_type, count in statistics['files_by_type'].items():
        print(f"  {file_type}: {count}")
    print(f"\nDocuments by type:")
    for doc_type, count in statistics['documents_by_type'].items():
        print(f"  {doc_type}: {count}")
    
    print(f"\nResults saved to: {output_file}")
    print("Full structure saved to JSON file for detailed analysis.")

if __name__ == "__main__":
    main()