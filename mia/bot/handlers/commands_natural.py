"""Natural language command handler for system management via Telegram.

Allows users to control Mia PM OS components using natural language commands like:
- "Мия, запусти бота"
- "Мия, статус системы"
- "Мия, останови все"
"""

import logging
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes

from mia.core.employees import get_employee, is_authoritative
from app.runtime.manager import RuntimeManager, ComponentType

logger = logging.getLogger(__name__)


# Command patterns
COMMAND_PATTERNS = {
    'start_telegram': ['запусти бота', 'старт бота', 'запуск бота', 'start bot'],
    'stop_telegram': ['останови бота', 'стоп бота', 'останов бота', 'stop bot'],
    'start_worker': ['запусти воркеров', 'старт воркеров', 'запуск воркеров', 'start workers'],
    'stop_worker': ['останови воркеров', 'стоп воркеров', 'останов воркеров', 'stop workers'],
    'start_all': ['запусти все', 'старт все', 'запуск всех', 'start all'],
    'stop_all': ['останови все', 'стоп все', 'останов всех', 'stop all'],
    'status': ['статус системы', 'системный статус', 'system status', 'как дела система'],
    'restart': ['перезагрузи', 'рестарт', 'restart'],
}


def detect_command(text: str) -> Optional[str]:
    """
    Detect which natural language command is being requested.
    
    Args:
        text: User message text
        
    Returns:
        Command key or None
    """
    text_lower = text.lower()
    
    for command, patterns in COMMAND_PATTERNS.items():
        for pattern in patterns:
            if pattern in text_lower:
                return command
    
    return None


async def handle_natural_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle natural language system management commands.
    
    Only authoritative users (Denis Kuleshov, Alexey Kalachev) can control the system.
    """
    if not update.message or not update.message.text:
        return
    
    user_id = update.effective_user.id
    username = update.effective_user.username
    text = update.message.text
    
    logger.info(f"Natural command from {username} ({user_id}): {text}")
    
    # Check RBAC - only authoritative users can control system
    employee = get_employee(user_id)
    if not employee or not is_authoritative(user_id):
        await update.message.reply_text(
            "⛔ У вас нет прав для управления системой. "
            "Только авторитетные пользователи могут управлять компонентами."
        )
        logger.warning(f"Unauthorized system control attempt by {username} ({user_id})")
        return
    
    # Detect command
    command = detect_command(text)
    if not command:
        await update.message.reply_text(
            "🤔 Я не поняла команду. Доступные команды:\n"
            "- «Мия, запусти бота»\n"
            "- «Мия, останови бота»\n"
            "- «Мия, запусти воркеров»\n"
            "- «Мия, останови воркеров»\n"
            "- «Мия, запусти все»\n"
            "- «Мия, останови все»\n"
            "- «Мия, статус системы»"
        )
        return
    
    # Execute command
    try:
        runtime_manager = RuntimeManager()
        
        if command == 'start_telegram':
            if runtime_manager.start_telegram_bot():
                await update.message.reply_text("✅ Telegram бот запущен")
            else:
                await update.message.reply_text("❌ Не удалось запустить Telegram бот")
        
        elif command == 'stop_telegram':
            if runtime_manager.stop_telegram_bot():
                await update.message.reply_text("✅ Telegram бот остановлен")
            else:
                await update.message.reply_text("❌ Не удалось остановить Telegram бот")
        
        elif command == 'start_worker':
            if runtime_manager.start_worker_pool():
                await update.message.reply_text("✅ Worker Pool запущен")
            else:
                await update.message.reply_text("❌ Не удалось запустить Worker Pool")
        
        elif command == 'stop_worker':
            if runtime_manager.stop_worker_pool():
                await update.message.reply_text("✅ Worker Pool остановлен")
            else:
                await update.message.reply_text("❌ Не удалось остановить Worker Pool")
        
        elif command == 'start_all':
            if runtime_manager.start_all():
                await update.message.reply_text("✅ Все компоненты запущены")
            else:
                await update.message.reply_text("❌ Не удалось запустить все компоненты")
        
        elif command == 'stop_all':
            if runtime_manager.stop_all():
                await update.message.reply_text("✅ Все компоненты остановлены")
            else:
                await update.message.reply_text("❌ Не удалось остановить все компоненты")
        
        elif command == 'status':
            status = runtime_manager.get_status()
            status_text = "📊 Статус системы:\n\n"
            
            status_emoji = {
                'running': '🟢',
                'stopped': '🔴',
                'error': '⚠️',
                'starting': '⚪',
                'stopping': '⚪'
            }
            
            component_names = {
                'telegram_bot': 'Telegram Bot',
                'worker_pool': 'Worker Pool',
                'llm_server': 'LLM Server',
                'doctor_observer': 'Doctor Observer',
                'audit_vector': 'Audit Vector'
            }
            
            for comp_key, comp_status in status.items():
                comp_name = component_names.get(comp_key, comp_key)
                status_emo = status_emoji.get(comp_status['status'], '❓')
                pid = comp_status.get('pid', 'N/A')
                uptime = comp_status.get('uptime', 0)
                
                if uptime > 0:
                    hours = int(uptime // 3600)
                    minutes = int((uptime % 3600) // 60)
                    uptime_str = f"{hours}h {minutes}m"
                else:
                    uptime_str = "0m"
                
                status_text += f"{status_emo} {comp_name}: {comp_status['status']} (PID: {pid}, Uptime: {uptime_str})\n"
            
            await update.message.reply_text(status_text)
        
        elif command == 'restart':
            await update.message.reply_text("🔄 Перезагрузка не реализована. Используйте отдельные команды запуска/остановки.")
        
        # Log the command
        from app.core.audit_logger import get_audit_logger
        audit_logger = get_audit_logger()
        audit_logger.log_change(
            actor=str(user_id),
            action="system_command",
            entity_type="system_control",
            entity_id=command,
            new_value={"command": command, "text": text},
            origin="manual"
        )
        
    except Exception as e:
        logger.error(f"Error executing natural command: {e}")
        await update.message.reply_text(f"❌ Ошибка выполнения команды: {e}")
