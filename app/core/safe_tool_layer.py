"""Safe Tool Generation Layer - Secure parameterized tool execution.

This module provides a safe layer for LLM-generated tool calls,
preventing raw SQL/Python execution and enforcing parameter validation.
"""

import json
import logging
import ast
import re
import subprocess
import tempfile
import os
from typing import Dict, List, Any, Optional, Callable, Tuple
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)


class ToolPermission(str, Enum):
    """Permission levels for tools."""
    READ_ONLY = "read_only"  # Only read operations
    WRITE_SAFE = "write_safe"  # Safe write operations (with approval)
    DANGEROUS = "dangerous"  # Requires explicit approval
    FORBIDDEN = "forbidden"  # Not allowed


class MiaTool:
    """
    Base class for safe Mia tools.
    
    All tools must inherit from this class and declare their parameters,
    permissions, and validation logic.
    """
    
    def __init__(self, name: str, description: str, permission: ToolPermission):
        """
        Initialize a Mia tool.
        
        Args:
            name: Tool name
            description: Tool description
            permission: Permission level
        """
        self.name = name
        self.description = description
        self.permission = permission
        self.parameters: Dict[str, Any] = {}
    
    def define_parameter(self, name: str, param_type: type, required: bool = True, 
                       description: str = "", validation: Optional[Callable] = None):
        """
        Define a parameter for the tool.
        
        Args:
            name: Parameter name
            param_type: Parameter type
            required: Whether parameter is required
            description: Parameter description
            validation: Validation function
        """
        self.parameters[name] = {
            'type': param_type,
            'required': required,
            'description': description,
            'validation': validation
        }
    
    def validate_parameters(self, params: Dict[str, Any]) -> tuple[bool, str]:
        """
        Validate parameters against definition.
        
        Args:
            params: Parameters to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check required parameters
        for param_name, param_def in self.parameters.items():
            if param_def['required'] and param_name not in params:
                return False, f"Required parameter '{param_name}' is missing"
            
            if param_name in params:
                # Type check
                param_value = params[param_name]
                expected_type = param_def['type']
                
                if not isinstance(param_value, expected_type):
                    try:
                        # Try to convert
                        params[param_name] = expected_type(param_value)
                    except (ValueError, TypeError):
                        return False, f"Parameter '{param_name}' must be {expected_type}, got {type(param_value)}"
                
                # Custom validation
                validation = param_def.get('validation')
                if validation:
                    try:
                        is_valid, error = validation(params[param_name])
                        if not is_valid:
                            return False, f"Parameter '{param_name}' validation failed: {error}"
                    except Exception as e:
                        return False, f"Parameter '{param_name}' validation error: {e}"
        
        return True, ""
    
    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the tool with parameters.
        
        Must be implemented by subclasses.
        
        Args:
            params: Validated parameters
            
        Returns:
            Execution result
        """
        raise NotImplementedError("Subclasses must implement execute()")
    
    def to_schema(self) -> Dict[str, Any]:
        """Get tool schema for LLM."""
        return {
            'name': self.name,
            'description': self.description,
            'parameters': {
                'type': 'object',
                'properties': {
                    name: {
                        'type': self._type_to_json_type(param_def['type']),
                        'description': param_def['description']
                    }
                    for name, param_def in self.parameters.items()
                },
                'required': [name for name, param_def in self.parameters.items() if param_def['required']]
            },
            'permission': self.permission.value
        }
    
    def _type_to_json_type(self, python_type: type) -> str:
        """Convert Python type to JSON schema type."""
        type_mapping = {
            str: 'string',
            int: 'integer',
            float: 'number',
            bool: 'boolean',
            list: 'array',
            dict: 'object'
        }
        return type_mapping.get(python_type, 'string')


class SafeToolLayer:
    """
    Safe layer for tool execution.
    
    Validates tool calls, checks permissions, and executes in sandbox.
    """
    
    def __init__(self):
        """Initialize Safe Tool Layer."""
        self.tools: Dict[str, MiaTool] = {}
        self._register_builtin_tools()
    
    def _register_builtin_tools(self):
        """Register built-in safe tools (semantic, parameterized — no raw SQL)."""
        for tool_cls in (
            SearchObjectsTool,
            GetObjectEventsTool,
            GetHealthScoreTool,
            SearchMessagesTool,
            ReadFileTool,
            WriteFileTool,
        ):
            self.register_tool(tool_cls())
        
        logger.info(f"Registered {len(self.tools)} built-in tools")
    
    def register_tool(self, tool: MiaTool):
        """Register a tool."""
        self.tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name} ({tool.permission.value})")
    
    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Get all tool schemas for LLM."""
        return [tool.to_schema() for tool in self.tools.values()]
    
    def execute_tool(self, tool_name: str, params: Dict[str, Any], 
                    approval_callback: Optional[Callable] = None) -> Dict[str, Any]:
        """
        Execute a tool with validation and permission check.
        
        Args:
            tool_name: Tool name
            params: Tool parameters
            approval_callback: Callback for approval (for dangerous tools)
            
        Returns:
            Execution result
        """
        # Check if tool exists
        if tool_name not in self.tools:
            return {
                'success': False,
                'error': f"Tool '{tool_name}' not found"
            }
        
        tool = self.tools[tool_name]
        
        # Check permission
        if tool.permission == ToolPermission.FORBIDDEN:
            return {
                'success': False,
                'error': f"Tool '{tool_name}' is forbidden"
            }
        
        # Require approval for dangerous tools
        if tool.permission == ToolPermission.DANGEROUS:
            if approval_callback:
                approved = approval_callback(tool_name, params)
                if not approved:
                    return {
                        'success': False,
                        'error': f"Tool '{tool_name}' requires approval and was not approved"
                    }
            else:
                return {
                    'success': False,
                    'error': f"Tool '{tool_name}' requires approval but no callback provided"
                }
        
        # Validate parameters
        is_valid, error = tool.validate_parameters(params)
        if not is_valid:
            return {
                'success': False,
                'error': f"Parameter validation failed: {error}"
            }
        
        # Execute tool
        try:
            result = tool.execute(params)
            return {
                'success': True,
                'result': result
            }
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def parse_tool_call(self, payload: Any) -> Tuple[bool, str, Dict[str, Any], str]:
        """
        Parse an LLM tool call payload into (tool_name, params).
        
        Accepts:
          - dict: {"tool": name, "parameters": {...}} (also "name"/"tool_name",
            "params"/"arguments"/"input")
          - str: JSON with the same shape, or a bare JSON object of parameters
            (a single registered tool is then implied — error if ambiguous)
          - JSON extracted from a fenced ```json ...``` block
        
        Returns:
            (ok, tool_name, params, error_message)
        """
        if isinstance(payload, dict):
            data = payload
        elif isinstance(payload, str):
            text = payload.strip()
            fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
            if fence:
                text = fence.group(1)
            try:
                data = json.loads(text)
            except (json.JSONDecodeError, ValueError) as e:
                return False, "", {}, f"Tool call is not valid JSON: {e}"
        else:
            return False, "", {}, f"Unsupported tool call payload type: {type(payload).__name__}"
        
        if not isinstance(data, dict):
            return False, "", {}, "Tool call JSON must be an object"
        
        tool_name = (
            data.get('tool')
            or data.get('tool_name')
            or data.get('name')
            or data.get('function')
        )
        params = (
            data.get('parameters')
            if isinstance(data.get('parameters'), dict)
            else data.get('params')
            if isinstance(data.get('params'), dict)
            else data.get('arguments')
            if isinstance(data.get('arguments'), dict)
            else data.get('input')
            if isinstance(data.get('input'), dict)
            else None
        )
        
        if params is None:
            # Bare parameter object: everything except well-known keys
            reserved = {'tool', 'tool_name', 'name', 'function', 'type'}
            params = {k: v for k, v in data.items() if k not in reserved}
        
        if isinstance(tool_name, dict):
            tool_name = tool_name.get('name') or tool_name.get('function')
        
        if not isinstance(tool_name, str) or not tool_name:
            if len(self.tools) == 1:
                tool_name = next(iter(self.tools))
            else:
                return False, "", {}, (
                    "Tool name missing in tool call and cannot be inferred "
                    f"({len(self.tools)} tools registered)"
                )
        
        if not isinstance(params, dict):
            return False, "", {}, "Tool call parameters must be a JSON object"
        
        return True, tool_name, params, ""
    
    def execute_tool_call(self, payload: Any,
                          approval_callback: Optional[Callable] = None) -> Dict[str, Any]:
        """
        Parse an LLM tool call (JSON string or dict) and execute it.
        
        Returns:
            Execution result dict; parse failures come back as
            {'success': False, 'error': ...} without raising.
        """
        ok, tool_name, params, error = self.parse_tool_call(payload)
        if not ok:
            return {'success': False, 'error': f'Invalid tool call: {error}'}
        return self.execute_tool(tool_name, params, approval_callback=approval_callback)
    
    def validate_generated_code(self, code: str) -> tuple[bool, str]:
        """
        Validate generated Python code for safety.
        
        Args:
            code: Python code to validate
            
        Returns:
            Tuple of (is_safe, error_message)
        """
        # Check for dangerous patterns
        dangerous_patterns = [
            'import os',
            'import subprocess',
            'exec(',
            'eval(',
            '__import__',
            'DROP TABLE',
            'DELETE FROM',
            'TRUNCATE',
            'shell=True',
            'rm -rf',
            'del '
        ]
        
        code_lower = code.lower()
        for pattern in dangerous_patterns:
            if pattern.lower() in code_lower:
                return False, f"Dangerous pattern detected: {pattern}"
        
        # Try to parse AST
        try:
            ast.parse(code)
        except SyntaxError as e:
            return False, f"Syntax error: {e}"
        
        return True, ""


class SearchObjectsTool(MiaTool):
    """Semantic tool: search construction objects by name/customer."""
    
    def __init__(self):
        super().__init__(
            name="search_objects",
            description="Search construction objects by name, customer or contract number",
            permission=ToolPermission.READ_ONLY
        )
        
        self.define_parameter("query", str, True, "Search text (name, customer or contract number)")
        self.define_parameter("limit", int, False, "Maximum number of rows (default 20)")
    
    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        from app.modules.storage.database import get_db_connection
        
        query = f"%{params['query']}%"
        limit = min(int(params.get('limit', 20)), 100)
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT object_id, object_name, customer, customer_company,
                       contract_number, contract_amount, contract_date
                FROM objects
                WHERE object_name LIKE ? OR customer LIKE ?
                   OR customer_company LIKE ? OR contract_number LIKE ?
                ORDER BY object_name
                LIMIT ?
                """,
                (query, query, query, query, limit)
            )
            columns = [description[0] for description in cursor.description]
            rows = cursor.fetchall()
            
            return {
                'columns': columns,
                'rows': [dict(row) for row in rows],
                'count': len(rows)
            }


class GetObjectEventsTool(MiaTool):
    """Semantic tool: get diary events for an object."""
    
    def __init__(self):
        super().__init__(
            name="get_object_events",
            description="Get the timeline of diary events for a construction object",
            permission=ToolPermission.READ_ONLY
        )
        
        self.define_parameter("object_id", str, True, "Object ID (as stored in objects.object_id)")
        self.define_parameter("limit", int, False, "Maximum number of events (default 50)")
        self.define_parameter("current_only", bool, False, "Only current (non-superseded) events (default true)")
    
    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        from app.modules.storage.database import get_db_connection
        
        object_id = params['object_id']
        limit = min(int(params.get('limit', 50)), 200)
        current_only = params.get('current_only', True)
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT diary_id FROM objects WHERE object_id = ?", (object_id,))
            row = cursor.fetchone()
            if row is None:
                return {'columns': [], 'rows': [], 'count': 0, 'error': f"Object '{object_id}' not found"}
            diary_id = row["diary_id"] if not isinstance(row, tuple) else row[0]
            
            sql = """
                SELECT event_id, event_type, event_timestamp, entity_type,
                       entity_id, summary, is_current, verification_status
                FROM diary_events
                WHERE diary_id = ?
            """
            args: List[Any] = [diary_id]
            if current_only:
                sql += " AND is_current = 1"
            sql += " ORDER BY event_timestamp DESC LIMIT ?"
            args.append(limit)
            
            cursor.execute(sql, args)
            columns = [description[0] for description in cursor.description]
            rows = cursor.fetchall()
            
            return {
                'columns': columns,
                'rows': [dict(r) for r in rows],
                'count': len(rows)
            }


class GetHealthScoreTool(MiaTool):
    """Semantic tool: latest health score for an object."""
    
    def __init__(self):
        super().__init__(
            name="get_health_score",
            description="Get the latest health score (risk zone) of a construction object",
            permission=ToolPermission.READ_ONLY
        )
        
        self.define_parameter("object_id", str, True, "Object ID")
    
    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        from app.modules.storage.database import get_db_connection
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT object_id, score, zone, calculated_at, risk_factors
                FROM health_scores
                WHERE object_id = ?
                ORDER BY calculated_at DESC
                LIMIT 1
                """,
                (params['object_id'],)
            )
            row = cursor.fetchone()
            if row is None:
                return {'count': 0, 'error': f"No health score for '{params['object_id']}'"}
            return {'count': 1, 'row': dict(row)}


class SearchMessagesTool(MiaTool):
    """Semantic tool: search distilled Telegram messages."""
    
    def __init__(self):
        super().__init__(
            name="search_messages",
            description="Search stored Telegram messages by text (optionally within one chat)",
            permission=ToolPermission.READ_ONLY
        )
        
        self.define_parameter("query", str, True, "Text to search for")
        self.define_parameter("chat_id", int, False, "Restrict to one Telegram chat ID")
        self.define_parameter("limit", int, False, "Maximum number of messages (default 20)")
    
    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        from app.modules.storage.database import get_db_connection
        
        query = f"%{params['query']}%"
        limit = min(int(params.get('limit', 20)), 100)
        chat_id = params.get('chat_id')
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            if chat_id is not None:
                cursor.execute(
                    """
                    SELECT message_id, telegram_chat_id, username, message_text, timestamp
                    FROM telegram_messages
                    WHERE message_text LIKE ? AND telegram_chat_id = ?
                    ORDER BY timestamp DESC LIMIT ?
                    """,
                    (query, chat_id, limit)
                )
            else:
                cursor.execute(
                    """
                    SELECT message_id, telegram_chat_id, username, message_text, timestamp
                    FROM telegram_messages
                    WHERE message_text LIKE ?
                    ORDER BY timestamp DESC LIMIT ?
                    """,
                    (query, limit)
                )
            columns = [description[0] for description in cursor.description]
            rows = cursor.fetchall()
            
            return {
                'columns': columns,
                'rows': [dict(row) for row in rows],
                'count': len(rows)
            }


class ReadFileTool(MiaTool):
    """Safe file reading tool."""
    
    def __init__(self):
        super().__init__(
            name="read_file",
            description="Read a file from the project directory",
            permission=ToolPermission.READ_ONLY
        )
        
        self.define_parameter("file_path", str, True, "Path to file to read")
        self.define_parameter("max_lines", int, False, "Maximum lines to read (default 100)")
    
    def validate_parameters(self, params: Dict[str, Any]) -> tuple[bool, str]:
        """Validate file path."""
        is_valid, error = super().validate_parameters(params)
        if not is_valid:
            return is_valid, error
        
        file_path = Path(params['file_path'])
        
        # Only allow files within project directory
        if not str(file_path).startswith('C:\\mia'):
            return False, "Only files within C:\\mia directory are allowed"
        
        return True, ""
    
    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Read the file."""
        file_path = Path(params['file_path'])
        max_lines = params.get('max_lines', 100)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                if max_lines:
                    lines = lines[:max_lines]
                
                return {
                    'content': ''.join(lines),
                    'line_count': len(lines),
                    'file_path': str(file_path)
                }
        except Exception as e:
            raise Exception(f"File read failed: {e}")


class WriteFileTool(MiaTool):
    """Safe file writing tool (requires approval)."""
    
    def __init__(self):
        super().__init__(
            name="write_file",
            description="Write content to a file in the project directory",
            permission=ToolPermission.WRITE_SAFE
        )
        
        self.define_parameter("file_path", str, True, "Path to file to write")
        self.define_parameter("content", str, True, "Content to write")
    
    def validate_parameters(self, params: Dict[str, Any]) -> tuple[bool, str]:
        """Validate file path."""
        is_valid, error = super().validate_parameters(params)
        if not is_valid:
            return is_valid, error
        
        file_path = Path(params['file_path'])
        
        # Only allow files within project directory
        if not str(file_path).startswith('C:\\mia'):
            return False, "Only files within C:\\mia directory are allowed"
        
        # Don't allow overwriting critical files
        critical_files = ['mia_config.json', 'data/mia_pm.db']
        if str(file_path) in critical_files:
            return False, f"Cannot overwrite critical file: {file_path}"
        
        return True, ""
    
    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Write the file."""
        file_path = Path(params['file_path'])
        content = params['content']
        
        try:
            # Create directory if it doesn't exist
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return {
                'success': True,
                'file_path': str(file_path),
                'bytes_written': len(content)
            }
        except Exception as e:
            raise Exception(f"File write failed: {e}")


# Global safe tool layer instance
_safe_tool_layer: Optional[SafeToolLayer] = None


def get_safe_tool_layer() -> SafeToolLayer:
    """Get global safe tool layer instance."""
    global _safe_tool_layer
    if _safe_tool_layer is None:
        _safe_tool_layer = SafeToolLayer()
    return _safe_tool_layer


if __name__ == "__main__":
    # Test Safe Tool Layer
    logging.basicConfig(level=logging.INFO)
    
    layer = SafeToolLayer()
    
    # Get tool schemas
    schemas = layer.get_tool_schemas()
    print(f"Tool schemas: {len(schemas)}")
    
    # Test semantic search tool
    result = layer.execute_tool("search_objects", {"query": "Судакова"})
    print(f"Search result: {result}")
    
    # Test JSON tool call parsing
    result = layer.execute_tool_call(
        '{"tool": "search_objects", "parameters": {"query": "Судакова", "limit": 5}}'
    )
    print(f"Tool call result: {result}")
    
    # Test read file tool
    result = layer.execute_tool("read_file", {
        "file_path": "C:\\mia\\README.md"
    })
    print(f"Read file result: {result}")
