"""Alert Dispatcher - Send notifications for important events.

This module handles dispatching alerts for:
- Deadline warnings
- High-risk changes
- Negative events
- System health issues
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    HIGH = "high"
    CRITICAL = "critical"


class AlertDispatcher:
    """
    Dispatch alerts to various channels.
    
    Supports multiple alert channels:
    - Telegram notifications
    - GUI alerts
    - Email (future)
    - SMS (future)
    """
    
    def __init__(self):
        """Initialize Alert Dispatcher."""
        self.alert_history: List[Dict[str, Any]] = []
    
    def create_alert(
        self,
        severity: AlertSeverity,
        title: str,
        message: str,
        source: str,
        object_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create an alert.
        
        Args:
            severity: Alert severity
            title: Alert title
            message: Alert message
            source: Alert source
            object_id: Associated object ID (optional)
            metadata: Additional metadata
            
        Returns:
            Alert dict
        """
        alert = {
            'alert_id': f"ALERT-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            'severity': severity.value,
            'title': title,
            'message': message,
            'source': source,
            'object_id': object_id,
            'metadata': metadata or {},
            'created_at': datetime.now().isoformat(),
            'sent_to_telegram': False,
            'sent_to_gui': False
        }
        
        self.alert_history.append(alert)
        logger.info(f"Created alert: {title} ({severity.value})")
        
        return alert
    
    def send_to_telegram(self, alert: Dict[str, Any], chat_id: int) -> bool:
        """
        Send alert to Telegram.
        
        Args:
            alert: Alert dict
            chat_id: Telegram chat ID
            
        Returns:
            True if sent successfully
        """
        try:
            # Import here to avoid circular dependency
            from mia.bot.handlers import messages
            
            # Format alert message
            severity_emoji = {
                'info': 'ℹ️',
                'warning': '⚠️',
                'high': '🔴',
                'critical': '🚨'
            }
            
            emoji = severity_emoji.get(alert['severity'], '📢')
            
            message = f"{emoji} {alert['title']}\n\n{alert['message']}"
            
            if alert['object_id']:
                message += f"\n\nОбъект: {alert['object_id']}"
            
            # Send message (would need actual Telegram bot instance)
            # For now, just log
            logger.info(f"Would send to Telegram {chat_id}: {message}")
            
            alert['sent_to_telegram'] = True
            return True
            
        except Exception as e:
            logger.error(f"Error sending alert to Telegram: {e}")
            return False
    
    def send_to_gui(self, alert: Dict[str, Any]) -> bool:
        """
        Send alert to GUI.
        
        Args:
            alert: Alert dict
            
        Returns:
            True if sent successfully
        """
        try:
            # This would be called by GUI polling or event system
            # For now, just log
            logger.info(f"GUI alert: {alert['title']} ({alert['severity']})")
            
            alert['sent_to_gui'] = True
            return True
            
        except Exception as e:
            logger.error(f"Error sending alert to GUI: {e}")
            return False
    
    def dispatch_alert(
        self,
        severity: AlertSeverity,
        title: str,
        message: str,
        source: str,
        channels: List[str] = None,
        object_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        telegram_chat_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Create and dispatch alert to specified channels.
        
        Args:
            severity: Alert severity
            title: Alert title
            message: Alert message
            source: Alert source
            channels: List of channels to send to (['telegram', 'gui'])
            object_id: Associated object ID
            metadata: Additional metadata
            telegram_chat_id: Telegram chat ID for Telegram alerts
            
        Returns:
            Alert dict with dispatch status
        """
        if channels is None:
            channels = ['gui']  # Default to GUI only
        
        # Create alert
        alert = self.create_alert(
            severity=severity,
            title=title,
            message=message,
            source=source,
            object_id=object_id,
            metadata=metadata
        )
        
        # Dispatch to channels
        if 'telegram' in channels and telegram_chat_id:
            self.send_to_telegram(alert, telegram_chat_id)
        
        if 'gui' in channels:
            self.send_to_gui(alert)
        
        return alert
    
    def get_recent_alerts(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get recent alerts.
        
        Args:
            limit: Maximum number of alerts
            
        Returns:
            List of recent alerts
        """
        return self.alert_history[-limit:]
    
    def get_alerts_by_severity(self, severity: AlertSeverity) -> List[Dict[str, Any]]:
        """
        Get alerts by severity.
        
        Args:
            severity: Alert severity
            
        Returns:
            List of alerts with that severity
        """
        return [alert for alert in self.alert_history if alert['severity'] == severity.value]
    
    def get_alerts_by_object(self, object_id: str) -> List[Dict[str, Any]]:
        """
        Get alerts for a specific object.
        
        Args:
            object_id: Object ID
            
        Returns:
            List of alerts for that object
        """
        return [alert for alert in self.alert_history if alert['object_id'] == object_id]
    
    def clear_old_alerts(self, days: int = 30):
        """
        Clear alerts older than specified days.
        
        Args:
            days: Days threshold
        """
        cutoff = datetime.now() - timedelta(days=days)
        
        self.alert_history = [
            alert for alert in self.alert_history
            if datetime.fromisoformat(alert['created_at']) > cutoff
        ]
        
        logger.info(f"Cleared alerts older than {days} days")


# Global alert dispatcher instance
_alert_dispatcher: Optional[AlertDispatcher] = None


def get_alert_dispatcher() -> AlertDispatcher:
    """Get global alert dispatcher instance."""
    global _alert_dispatcher
    if _alert_dispatcher is None:
        _alert_dispatcher = AlertDispatcher()
    return _alert_dispatcher


if __name__ == "__main__":
    # Test Alert Dispatcher
    logging.basicConfig(level=logging.INFO)
    
    dispatcher = AlertDispatcher()
    
    # Create test alert
    alert = dispatcher.dispatch_alert(
        severity=AlertSeverity.HIGH,
        title="Deadline Warning",
        message="Project deadline is approaching in 3 days",
        source="temporal_logic",
        channels=['gui'],
        object_id="TEST-001"
    )
    
    print(f"Created alert: {alert}")
    
    # Get recent alerts
    recent = dispatcher.get_recent_alerts()
    print(f"Recent alerts: {len(recent)}")
