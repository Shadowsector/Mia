"""Reclassify documents in JSON scan result with improved patterns"""

import sys
import json
from pathlib import Path

# Fix Windows console encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.modules.google_drive.oauth_scanner import OAuthDriveScanner
from app.modules.google_drive.document_classifier import ImprovedDocumentClassifier

def reclassify_file(file_data: dict, classifier: ImprovedDocumentClassifier) -> dict:
    """Reclassify a single file with improved patterns"""
    file_data['document_type'] = classifier.classify(file_data['name'])
    return file_data

def reclassify_folder(folder_data: dict, classifier: ImprovedDocumentClassifier) -> dict:
    """Recursively reclassify all files in a folder"""
    # Reclassify files in this folder
    for file_data in folder_data.get('files', []):
        reclassify_file(file_data, classifier)
    
    # Recursively reclassify subfolders
    for subfolder in folder_data.get('subfolders', []):
        reclassify_folder(subfolder, classifier)
    
    return folder_data

def generate_new_statistics(scan_result: dict) -> dict:
    """Generate statistics from reclassified scan results"""
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
    
    process_folder(scan_result['folder_structure'])
    
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
    print("Loading existing scan result...")
    
    input_file = Path('google_drive_scan_result.json')
    if not input_file.exists():
        print(f"Error: {input_file} not found")
        return
    
    with open(input_file, 'r', encoding='utf-8') as f:
        scan_result = json.load(f)
    
    print(f"Loaded scan result from {scan_result['scan_metadata']['scan_timestamp']}")
    print(f"Total files: {scan_result['scan_metadata']['total_files_analyzed']}")
    
    # Create improved classifier instance
    classifier = ImprovedDocumentClassifier()
    
    print("\nReclassifying documents with improved regex patterns...")
    reclassify_folder(scan_result['folder_structure'], classifier)
    
    print("Generating new statistics...")
    new_statistics = generate_new_statistics(scan_result)
    
    # Update scan result with new statistics
    scan_result['file_statistics'] = new_statistics
    scan_result['scan_metadata']['reclassification_timestamp'] = '2026-09-12T14:00:00'
    scan_result['scan_metadata']['reclassification_method'] = 'improved_regex_patterns_with_word_boundaries'
    
    # Save reclassified result
    output_file = Path('google_drive_scan_result_reclassified.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(scan_result, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*60}")
    print("RECLASSIFICATION COMPLETE")
    print(f"{'='*60}")
    print(f"Total files: {new_statistics['total_files']}")
    print(f"Total size: {new_statistics['total_size']:,} bytes")
    print(f"Average file size: {new_statistics['average_file_size']:,.0f} bytes")
    
    print(f"\nFiles by type:")
    for file_type, count in sorted(new_statistics['files_by_type'].items(), key=lambda x: x[1], reverse=True):
        print(f"  {file_type}: {count}")
    
    print(f"\nDocuments by type (showing top 20):")
    sorted_docs = sorted(new_statistics['documents_by_type'].items(), key=lambda x: x[1], reverse=True)
    for doc_type, count in sorted_docs[:20]:
        print(f"  {doc_type}: {count}")
    
    # Calculate classification improvement
    unknown_count = new_statistics['documents_by_type'].get('unknown', 0)
    classified_count = new_statistics['total_files'] - unknown_count
    classification_rate = (classified_count / new_statistics['total_files']) * 100
    
    print(f"\nClassification rate: {classification_rate:.1f}%")
    print(f"Previously: 4.4% classified")
    print(f"Improvement: {classification_rate - 4.4:.1f} percentage points")
    
    print(f"\nReclassified result saved to: {output_file}")

if __name__ == "__main__":
    main()