"""Integration: ConstraintManager + HealthScore - RFC v1.9"""

from typing import Any, Dict

from app.modules.object_diary.constraint_manager import (
    ConstraintManager,
    ConstraintStatus,
)
from app.modules.object_diary.health_score_engine import HealthScoreEngine

# Must match the weights used by HealthScoreEngine.calculate_health_score
WEIGHTS = {
    'schedule': 0.3,
    'budget': 0.3,
    'constraint': 0.2,
    'silence': 0.2,
}


def _zone_for(score: float) -> str:
    if score <= 30:
        return 'green'
    if score <= 60:
        return 'yellow'
    return 'red'


class ConstraintHealthIntegration:
    """
    Интеграция ConstraintManager и HealthScoreEngine.

    - Блокирующие ограничения не дают выполнить действие.
    - Предупреждающие ограничения учитываются в Health Score.
    - Зона риска определяет уровень алерта.
    """

    def __init__(self):
        self.constraint_manager = ConstraintManager()
        self.health_engine = HealthScoreEngine()

    def check_action_with_health_impact(
        self,
        object_id: str,
        action: str,
    ) -> Dict[str, Any]:
        """Проверить действие с учётом ограничений и Health Score."""
        feasibility = self.constraint_manager.can_proceed(object_id, action)
        health = self.health_engine.calculate_health_score(object_id)

        constraints = self.constraint_manager.get_object_constraints(object_id)
        warnings = [
            c for c in constraints
            if c['status'] == ConstraintStatus.NOT_SATISFIED.value
            and c['severity_level'] != 'CRITICAL'
            and action in c['required_for']
        ]

        if not feasibility['can_proceed']:
            return {
                'can_proceed': False,
                'block_reason': feasibility['message'],
                'blocking_constraints': [
                    c['description'] for c in feasibility['blocking_constraints']
                ],
                'health_score': health['overall_score'],
                'health_zone': health['zone'],
                'recommendation': 'Устраните блокирующие ограничения перед продолжением',
            }

        if warnings:
            return {
                'can_proceed': True,
                'warnings': [c['description'] for c in warnings],
                'health_score': health['overall_score'],
                'health_zone': health['zone'],
                'recommendation': (
                    f"Продолжить с осторожностью: {len(warnings)} предупреждений"
                ),
            }

        return {
            'can_proceed': True,
            'health_score': health['overall_score'],
            'health_zone': health['zone'],
            'recommendation': 'Можно продолжать',
        }

    def generate_alert_by_zone(self, object_id: str) -> Dict[str, Any]:
        """Сгенерировать алерт на основе зоны риска."""
        health = self.health_engine.calculate_health_score(object_id)
        zone = health['zone']

        if zone == 'red':
            return {
                'alert_level': 'CRITICAL',
                'message': f"КРИТИЧЕСКИЙ РИСК на объекте {object_id}",
                'score': health['overall_score'],
                'risk_factors': health['components'],
                'action_required': 'Немедленное вмешательство',
                'blocking_constraints': self.constraint_manager.get_object_constraints(
                    object_id, ConstraintStatus.BLOCKING
                ),
            }
        if zone == 'yellow':
            return {
                'alert_level': 'WARNING',
                'message': f"Риск нарастает на объекте {object_id}",
                'score': health['overall_score'],
                'risk_factors': health['components'],
                'action_required': 'Проверьте предупреждающие ограничения',
                'blocking_constraints': [],
            }
        return {
            'alert_level': 'OK',
            'message': f"Стабильное состояние объекта {object_id}",
            'score': health['overall_score'],
            'risk_factors': [],
            'action_required': 'Продолжить мониторинг',
            'blocking_constraints': [],
        }

    def evaluate_dependency_impact(
        self,
        object_id: str,
        constraint_satisfied: bool = True,
    ) -> Dict[str, Any]:
        """
        Оценить, как снятие одного блокирующего ограничения изменит Health Score.

        Оценка не изменяет БД: пересчитывается только constraint-компонент
        (каждое блокирующее ограничение даёт +15 к риску, как в
        HealthScoreEngine.calculate_constraint_risk).
        """
        health = self.health_engine.calculate_health_score(object_id)
        components = health['components']
        old_score = health['overall_score']

        if not constraint_satisfied:
            return {
                'old_score': old_score,
                'new_score': old_score,
                'improvement': 0.0,
                'zone_changed': False,
                'message': 'Health Score не изменился',
            }

        blocking = self.constraint_manager.get_object_constraints(
            object_id, ConstraintStatus.BLOCKING
        )
        if not blocking:
            return {
                'old_score': old_score,
                'new_score': old_score,
                'improvement': 0.0,
                'zone_changed': False,
                'message': 'Нет блокирующих ограничений для снятия',
            }

        projected_constraint_risk = min(max(len(blocking) - 1, 0) * 15, 100)
        new_score = round(
            components['schedule_risk'] * WEIGHTS['schedule']
            + components['budget_risk'] * WEIGHTS['budget']
            + projected_constraint_risk * WEIGHTS['constraint']
            + components['silence_risk'] * WEIGHTS['silence'],
            2,
        )

        return {
            'old_score': old_score,
            'new_score': new_score,
            'improvement': round(old_score - new_score, 2),
            'zone_changed': _zone_for(new_score) != _zone_for(old_score),
            'message': 'Health Score улучшен',
        }
