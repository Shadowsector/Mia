"""Telegram Distiller - Aggregate chaos: merge documents and Telegram channels.

This module aggregates information from multiple sources (documents, Telegram chats)
into a coherent view, distilling the signal from the noise.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

from app.modules.storage.database import get_db_connection

logger = logging.getLogger(__name__)


class TelegramDistiller:
    """
    Aggregate and distill information from Telegram chats and documents.
    
    Merges information from multiple sources into a coherent timeline,
    deduplicating and prioritizing information based on source reliability.
    Also detects risk-related keywords for negative event triggering.
    """
    
    # Risk-related keywords for construction projects
    RISK_KEYWORDS = {
        'material_shortage': [
            'нет материала', 'не приехал', 'не приехали',
            'отсутствует', 'закончился', 'закончились', 'не доставлен',
            'не доставлены', 'нет', 'нехватка', 'дефицит'
        ],
        'payment_issue': [
            'не оплатили', 'не заплатили', 'нет оплаты', 'нет платежа',
            'задержка оплаты', 'кассовый разрыв', 'не хватает денег',
            'бюджет', 'стоим', 'оплата', 'счёт', 'счет'
        ],
        'schedule_delay': [
            'задержка', 'задерживаем', 'задержали', 'не успеваем',
            'опаздываем', 'срок нарушен', 'не успеем', 'срыв сроков',
            'дедлайн', 'deadline'
        ],
        'quality_issue': [
            'брак', 'дефект', 'некачественно', 'плохого качества',
            'не соответствует', 'отклонение', 'ошибка', 'проблема'
        ],
        'personnel_issue': [
            'нет людей', 'не хватает рабочих', 'людей нет',
            'кадры', 'персонал', 'бригада', 'нет бригады'
        ]
    }
    
    def __init__(self):
        """Initialize Telegram Distiller."""
        pass

    def _resolve_chat_id(self, object_id: str) -> Optional[int]:
        """
        Resolve the Telegram chat linked to an object.

        Objects do not store a chat ID directly, so the link is resolved
        through the projects table: either the object ID matches a project ID
        or it matches the project's Google Drive folder ID.

        Args:
            object_id: Object ID

        Returns:
            Telegram chat ID or None if no project is linked
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT telegram_chat_id FROM projects
                    WHERE project_id = ? OR google_drive_folder_id = ?
                    LIMIT 1
                """, (object_id, object_id))

                row = cursor.fetchone()
                return row['telegram_chat_id'] if row else None

        except Exception as e:
            logger.error(f"Error resolving Telegram chat for {object_id}: {e}")
            return None
    
    def detect_risk_keywords(self, text: str) -> Dict[str, Any]:
        """
        Detect risk-related keywords in text.
        
        Args:
            text: Text to analyze
            
        Returns:
            Risk detection result
        """
        text_lower = text.lower()

        detected_risks = []
        risk_scores = {}

        for risk_type, keywords in self.RISK_KEYWORDS.items():
            matched = []
            for keyword in keywords:
                if keyword in text_lower and not any(
                    keyword in existing for existing in matched
                ):
                    matched.append(keyword)

            for keyword in matched:
                detected_risks.append({
                    'risk_type': risk_type,
                    'keyword': keyword
                })

            if matched:
                # Assign risk score based on severity
                if risk_type in ['material_shortage', 'payment_issue']:
                    risk_scores[risk_type] = 10  # Highest priority
                elif risk_type in ['schedule_delay', 'quality_issue']:
                    risk_scores[risk_type] = 7  # High priority
                else:
                    risk_scores[risk_type] = 5  # Medium priority
        
        return {
            'has_risk': len(detected_risks) > 0,
            'detected_risks': detected_risks,
            'risk_scores': risk_scores,
            'max_risk_score': max(risk_scores.values()) if risk_scores else 0
        }
    
    def calculate_message_priority(self, message: str, user_id: Optional[int] = None) -> int:
        """
        Calculate priority for a Telegram message.
        
        Args:
            message: Message text
            user_id: User ID (for authority check)
            
        Returns:
            Priority score (1-10)
        """
        base_priority = 5
        
        # Check for risk keywords
        risk_detection = self.detect_risk_keywords(message)
        if risk_detection['has_risk']:
            base_priority = max(base_priority, risk_detection['max_risk_score'])
        
        # Check for authority (if employee data available)
        # This would require employee database integration
        # For now, use risk-based priority
        
        return min(base_priority, 10)
    
    def get_unified_timeline(
        self,
        object_id: str,
        include_telegram: bool = True,
        include_documents: bool = True,
        include_events: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get unified timeline from all sources.
        
        Args:
            object_id: Object ID
            include_telegram: Include Telegram messages
            include_documents: Include document events
            include_events: Include system events
            
        Returns:
            Unified timeline sorted by timestamp
        """
        timeline = []
        
        # Get Telegram messages for the chat linked to this object
        if include_telegram:
            try:
                chat_id = self._resolve_chat_id(object_id)
                if chat_id is None:
                    logger.debug(
                        f"No Telegram chat linked to object {object_id}, skipping messages"
                    )
                else:
                    with get_db_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("""
                            SELECT message_id, user_id, username, message_text, timestamp
                            FROM telegram_messages
                            WHERE telegram_chat_id = ?
                            ORDER BY timestamp
                        """, (chat_id,))
                        
                        for row in cursor.fetchall():
                            message_text = row['message_text'] or ''
                            
                            # Detect risk keywords
                            risk_detection = self.detect_risk_keywords(message_text)
                            
                            timeline.append({
                                'source': 'telegram',
                                'event_type': 'message',
                                'timestamp': row['timestamp'],
                                'message_id': row['message_id'],
                                'user_id': row['user_id'],
                                'username': row['username'],
                                'content': message_text,
                                'risk_detection': risk_detection,
                                'priority': risk_detection['max_risk_score'] if risk_detection['has_risk'] else 5
                            })
                        
            except Exception as e:
                logger.error(f"Error getting Telegram messages: {e}")
        
        # Get document events
        if include_documents:
            try:
                with get_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT document_id, document_name, linked_at
                        FROM document_links
                        WHERE object_id = ?
                        ORDER BY linked_at
                    """, (object_id,))
                    
                    for row in cursor.fetchall():
                        timeline.append({
                            'source': 'document',
                            'event_type': 'document_linked',
                            'timestamp': row['linked_at'],
                            'document_id': row['document_id'],
                            'document_name': row['document_name']
                        })
                        
            except Exception as e:
                logger.error(f"Error getting document events: {e}")
        
        # Get system events
        if include_events:
            try:
                with get_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT event_id, event_type, event_date, description
                        FROM object_events
                        WHERE object_id = ?
                        ORDER BY event_date
                    """, (object_id,))
                    
                    for row in cursor.fetchall():
                        timeline.append({
                            'source': 'system',
                            'event_type': row['event_type'],
                            'timestamp': row['event_date'],
                            'event_id': row['event_id'],
                            'description': row['description']
                        })
                        
            except Exception as e:
                logger.error(f"Error getting system events: {e}")
        
        # Sort by timestamp
        timeline.sort(key=lambda x: x['timestamp'])
        
        return timeline
    
    def deduplicate_timeline(self, timeline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Deduplicate timeline entries.
        
        Args:
            timeline: Timeline to deduplicate
            
        Returns:
            Deduplicated timeline
        """
        seen = set()
        deduplicated = []
        
        for event in timeline:
            # Create a hash key for deduplication. Include the source-specific
            # identifier so distinct messages/documents with identical
            # timestamps are not collapsed into one.
            identifier = (
                event.get('message_id')
                or event.get('document_id')
                or event.get('event_id')
                or event.get('content')
                or event.get('description')
            )
            key = (
                f"{event['source']}:{event['event_type']}:"
                f"{event['timestamp']}:{identifier}"
            )
            
            if key not in seen:
                seen.add(key)
                deduplicated.append(event)
        
        return deduplicated
    
    def prioritize_sources(self, timeline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Prioritize timeline entries by source reliability.
        
        Args:
            timeline: Timeline to prioritize
            
        Returns:
            Prioritized timeline
        """
        # Source reliability weights
        source_weights = {
            'system': 1.0,  # Highest priority
            'document': 0.8,
            'telegram': 0.6  # Lower priority (may be informal)
        }
        
        for event in timeline:
            event['source_weight'] = source_weights.get(event['source'], 0.5)

        # Sort by source reliability (descending), then risk priority, then timestamp
        timeline.sort(
            key=lambda x: (
                -x['source_weight'],
                -x.get('priority', 0),
                x['timestamp'],
            )
        )
        
        return timeline
    
    def generate_digest(self, object_id: str, days: int = 7) -> Dict[str, Any]:
        """
        Generate a digest of recent activity.
        
        Args:
            object_id: Object ID
            days: Number of days to include
            
        Returns:
            Activity digest
        """
        timeline = self.get_unified_timeline(object_id)
        
        # Filter by date range
        cutoff = datetime.now() - timedelta(days=days)
        recent = [t for t in timeline if datetime.fromisoformat(t['timestamp']) > cutoff]
        
        # Deduplicate and prioritize
        recent = self.deduplicate_timeline(recent)
        recent = self.prioritize_sources(recent)
        
        # Calculate statistics
        stats = {
            'total_events': len(recent),
            'by_source': {},
            'by_type': {}
        }
        
        for event in recent:
            source = event['source']
            event_type = event['event_type']
            
            stats['by_source'][source] = stats['by_source'].get(source, 0) + 1
            stats['by_type'][event_type] = stats['by_type'].get(event_type, 0) + 1
        
        return {
            'object_id': object_id,
            'days_range': days,
            'timeline': recent,
            'statistics': stats,
            'generated_at': datetime.now().isoformat()
        }
    
    def get_high_risk_messages(self, object_id: str, min_priority: int = 7) -> List[Dict[str, Any]]:
        """
        Get high-risk Telegram messages for an object.
        
        Args:
            object_id: Object ID
            min_priority: Minimum priority threshold
            
        Returns:
            List of high-risk messages
        """
        timeline = self.get_unified_timeline(object_id, include_telegram=True, 
                                           include_documents=False, include_events=False)
        
        # Filter by priority and source
        high_risk = [
            event for event in timeline
            if event['source'] == 'telegram' 
            and event.get('priority', 0) >= min_priority
        ]
        
        # Sort by priority (descending), then timestamp
        high_risk.sort(key=lambda x: (-x.get('priority', 0), x['timestamp']))
        
        return high_risk
    
    def integrate_with_negative_event_trigger(self, object_id: str) -> List[Dict[str, Any]]:
        """
        Integrate with Negative Event Trigger.
        
        Extracts high-risk Telegram messages and formats them as negative events.
        
        Args:
            object_id: Object ID
            
        Returns:
            List of negative events from Telegram
        """
        high_risk_messages = self.get_high_risk_messages(object_id)
        
        negative_events = []
        for msg in high_risk_messages:
            risk_detection = msg.get('risk_detection', {})
            
            for risk in risk_detection.get('detected_risks', []):
                negative_events.append({
                    'event_type': 'telegram_risk',
                    'object_id': object_id,
                    'risk_type': risk['risk_type'],
                    'keyword': risk['keyword'],
                    'message_id': msg['message_id'],
                    'username': msg['username'],
                    'timestamp': msg['timestamp'],
                    'severity': 'high' if msg.get('priority', 0) >= 10 else 'medium',
                    'triggered_at': datetime.now().isoformat()
                })
        
        return negative_events
    
    def extract_key_insights(self, digest: Dict[str, Any]) -> List[str]:
        """
        Extract key insights from activity digest.
        
        Args:
            digest: Activity digest
            
        Returns:
            List of insight strings
        """
        insights = []
        
        timeline = digest['timeline']
        stats = digest['statistics']
        
        # Insight 1: High activity period
        if stats['total_events'] > 20:
            insights.append(f"High activity period: {stats['total_events']} events in {digest['days_range']} days")
        
        # Insight 2: Document activity
        doc_events = stats['by_source'].get('document', 0)
        if doc_events > 5:
            insights.append(f"Significant document activity: {doc_events} documents added")
        
        # Insight 3: Telegram chatter
        telegram_events = stats['by_source'].get('telegram', 0)
        if telegram_events > 10:
            insights.append(f"Active Telegram discussion: {telegram_events} messages")
        
        # Insight 4: Recent system events
        system_events = stats['by_type'].get('deadline', 0)
        if system_events > 0:
            insights.append(f"Recent deadline-related events: {system_events}")
        
        # Insight 5: High-risk messages
        high_risk_count = sum(1 for event in timeline if event.get('priority', 0) >= 7)
        if high_risk_count > 0:
            insights.append(f"High-risk messages detected: {high_risk_count}")
        
        return insights


if __name__ == "__main__":
    # Test Telegram Distiller
    logging.basicConfig(level=logging.INFO)
    
    distiller = TelegramDistiller()
    
    # Test unified timeline (would need actual data)
    # timeline = distiller.get_unified_timeline("TEST-001")
    # print(f"Timeline: {len(timeline)} events")
    
    print("Telegram Distiller initialized")
