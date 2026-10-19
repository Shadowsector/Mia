"""Manual installation script for manually downloaded llama.cpp"""

import os
import zipfile
from pathlib import Path
import shutil
import urllib.request
import json


def extract_downloaded_llama():
    """Extract manually downloaded llama.cpp from desktop"""
    
    print("=" * 60)
    print("Extracting llama.cpp from Desktop")
    print("=" * 60)
    
    # Desktop path
    desktop = Path.home() / "Desktop"
    
    # Find the downloaded zip
    zip_files = list(desktop.glob("llama-b*.zip"))
    
    if not zip_files:
        print("ERROR: llama.cpp zip file not found on Desktop")
        print("Looking for files matching: llama-b*.zip")
        print(f"Desktop path: {desktop}")
        return False
    
    zip_file = zip_files[0]
    print(f"Found: {zip_file}")
    
    # Extract to C:\llama.cpp
    install_dir = Path("C:/llama.cpp")
    install_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Extracting to: {install_dir}")
    
    try:
        with zipfile.ZipFile(zip_file, 'r') as zip_ref:
            zip_ref.extractall(install_dir)
        print("[OK] Extracted successfully")
    except Exception as e:
        print(f"ERROR: Failed to extract: {e}")
        return False
    
    # Find llama-server.exe
    llama_server = None
    for root, dirs, files in os.walk(install_dir):
        if "llama-server.exe" in files:
            llama_server = Path(root) / "llama-server.exe"
            break
    
    if llama_server:
        print(f"Found llama-server.exe: {llama_server}")
        
        # Copy to root (if not already there)
        target_path = install_dir / "llama-server.exe"
        
        if llama_server == target_path:
            print(f"Already in correct location: {target_path}")
        else:
            shutil.copy(llama_server, target_path)
            print(f"Copied to: {target_path}")
        
        return True
    else:
        print("ERROR: llama-server.exe not found")
        return False


def download_qwen_model():
    """Download Qwen 2.5 14B Instruct model"""
    
    print("\n" + "=" * 60)
    print("Downloading Qwen 2.5 14B Instruct Model")
    print("=" * 60)
    
    # Model URL - correct filename with uppercase
    model_url = "https://huggingface.co/bartowski/Qwen2.5-14B-Instruct-GGUF/resolve/main/Qwen2.5-14B-Instruct-Q4_K_M.gguf"
    
    # Model directory
    models_dir = Path("C:/models")
    model_path = models_dir / "Qwen2.5-14B-Instruct-Q4_K_M.gguf"
    
    if model_path.exists():
        print(f"Model already exists: {model_path}")
        return True
    
    print(f"Downloading: {model_url}")
    print(f"Saving to: {model_path}")
    print("This may take 10-30 minutes (around 9 GB)...")
    
    models_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        urllib.request.urlretrieve(model_url, model_path)
        print(f"[OK] Model downloaded: {model_path}")
        return True
    except Exception as e:
        print(f"ERROR: Failed to download: {e}")
        return False


def update_config():
    """Update configuration file"""
    
    print("\n" + "=" * 60)
    print("Updating Configuration")
    print("=" * 60)
    
    config_file = Path("mia_config.json")
    
    config = {
        "llama_cpp_path": "C:\\llama.cpp\\llama-server.exe",
        "model_path": "C:\\models\\Qwen2.5-14B-Instruct-Q4_K_M.gguf",
        "llama_port": 8080,
        "telegram_enabled": False,
        "n_gpu_layers": 35,
        "context_size": 8192,
        "n_threads": 8
    }
    
    try:
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
        print(f"[OK] Configuration updated: {config_file}")
        return True
    except Exception as e:
        print(f"ERROR: Failed to update config: {e}")
        return False


def main():
    """Main installation function"""
    
    print("\n" + "=" * 60)
    print("Mia PM OS - Manual Installation")
    print("=" * 60)
    
    # Step 1: Extract llama.cpp
    print("\nStep 1: Extracting llama.cpp from Desktop...")
    if not extract_downloaded_llama():
        print("[ERROR] Failed to extract llama.cpp")
        return
    
    # Step 2: Download model
    print("\nStep 2: Downloading Qwen 2.5 14B model...")
    if not download_qwen_model():
        print("[ERROR] Failed to download model")
        print("\nYou can download manually from:")
        print("https://huggingface.co/Qwen/Qwen2.5-14B-Instruct-GGUF")
        print("Download: qwen2.5-14b-instruct-q4_k_m.gguf")
        print("Save to: C:\\models\\")
        return
    
    # Step 3: Update config
    print("\nStep 3: Updating configuration...")
    if not update_config():
        print("[ERROR] Failed to update config")
        return
    
    print("\n" + "=" * 60)
    print("[OK] Installation Complete!")
    print("=" * 60)
    print("\nYou can now run Mia PM OS:")
    print("python gui\\mia_gui_redesigned.py")
    print("\nOr create a desktop shortcut:")
    print("create_shortcut.bat")


if __name__ == "__main__":
    main()
