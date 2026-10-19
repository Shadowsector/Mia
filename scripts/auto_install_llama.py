"""Automatic installation script for llama.cpp"""

import os
import sys
import subprocess
import urllib.request
import zipfile
from pathlib import Path
import shutil


def download_file(url: str, dest_path: Path):
    """Download file from URL"""
    print(f"Downloading: {url}")
    print(f"Saving to: {dest_path}")
    
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        urllib.request.urlretrieve(url, dest_path)
        print(f"Downloaded: {dest_path}")
        return True
    except Exception as e:
        print(f"Error downloading: {e}")
        return False


def extract_zip(zip_path: Path, extract_to: Path):
    """Extract zip file"""
    print(f"Extracting: {zip_path}")
    print(f"To: {extract_to}")
    
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)
        print(f"Extracted successfully")
        return True
    except Exception as e:
        print(f"Error extracting: {e}")
        return False


def install_llama_cpp():
    """Install llama.cpp automatically"""
    
    print("=" * 60)
    print("Automatic Installation of llama.cpp")
    print("=" * 60)
    
    # llama.cpp release URL (Windows x64) - use latest stable release
    llama_url = "https://github.com/ggerganov/llama.cpp/releases/download/b4534/llama-b4534-bin-win-cuda-cu12.2.0-x64.zip"
    
    # Installation directory
    install_dir = Path("C:/llama.cpp")
    temp_zip = Path("C:/temp/llama.zip")
    
    # Create temp directory
    temp_zip.parent.mkdir(parents=True, exist_ok=True)
    
    # Download
    if not download_file(llama_url, temp_zip):
        print("Failed to download llama.cpp")
        print("Please download manually from: https://github.com/ggerganov/llama.cpp/releases")
        print("Extract to C:/llama.cpp")
        return False
    
    # Extract
    if not extract_zip(temp_zip, install_dir):
        print("Failed to extract llama.cpp")
        return False
    
    # Clean up
    temp_zip.unlink()
    
    # Find llama-server.exe
    llama_server = None
    for root, dirs, files in os.walk(install_dir):
        if "llama-server.exe" in files:
            llama_server = Path(root) / "llama-server.exe"
            break
    
    if llama_server:
        print(f"llama-server.exe found at: {llama_server}")
        
        # Copy to root of install dir for easier access
        target_path = install_dir / "llama-server.exe"
        shutil.copy(llama_server, target_path)
        print(f"Copied to: {target_path}")
        
        return True
    else:
        print("llama-server.exe not found in extracted files")
        return False


def download_qwen_model():
    """Download Qwen 2.5 14B Instruct model"""
    
    print("\n" + "=" * 60)
    print("Downloading Qwen 2.5 14B Instruct Model")
    print("=" * 60)
    
    # Model URL
    model_url = "https://huggingface.co/Qwen/Qwen2.5-14B-Instruct-GGUF/resolve/main/qwen2.5-14b-instruct-q4_k_m.gguf"
    
    # Model directory
    models_dir = Path("C:/models")
    model_path = models_dir / "qwen2.5-14b-instruct-q4_k_m.gguf"
    
    if model_path.exists():
        print(f"Model already exists: {model_path}")
        return True
    
    # Download
    if not download_file(model_url, model_path):
        print("Failed to download model")
        return False
    
    print(f"Model downloaded: {model_path}")
    return True


def main():
    """Main installation function"""
    
    print("\n" + "=" * 60)
    print("Mia PM OS - Automatic Setup")
    print("=" * 60)
    
    # Install llama.cpp
    print("\nStep 1: Installing llama.cpp...")
    if install_llama_cpp():
        print("[OK] llama.cpp installed successfully")
    else:
        print("[ERROR] Failed to install llama.cpp")
        return
    
    # Download model
    print("\nStep 2: Downloading Qwen 2.5 14B model...")
    if download_qwen_model():
        print("[OK] Model downloaded successfully")
    else:
        print("[ERROR] Failed to download model")
        return
    
    # Update config
    print("\nStep 3: Updating configuration...")
    config_file = Path("mia_config.json")
    
    config = {
        "llama_cpp_path": "C:\\llama.cpp\\llama-server.exe",
        "model_path": "C:\\models\\qwen2.5-14b-instruct-q4_k_m.gguf",
        "llama_port": 8080,
        "telegram_enabled": False,
        "n_gpu_layers": 35,
        "context_size": 8192,
        "n_threads": 8
    }
    
    import json
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)
    
    print(f"[OK] Configuration updated: {config_file}")
    
    print("\n" + "=" * 60)
    print("[OK] Installation Complete!")
    print("=" * 60)
    print("\nYou can now run Mia PM OS from the desktop shortcut")


if __name__ == "__main__":
    main()
