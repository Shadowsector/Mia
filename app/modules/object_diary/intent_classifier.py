"""Intent Classifier - Analyze user intent based on basic concepts.

This module implements the Intent Classifier pattern for understanding
user actions in the construction domain.
"""

import logging
from typing import Dict, List, Any, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class IntentType(str, Enum):
    """Types of user intents."""
    QUERY_STATUS = "query_status"  # Ask about project status
    QUERY_MATERIAL = "query_material"  # Ask about materials
    QUERY_FINANCIAL = "query_financial"  # Ask about finances
    QUERY_DOCUMENT = "query_document"  # Ask about documents
    REQUEST_ACTION = "request_action"  # Request an action
    REPORT_ISSUE = "report_issue"  # Report a problem
    REQUEST_APPROVAL = "request_approval"  # Request approval
    SYSTEM_CONTROL = "system_control"  # Control system components
    GENERAL_CHAT = "general_chat"  # General conversation


class IntentClassifier:
    """
    Classify user intent based on basic construction concepts.
    
    Uses pattern matching and keyword analysis to determine
    what the user wants to do.
    """
    
    # Keywords for each intent type
    INTENT_KEYWORDS = {
        IntentType.QUERY_STATUS: [
            'статус', 'status', 'как дела', 'как идет', 'прогресс', 'progress',
            'состояние', 'ready', 'готово'
        ],
        IntentType.QUERY_MATERIAL: [
            'материал', 'material', 'кабель', 'cable', 'труба', 'pipe',
            'провод', 'wire', 'доставка', 'delivery', 'наличие', 'available'
        ],
        IntentType.QUERY_FINANCIAL: [
            'деньги', 'money', 'бюджет', 'budget', 'оплата', 'payment',
            'счет', 'invoice', 'смета', 'estimate', 'цена', 'price', 'стоимость'
        ],
        IntentType.QUERY_DOCUMENT: [
            'документ', 'document', 'договор', 'contract', 'акт', 'act',
            'кп', 'proposal', 'счёт', 'invoice', 'файл', 'file'
        ],
        IntentType.REQUEST_ACTION: [
            'сделай', 'do', 'выполни', 'execute', 'запусти', 'start',
            'создай', 'create', 'обнови', 'update', 'измени', 'change'
        ],
        IntentType.REPORT_ISSUE: [
            'проблема', 'problem', 'ошибка', 'error', 'не работает', 'not working',
            'баг', 'bug', 'сломалось', 'broken', 'задержка', 'delay'
        ],
        IntentType.REQUEST_APPROVAL: [
            'одобри', 'approve', 'разреши', 'allow', 'подтверди', 'confirm',
            'согласие', 'consent', 'разрешение', 'permission'
        ],
        IntentType.SYSTEM_CONTROL: [
            'запусти бота', 'start bot', 'останови бота', 'stop bot',
            'статус системы', 'system status', 'перезагрузи', 'restart'
        ]
    }
    
    def __init__(self):
        """Initialize Intent Classifier."""
        pass
    
    def classify(self, text: str) -> Dict[str, Any]:
        """
        Classify user intent from text.
        
        Args:
            text: User message text
            
        Returns:
            Classification result with intent and confidence
        """
        text_lower = text.lower()
        
        # Score each intent type. Longer (more specific) keywords weigh more,
        # so "запусти бота" beats the generic "запусти".
        scores = {}
        for intent_type, keywords in self.INTENT_KEYWORDS.items():
            score = 0
            for keyword in keywords:
                if keyword in text_lower:
                    score += len(keyword)
            scores[intent_type] = score
        
        # Find best match
        if not scores or max(scores.values()) == 0:
            return {
                'intent': IntentType.GENERAL_CHAT,
                'confidence': 0.5,
                'reason': 'No matching keywords'
            }
        
        best_intent = max(scores, key=scores.get)
        max_score = scores[best_intent]
        
        # Calculate confidence (normalized by keyword count)
        confidence = min(max_score / 3, 1.0)
        
        return {
            'intent': best_intent,
            'confidence': confidence,
            'all_scores': scores,
            'reason': f"Matched {max_score} keywords for {best_intent.value}"
        }
    
    def extract_entities(self, text: str, intent: IntentType) -> Dict[str, Any]:
        """
        Extract entities based on intent.
        
        Args:
            text: User message text
            intent: Classified intent
            
        Returns:
            Extracted entities
        """
        entities = {}
        
        # Extract object references
        import re
        object_match = re.search(r'объект[:\s]+(\d+)', text, re.IGNORECASE)
        if object_match:
            entities['object_id'] = object_match.group(1)
        
        # Extract dates
        date_match = re.search(r'(\d{1,2})\.(\d{1,2})\.(\d{4})', text)
        if date_match:
            entities['date'] = f"{date_match.group(3)}-{date_match.group(2)}-{date_match.group(1)}"
        
        # Extract amounts
        amount_match = re.search(r'(\d+[.,]\d+)\s*(?:руб|р\.|₽)', text)
        if amount_match:
            entities['amount'] = amount_match.group(1).replace(',', '.')
        
        return entities
    
    def classify_with_entities(self, text: str) -> Dict[str, Any]:
        """
        Classify intent and extract entities.
        
        Args:
            text: User message text
            
        Returns:
            Classification with entities
        """
        classification = self.classify(text)
        intent = classification['intent']
        
        entities = self.extract_entities(text, intent)
        
        classification['entities'] = entities
        
        return classification


if __name__ == "__main__":
    # Test Intent Classifier
    logging.basicConfig(level=logging.INFO)
    
    classifier = IntentClassifier()
    
    # Test queries
    test_queries = [
        "Какой статус объекта 123?",
        "Кабель доставлен?",
        "Какой бюджет проекта?",
        "Покажи договор",
        "Запусти бота",
        "Есть проблема с доставкой"
    ]
    
    for query in test_queries:
        result = classifier.classify_with_entities(query)
        print(f"'{query}' -> {result['intent'].value} (confidence: {result['confidence']})")
        if result['entities']:
            print(f"  Entities: {result['entities']}")
