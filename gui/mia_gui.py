"""Modern GUI for Mia PM OS - Complete System Management

Features:
- Task Queue management with priorities
- VRAM Management with DAYTIME/NIGHTTIME modes
- Questions Gateway for human intervention
- Health Monitor (Doctor Observer + Audit Vector)
- Real-time statistics and logs
- Single instance enforcement (only one Mia instance at a time)
"""

import sys
import os
import io
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
import socket

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('mia_gui.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class SingleInstanceChecker:
    """Ensures only one instance of Mia is running at a time using TCP socket binding."""
    
    def __init__(self):
        self.host = '127.0.0.1'
        self.port = 57423  # Arbitrary port for Mia instance lock
        self.socket = None
        self.lock_file = Path(__file__).parent.parent / "mia_instance.lock"
    
    def cleanup_stale_lock(self):
        """Clean up stale lock file if the port is not actually in use."""
        if not self.lock_file.exists():
            return False
        
        try:
            # Try to bind the port - if successful, the lock is stale
            test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test_socket.bind((self.host, self.port))
            test_socket.close()
            
            # Port is available, so lock file is stale
            logger.info("Detected stale lock file - cleaning up")
            self.lock_file.unlink()
            return True
        except socket.error:
            # Port is actually in use, lock is valid
            return False
        except Exception as e:
            logger.warning(f"Error checking stale lock: {e}")
            return False
    
    def is_already_running(self) -> bool:
        """Check if another instance is already running by trying to bind the port."""
        # First, clean up any stale lock files
        self.cleanup_stale_lock()
        
        try:
            # Try to bind the port - if it fails, another instance is running
            test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # DO NOT set SO_REUSEADDR - we want exclusive binding
            test_socket.bind((self.host, self.port))
            test_socket.close()
            logger.info(f"Port {self.port} is available")
            return False
        except socket.error as e:
            # Port is already in use
            logger.warning(f"Port {self.port} is already in use: {e}")
            return True
        except Exception as e:
            logger.warning(f"Error checking instance lock: {e}")
            return False
    
    def acquire_lock(self) -> bool:
        """Acquire instance lock by binding to the port."""
        try:
            if self.is_already_running():
                logger.error("Instance already running - cannot acquire lock")
                return False
            
            # Bind to the port and keep the socket open (exclusive binding)
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # DO NOT set SO_REUSEADDR - we want exclusive binding
            self.socket.bind((self.host, self.port))
            self.socket.listen(1)
            logger.info(f"Successfully bound to port {self.port} for instance lock")
            
            # Create lock file as information only (OS handles actual locking via socket)
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
        """Release instance lock by closing the socket."""
        try:
            if self.socket:
                try:
                    self.socket.close()
                except Exception as e:
                    logger.warning(f"Error closing socket: {e}")
                self.socket = None
                logger.info("Released instance lock socket")
            
            # Remove the informational lock file
            if self.lock_file.exists():
                try:
                    self.lock_file.unlink()
                    logger.info("Removed lock file")
                except Exception as e:
                    logger.warning(f"Error removing lock file: {e}")
        except Exception as e:
            logger.error(f"Failed to release lock: {e}")


class MiaGUI:
    """Modern GUI for Mia PM OS system management."""
    
    def __init__(self, root, instance_checker):
        self.root = root
        self.root.title("Mia PM OS - System Management")
        self.root.geometry("1000x700")
        self.root.minsize(900, 600)
        
        # Use the instance checker passed from main()
        self.instance_checker = instance_checker
        
        # Setup cleanup on exit
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # System state
        self.is_running = False
        self.worker_pool = None
        self.questions_gateway = None
        self.audit_vector = None
        self.doctor_observer = None
        self.vram_policy = None
        self.telegram_bot_process = None
        self.ollama_process = None  # Ollama background process
        
        # Style
        self.setup_style()
        
        # Build UI
        self.build_header()
        self.build_main_content()
        self.build_status_bar()
        
        # Initialize components
        self.initialize_system()
        
        # Start refresh timer
        self.refresh_timer()
    
    def on_closing(self):
        """Handle window closing."""
        # Stop system if running
        if self.is_running:
            self.stop_system()
        
        # Stop Ollama if running
        self.stop_ollama()
        
        # Ensure Telegram bot is stopped
        self.stop_telegram_bot_process()
        
        # Release instance lock
        self.instance_checker.release_lock()
        
        # Destroy window
        self.root.destroy()
    
    def setup_style(self):
        """Setup modern styling."""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Custom colors
        style.configure('TFrame', background='#f0f0f0')
        style.configure('TLabel', background='#f0f0f0', font=('Segoe UI', 10))
        style.configure('TButton', font=('Segoe UI', 10, 'bold'))
        style.configure('TNotebook', background='#f0f0f0')
        style.configure('TNotebook.Tab', font=('Segoe UI', 10, 'bold'))
        
        # Header style
        style.configure('Header.TLabel', font=('Segoe UI', 16, 'bold'), 
                      background='#2c3e50', foreground='white')
        
        # Status colors
        style.configure('Success.TLabel', foreground='#27ae60', font=('Segoe UI', 10, 'bold'))
        style.configure('Warning.TLabel', foreground='#f39c12', font=('Segoe UI', 10, 'bold'))
        style.configure('Error.TLabel', foreground='#e74c3c', font=('Segoe UI', 10, 'bold'))
    
    def build_header(self):
        """Build application header."""
        header = ttk.Frame(self.root, style='Header.TFrame')
        header.pack(fill='x', ipady=10)
        
        # Configure header frame background
        header.configure(style='TFrame')
        
        title = ttk.Label(header, text="Mia PM OS", style='Header.TLabel')
        title.pack(side='left', padx=20)
        
        subtitle = ttk.Label(header, text="Construction Project Management System", 
                           font=('Segoe UI', 10), background='#2c3e50', foreground='#ecf0f1')
        subtitle.pack(side='left', padx=5)
        
        # System status indicator
        self.system_status_var = tk.StringVar(value="System: STOPPED")
        status_label = ttk.Label(header, textvariable=self.system_status_var,
                               font=('Segoe UI', 10, 'bold'), background='#2c3e50', foreground='#ecf0f1')
        status_label.pack(side='right', padx=20)
    
    def build_main_content(self):
        """Build main content area with tabs."""
        content = ttk.Frame(self.root)
        content.pack(fill='both', expand=True, padx=10, pady=10)
        
        notebook = ttk.Notebook(content)
        notebook.pack(fill='both', expand=True)
        
        # Build tabs
        self.build_control_tab(notebook)
        self.build_queue_tab(notebook)
        self.build_vram_tab(notebook)
        self.build_questions_tab(notebook)
        self.build_telegram_tab(notebook)
        self.build_health_tab(notebook)
        self.build_chat_tab(notebook)  # Новая вкладка с чатом
        self.build_logs_tab(notebook)
    
    def build_control_tab(self, notebook):
        """Build system control tab."""
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Control")
        
        # Main control buttons
        control_frame = ttk.LabelFrame(tab, text="System Control", padding=15)
        control_frame.pack(fill='x', padx=10, pady=10)
        
        buttons = ttk.Frame(control_frame)
        buttons.pack(fill='x', pady=10)
        
        self.start_btn = ttk.Button(buttons, text="▶ START SYSTEM", command=self.start_system)
        self.start_btn.pack(side='left', padx=5, expand=True, fill='x')
        
        self.stop_btn = ttk.Button(buttons, text="■ STOP SYSTEM", command=self.stop_system, state='disabled')
        self.stop_btn.pack(side='left', padx=5, expand=True, fill='x')
        
        self.restart_btn = ttk.Button(buttons, text="⟳ RESTART", command=self.restart_system, state='disabled')
        self.restart_btn.pack(side='left', padx=5, expand=True, fill='x')
        
        # Quick actions
        quick_frame = ttk.LabelFrame(tab, text="Quick Actions", padding=15)
        quick_frame.pack(fill='x', padx=10, pady=10)
        
        quick_buttons = ttk.Frame(quick_frame)
        quick_buttons.pack(fill='x', pady=5)
        
        ttk.Button(quick_buttons, text="➕ Add Test Task", command=self.add_test_task).pack(side='left', padx=5, expand=True)
        ttk.Button(quick_buttons, text="Run Quick Test", command=self.run_quick_test).pack(side='left', padx=5, expand=True)
        ttk.Button(quick_buttons, text="Refresh Status", command=self.refresh_status).pack(side='left', padx=5, expand=True)
        
        # Ollama control
        ollama_frame = ttk.LabelFrame(tab, text="Ollama Control", padding=15)
        ollama_frame.pack(fill='x', padx=10, pady=10)
        
        ollama_buttons = ttk.Frame(ollama_frame)
        ollama_buttons.pack(fill='x', pady=5)
        
        self.start_ollama_btn = ttk.Button(ollama_buttons, text="▶ Start Ollama", command=self.start_ollama)
        self.start_ollama_btn.pack(side='left', padx=5, expand=True)
        
        self.stop_ollama_btn = ttk.Button(ollama_buttons, text="■ Stop Ollama", command=self.stop_ollama, state='disabled')
        self.stop_ollama_btn.pack(side='left', padx=5, expand=True)
        
        # System info
        info_frame = ttk.LabelFrame(tab, text="System Information", padding=15)
        info_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        self.system_info_var = tk.StringVar(value="System not initialized")
        info_label = ttk.Label(info_frame, textvariable=self.system_info_var, wraplength=800)
        info_label.pack(fill='both', expand=True)
    
    def build_queue_tab(self, notebook):
        """Build task queue management tab."""
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Queue")
        
        # Queue statistics
        stats_frame = ttk.LabelFrame(tab, text="Queue Statistics", padding=15)
        stats_frame.pack(fill='x', padx=10, pady=10)
        
        self.queue_stats_var = tk.StringVar(value="Queue not initialized")
        stats_label = ttk.Label(stats_frame, textvariable=self.queue_stats_var, font=('Segoe UI', 11))
        stats_label.pack(fill='x', pady=5)
        
        # Priority management
        priority_frame = ttk.LabelFrame(tab, text="Priority Management", padding=15)
        priority_frame.pack(fill='x', padx=10, pady=10)
        
        priority_info = ttk.Label(priority_frame, 
                                text="Priority Levels: 10=CRITICAL, 8=HIGH, 5=NORMAL, 3=LOW, 1=BACKGROUND")
        priority_info.pack(fill='x', pady=5)
        
        # Recent tasks
        tasks_frame = ttk.LabelFrame(tab, text="Recent Tasks", padding=15)
        tasks_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        self.tasks_text = scrolledtext.ScrolledText(tasks_frame, height=15, state='disabled')
        self.tasks_text.pack(fill='both', expand=True)
        
        refresh_btn = ttk.Button(tasks_frame, text="Refresh Tasks", command=self.refresh_tasks)
        refresh_btn.pack(fill='x', pady=5)
    
    def build_vram_tab(self, notebook):
        """Build VRAM management tab."""
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="VRAM")
        
        # VRAM policy status
        policy_frame = ttk.LabelFrame(tab, text="VRAM Management Policy", padding=15)
        policy_frame.pack(fill='x', padx=10, pady=10)
        
        self.vram_status_var = tk.StringVar(value="VRAM policy not initialized")
        vram_label = ttk.Label(policy_frame, textvariable=self.vram_status_var, font=('Segoe UI', 11))
        vram_label.pack(fill='x', pady=5)
        
        # Mode control
        mode_frame = ttk.LabelFrame(tab, text="Execution Mode", padding=15)
        mode_frame.pack(fill='x', padx=10, pady=10)
        
        self.mode_var = tk.StringVar(value="Unknown")
        mode_label = ttk.Label(mode_frame, textvariable=self.mode_var, font=('Segoe UI', 12, 'bold'))
        mode_label.pack(fill='x', pady=10)
        
        mode_buttons = ttk.Frame(mode_frame)
        mode_buttons.pack(fill='x', pady=5)
        
        ttk.Button(mode_buttons, text="☀️ Force DAYTIME Mode", command=self.set_daytime_mode).pack(side='left', padx=5, expand=True)
        ttk.Button(mode_buttons, text="Force NIGHTTIME Mode", command=self.set_nighttime_mode).pack(side='left', padx=5, expand=True)
        
        # Model slots
        slots_frame = ttk.LabelFrame(tab, text="Active Model Slots", padding=15)
        slots_frame.pack(fill='x', padx=10, pady=10)
        
        self.slots_var = tk.StringVar(value="No model slots loaded")
        slots_label = ttk.Label(slots_frame, textvariable=self.slots_var, font=('Segoe UI', 11))
        slots_label.pack(fill='x', pady=5)
    
    def build_questions_tab(self, notebook):
        """Build questions gateway tab."""
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="❓ Questions")
        
        # Questions statistics
        stats_frame = ttk.LabelFrame(tab, text="Questions Gateway", padding=15)
        stats_frame.pack(fill='x', padx=10, pady=10)
        
        self.questions_stats_var = tk.StringVar(value="Questions gateway not initialized")
        stats_label = ttk.Label(stats_frame, textvariable=self.questions_stats_var, font=('Segoe UI', 11))
        stats_label.pack(fill='x', pady=5)
        
        # Action buttons
        actions_frame = ttk.LabelFrame(tab, text="Actions", padding=15)
        actions_frame.pack(fill='x', padx=10, pady=10)
        
        actions_buttons = ttk.Frame(actions_frame)
        actions_buttons.pack(fill='x', pady=5)
        
        ttk.Button(actions_buttons, text="➕ Create Test Question", command=self.create_test_question).pack(side='left', padx=5, expand=True)
        ttk.Button(actions_buttons, text="Refresh Questions", command=self.refresh_questions).pack(side='left', padx=5, expand=True)
        
        # Open questions list
        questions_frame = ttk.LabelFrame(tab, text="Open Questions", padding=15)
        questions_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        self.questions_text = scrolledtext.ScrolledText(questions_frame, height=15, state='disabled')
        self.questions_text.pack(fill='both', expand=True)
    
    def build_telegram_tab(self, notebook):
        """Build Telegram chat log tab."""
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Telegram")
        
        # Telegram connection status
        status_frame = ttk.LabelFrame(tab, text="Telegram Connection", padding=15)
        status_frame.pack(fill='x', padx=10, pady=10)
        
        self.telegram_status_var = tk.StringVar(value="Telegram not connected")
        status_label = ttk.Label(status_frame, textvariable=self.telegram_status_var, font=('Segoe UI', 11))
        status_label.pack(fill='x', pady=5)
        
        # Telegram actions
        actions_frame = ttk.LabelFrame(tab, text="Telegram Actions", padding=15)
        actions_frame.pack(fill='x', padx=10, pady=10)
        
        action_buttons = ttk.Frame(actions_frame)
        action_buttons.pack(fill='x', pady=5)
        
        ttk.Button(action_buttons, text="Refresh Chat", command=self.refresh_telegram_chat).pack(side='left', padx=5, expand=True)
        ttk.Button(action_buttons, text="Send Test Message", command=self.send_test_telegram_message).pack(side='left', padx=5, expand=True)
        ttk.Button(action_buttons, text="Show Bot Log", command=self.show_telegram_bot_log).pack(side='left', padx=5, expand=True)
        
        # Chat log
        chat_frame = ttk.LabelFrame(tab, text="Telegram Chat Log", padding=15)
        chat_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        self.telegram_chat_text = scrolledtext.ScrolledText(chat_frame, height=20, state='disabled', font=('Consolas', 9))
        self.telegram_chat_text.pack(fill='both', expand=True)
    
    def build_chat_tab(self, notebook):
        """Build Qwen chat tab for AI assistant interaction - RFC v1.9"""
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="💬 Chat")
        
        # Chat connection status
        status_frame = ttk.LabelFrame(tab, text="AI Chat Status", padding=15)
        status_frame.pack(fill='x', padx=10, pady=10)
        
        self.chat_status_var = tk.StringVar(value="Ollama: Checking connection...")
        status_label = ttk.Label(status_frame, textvariable=self.chat_status_var, font=('Segoe UI', 11))
        status_label.pack(fill='x', pady=5)
        
        # Model selection
        model_frame = ttk.LabelFrame(tab, text="Model Selection", padding=15)
        model_frame.pack(fill='x', padx=10, pady=10)
        
        model_label = ttk.Label(model_frame, text="Available Models:")
        model_label.pack(anchor='w', pady=5)
        
        models_frame = ttk.Frame(model_frame)
        models_frame.pack(fill='x', pady=5)
        
        self.model_var = tk.StringVar(value="mistral:7b-instruct-v0.3")
        models = ["mistral:7b-instruct-v0.3", "qwen2.5:14b-instruct-q4_K_M"]
        
        for model in models:
            ttk.Radiobutton(models_frame, text=model, variable=self.model_var, value=model).pack(anchor='w')
        
        # Chat interface
        chat_frame = ttk.LabelFrame(tab, text="Chat with Qwen", padding=15)
        chat_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Ollama status and control
        ollama_control_frame = ttk.Frame(chat_frame)
        ollama_control_frame.pack(fill='x', pady=(0, 10))
        
        ollama_status_label = ttk.Label(ollama_control_frame, textvariable=self.chat_status_var, font=('Segoe UI', 10, 'bold'))
        ollama_status_label.pack(side='left')
        
        self.start_ollama_chat_btn = ttk.Button(ollama_control_frame, text="▶ Запустить Ollama", command=self.start_ollama)
        self.start_ollama_chat_btn.pack(side='right', padx=5)
        
        # Chat history
        history_label = ttk.Label(chat_frame, text="История чата:", font=('Segoe UI', 9, 'bold'))
        history_label.pack(anchor='w', pady=(0, 5))
        
        self.chat_history = scrolledtext.ScrolledText(chat_frame, height=12, state='disabled', font=('Segoe UI', 10))
        self.chat_history.pack(fill='both', expand=True, pady=5)
        
        # Input area - simplified
        input_label = ttk.Label(chat_frame, text="📝 Введите сообщение:", font=('Segoe UI', 10, 'bold'))
        input_label.pack(anchor='w', pady=(10, 5))
        
        self.chat_input = ttk.Entry(chat_frame, font=('Segoe UI', 11))
        self.chat_input.pack(fill='x', pady=5, ipady=5)
        self.chat_input.bind('<Return>', lambda e: self.send_chat_message())
        
        # Placeholder text
        self.chat_input.insert(0, "Напишите сообщение здесь...")
        self.chat_input.bind('<FocusIn>', lambda e: self._on_input_focus())
        
        # Buttons
        button_frame = ttk.Frame(chat_frame)
        button_frame.pack(fill='x', pady=5)
        
        send_btn = ttk.Button(button_frame, text="📤 Отправить", command=self.send_chat_message, width=20)
        send_btn.pack(side='left', padx=5)
        
        clear_btn = ttk.Button(button_frame, text="🗑️ Очистить", command=self.clear_chat, width=15)
        clear_btn.pack(side='left', padx=5)
        
        # Quick prompts
        quick_frame = ttk.LabelFrame(tab, text="Quick Prompts", padding=15)
        quick_frame.pack(fill='x', padx=10, pady=10)
        
        quick_buttons = ttk.Frame(quick_frame)
        quick_buttons.pack(fill='x', pady=5)
        
        ttk.Button(quick_buttons, text="📊 System Status", command=self.ask_system_status).pack(side='left', padx=5, expand=True)
        ttk.Button(quick_buttons, text="📝 Create Diary", command=self.ask_create_diary).pack(side='left', padx=5, expand=True)
        ttk.Button(quick_buttons, text="⏰ Current Time", command=self.ask_current_time).pack(side='left', padx=5, expand=True)
        ttk.Button(quick_buttons, text="❓ Help", command=self.ask_help).pack(side='left', padx=5, expand=True)
    
    def send_chat_message(self):
        """Send message to Qwen via Ollama"""
        message = self.chat_input.get().strip()
        if not message:
            return
        
        # Add user message to history
        self.chat_history.config(state='normal')
        self.chat_history.insert('end', f"You: {message}\n")
        self.chat_history.config(state='disabled')
        self.chat_input.delete(0, 'end')
        
        # Add to history (enable temporarily)
        self.chat_history.see('end')
        
        # Get selected model
        model = self.model_var.get()
        
        # Process in background thread
        threading.Thread(target=self._process_chat_message, args=(message, model), daemon=True).start()
    
    def _process_chat_message(self, message: str, model: str):
        """Process chat message with Ollama"""
        try:
            # Import Ollama client
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from app.modules.llm.ollama_client import OllamaClient
            from app.modules.temporal.temporal_logic import TemporalLogicManager
            
            # Initialize client
            client = OllamaClient(base_url="http://localhost:11434")
            
            # Get temporal context
            temporal_manager = TemporalLogicManager()
            context = temporal_manager.get_temporal_context()
            
            # Add temporal context to prompt
            temporal_header = f"""
[ SYSTEM CONTEXT ]
Current Absolute Time: {context.current_absolute_time.strftime('%Y-%m-%d %H:%M:%S')}
Current Day of Week: {context.current_day_of_week}
Relative Translation Map:
"""
            for key, value in context.relative_translation_map.items():
                temporal_header += f'- "{key}" = {value}\n'
            temporal_header += "[ END SYSTEM CONTEXT ]\n\n"
            
            full_prompt = temporal_header + message
            
            # Generate response
            import asyncio
            result = asyncio.run(client.generate(
                prompt=full_prompt,
                model=model,
                cache_key=f"chat_{hash(message)}_{model}"
            ))
            
            # Add AI response to history
            self.chat_history.config(state='normal')
            self.chat_history.insert('end', f"AI ({model}): {result['response']}\n\n")
            self.chat_history.config(state='disabled')
            self.chat_history.see('end')
            
            # Update status
            self.chat_status_var.set(f"Ollama: Connected (using {model})")
            
        except Exception as e:
            self.chat_history.config(state='normal')
            self.chat_history.insert('end', f"Error: {str(e)}\n\n")
            self.chat_history.config(state='disabled')
            self.chat_history.see('end')
            
            self.chat_status_var.set(f"Ollama: Error - {str(e)}")
    
    def clear_chat(self):
        """Clear chat history"""
        self.chat_history.config(state='normal')
        self.chat_history.delete('1.0', 'end')
        self.chat_history.config(state='disabled')
    
    def ask_system_status(self):
        """Quick prompt: Ask system status"""
        self.chat_input.delete(0, 'end')
        self.chat_input.insert(0, "What is the current system status?")
        self.send_chat_message()
    
    def ask_create_diary(self):
        """Quick prompt: Ask to create diary"""
        self.chat_input.delete(0, 'end')
        self.chat_input.insert(0, "How do I create a new object diary?")
        self.send_chat_message()
    
    def ask_current_time(self):
        """Quick prompt: Ask current time with context"""
        self.chat_input.delete(0, 'end')
        self.chat_input.insert(0, "What is the current date and what day of the week is it?")
        self.send_chat_message()
    
    def ask_help(self):
        """Quick prompt: Ask for help"""
        self.chat_input.delete(0, 'end')
        self.chat_input.insert(0, "What can you help me with regarding construction project management?")
        self.send_chat_message()
    
    def _on_input_focus(self):
        """Clear placeholder text when input gets focus"""
        if self.chat_input.get() == "Напишите сообщение здесь...":
            self.chat_input.delete(0, 'end')
    
    def build_health_tab(self, notebook):
        """Build health monitoring tab."""
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Health")
        
        # Doctor Observer status
        doctor_frame = ttk.LabelFrame(tab, text="Doctor Observer", padding=15)
        doctor_frame.pack(fill='x', padx=10, pady=10)
        
        self.doctor_stats_var = tk.StringVar(value="Doctor observer not initialized")
        doctor_label = ttk.Label(doctor_frame, textvariable=self.doctor_stats_var, font=('Segoe UI', 11))
        doctor_label.pack(fill='x', pady=5)
        
        # Audit Vector status
        audit_frame = ttk.LabelFrame(tab, text="Nighttime Audit Vector", padding=15)
        audit_frame.pack(fill='x', padx=10, pady=10)
        
        self.audit_stats_var = tk.StringVar(value="Audit vector not initialized")
        audit_label = ttk.Label(audit_frame, textvariable=self.audit_stats_var, font=('Segoe UI', 11))
        audit_label.pack(fill='x', pady=5)
        
        # Health actions
        health_actions = ttk.LabelFrame(tab, text="Health Actions", padding=15)
        health_actions.pack(fill='x', padx=10, pady=10)
        
        action_buttons = ttk.Frame(health_actions)
        action_buttons.pack(fill='x', pady=5)
        
        ttk.Button(action_buttons, text="Run Audit Cycle", command=self.run_audit_cycle).pack(side='left', padx=5, expand=True)
        ttk.Button(action_buttons, text="Check Health Status", command=self.check_health_status).pack(side='left', padx=5, expand=True)
        
        # Diagnoses list
        diagnoses_frame = ttk.LabelFrame(tab, text="Recent Diagnoses", padding=15)
        diagnoses_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        self.diagnoses_text = scrolledtext.ScrolledText(diagnoses_frame, height=10, state='disabled')
        self.diagnoses_text.pack(fill='both', expand=True)
    
    def build_logs_tab(self, notebook):
        """Build logs tab."""
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Logs")
        
        # Log controls
        controls_frame = ttk.Frame(tab)
        controls_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Button(controls_frame, text="Refresh Logs", command=self.refresh_logs).pack(side='left', padx=5)
        ttk.Button(controls_frame, text="Clear Logs", command=self.clear_logs).pack(side='left', padx=5)
        ttk.Button(controls_frame, text="Export Logs", command=self.export_logs).pack(side='left', padx=5)
        
        # Log viewer
        log_frame = ttk.LabelFrame(tab, text="System Logs", padding=15)
        log_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=20, state='disabled')
        self.log_text.pack(fill='both', expand=True)
    
    def _check_ollama_connection(self):
        """Check Ollama connection for chat tab"""
        try:
            import ollama
            client = ollama.Client(host='http://localhost:11434')
            models = client.list()
            self.chat_status_var.set(f"Ollama: Connected ({len(models['models'])} models)")
            logger.info(f"Ollama connected: {len(models['models'])} models available")
        except Exception as e:
            if self.ollama_process:
                self.chat_status_var.set("Ollama: Starting...")
            else:
                self.chat_status_var.set("Ollama: Stopped - Click 'Start Ollama' in Control tab")
            logger.warning(f"Ollama not connected: {e}")
    
    def build_status_bar(self):
        """Build status bar."""
        status_bar = ttk.Frame(self.root)
        status_bar.pack(fill='x', padx=10, pady=5)
        
        self.status_var = tk.StringVar(value="Ready")
        status_label = ttk.Label(status_bar, textvariable=self.status_var)
        status_label.pack(side='left')
        
        # Time
        self.time_var = tk.StringVar(value="")
        time_label = ttk.Label(status_bar, textvariable=self.time_var)
        time_label.pack(side='right')
    
    def initialize_system(self):
        """Initialize system components."""
        try:
            # Initialize databases
            from app.modules.storage.database import initialize_database
            from app.modules.storage.questions_gateway import initialize_questions_database
            from app.workers.audit_vector import initialize_audit_database
            from app.modules.doctor.observer import initialize_doctor_database
            
            initialize_database()
            initialize_questions_database()
            initialize_audit_database()
            initialize_doctor_database()
            
            self.update_system_info("✅ System components initialized successfully")
            logger.info("System components initialized")
            
            # Check Ollama connection for chat
            self._check_ollama_connection()
            
        except Exception as e:
            self.update_system_info(f"❌ Initialization failed: {e}")
            logger.error(f"System initialization failed: {e}")
    
    def start_system(self):
        """Start Mia PM OS system."""
        if self.is_running:
            messagebox.showwarning("System Running", "System is already running!")
            return
        
        try:
            self.update_status("Starting system...")
            
            # Create Questions Gateway
            from app.modules.storage.questions_gateway import QuestionsGateway
            self.questions_gateway = QuestionsGateway(Path(__file__).parent)
            
            # Create VRAM Policy
            from app.modules.vram_policy import VRAMManagementPolicy
            self.vram_policy = VRAMManagementPolicy()
            
            # Create Worker Pool
            from app.workers.worker_pool import SingleThreadedWorkerPool
            
            def task_handler(task):
                logger.info(f"Processing task: {task['task_id']}")
                time.sleep(1)  # Simulate processing
                return {"status": "success", "task_id": task['task_id']}
            
            self.worker_pool = SingleThreadedWorkerPool(
                task_handler=task_handler,
                max_concurrent_tasks=1,
                poll_interval=0.5,
                questions_gateway=self.questions_gateway
            )
            
            self.worker_pool.start()
            
            # Create Doctor Observer
            from app.modules.doctor.observer import DoctorObserver
            self.doctor_observer = DoctorObserver(questions_gateway=self.questions_gateway)
            self.doctor_observer.start()
            
            # Create Audit Vector
            from app.workers.audit_vector import NighttimeAuditVector
            self.audit_vector = NighttimeAuditVector(Path(__file__).parent, 
                                                       questions_gateway=self.questions_gateway)
            self.audit_vector.start()
            
            # Start Telegram bot
            self.telegram_bot_process = self.start_telegram_bot_process()
            
            self.is_running = True
            self.start_time = datetime.now()
            
            # Update UI
            self.start_btn.config(state='disabled')
            self.stop_btn.config(state='normal')
            self.restart_btn.config(state='normal')
            self.system_status_var.set("System: RUNNING")
            
            self.update_status("System started successfully!")
            self.update_system_info(f"✅ System running since {self.start_time.strftime('%H:%M:%S')}")
            
            logger.info("Mia PM OS system started successfully")
            
        except Exception as e:
            self.update_status(f"❌ Failed to start: {e}")
            logger.error(f"System start failed: {e}")
            messagebox.showerror("Start Error", f"Failed to start system: {e}")
    
    def stop_system(self):
        """Stop Mia PM OS system."""
        if not self.is_running:
            messagebox.showwarning("System Not Running", "System is not running!")
            return
        
        try:
            self.update_status("Stopping system...")
            
            # Stop Telegram bot first
            self.stop_telegram_bot_process()
            
            # Stop components
            if self.worker_pool:
                self.worker_pool.stop()
            
            if self.doctor_observer:
                self.doctor_observer.stop()
            
            if self.audit_vector:
                self.audit_vector.stop()
            
            self.is_running = False
            runtime = datetime.now() - self.start_time if self.start_time else "unknown"
            
            # Update UI
            self.start_btn.config(state='normal')
            self.stop_btn.config(state='disabled')
            self.restart_btn.config(state='disabled')
            self.system_status_var.set("⚪ System: STOPPED")
            
            self.update_status(f"System stopped. Runtime: {runtime}")
            self.update_system_info(f"⏹️ System stopped. Total runtime: {runtime}")
            
            logger.info("Mia PM OS system stopped successfully")
            
        except Exception as e:
            self.update_status(f"❌ Failed to stop: {e}")
            logger.error(f"System stop failed: {e}")
            messagebox.showerror("Stop Error", f"Failed to stop system: {e}")
    
    def restart_system(self):
        """Restart Mia PM OS system."""
        self.stop_system()
        time.sleep(2)
        self.start_system()
    
    def add_test_task(self):
        """Add a test task to the queue."""
        if not self.is_running:
            messagebox.showwarning("System Not Running", "Start the system first!")
            return
        
        try:
            from app.modules.storage.database import enqueue_task
            
            task_data = {
                'task_id': f"TEST-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                'task_type': 'test_task',
                'priority': 8,
                'system_current_time': datetime.now(),
                'user_message': 'Test task from GUI',
                'user_intent': 'test',
                'telegram_chat_id': -1001234567890,
                'user_id': 123456789
            }
            
            if enqueue_task(task_data):
                self.update_status(f"✅ Test task added: {task_data['task_id']}")
                self.refresh_tasks()
            else:
                self.update_status("❌ Failed to add task")
                
        except Exception as e:
            self.update_status(f"❌ Error adding task: {e}")
            logger.error(f"Failed to add test task: {e}")
    
    def run_quick_test(self):
        """Run a quick comprehensive test."""
        if not self.is_running:
            messagebox.showwarning("System Not Running", "Start the system first!")
            return
        
        try:
            self.update_status("Running quick test...")
            
            # Add test tasks
            for i in range(3):
                self.add_test_task()
                time.sleep(0.5)
            
            # Wait for processing
            time.sleep(5)
            
            # Refresh status
            self.refresh_status()
            self.refresh_tasks()
            
            self.update_status("✅ Quick test completed")
            
        except Exception as e:
            self.update_status(f"❌ Test failed: {e}")
            logger.error(f"Quick test failed: {e}")
    
    def refresh_status(self):
        """Refresh system status."""
        if not self.is_running:
            self.update_system_info("⚪ System: STOPPED")
            return
        
        try:
            # Worker pool status
            if self.worker_pool:
                worker_status = self.worker_pool.get_status()
                self.update_system_info(
                    f"System RUNNING\n"
                    f"Worker: {worker_status['state']}\n"
                    f"Tasks processed: {worker_status['tasks_processed']}\n"
                    f"Tasks failed: {worker_status['tasks_failed']}\n"
                    f"Tasks suspended: {worker_status.get('tasks_suspended', 0)}"
                )
            
            # VRAM status
            if self.vram_policy:
                vram_status = self.vram_policy.get_status()
                self.vram_status_var.set(
                    f"Mode: {vram_status['execution_mode']}\n"
                    f"Models loaded: {len(vram_status['current_loaded_models'])}\n"
                    f"Current model: {vram_status['current_model']}"
                )
                self.mode_var.set(vram_status['execution_mode'].upper())
                self.slots_var.set(str(vram_status['current_loaded_models']))
            
            # Questions gateway
            if self.questions_gateway:
                open_questions = self.questions_gateway.get_open_questions()
                self.questions_stats_var.set(f"Open questions: {len(open_questions)}")
            
            # Health status
            if self.doctor_observer:
                doctor_stats = self.doctor_observer.get_observer_statistics()
                self.doctor_stats_var.set(
                    f"Anomalies detected: {doctor_stats['anomalies_detected']}\n"
                    f"Critical anomalies: {doctor_stats['critical_anomalies']}\n"
                    f"Response history: {doctor_stats['response_history_size']}\n"
                    f"Active tasks: {doctor_stats['active_tasks']}"
                )
            
            if self.audit_vector:
                audit_stats = self.audit_vector.get_audit_statistics()
                self.audit_stats_var.set(
                    f"Audits performed: {audit_stats['audits_performed']}\n"
                    f"Gaps detected: {audit_stats['gaps_detected']}\n"
                    f"Critical gaps: {audit_stats['critical_gaps']}"
                )
            
        except Exception as e:
            logger.error(f"Failed to refresh status: {e}")
    
    def refresh_tasks(self):
        """Refresh task queue information."""
        try:
            from app.modules.storage.database import get_queue_statistics
            
            stats = get_queue_statistics()
            self.queue_stats_var.set(
                f"Pending: {stats['pending']} | "
                f"Processing: {stats['processing']} | "
                f"Completed: {stats['completed']} | "
                f"Failed: {stats['failed']}"
            )
            
            # Show recent tasks
            from app.modules.storage.database import get_db_connection
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT task_id, task_type, priority, status, queued_at
                    FROM llm_task_queue 
                    ORDER BY queued_at DESC 
                    LIMIT 10
                """)
                
                self.tasks_text.config(state='normal')
                self.tasks_text.delete('1.0', 'end')
                
                for row in cursor.fetchall():
                    task_info = f"{row['task_id']} | {row['task_type']} | Priority: {row['priority']} | {row['status']}\n"
                    self.tasks_text.insert('end', task_info)
                
                self.tasks_text.config(state='disabled')
                
        except Exception as e:
            logger.error(f"Failed to refresh tasks: {e}")
    
    def set_daytime_mode(self):
        """Force daytime mode."""
        if not self.vram_policy:
            messagebox.showwarning("VRAM Policy", "VRAM policy not initialized!")
            return
        
        try:
            from app.modules.vram_policy import ExecutionMode
            self.vram_policy.switch_execution_mode(ExecutionMode.DAYTIME)
            self.refresh_status()
            self.update_status("✅ Switched to DAYTIME mode")
        except Exception as e:
            self.update_status(f"❌ Failed to switch mode: {e}")
    
    def set_nighttime_mode(self):
        """Force nighttime mode."""
        if not self.vram_policy:
            messagebox.showwarning("VRAM Policy", "VRAM policy not initialized!")
            return
        
        try:
            from app.modules.vram_policy import ExecutionMode
            self.vram_policy.switch_execution_mode(ExecutionMode.NIGHTTIME)
            self.refresh_status()
            self.update_status("✅ Switched to NIGHTTIME mode")
        except Exception as e:
            self.update_status(f"❌ Failed to switch mode: {e}")
    
    def create_test_question(self):
        """Create a test question."""
        if not self.questions_gateway:
            messagebox.showwarning("Questions Gateway", "Questions gateway not initialized!")
            return
        
        try:
            question_data = {
                "question_id": f"Q-TEST-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "question_type": "test_question",
                "priority": "normal",
                "project_id": "PROJ-TEST-001",
                "related_schema_type": "TestSchema",
                "related_entity_id": "TEST-001",
                "question_markdown": "# Test Question\n\nThis is a test question from GUI.\n\n## Options:\n**(a)** Option A\n**(b)** Option B",
                "option_a": "Option A",
                "option_b": "Option B"
            }
            
            question_id = self.questions_gateway.ask_human(question_data)
            self.update_status(f"✅ Test question created: {question_id}")
            self.refresh_questions()
            
        except Exception as e:
            self.update_status(f"❌ Failed to create question: {e}")
            logger.error(f"Failed to create test question: {e}")
    
    def refresh_questions(self):
        """Refresh questions gateway information."""
        if not self.questions_gateway:
            return
        
        try:
            open_questions = self.questions_gateway.get_open_questions()
            
            self.questions_text.config(state='normal')
            self.questions_text.delete('1.0', 'end')
            
            for q in open_questions:
                question_info = f"❓ {q['question_id']} | {q['question_type']} | {q['priority']}\n"
                self.questions_text.insert('end', question_info)
            
            self.questions_text.config(state='disabled')
            
        except Exception as e:
            logger.error(f"Failed to refresh questions: {e}")
    
    def refresh_telegram_chat(self):
        """Refresh Telegram chat log from existing bot database."""
        try:
            # Update bot status
            if self.telegram_bot_process and self.telegram_bot_process.poll() is None:
                self.telegram_status_var.set("Telegram: Bot RUNNING")
            elif self.telegram_bot_process:
                self.telegram_status_var.set("Telegram: Bot STOPPED")
            else:
                self.telegram_status_var.set("Telegram: Bot NOT STARTED")
            
            # Try to get recent Telegram messages from the existing bot database
            try:
                from mia.memory.database import Database
                from config import settings
                
                db = Database()
                
                # Get recent messages from all chats (newest first for display)
                with db._lock:
                    rows = db._conn.execute(
                        """SELECT * FROM messages 
                           ORDER BY id DESC LIMIT 50"""
                    ).fetchall()
                
                self.telegram_chat_text.config(state='normal')
                self.telegram_chat_text.delete('1.0', 'end')
                
                if rows:
                    # Reverse to show oldest first, newest at bottom
                    rows = list(reversed(rows))
                    for row in rows:
                        msg = Database._row_to_message(row)
                        direction = "[IN]" if msg.user_id else "[SYS]"
                        timestamp = msg.created_at if msg.created_at else 'Unknown'
                        username = msg.user_name if msg.user_name else f"User {msg.user_id}"
                        chat_info = f" (Chat: {msg.chat_title})" if msg.chat_title else ""
                        
                        message_info = f"[{timestamp}] {direction} {username}{chat_info}: {msg.text}\n"
                        self.telegram_chat_text.insert('end', message_info)
                    
                    # Auto-scroll to bottom to show newest messages
                    self.telegram_chat_text.see('end')
                    
                    self.telegram_status_var.set(f"Telegram: {len(rows)} messages (Bot RUNNING)" if self.telegram_bot_process and self.telegram_bot_process.poll() is None else f"Telegram: {len(rows)} messages")
                else:
                    self.telegram_chat_text.insert('end', "No messages found in bot database.\n")
                    self.telegram_chat_text.insert('end', "Messages will appear here when you send them via Telegram.\n")
                
                self.telegram_chat_text.config(state='disabled')
                db.close()
                    
            except ImportError as e:
                # Fallback to new database if old bot database is not available
                logger.warning(f"Could not import bot database: {e}")
                self.telegram_chat_text.config(state='normal')
                self.telegram_chat_text.delete('1.0', 'end')
                self.telegram_chat_text.insert('end', "Bot database not available.\n")
                self.telegram_chat_text.insert('end', "Ensure Telegram bot is properly configured.\n")
                self.telegram_chat_text.config(state='disabled')
                    
        except Exception as e:
            logger.error(f"Failed to refresh Telegram chat: {e}")
            self.telegram_chat_text.config(state='normal')
            self.telegram_chat_text.delete('1.0', 'end')
            self.telegram_chat_text.insert('end', f"Error loading Telegram chat: {e}\n")
            self.telegram_chat_text.config(state='disabled')
            self.telegram_status_var.set("Telegram: Error loading chat")
    
    def send_test_telegram_message(self):
        """Send a test message via Telegram."""
        try:
            self.update_status("Sending message via Telegram bot...")
            
            from dotenv import load_dotenv
            import os
            load_dotenv()
            
            bot_token = os.getenv('BOT_TOKEN')
            if not bot_token:
                messagebox.showerror("Telegram Error", "BOT_TOKEN not found in .env file")
                return
            
            # Use a simple dialog to get chat ID
            chat_id = simpledialog.askstring("Telegram Chat ID", 
                                           "Enter your Telegram chat ID:\n(Message @userinfobot in Telegram to get your ID)",
                                           parent=self.root)
            
            if not chat_id:
                messagebox.showinfo("Telegram Info", 
                                  "To send real messages, you need your Telegram chat ID.\n"
                                  "Message @userinfobot in Telegram to get your chat ID.")
                return
            
            # Send message via Telegram Bot API
            import requests
            
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            message_text = f"Test message from Mia GUI at {datetime.now().strftime('%H:%M:%S')}"
            
            response = requests.post(url, json={
                'chat_id': chat_id,
                'text': message_text
            })
            
            if response.status_code == 200:
                self.update_status("Message sent successfully via Telegram")
                messagebox.showinfo("Telegram Success", "Message sent successfully via Telegram!")
                self.refresh_telegram_chat()
            else:
                error_msg = response.json().get('description', 'Unknown error')
                messagebox.showerror("Telegram Error", f"Failed to send message: {error_msg}")
            
        except Exception as e:
            self.update_status(f"Failed to send message: {e}")
            logger.error(f"Failed to send Telegram message: {e}")
            messagebox.showerror("Telegram Error", f"Error: {e}")
    
    def start_telegram_bot_process(self):
        """Start Telegram bot as a subprocess."""
        try:
            import subprocess
            import sys
            
            bot_script = Path(__file__).parent.parent / "mia" / "bot" / "main.py"
            project_root = Path(__file__).parent.parent
            
            # Start bot in background with output to log file
            log_file = Path(__file__).parent.parent / "telegram_bot.log"
            
            # Clear previous log
            if log_file.exists():
                log_file.unlink()
            
            with open(log_file, 'a', encoding='utf-8') as log_out:
                # Set PYTHONPATH to include project root
                env = os.environ.copy()
                env['PYTHONPATH'] = str(project_root)
                
                process = subprocess.Popen(
                    [sys.executable, str(bot_script)],
                    cwd=str(project_root),
                    stdout=log_out,
                    stderr=subprocess.STDOUT,
                    text=True,
                    env=env
                )
            
            logger.info(f"Telegram bot started with PID: {process.pid}, logging to {log_file}")
            return process
            
        except Exception as e:
            logger.error(f"Failed to start Telegram bot: {e}")
            return None
    
    def stop_telegram_bot_process(self):
        """Stop Telegram bot subprocess."""
        if self.telegram_bot_process:
            try:
                self.telegram_bot_process.terminate()
                self.telegram_bot_process.wait(timeout=5)
                logger.info("Telegram bot stopped successfully")
            except subprocess.TimeoutExpired:
                self.telegram_bot_process.kill()
                logger.warning("Telegram bot killed forcefully")
            except Exception as e:
                logger.error(f"Error stopping Telegram bot: {e}")
    
    def start_ollama(self):
        """Start Ollama server as background process."""
        if self.ollama_process:
            messagebox.showwarning("Ollama Already Running", "Ollama is already running")
            return
        
        try:
            # Start Ollama server
            self.ollama_process = subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            logger.info(f"Ollama started with PID: {self.ollama_process.pid}")
            self.start_ollama_btn.config(state='disabled')
            self.stop_ollama_btn.config(state='normal')
            
            # Also disable the chat button
            if hasattr(self, 'start_ollama_chat_btn'):
                self.start_ollama_chat_btn.config(state='disabled')
            
            self.update_status("⏳ Запуск Ollama, подождите...")
            
            # Wait longer for Ollama to start and retry connection
            import time
            max_retries = 10
            for i in range(max_retries):
                time.sleep(2)  # Wait 2 seconds between retries
                try:
                    self._check_ollama_connection()
                    if "Connected" in self.chat_status_var.get():
                        break
                except:
                    logger.warning(f"Retry {i+1}/{max_retries}: Ollama not ready yet")
            
            self.update_status("✅ Ollama запущен")
            
        except Exception as e:
            logger.error(f"Failed to start Ollama: {e}")
            messagebox.showerror("Ollama Error", f"Failed to start Ollama: {e}")
    
    def stop_ollama(self):
        """Stop Ollama server."""
        if not self.ollama_process:
            messagebox.showwarning("Ollama Not Running", "Ollama is not running")
            return
        
        try:
            self.ollama_process.terminate()
            self.ollama_process.wait(timeout=5)
            logger.info("Ollama stopped successfully")
            
            self.start_ollama_btn.config(state='normal')
            self.stop_ollama_btn.config(state='disabled')
            
            # Also enable the chat button
            if hasattr(self, 'start_ollama_chat_btn'):
                self.start_ollama_chat_btn.config(state='normal')
            
            self.chat_status_var.set("Ollama: Stopped")
            self.update_status("✅ Ollama stopped")
            
        except subprocess.TimeoutExpired:
            self.ollama_process.kill()
            logger.warning("Ollama killed forcefully")
            self.start_ollama_btn.config(state='normal')
            self.stop_ollama_btn.config(state='disabled')
            if hasattr(self, 'start_ollama_chat_btn'):
                self.start_ollama_chat_btn.config(state='normal')
            self.chat_status_var.set("Ollama: Killed")
        except Exception as e:
            logger.error(f"Error stopping Ollama: {e}")
            messagebox.showerror("Ollama Error", f"Error stopping Ollama: {e}")
    
    def stop_telegram_bot_process(self):
        """Stop Telegram bot subprocess."""
        if self.telegram_bot_process:
            try:
                self.telegram_bot_process.terminate()
                self.telegram_bot_process.wait(timeout=5)
                logger.info("Telegram bot stopped successfully")
            except subprocess.TimeoutExpired:
                self.telegram_bot_process.kill()
                logger.warning("Telegram bot killed forcefully")
            except Exception as e:
                logger.error(f"Error stopping Telegram bot: {e}")
            finally:
                self.telegram_bot_process = None
    
    def show_telegram_bot_log(self):
        """Show Telegram bot log in a separate window."""
        try:
            log_file = Path(__file__).parent.parent / "telegram_bot.log"
            if log_file.exists():
                # Create a new window to show the log
                log_window = tk.Toplevel(self.root)
                log_window.title("Telegram Bot Log")
                log_window.geometry("800x600")
                
                log_text = scrolledtext.ScrolledText(log_window, font=('Consolas', 9))
                log_text.pack(fill='both', expand=True)
                
                # Read log with encoding fallback
                try:
                    with open(log_file, 'r', encoding='utf-8') as f:
                        log_content = f.read()[-10000:]  # Last 10000 chars
                except UnicodeDecodeError:
                    with open(log_file, 'r', encoding='cp1251', errors='ignore') as f:
                        log_content = f.read()[-10000:]
                
                log_text.insert('end', log_content)
                log_text.see('end')
                log_text.config(state='disabled')
            else:
                messagebox.showinfo("Bot Log", "Telegram bot log file not found.\nBot may not have started yet.")
        except Exception as e:
            logger.error(f"Failed to show bot log: {e}")
            messagebox.showerror("Error", f"Failed to show bot log: {e}")
    
    def run_audit_cycle(self):
        """Run an audit cycle."""
        if not self.audit_vector:
            messagebox.showwarning("Audit Vector", "Audit vector not initialized!")
            return
        
        try:
            self.update_status("Running audit cycle...")
            self.audit_vector._perform_audit_cycle()
            self.refresh_status()
            self.update_status("✅ Audit cycle completed")
        except Exception as e:
            self.update_status(f"❌ Audit failed: {e}")
            logger.error(f"Audit cycle failed: {e}")
    
    def check_health_status(self):
        """Check system health status."""
        try:
            self.update_status("Checking health status...")
            self.refresh_status()
            self.update_status("✅ Health status checked")
        except Exception as e:
            self.update_status(f"❌ Health check failed: {e}")
            logger.error(f"Health check failed: {e}")
    
    def refresh_logs(self):
        """Refresh system logs."""
        try:
            log_file = Path('mia_gui.log')
            if log_file.exists():
                # Try to read with UTF-8, fallback to CP1251 (Windows encoding)
                try:
                    with open(log_file, 'r', encoding='utf-8') as f:
                        log_content = f.read()[-5000:]  # Last 5000 chars
                except UnicodeDecodeError:
                    # Fallback to Windows encoding
                    with open(log_file, 'r', encoding='cp1251', errors='ignore') as f:
                        log_content = f.read()[-5000:]
                
                self.log_text.config(state='normal')
                self.log_text.delete('1.0', 'end')
                self.log_text.insert('end', log_content)
                self.log_text.see('end')
                self.log_text.config(state='disabled')
        except Exception as e:
            logger.error(f"Failed to refresh logs: {e}")
    
    def clear_logs(self):
        """Clear log display."""
        self.log_text.config(state='normal')
        self.log_text.delete('1.0', 'end')
        self.log_text.config(state='disabled')
    
    def export_logs(self):
        """Export logs to file."""
        try:
            from tkinter import filedialog
            file_path = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt")],
                initialfile="mia_logs.txt"
            )
            
            if file_path:
                log_file = Path('mia_gui.log')
                if log_file.exists():
                    with open(log_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    
                    self.update_status(f"✅ Logs exported to {file_path}")
        except Exception as e:
            self.update_status(f"❌ Export failed: {e}")
            logger.error(f"Log export failed: {e}")
    
    def update_status(self, message):
        """Update status bar."""
        self.status_var.set(message)
        logger.info(message)
    
    def update_system_info(self, message):
        """Update system information display."""
        self.system_info_var.set(message)
    
    def refresh_timer(self):
        """Refresh timer for periodic updates."""
        # Update time
        self.time_var.set(datetime.now().strftime('%H:%M:%S'))
        
        # Refresh status if system is running (but not Telegram chat to avoid jumping)
        if self.is_running:
            self.refresh_status()
            self.refresh_tasks()
            self.refresh_questions()
            # Don't auto-refresh Telegram chat to avoid scrolling issues
        
        # Schedule next refresh
        self.root.after(5000, self.refresh_timer)


def main():
    """Main function to run the GUI."""
    try:
        # Single instance enforcement - check BEFORE creating GUI
        instance_checker = SingleInstanceChecker()
        if not instance_checker.acquire_lock():
            # Show error using a temporary Tkinter root
            temp_root = tk.Tk()
            temp_root.withdraw()  # Hide the window
            error_msg = "Mia PM OS is already running!\n\n"
            error_msg += "Only one instance of Mia can be active at a time to prevent:\n"
            error_msg += "• VRAM conflicts on RTX 5060\n"
            error_msg += "• Database corruption\n"
            error_msg += "• Queue processing conflicts\n\n"
            error_msg += "Please close the existing instance first."
            messagebox.showerror("Mia Already Running", error_msg)
            temp_root.destroy()
            sys.exit(1)
        
        print("Starting Mia PM OS GUI...")
        root = tk.Tk()
        app = MiaGUI(root, instance_checker)
        print("GUI initialized successfully")
        root.mainloop()
        print("GUI closed")
    except Exception as e:
        print(f"GUI Error: {e}")
        import traceback
        traceback.print_exc()
        messagebox.showerror("GUI Error", f"Failed to start GUI: {e}")


if __name__ == "__main__":
    main()