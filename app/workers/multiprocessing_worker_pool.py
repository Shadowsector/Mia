"""Multiprocessing Worker Pool - Parallel task execution with VRAM safety.

This module implements a multiprocessing worker pool that:
- Uses multiple processes for CPU-intensive tasks (document parsing)
- Uses single process for LLM tasks (VRAM safety)
- Uses task queue with priority handling
"""

import logging
import multiprocessing as mp
from typing import Optional, Callable, Dict, Any, List
from datetime import datetime
from enum import Enum
import queue
import time

from app.modules.storage.database import get_next_pending_task, update_task_status, get_queue_statistics
from app.modules.storage.questions_gateway import QuestionsGateway

logger = logging.getLogger(__name__)


class TaskType(str, Enum):
    """Types of tasks."""
    LLM = "llm"  # LLM inference (single process for VRAM safety)
    CPU = "cpu"  # CPU-intensive (document parsing, etc. - multiple processes)
    IO = "io"  # I/O operations (file reading, network - moderate parallelism)


class WorkerState(str, Enum):
    """Worker states."""
    IDLE = "idle"
    PROCESSING = "processing"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


class MultiprocessingWorkerPool:
    """
    Multiprocessing worker pool with VRAM-safe LLM handling.
    
    Architecture:
    - LLM tasks: Single process (VRAM safety)
    - CPU tasks: Multiple processes (4-8 for document parsing)
    - IO tasks: Moderate parallelism (2-4 processes)
    """
    
    def __init__(self,
                 llm_handler: Callable[[Dict[str, Any]], Dict[str, Any]],
                 cpu_handler: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
                 io_handler: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
                 llm_processes: int = 1,  # Single LLM process for VRAM safety
                 cpu_processes: int = 4,  # 4 CPU processes for document parsing
                 io_processes: int = 2,  # 2 IO processes
                 poll_interval: float = 1.0,
                 questions_gateway: Optional[QuestionsGateway] = None):
        """
        Initialize multiprocessing worker pool.
        
        Args:
            llm_handler: Handler for LLM tasks
            cpu_handler: Handler for CPU-intensive tasks
            io_handler: Handler for I/O tasks
            llm_processes: Number of LLM processes (default 1 for VRAM safety)
            cpu_processes: Number of CPU processes (default 4)
            io_processes: Number of IO processes (default 2)
            poll_interval: Queue poll interval
            questions_gateway: Questions Gateway instance
        """
        self.llm_handler = llm_handler
        self.cpu_handler = cpu_handler
        self.io_handler = io_handler
        self.llm_processes = llm_processes
        self.cpu_processes = cpu_processes
        self.io_processes = io_processes
        self.poll_interval = poll_interval
        self.questions_gateway = questions_gateway
        
        self.state = WorkerState.IDLE
        self.stop_event = mp.Event()
        self.pause_event = mp.Event()
        
        # Task queues
        self.llm_queue = mp.Queue()
        self.cpu_queue = mp.Queue()
        self.io_queue = mp.Queue()
        
        # Result queues
        self.llm_result_queue = mp.Queue()
        self.cpu_result_queue = mp.Queue()
        self.io_result_queue = mp.Queue()
        
        # Worker processes
        self.llm_workers: List[mp.Process] = []
        self.cpu_workers: List[mp.Process] = []
        self.io_workers: List[mp.Process] = []
        
        # Statistics
        self.tasks_processed = 0
        self.tasks_failed = 0
        self.tasks_suspended = 0
        self.last_error: Optional[str] = None
        
        logger.info(f"MultiprocessingWorkerPool initialized: LLM={llm_processes}, CPU={cpu_processes}, IO={io_processes}")
    
    def _llm_worker(self, worker_id: int):
        """LLM worker process (single process for VRAM safety)."""
        logger.info(f"LLM worker {worker_id} started")
        
        while not self.stop_event.is_set():
            try:
                # Check pause
                if self.pause_event.is_set():
                    time.sleep(0.1)
                    continue
                
                # Get task from queue with timeout
                try:
                    task = self.llm_queue.get(timeout=1.0)
                except queue.Empty:
                    continue
                
                # Process task
                task_id = task.get('task_id')
                logger.info(f"LLM worker {worker_id} processing task {task_id}")
                
                try:
                    # Update status to processing
                    update_task_status(task_id, 'processing')
                    
                    # Handle task
                    result = self.llm_handler(task)
                    
                    # Update status to completed
                    update_task_status(task_id, 'completed', result)
                    
                    # Put result in result queue
                    self.llm_result_queue.put({
                        'task_id': task_id,
                        'result': result,
                        'success': True
                    })
                    
                    self.tasks_processed += 1
                    
                except Exception as e:
                    logger.error(f"LLM worker {worker_id} error processing task {task_id}: {e}")
                    update_task_status(task_id, 'failed', {'error': str(e)})
                    self.llm_result_queue.put({
                        'task_id': task_id,
                        'error': str(e),
                        'success': False
                    })
                    self.tasks_failed += 1
                    self.last_error = str(e)
                
            except Exception as e:
                logger.error(f"LLM worker {worker_id} error: {e}")
                break
        
        logger.info(f"LLM worker {worker_id} stopped")
    
    def _cpu_worker(self, worker_id: int):
        """CPU worker process (multiple processes for parallelism)."""
        logger.info(f"CPU worker {worker_id} started")
        
        while not self.stop_event.is_set():
            try:
                # Check pause
                if self.pause_event.is_set():
                    time.sleep(0.1)
                    continue
                
                # Get task from queue with timeout
                try:
                    task = self.cpu_queue.get(timeout=1.0)
                except queue.Empty:
                    continue
                
                # Process task
                task_id = task.get('task_id')
                logger.info(f"CPU worker {worker_id} processing task {task_id}")
                
                try:
                    if self.cpu_handler:
                        result = self.cpu_handler(task)
                    else:
                        result = {'error': 'No CPU handler configured'}
                    
                    self.cpu_result_queue.put({
                        'task_id': task_id,
                        'result': result,
                        'success': True
                    })
                    
                    self.tasks_processed += 1
                    
                except Exception as e:
                    logger.error(f"CPU worker {worker_id} error processing task {task_id}: {e}")
                    self.cpu_result_queue.put({
                        'task_id': task_id,
                        'error': str(e),
                        'success': False
                    })
                    self.tasks_failed += 1
                
            except Exception as e:
                logger.error(f"CPU worker {worker_id} error: {e}")
                break
        
        logger.info(f"CPU worker {worker_id} stopped")
    
    def _io_worker(self, worker_id: int):
        """IO worker process."""
        logger.info(f"IO worker {worker_id} started")
        
        while not self.stop_event.is_set():
            try:
                # Check pause
                if self.pause_event.is_set():
                    time.sleep(0.1)
                    continue
                
                # Get task from queue with timeout
                try:
                    task = self.io_queue.get(timeout=1.0)
                except queue.Empty:
                    continue
                
                # Process task
                task_id = task.get('task_id')
                logger.info(f"IO worker {worker_id} processing task {task_id}")
                
                try:
                    if self.io_handler:
                        result = self.io_handler(task)
                    else:
                        result = {'error': 'No IO handler configured'}
                    
                    self.io_result_queue.put({
                        'task_id': task_id,
                        'result': result,
                        'success': True
                    })
                    
                    self.tasks_processed += 1
                    
                except Exception as e:
                    logger.error(f"IO worker {worker_id} error processing task {task_id}: {e}")
                    self.io_result_queue.put({
                        'task_id': task_id,
                        'error': str(e),
                        'success': False
                    })
                    self.tasks_failed += 1
                
            except Exception as e:
                logger.error(f"IO worker {worker_id} error: {e}")
                break
        
        logger.info(f"IO worker {worker_id} stopped")
    
    def _dispatcher(self):
        """Dispatcher thread that routes tasks to appropriate queues."""
        logger.info("Dispatcher started")
        
        while not self.stop_event.is_set():
            try:
                # Check pause
                if self.pause_event.is_set():
                    time.sleep(0.1)
                    continue
                
                # Get next task from database
                task = get_next_pending_task()
                
                if not task:
                    time.sleep(self.poll_interval)
                    continue
                
                # Determine task type
                task_type = task.get('task_type', 'llm')
                priority = task.get('priority', 5)
                
                # Route to appropriate queue
                if task_type == TaskType.LLM.value:
                    self.llm_queue.put(task)
                elif task_type == TaskType.CPU.value:
                    self.cpu_queue.put(task)
                elif task_type == TaskType.IO.value:
                    self.io_queue.put(task)
                else:
                    # Default to LLM
                    self.llm_queue.put(task)
                
                logger.debug(f"Routed task {task.get('task_id')} to {task_type} queue")
                
            except Exception as e:
                logger.error(f"Dispatcher error: {e}")
                time.sleep(self.poll_interval)
        
        logger.info("Dispatcher stopped")
    
    def start(self) -> bool:
        """Start the multiprocessing worker pool."""
        if self.state != WorkerState.IDLE and self.state != WorkerState.STOPPED:
            logger.warning(f"Worker pool already in state: {self.state}")
            return False
        
        self.state = WorkerState.IDLE
        self.stop_event.clear()
        self.pause_event.clear()
        
        # Start LLM workers (single process for VRAM safety)
        for i in range(self.llm_processes):
            worker = mp.Process(target=self._llm_worker, args=(i,))
            worker.start()
            self.llm_workers.append(worker)
        
        # Start CPU workers (multiple processes for parallelism)
        for i in range(self.cpu_processes):
            worker = mp.Process(target=self._cpu_worker, args=(i,))
            worker.start()
            self.cpu_workers.append(worker)
        
        # Start IO workers
        for i in range(self.io_processes):
            worker = mp.Process(target=self._io_worker, args=(i,))
            worker.start()
            self.io_workers.append(worker)
        
        # Start dispatcher thread
        self.dispatcher_thread = mp.Process(target=self._dispatcher)
        self.dispatcher_thread.start()
        
        logger.info("Multiprocessing worker pool started")
        return True
    
    def stop(self, graceful: bool = True) -> bool:
        """
        Stop the worker pool.
        
        Args:
            graceful: If True, wait for current tasks to complete
        """
        if self.state == WorkerState.STOPPED:
            logger.warning("Worker pool already stopped")
            return False
        
        logger.info(f"Stopping worker pool (graceful={graceful})")
        
        self.stop_event.set()
        
        if graceful:
            # Wait for workers to finish
            timeout = 60  # 1 minute max wait
            start_time = time.time()
            
            for worker in self.llm_workers + self.cpu_workers + self.io_workers:
                if worker.is_alive():
                    worker.join(timeout=timeout)
            
            if self.dispatcher_thread.is_alive():
                self.dispatcher_thread.join(timeout=timeout)
        else:
            # Terminate immediately
            for worker in self.llm_workers + self.cpu_workers + self.io_workers:
                if worker.is_alive():
                    worker.terminate()
            
            if self.dispatcher_thread.is_alive():
                self.dispatcher_thread.terminate()
        
        self.state = WorkerState.STOPPED
        logger.info("Worker pool stopped")
        return True
    
    def pause(self) -> bool:
        """Pause the worker pool."""
        if self.state == WorkerState.PROCESSING:
            self.pause_event.set()
            self.state = WorkerState.PAUSED
            logger.info("Worker pool paused")
            return True
        return False
    
    def resume(self) -> bool:
        """Resume the worker pool."""
        if self.state == WorkerState.PAUSED:
            self.pause_event.clear()
            self.state = WorkerState.PROCESSING
            logger.info("Worker pool resumed")
            return True
        return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get worker pool status."""
        return {
            'state': self.state.value,
            'llm_workers': len(self.llm_workers),
            'cpu_workers': len(self.cpu_workers),
            'io_workers': len(self.io_workers),
            'tasks_processed': self.tasks_processed,
            'tasks_failed': self.tasks_failed,
            'tasks_suspended': self.tasks_suspended,
            'last_error': self.last_error,
            'llm_queue_size': self.llm_queue.qsize(),
            'cpu_queue_size': self.cpu_queue.qsize(),
            'io_queue_size': self.io_queue.qsize()
        }


# Backward compatibility: use SingleThreadedWorkerPool as default
from app.workers.worker_pool import SingleThreadedWorkerPool


if __name__ == "__main__":
    # Test Multiprocessing Worker Pool
    logging.basicConfig(level=logging.INFO)
    
    def dummy_llm_handler(task):
        return {'result': f"Processed {task.get('task_id')}"}
    
    pool = MultiprocessingWorkerPool(
        llm_handler=dummy_llm_handler,
        llm_processes=1,
        cpu_processes=2,
        io_processes=1
    )
    
    pool.start()
    
    time.sleep(2)
    
    status = pool.get_status()
    print(f"Status: {status}")
    
    pool.stop()
