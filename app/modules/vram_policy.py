"""VRAM Management Policy for model switching and GPU resource control"""

import logging
import time
from datetime import datetime, time as dt_time
from typing import Optional, Dict, Any
from enum import Enum
from threading import Lock

logger = logging.getLogger(__name__)


class ExecutionMode(str, Enum):
    DAYTIME = "daytime"      # 07:00-19:00: Focus on real-time user interaction
    NIGHTTIME = "nighttime"  # 19:00-07:00: Focus on batch processing and vision


class ModelSlot(str, Enum):
    CHAT_MODEL = "chat_model"       # Primary chat model (qwen2.5-14b-instruct)
    CODER_MODEL = "coder_model"   # Coding model (merged with chat for VRAM efficiency)
    VISION_MODEL = "vision_model"   # Multimodal model (qwen2.5-vl:7b)
    HEAVY_VISION = "heavy_vision"   # Monopoly slot for night vision
    NONE = "none"                   # No model loaded


class VRAMManagementPolicy:
    """
    VRAM Management Policy for RTX 5060 single-GPU deployment.
    
    Enforces strict VRAM discipline with day/night mode switching
    and exclusive model slot management to prevent OOM errors.
    """
    
    def __init__(self,
                 daytime_model: str = "qwen2.5-14b-instruct",
                 nighttime_model: str = "qwen2.5-14b-instruct",
                 coder_model: str = "qwen2.5-14b-instruct",  # Merged with chat for VRAM efficiency
                 nighttime_vision_model: str = "qwen2.5-vl:7b",
                 max_concurrent_models: int = 1,  # Enforce single model for RTX 5060 16GB
                 model_switch_cooldown_seconds: int = 30,
                 vision_model_unload_threshold_hours: int = 6,
                 use_single_model: bool = True,  # Use single model for both chat and coding
                 target_vram_mb: int = 13000):  # Target 13GB to leave 3GB for system
        """
        Initialize VRAM management policy with RTX 5060 16GB optimization.
        
        Args:
            daytime_model: Primary model for daytime usage
            nighttime_model: Primary model for nighttime usage
            coder_model: Coding model (merged with chat by default for VRAM efficiency)
            nighttime_vision_model: Vision model for nighttime batch processing
            max_concurrent_models: Maximum models loaded simultaneously (default 1 for 16GB VRAM)
            model_switch_cooldown_seconds: Cooldown between model switches
            vision_model_unload_threshold_hours: Hours to keep vision loaded after use
            use_single_model: Use single model for both chat and coding (recommended for 16GB VRAM)
            target_vram_mb: Target VRAM usage in MB (13GB to leave 3GB for system)
        """
        self.daytime_model = daytime_model
        self.nighttime_model = nighttime_model
        self.coder_model = coder_model if not use_single_model else daytime_model
        self.nighttime_vision_model = nighttime_vision_model
        self.max_concurrent_models = max_concurrent_models
        self.model_switch_cooldown_seconds = model_switch_cooldown_seconds
        self.vision_model_unload_threshold_hours = vision_model_unload_threshold_hours
        self.use_single_model = use_single_model
        self.target_vram_mb = target_vram_mb
        
        # Current state
        self.execution_mode = self._determine_execution_mode()
        self.current_loaded_models: Dict[ModelSlot, str] = {}
        self.current_vram_usage_mb: Optional[int] = None
        self.last_mode_switch: Optional[datetime] = None
        self.last_model_switch: Optional[datetime] = None
        
        # Thread safety
        self._lock = Lock()
        
        # Priority execution policy mapping (updated for single model)
        self.priority_execution_policy = {
            10: "chat_model",  # Real-time admin tags → chat model
            8: "chat_model",   # User queries → chat model
            7: "chat_model",   # Coding tasks → chat model (single model mode)
            5: "chat_model",   # Summarization → chat model
            3: "vision_model", # Document analysis → vision (nighttime only)
            1: "heavy_vision"  # Night vision → monopoly slot
        }
        
        logger.info(f"VRAM Management Policy initialized in {self.execution_mode} mode")
        logger.info(f"Single model mode: {self.use_single_model}, Target VRAM: {self.target_vram_mb} MB")
    
    def _determine_execution_mode(self) -> ExecutionMode:
        """Determine current execution mode based on time of day."""
        now = datetime.now().time()
        morning = dt_time(7, 0)   # 07:00
        evening = dt_time(19, 0)  # 19:00
        
        if morning <= now < evening:
            return ExecutionMode.DAYTIME
        else:
            return ExecutionMode.NIGHTTIME
    
    def check_execution_mode_change(self) -> bool:
        """Check if execution mode should change (07:00 or 19:00)."""
        new_mode = self._determine_execution_mode()
        
        if new_mode != self.execution_mode:
            logger.info(f"Execution mode change detected: {self.execution_mode} -> {new_mode}")
            self.execution_mode = new_mode
            self.last_mode_switch = datetime.now()
            return True
        
        return False
    
    def get_current_model(self) -> str:
        """Get the appropriate model for current execution mode."""
        if self.use_single_model:
            # Use single model for both chat and coding
            return self.daytime_model
        elif self.execution_mode == ExecutionMode.DAYTIME:
            return self.daytime_model
        else:
            return self.nighttime_model
    
    def get_coder_model(self) -> str:
        """Get the coding model (merged with chat in single model mode)."""
        if self.use_single_model:
            return self.daytime_model
        return self.coder_model
    
    def should_use_vision_model(self, task_priority: int) -> bool:
        """
        Determine if task should use vision model.
        
        Vision model only available in nighttime mode for priority 1-3 tasks.
        """
        if self.execution_mode != ExecutionMode.NIGHTTIME:
            return False
        
        if task_priority in [1, 3]:
            return True
        
        return False
    
    def acquire_model_slot(self, model_type: ModelSlot, model_name: str) -> bool:
        """
        Acquire a model slot with VRAM discipline.
        
        Returns True if slot acquired, False if slot unavailable.
        """
        with self._lock:
            # Skip cooldown for HEAVY_VISION monopoly (urgent)
            if model_type != ModelSlot.HEAVY_VISION:
                # Check cooldown
                if self.last_model_switch:
                    cooldown_elapsed = (datetime.now() - self.last_model_switch).total_seconds()
                    if cooldown_elapsed < self.model_switch_cooldown_seconds:
                        logger.debug(f"Model switch cooldown: {cooldown_elapsed:.1f}s / {self.model_switch_cooldown_seconds}s")
                        return False
            
            # Check concurrent model limit
            if len(self.current_loaded_models) >= self.max_concurrent_models:
                # Special case: if requesting HEAVY_VISION slot, it has monopoly
                if model_type == ModelSlot.HEAVY_VISION:
                    # Unload all current models for monopoly
                    logger.info("HEAVY_VISION slot acquiring monopoly - unloading current models")
                    self.current_loaded_models.clear()
                else:
                    logger.warning(f"Cannot acquire slot {model_type}: max concurrent models reached")
                    return False
            
            # Acquire slot
            self.current_loaded_models[model_type] = model_name
            self.last_model_switch = datetime.now()
            
            logger.info(f"Acquired model slot {model_type} with model {model_name}")
            return True
    
    def release_model_slot(self, model_type: ModelSlot) -> bool:
        """Release a model slot."""
        with self._lock:
            if model_type in self.current_loaded_models:
                del self.current_loaded_models[model_type]
                logger.info(f"Released model slot {model_type}")
                return True
            return False
    
    def update_vram_usage(self, usage_mb: int):
        """Update current VRAM usage."""
        self.current_vram_usage_mb = usage_mb
        logger.debug(f"VRAM usage updated: {usage_mb} MB")
    
    def check_vram_limit(self, limit_mb: int = None) -> bool:
        """
        Check if VRAM usage is within limits.
        
        RTX 5060 has ~16GB VRAM. Use target_vram_mb or conservative default.
        """
        if limit_mb is None:
            limit_mb = self.target_vram_mb
        
        if self.current_vram_usage_mb is None:
            return True
        
        if self.current_vram_usage_mb > limit_mb:
            logger.warning(f"VRAM usage {self.current_vram_usage_mb} MB exceeds limit {limit_mb} MB")
            return False
        
        return True
    
    def unload_all_models(self) -> bool:
        """
        Unload all currently loaded models to free VRAM.
        
        Used when switching models or when VRAM is critically low.
        """
        with self._lock:
            if self.current_loaded_models:
                logger.info(f"Unloading all models: {list(self.current_loaded_models.keys())}")
                self.current_loaded_models.clear()
                self.current_vram_usage_mb = 0
                return True
            return False
    
    def get_model_for_task(self, task_priority: int, task_type: str = "chat") -> str:
        """
        Get the appropriate model for a task based on priority and execution mode.
        
        Args:
            task_priority: Task priority (1-10)
            task_type: Type of task ("chat", "coder", "vision")
            
        Returns:
            Model name to use
        """
        # Vision tasks are routed to the vision model even in single model mode:
        # the day/night pipeline is DAYTIME chat (qwen2.5:14b) / NIGHTTIME vision (qwen2.5-vl:7b)
        if self.should_use_vision_model(task_priority):
            return self.nighttime_vision_model

        # In single model mode, use the same model for everything else
        if self.use_single_model:
            return self.daytime_model

        # Otherwise, use task-specific models
        if task_type == "coder":
            return self.coder_model
        else:
            return self.get_current_model()
    
    def get_status(self) -> Dict[str, Any]:
        """Get current VRAM management status."""
        return {
            "execution_mode": self.execution_mode.value,
            "current_loaded_models": {slot.value: model for slot, model in self.current_loaded_models.items()},
            "current_vram_usage_mb": self.current_vram_usage_mb,
            "last_mode_switch": self.last_mode_switch.isoformat() if self.last_mode_switch else None,
            "last_model_switch": self.last_model_switch.isoformat() if self.last_model_switch else None,
            "current_model": self.get_current_model(),
            "coder_model": self.get_coder_model(),
            "vision_model_available": self.execution_mode == ExecutionMode.NIGHTTIME,
            "max_concurrent_models": self.max_concurrent_models,
            "priority_execution_policy": self.priority_execution_policy,
            "use_single_model": self.use_single_model,
            "target_vram_mb": self.target_vram_mb
        }
    
    def should_unload_vision_model(self) -> bool:
        """
        Check if vision model should be unloaded.
        
        Unload if not used for threshold hours or switching to daytime mode.
        """
        if self.execution_mode == ExecutionMode.DAYTIME:
            return True
        
        if ModelSlot.VISION_MODEL in self.current_loaded_models:
            if self.last_model_switch:
                hours_since_use = (datetime.now() - self.last_model_switch).total_seconds() / 3600
                if hours_since_use > self.vision_model_unload_threshold_hours:
                    logger.info(f"Vision model idle for {hours_since_use:.1f}h, unloading")
                    return True
        
        return False
    
    def switch_execution_mode(self, new_mode: ExecutionMode) -> bool:
        """
        Manually switch execution mode.
        
        Returns True if switch successful, False if cooldown not met.
        """
        if self.last_mode_switch:
            cooldown_elapsed = (datetime.now() - self.last_mode_switch).total_seconds()
            if cooldown_elapsed < self.model_switch_cooldown_seconds:
                logger.warning(f"Mode switch cooldown: {cooldown_elapsed:.1f}s / {self.model_switch_cooldown_seconds}s")
                return False
        
        logger.info(f"Manually switching execution mode: {self.execution_mode} -> {new_mode}")
        self.execution_mode = new_mode
        self.last_mode_switch = datetime.now()
        
        # Clear current models for clean switch
        with self._lock:
            self.current_loaded_models.clear()
        
        return True


class VRAMAwareWorkerPool:
    """
    Worker pool with VRAM awareness and automatic mode switching.
    
    Integrates VRAM management policy with task execution.
    """
    
    def __init__(self, 
                 task_handler,
                 vram_policy: VRAMManagementPolicy,
                 poll_interval: float = 1.0):
        """
        Initialize VRAM-aware worker pool.
        
        Args:
            task_handler: Function to process tasks
            vram_policy: VRAM management policy instance
            poll_interval: Queue poll interval
        """
        from app.workers.worker_pool import SingleThreadedWorkerPool
        
        self.task_handler = task_handler
        self.vram_policy = vram_policy
        self.worker_pool = SingleThreadedWorkerPool(
            task_handler=self._vram_aware_task_handler,
            max_concurrent_tasks=1,
            poll_interval=poll_interval
        )
        
        logger.info("VRAM-aware worker pool initialized")
    
    def _vram_aware_task_handler(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Task handler with VRAM awareness."""
        task_id = task['task_id']
        priority = task.get('priority', 5)
        
        # Check for mode changes
        self.vram_policy.check_execution_mode_change()
        
        # Get appropriate model for task
        model_name = self.vram_policy.get_model_for_task(priority)
        
        # Acquire model slot
        if priority == 1:
            model_slot = ModelSlot.HEAVY_VISION
        elif self.vram_policy.should_use_vision_model(priority):
            model_slot = ModelSlot.VISION_MODEL
        else:
            model_slot = ModelSlot.CHAT_MODEL
        
        if not self.vram_policy.acquire_model_slot(model_slot, model_name):
            raise Exception(f"Failed to acquire model slot {model_slot} for model {model_name}")
        
        try:
            # Call the actual task handler
            result = self.task_handler(task)
            return result
            
        finally:
            # Release model slot
            self.vram_policy.release_model_slot(model_slot)
            
            # Check if vision model should be unloaded
            if self.vram_policy.should_unload_vision_model():
                self.vram_policy.release_model_slot(ModelSlot.VISION_MODEL)
    
    def start(self):
        """Start the VRAM-aware worker pool."""
        self.worker_pool.start()
    
    def stop(self, graceful: bool = True):
        """Stop the VRAM-aware worker pool."""
        self.worker_pool.stop(graceful=graceful)
    
    def get_status(self) -> Dict[str, Any]:
        """Get combined status of worker pool and VRAM policy."""
        worker_status = self.worker_pool.get_status()
        vram_status = self.vram_policy.get_status()
        
        return {
            "worker": worker_status,
            "vram_policy": vram_status
        }


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)
    
    # Create VRAM policy
    vram_policy = VRAMManagementPolicy()
    
    # Create VRAM-aware worker pool
    worker = VRAMAwareWorkerPool(
        task_handler=None,  # Will use example handler
        vram_policy=vram_policy,
        poll_interval=1.0
    )
    
    # Start worker
    worker.start()
    
    # Check status
    status = worker.get_status()
    print(f"Status: {status}")
    
    # Let it run
    time.sleep(5)
    
    # Stop worker
    worker.stop()