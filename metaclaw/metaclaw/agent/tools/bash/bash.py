"""
Bash tool - Execute bash commands
"""

import os
import re
import sys
import subprocess
import tempfile
import unicodedata
from typing import Dict, Any

from agent.tools.base_tool import BaseTool, ToolResult
from agent.tools.utils.truncate import truncate_tail, format_size, DEFAULT_MAX_LINES, DEFAULT_MAX_BYTES
from common.brand import DEFAULT_ENV_DIR, DEFAULT_ENV_FILE
from common.log import logger
from common.utils import expand_path


class Bash(BaseTool):
    """Tool for executing bash commands"""

    _IS_WIN = sys.platform == "win32"

    name: str = "bash"
    description: str = f"""Execute a bash command in the current working directory. Returns stdout and stderr. Output is truncated to last {DEFAULT_MAX_LINES} lines or {DEFAULT_MAX_BYTES // 1024}KB (whichever is hit first). If truncated, full output is saved to a temp file.
{'''
PLATFORM: Windows (cmd.exe). Do NOT use Unix-only commands like grep, head, tail, sed, awk.
''' if _IS_WIN else ''}
ENVIRONMENT: All API keys from env_config are auto-injected. Use $VAR_NAME directly.

SAFETY:
- Freely create/modify/delete files within the workspace
- For destructive and out-of-workspace commands, explain and confirm first"""

    params: dict = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Bash command to execute"
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds (optional, default: 30)"
            }
        },
        "required": ["command"]
    }

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.cwd = self.config.get("cwd", os.getcwd())
        # Ensure working directory exists
        if not os.path.exists(self.cwd):
            os.makedirs(self.cwd, exist_ok=True)
        self.default_timeout = self.config.get("timeout", 30)
        # Enable safety mode by default (can be disabled in config)
        self.safety_mode = self.config.get("safety_mode", True)

    # Dangerous shell metacharacters that could enable command injection
    _DANGEROUS_CHARS = re.compile(r'[;&|`$(){}[\]\\]')
    
    def execute(self, args: Dict[str, Any]) -> ToolResult:
        """
        Execute a bash command
        
        :param args: Dictionary containing the command and optional timeout
        :return: Command output or error
        """
        command = args.get("command", "").strip()
        timeout = args.get("timeout", self.default_timeout)

        if not command:
            return ToolResult.fail("Error: command parameter is required")

        # Security check: Prevent accessing sensitive config files
        if DEFAULT_ENV_FILE in command or DEFAULT_ENV_DIR in command:
            return ToolResult.fail(
                "Error: Access denied. API keys and credentials must be accessed through the env_config tool only."
            )

        # Security check: Detect command injection attempts
        injection_warning = self._detect_command_injection(command)
        if injection_warning:
            logger.warning(f"[Bash] Blocked command injection attempt: {command[:200]}")
            return ToolResult.fail(
                f"Security Error: {injection_warning}\n\n"
                f"The command contains potentially dangerous patterns. "
                f"If you need to use shell features (pipes, redirects), ensure they are safe and necessary."
            )

        # Optional safety check - only warn about extremely dangerous commands
        if self.safety_mode:
            warning = self._get_safety_warning(command)
            if warning:
                return ToolResult.fail(
                    f"Safety Warning: {warning}\n\nIf you believe this command is safe and necessary, please ask the user for confirmation first, explaining what the command does and why it's needed.")

        try:
            # Prepare environment with .env file variables
            env = os.environ.copy()
            
            # Load environment variables from the managed .env file if it exists
            env_file = expand_path(DEFAULT_ENV_FILE)
            dotenv_vars = {}
            if os.path.exists(env_file):
                try:
                    from dotenv import dotenv_values
                    dotenv_vars = dotenv_values(env_file)
                    env.update(dotenv_vars)
                    logger.debug(f"[Bash] Loaded {len(dotenv_vars)} variables from {env_file}")
                except ImportError:
                    logger.debug("[Bash] python-dotenv not installed, skipping .env loading")
                except Exception as e:
                    logger.debug(f"[Bash] Failed to load .env: {e}")

            # getuid() only exists on Unix-like systems
            if hasattr(os, 'getuid'):
                logger.debug(f"[Bash] Process UID: {os.getuid()}")
            else:
                logger.debug(f"[Bash] Process User: {os.environ.get('USERNAME', os.environ.get('USER', 'unknown'))}")
            
            # On Windows, convert $VAR references to %VAR% for cmd.exe
            if self._IS_WIN:
                env["PYTHONIOENCODING"] = "utf-8"
                command = self._convert_env_vars_for_windows(command, dotenv_vars)
                if command and not command.strip().lower().startswith("chcp"):
                    command = f"chcp 65001 >nul 2>&1 && {command}"

            result = subprocess.run(
                command,
                shell=True,  # nosec B602: Intentional shell=True — bash tool requires shell for pipe/redirect support
                cwd=self.cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                env=env,
            )
            
            logger.debug(f"[Bash] Exit code: {result.returncode}")
            logger.debug(f"[Bash] Stdout length: {len(result.stdout)}")
            logger.debug(f"[Bash] Stderr length: {len(result.stderr)}")
            
            # Workaround for exit code 126 with no output
            if result.returncode == 126 and not result.stdout and not result.stderr:
                logger.warning(f"[Bash] Exit 126 with no output - trying alternative execution method")
                # Try using argument list instead of shell=True
                import shlex
                try:
                    parts = shlex.split(command)
                    if len(parts) > 0:
                        logger.info(f"[Bash] Retrying with argument list: {parts[:3]}...")
                        retry_result = subprocess.run(
                            parts,
                            cwd=self.cwd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                            encoding="utf-8",
                            errors="replace",
                            timeout=timeout,
                            env=env
                        )
                        logger.debug(f"[Bash] Retry exit code: {retry_result.returncode}, stdout: {len(retry_result.stdout)}, stderr: {len(retry_result.stderr)}")
                        
                        # If retry succeeded, use retry result
                        if retry_result.returncode == 0 or retry_result.stdout or retry_result.stderr:
                            result = retry_result
                        else:
                            # Both attempts failed - check if this is openai-image-vision skill
                            if 'openai-image-vision' in command or 'vision.sh' in command:
                                # Create a mock result with helpful error message
                                from types import SimpleNamespace
                                result = SimpleNamespace(
                                    returncode=1,
                                    stdout='{"error": "图片无法解析", "reason": "该图片格式可能不受支持，或图片文件存在问题", "suggestion": "请尝试其他图片"}',
                                    stderr=''
                                )
                                logger.info(f"[Bash] Converted exit 126 to user-friendly image error message for vision skill")
                except Exception as retry_err:
                    logger.warning(f"[Bash] Retry failed: {retry_err}")

            # When command succeeds with stdout, keep output clean (stderr goes to server log only).
            # When command fails or stdout is empty, include stderr so the agent can diagnose.
            if result.returncode == 0 and result.stdout.strip():
                output = result.stdout
                if result.stderr:
                    logger.info(f"[Bash] stderr (not forwarded): {result.stderr[:500]}")
            else:
                output = result.stdout
                if result.stderr:
                    output += "\n" + result.stderr

            # Check if we need to save full output to temp file
            temp_file_path = None
            total_bytes = len(output.encode('utf-8'))

            if total_bytes > DEFAULT_MAX_BYTES:
                # Save full output to temp file
                with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log', prefix='bash-') as f:
                    f.write(output)
                    temp_file_path = f.name

            # Apply tail truncation
            truncation = truncate_tail(output)
            output_text = truncation.content or "(no output)"

            # Build result
            details = {}

            if truncation.truncated:
                details["truncation"] = truncation.to_dict()
                if temp_file_path:
                    details["full_output_path"] = temp_file_path

                # Build notice
                start_line = truncation.total_lines - truncation.output_lines + 1
                end_line = truncation.total_lines

                if truncation.last_line_partial:
                    # Edge case: last line alone > 30KB
                    last_line = output.split('\n')[-1] if output else ""
                    last_line_size = format_size(len(last_line.encode('utf-8')))
                    output_text += f"\n\n[Showing last {format_size(truncation.output_bytes)} of line {end_line} (line is {last_line_size}). Full output: {temp_file_path}]"
                elif truncation.truncated_by == "lines":
                    output_text += f"\n\n[Showing lines {start_line}-{end_line} of {truncation.total_lines}. Full output: {temp_file_path}]"
                else:
                    output_text += f"\n\n[Showing lines {start_line}-{end_line} of {truncation.total_lines} ({format_size(DEFAULT_MAX_BYTES)} limit). Full output: {temp_file_path}]"

            # Check exit code
            if result.returncode != 0:
                output_text += f"\n\nCommand exited with code {result.returncode}"
                return ToolResult.fail({
                    "output": output_text,
                    "exit_code": result.returncode,
                    "details": details if details else None
                })

            return ToolResult.success({
                "output": output_text,
                "exit_code": result.returncode,
                "details": details if details else None
            })

        except subprocess.TimeoutExpired:
            return ToolResult.fail(f"Error: Command timed out after {timeout} seconds")
        except Exception as e:
            return ToolResult.fail(f"Error executing command: {str(e)}")

    def _get_safety_warning(self, command: str) -> str:
        """
        Get safety warning for potentially dangerous commands
        Only warns about extremely dangerous system-level operations
        
        :param command: Command to check
        :return: Warning message if dangerous, empty string if safe
        """
        cmd_lower = command.lower().strip()

        # Only block extremely dangerous system operations
        dangerous_patterns = [
            # System shutdown/reboot
            ("shutdown", "This command will shut down the system"),
            ("reboot", "This command will reboot the system"),
            ("halt", "This command will halt the system"),
            ("poweroff", "This command will power off the system"),

            # Critical system modifications
            ("rm -rf /", "This command will delete the entire filesystem"),
            ("rm -rf /*", "This command will delete the entire filesystem"),
            ("dd if=/dev/zero", "This command can destroy disk data"),
            ("mkfs", "This command will format a filesystem, destroying all data"),
            ("fdisk", "This command modifies disk partitions"),

            # User/system management (only if targeting system users)
            ("userdel root", "This command will delete the root user"),
            ("passwd root", "This command will change the root password"),
        ]

        for pattern, warning in dangerous_patterns:
            if pattern in cmd_lower:
                return warning

        # Check for recursive deletion outside workspace
        if "rm" in cmd_lower and "-rf" in cmd_lower:
            # Allow deletion within current workspace
            if not any(path in cmd_lower for path in ["./", self.cwd.lower()]):
                # Check if targeting system directories
                system_dirs = ["/bin", "/usr", "/etc", "/var", "/home", "/root", "/sys", "/proc"]
                if any(sysdir in cmd_lower for sysdir in system_dirs):
                    return "This command will recursively delete system directories"

        return ""  # No warning needed

    def _detect_command_injection(self, command: str) -> str:
        """
        Detect potential command injection patterns.
        
        :param command: Command to check
        :return: Warning message if injection detected, empty string if safe
        """
        # Normalize Unicode to catch homoglyph attacks (e.g., fullwidth chars, cyrillic lookalikes)
        normalized = unicodedata.normalize('NFKC', command)
        
        # Allow safe shell features: pipes (|), redirects (>, <), background (&)
        # Block dangerous patterns that enable arbitrary code execution
        
        dangerous_patterns = [
            # Command substitution - $(cmd) or `cmd`
            (r'`[^`]+`', "Command substitution with backticks detected"),
            (r'\$\([^)]+\)', "Command substitution with $() detected"),
            
            # Chaining commands with semicolons (but allow in strings/args)
            # Only flag if followed by another command-like pattern
            (r';\s*(rm|cat|echo|python|bash|sh|curl|wget|nc|netcat)', "Command chaining with semicolon detected"),
            
            # Logic operators for command chaining
            (r'&&\s*(rm|cat|echo|python|bash|sh|curl|wget)', "Command chaining with && detected"),
            (r'\|\|\s*(rm|cat|echo|python|bash|sh|curl|wget)', "Command chaining with || detected"),
            
            # Shell evasion patterns
            (r'\b(bash|sh|zsh)\s+-[ci]', "Shell invocation with inline commands detected"),
            (r'\beval\s', "eval() detected"),
            (r'\bexec\s', "exec() detected"),
            
            # Inline code execution via interpreters (python -c, perl -e, ruby -e, node -e)
            (r'\b(python3?|perl|ruby|php|node)\s+-[ce]\s', "Inline code execution via interpreter detected"),
            
            # Dynamic imports and code compilation
            (r'\b__import__\s*\(', "Dynamic import detected"),
            (r'\bcompile\s*\(', "Dynamic code compilation detected"),
            (r'\bexec\s*\(', "Dynamic exec() call detected"),
            (r'\bgetattr\s*\(\s*__import__', "Dynamic attribute access on import detected"),
            
            # Obfuscated code execution patterns
            (r'codecs?\.decode\s*\(', "Codec-based decoding detected"),
            (r'base64\s+.*-d.*\||.*decode.*base64', "Base64 decode pipeline detected"),
            
            # Network exfiltration
            (r'\b(nc|netcat)\s+-[el]', "Netcat listener detected"),
            (r'\bcurl\s+.*\|', "curl piped to shell detected"),
            (r'\bwget\s+.*\|', "wget piped to shell detected"),
            
            # Environment variable manipulation for privilege escalation
            (r'PATH\s*=\s*', "PATH manipulation detected"),
            (r'SUDO_\w+\s*=\s*', "Sudo environment manipulation detected"),
            
            # Base64 encoded commands
            (r'base64\s+.*\|.*\b(bash|sh|zsh|python|ruby|perl)', "Base64 decoded command execution detected"),
            
            # History manipulation
            (r'history\s+-[cd]', "History manipulation detected"),
        ]
        
        import re as _re
        for pattern, warning in dangerous_patterns:
            if _re.search(pattern, normalized, _re.IGNORECASE):
                return warning
        
        # Check for unbalanced quotes (potential injection via string termination)
        single_quotes = normalized.count("'") % 2
        double_quotes = normalized.count('"') % 2
        if single_quotes == 1 or double_quotes == 1:
            # Only flag if there's also a suspicious pattern
            if _re.search(r'[;|&`$]', normalized):
                return "Unbalanced quotes with shell metacharacters detected"
        
        return ""  # No injection detected

    @staticmethod
    def _convert_env_vars_for_windows(command: str, dotenv_vars: dict) -> str:
        """
        Convert bash-style $VAR / ${VAR} references to cmd.exe %VAR% syntax.
        Only converts variables loaded from .env (user-configured API keys etc.)
        to avoid breaking $PATH, jq expressions, regex, etc.
        """
        if not dotenv_vars:
            return command

        def replace_match(m):
            var_name = m.group(1) or m.group(2)
            if var_name in dotenv_vars:
                return f"%{var_name}%"
            return m.group(0)

        return re.sub(r'\$\{(\w+)\}|\$(\w+)', replace_match, command)
