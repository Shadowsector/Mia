"""SQLite database initialization and management for Mia PM OS"""

import sqlite3
import json
from contextlib import contextmanager
from typing import Optional, List, Dict, Any
from datetime import datetime
from pathlib import Path
import threading

# Database path
DB_PATH = Path(__file__).parent.parent.parent / "data" / "mia_pm.db"

# Thread lock for SQLite operations
db_lock = threading.Lock()


@contextmanager
def get_db_connection():
    """Context manager for database connections with thread safety."""
    # Ensure data directory exists
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def initialize_database():
    """Initialize all database tables with proper schema."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Projects table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                project_id TEXT PRIMARY KEY,
                project_name TEXT NOT NULL,
                telegram_chat_id INTEGER UNIQUE NOT NULL,
                google_drive_folder_id TEXT NOT NULL,
                email_filters TEXT DEFAULT '[]',
                status TEXT DEFAULT 'planning',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT DEFAULT '{}'
            )
        """)
        
        # Unified LLM Task Queue
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS llm_task_queue (
                task_id TEXT PRIMARY KEY,
                task_type TEXT NOT NULL,
                priority INTEGER NOT NULL,
                system_current_time TIMESTAMP NOT NULL,
                user_timezone TEXT DEFAULT 'UTC',
                conversation_context TEXT DEFAULT '[]',
                parent_thread_id INTEGER,
                reply_chain TEXT DEFAULT '[]',
                agent_reasoning TEXT,
                selected_tools TEXT DEFAULT '[]',
                tool_call_sequence TEXT DEFAULT '[]',
                user_message TEXT NOT NULL,
                user_intent TEXT,
                entities_detected TEXT DEFAULT '{}',
                project_id TEXT,
                telegram_chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                username TEXT,
                status TEXT DEFAULT 'pending',
                queued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                result TEXT,
                error_message TEXT,
                FOREIGN KEY (project_id) REFERENCES projects(project_id)
            )
        """)
        
        # Create indexes for queue performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_task_priority 
            ON llm_task_queue(priority, queued_at)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_task_status 
            ON llm_task_queue(status)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_task_project 
            ON llm_task_queue(project_id)
        """)
        
        # Financial Reports table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS financial_reports (
                report_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                reporting_period_start TIMESTAMP NOT NULL,
                reporting_period_end TIMESTAMP NOT NULL,
                total_budget DECIMAL(15,2) NOT NULL,
                spent_budget DECIMAL(15,2) DEFAULT 0,
                remaining_budget DECIMAL(15,2) DEFAULT 0,
                budget_utilization_percent REAL DEFAULT 0,
                ks2_documents TEXT DEFAULT '[]',
                ks2_total_amount DECIMAL(15,2) DEFAULT 0,
                ks3_document_count INTEGER DEFAULT 0,
                ks3_total_amount DECIMAL(15,2) DEFAULT 0,
                invoice_count INTEGER DEFAULT 0,
                invoice_total_amount DECIMAL(15,2) DEFAULT 0,
                pending_invoices INTEGER DEFAULT 0,
                pending_invoice_amount DECIMAL(15,2) DEFAULT 0,
                material_costs TEXT DEFAULT '{}',
                labor_costs DECIMAL(15,2) DEFAULT 0,
                equipment_costs DECIMAL(15,2) DEFAULT 0,
                overhead_costs DECIMAL(15,2) DEFAULT 0,
                generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                generated_by TEXT NOT NULL,
                data_sources TEXT DEFAULT '[]',
                FOREIGN KEY (project_id) REFERENCES projects(project_id)
            )
        """)
        
        # Material Status table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS material_status (
                material_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                canonical_name TEXT NOT NULL,
                alias_names TEXT DEFAULT '[]',
                unit TEXT NOT NULL,
                total_ordered DECIMAL(15,2) DEFAULT 0,
                total_delivered DECIMAL(15,2) DEFAULT 0,
                total_installed DECIMAL(15,2) DEFAULT 0,
                remaining_required DECIMAL(15,2) DEFAULT 0,
                current_status TEXT DEFAULT 'unknown',
                status_last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status_source TEXT NOT NULL,
                supplier_name TEXT,
                expected_delivery_date TIMESTAMP,
                actual_delivery_date TIMESTAMP,
                delivery_reference TEXT,
                technical_specifications TEXT DEFAULT '{}',
                material_spec_url TEXT,
                unit_cost DECIMAL(15,2),
                total_cost DECIMAL(15,2),
                status_conflicts TEXT DEFAULT '[]',
                last_conflict_check TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                notes TEXT,
                FOREIGN KEY (project_id) REFERENCES projects(project_id)
            )
        """)
        
        # Document Metadata table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS document_metadata (
                document_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                document_type TEXT NOT NULL,
                source_url TEXT NOT NULL,
                source_type TEXT NOT NULL,
                file_name TEXT NOT NULL,
                file_size_bytes INTEGER NOT NULL,
                mime_type TEXT,
                version_index INTEGER DEFAULT 1,
                is_latest_version BOOLEAN DEFAULT 1,
                previous_version_id TEXT,
                next_version_id TEXT,
                version_conflict_detected BOOLEAN DEFAULT 0,
                stamps_present BOOLEAN DEFAULT 0,
                stamp_verification_status TEXT DEFAULT 'not_checked',
                detected_stamps TEXT DEFAULT '[]',
                signatures_present BOOLEAN DEFAULT 0,
                signature_verification_status TEXT DEFAULT 'not_checked',
                detected_signatures TEXT DEFAULT '[]',
                issuing_authority TEXT,
                document_date TIMESTAMP,
                valid_from TIMESTAMP,
                valid_until TIMESTAMP,
                document_number TEXT,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processing_status TEXT DEFAULT 'pending',
                processing_errors TEXT DEFAULT '[]',
                extracted_text_summary TEXT,
                key_entities TEXT DEFAULT '[]',
                monetary_amounts TEXT DEFAULT '[]',
                dates_mentioned TEXT DEFAULT '[]',
                chunk_count INTEGER DEFAULT 0,
                chunk_ids TEXT DEFAULT '[]',
                related_document_ids TEXT DEFAULT '[]',
                referenced_in_chat_ids TEXT DEFAULT '[]',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT DEFAULT '{}',
                FOREIGN KEY (project_id) REFERENCES projects(project_id)
            )
        """)
        
        # Deadline Registry table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS deadline_registry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                event_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                event_title TEXT NOT NULL,
                target_date TIMESTAMP NOT NULL,
                target_telegram_chat_id INTEGER NOT NULL,
                additional_notify_user_ids TEXT DEFAULT '[]',
                notification_threshold_days INTEGER DEFAULT 30,
                notification_threshold_hours INTEGER,
                source_reference_url TEXT,
                source_reference_id TEXT,
                notified_status TEXT DEFAULT 'not_notified',
                first_notification_sent_at TIMESTAMP,
                last_notification_sent_at TIMESTAMP,
                notification_count INTEGER DEFAULT 0,
                notification_error_message TEXT,
                event_status TEXT DEFAULT 'upcoming',
                event_completed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                notes TEXT,
                FOREIGN KEY (project_id) REFERENCES projects(project_id)
            )
        """)
        
        # Extracted Events table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS extracted_events (
                event_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                raw_text TEXT NOT NULL,
                source_document_id TEXT,
                source_chat_message_id TEXT,
                source_type TEXT NOT NULL,
                original_date_phrase TEXT NOT NULL,
                extraction_method TEXT NOT NULL,
                extraction_confidence REAL DEFAULT 1.0,
                target_date TIMESTAMP NOT NULL,
                target_date_timezone TEXT DEFAULT 'UTC',
                is_duration_based BOOLEAN DEFAULT 0,
                duration_start_date TIMESTAMP,
                duration_value INTEGER,
                duration_unit TEXT,
                event_title TEXT NOT NULL,
                event_description TEXT,
                location TEXT,
                participants TEXT DEFAULT '[]',
                importance_level TEXT DEFAULT 'medium',
                notification_threshold_days INTEGER DEFAULT 30,
                notification_threshold_hours INTEGER,
                reference_url TEXT,
                reference_text TEXT,
                extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                extracted_by TEXT NOT NULL,
                verified BOOLEAN DEFAULT 0,
                verified_by TEXT,
                verified_at TIMESTAMP,
                event_status TEXT DEFAULT 'upcoming',
                completed_at TIMESTAMP,
                completion_notes TEXT,
                related_conflict_ids TEXT DEFAULT '[]',
                related_material_ids TEXT DEFAULT '[]',
                FOREIGN KEY (project_id) REFERENCES projects(project_id)
            )
        """)
        
        # Nomenclature Mapping table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS nomenclature_mapping (
                mapping_id TEXT PRIMARY KEY,
                canonical_name TEXT NOT NULL,
                alias_names TEXT DEFAULT '[]',
                project_id TEXT NOT NULL,
                material_category TEXT,
                confidence_score REAL DEFAULT 1.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                verified_by TEXT,
                verified_at TIMESTAMP,
                usage_count INTEGER DEFAULT 0,
                FOREIGN KEY (project_id) REFERENCES projects(project_id)
            )
        """)
        
        # Telegram Messages table for chat logging
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS telegram_messages (
                message_id INTEGER PRIMARY KEY,
                telegram_chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                username TEXT,
                message_text TEXT NOT NULL,
                direction TEXT DEFAULT 'incoming',
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                message_type TEXT DEFAULT 'text',
                reply_to_message_id INTEGER,
                entities TEXT DEFAULT '[]',
                media_file_path TEXT,
                processing_status TEXT DEFAULT 'pending',
                task_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create index for telegram messages performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_telegram_chat_timestamp 
            ON telegram_messages(telegram_chat_id, timestamp DESC)
        """)
        
        # Project Ledger table (Chronological state-machine ledger)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS project_ledger (
                ledger_id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                event_timestamp TIMESTAMP NOT NULL,
                discovered_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                entity_type TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                revision_index INTEGER DEFAULT 0,
                overrides_ledger_id INTEGER REFERENCES project_ledger(ledger_id),
                summary_delta TEXT NOT NULL,
                metadata TEXT DEFAULT '{}',
                FOREIGN KEY (project_id) REFERENCES projects(project_id)
            )
        """)
        
        # Create index for ledger chronology
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ledger_chronology 
            ON project_ledger(project_id, event_timestamp ASC)
        """)
        
        # Questions Gateway table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS questions_gateway (
                question_id TEXT PRIMARY KEY,
                question_type TEXT NOT NULL,
                status TEXT DEFAULT 'open',
                priority TEXT DEFAULT 'normal',
                project_id TEXT NOT NULL,
                related_schema_type TEXT NOT NULL,
                related_entity_id TEXT NOT NULL,
                question_markdown TEXT NOT NULL,
                option_a TEXT NOT NULL,
                option_b TEXT NOT NULL,
                option_c TEXT,
                suspended_task_id TEXT,
                suspended_task_type TEXT,
                shadow_file_path TEXT,
                file_mtime TEXT,
                integrity_regex_match BOOLEAN DEFAULT 1,
                resolved_by TEXT,
                resolved_option TEXT,
                resolution_notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                answered_at TIMESTAMP
            )
        """)
        
        # Create index for questions
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_questions_status 
            ON questions_gateway(status, priority)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_questions_project 
            ON questions_gateway(project_id)
        """)
        
        # Audit Gaps table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_gaps (
                audit_id TEXT PRIMARY KEY,
                severity TEXT NOT NULL,
                gap_type TEXT NOT NULL,
                project_id TEXT NOT NULL,
                affected_schemas TEXT NOT NULL,
                affected_entity_ids TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                detected_by TEXT NOT NULL,
                evidence_data TEXT DEFAULT '{}',
                expected_state TEXT NOT NULL,
                actual_state TEXT NOT NULL,
                rag_performed BOOLEAN DEFAULT 0,
                rag_results TEXT DEFAULT '[]',
                documents_found BOOLEAN DEFAULT 0,
                auto_resolution_attempted BOOLEAN DEFAULT 0,
                auto_resolution_successful BOOLEAN DEFAULT 0,
                manual_action_required BOOLEAN DEFAULT 1,
                question_gateway_id TEXT,
                checklist_item TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP
            )
        """)
        
        # Create indexes for audit gaps
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_severity 
            ON audit_gaps(severity, created_at)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_project 
            ON audit_gaps(project_id, gap_type)
        """)
        
        # Doctor Diagnoses table
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
        
        # Create indexes for doctor diagnoses
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_diagnosis_severity 
            ON doctor_diagnoses(severity, detected_at)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_diagnosis_type 
            ON doctor_diagnoses(anomaly_type, severity)
        """)
        
        # Object Diary tables (RFC v1.9)
        
        # Objects table (Основная таблица объектов)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS objects (
                diary_id INTEGER PRIMARY KEY AUTOINCREMENT,
                object_name TEXT NOT NULL,
                object_id TEXT UNIQUE NOT NULL,
                customer TEXT,
                customer_company TEXT,
                contract_date TIMESTAMP,
                contract_amount REAL,
                contract_number TEXT,
                subcontractors TEXT DEFAULT '[]',
                parent_contract_id TEXT,
                sub_contracts TEXT DEFAULT '[]',
                has_proposal BOOLEAN DEFAULT 0,
                proposal_date TIMESTAMP,
                proposal_amount REAL,
                converted_to_contract BOOLEAN DEFAULT 0,
                custom_fields TEXT DEFAULT '{}',
                rag_metadata TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Diary Events table (События в дневнике)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS diary_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                diary_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                event_timestamp TIMESTAMP NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                summary TEXT NOT NULL,
                metadata TEXT DEFAULT '{}',
                overrides_event_id INTEGER,
                is_current BOOLEAN DEFAULT 1,
                citation_text TEXT,
                citation_page INTEGER,
                citation_bbox TEXT,
                citation_confidence REAL,
                requires_verification BOOLEAN DEFAULT 0,
                verification_status TEXT,
                temporal_context TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (diary_id) REFERENCES objects(diary_id),
                FOREIGN KEY (overrides_event_id) REFERENCES diary_events(event_id)
            )
        """)
        
        # Virtual Documents table (Shadow Document pattern)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS virtual_documents (
                virtual_doc_id INTEGER PRIMARY KEY AUTOINCREMENT,
                diary_id INTEGER NOT NULL,
                doc_type TEXT NOT NULL,
                doc_name TEXT NOT NULL,
                status TEXT DEFAULT 'MISSING',
                expected_deadline TIMESTAMP,
                expected_source TEXT,
                actual_doc_id TEXT,
                actual_received_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (diary_id) REFERENCES objects(diary_id)
            )
        """)
        
        # Constraints table (Сеть Условий и Ограничений)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS constraints (
                constraint_id INTEGER PRIMARY KEY AUTOINCREMENT,
                object_id TEXT NOT NULL,
                constraint_type TEXT NOT NULL,
                constraint_name TEXT NOT NULL,
                description TEXT NOT NULL,
                required_for_actions TEXT DEFAULT '[]',
                status TEXT DEFAULT 'NOT_SATISFIED',
                satisfied_at TIMESTAMP,
                deadline TIMESTAMP,
                source_document_id TEXT,
                severity_level TEXT DEFAULT 'MAJOR',
                bypass_strict_rule BOOLEAN DEFAULT 0,
                bypass_reason TEXT,
                bypass_expiry TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Constraint Dependencies table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS constraint_dependencies (
                dependency_id INTEGER PRIMARY KEY AUTOINCREMENT,
                constraint_id INTEGER NOT NULL,
                depends_on_constraint_id INTEGER NOT NULL,
                dependency_type TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (constraint_id) REFERENCES constraints(constraint_id),
                FOREIGN KEY (depends_on_constraint_id) REFERENCES constraints(constraint_id)
            )
        """)
        
        # System Roles table (Матрица компетенций ролей)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_roles (
                role_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                username TEXT NOT NULL,
                role TEXT NOT NULL,
                object_id TEXT,
                capabilities TEXT DEFAULT '[]',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Delegated Questions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS delegated_questions (
                question_id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_request_id INTEGER NOT NULL,
                assigned_user_id TEXT NOT NULL,
                assigned_user_role TEXT NOT NULL,
                communication_channel TEXT NOT NULL,
                message_sent BOOLEAN DEFAULT 0,
                answer_received BOOLEAN DEFAULT 0,
                answer_text TEXT,
                answer_timestamp TIMESTAMP,
                deadline_for_reply TIMESTAMP,
                reminder_count INTEGER DEFAULT 0,
                escalation_status TEXT DEFAULT 'NONE',
                escalated_to_user_id TEXT,
                escalation_timestamp TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Expert Lessons table (Живая Онтология Девиаций)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS expert_lessons (
                lesson_id INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_category TEXT NOT NULL,
                context_tags TEXT DEFAULT '[]',
                raw_page_text TEXT NOT NULL,
                anchor_text_embedding_id TEXT NOT NULL,
                expert_commentary TEXT NOT NULL,
                applicability_scope TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                verified_by_human BOOLEAN DEFAULT 0
            )
        """)
        
        # Quality Metrics table (Метрики качества разработки)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS quality_metrics (
                metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
                metric_name TEXT NOT NULL,
                metric_value REAL NOT NULL,
                measurement_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                threshold_limit REAL,
                is_critical BOOLEAN DEFAULT 0
            )
        """)
        
        # Code Candidates table (CodeCandidate pattern)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS code_candidates (
                candidate_id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_type TEXT NOT NULL,
                source_model TEXT NOT NULL,
                generated_code TEXT NOT NULL,
                target_module TEXT NOT NULL,
                source_context TEXT NOT NULL,
                status TEXT DEFAULT 'PENDING',
                sha256_hash TEXT NOT NULL,
                smoke_test_result TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                approved_at TIMESTAMP,
                approved_by TEXT
            )
        """)
        
        # Hash Bound Resources table (Hash-Bound Admission)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS hash_bound_resources (
                hash_id INTEGER PRIMARY KEY AUTOINCREMENT,
                resource_type TEXT NOT NULL,
                resource_path TEXT NOT NULL,
                sha256_hash TEXT NOT NULL,
                resource_content TEXT NOT NULL,
                status TEXT DEFAULT 'ACTIVE',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_verified TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                verified_by TEXT NOT NULL
            )
        """)
        
        # Cron Tasks table (Cron tasks для SQLite)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cron_tasks (
                task_id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_text TEXT NOT NULL,
                trigger_date TIMESTAMP NOT NULL,
                status TEXT DEFAULT 'PENDING',
                executed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Negative Event Triggers table (Триггеры на «Молчание»)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS negative_event_triggers (
                trigger_id INTEGER PRIMARY KEY AUTOINCREMENT,
                object_id TEXT NOT NULL,
                expected_event_type TEXT NOT NULL,
                deadline_date TIMESTAMP NOT NULL,
                severity TEXT DEFAULT 'MAJOR',
                status TEXT DEFAULT 'ACTIVE',
                alert_sent BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Health Scores table (Индекс Здоровья Объекта)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS health_scores (
                score_id INTEGER PRIMARY KEY AUTOINCREMENT,
                object_id TEXT NOT NULL,
                score REAL NOT NULL,
                zone TEXT NOT NULL,
                calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                contributing_events TEXT DEFAULT '[]',
                risk_factors TEXT DEFAULT '[]'
            )
        """)
        
        # Alert Queue table (Очередь алертов)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alert_queue (
                alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_type TEXT NOT NULL,
                recipient_id TEXT NOT NULL,
                message TEXT NOT NULL,
                scheduled_at TIMESTAMP NOT NULL,
                sent_at TIMESTAMP,
                status TEXT DEFAULT 'PENDING',
                channel TEXT DEFAULT 'telegram',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes for Object Diary tables
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_objects_id 
            ON objects(object_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_diary_events_diary 
            ON diary_events(diary_id, event_timestamp DESC)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_diary_events_current 
            ON diary_events(diary_id, is_current)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_constraints_object 
            ON constraints(object_id, status)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_delegated_questions_status 
            ON delegated_questions(escalation_status, deadline_for_reply)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_expert_lessons_tags 
            ON expert_lessons(context_tags)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_health_scores_object 
            ON health_scores(object_id, calculated_at DESC)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_alert_queue_status 
            ON alert_queue(status, scheduled_at)
        """)
        
        print("Database initialized successfully")
        
        # Create index for deadline target dates
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_deadline_target_date 
            ON deadline_registry(target_date, event_status)
        """)
        
        # Create index for material canonical names
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_material_canonical 
            ON material_status(canonical_name, project_id)
        """)
        
        # System commands log table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_commands_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor TEXT NOT NULL,
                command TEXT NOT NULL,
                entity_type TEXT,
                entity_id TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                trace_id TEXT,
                metadata TEXT DEFAULT '{}'
            )
        """)
        
        print("Database initialized successfully")


def insert_project(project_data: Dict[str, Any]) -> bool:
    """Insert a new project into the database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO projects (
                    project_id, project_name, telegram_chat_id, 
                    google_drive_folder_id, email_filters, status, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                project_data['project_id'],
                project_data['project_name'],
                project_data['telegram_chat_id'],
                project_data['google_drive_folder_id'],
                str(project_data.get('email_filters', [])),
                project_data.get('status', 'planning'),
                str(project_data.get('metadata', {}))
            ))
            return True
        except sqlite3.IntegrityError as e:
            print(f"Error inserting project: {e}")
            return False


def get_project_by_chat_id(telegram_chat_id: int) -> Optional[Dict[str, Any]]:
    """Get project by Telegram chat ID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM projects WHERE telegram_chat_id = ?
        """, (telegram_chat_id,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None


def insert_telegram_message(message_data: Dict[str, Any]) -> bool:
    """Insert a Telegram message into the database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO telegram_messages (
                    message_id, telegram_chat_id, user_id, username, 
                    message_text, direction, timestamp, message_type,
                    reply_to_message_id, entities, media_file_path, 
                    processing_status, task_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                message_data['message_id'],
                message_data['telegram_chat_id'],
                message_data['user_id'],
                message_data.get('username'),
                message_data['message_text'],
                message_data.get('direction', 'incoming'),
                message_data.get('timestamp'),
                message_data.get('message_type', 'text'),
                message_data.get('reply_to_message_id'),
                str(message_data.get('entities', [])),
                message_data.get('media_file_path'),
                message_data.get('processing_status', 'pending'),
                message_data.get('task_id')
            ))
            return True
        except sqlite3.IntegrityError as e:
            print(f"Error inserting telegram message: {e}")
            return False


def get_recent_telegram_messages(limit: int = 50, chat_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Get recent Telegram messages from the database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        if chat_id:
            cursor.execute("""
                SELECT * FROM telegram_messages 
                WHERE telegram_chat_id = ?
                ORDER BY timestamp DESC 
                LIMIT ?
            """, (chat_id, limit))
        else:
            cursor.execute("""
                SELECT * FROM telegram_messages 
                ORDER BY timestamp DESC 
                LIMIT ?
            """, (limit,))
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def enqueue_task(task_data: Dict[str, Any]) -> bool:
    """Add a task to the unified LLM task queue."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO llm_task_queue (
                    task_id, task_type, priority, system_current_time,
                    user_timezone, conversation_context, parent_thread_id,
                    reply_chain, user_message, user_intent, entities_detected,
                    project_id, telegram_chat_id, user_id, username
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task_data['task_id'],
                task_data['task_type'],
                task_data['priority'],
                task_data['system_current_time'],
                task_data.get('user_timezone', 'UTC'),
                str(task_data.get('conversation_context', [])),
                task_data.get('parent_thread_id'),
                str(task_data.get('reply_chain', [])),
                task_data['user_message'],
                task_data.get('user_intent'),
                str(task_data.get('entities_detected', {})),
                task_data.get('project_id'),
                task_data['telegram_chat_id'],
                task_data['user_id'],
                task_data.get('username')
            ))
            return True
        except sqlite3.IntegrityError as e:
            print(f"Error enqueuing task: {e}")
            return False


def get_next_pending_task() -> Optional[Dict[str, Any]]:
    """Get the next pending task with highest priority."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM llm_task_queue 
            WHERE status = 'pending' 
            ORDER BY priority DESC, queued_at ASC 
            LIMIT 1
        """)
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None


def update_task_status(task_id: str, status: str, result: Optional[str] = None, 
                      error_message: Optional[str] = None) -> bool:
    """Update task status and optionally result/error."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            if status == 'processing':
                cursor.execute("""
                    UPDATE llm_task_queue 
                    SET status = ?, started_at = CURRENT_TIMESTAMP 
                    WHERE task_id = ?
                """, (status, task_id))
            elif status == 'waiting_human':
                cursor.execute("""
                    UPDATE llm_task_queue 
                    SET status = ?, started_at = CURRENT_TIMESTAMP 
                    WHERE task_id = ?
                """, (status, task_id))
            elif status == 'completed':
                cursor.execute("""
                    UPDATE llm_task_queue 
                    SET status = ?, completed_at = CURRENT_TIMESTAMP, result = ? 
                    WHERE task_id = ?
                """, (status, result, task_id))
            elif status == 'failed':
                cursor.execute("""
                    UPDATE llm_task_queue 
                    SET status = ?, completed_at = CURRENT_TIMESTAMP, error_message = ? 
                    WHERE task_id = ?
                """, (status, error_message, task_id))
            return True
        except Exception as e:
            print(f"Error updating task status: {e}")
            return False


def get_queue_statistics() -> Dict[str, int]:
    """Get statistics about the task queue."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM llm_task_queue WHERE status = 'pending'")
        pending = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM llm_task_queue WHERE status = 'processing'")
        processing = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM llm_task_queue WHERE status = 'completed'")
        completed = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM llm_task_queue WHERE status = 'failed'")
        failed = cursor.fetchone()[0]
        
        return {
            'pending': pending,
            'processing': processing,
            'completed': completed,
            'failed': failed
        }


if __name__ == "__main__":
    # Initialize database when run directly
    initialize_database()