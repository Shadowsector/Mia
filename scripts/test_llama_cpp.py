"""Simple test for llama.cpp generation"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.modules.llm.llama_cpp_manager import LlamaCppManager

print("=" * 60)
print("Testing llama.cpp generation")
print("=" * 60)

llama = LlamaCppManager()

print(f"Base URL: {llama.base_url}")
print(f"Checking connection...")

if llama.check_connection():
    print("✅ Connected to llama.cpp")
    
    print("\nGenerating response...")
    response = llama.generate(
        prompt="Привет, как дела?",
        max_tokens=100,
        temperature=0.7
    )
    
    print(f"\nResponse: {response}")
else:
    print("❌ Not connected to llama.cpp")
    print("Make sure llama-server.exe is running on port 8080")
