"""Runtime Manager - Management of Mia PM OS system components.

This module provides centralized management for all system components:
- Telegram bot
- Worker pool
- LLM server (llama.cpp)
- Doctor observer
- Audit vector

Components are managed as subprocesses with PID tracking and status monitoring.
"""

import subprocess
import threading
import time
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class ComponentType(str, Enum):
    """Types of system components."""
    TELEGRAM_BOT = "telegram_bot"
    WORKER_POOL = "worker_pool"
    LLM_SERVER = "llm_server"
    DOCTOR_OBSERVER = "doctor_observer"
    AUDIT_VECTOR = "audit_vector"


class ComponentStatus(str, Enum):
    """Status of a component."""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


class RuntimeManager:
    """
    Central manager for all Mia PM OS system components.
    
    Manages subprocess lifecycle, PID tracking, status monitoring,
    and provides unified interface for GUI control.
    """
    
    def __init__(self, project_root: str = "C:/mia"):
        """
        Initialize Runtime Manager.
        
        Args:
            project_root: Root directory of the project
        """
        self.project_root = Path(project_root)
        self.runtime_file = self.project_root / "runtime.json"
        
        # Component processes: {component_type: (process, pid, start_time)}
        self.processes: Dict[ComponentType, tuple] = {}
        
        # Component configurations
        self.component_configs = {
            ComponentType.TELEGRAM_BOT: {
                "entry_point": self.project_root / "mia" / "bot" / "main.py",
                "python_path": r"C:\Users\MSI\AppData\Local\Programs\Python\Python312\python.exe",
                "env_vars": {}
            },
            ComponentType.WORKER_POOL: {
                "entry_point": self.project_root / "app" / "workers" / "worker_pool.py",
                "python_path": r"C:\Users\MSI\AppData\Local\Programs\Python\Python312\python.exe",
                "env_vars": {}
            },
            ComponentType.LLM_SERVER: {
                "entry_point": None,  # Managed by llama_cpp_manager
                "python_path": None,
                "env_vars": {}
            },
            ComponentType.DOCTOR_OBSERVER: {
                "entry_point": self.project_root / "app" / "modules" / "doctor" / "observer.py",
                "python_path": r"C:\Users\MSI\AppData\Local\Programs\Python\Python312\python.exe",
                "env_vars": {}
            },
            ComponentType.AUDIT_VECTOR: {
                "entry_point": self.project_root / "app" / "workers" / "audit_vector.py",
                "python_path": r"C:\Users\MSI\AppData\Local\Programs\Python\Python312\python.exe",
                "env_vars": {}
            }
        }
        
        # Load existing runtime state
        self._load_runtime_state()
        
        logger.info(f"RuntimeManager initialized with project_root={project_root}")
    
    def _load_runtime_state(self):
        """Load runtime state from runtime.json if exists."""
        if self.runtime_file.exists():
            try:
                with open(self.runtime_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                logger.info(f"Loaded runtime state: {state}")
            except Exception as e:
                logger.error(f"Failed to load runtime state: {e}")
    
    def _save_runtime_state(self):
        """Save current runtime state to runtime.json."""
        state = {
            "last_updated": datetime.now().isoformat(),
            "components": {}
        }
        
        for comp_type, (process, pid, start_time) in self.processes.items():
            state["components"][comp_type.value] = {
                "pid": pid,
                "status": "running" if process and process.poll() is None else "stopped",
                "start_time": start_time.isoformat() if start_time else None
            }
        
        try:
            with open(self.runtime_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
            logger.debug(f"Saved runtime state to {self.runtime_file}")
        except Exception as e:
            logger.error(f"Failed to save runtime state: {e}")
    
    def start_telegram_bot(self) -> bool:
        """
        Start Telegram bot as subprocess.
        
        Returns:
            True if started successfully, False otherwise
        """
        if ComponentType.TELEGRAM_BOT in self.processes:
            logger.warning("Telegram bot already running")
            return False
        
        config = self.component_configs[ComponentType.TELEGRAM_BOT]
        entry_point = config["entry_point"]
        python_path = config["python_path"]
        
        if not entry_point.exists():
            logger.error(f"Telegram bot entry point not found: {entry_point}")
            return False
        
        try:
            # Change to project directory to ensure correct imports
            cmd = [python_path, str(entry_point)]
            
            process = subprocess.Popen(
                cmd,
                cwd=str(self.project_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            self.processes[ComponentType.TELEGRAM_BOT] = (process, process.pid, datetime.now())
            self._save_runtime_state()
            
            logger.info(f"Telegram bot started with PID {process.pid}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start Telegram bot: {e}")
            return False
    
    def stop_telegram_bot(self) -> bool:
        """Stop Telegram bot subprocess."""
        return self._stop_component(ComponentType.TELEGRAM_BOT)
    
    def start_worker_pool(self) -> bool:
        """
        Start worker pool as subprocess.
        
        Note: Worker pool is currently embedded in application,
        but this provides foundation for standalone execution.
        """
        if ComponentType.WORKER_POOL in self.processes:
            logger.warning("Worker pool already running")
            return False
        
        config = self.component_configs[ComponentType.WORKER_POOL]
        entry_point = config["entry_point"]
        python_path = config["python_path"]
        
        if not entry_point.exists():
            logger.error(f"Worker pool entry point not found: {entry_point}")
            return False
        
        try:
            cmd = [python_path, str(entry_point)]
            
            process = subprocess.Popen(
                cmd,
                cwd=str(self.project_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            self.processes[ComponentType.WORKER_POOL] = (process, process.pid, datetime.now())
            self._save_runtime_state()
            
            logger.info(f"Worker pool started with PID {process.pid}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start worker pool: {e}")
            return False
    
    def stop_worker_pool(self) -> bool:
        """Stop worker pool subprocess."""
        return self._stop_component(ComponentType.WORKER_POOL)
    
    def start_doctor_observer(self) -> bool:
        """
        Start Doctor Observer as subprocess.
        
        The Doctor Observer monitors system health and detects anomalies.
        """
        if ComponentType.DOCTOR_OBSERVER in self.processes:
            logger.warning("Doctor Observer already running")
            return False
        
        config = self.component_configs[ComponentType.DOCTOR_OBSERVER]
        entry_point = config["entry_point"]
        python_path = config["python_path"]
        
        if not entry_point.exists():
            logger.error(f"Doctor Observer entry point not found: {entry_point}")
            return False
        
        try:
            cmd = [python_path, str(entry_point)]
            
            process = subprocess.Popen(
                cmd,
                cwd=str(self.project_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            self.processes[ComponentType.DOCTOR_OBSERVER] = (process, process.pid, datetime.now())
            self._save_runtime_state()
            
            logger.info(f"Doctor Observer started with PID {process.pid}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start Doctor Observer: {e}")
            return False
    
    def stop_doctor_observer(self) -> bool:
        """Stop Doctor Observer subprocess."""
        return self._stop_component(ComponentType.DOCTOR_OBSERVER)
    
    def start_audit_vector(self) -> bool:
        """
        Start Audit Vector as subprocess.
        
        The Audit Vector tracks system changes and maintains audit logs.
        """
        if ComponentType.AUDIT_VECTOR in self.processes:
            logger.warning("Audit Vector already running")
            return False
        
        config = self.component_configs[ComponentType.AUDIT_VECTOR]
        entry_point = config["entry_point"]
        python_path = config["python_path"]
        
        if not entry_point.exists():
            logger.error(f"Audit Vector entry point not found: {entry_point}")
            return False
        
        try:
            cmd = [python_path, str(entry_point)]
            
            process = subprocess.Popen(
                cmd,
                cwd=str(self.project_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            self.processes[ComponentType.AUDIT_VECTOR] = (process, process.pid, datetime.now())
            self._save_runtime_state()
            
            logger.info(f"Audit Vector started with PID {process.pid}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start Audit Vector: {e}")
            return False
    
    def stop_audit_vector(self) -> bool:
        """Stop Audit Vector subprocess."""
        return self._stop_component(ComponentType.AUDIT_VECTOR)
    
    def _stop_component(self, component_type: ComponentType) -> bool:
        """
        Generic component stop method.
        
        Args:
            component_type: Type of component to stop
            
        Returns:
            True if stopped successfully, False otherwise
        """
        if component_type not in self.processes:
            logger.warning(f"{component_type} not running")
            return False
        
        process, pid, start_time = self.processes[component_type]
        
        try:
            process.terminate()
            process.wait(timeout=10)
            logger.info(f"{component_type} stopped (PID {pid})")
        except subprocess.TimeoutExpired:
            logger.warning(f"{component_type} did not stop gracefully, killing")
            process.kill()
        except Exception as e:
            logger.error(f"Error stopping {component_type}: {e}")
        
        del self.processes[component_type]
        self._save_runtime_state()
        return True
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get status of all components.
        
        Returns:
            Dictionary with component statuses
        """
        status = {}
        
        for comp_type in ComponentType:
            if comp_type in self.processes:
                process, pid, start_time = self.processes[comp_type]
                if process.poll() is None:
                    status[comp_type.value] = {
                        "status": ComponentStatus.RUNNING.value,
                        "pid": pid,
                        "uptime": (datetime.now() - start_time).total_seconds() if start_time else 0,
                        "last_heartbeat": datetime.now().isoformat()
                    }
                else:
                    status[comp_type.value] = {
                        "status": ComponentStatus.ERROR.value,
                        "pid": pid,
                        "uptime": (datetime.now() - start_time).total_seconds() if start_time else 0,
                        "last_heartbeat": datetime.now().isoformat(),
                        "error_message": "Process terminated unexpectedly"
                    }
                    # Clean up dead process
                    del self.processes[comp_type]
            else:
                status[comp_type.value] = {
                    "status": ComponentStatus.STOPPED.value,
                    "pid": None,
                    "uptime": 0,
                    "last_heartbeat": None,
                    "error_message": None
                }
        
        return status
    
    def get_all_statuses(self) -> List[Dict[str, Any]]:
        """
        Get all component statuses as list for GUI display.
        
        Returns:
            List of component status dictionaries
        """
        from app.core.schemas import ComponentStatusSchema
        
        statuses = []
        status_dict = self.get_status()
        
        for comp_name, comp_status in status_dict.items():
            schema = ComponentStatusSchema(
                component_name=comp_name,
                status=comp_status["status"],
                pid=comp_status["pid"],
                uptime=comp_status["uptime"],
                last_heartbeat=comp_status["last_heartbeat"],
                error_message=comp_status["error_message"]
            )
            statuses.append(schema.model_dump())
        
        return statuses
    
    def start_all(self) -> bool:
        """
        Start all components in dependency order.
        
        Returns:
            True if all started successfully
        """
        # Start order: LLM first, then others
        components_order = [
            ComponentType.LLM_SERVER,  # May be started by GUI separately
            ComponentType.WORKER_POOL,
            ComponentType.TELEGRAM_BOT,
            ComponentType.DOCTOR_OBSERVER,
            ComponentType.AUDIT_VECTOR
        ]
        
        success = True
        for comp_type in components_order:
            if comp_type == ComponentType.LLM_SERVER:
                # LLM server is managed by llama_cpp_manager in GUI
                continue
            
            method_name = f"start_{comp_type.value}"
            if hasattr(self, method_name):
                if not getattr(self, method_name)():
                    logger.error(f"Failed to start {comp_type}")
                    success = False
        
        return success
    
    def stop_all(self) -> bool:
        """
        Stop all components in reverse order.
        
        Returns:
            True if all stopped successfully
        """
        # Stop in reverse order
        components_order = [
            ComponentType.AUDIT_VECTOR,
            ComponentType.DOCTOR_OBSERVER,
            ComponentType.TELEGRAM_BOT,
            ComponentType.WORKER_POOL,
            ComponentType.LLM_SERVER
        ]
        
        success = True
        for comp_type in components_order:
            if comp_type == ComponentType.LLM_SERVER:
                # LLM server is managed by llama_cpp_manager in GUI
                continue
            
            method_name = f"stop_{comp_type.value}"
            if hasattr(self, method_name):
                if not getattr(self, method_name)():
                    logger.error(f"Failed to stop {comp_type}")
                    success = False
        
        return success
    
    def cleanup_dead_processes(self):
        """Check for dead processes and clean up."""
        dead_components = []
        
        for comp_type, (process, pid, start_time) in self.processes.items():
            if process.poll() is not None:
                logger.warning(f"Dead process detected: {comp_type} (PID {pid})")
                dead_components.append(comp_type)
        
        for comp_type in dead_components:
            del self.processes[comp_type]
        
        if dead_components:
            self._save_runtime_state()
            logger.info(f"Cleaned up {len(dead_components)} dead processes")


if __name__ == "__main__":
    # Test Runtime Manager
    logging.basicConfig(level=logging.INFO)
    
    manager = RuntimeManager()
    
    # Test status
    status = manager.get_status()
    print("Status:", status)
    
    # Cleanup
    manager.cleanup_dead_processes()
