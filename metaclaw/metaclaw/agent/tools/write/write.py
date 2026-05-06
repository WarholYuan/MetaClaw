"""
Write tool - Write file content
Creates or overwrites files, automatically creates parent directories
"""

import os
from typing import Dict, Any
from pathlib import Path

from agent.tools.base_tool import BaseTool, ToolResult
from common.utils import expand_path


class Write(BaseTool):
    """Tool for writing file content"""
    
    name: str = "write"
    description: str = "Write content to a file. Creates the file if it doesn't exist, overwrites if it does. Automatically creates parent directories. By default, bare generated filenames like report.md are saved under workspace tmp/. Use an explicit directory for memory, knowledge, skills, rules, or user-requested durable files. IMPORTANT: Single write should not exceed 10KB. For large files, create a skeleton first, then use edit to add content in chunks."
    
    params: dict = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file to write (relative or absolute). Bare filenames default to workspace tmp/ unless they are reserved workspace files such as AGENT.md, USER.md, RULE.md, or MEMORY.md."
            },
            "content": {
                "type": "string",
                "description": "Content to write to the file"
            }
        },
        "required": ["path", "content"]
    }
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.cwd = self.config.get("cwd", os.getcwd())
        self.memory_manager = self.config.get("memory_manager", None)
    
    def execute(self, args: Dict[str, Any]) -> ToolResult:
        """
        Execute file write operation
        
        :param args: Contains file path and content
        :return: Operation result
        """
        original_path = args.get("path", "").strip()
        path = original_path
        content = args.get("content", "")
        
        if not path:
            return ToolResult.fail("Error: path parameter is required")
        
        # Resolve path
        try:
            absolute_path = self._resolve_path(path)
        except ValueError as e:
            return ToolResult.fail(f"Error: Invalid path - {e}")
        display_path = self._display_path(absolute_path)
        
        # Security check: Path traversal prevention
        allowed, reason = self._is_path_allowed(absolute_path)
        if not allowed:
            return ToolResult.fail(f"Error: {reason}")
        
        try:
            # Create parent directory (if needed)
            parent_dir = os.path.dirname(absolute_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
            
            # Write file
            with open(absolute_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Get bytes written
            bytes_written = len(content.encode('utf-8'))
            
            # Auto-sync to memory database if this is a memory file
            if self.memory_manager and 'memory/' in display_path:
                self.memory_manager.mark_dirty()
            
            result = {
                "message": f"Successfully wrote {bytes_written} bytes to {display_path}",
                "path": display_path,
                "bytes_written": bytes_written
            }
            
            return ToolResult.success(result)
            
        except PermissionError:
            return ToolResult.fail(f"Error: Permission denied writing to {display_path}")
        except Exception as e:
            return ToolResult.fail(f"Error writing file: {str(e)}")

    _ROOT_WORKSPACE_FILES = {
        "AGENT.md",
        "USER.md",
        "RULE.md",
        "MEMORY.md",
        "BOOTSTRAP.md",
        "AGENTS.md",
        "AGENTS.override.md",
    }
    
    def _resolve_path(self, path: str) -> str:
        """
        Resolve path to absolute path with security checks
        
        :param path: Relative or absolute path
        :return: Absolute path
        :raises ValueError: if path contains directory traversal attempts
        """
        original_path = path

        # Expand ~ to user home directory
        path = expand_path(path)
        
        # Security: Reject paths with null bytes
        if '\x00' in path:
            raise ValueError("Path contains null bytes")
        
        # Security: Normalize path to resolve .. and .
        path = os.path.normpath(path)
        
        # Security: Check for directory traversal after normalization
        if path.startswith('..'):
            raise ValueError(f"Path traversal detected: {path}")
        
        if os.path.isabs(path):
            return path
        if self._should_default_to_tmp(original_path, path):
            path = os.path.join("tmp", path)
        return os.path.abspath(os.path.join(self.cwd, path))

    def _should_default_to_tmp(self, original_path: str, normalized_path: str) -> bool:
        """
        Treat a bare filename as a generated artifact and place it in tmp/.

        Explicit relative paths (e.g. ``memory/foo.md``, ``./README.md``) keep
        their requested location. Reserved workspace files also stay at root.
        """
        if os.path.isabs(normalized_path):
            return False
        if original_path.startswith((".", "~")):
            return False
        if os.sep in normalized_path or (os.altsep and os.altsep in normalized_path):
            return False
        if normalized_path in self._ROOT_WORKSPACE_FILES:
            return False
        return True

    def _display_path(self, absolute_path: str) -> str:
        try:
            rel = os.path.relpath(absolute_path, self.cwd)
            if not rel.startswith("..") and rel != os.curdir:
                return rel
        except ValueError:
            pass
        return absolute_path
    
    def _is_path_allowed(self, absolute_path: str) -> tuple[bool, str]:
        """
        Check if a path is within allowed directories.
        
        :param absolute_path: Absolute path to check
        :return: (is_allowed, reason)
        """
        normalized = os.path.normpath(os.path.abspath(absolute_path))
        allowed_bases = [self.cwd, os.path.expanduser('~')]
        
        for base in allowed_bases:
            base_normalized = os.path.normpath(os.path.abspath(base))
            if not base_normalized.endswith(os.sep):
                base_normalized += os.sep
            if normalized.startswith(base_normalized) or normalized == base_normalized.rstrip(os.sep):
                return True, ""
        
        return False, f"Access denied: path is outside allowed directories (workspace: {self.cwd}, home: ~)"
