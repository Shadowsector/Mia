"""Negative Event Trigger - Monitor for negative events and silence.

This module implements triggers for detecting negative events such as:
- Silence (no updates for extended period)
- Missed deadlines
- Unapproved changes
- Unresolved questions
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from pathlib import Path

from app.modules.storage.database import get_db_connection

logger = logging.getLogger(__name__)


class NegativeEventTrigger:
    """
    Monitor for negative events and silence.
    
    Detects concerning patterns that require attention:
    - Extended silence on active objects
    - Overdue deadlines
    - Unresolved human questions
    - High-risk status changes
    """
    
    def __init__(self):
        """Initialize Negative Event Trigger."""
        self.silence_threshold_days = 7  # Consider silence after 7 days
        self.deadline_warning_days = 3  # Warn 3 days before deadline
    
    def check_silence(self, object_id: str) -> Optional[Dict[str, Any]]:
        """
        Check if an object has been silent for too long.
        
        Args:
            object_id: Object ID
            
        Returns:
            Silence event dict or None if no silence
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Get last event date
                cursor.execute("""
                    SELECT MAX(event_date) as last_event
                    FROM object_events
                    WHERE object_id = ?
                """, (object_id,))
                
                row = cursor.fetchone()
                if not row or not row['last_event']:
                    return None
                
                last_event = datetime.strptime(row['last_event'], '%Y-%m-%d')
                days_since = (datetime.now() - last_event).days
                
                if days_since >= self.silence_threshold_days:
                    return {
                        'event_type': 'silence',
                        'object_id': object_id,
                        'days_since_last_event': days_since,
                        'severity': 'high' if days_since >= 14 else 'medium',
                        'triggered_at': datetime.now().isoformat()
                    }
                
                return None
                
        except Exception as e:
            logger.error(f"Error checking silence for {object_id}: {e}")
            return None
    
    def check_overdue_deadlines(self) -> List[Dict[str, Any]]:
        """
        Check for overdue deadlines.
        
        Returns:
            List of overdue deadline events
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Get uncompleted deadlines
                cursor.execute("""
                    SELECT object_id, deadline_date, event_type, description
                    FROM object_events
                    WHERE event_type IN ('deadline', 'milestone')
                    AND deadline_date < ?
                    AND status != 'completed'
                    ORDER BY deadline_date
                """, (datetime.now().date(),))
                
                events = []
                for row in cursor.fetchall():
                    deadline = datetime.strptime(row['deadline_date'], '%Y-%m-%d')
                    days_overdue = (datetime.now() - deadline).days
                    
                    events.append({
                        'event_type': 'overdue_deadline',
                        'object_id': row['object_id'],
                        'deadline_date': row['deadline_date'],
                        'days_overdue': days_overdue,
                        'description': row['description'],
                        'severity': 'critical' if days_overdue >= 7 else 'high',
                        'triggered_at': datetime.now().isoformat()
                    })
                
                return events
                
        except Exception as e:
            logger.error(f"Error checking overdue deadlines: {e}")
            return []
    
    def check_unresolved_questions(self) -> List[Dict[str, Any]]:
        """
        Check for unresolved human questions.
        
        Returns:
            List of unresolved question events
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Get unresolved questions
                cursor.execute("""
                    SELECT question_id, project_id, question_type, created_at
                    FROM questions
                    WHERE status IN ('pending', 'suspended')
                    ORDER BY created_at
                """)
                
                events = []
                for row in cursor.fetchall():
                    created_at = datetime.strptime(row['created_at'], '%Y-%m-%d %H:%M:%S')
                    days_pending = (datetime.now() - created_at).days
                    
                    events.append({
                        'event_type': 'unresolved_question',
                        'question_id': row['question_id'],
                        'project_id': row['project_id'],
                        'question_type': row['question_type'],
                        'days_pending': days_pending,
                        'severity': 'high' if days_pending >= 3 else 'medium',
                        'triggered_at': datetime.now().isoformat()
                    })
                
                return events
                
        except Exception as e:
            logger.error(f"Error checking unresolved questions: {e}")
            return []
    
    def check_high_risk_changes(self) -> List[Dict[str, Any]]:
        """
        Check for high-risk status changes.
        
        Returns:
            List of high-risk change events
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Get recent high-risk changes
                cursor.execute("""
                    SELECT object_id, event_type, description, event_date
                    FROM object_events
                    WHERE event_type IN ('contract_modified', 'budget_cut', 'schedule_delay')
                    AND event_date >= ?
                    ORDER BY event_date DESC
                """, ((datetime.now() - timedelta(days=7)).date(),))
                
                events = []
                for row in cursor.fetchall():
                    events.append({
                        'event_type': 'high_risk_change',
                        'object_id': row['object_id'],
                        'change_type': row['event_type'],
                        'description': row['description'],
                        'event_date': row['event_date'],
                        'severity': 'high',
                        'triggered_at': datetime.now().isoformat()
                    })
                
                return events
                
        except Exception as e:
            logger.error(f"Error checking high-risk changes: {e}")
            return []
    
    def scan_all_objects(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Scan all objects for negative events.
        
        Returns:
            Dictionary of event types to event lists
        """
        results = {
            'silence_events': [],
            'overdue_deadlines': [],
            'unresolved_questions': [],
            'high_risk_changes': []
        }
        
        # Check silence for all objects
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT DISTINCT object_id FROM objects")
                
                for row in cursor.fetchall():
                    object_id = row['object_id']
                    silence_event = self.check_silence(object_id)
                    if silence_event:
                        results['silence_events'].append(silence_event)
                        
        except Exception as e:
            logger.error(f"Error scanning objects for silence: {e}")
        
        # Check other event types
        results['overdue_deadlines'] = self.check_overdue_deadlines()
        results['unresolved_questions'] = self.check_unresolved_questions()
        results['high_risk_changes'] = self.check_high_risk_changes()
        
        total_events = (
            len(results['silence_events']) +
            len(results['overdue_deadlines']) +
            len(results['unresolved_questions']) +
            len(results['high_risk_changes'])
        )
        
        logger.info(f"Negative event scan complete: {total_events} events detected")
        
        return results
    
    def generate_alert_summary(self, scan_results: Dict[str, List[Dict[str, Any]]]) -> str:
        """
        Generate human-readable alert summary.
        
        Args:
            scan_results: Results from scan_all_objects
            
        Returns:
            Alert summary text
        """
        summary_parts = ["🚨 Negative Event Alert Summary\n"]
        
        # Silence events
        if scan_results['silence_events']:
            summary_parts.append(f"\n🔇 Silence Events ({len(scan_results['silence_events'])}):")
            for event in scan_results['silence_events'][:5]:
                summary_parts.append(f"  - Object {event['object_id']}: {event['days_since_last_event']} days without updates")
        
        # Overdue deadlines
        if scan_results['overdue_deadlines']:
            summary_parts.append(f"\n⏰ Overdue Deadlines ({len(scan_results['overdue_deadlines'])}):")
            for event in scan_results['overdue_deadlines'][:5]:
                summary_parts.append(f"  - Object {event['object_id']}: {event['days_overdue']} days overdue")
        
        # Unresolved questions
        if scan_results['unresolved_questions']:
            summary_parts.append(f"\n❓ Unresolved Questions ({len(scan_results['unresolved_questions'])}):")
            for event in scan_results['unresolved_questions'][:5]:
                summary_parts.append(f"  - Question {event['question_id']}: {event['days_pending']} days pending")
        
        # High-risk changes
        if scan_results['high_risk_changes']:
            summary_parts.append(f"\n⚠️ High-Risk Changes ({len(scan_results['high_risk_changes'])}):")
            for event in scan_results['high_risk_changes'][:5]:
                summary_parts.append(f"  - Object {event['object_id']}: {event['change_type']}")
        
        return "\n".join(summary_parts)


if __name__ == "__main__":
    # Test Negative Event Trigger
    logging.basicConfig(level=logging.INFO)
    
    trigger = NegativeEventTrigger()
    
    # Scan all objects
    results = trigger.scan_all_objects()
    
    # Generate summary
    summary = trigger.generate_alert_summary(results)
    print(summary)
