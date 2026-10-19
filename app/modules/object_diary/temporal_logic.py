"""Temporal Logic - Time-based reasoning and deadline management.

This module implements temporal logic for construction projects:
- Absolute Time Injection
- Deadline tracking
- Schedule validation
- Time-based constraints
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from decimal import Decimal

from app.modules.storage.database import get_db_connection

logger = logging.getLogger(__name__)


class TemporalLogic:
    """
    Temporal logic for construction projects.
    
    Handles time-based reasoning, deadline tracking,
    and schedule validation.
    """
    
    def __init__(self):
        """Initialize Temporal Logic."""
        pass
    
    def inject_absolute_time(self, relative_time: str, reference_date: Optional[datetime] = None) -> datetime:
        """
        Convert relative time to absolute datetime.
        
        Args:
            relative_time: Relative time expression (e.g., "2 weeks", "3 days", "1 month")
            reference_date: Reference date (defaults to now)
            
        Returns:
            Absolute datetime
        """
        if reference_date is None:
            reference_date = datetime.now()
        
        relative_time = relative_time.lower().strip()
        
        # Parse quantity and unit
        import re
        match = re.search(r'(\d+)', relative_time)
        if not match:
            return reference_date
        
        quantity = int(match.group(1))
        
        if 'недел' in relative_time or 'week' in relative_time:
            return reference_date + timedelta(weeks=quantity)
        if 'месяц' in relative_time or 'month' in relative_time:
            return reference_date + timedelta(days=quantity * 30)  # Approximate
        if 'год' in relative_time or 'year' in relative_time:
            return reference_date + timedelta(days=quantity * 365)  # Approximate
        
        # Days (explicit or default)
        return reference_date + timedelta(days=quantity)
    
    def calculate_schedule_variance(
        self,
        planned_completion: datetime,
        actual_completion: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Calculate schedule variance.
        
        Args:
            planned_completion: Planned completion date
            actual_completion: Actual completion date (None if not completed)
            
        Returns:
            Variance information
        """
        now = datetime.now()
        
        if actual_completion:
            variance_days = (actual_completion - planned_completion).days
            status = 'completed'
        else:
            variance_days = (now - planned_completion).days
            if variance_days < 0:
                status = 'on_track'
            elif variance_days == 0:
                status = 'due_today'
            else:
                status = 'overdue'
        
        return {
            'planned_completion': planned_completion.isoformat(),
            'actual_completion': actual_completion.isoformat() if actual_completion else None,
            'variance_days': variance_days,
            'status': status
        }
    
    def validate_deadline_feasibility(
        self,
        start_date: datetime,
        deadline: datetime,
        estimated_days: int
    ) -> Dict[str, Any]:
        """
        Validate if a deadline is feasible given estimated duration.
        
        Args:
            start_date: Project start date
            deadline: Required deadline
            estimated_days: Estimated days to complete
            
        Returns:
            Feasibility assessment
        """
        available_days = (deadline - start_date).days
        buffer_days = available_days - estimated_days
        
        if buffer_days >= 7:
            feasibility = 'high'
            confidence = 0.9
        elif buffer_days >= 0:
            feasibility = 'medium'
            confidence = 0.7
        else:
            feasibility = 'low'
            confidence = 0.3
        
        return {
            'available_days': available_days,
            'estimated_days': estimated_days,
            'buffer_days': buffer_days,
            'feasibility': feasibility,
            'confidence': confidence,
            'is_feasible': buffer_days >= 0
        }
    
    def get_critical_path(self, object_id: str) -> List[Dict[str, Any]]:
        """
        Get critical path events for an object.
        
        Args:
            object_id: Object ID
            
        Returns:
            List of critical path events
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Get events with deadlines
                cursor.execute("""
                    SELECT event_id, event_type, event_date, deadline_date, description
                    FROM object_events
                    WHERE object_id = ?
                    AND deadline_date IS NOT NULL
                    ORDER BY deadline_date
                """, (object_id,))
                
                events = []
                for row in cursor.fetchall():
                    deadline = datetime.strptime(row['deadline_date'], '%Y-%m-%d')
                    now = datetime.now()
                    days_until = (deadline - now).days
                    
                    events.append({
                        'event_id': row['event_id'],
                        'event_type': row['event_type'],
                        'event_date': row['event_date'],
                        'deadline_date': row['deadline_date'],
                        'days_until_deadline': days_until,
                        'is_critical': days_until <= 7 and days_until >= 0
                    })
                
                return events
                
        except Exception as e:
            logger.error(f"Error getting critical path for {object_id}: {e}")
            return []
    
    def calculate_burn_rate(
        self,
        start_date: datetime,
        budget: float,
        spent: float
    ) -> Dict[str, Any]:
        """
        Calculate budget burn rate.
        
        Args:
            start_date: Project start date
            budget: Total budget
            spent: Amount spent
            
        Returns:
            Burn rate information
        """
        now = datetime.now()
        elapsed_days = (now - start_date).days
        
        if elapsed_days <= 0:
            return {
                'burn_rate_per_day': 0,
                'projected_completion': None,
                'on_track': True
            }
        
        burn_rate_per_day = spent / elapsed_days
        
        # Assuming 180-day project duration (can be configured)
        estimated_total_days = 180
        projected_total = burn_rate_per_day * estimated_total_days
        
        if projected_total <= budget:
            on_track = True
        else:
            on_track = False
        
        return {
            'burn_rate_per_day': burn_rate_per_day,
            'projected_total': projected_total,
            'budget': budget,
            'budget_remaining': budget - spent,
            'on_track': on_track,
            'over_budget_risk': projected_total > budget
        }
    
    def generate_time_report(self, object_id: str) -> Dict[str, Any]:
        """
        Generate comprehensive time-based report for an object.
        
        Args:
            object_id: Object ID
            
        Returns:
            Time report
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Get object info
                cursor.execute("""
                    SELECT contract_date, contract_amount, created_at
                    FROM objects WHERE object_id = ?
                """, (object_id,))
                
                row = cursor.fetchone()
                if not row:
                    return {'error': 'Object not found'}
                
                contract_date = datetime.strptime(row['contract_date'], '%Y-%m-%d') if row['contract_date'] else None
                budget = float(row['contract_amount']) if row['contract_amount'] else 0
                
                # Get spent amount (from invoices)
                cursor.execute("""
                    SELECT SUM(amount) as total_spent
                    FROM invoices WHERE object_id = ?
                """, (object_id,))
                
                spent_row = cursor.fetchone()
                spent = float(spent_row['total_spent']) if spent_row and spent_row['total_spent'] else 0
                
                # Calculate metrics
                report = {
                    'object_id': object_id,
                    'contract_date': contract_date.isoformat() if contract_date else None,
                    'days_since_contract': (datetime.now() - contract_date).days if contract_date else None,
                    'critical_path': self.get_critical_path(object_id),
                    'burn_rate': self.calculate_burn_rate(contract_date, budget, spent) if contract_date else None,
                    'generated_at': datetime.now().isoformat()
                }
                
                return report
                
        except Exception as e:
            logger.error(f"Error generating time report for {object_id}: {e}")
            return {'error': str(e)}


if __name__ == "__main__":
    # Test Temporal Logic
    logging.basicConfig(level=logging.INFO)
    
    temporal = TemporalLogic()
    
    # Test absolute time injection
    absolute = temporal.inject_absolute_time("2 weeks")
    print(f"2 weeks from now: {absolute}")
    
    # Test schedule variance
    planned = datetime(2024, 12, 31)
    variance = temporal.calculate_schedule_variance(planned)
    print(f"Schedule variance: {variance}")
    
    # Test deadline feasibility
    start = datetime(2024, 10, 1)
    deadline = datetime(2024, 12, 31)
    feasibility = temporal.validate_deadline_feasibility(start, deadline, 60)
    print(f"Deadline feasibility: {feasibility}")
