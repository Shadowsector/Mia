"""Script to find specific Google Drive folder by name"""

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
    
    scanner = OAuthDriveScanner(credentials_path, "")
    
    print("Starting OAuth authentication...")
    print("A browser window will open. Please authorize the application.")
    
    if not scanner.authenticate():
        print("Error: OAuth authentication failed")
        return
    
    print("OAuth authentication successful!")
    
    # Search for specific folder by name
    target_name = "5_Стройка"
    print(f"\nSearching for folder: {target_name}")
    
    # Get all folders with pagination
    all_folders = []
    page_token = None
    
    while True:
        try:
            if page_token:
                results = scanner.service.files().list(
                    q=f"mimeType='application/vnd.google-apps.folder' and name='{target_name}'",
                    fields='nextPageToken,files(id,name)',
                    pageSize=100,
                    pageToken=page_token
                ).execute()
            else:
                results = scanner.service.files().list(
                    q=f"mimeType='application/vnd.google-apps.folder' and name='{target_name}'",
                    fields='nextPageToken,files(id,name)',
                    pageSize=100
                ).execute()
            
            folders = results.get('files', [])
            all_folders.extend(folders)
            
            page_token = results.get('nextPageToken')
            if not page_token:
                break
                
        except Exception as e:
            print(f"Error searching folders: {e}")
            break
    
    print(f"Found {len(all_folders)} folders matching '{target_name}'")
    
    if all_folders:
        for i, folder in enumerate(all_folders):
            print(f"  {i+1}. {folder['name']} (ID: {folder['id']})")
        
        if len(all_folders) == 1:
            selected_folder = all_folders[0]
            print(f"\nSelected folder: {selected_folder['name']}")
            print(f"Folder ID: {selected_folder['id']}")
            print(f"\nAdd this to .env:")
            print(f"GOOGLE_DRIVE_TARGET_FOLDER_ID={selected_folder['id']}")
            
            # Update .env file
            env_path = Path('.env')
            if env_path.exists():
                with open(env_path, 'r', encoding='utf-8') as f:
                    env_content = f.read()
                
                # Replace or add the folder ID
                if 'GOOGLE_DRIVE_TARGET_FOLDER_ID=' in env_content:
                    env_content = env_content.replace(
                        f'GOOGLE_DRIVE_TARGET_FOLDER_ID={os.getenv("GOOGLE_DRIVE_TARGET_FOLDER_ID", "")}',
                        f'GOOGLE_DRIVE_TARGET_FOLDER_ID={selected_folder["id"]}'
                    )
                else:
                    env_content += f'\nGOOGLE_DRIVE_TARGET_FOLDER_ID={selected_folder["id"]}'
                
                with open(env_path, 'w', encoding='utf-8') as f:
                    f.write(env_content)
                
                print(f"Updated .env file with folder ID")
        else:
            print("\nMultiple folders found. Please specify which one to use.")
    else:
        print(f"No folder found with name '{target_name}'")
        print("Getting all folders to help you find the right one...")
        
        # Get ALL folders with pagination
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
        
        # Save to file with UTF-8 encoding
        with open('all_folders.txt', 'w', encoding='utf-8') as f:
            f.write(f"Total folders: {len(all_folders)}\n\n")
            for i, folder in enumerate(all_folders):
                f.write(f"{i+1}. {folder['name']} (ID: {folder['id']})\n")
        
        print("All folders saved to all_folders.txt")
        print("Please check the file and tell me which folder ID to use.")

if __name__ == "__main__":
    main()