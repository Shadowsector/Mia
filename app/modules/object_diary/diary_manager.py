"""Diary Manager for Object Diary System - RFC v1.9"""

from typing import Optional, List, Dict, Any
from datetime import datetime
import json
from pathlib import Path

from app.core.schemas import ObjectDiarySchema, DiaryEventSchema
from app.modules.storage.database import get_db_connection
from app.core.audit_logger import get_audit_logger


class DiaryManager:
    """Базовый менеджер дневников объектов (CRUD, таймлайн, версионирование, цитирование)"""
    
    def __init__(self):
        self.audit_logger = get_audit_logger()
    
    def create_diary(self, diary_data: ObjectDiarySchema, actor: str = "system") -> int:
        """Создать новый дневник объекта"""
        diary_id = None
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO objects (
                        object_name, object_id, customer, customer_company,
                        contract_date, contract_amount, contract_number,
                        subcontractors, parent_contract_id, sub_contracts,
                        has_proposal, proposal_date, proposal_amount,
                        converted_to_contract, custom_fields, rag_metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    diary_data.object_name,
                    diary_data.object_id,
                    diary_data.customer,
                    diary_data.customer_company,
                    diary_data.contract_date,
                    diary_data.contract_amount,
                    diary_data.contract_number,
                    json.dumps(diary_data.subcontractors),
                    diary_data.parent_contract_id,
                    json.dumps(diary_data.sub_contracts),
                    diary_data.has_proposal,
                    diary_data.proposal_date,
                    diary_data.proposal_amount,
                    diary_data.converted_to_contract,
                    json.dumps(diary_data.custom_fields),
                    json.dumps(diary_data.rag_metadata)
                ))
                diary_id = cursor.lastrowid
            
            # Log audit trail
            self.audit_logger.log_change(
                actor=actor,
                action="create",
                entity_type="object_diary",
                entity_id=str(diary_id),
                new_value=diary_data.model_dump(),
                origin="manual"
            )
            
            return diary_id
        except Exception as e:
            # Log failure
            if diary_id:
                self.audit_logger.log_change(
                    actor=actor,
                    action="create",
                    entity_type="object_diary",
                    entity_id=str(diary_id),
                    old_value=None,
                    new_value={"error": str(e)},
                    origin="manual"
                )
            raise
    
    def get_diary(self, diary_id: int) -> Optional[ObjectDiarySchema]:
        """Получить дневник по ID"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM objects WHERE diary_id = ?", (diary_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_diary_schema(row)
            return None
    
    def get_diary_by_object_id(self, object_id: str) -> Optional[ObjectDiarySchema]:
        """Получить дневник по object_id (Google Drive folder ID)"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM objects WHERE object_id = ?", (object_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_diary_schema(row)
            return None
    
    def update_diary(self, diary_id: int, update_data: Dict[str, Any]) -> bool:
        """Обновить дневник"""
        allowed_fields = {
            'customer', 'customer_company', 'contract_date', 'contract_amount',
            'contract_number', 'subcontractors', 'parent_contract_id', 'sub_contracts',
            'has_proposal', 'proposal_date', 'proposal_amount', 'converted_to_contract',
            'custom_fields', 'rag_metadata'
        }
        
        update_fields = {k: v for k, v in update_data.items() if k in allowed_fields}
        
        if not update_fields:
            return False
        
        json_fields = {'subcontractors', 'sub_contracts', 'custom_fields', 'rag_metadata'}
        
        set_clause = ", ".join([f"{field} = ?" for field in update_fields.keys()])
        values = [
            json.dumps(value) if field in json_fields and isinstance(value, (dict, list)) else value
            for field, value in update_fields.items()
        ]
        
        values.append(datetime.now())
        values.append(diary_id)
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                UPDATE objects 
                SET {set_clause}, updated_at = ?
                WHERE diary_id = ?
            """, values)
            return cursor.rowcount > 0
    
    def delete_diary(self, diary_id: int) -> bool:
        """Удалить дневник"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM objects WHERE diary_id = ?", (diary_id,))
            return cursor.rowcount > 0
    
    def add_event(self, diary_id: int, event_data: DiaryEventSchema) -> int:
        """Добавить событие в дневник"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO diary_events (
                    diary_id, event_type, event_timestamp, entity_type, entity_id,
                    summary, metadata, overrides_event_id, is_current,
                    citation_text, citation_page, citation_bbox, citation_confidence,
                    requires_verification, verification_status, temporal_context
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                diary_id,
                event_data.event_type,
                event_data.event_timestamp,
                event_data.entity_type,
                event_data.entity_id,
                event_data.summary,
                json.dumps(event_data.metadata),
                event_data.overrides_event_id,
                event_data.is_current,
                event_data.citation_text,
                event_data.citation_page,
                json.dumps(event_data.citation_bbox) if event_data.citation_bbox else None,
                event_data.citation_confidence,
                event_data.requires_verification,
                event_data.verification_status,
                json.dumps(event_data.temporal_context) if event_data.temporal_context else None
            ))
            
            # Если событие переопределяет другое, помечаем старое как неактуальное
            if event_data.overrides_event_id:
                cursor.execute("""
                    UPDATE diary_events 
                    SET is_current = 0 
                    WHERE event_id = ?
                """, (event_data.overrides_event_id,))
            
            return cursor.lastrowid
    
    def get_timeline(self, diary_id: int, only_current: bool = True) -> List[DiaryEventSchema]:
        """Получить таймлайн событий дневника"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM diary_events WHERE diary_id = ?"
            params = [diary_id]
            
            if only_current:
                query += " AND is_current = 1"
            
            query += " ORDER BY event_timestamp ASC"
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [self._row_to_event_schema(row) for row in rows]
    
    def delete_event(self, event_id: int) -> bool:
        """Удалить событие"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM diary_events WHERE event_id = ?", (event_id,))
            return cursor.rowcount > 0
    
    def override_event(self, event_id: int, new_event_data: DiaryEventSchema) -> int:
        """Переопределить событие (версионирование)"""
        new_event_data.overrides_event_id = event_id
        diary_id = self._get_diary_id_by_event(event_id)
        if diary_id:
            return self.add_event(diary_id, new_event_data)
        return -1
    
    def get_all_diaries(self) -> List[ObjectDiarySchema]:
        """Получить все дневники"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM objects ORDER BY created_at DESC")
            rows = cursor.fetchall()
            return [self._row_to_diary_schema(row) for row in rows]
    
    def _row_to_diary_schema(self, row) -> ObjectDiarySchema:
        """Конвертировать строку БД в ObjectDiarySchema"""
        return ObjectDiarySchema(
            diary_id=row['diary_id'],
            object_name=row['object_name'],
            object_id=row['object_id'],
            customer=row['customer'],
            customer_company=row['customer_company'],
            contract_date=row['contract_date'],
            contract_amount=row['contract_amount'],
            contract_number=row['contract_number'],
            subcontractors=json.loads(row['subcontractors']) if row['subcontractors'] else [],
            parent_contract_id=row['parent_contract_id'],
            sub_contracts=json.loads(row['sub_contracts']) if row['sub_contracts'] else [],
            has_proposal=row['has_proposal'],
            proposal_date=row['proposal_date'],
            proposal_amount=row['proposal_amount'],
            converted_to_contract=row['converted_to_contract'],
            custom_fields=json.loads(row['custom_fields']) if row['custom_fields'] else {},
            rag_metadata=json.loads(row['rag_metadata']) if row['rag_metadata'] else {},
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )
    
    def _row_to_event_schema(self, row) -> DiaryEventSchema:
        """Конвертировать строку БД в DiaryEventSchema"""
        return DiaryEventSchema(
            event_id=row['event_id'],
            event_type=row['event_type'],
            event_timestamp=row['event_timestamp'],
            entity_type=row['entity_type'],
            entity_id=row['entity_id'],
            summary=row['summary'],
            metadata=json.loads(row['metadata']) if row['metadata'] else {},
            overrides_event_id=row['overrides_event_id'],
            is_current=row['is_current'],
            citation_text=row['citation_text'],
            citation_page=row['citation_page'],
            citation_bbox=json.loads(row['citation_bbox']) if row['citation_bbox'] else None,
            citation_confidence=row['citation_confidence'],
            requires_verification=row['requires_verification'],
            verification_status=row['verification_status'],
            temporal_context=json.loads(row['temporal_context']) if row['temporal_context'] else None
        )
    
    def _get_diary_id_by_event(self, event_id: int) -> Optional[int]:
        """Получить diary_id по event_id"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT diary_id FROM diary_events WHERE event_id = ?", (event_id,))
            row = cursor.fetchone()
            return row['diary_id'] if row else None
