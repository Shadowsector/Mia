"""Modern GUI for Mia PM OS - Complete Redesign - RFC v1.9

Features:
- Auto-start llama.cpp on launch
- Normal chat interface with input/send/copy-paste
- Real-time Telegram chat
- Clean and logical interface
- Single instance enforcement
"""

# -*- coding: utf-8 -*-

import sys
import os
import socket
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, simpledialog
import threading
import time
import subprocess
from datetime import datetime
import logging
import json

# Setup logging with UTF-8 encoding
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('mia_gui.log', encoding='utf-8', errors='replace'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class SingleInstanceChecker:
    """Ensures only one instance of Mia is running at a time."""
    
    def __init__(self):
        self.host = '127.0.0.1'
        self.port = 57423
        self.socket = None
        self.lock_file = Path(__file__).parent.parent / "mia_instance.lock"
    
    def cleanup_stale_lock(self):
        """Clean up stale lock file if the port is not actually in use."""
        if not self.lock_file.exists():
            return False
        
        try:
            test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test_socket.bind((self.host, self.port))
            test_socket.close()
            logger.info("Detected stale lock file - cleaning up")
            self.lock_file.unlink()
            return True
        except socket.error:
            return False
        except Exception as e:
            logger.warning(f"Error checking stale lock: {e}")
            return False
    
    def is_already_running(self) -> bool:
        """Check if another instance is already running."""
        self.cleanup_stale_lock()
        
        try:
            test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test_socket.bind((self.host, self.port))
            test_socket.close()
            logger.info(f"Port {self.port} is available")
            return False
        except socket.error as e:
            logger.warning(f"Port {self.port} is already used: {e}")
            return True
        except Exception as e:
            logger.warning(f"Error checking instance lock: {e}")
            return False
    
    def acquire_lock(self) -> bool:
        """Acquire instance lock."""
        try:
            if self.is_already_running():
                logger.error("Instance already running")
                return False
            
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.bind((self.host, self.port))
            self.socket.listen(1)
            logger.info(f"Bound to port {self.port}")
            
            try:
                with open(self.lock_file, 'w') as f:
                    f.write(str(os.getpid()))
                logger.info(f"Created lock file with PID {os.getpid()}")
            except Exception as e:
                logger.warning(f"Could not create lock file: {e}")
            
            return True
        except Exception as e:
            logger.error(f"Failed to acquire lock: {e}")
            return False
    
    def release_lock(self):
        """Release instance lock."""
        try:
            if self.socket:
                try:
                    self.socket.close()
                except Exception as e:
                    logger.warning(f"Error closing socket: {e}")
                self.socket = None
                logger.info("Released instance lock")
            
            if self.lock_file.exists():
                try:
                    self.lock_file.unlink()
                    logger.info("Removed lock file")
                except Exception as e:
                    logger.warning(f"Error removing lock file: {e}")
        except Exception as e:
            logger.error(f"Failed to release lock: {e}")


class MiaGUI:
    """Modern GUI for Mia PM OS - Complete Redesign."""
    
    def __init__(self, root, instance_checker):
        self.root = root
        self.root.title("Mia PM OS - Construction Project Management")
        self.root.geometry("1200x800")
        self.root.minsize(1000, 700)
        
        self.instance_checker = instance_checker
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # System state
        self.llama_process = None
        self.telegram_process = None
        self.is_running = False
        
        # Configuration
        self.config = self._load_config()
        
        # Runtime Manager for system components
        try:
            from app.runtime.manager import RuntimeManager
            self.runtime_manager = RuntimeManager(project_root=str(Path(__file__).parent.parent))
        except Exception as e:
            logger.error(f"Failed to initialize RuntimeManager: {e}")
            self.runtime_manager = None
        
        # Build UI
        self.setup_style()
        self.build_ui()
        
        # Initialize components
        self.initialize_system()
        
        # Start llama.cpp
        self.start_llama_cpp()
        
        # Start refresh timer
        self.refresh_timer()
    
    def _load_config(self) -> dict:
        """Load configuration from file."""
        config_file = Path(__file__).parent.parent / "mia_config.json"
        default_config = {
            "llama_cpp_path": r"C:\llama.cpp\llama-server.exe",
            "model_path": r"C:\models\Qwen2.5-14B-Instruct-Q4_K_M.gguf",
            "llama_port": 8080,
            "telegram_enabled": False
        }
        
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    default_config.update(config)
            except Exception as e:
                logger.warning(f"Error loading config: {e}")
        
        return default_config
    
    def setup_style(self):
        """Setup modern styling."""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Custom colors
        style.configure('TFrame', background='#f5f5f5')
        style.configure('TLabel', background='#f5f5f5', font=('Segoe UI', 10))
        style.configure('TButton', font=('Segoe UI', 10, 'bold'))
        style.configure('TNotebook', background='#f5f5f5')
        style.configure('TNotebook.Tab', font=('Segoe UI', 10, 'bold'))
        
        # Header style
        style.configure('Header.TLabel', font=('Segoe UI', 18, 'bold'), 
                      background='#2c3e50', foreground='white')
        
        # Status colors
        style.configure('Success.TLabel', foreground='#27ae60', font=('Segoe UI', 10, 'bold'))
        style.configure('Warning.TLabel', foreground='#f39c12', font=('Segoe UI', 10, 'bold'))
        style.configure('Error.TLabel', foreground='#e74c3c', font=('Segoe UI', 10, 'bold'))
    
    def build_ui(self):
        """Build main UI."""
        # Header
        header = ttk.Frame(self.root, style='Header.TFrame')
        header.pack(fill='x', ipady=15)
        header.configure(style='TFrame')
        
        title = ttk.Label(header, text="Mia PM OS", style='Header.TLabel')
        title.pack(side='left', padx=20)
        
        subtitle = ttk.Label(header, text="Construction Project Management System", 
                           font=('Segoe UI', 11), background='#2c3e50', foreground='#ecf0f1')
        subtitle.pack(side='left', padx=10)
        
        # Status indicator
        self.status_var = tk.StringVar(value="System: Initializing...")
        status_label = ttk.Label(header, textvariable=self.status_var,
                               font=('Segoe UI', 10, 'bold'), background='#2c3e50', foreground='#ecf0f1')
        status_label.pack(side='right', padx=20)
        
        # Main content with sidebar and chat
        main_container = ttk.Frame(self.root)
        main_container.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Sidebar (left)
        sidebar = ttk.Frame(main_container, width=300)
        sidebar.pack(side='left', fill='y', padx=(0, 10))
        sidebar.pack_propagate(False)
        
        self.build_sidebar(sidebar)
        
        # Chat area (right)
        chat_area = ttk.Frame(main_container)
        chat_area.pack(side='right', fill='both', expand=True)
        
        self.build_chat_area(chat_area)
    
    def build_sidebar(self, parent):
        """Build sidebar with system info and controls."""
        # System status
        status_frame = ttk.LabelFrame(parent, text="System Status", padding=15)
        status_frame.pack(fill='x', pady=10)
        
        # LLM Server status
        self.llama_status_var = tk.StringVar(value="LLM: Checking...")
        llama_row = ttk.Frame(status_frame)
        llama_row.pack(fill='x', pady=2)
        ttk.Label(llama_row, textvariable=self.llama_status_var, font=('Segoe UI', 10)).pack(side='left')
        ttk.Button(llama_row, text="Start", command=self.start_llama_manual, width=8).pack(side='right')
        
        # Telegram Bot status
        self.telegram_status_var = tk.StringVar(value="Telegram: Checking...")
        telegram_row = ttk.Frame(status_frame)
        telegram_row.pack(fill='x', pady=2)
        ttk.Label(telegram_row, textvariable=self.telegram_status_var, font=('Segoe UI', 10)).pack(side='left')
        ttk.Button(telegram_row, text="Start", command=self.start_telegram_manual, width=8).pack(side='right')
        
        # Worker Pool status
        self.worker_status_var = tk.StringVar(value="Worker Pool: Checking...")
        worker_row = ttk.Frame(status_frame)
        worker_row.pack(fill='x', pady=2)
        ttk.Label(worker_row, textvariable=self.worker_status_var, font=('Segoe UI', 10)).pack(side='left')
        ttk.Button(worker_row, text="Start", command=self.start_worker_manual, width=8).pack(side='right')
        
        # Quick actions
        actions_frame = ttk.LabelFrame(parent, text="Quick Actions", padding=15)
        actions_frame.pack(fill='x', pady=10)
        
        ttk.Button(actions_frame, text="📊 Project Ledger", command=self.show_project_ledger).pack(fill='x', pady=5)
        ttk.Button(actions_frame, text="📝 Object Diary", command=self.show_object_diary).pack(fill='x', pady=5)
        ttk.Button(actions_frame, text="⏰ Alerts", command=self.show_alerts).pack(fill='x', pady=5)
        ttk.Button(actions_frame, text="📈 Health Score", command=self.show_health_score).pack(fill='x', pady=5)
        
        # Logs
        logs_frame = ttk.LabelFrame(parent, text="System Logs", padding=15)
        logs_frame.pack(fill='both', expand=True, pady=10)
        
        self.logs_text = scrolledtext.ScrolledText(logs_frame, height=20, state='disabled', font=('Consolas', 9))
        self.logs_text.pack(fill='both', expand=True)
        
        ttk.Button(logs_frame, text="Refresh Logs", command=self.refresh_logs).pack(fill='x', pady=5)
    
    def build_chat_area(self, parent):
        """Build main chat area."""
        # Chat tabs
        notebook = ttk.Notebook(parent)
        notebook.pack(fill='both', expand=True)
        
        # AI Chat tab
        ai_chat_frame = ttk.Frame(notebook)
        notebook.add(ai_chat_frame, text="💬 AI Chat")
        
        self.build_ai_chat(ai_chat_frame)
        
        # Telegram tab
        telegram_frame = ttk.Frame(notebook)
        notebook.add(telegram_frame, text="📱 Telegram")
        
        self.build_telegram_chat(telegram_frame)
        
        # Runtime Logs tab
        runtime_logs_frame = ttk.Frame(notebook)
        notebook.add(runtime_logs_frame, text="📋 Runtime Logs")
        
        self.build_runtime_logs(runtime_logs_frame)
        
        # Audit Log tab
        audit_log_frame = ttk.Frame(notebook)
        notebook.add(audit_log_frame, text="🔍 Audit Log")
        
        self.build_audit_log(audit_log_frame)
    
    def build_ai_chat(self, parent):
        """Build AI chat interface."""
        # Model info and selection
        model_frame = ttk.LabelFrame(parent, text="Model Selection", padding=15)
        model_frame.pack(fill='x', padx=10, pady=10)
        
        # Current model info
        self.current_model_info = tk.StringVar(value="Loading model info...")
        ttk.Label(model_frame, textvariable=self.current_model_info, font=('Segoe UI', 9)).pack(anchor='w', pady=2)
        
        # Model selector
        selector_frame = ttk.Frame(model_frame)
        selector_frame.pack(fill='x', pady=5)
        
        ttk.Label(selector_frame, text="Select Model:", font=('Segoe UI', 10, 'bold')).pack(side='left', padx=5)
        
        self.model_var = tk.StringVar(value="qwen2.5-14b-instruct")
        model_combo = ttk.Combobox(selector_frame, textvariable=self.model_var, state='readonly', width=35)
        model_combo['values'] = ['qwen2.5-14b-instruct', 'mistral-7b-instruct', 'llama-3.1-8b-instruct']
        model_combo.pack(side='left', padx=5)
        model_combo.bind('<<ComboboxSelected>>', self.on_model_change)
        
        # Switch model button
        self.mode_var = tk.StringVar(value="chat")
        mode_frame = ttk.Frame(selector_frame)
        mode_frame.pack(side='left', padx=5)
        
        ttk.Radiobutton(mode_frame, text="� Chat", variable=self.mode_var, value="chat", command=self.switch_mode).pack(side='left')
        ttk.Radiobutton(mode_frame, text="💻 Coder", variable=self.mode_var, value="coder", command=self.switch_mode).pack(side='left')
        
        ttk.Button(selector_frame, text="🔄 Reload", command=self.reload_model).pack(side='left', padx=5)
        
        # Chat history with copy support
        chat_frame = ttk.Frame(parent)
        chat_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        self.ai_chat_history = scrolledtext.ScrolledText(chat_frame, state='normal', font=('Segoe UI', 10))
        self.ai_chat_history.pack(fill='both', expand=True)
        
        # Make read-only by binding events
        self.ai_chat_history.bind('<Key>', lambda e: 'break')
        self.ai_chat_history.bind('<Button-3>', self.show_context_menu)
        self.ai_chat_history.bind('<Control-v>', self.paste_to_chat)  # Ctrl+V paste to chat
        
        # Copy button
        copy_btn = ttk.Button(chat_frame, text="📋 Copy", command=self.copy_chat_selection)
        copy_btn.pack(anchor='e', pady=(5, 0))
        
        # Input area
        input_frame = ttk.Frame(parent)
        input_frame.pack(fill='x', padx=10, pady=10)
        
        self.ai_input = ttk.Entry(input_frame, font=('Segoe UI', 11))
        self.ai_input.pack(side='left', fill='x', expand=True, padx=(0, 5), ipady=5)
        self.ai_input.bind('<Return>', lambda e: self.send_ai_message())
        self.ai_input.bind('<Control-v>', self.paste_from_clipboard)  # Ctrl+V paste
        
        send_btn = ttk.Button(input_frame, text="📤 Send", command=self.send_ai_message, width=15)
        send_btn.pack(side='left', padx=5)
        
        clear_btn = ttk.Button(input_frame, text="🗑️ Clear", command=self.clear_ai_chat, width=10)
        clear_btn.pack(side='left', padx=5)
    
    def build_telegram_chat(self, parent):
        """Build Telegram chat interface."""
        # Telegram status
        status_frame = ttk.Frame(parent)
        status_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Label(status_frame, textvariable=self.telegram_status_var, font=('Segoe UI', 10, 'bold')).pack(side='left')
        
        self.enable_telegram_btn = ttk.Button(status_frame, text="Enable Telegram", command=self.enable_telegram)
        self.enable_telegram_btn.pack(side='right', padx=5)
        
        # Chat history
        self.telegram_chat_history = scrolledtext.ScrolledText(parent, state='disabled', font=('Segoe UI', 10))
        self.telegram_chat_history.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Input area
        input_frame = ttk.Frame(parent)
        input_frame.pack(fill='x', padx=10, pady=10)
        
        self.telegram_input = ttk.Entry(input_frame, font=('Segoe UI', 11))
        self.telegram_input.pack(side='left', fill='x', expand=True, padx=(0, 5), ipady=5)
        self.telegram_input.bind('<Return>', lambda e: self.send_telegram_message())
        
        send_btn = ttk.Button(input_frame, text="📤 Send", command=self.send_telegram_message, width=15)
        send_btn.pack(side='left', padx=5)
    
    def build_runtime_logs(self, parent):
        """Build runtime logs interface."""
        # Log file selector
        selector_frame = ttk.Frame(parent)
        selector_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Label(selector_frame, text="Log File:", font=('Segoe UI', 10)).pack(side='left')
        
        self.log_file_var = tk.StringVar(value="mia_runtime.log")
        log_combo = ttk.Combobox(selector_frame, textvariable=self.log_file_var, width=30, state='readonly')
        log_combo['values'] = ['mia_runtime.log', 'mia_gui.log', 'llama_server.log']
        log_combo.pack(side='left', padx=5)
        
        ttk.Button(selector_frame, text="🔄 Refresh", command=self.refresh_runtime_logs).pack(side='left', padx=5)
        ttk.Button(selector_frame, text="🗑️ Clear", command=self.clear_runtime_logs).pack(side='left', padx=5)
        
        # Log display
        self.runtime_logs_text = scrolledtext.ScrolledText(parent, state='disabled', font=('Consolas', 9))
        self.runtime_logs_text.pack(fill='both', expand=True, padx=10, pady=10)
    
    def refresh_runtime_logs(self):
        """Refresh runtime logs from selected log file."""
        log_file = self.log_file_var.get()
        log_path = Path(__file__).parent.parent / log_file
        
        try:
            if log_path.exists():
                with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()
                self.runtime_logs_text.config(state='normal')
                self.runtime_logs_text.delete(1.0, 'end')
                self.runtime_logs_text.insert('end', content)
                self.runtime_logs_text.config(state='disabled')
                logger.info(f"Refreshed runtime logs from {log_file}")
            else:
                self.runtime_logs_text.config(state='normal')
                self.runtime_logs_text.delete(1.0, 'end')
                self.runtime_logs_text.insert('end', f"Log file not found: {log_path}")
                self.runtime_logs_text.config(state='disabled')
        except Exception as e:
            logger.error(f"Error reading log file: {e}")
            self.runtime_logs_text.config(state='normal')
            self.runtime_logs_text.delete(1.0, 'end')
            self.runtime_logs_text.insert('end', f"Error reading log file: {e}")
            self.runtime_logs_text.config(state='disabled')
    
    def clear_runtime_logs(self):
        """Clear runtime logs display."""
        self.runtime_logs_text.config(state='normal')
        self.runtime_logs_text.delete(1.0, 'end')
        self.runtime_logs_text.config(state='disabled')
    
    def build_audit_log(self, parent):
        """Build audit log interface."""
        # Filter frame
        filter_frame = ttk.Frame(parent)
        filter_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Label(filter_frame, text="Entity Type:", font=('Segoe UI', 10)).pack(side='left')
        self.audit_entity_type_var = tk.StringVar(value="all")
        entity_combo = ttk.Combobox(filter_frame, textvariable=self.audit_entity_type_var, width=20, state='readonly')
        entity_combo['values'] = ['all', 'object_diary', 'document', 'contract', 'llm_task']
        entity_combo.pack(side='left', padx=5)
        
        ttk.Label(filter_frame, text="Actor:", font=('Segoe UI', 10)).pack(side='left')
        self.audit_actor_var = tk.StringVar(value="")
        ttk.Entry(filter_frame, textvariable=self.audit_actor_var, width=20).pack(side='left', padx=5)
        
        ttk.Button(filter_frame, text="🔍 Filter", command=self.filter_audit_log).pack(side='left', padx=5)
        ttk.Button(filter_frame, text="🗑️ Clear", command=self.clear_audit_log).pack(side='left', padx=5)
        
        # Audit log display
        self.audit_log_text = scrolledtext.ScrolledText(parent, state='disabled', font=('Consolas', 9))
        self.audit_log_text.pack(fill='both', expand=True, padx=10, pady=10)
    
    def filter_audit_log(self):
        """Filter and display audit log entries."""
        try:
            from app.core.audit_logger import get_audit_logger
            
            audit_logger = get_audit_logger()
            entity_type = self.audit_entity_type_var.get()
            actor = self.audit_actor_var.get()
            
            # Read audit log file
            audit_file = Path(__file__).parent.parent / "audit.log"
            if not audit_file.exists():
                self.audit_log_text.config(state='normal')
                self.audit_log_text.delete(1.0, 'end')
                self.audit_log_text.insert('end', "No audit log found")
                self.audit_log_text.config(state='disabled')
                return
            
            with open(audit_file, 'r', encoding='utf-8') as f:
                entries = []
                for line in f:
                    try:
                        entry_data = eval(line.strip())
                        # Apply filters
                        if entity_type != "all" and entry_data.get("entity_type") != entity_type:
                            continue
                        if actor and entry_data.get("actor") != actor:
                            continue
                        entries.append(entry_data)
                    except:
                        pass
            
            # Display entries
            self.audit_log_text.config(state='normal')
            self.audit_log_text.delete(1.0, 'end')
            
            for entry in entries:
                timestamp = entry.get("timestamp", "N/A")
                actor = entry.get("actor", "N/A")
                action = entry.get("action", "N/A")
                entity_type = entry.get("entity_type", "N/A")
                entity_id = entry.get("entity_id", "N/A")
                trace_id = entry.get("trace_id", "N/A")
                
                self.audit_log_text.insert('end', f"[{timestamp}] {actor} -> {action} {entity_type}:{entity_id} (trace: {trace_id})\n")
            
            self.audit_log_text.config(state='disabled')
            logger.info(f"Displayed {len(entries)} audit log entries")
            
        except Exception as e:
            logger.error(f"Error filtering audit log: {e}")
            self.audit_log_text.config(state='normal')
            self.audit_log_text.delete(1.0, 'end')
            self.audit_log_text.insert('end', f"Error: {e}")
            self.audit_log_text.config(state='disabled')
    
    def clear_audit_log(self):
        """Clear audit log display."""
        self.audit_log_text.config(state='normal')
        self.audit_log_text.delete(1.0, 'end')
        self.audit_log_text.config(state='disabled')
    
    def initialize_system(self):
        """Initialize system components."""
        try:
            from app.modules.storage.database import initialize_database
            initialize_database()
            logger.info("Database initialized")
            self.status_var.set("System: Ready")
        except Exception as e:
            logger.error(f"Error initializing system: {e}")
            self.status_var.set("System: Error")
    
    def start_llama_cpp(self):
        """Start llama.cpp server automatically."""
        try:
            # Kill ollama.exe if running (conflicts with llama-server)
            try:
                subprocess.run("taskkill /F /IM ollama.exe", shell=True, capture_output=True)
                print("DEBUG: Killed ollama.exe to avoid port conflict")
                time.sleep(2)  # Wait for process to fully terminate
            except:
                pass
            
            from app.modules.llm.llama_cpp_manager import LlamaCppManager
            
            llama_path = self.config.get("llama_cpp_path")
            model_path = self.config.get("model_path")
            
            print(f"DEBUG: llama_path = {llama_path}")
            print(f"DEBUG: model_path = {model_path}")
            
            if not Path(llama_path).exists():
                self.llama_status_var.set("LLM: Not found - Install llama.cpp")
                messagebox.showwarning(
                    "llama.cpp Not Found",
                    "llama-server.exe not found.\n\nDownload from:\nhttps://github.com/ggerganov/llama.cpp/releases\n\nAnd update path in mia_config.json"
                )
                return
            
            if not Path(model_path).exists():
                self.llama_status_var.set("LLM: Model not found")
                messagebox.showwarning(
                    "Model Not Found",
                    f"Model not found: {model_path}\n\nDownload model and update path in mia_config.json"
                )
                return
            
            # Stop any existing llama.cpp process
            if hasattr(self, 'llama_manager') and self.llama_manager.process:
                print("DEBUG: Stopping existing llama.cpp process")
                self.llama_manager.stop_server()
            
            # Start llama.cpp
            self.llama_manager = LlamaCppManager(exe_path=llama_path)
            
            # Start in background thread
            print(f"DEBUG: Starting llama.cpp with model: {model_path}")
            print(f"DEBUG: llama-server.exe: {llama_path}")
            
            threading.Thread(target=self._run_llama_server, args=(model_path,), daemon=True).start()
            
            self.llama_status_var.set("LLM: Starting (please wait 60-90s for 14B model)...")
            
        except Exception as e:
            logger.error(f"Error starting llama.cpp: {e}")
            print(f"DEBUG: Error: {e}")
            import traceback
            traceback.print_exc()
            self.llama_status_var.set("LLM: ❌ Error")
    
    def _run_llama_server(self, model_path: str):
        """Run llama.cpp server in background."""
        try:
            print(f"DEBUG: Starting llama.cpp server with model: {model_path}")
            
            success = self.llama_manager.start_server(
                model_path=model_path,
                port=self.config.get("llama_port", 8080),
                n_gpu_layers=self.config.get("n_gpu_layers", 35),
                context_size=self.config.get("context_size", 8192),
                n_threads=self.config.get("n_threads", 8)
            )
            
            if success:
                print("DEBUG: Server started successfully")
                
                # Force update model info regardless of check_connection
                print("DEBUG: Forcing model info update")
                self.update_model_info()
                
                # Try to verify connection
                time.sleep(5)  # Give it a moment
                if self.llama_manager.check_connection():
                    self.llama_status_var.set("LLM: ✅ Running")
                    logger.info("llama.cpp server started successfully")
                else:
                    self.llama_status_var.set("LLM: ⚠️ Running (may be busy)")
                    logger.warning("llama.cpp server started but connection check failed")
            else:
                self.llama_status_var.set("LLM: ❌ Failed")
                logger.error("llama.cpp server failed to start")
                print("DEBUG: Server failed to start")
                
        except Exception as e:
            logger.error(f"Error running llama.cpp server: {e}")
            print(f"DEBUG: Error: {e}")
            import traceback
            traceback.print_exc()
            self.llama_status_var.set("LLM: ❌ Error")
    
    def paste_to_chat(self, event):
        """Paste text from clipboard to chat history (for pasting code/results)."""
        try:
            clipboard_text = self.root.clipboard_get()
            self.ai_chat_history.insert('end', clipboard_text)
        except:
            pass
        return 'break'  # Prevent default behavior
    
    def paste_from_clipboard(self, event):
        """Paste text from clipboard to input field."""
        try:
            clipboard_text = self.root.clipboard_get()
            self.ai_input.insert('end', clipboard_text)
        except:
            pass
        return 'break'  # Prevent default behavior
    
    def send_ai_message(self):
        """Send message to AI."""
        message = self.ai_input.get().strip()
        if not message:
            return
        
        # Log raw info before any conversion
        logger.info(f"Raw message: {repr(message)}")
        logger.info(f"Message length: {len(message)}")
        
        # On Windows, Tkinter may return text in local encoding (cp1251)
        # Try to fix encoding, but don't lose data
        if sys.platform == 'win32':
            try:
                # Check if the string is already valid UTF-8
                message.encode('utf-8')
                logger.info("Message is already valid UTF-8")
            except UnicodeEncodeError:
                # If not, try to convert from cp1251
                try:
                    message = message.encode('cp1251').decode('utf-8')
                    logger.info("Converted from cp1251 to UTF-8")
                except Exception as e:
                    logger.error(f"Encoding conversion failed: {e}")
        
        logger.info(f"Final message: {repr(message)}")
        print(f"DEBUG: Sending message: {message}")
        
        # Add user message
        self.ai_chat_history.insert('end', f"You: {message}\n")
        self.ai_input.delete(0, 'end')
        
        # Add typing indicator
        self.ai_chat_history.insert('end', "AI: Typing...\n")
        
        # Generate response in background
        print("DEBUG: Starting background thread for generation")
        thread = threading.Thread(target=self._generate_ai_response, args=(message,), daemon=True)
        thread.start()
        print(f"DEBUG: Thread started: {thread.is_alive()}")
    
    def _generate_ai_response(self, message: str):
        """Generate AI response."""
        try:
            print("DEBUG: _generate_ai_response started")
            
            from app.modules.llm.llama_cpp_manager import LlamaCppManager
            
            # Check for file operations (natural language)
            mode = self.config.get("current_mode", "chat")
            if mode == "coder":
                import re
                
                # Auto-detect job references and read jobs file
                if re.search(r'job\s*#?\d+', message, re.IGNORECASE):
                    try:
                        jobs_file = Path("C:/mia/docs/jobs_stage6_coder.md")
                        if jobs_file.exists():
                            with open(jobs_file, 'r', encoding='utf-8') as f:
                                jobs_content = f.read()
                            message = f"JOBS FILE CONTENT:\n\n{jobs_content}\n\n---END JOBS FILE---\n\nИНСТРУКЦИЯ: Найди указанный job в этом файле, прочитай его описание. Если нужно прочитать другие файлы для выполнения job, НЕ проси пользователя. Напиши: прочитай файл: путь/к/файлу - система автоматически прочитает их. Начни с первой задачи в списке задач и ЗАПИШИ КОД."
                            logger.info(f"Auto-read jobs file for job reference ({len(jobs_content)} bytes)")
                    except Exception as e:
                        logger.error(f"Error auto-reading jobs file: {e}")
                
                # Auto-detect file read requests in coder's response pattern
                # If coder mentions files like "мне нужно прочитать X.py", auto-read them
                file_mentions = re.findall(r'прочитать|read|открыть|посмотреть[:\s]+([`\'"]?[\w/\\.\-]+[`\'"]?)', message, re.IGNORECASE)
                if file_mentions and not any(p in message.lower() for p in ['прочитай файл:', 'read file:', 'открой файл:']):
                    for file_ref in file_mentions[:3]:  # Max 3 files
                        file_path = file_ref.strip('`\'"')
                        try:
                            full_path = Path("C:/mia") / file_path
                            if full_path.exists():
                                with open(full_path, 'r', encoding='utf-8') as f:
                                    file_content = f.read()
                                message = f"FILE CONTENT ({file_path}):\n\n{file_content}\n\n---END FILE---\n\n{message}"
                                logger.info(f"Auto-read mentioned file: {file_path} ({len(file_content)} bytes)")
                        except Exception as e:
                            logger.error(f"Error auto-reading mentioned file {file_path}: {e}")
                
                # READ operations - natural language patterns
                read_patterns = [
                    r'прочитай файл[:\s]+(.+)',
                    r'read file[:\s]+(.+)',
                    r'открой файл[:\s]+(.+)',
                    r'посмотри файл[:\s]+(.+)',
                ]
                
                for pattern in read_patterns:
                    match = re.search(pattern, message, re.IGNORECASE)
                    if match:
                        file_path = match.group(1).strip()
                        try:
                            full_path = Path("C:/mia") / file_path
                            if full_path.exists():
                                with open(full_path, 'r', encoding='utf-8') as f:
                                    file_content = f.read()
                                message = f"FILE CONTENT ({file_path}):\n\n{file_content}\n\n---END FILE---\n\nВыполни задачу на основе этого файла."
                                logger.info(f"Read file: {file_path} ({len(file_content)} bytes)")
                            else:
                                message = f"Файл не найден: {file_path}. Попробуй другой путь."
                                logger.error(f"File not found: {file_path}")
                        except Exception as e:
                            message = f"Ошибка чтения файла {file_path}: {e}"
                            logger.error(f"Error reading file: {e}")
                        break
                
                # WRITE operations - natural language patterns
                write_patterns = [
                    r'запиши в файл[:\s]+(.+)',
                    r'write to file[:\s]+(.+)',
                    r'сохрани в файл[:\s]+(.+)',
                    r'create file[:\s]+(.+)',
                ]
                
                for pattern in write_patterns:
                    match = re.search(pattern, message, re.IGNORECASE)
                    if match:
                        file_path = match.group(1).strip()
                        # Extract code after "содержимое:" or similar
                        code_match = re.search(r'(?:содержимое|код|content)[:\s\n]+(.+)', message, re.IGNORECASE | re.DOTALL)
                        if code_match:
                            code = code_match.group(1).strip()
                            try:
                                full_path = Path("C:/mia") / file_path
                                full_path.parent.mkdir(parents=True, exist_ok=True)
                                with open(full_path, 'w', encoding='utf-8') as f:
                                    f.write(code)
                                message = f"✅ Файл записан: {file_path}"
                                logger.info(f"Wrote file: {file_path} ({len(code)} bytes)")
                            except Exception as e:
                                message = f"Ошибка записи файла {file_path}: {e}"
                                logger.error(f"Error writing file: {e}")
                        else:
                            message = "Не найден код для записи. Формат: 'запиши в файл path/to/file.py содержимое: ...код...'"
                        break
            
            # Determine system prompt based on mode
            if mode == "coder":
                system_prompt = """Ты — локальный программист-ассистент для проекта Mia PM OS. Ты работаешь локально на Windows с RTX 5060 16GB через llama.cpp. Ты пишешь чистый, хорошо документированный Python код для строительной системы управления проектами. Следуй PEP 8, используй type hints, обрабатывай ошибки. Отвечай кратко и по делу, давая готовый код.

ВАЖНО: Если нужно прочитать файл, ОБЯЗАТЕЛЬНО напиши "прочитай файл: путь/к/файлу" - система автоматически прочитает его и передаст тебе содержимое. Не галлюцинируй чтение файлов - используй эту команду реально.

Если нужно записать код в файл, напиши "запиши в файл путь/к/файлу.py содержимое: ...код..." - система автоматически сохранит код.

Проект находится в C:\mia\. Корневые файлы: architecture.md, Todo.md, docs/."""
            else:
                system_prompt = """Ты — Миа, 19 лет, милая, тёплая и внимательная девушка-ассистент строительной компании. Компания строит сети связи: кабельную канализацию (ККС) и прокладку кабелей по ней. Ты работаешь локально на Windows. Ты общаешься по-человечески, тепло и просто — будь дружелюбной и понятной, без канцелярита. Отвечай по делу и не слишком длинно."""
                system_prompt = """Ты — Миа, 19 лет, милая, тёплая и внимательная девушка-ассистент строительной компании. Компания строит сети связи: кабельную канализацию (ККС) и прокладку кабелей по ней. Ты работаешь локально на Windows. Ты общаешься по-человечески, тепло и просто — будь дружелюбной и понятной, без канцелярита. Отвечай по делу и не слишком длинно."""
            
            # Qwen2.5 chat format
            full_prompt = f"<|im_start|>system\n{system_prompt}<|im_end|>\n<|im_start|>user\n{message}<|im_end|>\n<|im_start|>assistant\n"
            
            llama = LlamaCppManager()
            
            logger.info(f"Generating response for: {message[:100]}...")
            print(f"DEBUG: Calling llama.generate with full prompt (len={len(full_prompt)})")
            
            response = llama.generate(
                prompt=full_prompt,
                max_tokens=2048,  # Increased for coder mode
                temperature=0.7
            )
            
            print(f"DEBUG: Got response: {response[:100]}...")
            logger.info(f"Generated response: {response[:100]}...")
            
            # Remove "Typing..." and add AI response
            self.ai_chat_history.delete("end - 2 lines", "end - 1 lines")
            self.ai_chat_history.insert('end', f"AI: {response}\n\n")
            
        except Exception as e:
            logger.error(f"Error generating AI response: {e}")
            import traceback
            traceback.print_exc()
            print(f"DEBUG: Error: {e}")
            
            # Remove "Typing..." and add error
            self.ai_chat_history.delete("end - 2 lines", "end - 1 lines")
            self.ai_chat_history.insert('end', f"Error: {str(e)}\n\n")
    
    def clear_ai_chat(self):
        """Clear AI chat history."""
        self.ai_chat_history.delete('1.0', 'end')
    
    def copy_chat_selection(self):
        """Copy selected text from chat history."""
        try:
            # Try multiple methods
            selected_text = ""
            
            # Method 1: selection_get
            try:
                selected_text = self.ai_chat_history.selection_get()
            except:
                pass
            
            # Method 2: get selected range
            if not selected_text:
                try:
                    sel_start = self.ai_chat_history.index("sel.first")
                    sel_end = self.ai_chat_history.index("sel.last")
                    selected_text = self.ai_chat_history.get(sel_start, sel_end)
                except:
                    pass
            
            # Method 3: get all text if nothing selected
            if not selected_text:
                try:
                    selected_text = self.ai_chat_history.get("1.0", "end")
                except:
                    pass
            
            if selected_text:
                self.root.clipboard_clear()
                self.root.clipboard_append(selected_text)
                print(f"Copied {len(selected_text)} characters")
            else:
                print("No text to copy")
        except Exception as e:
            print(f"Copy error: {e}")
    
    def show_context_menu(self, event):
        """Show context menu for right-click copy."""
        menu = tk.Menu(self.ai_chat_history, tearoff=0)
        menu.add_command(label="Copy", command=self.copy_chat_selection)
        menu.post(event.x_root, event.y_root)
    
    def update_model_info(self):
        """Update current model information display."""
        try:
            from app.modules.llm.llama_cpp_manager import LlamaCppManager
            
            llama = LlamaCppManager()
            
            # Try to get model info
            try:
                model_info = llama.get_model_info()
                
                if model_info and 'model_path' in model_info:
                    info_text = f"Model: {Path(model_info['model_path']).name}\n"
                    info_text += f"Context: {model_info.get('n_ctx', 'N/A')} tokens\n"
                    info_text += f"GPU Layers: {model_info.get('n_gpu_layers', 'N/A')}\n"
                    info_text += f"Threads: {model_info.get('n_threads', 'N/A')}"
                    
                    self.current_model_info.set(info_text)
                    print(f"DEBUG: Model info updated: {info_text}")
                else:
                    self.current_model_info.set("Model info not available")
            except Exception as e:
                print(f"DEBUG: Error getting model info: {e}")
                self.current_model_info.set("Model info error (but server may be running)")
                
        except Exception as e:
            logger.error(f"Error updating model info: {e}")
            self.current_model_info.set("LLM: Error loading info")
    
    def on_model_change(self, event):
        """Handle model selection change."""
        selected_model = self.model_var.get()
        logger.info(f"Model selected: {selected_model}")
    
    def switch_mode(self):
        """Switch between chat and coder modes."""
        current_mode = self.mode_var.get()
        print(f"DEBUG: Switching to {current_mode} mode")
        
        # Update config
        self.config["current_mode"] = current_mode
        
        # Reload model
        self.reload_model()
    
    def reload_model(self):
        """Reload llama.cpp with current model based on mode."""
        try:
            from app.modules.llm.llama_cpp_manager import LlamaCppManager
            
            # Stop current server
            if self.llama_manager:
                self.llama_manager.stop_server()
            
            # Determine which model to use
            mode = self.config.get("current_mode", "chat")
            if mode == "coder":
                model_path = self.config.get("coder_model_path")
                if not model_path or not Path(model_path).exists():
                    messagebox.showerror("Error", f"Coder model not found: {model_path}\nPlease download Qwen2.5-Coder-14B-Instruct-Q4_K_M.gguf")
                    return
            else:
                model_path = self.config.get("model_path")
            
            if not model_path or not Path(model_path).exists():
                messagebox.showerror("Error", f"Model not found: {model_path}")
                return
            
            # Start new server
            llama_path = self.config.get("llama_cpp_path")
            self.llama_manager = LlamaCppManager(exe_path=llama_path)
            success = self.llama_manager.start_server(
                model_path=model_path,
                port=self.config.get("llama_port", 8080),
                n_gpu_layers=self.config.get("n_gpu_layers", 45),
                context_size=self.config.get("context_size", 8192),
                n_threads=self.config.get("n_threads", 8)
            )
            
            if success:
                messagebox.showinfo("Success", f"Switched to {mode} mode with {Path(model_path).name}")
            else:
                messagebox.showerror("Error", "Failed to start LLM server")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to reload model: {e}")
            print(f"DEBUG: Error reloading model: {e}")
            import traceback
            traceback.print_exc()
    
    def switch_model(self):
        """Switch to selected model (requires restart)."""
        selected_model = self.model_var.get()
        
        # Map model names to file paths
        model_paths = {
            'qwen2.5-14b-instruct': r'C:\models\Qwen2.5-14B-Instruct-Q4_K_M.gguf',
            'mistral-7b-instruct': r'C:\models\mistral-7b-instruct-v0.3-q4_k_m.gguf',
            'llama-3.1-8b-instruct': r'C:\models\llama-3.1-8b-instruct-q4_k_m.gguf'
        }
        
        model_path = model_paths.get(selected_model)
        
        if not model_path or not Path(model_path).exists():
            messagebox.showerror(
                "Model Not Found",
                f"Model file not found: {model_path}\n\nPlease download the model first."
            )
            return
        
        # Confirm switch
        result = messagebox.askyesno(
            "Switch Model",
            f"Switch to {selected_model}?\n\nThis will restart the LLM server."
        )
        
        if result:
            # Stop current server
            if hasattr(self, 'llama_manager'):
                self.llama_manager.stop_server()
            
            # Update config
            self.config['model_path'] = model_path
            self._save_config()
            
            # Start new server
            self.llama_status_var.set("LLM: Starting...")
            threading.Thread(target=self._run_llama_server, args=(model_path,), daemon=True).start()
    
    def _save_config(self):
        """Save configuration to file."""
        config_file = Path(__file__).parent.parent / "mia_config.json"
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2)
            logger.info("Configuration saved")
        except Exception as e:
            logger.error(f"Error saving config: {e}")
    
    def enable_telegram(self):
        """Enable Telegram bot."""
        # TODO: Implement Telegram bot enable/disable
        self.telegram_status_var.set("Telegram: Not implemented yet")
    
    def start_telegram_manual(self):
        """Manually start Telegram bot."""
        if not self.runtime_manager:
            messagebox.showerror("Error", "Runtime Manager not available")
            return
        
        if self.runtime_manager.start_telegram_bot():
            messagebox.showinfo("Success", "Telegram bot started")
        else:
            messagebox.showerror("Error", "Failed to start Telegram bot")
    
    def start_worker_manual(self):
        """Manually start worker pool."""
        if not self.runtime_manager:
            messagebox.showerror("Error", "Runtime Manager not available")
            return
        
        if self.runtime_manager.start_worker_pool():
            messagebox.showinfo("Success", "Worker pool started")
        else:
            messagebox.showerror("Error", "Failed to start worker pool")
    
    def start_llama_manual(self):
        """Manually start LLM server."""
        # This is handled by start_llama_cpp() on startup
        messagebox.showinfo("Info", "LLM server is auto-started on GUI launch")
    
    def send_telegram_message(self):
        """Send Telegram message."""
        # TODO: Implement Telegram message sending
        messagebox.showinfo("Telegram", "Telegram not implemented yet")
    
    def show_project_ledger(self):
        """Show project ledger."""
        messagebox.showinfo("Project Ledger", "Project Ledger - Coming soon")
    
    def show_object_diary(self):
        """Show object diary."""
        messagebox.showinfo("Object Diary", "Object Diary - Coming soon")
    
    def show_alerts(self):
        """Show alerts."""
        messagebox.showinfo("Alerts", "Alerts - Coming soon")
    
    def show_health_score(self):
        """Show health score."""
        messagebox.showinfo("Health Score", "Health Score - Coming soon")
    
    def refresh_logs(self):
        """Refresh system logs."""
        try:
            with open('mia_gui.log', 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                last_lines = lines[-100:]  # Last 100 lines
                
                self.logs_text.config(state='normal')
                self.logs_text.delete('1.0', 'end')
                self.logs_text.insert('end', ''.join(last_lines))
                self.logs_text.config(state='disabled')
                
        except Exception as e:
            logger.error(f"Error refreshing logs: {e}")
            self.logs_text.config(state='normal')
            self.logs_text.delete('1.0', 'end')
            self.logs_text.insert('end', f"Error loading logs: {e}\n")
            self.logs_text.config(state='disabled')
    
    def refresh_timer(self):
        """Refresh timer for periodic updates."""
        self.refresh_logs()
        self.update_component_statuses()
        self.root.after(10000, self.refresh_timer)  # Changed from 5000 to 10000 (10 seconds)
    
    def update_component_statuses(self):
        """Update component status displays from Runtime Manager."""
        if not self.runtime_manager:
            return
        
        try:
            statuses = self.runtime_manager.get_status()
            
            # Update LLM status
            llm_status = statuses.get("llm_server", {}).get("status", "unknown")
            if llm_status == "running":
                self.llama_status_var.set("LLM: ✅ Running")
            elif llm_status == "stopped":
                self.llama_status_var.set("LLM: 🔴 Stopped")
            elif llm_status == "error":
                self.llama_status_var.set("LLM: ⚠️ Error")
            else:
                self.llama_status_var.set(f"LLM: {llama_status}")
            
            # Update Telegram status
            telegram_status = statuses.get("telegram_bot", {}).get("status", "unknown")
            if telegram_status == "running":
                self.telegram_status_var.set("Telegram: ✅ Running")
            elif telegram_status == "stopped":
                self.telegram_status_var.set("Telegram: 🔴 Stopped")
            elif telegram_status == "error":
                self.telegram_status_var.set("Telegram: ⚠️ Error")
            else:
                self.telegram_status_var.set(f"Telegram: {telegram_status}")
            
            # Update Worker status
            worker_status = statuses.get("worker_pool", {}).get("status", "unknown")
            if worker_status == "running":
                self.worker_status_var.set("Worker Pool: ✅ Running")
            elif worker_status == "stopped":
                self.worker_status_var.set("Worker Pool: 🔴 Stopped")
            elif worker_status == "error":
                self.worker_status_var.set("Worker Pool: ⚠️ Error")
            else:
                self.worker_status_var.set(f"Worker Pool: {worker_status}")
            
        except Exception as e:
            logger.error(f"Error updating component statuses: {e}")
    
    def on_closing(self):
        """Handle window closing."""
        # Stop all components
        if self.runtime_manager:
            self.runtime_manager.stop_all()
        
        # Stop llama.cpp
        if hasattr(self, 'llama_manager'):
            self.llama_manager.stop_server()
        
        # Release instance lock
        self.instance_checker.release_lock()
        
        # Destroy window
        self.root.destroy()


def main():
    """Main entry point."""
    # Check for single instance
    instance_checker = SingleInstanceChecker()
    
    if not instance_checker.acquire_lock():
        messagebox.showerror(
            "Instance Already Running",
            "Mia PM OS is already running.\nOnly one instance is allowed."
        )
        return
    
    # Create GUI
    root = tk.Tk()
    app = MiaGUI(root, instance_checker)
    root.mainloop()


if __name__ == "__main__":
    main()
