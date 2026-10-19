"""Tests for queue management and VRAM policy"""

import pytest
import time
import threading
from datetime import datetime, timedelta
from app.modules.storage.database import (
    initialize_database, enqueue_task, get_next_pending_task,
    update_task_status, get_queue_statistics, insert_project
)
from app.workers.worker_pool import (
    SingleThreadedWorkerPool, WorkerState, PriorityAwareScheduler
)
from app.modules.vram_policy import (
    VRAMManagementPolicy, ExecutionMode, ModelSlot
)


class TestDatabaseQueue:
    """Tests for database queue operations."""
    
    @pytest.fixture(autouse=True)
    def setup_database(self):
        """Initialize and clean database before each test."""
        initialize_database()
        # Clean up existing test data
        import sqlite3
        from app.modules.storage.database import DB_PATH
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM llm_task_queue WHERE task_id LIKE 'TASK-%'")
        cursor.execute("DELETE FROM projects WHERE project_id LIKE 'PROJ-%'")
        conn.commit()
        conn.close()
        yield
        # Cleanup could be added here if needed
    
    def test_enqueue_task(self):
        """Test task enqueuing."""
        task_data = {
            'task_id': 'TASK-TEST-001',
            'task_type': 'tool_call',
            'priority': 8,
            'system_current_time': datetime.now(),
            'user_message': 'Test message',
            'telegram_chat_id': -1001234567890,
            'user_id': 123456789
        }
        
        result = enqueue_task(task_data)
        assert result is True
    
    def test_enqueue_duplicate_task(self):
        """Test that duplicate task IDs are rejected."""
        task_data = {
            'task_id': 'TASK-TEST-002',
            'task_type': 'tool_call',
            'priority': 8,
            'system_current_time': datetime.now(),
            'user_message': 'Test message',
            'telegram_chat_id': -1001234567890,
            'user_id': 123456789
        }
        
        # First enqueue should succeed
        assert enqueue_task(task_data) is True
        
        # Second enqueue with same ID should fail
        assert enqueue_task(task_data) is False
    
    def test_get_next_pending_task(self):
        """Test retrieving next pending task."""
        # Enqueue multiple tasks with different priorities
        tasks = [
            {
                'task_id': 'TASK-PRIORITY-LOW',
                'task_type': 'tool_call',
                'priority': 3,
                'system_current_time': datetime.now(),
                'user_message': 'Low priority task',
                'telegram_chat_id': -1001234567890,
                'user_id': 123456789
            },
            {
                'task_id': 'TASK-PRIORITY-HIGH',
                'task_type': 'tool_call',
                'priority': 10,
                'system_current_time': datetime.now(),
                'user_message': 'High priority task',
                'telegram_chat_id': -1001234567890,
                'user_id': 123456789
            }
        ]
        
        for task in tasks:
            enqueue_task(task)
        
        # Should get highest priority task first
        next_task = get_next_pending_task()
        assert next_task is not None
        assert next_task['task_id'] == 'TASK-PRIORITY-HIGH'
        assert next_task['priority'] == 10
    
    def test_update_task_status(self):
        """Test updating task status."""
        task_data = {
            'task_id': 'TASK-STATUS-001',
            'task_type': 'tool_call',
            'priority': 5,
            'system_current_time': datetime.now(),
            'user_message': 'Status test task',
            'telegram_chat_id': -1001234567890,
            'user_id': 123456789
        }
        
        enqueue_task(task_data)
        
        # Update to processing
        assert update_task_status('TASK-STATUS-001', 'processing') is True
        
        # Update to completed
        assert update_task_status('TASK-STATUS-001', 'completed', result='Success') is True
    
    def test_queue_statistics(self):
        """Test queue statistics."""
        stats = get_queue_statistics()
        
        # Should have all keys
        assert 'pending' in stats
        assert 'processing' in stats
        assert 'completed' in stats
        assert 'failed' in stats
        
        # Should be non-negative
        for key, value in stats.items():
            assert value >= 0
    
    def test_project_insertion(self):
        """Test project insertion."""
        project_data = {
            'project_id': 'PROJ-TEST-001',
            'project_name': 'Test Project',
            'telegram_chat_id': -1001234567890,
            'google_drive_folder_id': '1AbCdEfGhIjKlMnOpQrStUvWxYz'
        }
        
        result = insert_project(project_data)
        assert result is True


class TestWorkerPool:
    """Tests for single-threaded worker pool."""
    
    @pytest.fixture(autouse=True)
    def setup_database(self):
        """Initialize database before each test."""
        initialize_database()
        yield
    
    def test_worker_pool_initialization(self):
        """Test worker pool initialization."""
        def dummy_handler(task):
            return {"status": "success"}
        
        worker = SingleThreadedWorkerPool(
            task_handler=dummy_handler,
            max_concurrent_tasks=1,
            poll_interval=0.1
        )
        
        assert worker.state == WorkerState.IDLE
        assert worker.max_concurrent_tasks == 1
    
    def test_worker_pool_start_stop(self):
        """Test starting and stopping worker pool."""
        def dummy_handler(task):
            return {"status": "success"}
        
        worker = SingleThreadedWorkerPool(
            task_handler=dummy_handler,
            max_concurrent_tasks=1,
            poll_interval=0.1
        )
        
        # Start worker
        assert worker.start() is True
        assert worker.state == WorkerState.IDLE
        assert worker.worker_thread.is_alive()
        
        # Stop worker
        assert worker.stop(graceful=True) is True
        # Give it a moment to stop
        time.sleep(0.2)
        assert worker.state == WorkerState.STOPPED
    
    def test_worker_pool_pause_resume(self):
        """Test pausing and resuming worker pool."""
        def dummy_handler(task):
            return {"status": "success"}
        
        worker = SingleThreadedWorkerPool(
            task_handler=dummy_handler,
            max_concurrent_tasks=1,
            poll_interval=0.1
        )
        
        worker.start()
        
        # Pause worker
        assert worker.pause() is True
        assert worker.state == WorkerState.PAUSED
        
        # Resume worker
        assert worker.resume() is True
        assert worker.state == WorkerState.IDLE
        
        worker.stop()
    
    def test_worker_pool_task_processing(self):
        """Test actual task processing."""
        def test_handler(task):
            time.sleep(0.1)  # Simulate processing
            return {"task_id": task['task_id'], "processed": True}
        
        worker = SingleThreadedWorkerPool(
            task_handler=test_handler,
            max_concurrent_tasks=1,
            poll_interval=0.05
        )
        
        # Enqueue a task
        task_data = {
            'task_id': 'TASK-PROCESS-001',
            'task_type': 'tool_call',
            'priority': 8,
            'system_current_time': datetime.now(),
            'user_message': 'Process this task',
            'telegram_chat_id': -1001234567890,
            'user_id': 123456789
        }
        
        enqueue_task(task_data)
        
        # Start worker
        worker.start()
        
        # Wait for processing
        time.sleep(1)
        
        # Check status
        status = worker.get_status()
        assert status['tasks_processed'] >= 1
        
        worker.stop()
    
    def test_worker_pool_status(self):
        """Test worker pool status reporting."""
        def dummy_handler(task):
            return {"status": "success"}
        
        worker = SingleThreadedWorkerPool(
            task_handler=dummy_handler,
            max_concurrent_tasks=1,
            poll_interval=0.1
        )
        
        status = worker.get_status()
        
        assert 'state' in status
        assert 'current_task_id' in status
        assert 'tasks_processed' in status
        assert 'tasks_failed' in status
        assert 'queue_statistics' in status


class TestPriorityScheduler:
    """Tests for priority-aware scheduler."""
    
    def test_priority_score_calculation(self):
        """Test priority score calculation."""
        scheduler = PriorityAwareScheduler()
        
        # High priority task
        high_priority_task = {
            'priority': 10,
            'queued_at': datetime.now()
        }
        high_score = scheduler.calculate_task_score(high_priority_task)
        
        # Low priority task
        low_priority_task = {
            'priority': 1,
            'queued_at': datetime.now()
        }
        low_score = scheduler.calculate_task_score(low_priority_task)
        
        # High priority should have higher score
        assert high_score > low_score
    
    def test_preemption_logic(self):
        """Test task preemption logic."""
        scheduler = PriorityAwareScheduler()
        
        current_task = {'priority': 5}
        new_critical_task = {'priority': 10}
        new_normal_task = {'priority': 5}
        
        # Critical task should preempt normal task
        assert scheduler.should_preempt(current_task, new_critical_task) is True
        
        # Normal task should not preempt same priority
        assert scheduler.should_preempt(current_task, new_normal_task) is False
    
    def test_age_based_priority(self):
        """Test that older tasks get slight priority boost."""
        from datetime import timedelta
        scheduler = PriorityAwareScheduler()
        
        # Old task (queued 2 minutes ago)
        old_task = {
            'priority': 5,
            'queued_at': datetime.now() - timedelta(minutes=2)
        }
        
        # New task (just queued)
        new_task = {
            'priority': 5,
            'queued_at': datetime.now()
        }
        
        old_score = scheduler.calculate_task_score(old_task)
        new_score = scheduler.calculate_task_score(new_task)
        
        # Old task should have slightly higher score due to age
        assert old_score > new_score


class TestVRAMPolicy:
    """Tests for VRAM management policy."""
    
    def test_vram_policy_initialization(self):
        """Test VRAM policy initialization."""
        policy = VRAMManagementPolicy()
        
        assert policy.execution_mode in [ExecutionMode.DAYTIME, ExecutionMode.NIGHTTIME]
        assert policy.max_concurrent_models == 1
        assert len(policy.current_loaded_models) == 0
    
    def test_execution_mode_determination(self):
        """Test execution mode determination based on time."""
        policy = VRAMManagementPolicy()
        
        # Just check that it returns a valid mode
        assert policy.execution_mode in [ExecutionMode.DAYTIME, ExecutionMode.NIGHTTIME]
    
    def test_model_slot_acquisition(self):
        """Test model slot acquisition."""
        policy = VRAMManagementPolicy()
        
        # Acquire chat model slot
        assert policy.acquire_model_slot(ModelSlot.CHAT_MODEL, "qwen3:14b") is True
        assert ModelSlot.CHAT_MODEL in policy.current_loaded_models
        
        # Try to acquire another slot (should fail due to limit)
        assert policy.acquire_model_slot(ModelSlot.VISION_MODEL, "qwen2.5-vl:7b") is False
    
    def test_heavy_vision_monopoly(self):
        """Test that HEAVY_VISION has monopoly."""
        policy = VRAMManagementPolicy()
        
        # First acquire a regular slot
        policy.acquire_model_slot(ModelSlot.CHAT_MODEL, "qwen3:14b")
        
        # Clear cooldown to allow immediate switch
        policy.last_model_switch = None
        
        # HEAVY_VISION should acquire monopoly and clear other slots
        assert policy.acquire_model_slot(ModelSlot.HEAVY_VISION, "qwen2.5-vl:7b") is True
        assert ModelSlot.CHAT_MODEL not in policy.current_loaded_models
        assert ModelSlot.HEAVY_VISION in policy.current_loaded_models
    
    def test_model_slot_release(self):
        """Test model slot release."""
        policy = VRAMManagementPolicy()
        
        # Acquire and release
        policy.acquire_model_slot(ModelSlot.CHAT_MODEL, "qwen3:14b")
        assert policy.release_model_slot(ModelSlot.CHAT_MODEL) is True
        assert ModelSlot.CHAT_MODEL not in policy.current_loaded_models
    
    def test_vram_limit_check(self):
        """Test VRAM limit checking."""
        policy = VRAMManagementPolicy()
        
        # Normal usage should pass
        policy.update_vram_usage(8192)
        assert policy.check_vram_limit(16384) is True
        
        # Excessive usage should fail
        policy.update_vram_usage(20000)
        assert policy.check_vram_limit(16384) is False
    
    def test_model_selection_for_task(self):
        """Test model selection based on task priority."""
        policy = VRAMManagementPolicy()
        
        # High priority tasks should use chat model
        model = policy.get_model_for_task(10)
        assert model == policy.get_current_model()
        
        # In nighttime, low priority should use vision
        policy.execution_mode = ExecutionMode.NIGHTTIME
        model = policy.get_model_for_task(1)
        # The vision model name contains "vl" (vision language) not "vision"
        assert "vl" in model.lower() or "vision" in model.lower()
    
    def test_vram_policy_status(self):
        """Test VRAM policy status reporting."""
        policy = VRAMManagementPolicy()
        
        status = policy.get_status()
        
        assert 'execution_mode' in status
        assert 'current_loaded_models' in status
        assert 'current_vram_usage_mb' in status
        assert 'priority_execution_policy' in status


if __name__ == "__main__":
    pytest.main([__file__, "-v"])