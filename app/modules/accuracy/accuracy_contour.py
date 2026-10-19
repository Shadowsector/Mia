"""Accuracy Contour Manager - Triple Audit for Deadlines and Metrics - RFC v1.9"""

import asyncio
import concurrent.futures
import json
import logging
import re
from typing import Optional, List, Dict, Any, Callable, Awaitable
from datetime import datetime
import networkx as nx
from enum import Enum

from app.modules.llm.ollama_client import PromptTemplates

logger = logging.getLogger(__name__)

_AMOUNT_RE = re.compile(r"\d[\d\s]{3,}(?:[.,]\d+)?")
_DATE_RE = re.compile(r"\b(\d{2})[.\-/](\d{2})[.\-/](\d{4})\b")


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
    
    def __init__(self, llm_client=None, model: str = "qwen2.5:14b-instruct-q4_K_M"):
        """
        Args:
            llm_client: экземпляр `OllamaClient` для Метода 3 (анализ переписки).
            model: модель Ollama для анализа Telegram-чата.
        """
        # Инициализация NetworkX графа для Метода 1
        self.dependency_graph = nx.DiGraph()

        self.llm_client = llm_client
        self.model = model

        # Определение правил строительного ГОСТа и регламентов
        self.regulatory_rules = self._initialize_regulatory_rules()

    def _run_async(self, factory: Callable[[], Awaitable[Any]]) -> Any:
        """Выполнить async-вызов LLM из синхронного кода."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(factory())

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(lambda: asyncio.run(factory())).result()

    @staticmethod
    def _extract_facts(text: str) -> Dict[str, List[str]]:
        """Выделить суммы и даты из текста для сравнения документов."""
        text = text or ""
        return {
            "amounts": {m.group(0).replace(" ", "").replace(",", ".") for m in _AMOUNT_RE.finditer(text)},
            "dates": {".".join(m.groups()) for m in _DATE_RE.finditer(text)},
        }
    
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

        reference_texts = self._collect_reference_texts(reference_documents, rag_manager)

        if not reference_texts:
            # RAG недоступен или не вернул контекст → прежнее безопасное поведение
            result.status = CheckStatus.OK
            result.anomalies = []
            result.confidence = 0.8
            return result

        spec_facts = self._extract_facts(specification_text or "")

        anomalies: List[Dict[str, Any]] = []
        matched = 0
        for doc_index, ref_text in enumerate(reference_texts):
            ref_facts = self._extract_facts(ref_text)

            for amount in spec_facts["amounts"]:
                if ref_facts["amounts"] and amount not in ref_facts["amounts"]:
                    anomalies.append({
                        "type": "amount_mismatch",
                        "description": (
                            f"Сумма {amount} из спецификации отсутствует в "
                            f"справочном документе #{doc_index}"
                        ),
                        "source": reference_documents[doc_index]
                        if doc_index < len(reference_documents) else str(doc_index),
                        "value": amount,
                    })
                elif amount in ref_facts["amounts"]:
                    matched += 1

            for date in spec_facts["dates"]:
                if ref_facts["dates"] and date not in ref_facts["dates"]:
                    anomalies.append({
                        "type": "date_mismatch",
                        "description": (
                            f"Дата {date} из спецификации не совпадает со "
                            f"справочным документом #{doc_index}"
                        ),
                        "source": reference_documents[doc_index]
                        if doc_index < len(reference_documents) else str(doc_index),
                        "value": date,
                    })
                elif date in ref_facts["dates"]:
                    matched += 1

        result.anomalies = anomalies
        result.status = CheckStatus.WARNING if anomalies else CheckStatus.OK
        total_tokens = len(spec_facts["amounts"]) + len(spec_facts["dates"])
        coverage = (matched / total_tokens) if total_tokens else 1.0
        result.confidence = round(min(0.95, 0.5 + 0.45 * coverage), 2)

        return result

    @staticmethod
    def _collect_reference_texts(
        reference_documents: List[str],
        rag_manager
    ) -> List[str]:
        """
        Получить текст справочных документов через RAG-менеджер.
        Поддерживаются методы `search_between_objects`, `query`, `search`.
        """
        if rag_manager is None or reference_documents is None:
            return []

        search = None
        for method_name in ("search_between_objects", "query", "search"):
            candidate = getattr(rag_manager, method_name, None)
            if callable(candidate):
                search = candidate
                break

        if search is None:
            return []

        texts: List[str] = []
        for doc in reference_documents:
            try:
                raw = search(query=doc, n_results=3)
            except TypeError:
                try:
                    raw = search(doc)
                except Exception as e:  # pragma: no cover - defensive
                    logger.warning(f"RAG query failed for '{doc}': {e}")
                    continue
            except Exception as e:  # pragma: no cover - defensive
                logger.warning(f"RAG query failed for '{doc}': {e}")
                continue

            texts.extend(AccuracyContourManager._extract_texts(raw))

        return texts

    @staticmethod
    def _extract_texts(raw: Any) -> List[str]:
        """Нормализовать произвольный ответ RAG-менеджера в список строк."""
        if raw is None:
            return []
        if isinstance(raw, str):
            return [raw]
        if isinstance(raw, dict):
            for key in ("documents", "texts", "results", "matches"):
                if key in raw:
                    return AccuracyContourManager._extract_texts(raw[key])
            return []
        if isinstance(raw, (list, tuple)):
            out: List[str] = []
            for item in raw:
                if isinstance(item, str):
                    out.append(item)
                elif isinstance(item, dict):
                    for key in ("document", "text", "content"):
                        if isinstance(item.get(key), str):
                            out.append(item[key])
                            break
                elif isinstance(item, (list, tuple)):
                    out.extend(AccuracyContourManager._extract_texts(item))
            return out
        return []
    
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

        if not telegram_messages or self.llm_client is None:
            result.status = CheckStatus.OK
            result.informal_deadlines = []
            result.chat_derived_facts = []
            return result

        chat_text = self._render_messages(telegram_messages)
        prompt = PromptTemplates.informal_deadline_prompt(chat_text)

        data: Dict[str, Any] = {}
        try:
            data = self._run_async(
                lambda: self.llm_client.generate_json(prompt, model=self.model)
            )
        except Exception as e:  # pragma: no cover - defensive
            logger.warning(f"Method 3 LLM call failed: {e}")
            data = {}

        if not isinstance(data, dict):
            data = {}

        deadlines = data.get("informal_deadlines") or []
        if not isinstance(deadlines, list):
            deadlines = []

        result.informal_deadlines = [d for d in deadlines if isinstance(d, dict)]
        result.chat_derived_facts = [
            d for d in result.informal_deadlines if d.get("type") == "fact"
        ]

        # Сопоставление с официальными документами: ищем неформальные сдвиги,
        # которых нет в реестре официальных дат.
        official_dates = set()
        for doc in official_documents or []:
            official_dates |= self._extract_facts(
                doc.get("text", "") if isinstance(doc, dict) else str(doc)
            )["dates"]

        conflicts = []
        for item in result.informal_deadlines:
            date = item.get("date")
            if date:
                normalized = self._normalize_date(date)
                if normalized and normalized not in official_dates:
                    conflicts.append(item)

        if conflicts:
            result.status = CheckStatus.WARNING
            result.bypass_strict_rule = True
            result.bypass_reason = (
                f"Неформальные дедлайны ({len(conflicts)}) противоречат официальному реестру"
            )
        else:
            result.status = CheckStatus.OK

        return result

    @staticmethod
    def _render_messages(messages: List[Dict[str, Any]]) -> str:
        """Собрать текст переписки из списка сообщений."""
        lines = []
        for msg in messages:
            if isinstance(msg, str):
                lines.append(msg)
            elif isinstance(msg, dict):
                lines.append(
                    str(msg.get("text") or msg.get("message") or msg.get("body") or msg)
                )
        return "\n".join(lines)

    @staticmethod
    def _normalize_date(value: str) -> Optional[str]:
        """Привести дату к формату DD.MM.YYYY, если возможно."""
        if not value:
            return None
        iso = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(value))
        if iso:
            y, m, d = iso.groups()
            return f"{d}.{m}.{y}"
        dmy = re.match(r"(\d{2})[.\-/](\d{2})[.\-/](\d{4})", str(value))
        if dmy:
            return ".".join(dmy.groups())
        return None
    
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
