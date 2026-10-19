"""Accuracy Contour Manager - Triple Audit for Deadlines and Metrics - RFC v1.9"""

from typing import Optional, List, Dict, Any
from datetime import datetime
import networkx as nx
from enum import Enum


class CheckStatus(str, Enum):
    """Статус проверки"""
    OK = "OK"
    WARNING = "WARNING"
    BLOCK = "BLOCK"
    UNKNOWN = "UNKNOWN"


class Method1Result:
    """Результат Метода 1 (NetworkX - детерминированный граф зависимостей)"""
    
    def __init__(self):
        self.status = CheckStatus.UNKNOWN
        self.violations: List[str] = []
        self.blocking_constraints: List[str] = []
        self.bypass_strict_rule = False
        self.bypass_reason: Optional[str] = None


class Method2Result:
    """Результат Метода 2 (RAG - сравнение сущностей)"""
    
    def __init__(self):
        self.status = CheckStatus.UNKNOWN
        self.anomalies: List[Dict[str, Any]] = []
        self.confidence: float = 0.0


class Method3Result:
    """Результат Метода 3 (Telegram - анализ временных сдвигов)"""
    
    def __init__(self):
        self.status = CheckStatus.UNKNOWN
        self.informal_deadlines: List[Dict[str, Any]] = []
        self.chat_derived_facts: List[Dict[str, Any]] = []
        self.bypass_strict_rule = False
        self.bypass_reason: Optional[str] = None


class ConsensusResult:
    """Результат Консенсус-Арбитра"""
    
    def __init__(self):
        self.final_status = CheckStatus.UNKNOWN
        self.conflicts: List[str] = []
        self.resolution: Optional[str] = None
        self.method_outputs: Dict[str, Any] = {}


class AccuracyContourManager:
    """Контур точности: Тройной перекрестный аудит дедлайнов и показателей"""
    
    def __init__(self):
        # Инициализация NetworkX графа для Метода 1
        self.dependency_graph = nx.DiGraph()
        
        # Определение правил строительного ГОСТа и регламентов
        self.regulatory_rules = self._initialize_regulatory_rules()
    
    def _initialize_regulatory_rules(self) -> Dict[str, List[str]]:
        """Инициализация неизменных правил строительного ГОСТа и регламентов"""
        return {
            "earthworks": ["OATI_NOTIFICATION", "STAMP_OPS_MGGT"],
            "cable_installation": ["TELCO_APPROVAL", "TECHNICAL_SPECIFICATION"],
            "handover": ["ACT_COMPLETION", "ACCEPTANCE_PROTOCOL"],
            "materials_delivery": ["INVOICE_VERIFICATION", "QUALITY_CERTIFICATE"]
        }
    
    # ==================== Метод 1: Детерминированный Граф Зависимостей (NetworkX) ====================
    
    def method1_networkx_check(
        self,
        action_type: str,
        current_state: Dict[str, Any],
        bypass_strict_rule: bool = False,
        bypass_reason: Optional[str] = None
    ) -> Method1Result:
        """
        Метод 1: Детерминированный Граф Зависимостей (NetworkX)
        Жесткий код на Python-библиотеке NetworkX
        Описывает неизменные правила строительного ГОСТа и регламентов
        """
        result = Method1Result()
        
        # Проверка наличия требуемых ограничений для действия
        required_constraints = self.regulatory_rules.get(action_type, [])
        
        blocking_constraints = []
        for constraint in required_constraints:
            if not current_state.get(constraint, False):
                blocking_constraints.append(constraint)
        
        # Если есть блокирующие ограничения
        if blocking_constraints:
            # Проверка "Пакта о помиловании" от Метода 3
            if bypass_strict_rule and bypass_reason:
                result.status = CheckStatus.WARNING
                result.bypass_strict_rule = True
                result.bypass_reason = bypass_reason
                result.violations = [f"Constraint {c} bypassed: {bypass_reason}" for c in blocking_constraints]
            else:
                result.status = CheckStatus.BLOCK
                result.blocking_constraints = blocking_constraints
                result.violations = [f"Missing constraint: {c}" for c in blocking_constraints]
        else:
            result.status = CheckStatus.OK
        
        return result
    
    def build_dependency_graph(self, constraints: List[Dict[str, Any]]):
        """Построение графа зависимостей ограничений"""
        self.dependency_graph.clear()
        
        for constraint in constraints:
            constraint_id = constraint['constraint_id']
            self.dependency_graph.add_node(constraint_id, **constraint)
            
            # Добавление зависимостей
            for dep in constraint.get('depends_on', []):
                self.dependency_graph.add_edge(dep, constraint_id)
    
    def check_constraint_network(self, object_id: str) -> Dict[str, Any]:
        """Проверка сети ограничений на предмет циклов и блокировок"""
        has_cycles = not nx.is_directed_acyclic_graph(self.dependency_graph)
        
        # Поиск слабо связанных компонентов
        weakly_connected = list(nx.weakly_connected_components(self.dependency_graph))
        
        return {
            "has_cycles": has_cycles,
            "num_components": len(weakly_connected),
            "largest_component_size": max(len(c) for c in weakly_connected) if weakly_connected else 0
        }
    
    # ==================== Метод 2: Критический RAG по Спецификациям ====================
    
    def method2_rag_check(
        self,
        specification_text: str,
        reference_documents: List[str],
        rag_manager
    ) -> Method2Result:
        """
        Метод 2: Критический RAG по Спецификациям (Ollama 8B - mistral:7b-instruct-v0.3)
        Изолированное сравнение сущностей: Смета/КП ↔ Накладные/Акты ↔ Текущий таймлайн
        Находит аномалии во времени и деньгах
        """
        result = Method2Result()
        
        # TODO: Интеграция с ChromaManager для поиска аномалий
        # Поиск по reference_documents в RAG
        # Сравнение с specification_text
        
        # Временная заглушка
        result.status = CheckStatus.OK
        result.anomalies = []
        result.confidence = 0.8
        
        return result
    
    # ==================== Метод 3: Анализатор Временных Сдвигов ====================
    
    def method3_telegram_check(
        self,
        telegram_messages: List[Dict[str, Any]],
        official_documents: List[Dict[str, Any]]
    ) -> Method3Result:
        """
        Метод 3: Анализатор Временных Сдвигов (Ollama 14B - qwen2.5:14b-instruct-q4_K_M)
        Читает переписку из Telegram-каналов объектов
        Сопоставляет с официальными документами
        Ловит неформальные дедлайны и перемещения
        """
        result = Method3Result()
        
        # TODO: Интеграция с OllamaClient для анализа Telegram
        # Извлечение неформальных дедлайнов из чата
        # Сопоставление с официальными документами
        # Возможность наложить BYPASS_STRICT_RULE на Метод 1
        
        # Временная заглушка
        result.status = CheckStatus.OK
        result.informal_deadlines = []
        result.chat_derived_facts = []
        
        return result
    
    # ==================== Консенсус-Арбитр ====================
    
    def consensus_arbiter(
        self,
        method1_result: Method1Result,
        method2_result: Method2Result,
        method3_result: Method3Result
    ) -> ConsensusResult:
        """
        Консенсус-Арбитр:
        Специальный промпт собирает выводы трех методов
        Если Метод 1 говорит "нельзя копать", а Метод 3 видит "мы начали копать"
        Mia бьет в набат: Критическое нарушение регламента
        """
        result = ConsensusResult()
        
        # Сохранение выводов методов
        result.method_outputs = {
            "method1": {
                "status": method1_result.status.value,
                "violations": method1_result.violations,
                "bypass": method1_result.bypass_strict_rule
            },
            "method2": {
                "status": method2_result.status.value,
                "anomalies": method2_result.anomalies,
                "confidence": method2_result.confidence
            },
            "method3": {
                "status": method3_result.status.value,
                "informal_deadlines": method3_result.informal_deadlines,
                "bypass": method3_result.bypass_strict_rule
            }
        }
        
        # Логика консенсуса
        # Если Метод 1 говорит BLOCK, а Метод 3 говорит OK с BYPASS
        if method1_result.status == CheckStatus.BLOCK and method3_result.bypass_strict_rule:
            result.final_status = CheckStatus.WARNING
            result.resolution = f"Method 1 block bypassed by Method 3: {method3_result.bypass_reason}"
            result.conflicts = ["Formal vs Informal deadline conflict"]
        
        # Если Метод 1 говорит BLOCK, а Метод 3 не подтверждает BYPASS
        elif method1_result.status == CheckStatus.BLOCK:
            result.final_status = CheckStatus.BLOCK
            result.resolution = "Formal blocking constraints take precedence"
            result.conflicts = method1_result.violations
        
        # Если все методы согласны
        elif (method1_result.status == CheckStatus.OK and 
              method2_result.status == CheckStatus.OK and 
              method3_result.status == CheckStatus.OK):
            result.final_status = CheckStatus.OK
            result.resolution = "All methods agree: OK"
        
        # Если есть аномалии в Методе 2
        elif method2_result.anomalies:
            result.final_status = CheckStatus.WARNING
            result.resolution = f"Anomalies detected: {len(method2_result.anomalies)} issues"
            result.conflicts = [a['description'] for a in method2_result.anomalies]
        
        else:
            result.final_status = CheckStatus.UNKNOWN
            result.resolution = "Unable to determine consensus"
        
        return result
    
    def run_full_audit(
        self,
        action_type: str,
        current_state: Dict[str, Any],
        specification_text: Optional[str] = None,
        telegram_messages: Optional[List[Dict[str, Any]]] = None,
        rag_manager=None
    ) -> ConsensusResult:
        """Запуск полного тройного аудита"""
        
        # Метод 1: NetworkX
        m1_result = self.method1_networkx_check(action_type, current_state)
        
        # Метод 2: RAG
        m2_result = Method2Result()
        if specification_text and rag_manager:
            m2_result = self.method2_rag_check(specification_text, [], rag_manager)
        
        # Метод 3: Telegram
        m3_result = Method3Result()
        if telegram_messages:
            m3_result = self.method3_telegram_check(telegram_messages, [])
        
        # Консенсус-Арбитр
        return self.consensus_arbiter(m1_result, m2_result, m3_result)
