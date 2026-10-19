"""Test document parsers on sample files from Google Drive scan"""

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

from app.modules.document_parser import DocumentParserFactory, parse_document, extract_text

def find_sample_files(scan_result_file: str, max_per_type: int = 3) -> dict:
    """Find sample files of each type from scan result"""
    with open(scan_result_file, 'r', encoding='utf-8') as f:
        scan_result = json.load(f)
    
    sample_files = {
        'pdf': [],
        'docx': [],
        'xlsx': [],
        'images': [],
        'text': [],
        'other': []
    }
    
    def collect_files(folder):
        for file in folder.get('files', []):
            filename = file['name'].lower()
            ext = Path(filename).suffix.lower()
            
            if ext == '.pdf' and len(sample_files['pdf']) < max_per_type:
                sample_files['pdf'].append(file)
            elif ext in ['.docx', '.doc'] and len(sample_files['docx']) < max_per_type:
                sample_files['docx'].append(file)
            elif ext in ['.xlsx', '.xls'] and len(sample_files['xlsx']) < max_per_type:
                sample_files['xlsx'].append(file)
            elif ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff'] and len(sample_files['images']) < max_per_type:
                sample_files['images'].append(file)
            elif ext in ['.txt', '.csv', '.json', '.xml', '.log', '.md'] and len(sample_files['text']) < max_per_type:
                sample_files['text'].append(file)
        
        for subfolder in folder.get('subfolders', []):
            collect_files(subfolder)
    
    collect_files(scan_result['folder_structure'])
    
    return sample_files

def test_parser_availability():
    """Test which parsers are available"""
    print("Testing parser availability...")
    print("=" * 60)
    
    factory = DocumentParserFactory()
    
    for parser in factory.parsers:
        print(f"\n{parser.parser_name.upper()} Parser:")
        print(f"  Supported extensions: {', '.join(parser.supported_extensions)}")
        
        if parser.parser_name == 'pdf':
            print(f"  PyMuPDF available: {parser.pymupdf_available}")
        elif parser.parser_name == 'word':
            print(f"  python-docx available: {parser.docx_available}")
        elif parser.parser_name == 'excel':
            print(f"  openpyxl available: {parser.openpyxl_available}")
        elif parser.parser_name == 'image':
            print(f"  Tesseract OCR available: {parser.tesseract_available}")
        elif parser.parser_name == 'text':
            print(f"  Always available")

def test_parsing_on_sample_files():
    """Test parsing on sample files from Google Drive"""
    print("\n\nTesting parsing on sample files from Google Drive...")
    print("=" * 60)
    
    scan_result_file = Path('google_drive_scan_result_reclassified.json')
    if not scan_result_file.exists():
        print(f"Error: {scan_result_file} not found")
        return
    
    sample_files = find_sample_files(str(scan_result_file), max_per_type=2)
    
    print(f"\nFound sample files:")
    for file_type, files in sample_files.items():
        print(f"  {file_type}: {len(files)} files")
    
    factory = DocumentParserFactory()
    
    # Test PDF parsing
    if sample_files['pdf']:
        print(f"\n\nTesting PDF parsing...")
        for file in sample_files['pdf']:
            print(f"\nFile: {file['name']}")
            print(f"  ID: {file['id']}")
            print(f"  Size: {file['size']} bytes")
            print(f"  Note: File is on Google Drive, not local")
            print(f"  Parser would handle: PDF with PyMuPDF")
    
    # Test Word parsing
    if sample_files['docx']:
        print(f"\n\nTesting Word parsing...")
        for file in sample_files['docx']:
            print(f"\nFile: {file['name']}")
            print(f"  ID: {file['id']}")
            print(f"  Size: {file['size']} bytes")
            print(f"  Note: File is on Google Drive, not local")
            print(f"  Parser would handle: Word with python-docx")
    
    # Test Excel parsing
    if sample_files['xlsx']:
        print(f"\n\nTesting Excel parsing...")
        for file in sample_files['xlsx']:
            print(f"\nFile: {file['name']}")
            print(f"  ID: {file['id']}")
            print(f"  Size: {file['size']} bytes")
            print(f"  Note: File is on Google Drive, not local")
            print(f"  Parser would handle: Excel with openpyxl")
    
    # Test Image parsing
    if sample_files['images']:
        print(f"\n\nTesting Image parsing...")
        for file in sample_files['images']:
            print(f"\nFile: {file['name']}")
            print(f"  ID: {file['id']}")
            print(f"  Size: {file['size']} bytes")
            print(f"  Note: File is on Google Drive, not local")
            print(f"  Parser would handle: Image with Tesseract OCR (if available)")
    
    # Test Text parsing
    if sample_files['text']:
        print(f"\n\nTesting Text parsing...")
        for file in sample_files['text']:
            print(f"\nFile: {file['name']}")
            print(f"  ID: {file['id']}")
            print(f"  Size: {file['size']} bytes")
            print(f"  Note: File is on Google Drive, not local")
            print(f"  Parser would handle: Text with built-in parser")

def create_test_files():
    """Create simple test files to verify parsers work"""
    print("\n\nCreating test files to verify parsers...")
    print("=" * 60)
    
    test_dir = Path('test_parsers')
    test_dir.mkdir(exist_ok=True)
    
    # Create test text file
    test_text = test_dir / 'test_document.txt'
    with open(test_text, 'w', encoding='utf-8') as f:
        f.write("Это тестовый документ для проверки парсера.\n")
        f.write("Вторая строка текста.\n")
        f.write("Третья строка текста.")
    
    print(f"Created test file: {test_text}")
    
    # Test text parser
    factory = DocumentParserFactory()
    result = factory.parse_document(test_text)
    
    print(f"\nParsing result for {test_text.name}:")
    print(f"  Success: {result['success']}")
    print(f"  Text length: {len(result['text'])} characters")
    print(f"  Line count: {result['metadata']['line_count']}")
    print(f"  First 100 chars: {result['text'][:100]}")
    
    # Clean up
    test_text.unlink()
    test_dir.rmdir()
    print(f"\nCleaned up test files")

def main():
    print("Document Parser Test Suite")
    print("=" * 60)
    
    # Test parser availability
    test_parser_availability()
    
    # Test on sample files from Google Drive
    test_parsing_on_sample_files()
    
    # Create and test with local files
    create_test_files()
    
    print("\n\n" + "=" * 60)
    print("Test suite completed!")
    print("=" * 60)

if __name__ == "__main__":
    main()