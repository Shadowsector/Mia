"""Test direct access to target folder"""

import sys
import os
from pathlib import Path

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

def main():
    credentials_path = os.getenv('GOOGLE_DRIVE_OAUTH_CREDENTIALS_PATH', 'config/oauth_credentials.json')
    target_folder_id = '1LXFAfJ7K7uwNfSaTGxMFf2hF9osn_WBv'  # From the screenshot
    
    scanner = OAuthDriveScanner(credentials_path, target_folder_id)
    
    print("Starting OAuth authentication...")
    print("A browser window will open. Please authorize the application.")
    
    if not scanner.authenticate():
        print("Error: OAuth authentication failed")
        return
    
    print("OAuth authentication successful!")
    
    # Try to access target folder
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
        
        print(f"\nFolder is accessible! Update .env with:")
        print(f"GOOGLE_DRIVE_TARGET_FOLDER_ID={target_folder_id}")
    else:
        print("Error: Could not access target folder")

if __name__ == "__main__":
    main()