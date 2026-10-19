"""Health Score Engine - Calculate cumulative risk for construction objects.

This module implements the Health Score calculation based on:
- Multiple small events
- Schedule variance
- Budget overruns
- Material delays
- Unresolved constraints
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from decimal import Decimal

from app.modules.storage.database import get_db_connection

logger = logging.getLogger(__name__)


class HealthScoreEngine:
    """
    Calculate health score for construction objects.
    
    Health Score is a cumulative risk metric that combines
    multiple factors into a single indicator:
    - Green zone: 0-30 (low risk)
    - Yellow zone: 31-60 (medium risk)
    - Red zone: 61-100 (high risk, potential default)
    """
    
    def __init__(self):
        """Initialize Health Score Engine."""
        pass
    
    def calculate_schedule_risk(self, object_id: str) -> float:
        """
        Calculate schedule risk component.
        
        Args:
            object_id: Object ID
            
        Returns:
            Risk score (0-100)
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Get overdue deadlines
                cursor.execute("""
                    SELECT COUNT(*) as count
                    FROM object_events
                    WHERE object_id = ?
                    AND event_type = 'deadline'
                    AND deadline_date < ?
                    AND status != 'completed'
                """, (object_id, datetime.now().date()))
                
                row = cursor.fetchone()
                overdue_count = row['count'] if row else 0
                
                # Each overdue deadline adds 20 points
                risk = min(overdue_count * 20, 100)
                
                return risk
                
        except Exception as e:
            logger.error(f"Error calculating schedule risk for {object_id}: {e}")
            return 0
    
    def calculate_budget_risk(self, object_id: str) -> float:
        """
        Calculate budget risk component.
        
        Args:
            object_id: Object ID
            
        Returns:
            Risk score (0-100)
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Get budget and spent
                cursor.execute("""
                    SELECT contract_amount
                    FROM objects WHERE object_id = ?
                """, (object_id,))
                
                row = cursor.fetchone()
                if not row or not row['contract_amount']:
                    return 0
                
                budget = float(row['contract_amount'])
                
                cursor.execute("""
                    SELECT SUM(amount) as total_spent
                    FROM invoices WHERE object_id = ?
                """, (object_id,))
                
                spent_row = cursor.fetchone()
                spent = float(spent_row['total_spent']) if spent_row and spent_row['total_spent'] else 0
                
                if budget == 0:
                    return 0
                
                # Calculate utilization percentage
                utilization = (spent / budget) * 100
                
                # Risk increases with utilization
                if utilization > 100:
                    risk = 100
                elif utilization > 90:
                    risk = 80
                elif utilization > 75:
                    risk = 50
                elif utilization > 50:
                    risk = 30
                else:
                    risk = 0
                
                return risk
                
        except Exception as e:
            logger.error(f"Error calculating budget risk for {object_id}: {e}")
            return 0
    
    def calculate_constraint_risk(self, object_id: str) -> float:
        """
        Calculate constraint risk component.
        
        Args:
            object_id: Object ID
            
        Returns:
            Risk score (0-100)
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Get blocking constraints
                cursor.execute("""
                    SELECT COUNT(*) as count
                    FROM constraints
                    WHERE object_id = ? AND status = 'NOT_SATISFIED'
                """, (object_id,))
                
                row = cursor.fetchone()
                blocking_count = row['count'] if row else 0
                
                # Each blocking constraint adds 15 points
                risk = min(blocking_count * 15, 100)
                
                return risk
                
        except Exception as e:
            logger.error(f"Error calculating constraint risk for {object_id}: {e}")
            return 0
    
    def calculate_silence_risk(self, object_id: str) -> float:
        """
        Calculate silence risk component.
        
        Args:
            object_id: Object ID
            
        Returns:
            Risk score (0-100)
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
                    return 50  # No events at all is risky
                
                last_event = datetime.strptime(row['last_event'], '%Y-%m-%d')
                days_since = (datetime.now() - last_event).days
                
                # Risk increases with silence
                if days_since >= 30:
                    risk = 100
                elif days_since >= 14:
                    risk = 75
                elif days_since >= 7:
                    risk = 50
                elif days_since >= 3:
                    risk = 25
                else:
                    risk = 0
                
                return risk
                
        except Exception as e:
            logger.error(f"Error calculating silence risk for {object_id}: {e}")
            return 0
    
    def calculate_health_score(self, object_id: str) -> Dict[str, Any]:
        """
        Calculate overall health score for an object.
        
        Args:
            object_id: Object ID
            
        Returns:
            Health score with components
        """
        schedule_risk = self.calculate_schedule_risk(object_id)
        budget_risk = self.calculate_budget_risk(object_id)
        constraint_risk = self.calculate_constraint_risk(object_id)
        silence_risk = self.calculate_silence_risk(object_id)
        
        # Weighted average (can be adjusted)
        weights = {
            'schedule': 0.3,
            'budget': 0.3,
            'constraint': 0.2,
            'silence': 0.2
        }
        
        overall_score = (
            schedule_risk * weights['schedule'] +
            budget_risk * weights['budget'] +
            constraint_risk * weights['constraint'] +
            silence_risk * weights['silence']
        )
        
        # Determine zone
        if overall_score <= 30:
            zone = 'green'
            zone_name = 'Green Zone (Low Risk)'
        elif overall_score <= 60:
            zone = 'yellow'
            zone_name = 'Yellow Zone (Medium Risk)'
        else:
            zone = 'red'
            zone_name = 'Red Zone (High Risk)'
        
        return {
            'object_id': object_id,
            'overall_score': round(overall_score, 2),
            'zone': zone,
            'zone_name': zone_name,
            'components': {
                'schedule_risk': schedule_risk,
                'budget_risk': budget_risk,
                'constraint_risk': constraint_risk,
                'silence_risk': silence_risk
            },
            'calculated_at': datetime.now().isoformat()
        }
    
    def calculate_all_scores(self) -> Dict[str, Dict[str, Any]]:
        """
        Calculate health scores for all objects.
        
        Returns:
            Dictionary mapping object_id to health score
        """
        scores = {}
        
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT object_id FROM objects")
                
                for row in cursor.fetchall():
                    object_id = row['object_id']
                    score = self.calculate_health_score(object_id)
                    scores[object_id] = score
                    
        except Exception as e:
            logger.error(f"Error calculating all scores: {e}")
        
        return scores
    
    def get_critical_objects(self, threshold: float = 60) -> List[Dict[str, Any]]:
        """
        Get objects in critical zone (red zone).
        
        Args:
            threshold: Score threshold for critical
            
        Returns:
            List of critical objects
        """
        all_scores = self.calculate_all_scores()
        
        critical = [
            {**score, 'object_id': obj_id}
            for obj_id, score in all_scores.items()
            if score['overall_score'] >= threshold
        ]
        
        # Sort by score (highest first)
        critical.sort(key=lambda x: x['overall_score'], reverse=True)
        
        return critical


if __name__ == "__main__":
    # Test Health Score Engine
    logging.basicConfig(level=logging.INFO)
    
    engine = HealthScoreEngine()
    
    # Calculate score for a specific object
    score = engine.calculate_health_score("TEST-001")
    print(f"Health score: {score}")
    
    # Get critical objects
    critical = engine.get_critical_objects()
    print(f"Critical objects: {len(critical)}")
    
    for obj in critical[:5]:
        print(f"  - {obj['object_id']}: {obj['overall_score']} ({obj['zone_name']})")
