"""Single-threaded worker pool for LLM task execution with priority handling"""

import threading
import time
import logging
from typing import Optional, Callable, Dict, Any
from datetime import datetime
from enum import Enum

from app.modules.storage.database import (
    get_next_pending_task, update_task_status, get_queue_statistics
)
from app.modules.storage.questions_gateway import QuestionsGateway

logger = logging.getLogger(__name__)


class WorkerState(str, Enum):
    IDLE = "idle"
    PROCESSING = "processing"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


class SingleThreadedWorkerPool:
    """
    Single-threaded worker pool for LLM task execution.
    
    This ensures zero VRAM collisions by only having one active LLM inference
    at a time. Tasks are processed based on priority (10=highest, 1=lowest).
    """
    
    def __init__(self, 
                 task_handler: Callable[[Dict[str, Any]], Dict[str, Any]],
                 max_concurrent_tasks: int = 1,
                 poll_interval: float = 1.0,
                 questions_gateway: Optional[QuestionsGateway] = None):
        """
        Initialize the worker pool.
        
        Args:
            task_handler: Function to process a task and return result
            max_concurrent_tasks: Maximum concurrent tasks (default 1 for VRAM safety)
            poll_interval: Seconds between queue polls
            questions_gateway: Questions Gateway instance for human intervention
        """
        self.task_handler = task_handler
        self.max_concurrent_tasks = max_concurrent_tasks
        self.poll_interval = poll_interval
        self.questions_gateway = questions_gateway
        
        self.state = WorkerState.IDLE
        self.current_task_id: Optional[str] = None
        self.worker_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        
        # Statistics
        self.tasks_processed = 0
        self.tasks_failed = 0
        self.tasks_suspended = 0
        self.total_processing_time = 0.0
        self.last_error: Optional[str] = None
        
        logger.info(f"SingleThreadedWorkerPool initialized with max_concurrent_tasks={max_concurrent_tasks}")
    
    def start(self) -> bool:
        """Start the worker pool."""
        if self.state != WorkerState.IDLE and self.state != WorkerState.STOPPED:
            logger.warning(f"Worker pool already in state: {self.state}")
            return False
        
        self.state = WorkerState.IDLE
        self.stop_event.clear()
        self.pause_event.clear()
        
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        
        logger.info("Worker pool started")
        return True
    
    def stop(self, graceful: bool = True) -> bool:
        """
        Stop the worker pool.
        
        Args:
            graceful: If True, wait for current task to complete before stopping
        """
        if self.state == WorkerState.STOPPED:
            logger.warning("Worker pool already stopped")
            return False
        
        logger.info(f"Stopping worker pool (graceful={graceful})")
        
        if graceful and self.state == WorkerState.PROCESSING:
            # Wait for current task to complete
            logger.info("Waiting for current task to complete...")
            timeout = 300  # 5 minutes max wait
            elapsed = 0
            while self.state == WorkerState.PROCESSING and elapsed < timeout:
                time.sleep(1)
                elapsed += 1
        
        self.stop_event.set()
        self.state = WorkerState.STOPPED
        
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
        
        logger.info("Worker pool stopped")
        return True
    
    def pause(self) -> bool:
        """Pause the worker pool (holds queue processing)."""
        if self.state == WorkerState.STOPPED:
            logger.warning("Cannot pause stopped worker pool")
            return False
        
        logger.info("Pausing worker pool")
        self.pause_event.set()
        self.state = WorkerState.PAUSED
        return True
    
    def resume(self) -> bool:
        """Resume the worker pool."""
        if self.state != WorkerState.PAUSED:
            logger.warning(f"Cannot resume worker pool in state: {self.state}")
            return False
        
        logger.info("Resuming worker pool")
        self.pause_event.clear()
        self.state = WorkerState.IDLE
        return True
    
    def get_status(self) -> Dict[str, Any]:
        """Get current worker pool status."""
        queue_stats = get_queue_statistics()
        
        return {
            "state": self.state.value,
            "current_task_id": self.current_task_id,
            "tasks_processed": self.tasks_processed,
            "tasks_failed": self.tasks_failed,
            "tasks_suspended": self.tasks_suspended,
            "total_processing_time": self.total_processing_time,
            "last_error": self.last_error,
            "queue_statistics": queue_stats,
            "is_running": self.worker_thread and self.worker_thread.is_alive(),
            "questions_gateway_enabled": self.questions_gateway is not None
        }
    
    def _worker_loop(self):
        """Main worker loop that processes tasks from the queue."""
        logger.info("Worker loop started")
        
        while not self.stop_event.is_set():
            try:
                # Check if paused
                if self.pause_event.is_set():
                    logger.debug("Worker paused, waiting...")
                    time.sleep(self.poll_interval)
                    continue
                
                # Get next pending task
                task = get_next_pending_task()
                
                if task is None:
                    # No tasks available, wait
                    if self.state == WorkerState.PROCESSING:
                        self.state = WorkerState.IDLE
                        self.current_task_id = None
                    time.sleep(self.poll_interval)
                    continue
                
                # Process the task
                self._process_task(task)
                
            except Exception as e:
                logger.error(f"Error in worker loop: {e}")
                self.last_error = str(e)
                self.state = WorkerState.ERROR
                time.sleep(self.poll_interval)
        
        logger.info("Worker loop stopped")
    
    def _process_task(self, task: Dict[str, Any]):
        """Process a single task."""
        task_id = task['task_id']
        priority = task['priority']
        
        logger.info(f"Processing task {task_id} (priority={priority})")
        
        self.state = WorkerState.PROCESSING
        self.current_task_id = task_id
        
        # Update task status to processing
        update_task_status(task_id, 'processing')
        
        start_time = time.time()
        
        try:
            # Check if this task requires human intervention via Questions Gateway
            if self.questions_gateway and self._requires_human_intervention(task):
                logger.info(f"Task {task_id} requires human intervention")
                
                # Suspend task and create question
                question_data = self._create_question_for_task(task)
                question_id = self.questions_gateway.ask_human(question_data)
                
                # Task is now suspended
                self.tasks_suspended += 1
                processing_time = time.time() - start_time
                self.total_processing_time += processing_time
                
                logger.info(f"Task {task_id} suspended for question {question_id}")
                return
            
            # Call the task handler
            result = self.task_handler(task)
            
            # Update task status to completed
            update_task_status(
                task_id, 
                'completed', 
                result=str(result) if result else None
            )
            
            self.tasks_processed += 1
            processing_time = time.time() - start_time
            self.total_processing_time += processing_time
            
            logger.info(f"Task {task_id} completed in {processing_time:.2f}s")
            
        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}")
            
            # Update task status to failed
            update_task_status(
                task_id, 
                'failed', 
                error_message=str(e)
            )
            
            self.tasks_failed += 1
            self.last_error = str(e)
            
        finally:
            self.state = WorkerState.IDLE
            self.current_task_id = None
    
    def _requires_human_intervention(self, task: Dict[str, Any]) -> bool:
        """
        Determine if task requires human intervention.
        
        This is a simple heuristic. In production, this would be more sophisticated
        based on task type, confidence scores, etc.
        """
        # For now, require intervention for financial decisions and permit issues
        task_type = task.get('task_type', '')
        user_intent = task.get('user_intent', '')
        
        intervention_triggers = [
            'financial',
            'budget',
            'permit',
            'conflict',
            'legal',
            'compliance'
        ]
        
        return any(trigger in task_type.lower() or trigger in user_intent.lower() 
                  for trigger in intervention_triggers)
    
    def _create_question_for_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Create a question data structure for human intervention."""
        task_id = task['task_id']
        user_intent = task.get('user_intent', 'unknown')
        project_id = task.get('project_id', 'unknown')
        
        # Determine question type based on intent
        if 'financial' in user_intent.lower() or 'budget' in user_intent.lower():
            question_type = "financial_decision"
            question_markdown = f"# Financial Decision Required\n\nTask {task_id} requires human approval for financial decision involving:\n\n{task.get('user_message', 'No details')}\n\n## Options:\n**(a)** Approve financial decision\n**(b)** Request additional information\n**(c)** Reject and escalate"
            option_a = "Approve financial decision"
            option_b = "Request additional information"
            option_c = "Reject and escalate"
        elif 'permit' in user_intent.lower():
            question_type = "permit_issue"
            question_markdown = f"# Permit Issue Detected\n\nTask {task_id} involves permit-related decision:\n\n{task.get('user_message', 'No details')}\n\n## Options:\n**(a)** Proceed with permit assumption\n**(b)** Request permit verification\n**(c)** Escalate to legal team"
            option_a = "Proceed with permit assumption"
            option_b = "Request permit verification"
            option_c = "Escalate to legal team"
        else:
            question_type = "general_conflict"
            question_markdown = f"# General Conflict Detected\n\nTask {task_id} requires human intervention:\n\n{task.get('user_message', 'No details')}\n\n## Options:\n**(a)** Proceed with recommended action\n**(b)** Request clarification\n**(c)** Manual override"
            option_a = "Proceed with recommended action"
            option_b = "Request clarification"
            option_c = "Manual override"
        
        return {
            "question_id": f"Q-{task_id}",
            "question_type": question_type,
            "priority": "high" if task.get('priority', 5) >= 8 else "normal",
            "project_id": project_id,
            "related_schema_type": "LLMTaskSchema",
            "related_entity_id": task_id,
            "question_markdown": question_markdown,
            "option_a": option_a,
            "option_b": option_b,
            "option_c": option_c,
            "suspended_task_id": task_id,
            "suspended_task_type": task.get('task_type', 'unknown')
        }


class PriorityAwareScheduler:
    """
    Priority-aware scheduler for task management.
    
    Ensures that higher priority tasks (10) are processed before lower priority tasks (1),
    while maintaining FIFO order within same priority level.
    """
    
    def __init__(self):
        self.priority_weights = {
            10: 1000,  # CRITICAL - highest weight
            8: 800,    # HIGH
            5: 500,    # NORMAL
            3: 300,    # LOW
            1: 100     # BACKGROUND - lowest weight
        }
    
    def calculate_task_score(self, task: Dict[str, Any]) -> float:
        """
        Calculate priority score for task.
        
        Higher score = higher priority.
        Factors: priority level, queue time.
        """
        priority = task.get('priority', 5)
        queued_at = task.get('queued_at', datetime.now())
        
        # Base score from priority
        base_score = self.priority_weights.get(priority, 500)
        
        # Add time-based component (older tasks get slight boost)
        time_delta = (datetime.now() - queued_at).total_seconds()
        time_bonus = min(time_delta / 60, 100)  # Max 100 points for age
        
        return base_score + time_bonus
    
    def should_preempt(self, current_task: Dict[str, Any], new_task: Dict[str, Any]) -> bool:
        """
        Determine if new task should preempt current task.
        
        Only allow preemption for CRITICAL priority (10) tasks.
        """
        current_priority = current_task.get('priority', 5)
        new_priority = new_task.get('priority', 5)
        
        # Only CRITICAL tasks can preempt
        if new_priority == 10 and current_priority < 10:
            logger.info(f"CRITICAL task preempts current task (priority {current_priority})")
            return True
        
        return False


def example_task_handler(task: Dict[str, Any]) -> Dict[str, Any]:
    """Example task handler for testing."""
    task_id = task['task_id']
    task_type = task['task_type']
    user_message = task['user_message']
    
    logger.info(f"Processing {task_type}: {user_message}")
    
    # Simulate processing time
    time.sleep(2)
    
    return {
        "task_id": task_id,
        "status": "success",
        "message": f"Processed task: {user_message}"
    }


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)
    
    # Create worker pool
    worker = SingleThreadedWorkerPool(
        task_handler=example_task_handler,
        max_concurrent_tasks=1,
        poll_interval=0.5
    )
    
    # Start worker
    worker.start()
    
    # Let it run for a bit
    time.sleep(10)
    
    # Check status
    status = worker.get_status()
    print(f"Worker status: {status}")
    
    # Stop worker
    worker.stop()