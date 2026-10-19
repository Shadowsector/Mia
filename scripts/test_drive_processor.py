"""Test document processor with Google Drive download"""

import sys
from pathlib import Path

# Fix Windows console encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.modules.google_drive.document_processor import test_document_processor

if __name__ == "__main__":
    print("Testing Document Processor with Google Drive")
    print("=" * 60)
    test_document_processor()