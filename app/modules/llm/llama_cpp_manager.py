"""Llama.cpp Manager - Migration from Ollama to llama.cpp - RFC v1.9"""

# -*- coding: utf-8 -*-

import subprocess
import time
import threading
import requests  # Changed from httpx to requests
from typing import Optional, Dict, Any, List
from pathlib import Path
import sys

# Add mia to path for persona import
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class LlamaCppManager:
    """
    Manager for llama.cpp server
    More lightweight and faster than Ollama for RTX 5060 16GB
    """
    
    def __init__(self, exe_path: str = None, base_url: str = None):
        """
        Initialize llama.cpp manager
        
        Args:
            exe_path: Path to llama-server.exe or None to use default locations
            base_url: Base URL for llama.cpp server (default: http://localhost:8080)
        """
        self.exe_path = exe_path or self._find_llama_server()
        self.base_url = base_url or "http://localhost:8080"
        self.process: Optional[subprocess.Popen] = None
        self.models = []
    
    def _find_llama_server(self) -> Optional[str]:
        """Find llama-server.exe in common locations"""
        possible_paths = [
            r"C:\llama.cpp\llama-server.exe",
            r"C:\llama-cpp\llama-server.exe",
            r"C:\llama-cpp-windows-x64\llama-server.exe",
            "./llama-server.exe",
        ]
        
        for path in possible_paths:
            if Path(path).exists():
                return path
        
        return None
    
    def start_server(
        self,
        model_path: str,
        port: int = 8080,
        n_gpu_layers: int = 35,  # For RTX 5060 16GB
        context_size: int = 8192,
        n_threads: int = 8,
        embeddings: bool = False
    ) -> bool:
        """
        Start llama.cpp server
        
        Args:
            model_path: Path to .gguf model file
            port: Server port
            n_gpu_layers: Number of layers to offload to GPU
            context_size: Context window size
            n_threads: Number of CPU threads
            embeddings: If True, run as a dedicated embedding server (--embedding)
        """
        if self.process:
            print("llama.cpp server already running")
            return True
        
        if not self.exe_path:
            print("ERROR: llama-server.exe not found")
            print("Download from: https://github.com/ggerganov/llama.cpp/releases")
            return False
        
        if not Path(model_path).exists():
            print(f"ERROR: Model not found: {model_path}")
            return False
        
        try:
            cmd = [
                self.exe_path,
                "-m", model_path,
                "--port", str(port),
                "--n-gpu-layers", str(n_gpu_layers),
                "--ctx-size", str(context_size),
                "--threads", str(n_threads),
                "--host", "0.0.0.0"
            ]

            if embeddings:
                cmd.append("--embedding")
            
            print(f"Starting llama.cpp with command: {' '.join(cmd)}")
            
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
                # REMOVED: creationflags=subprocess.CREATE_NO_WINDOW for debugging
            )
            
            print(f"llama.cpp server started with PID: {self.process.pid}")
            
            # Read stderr to see any errors
            stderr_thread = threading.Thread(target=self._read_stderr, daemon=True)
            stderr_thread.start()
            
            # Wait for server to be ready - increase timeout for 14B model
            print("Waiting for model to load (this may take 60-90 seconds for 14B model)...")
            for i in range(120):  # 120 seconds max for 14B model
                time.sleep(1)
                if self.check_connection():
                    print("llama.cpp server is ready")
                    return True
                if i % 10 == 0:
                    print(f"Loading model... {i}s")
            
            print("WARNING: Server started but not responding after 120s")
            return True
            
        except Exception as e:
            print(f"ERROR: Failed to start llama.cpp server: {e}")
            return False
    
    def stop_server(self) -> bool:
        """Stop llama.cpp server"""
        if not self.process:
            return True
        
        try:
            self.process.terminate()
            self.process.wait(timeout=5)
            print("llama.cpp server stopped")
            self.process = None
            return True
        except subprocess.TimeoutExpired:
            self.process.kill()
            print("llama.cpp server killed")
            self.process = None
            return True
        except Exception as e:
            print(f"ERROR: Failed to stop server: {e}")
            return False
    
    def _read_stderr(self):
        """Read stderr from llama-server process"""
        try:
            if self.process and self.process.stderr:
                for line in iter(self.process.stderr.readline, b''):
                    if line:
                        print(f"llama-server stderr: {line.decode('utf-8', errors='ignore').strip()}")
        except:
            pass
    
    def check_connection(self) -> bool:
        """Check if server is responding"""
        try:
            # Try health endpoint first
            response = requests.get(f"{self.base_url}/health", timeout=2)
            if response.status_code == 200:
                return True
        except:
            pass
        
        # If health fails, try props endpoint
        try:
            response = requests.get(f"{self.base_url}/props", timeout=2)
            if response.status_code == 200:
                return True
        except:
            pass
        
        return False
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about loaded model"""
        try:
            response = requests.get(f"{self.base_url}/props", timeout=5)
            if response.status_code == 200:
                return response.json()
        except:
            pass
        return {}
    
    def generate(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.9,
        top_k: int = 40
    ) -> str:
        """
        Generate text using llama.cpp server
        
        Args:
            prompt: Input prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            top_p: Nucleus sampling parameter
            top_k: Top-k sampling parameter
        """
        try:
            # First, try to clear any existing slots
            try:
                clear_response = requests.post(f"{self.base_url}/slots/0/clear", timeout=5)
                print(f"Cleared slot 0: {clear_response.status_code}")
            except:
                print("Failed to clear slot (may not exist)")
            
            payload = {
                "prompt": prompt,
                "n_predict": max_tokens,
                "temperature": temperature,
                "top_p": top_p,
                "top_k": top_k,
                "stream": False,
                "repeat_penalty": 1.0
            }
            
            print(f"Sending request to {self.base_url}/completion")
            print(f"Payload: {payload}")
            
            response = requests.post(
                f"{self.base_url}/completion",
                json=payload,
                timeout=300  # Increased from 120 to 300 seconds for large files
            )
            
            print(f"Response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                content = result.get("content", "")
                # Fix UTF-8 encoding issue
                if isinstance(content, str):
                    # Sometimes content is already UTF-8 but may have encoding issues
                    try:
                        # Try to encode and decode to fix any encoding issues
                        content = content.encode('utf-8', errors='ignore').decode('utf-8')
                    except:
                        pass
                print(f"Generated content: {content[:100]}...")
                return content
            else:
                print(f"ERROR: Generation failed with status {response.status_code}")
                print(f"Response: {response.text}")
                return ""
                
        except Exception as e:
            print(f"ERROR: Generation failed: {e}")
            import traceback
            traceback.print_exc()
            return ""
    
    def generate_stream(self, prompt: str, **kwargs):
        """
        Generate text with streaming
        Yields chunks as they are generated
        """
        try:
            payload = {
                "prompt": prompt,
                "n_predict": kwargs.get("max_tokens", 512),
                "temperature": kwargs.get("temperature", 0.7),
                "top_p": kwargs.get("top_p", 0.9),
                "top_k": kwargs.get("top_k", 40),
                "stream": True
            }
            
            response = requests.post(
                f"{self.base_url}/completion",
                json=payload,
                stream=True,
                timeout=120
            )
            
            for line in response.iter_lines():
                if line:
                    try:
                        import json
                        data = json.loads(line.decode('utf-8'))
                        if "content" in data:
                            yield data["content"]
                    except:
                        pass
                            
        except Exception as e:
            print(f"ERROR: Stream generation failed: {e}")
            yield from []


# Recommended models for RTX 5060 16GB
RECOMMENDED_MODELS = {
    "qwen2.5-14b-instruct-q4": {
        "url": "https://huggingface.co/Qwen/Qwen2.5-14B-Instruct-GGUF/resolve/main/qwen2.5-14b-instruct-q4_k_m.gguf",
        "description": "14B parameters, 4-bit quantization, good for coding and reasoning"
    },
    "mistral-7b-instruct-q4": {
        "url": "https://huggingface.co/mistralai/Mistral-7B-Instruct-v0.3-GGUF/resolve/main/mistral-7b-instruct-v0.3.Q4_K_M.gguf",
        "description": "7B parameters, 4-bit quantization, good for general tasks"
    },
    "llama-3.1-8b-instruct-q4": {
        "url": "https://huggingface.co/lmstudio-community/Meta-Llama-3.1-8B-Instruct-GGUF/resolve/main/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf",
        "description": "8B parameters, 4-bit quantization, good all-rounder"
    }
}


def download_model(model_name: str, output_dir: str = "./models") -> str:
    """
    Download model from HuggingFace
    
    Args:
        model_name: Key from RECOMMENDED_MODELS
        output_dir: Directory to save model
    
    Returns:
        Path to downloaded model
    """
    if model_name not in RECOMMENDED_MODELS:
        raise ValueError(f"Unknown model: {model_name}")
    
    model_info = RECOMMENDED_MODELS[model_name]
    url = model_info["url"]
    
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    filename = url.split("/")[-1]
    model_path = output_path / filename
    
    if model_path.exists():
        print(f"Model already exists: {model_path}")
        return str(model_path)
    
    print(f"Downloading {model_name} from {url}")
    print(f"Saving to: {model_path}")
    
    try:
        import requests
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        block_size = 8192
        
        with open(model_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=block_size):
                f.write(chunk)
        
        print(f"Download complete: {model_path}")
        return str(model_path)
        
    except Exception as e:
        print(f"ERROR: Download failed: {e}")
        if model_path.exists():
            model_path.unlink()
        raise
