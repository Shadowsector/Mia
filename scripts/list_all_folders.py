"""Script to list all Google Drive folders"""

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
    target_folder_id = os.getenv('GOOGLE_DRIVE_TARGET_FOLDER_ID', '1LXFAfJ7K7uwNfSaTGxMFf2hF9osn_WBv')
    
    scanner = OAuthDriveScanner(credentials_path, target_folder_id)
    
    print("Starting OAuth authentication...")
    print("A browser window will open. Please authorize the application.")
    
    if not scanner.authenticate():
        print("Error: OAuth authentication failed")
        return
    
    print("OAuth authentication successful!")
    
    print("Getting all folders from My Drive to help you find the right one...")
    
    # Get ALL folders from My Drive with pagination
    all_folders = []
    page_token = None
    
    while True:
        try:
            if page_token:
                results = scanner.service.files().list(
                    q="mimeType='application/vnd.google-apps.folder'",
                    fields='nextPageToken,files(id,name)',
                    pageSize=100,
                    pageToken=page_token
                ).execute()
            else:
                results = scanner.service.files().list(
                    q="mimeType='application/vnd.google-apps.folder'",
                    fields='nextPageToken,files(id,name)',
                    pageSize=100
                ).execute()
            
            folders = results.get('files', [])
            all_folders.extend(folders)
            print(f"Collected {len(all_folders)} folders so far...")
            
            page_token = results.get('nextPageToken')
            if not page_token:
                break
                
        except Exception as e:
            print(f"Error searching folders: {e}")
            break
    
    print(f"Total folders found: {len(all_folders)}")
    
    # Also try Shared with me
    print("\nChecking Shared with me folders...")
    shared_folders = []
    page_token = None
    
    while True:
        try:
            if page_token:
                results = scanner.service.files().list(
                    q="mimeType='application/vnd.google-apps.folder' and sharedWithMe=true",
                    fields='nextPageToken,files(id,name)',
                    pageSize=100,
                    pageToken=page_token
                ).execute()
            else:
                results = scanner.service.files().list(
                    q="mimeType='application/vnd.google-apps.folder' and sharedWithMe=true",
                    fields='nextPageToken,files(id,name)',
                    pageSize=100
                ).execute()
            
            folders = results.get('files', [])
            shared_folders.extend(folders)
            print(f"Collected {len(shared_folders)} shared folders so far...")
            
            page_token = results.get('nextPageToken')
            if not page_token:
                break
                
        except Exception as e:
            print(f"Error searching shared folders: {e}")
            break
    
    print(f"Total shared folders found: {len(shared_folders)}")
    
    # Also try Shared Drives (Team Drives)
    print("\nChecking Shared Drives...")
    try:
        drives = scanner.service.drives().list().execute()
        shared_drives = drives.get('drives', [])
        print(f"Found {len(shared_drives)} shared drives")
        
        if shared_drives:
            for drive in shared_drives:
                print(f"  Drive: {drive['name']} (ID: {drive['id']})")
    except Exception as e:
        print(f"Error checking shared drives: {e}")
        shared_drives = []
    
    # Try to access the specific folder ID from the URL
    print(f"\nTrying to access folder ID from URL: {scanner.target_folder_id}")
    try:
        folder_info = scanner.get_folder_info(scanner.target_folder_id)
        if folder_info:
            print(f"SUCCESS! Found folder: {folder_info['name']} (ID: {folder_info['id']})")
            print(f"Update .env with: GOOGLE_DRIVE_TARGET_FOLDER_ID={folder_info['id']}")
            return
    except Exception as e:
        print(f"Could not access folder ID from URL: {e}")
    
    # Save to file with UTF-8 encoding
    with open('all_folders.txt', 'w', encoding='utf-8') as f:
        f.write(f"Total folders: {len(all_folders)}\n\n")
        for i, folder in enumerate(all_folders):
            f.write(f"{i+1}. {folder['name']} (ID: {folder['id']})\n")
        
        f.write(f"\n\nShared folders: {len(shared_folders)}\n\n")
        for i, folder in enumerate(shared_folders):
            f.write(f"{i+1}. {folder['name']} (ID: {folder['id']})\n")
        
        if shared_drives:
            f.write(f"\n\nShared drives: {len(shared_drives)}\n\n")
            for i, drive in enumerate(shared_drives):
                f.write(f"{i+1}. {drive['name']} (ID: {drive['id']})\n")
    
    print("All folders saved to all_folders.txt")
    print("Please check the file and tell me which folder ID to use.")
    print("If the folder is in a Shared Drive, please provide the Shared Drive ID and folder name.")

if __name__ == "__main__":
    main()