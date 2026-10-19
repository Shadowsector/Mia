"""Integration: ConstraintManager + HealthScore - RFC v1.9"""

from typing import Dict, Any, List
from datetime import datetime

from app.modules.object_diary.constraint_manager import ConstraintManager, ConstraintCheckResult
from app.modules.object_diary.health_score_engine import HealthScoreEngine, RiskZone


class ConstraintHealthIntegration:
    """
    Интеграция ConstraintManager и HealthScoreEngine
    Жесткая блокировка для CRITICAL ограничений
    Кумулятивный риск от нескольких ограничений
    """
    
    def __init__(self):
        self.constraint_manager = ConstraintManager()
        self.health_engine = HealthScoreEngine()
    
    def check_action_with_health_impact(
        self,
        object_id: str,
        action: str
    ) -> Dict[str, Any]:
        """
        Проверить действие с учетом влияния на Health Score
        Интегрирует проверку ограничений и расчет риска
        """
        # Шаг 1: Проверка ограничений
        constraint_result = self.constraint_manager.check_constraints_for_action(
            object_id=object_id,
            action=action
        )
        
        # Шаг 2: Расчет текущего Health Score
        health_score = self.health_engine.calculate_health_score(object_id)
        
        # Шаг 3: Интеграция результатов
        # Если есть CRITICAL блокирующие ограничения → жесткая блокировка
        critical_blocking = [
            c for c in constraint_result.blocking_constraints
            if c.severity_level == "CRITICAL"
        ]
        
        if critical_blocking:
            return {
                "can_proceed": False,
                "block_reason": "CRITICAL constraints block action",
                "blocking_constraints": [c.constraint_name for c in critical_blocking],
                "health_score": health_score.score,
                "health_zone": health_score.zone,
                "recommendation": "Устраните CRITICAL ограничения перед продолжением"
            }
        
        # Если только MAJOR предупреждения → можно продолжить с риском
        if constraint_result.warning_constraints:
            # Кумулятивный риск увеличивается
            self.health_engine.accumulate_risk_factors(
                object_id=object_id,
                new_event={
                    'type': 'constraint_warning',
                    'action': action,
                    'severity': 'MAJOR',
                    'count': len(constraint_result.warning_constraints)
                }
            )
            
            return {
                "can_proceed": True,
                "warnings": [c.constraint_name for c in constraint_result.warning_constraints],
                "health_score": health_score.score,
                "health_zone": health_score.zone,
                "recommendation": f"Продолжить с осторожностью: {len(constraint_result.warning_constraints)} MAJOR предупреждений"
            }
        
        # Если все хорошо
        return {
            "can_proceed": True,
            "health_score": health_score.score,
            "health_zone": health_score.zone,
            "recommendation": "Можно продолжать"
        }
    
    def generate_alert_by_zone(
        self,
        object_id: str
    ) -> Dict[str, Any]:
        """
        Генерировать алерт на основе зоны риска
        GREEN → OK, YELLOW → WARNING, RED → CRITICAL
        """
        health_score = self.health_engine.calculate_health_score(object_id)
        
        if health_score.zone == RiskZone.RED.value:
            return {
                "alert_level": "CRITICAL",
                "message": f"КРИТИЧЕСКИЙ РИСК на объекте {object_id}",
                "score": health_score.score,
                "risk_factors": health_score.risk_factors,
                "action_required": "Немедленное вмешательство",
                "blocking_constraints": self.constraint_manager.get_blocking_constraints(object_id)
            }
        elif health_score.zone == RiskZone.YELLOW.value:
            return {
                "alert_level": "WARNING",
                "message": f"Риск нарастает на объекте {object_id}",
                "score": health_score.score,
                "risk_factors": health_score.risk_factors,
                "action_required": "Проверьте WARNING ограничения",
                "blocking_constraints": []
            }
        else:
            return {
                "alert_level": "OK",
                "message": f"Стабильное состояние объекта {object_id}",
                "score": health_score.score,
                "risk_factors": [],
                "action_required": "Продолжить мониторинг",
                "blocking_constraints": []
            }
    
    def evaluate_dependency_impact(
        self,
        object_id: str,
        constraint_satisfied: bool
    ) -> Dict[str, Any]:
        """
        Оценить влияние изменения ограничения на Health Score
        Если CRITICAL ограничение удовлетворено → снижается риск
        """
        old_score = self.health_engine._get_current_score(object_id)
        
        # Если ограничение удовлетворено, пересчитываем score
        if constraint_satisfied:
            new_score = self.health_engine.calculate_health_score(object_id)
            
            return {
                "old_score": old_score,
                "new_score": new_score.score,
                "improvement": old_score - new_score.score,
                "zone_changed": new_score.zone != self.health_engine._get_risk_zone(old_score),
                "message": "Health Score улучшен"
            }
        else:
            return {
                "old_score": old_score,
                "new_score": old_score,
                "improvement": 0.0,
                "zone_changed": False,
                "message": "Health Score не изменился"
            }
