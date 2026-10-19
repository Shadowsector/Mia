"""Doctor Observer for autonomous health monitoring with Jaccard 3-grams and META_SLIP detection"""

import logging
import re
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Set
from enum import Enum
import threading
from collections import defaultdict, deque

from app.core.schemas import DoctorDiagnosisSchema, AnomalyType, AnomalySeverity
from app.modules.storage.database import get_db_connection
from app.modules.storage.questions_gateway import QuestionsGateway

logger = logging.getLogger(__name__)


class MetaSlipPattern(str, Enum):
    """Patterns that indicate AI assistant slips in construction context."""
    AS_AN_AI = "as an ai"
    AS_A_LANGUAGE_MODEL = "as a language model"
    I_CANNOT = "i cannot"
    MY_KNOWLEDGE = "my knowledge"
    I_DONT_HAVE = "i don't have"
    TRAINING_DATA = "training data"
    GENERATIVE_AI = "generative ai"
    MACHINE_LEARNING = "machine learning"


class DoctorObserver:
    """
    Doctor Observer for monitoring Mia's technical health.
    
    Lightweight background process that detects semantic repetition,
    META_SLIP (AI assistant slips in construction context), worker hangs,
    VRAM leaks, and response degradation.
    """
    
    def __init__(self, 
                 response_window_size: int = 10,
                 jaccard_threshold: float = 0.75,
                 hang_threshold_minutes: int = 10,
                 questions_gateway: Optional[QuestionsGateway] = None):
        """
        Initialize the Doctor Observer.
        
        Args:
            response_window_size: Number of recent responses to analyze
            jaccard_threshold: Jaccard similarity threshold for semantic repetition
            hang_threshold_minutes: Time threshold for worker hang detection
            questions_gateway: Questions Gateway for critical anomaly notifications
        """
        self.response_window_size = response_window_size
        self.jaccard_threshold = jaccard_threshold
        self.hang_threshold_minutes = hang_threshold_minutes
        self.questions_gateway = questions_gateway
        
        # Response tracking
        self.response_history: deque = deque(maxlen=response_window_size)
        self.response_timestamps: deque = deque(maxlen=response_window_size)
        
        # Task tracking
        self.task_start_times: Dict[str, datetime] = {}
        self.task_status_history: Dict[str, List[str]] = defaultdict(list)
        
        # Anomaly tracking
        self.anomalies_detected = 0
        self.critical_anomalies = 0
        self.last_diagnosis_time: Optional[datetime] = None
        
        # Observer state
        self.is_running = False
        self.observer_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        
        logger.info("Doctor Observer initialized")
    
    def start(self):
        """Start the doctor observer."""
        if self.is_running:
            logger.warning("Doctor Observer already running")
            return False
        
        self.is_running = True
        self.stop_event.clear()
        
        self.observer_thread = threading.Thread(target=self._observer_loop, daemon=True)
        self.observer_thread.start()
        
        logger.info("Doctor Observer started")
        return True
    
    def stop(self):
        """Stop the doctor observer."""
        if not self.is_running:
            logger.warning("Doctor Observer not running")
            return False
        
        logger.info("Stopping Doctor Observer")
        self.stop_event.set()
        self.is_running = False
        
        if self.observer_thread:
            self.observer_thread.join(timeout=30)
        
        logger.info("Doctor Observer stopped")
        return True
    
    def _observer_loop(self):
        """Main observer loop for health monitoring."""
        logger.info("Observer loop started")
        
        while not self.stop_event.is_set():
            try:
                # Perform health checks
                self._perform_health_checks()
                
                # Check for stale tasks (worker hangs)
                self._check_worker_hangs()
                
                # Wait before next cycle (check every minute)
                time.sleep(60)
                
            except Exception as e:
                logger.error(f"Error in observer loop: {e}")
                time.sleep(30)
        
        logger.info("Observer loop stopped")
    
    def _perform_health_checks(self):
        """Perform health checks on system state."""
        try:
            # Check for semantic repetition
            self._check_semantic_repetition()
            
            # Check for meta slips
            self._check_meta_slips()
            
            # Check for VRAM leaks (would need actual VRAM monitoring)
            self._check_vram_leaks()
            
            # Check for response degradation
            self._check_response_degradation()
            
            self.last_diagnosis_time = datetime.now()
            
        except Exception as e:
            logger.error(f"Error in health checks: {e}")
    
    def add_response(self, response: str, task_id: str, construction_context: str):
        """
        Add a response to the monitoring history.
        
        Args:
            response: The AI-generated response
            task_id: The task that generated this response
            construction_context: The construction context for this response
        """
        self.response_history.append({
            'response': response,
            'task_id': task_id,
            'context': construction_context,
            'timestamp': datetime.now()
        })
        self.response_timestamps.append(datetime.now())
        
        # Track task start time
        if task_id not in self.task_start_times:
            self.task_start_times[task_id] = datetime.now()
    
    def complete_task(self, task_id: str):
        """Mark a task as completed."""
        if task_id in self.task_start_times:
            del self.task_start_times[task_id]
    
    def _check_semantic_repetition(self):
        """Check for semantic repetition using Jaccard 3-gram similarity."""
        if len(self.response_history) < 3:
            return
        
        recent_responses = list(self.response_history)[-3:]
        
        for i in range(len(recent_responses) - 1):
            current = recent_responses[i]['response']
            next_response = recent_responses[i + 1]['response']
            
            jaccard_score = self._calculate_jaccard_3gram(current, next_response)
            
            if jaccard_score > self.jaccard_threshold:
                self._create_semantic_repetition_diagnosis(
                    recent_responses[i],
                    recent_responses[i + 1],
                    jaccard_score
                )
    
    def _calculate_jaccard_3gram(self, text1: str, text2: str) -> float:
        """Calculate Jaccard similarity using 3-grams."""
        def get_3grams(text: str) -> Set[str]:
            text = text.lower()
            return {text[i:i+3] for i in range(len(text) - 2)}
        
        if not text1 or not text2:
            return 0.0
        
        grams1 = get_3grams(text1)
        grams2 = get_3grams(text2)
        
        if not grams1 or not grams2:
            return 0.0
        
        intersection = grams1.intersection(grams2)
        union = grams1.union(grams2)
        
        return len(intersection) / len(union) if union else 0.0
    
    def _check_meta_slips(self):
        """Check for META_SLIP patterns in recent responses."""
        if not self.response_history:
            return
        
        for response_data in list(self.response_history)[-5:]:
            response = response_data['response']
            
            for pattern in MetaSlipPattern:
                if pattern.value in response.lower():
                    self._create_meta_slip_diagnosis(
                        response_data,
                        pattern.value
                    )
    
    def _check_worker_hangs(self):
        """Check for worker hangs (tasks stuck in processing)."""
        current_time = datetime.now()
        
        for task_id, start_time in list(self.task_start_times.items()):
            duration = (current_time - start_time).total_seconds() / 60  # Convert to minutes
            
            if duration > self.hang_threshold_minutes:
                self._create_worker_hang_diagnosis(
                    task_id,
                    int(duration)
                )
    
    def _check_vram_leaks(self):
        """Check for VRAM leaks (placeholder for actual VRAM monitoring)."""
        # This would require actual VRAM monitoring via nvidia-smi or similar
        # For now, we'll log a placeholder message
        logger.debug("VRAM leak check - would monitor GPU memory growth")
    
    def _check_response_degradation(self):
        """Check for response quality degradation."""
        if len(self.response_history) < 5:
            return
        
        recent_responses = list(self.response_history)[-5:]
        
        # Check for empty or very short responses
        for response_data in recent_responses:
            response = response_data['response']
            if len(response.strip()) < 10:
                self._create_response_degradation_diagnosis(
                    response_data,
                    "extremely_short_response"
                )
    
    def _create_semantic_repetition_diagnosis(self, 
                                            response1: Dict[str, Any],
                                            response2: Dict[str, Any],
                                            jaccard_score: float):
        """Create a diagnosis for semantic repetition."""
        try:
            diagnosis = DoctorDiagnosisSchema(
                diagnosis_id=f"DIAG-REP-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                anomaly_type=AnomalyType.SEMANTIC_REPETITION,
                severity=AnomalySeverity.HIGH,
                semantic_jaccard_score=jaccard_score,
                construction_context=response1.get('context', 'unknown'),
                related_project_id=None,
                affected_task_type=response1.get('task_id', 'unknown'),
                diagnosis_description=f"Detected semantic repetition in responses (Jaccard score: {jaccard_score:.2f}). Assistant appears stuck in paraphrase loop.",
                technical_details={
                    "response1": response1['response'][:200],  # Truncate for logging
                    "response2": response2['response'][:200],
                    "jaccard_score": jaccard_score,
                    "response1_task": response1['task_id'],
                    "response2_task": response2['task_id']
                },
                recommended_actions=[
                    "Reduce temperature parameter",
                    "Increase repeat_penalty",
                    "Force context refresh"
                ],
                parameter_adjustments={
                    "temperature": 0.5,
                    "repeat_penalty": 1.2
                },
                self_action_forbidden=True,
                requires_director_approval=True
            )
            
            self._process_diagnosis(diagnosis)
            
        except Exception as e:
            logger.error(f"Error creating semantic repetition diagnosis: {e}")
    
    def _create_meta_slip_diagnosis(self, 
                                   response_data: Dict[str, Any],
                                   pattern: str):
        """Create a diagnosis for META_SLIP detection."""
        try:
            diagnosis = DoctorDiagnosisSchema(
                diagnosis_id=f"DIAG-META-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                anomaly_type=AnomalyType.META_SLIP,
                severity=AnomalySeverity.MEDIUM,
                meta_slip_pattern=pattern,
                construction_context=response_data.get('context', 'unknown'),
                related_project_id=None,
                affected_task_type=response_data.get('task_id', 'unknown'),
                diagnosis_description=f"Detected META_SLIP pattern '{pattern}' in construction context. AI assistant revealed its nature instead of staying in character.",
                technical_details={
                    "meta_slip_pattern": pattern,
                    "response": response_data['response'][:200],
                    "task_id": response_data['task_id']
                },
                recommended_actions=[
                    "System prompt reinforcement",
                    "Context boundary enforcement",
                    "Character consistency check"
                ],
                parameter_adjustments={
                    "system_prompt_injection": "emphasize construction assistant role"
                },
                self_action_forbidden=True,
                requires_director_approval=False
            )
            
            self._process_diagnosis(diagnosis)
            
        except Exception as e:
            logger.error(f"Error creating meta slip diagnosis: {e}")
    
    def _create_worker_hang_diagnosis(self, task_id: str, duration_minutes: int):
        """Create a diagnosis for worker hang."""
        try:
            severity = AnomalySeverity.CRITICAL if duration_minutes > 30 else AnomalySeverity.HIGH
            
            diagnosis = DoctorDiagnosisSchema(
                diagnosis_id=f"DIAG-HANG-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                anomaly_type=AnomalyType.WORKER_HANG,
                severity=severity,
                worker_hang_duration_minutes=duration_minutes,
                construction_context=f"Task {task_id} processing",
                related_project_id=None,
                affected_task_type=task_id,
                diagnosis_description=f"Task {task_id} has been processing for {duration_minutes} minutes, exceeding threshold of {self.hang_threshold_minutes} minutes.",
                technical_details={
                    "task_id": task_id,
                    "duration_minutes": duration_minutes,
                    "threshold_minutes": self.hang_threshold_minutes
                },
                recommended_actions=[
                    "Manual task intervention",
                    "Worker pool restart",
                    "System resource check"
                ],
                parameter_adjustments={
                    "task_timeout": self.hang_threshold_minutes // 2
                },
                self_action_forbidden=True,
                requires_director_approval=True
            )
            
            self._process_diagnosis(diagnosis)
            
        except Exception as e:
            logger.error(f"Error creating worker hang diagnosis: {e}")
    
    def _create_response_degradation_diagnosis(self, 
                                             response_data: Dict[str, Any],
                                             degradation_type: str):
        """Create a diagnosis for response degradation."""
        try:
            diagnosis = DoctorDiagnosisSchema(
                diagnosis_id=f"DIAG-DEG-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                anomaly_type=AnomalyType.RESPONSE_DEGRADATION,
                severity=AnomalySeverity.MEDIUM,
                response_quality_score=0.3,  # Low quality score
                construction_context=response_data.get('context', 'unknown'),
                related_project_id=None,
                affected_task_type=response_data.get('task_id', 'unknown'),
                diagnosis_description=f"Response degradation detected: {degradation_type}. Response quality appears to be declining.",
                technical_details={
                    "degradation_type": degradation_type,
                    "response": response_data['response'][:200],
                    "task_id": response_data['task_id']
                },
                recommended_actions=[
                    "Temperature adjustment",
                    "Context refresh",
                    "Quality threshold enforcement"
                ],
                parameter_adjustments={
                    "temperature": 0.6,
                    "min_response_length": 20
                },
                self_action_forbidden=True,
                requires_director_approval=False
            )
            
            self._process_diagnosis(diagnosis)
            
        except Exception as e:
            logger.error(f"Error creating response degradation diagnosis: {e}")
    
    def _process_diagnosis(self, diagnosis: DoctorDiagnosisSchema):
        """Process a detected diagnosis."""
        try:
            # Persist diagnosis to database
            self._persist_diagnosis(diagnosis)
            
            # For critical/high severity, create question via Questions Gateway
            if diagnosis.severity in [AnomalySeverity.CRITICAL, AnomalySeverity.HIGH] and self.questions_gateway:
                self._create_critical_diagnosis_question(diagnosis)
            
            self.anomalies_detected += 1
            if diagnosis.severity == AnomalySeverity.CRITICAL:
                self.critical_anomalies += 1
            
            logger.info(f"Processed diagnosis: {diagnosis.diagnosis_id} ({diagnosis.severity.value})")
            
        except Exception as e:
            logger.error(f"Error processing diagnosis {diagnosis.diagnosis_id}: {e}")
    
    def _persist_diagnosis(self, diagnosis: DoctorDiagnosisSchema) -> bool:
        """Persist diagnosis to database."""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO doctor_diagnoses (
                        diagnosis_id, anomaly_type, severity,
                        semantic_jaccard_score, meta_slip_pattern,
                        worker_hang_duration_minutes, vram_growth_mb,
                        response_quality_score, construction_context,
                        related_project_id, affected_task_type,
                        diagnosis_description, technical_details,
                        recommended_actions, parameter_adjustments,
                        self_action_forbidden, requires_director_approval,
                        question_gateway_id, telegram_notification_sent,
                        detected_at, resolved_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    diagnosis.diagnosis_id,
                    diagnosis.anomaly_type.value,
                    diagnosis.severity.value,
                    diagnosis.semantic_jaccard_score,
                    diagnosis.meta_slip_pattern,
                    diagnosis.worker_hang_duration_minutes,
                    diagnosis.vram_growth_mb,
                    diagnosis.response_quality_score,
                    diagnosis.construction_context,
                    diagnosis.related_project_id,
                    diagnosis.affected_task_type,
                    diagnosis.diagnosis_description,
                    str(diagnosis.technical_details),
                    str(diagnosis.recommended_actions),
                    str(diagnosis.parameter_adjustments) if diagnosis.parameter_adjustments else None,
                    diagnosis.self_action_forbidden,
                    diagnosis.requires_director_approval,
                    diagnosis.question_gateway_id,
                    diagnosis.telegram_notification_sent,
                    diagnosis.detected_at.isoformat(),
                    diagnosis.resolved_at.isoformat() if diagnosis.resolved_at else None
                ))
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to persist diagnosis: {e}")
            return False
    
    def _create_critical_diagnosis_question(self, diagnosis: DoctorDiagnosisSchema):
        """Create a question for critical diagnoses following G8 principle."""
        try:
            # Build recommended actions text
            actions_text = "\n".join([f"- {action}" for action in diagnosis.recommended_actions])
            
            # Build parameter adjustments text if available
            params_text = ""
            if diagnosis.parameter_adjustments:
                params_text = f"\n## Recommended Parameter Changes:\n```\n{diagnosis.parameter_adjustments}\n```"
            
            question_data = {
                "question_id": f"Q-TECH-{diagnosis.diagnosis_id}",
                "question_type": f"doctor_{diagnosis.anomaly_type.value}",
                "priority": "critical" if diagnosis.severity == AnomalySeverity.CRITICAL else "high",
                "project_id": diagnosis.related_project_id or "SYSTEM",
                "related_schema_type": "DoctorDiagnosisSchema",
                "related_entity_id": diagnosis.diagnosis_id,
                "question_markdown": f"# G8 Principle: Technical Anomaly Detected\n\n**Severity:** {diagnosis.severity.value.upper()}\n**Anomaly Type:** {diagnosis.anomaly_type.value}\n\n{diagnosis.diagnosis_description}\n\n## Technical Details:\n```\n{diagnosis.technical_details}\n```\n\n## Recommended Actions:\n{actions_text}\n{params_text}\n\n## G8 Principle Compliance:\n- Doctor has **diagnosed** the issue\n- Doctor has **recommended** remediation steps\n- Doctor **cannot self-execute** the remediation\n- **Director approval required** for parameter changes\n\n## Options:\n**(a)** APPROVE - Apply recommended parameter changes (Director authorization)\n**(b)** DECLINE - Manual intervention required (Director will handle)\n**(c)** REQUEST MORE INFO - Additional diagnostic information needed",
                "option_a": "APPROVE - Apply recommended parameter changes",
                "option_b": "DECLINE - Manual intervention required",
                "option_c": "REQUEST MORE INFO - Additional diagnostics"
            }
            
            question_id = self.questions_gateway.ask_human(question_data)
            
            # Link question to diagnosis
            diagnosis.question_gateway_id = question_id
            self._persist_diagnosis(diagnosis)
            
            logger.info(f"Created G8-compliant diagnosis question: {question_id}")
            
        except Exception as e:
            logger.error(f"Failed to create G8-compliant diagnosis question: {e}")
    
    def apply_doctor_recommendations(self, diagnosis_id: str, approved: bool, approver: str) -> bool:
        """
        Apply doctor recommendations after director approval (G8 principle).
        
        Args:
            diagnosis_id: The diagnosis ID to apply recommendations for
            approved: Whether director approved the recommendations
            approver: The director who approved/declined
            
        Returns:
            True if recommendations applied successfully, False otherwise
        """
        try:
            if not approved:
                logger.info(f"Director {approver} declined recommendations for {diagnosis_id}")
                return False
            
            # Get diagnosis from database
            diagnosis = self._get_diagnosis(diagnosis_id)
            if not diagnosis:
                logger.error(f"Diagnosis {diagnosis_id} not found")
                return False
            
            # Check G8 principle: cannot self-execute without approval
            if not diagnosis.get('requires_director_approval', True):
                logger.warning(f"Diagnosis {diagnosis_id} doesn't require director approval")
            
            # Apply parameter adjustments if available
            if diagnosis.get('parameter_adjustments'):
                self._apply_parameter_adjustments(
                    diagnosis['parameter_adjustments'],
                    diagnosis_id,
                    approver
                )
            
            # Mark diagnosis as resolved
            self._resolve_diagnosis(diagnosis_id, approver)
            
            logger.info(f"Successfully applied doctor recommendations for {diagnosis_id} approved by {approver}")
            return True
            
        except Exception as e:
            logger.error(f"Error applying doctor recommendations: {e}")
            return False
    
    def _get_diagnosis(self, diagnosis_id: str) -> Optional[Dict[str, Any]]:
        """Get diagnosis from database."""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM doctor_diagnoses WHERE diagnosis_id = ?
                """, (diagnosis_id,))
                row = cursor.fetchone()
                if row:
                    return dict(row)
                return None
                
        except Exception as e:
            logger.error(f"Failed to get diagnosis: {e}")
            return None
    
    def _apply_parameter_adjustments(self, adjustments: str, diagnosis_id: str, approver: str):
        """Apply parameter adjustments (placeholder for actual implementation)."""
        # This would be implemented based on the actual system configuration
        # For now, we'll log the action
        logger.info(f"Applying parameter adjustments for {diagnosis_id} approved by {approver}: {adjustments}")
        
        # Example implementation would be:
        # - Update Ollama model parameters
        # - Adjust worker pool settings
        # - Modify VRAM policy thresholds
        # - Update temperature, repeat_penalty, etc.
    
    def _resolve_diagnosis(self, diagnosis_id: str, approver: str):
        """Mark diagnosis as resolved."""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE doctor_diagnoses 
                    SET resolved_at = CURRENT_TIMESTAMP 
                    WHERE diagnosis_id = ?
                """, (diagnosis_id,))
                
            logger.info(f"Diagnosis {diagnosis_id} marked as resolved by {approver}")
            
        except Exception as e:
            logger.error(f"Failed to resolve diagnosis: {e}")
    
    def get_observer_statistics(self) -> Dict[str, Any]:
        """Get observer statistics."""
        return {
            "is_running": self.is_running,
            "anomalies_detected": self.anomalies_detected,
            "critical_anomalies": self.critical_anomalies,
            "last_diagnosis_time": self.last_diagnosis_time.isoformat() if self.last_diagnosis_time else None,
            "response_history_size": len(self.response_history),
            "active_tasks": len(self.task_start_times),
            "jaccard_threshold": self.jaccard_threshold,
            "hang_threshold_minutes": self.hang_threshold_minutes
        }


def initialize_doctor_database():
    """Initialize doctor diagnoses table in database."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS doctor_diagnoses (
                    diagnosis_id TEXT PRIMARY KEY,
                    anomaly_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    semantic_jaccard_score REAL,
                    meta_slip_pattern TEXT,
                    worker_hang_duration_minutes INTEGER,
                    vram_growth_mb INTEGER,
                    response_quality_score REAL,
                    construction_context TEXT NOT NULL,
                    related_project_id TEXT,
                    affected_task_type TEXT,
                    diagnosis_description TEXT NOT NULL,
                    technical_details TEXT DEFAULT '{}',
                    recommended_actions TEXT NOT NULL,
                    parameter_adjustments TEXT,
                    self_action_forbidden BOOLEAN DEFAULT 1,
                    requires_director_approval BOOLEAN DEFAULT 1,
                    question_gateway_id TEXT,
                    telegram_notification_sent BOOLEAN DEFAULT 0,
                    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    resolved_at TIMESTAMP
                )
            """)
            
            # Create indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_diagnosis_severity 
                ON doctor_diagnoses(severity, detected_at)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_diagnosis_type 
                ON doctor_diagnoses(anomaly_type, severity)
            """)
            
        logger.info("Doctor diagnoses database initialized")
        
    except Exception as e:
        logger.error(f"Failed to initialize doctor database: {e}")



if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)
    
    # Initialize database
    initialize_doctor_database()
    
    # Create doctor observer
    doctor = DoctorObserver()
    
    # Start observer
    doctor.start()
    
    # Add some test responses
    doctor.add_response("Check with supplier for cable trays", "TASK-001", "Material status query")
    doctor.add_response("Supplier should confirm delivery", "TASK-002", "Material status query")
    doctor.add_response("Verify with supplier regarding delivery", "TASK-003", "Material status query")
    
    # Check statistics
    stats = doctor.get_observer_statistics()
    print(f"Observer statistics: {stats}")
    
    # Let it run briefly
    time.sleep(5)
    
    # Stop observer
    doctor.stop()