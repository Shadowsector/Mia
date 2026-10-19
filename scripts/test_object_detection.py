"""Test object detection from Google Drive scan results."""

import sys
import shutil
from pathlib import Path

# Fix Windows console encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.modules.google_drive.project_ledger_manager import ProjectLedgerManager, ObjectMetadata

# Load Google Drive scan result
scan_result_file = project_root / "google_drive_scan_result_reclassified.json"

print("=" * 60)
print("Testing Object Detection from Google Drive")
print("=" * 60)

if not scan_result_file.exists():
    print(f"❌ Scan result file not found: {scan_result_file}")
    sys.exit(1)

import json
with open(scan_result_file, 'r', encoding='utf-8') as f:
    scan_result = json.load(f)

# Debug: show structure
print(f"\n📊 Scan result structure:")
print(f"   Keys: {list(scan_result.keys())}")
if 'folder_structure' in scan_result:
    print(f"   Has folder_structure: Yes")
    root_name = scan_result['folder_structure'].get('name', 'Unknown')
    print(f"   Root folder: {root_name}")
    subfolders_count = len(scan_result['folder_structure'].get('subfolders', []))
    print(f"   Direct subfolders: {subfolders_count}")
if 'folders' in scan_result:
    folders_count = len(scan_result['folders'])
    print(f"   Has folders dict: Yes ({folders_count} folders)")

# Initialize ledger manager
data_dir = project_root / "data"
manager = ProjectLedgerManager(data_dir)

print(f"\n📂 Scan result loaded: {scan_result_file}")
scan_metadata = scan_result.get('scan_metadata', {})
print(f"   Scan timestamp: {scan_metadata.get('scan_timestamp', 'Unknown')}")
print(f"   Total folders scanned: {scan_metadata.get('total_folders_scanned', 0)}")
print(f"   Total files analyzed: {scan_metadata.get('total_files_analyzed', 0)}")

# Clear existing ledgers for fresh test
print(f"\n🧹 Clearing existing ledgers for fresh test...")
existing_ledgers = manager.get_all_ledgers()
for ledger_name in list(existing_ledgers.keys()):
    ledger_path = Path(existing_ledgers[ledger_name]['path'])
    if ledger_path.exists():
        import shutil
        shutil.rmtree(ledger_path, ignore_errors=True)
        print(f"   Removed: {ledger_name}")

# Reset index
manager.ledgers_index = {}
manager._save_index()

# Detect construction objects
print("\n🔍 Detecting construction objects...")
detected_objects = manager.detect_object_folders(scan_result)

print(f"\n✅ Detected {len(detected_objects)} construction objects:\n")

for i, obj in enumerate(detected_objects, 1):
    print(f"{i}. {obj['ledger_name']}")
    print(f"   Folder: {obj['folder_name']}")
    print(f"   Path: {obj['folder_path']}")
    print(f"   Customer: {obj['customer'] or 'Not detected'}")
    print(f"   Folder ID: {obj['folder_id']}")
    print()

# Create ledgers for detected objects
print("=" * 60)
print("Creating Project Ledgers")
print("=" * 60)

# Debug: show all folder candidates at depth 2-3
print("\n🔍 Debug: Showing folder candidates at depth 2-3...")
debug_count = 0

def debug_extract_folders(node, path_prefix="", depth=0):
    global debug_count
    current_name = node.get('name', '')
    current_path = f"{path_prefix}/{current_name}" if path_prefix else current_name
    path_depth = len(current_path.split('/'))
    
    if 2 <= path_depth <= 3 and current_name != '5_Стройка':
        if debug_count < 50:  # Show first 50 instead of 20
            print(f"   {debug_count+1}. [{path_depth}] {current_name} - {current_path}")
            debug_count += 1
    
    for subfolder in node.get('subfolders', []):
        debug_extract_folders(subfolder, current_path, depth+1)

debug_extract_folders(scan_result['folder_structure'])
print(f"   Total candidates shown: {debug_count}")

print("\n--- Proceeding with actual detection ---\n")

created_count = 0
for obj in detected_objects:  # Create ledgers for all detected objects
    metadata = ObjectMetadata(
        ledger_name=obj['ledger_name'],
        address=obj['folder_path'],
        customer=obj['customer'] or 'Unknown',
        google_drive_folder_id=obj['folder_id']
    )
    
    ledger_path = manager.create_object_ledger(metadata)
    print(f"✅ Created ledger: {obj['ledger_name']}")
    print(f"   Path: {ledger_path}")
    created_count += 1

print(f"\n📊 Summary:")
print(f"   Detected objects: {len(detected_objects)}")
print(f"   Created ledgers: {created_count}")
print(f"   Total ledgers in index: {len(manager.get_all_ledgers())}")

print("\n💡 All ledgers saved to:", manager.ledgers_dir)
print("📄 Ledger index saved to:", manager.ledgers_index_file)
