"""
OpenCLI tool - Wrap the opencli CLI to give the agent browser automation
via the user's existing Chrome session and 90+ pre-built site adapters.

Prerequisites (on the user's machine):
  npm install -g @jackwener/opencli
  # Install the Browser Bridge extension from the Chrome Web Store
  # opencli doctor   ← verify setup

Two usage modes exposed through a single tool:
  mode="browser"  → opencli browser <subcmd> [args]
  mode="adapter"  → opencli <site> <command> [args]
"""

import json
import shlex
import shutil
import subprocess
from typing import Dict, Any, Optional

from agent.tools.base_tool import BaseTool, ToolResult
from common.log import logger


DEFAULT_TIMEOUT = 60  # seconds


class OpenCLITool(BaseTool):
    """
    Run opencli commands to automate websites via the user's Chrome session.

    Prefer this tool over the browser tool when:
    - The target site has a pre-built adapter (bilibili, xiaohongshu, github, etc.)
    - You need to reuse the user's existing login session without re-authenticating
    - You need structured JSON output from a known site

    Use mode="browser" for low-level page control (state/click/type/find/extract).
    Use mode="adapter" for high-level site-specific commands.

    Requirements: opencli must be installed (`npm install -g @jackwener/opencli`)
    and the Browser Bridge Chrome extension must be running.
    """

    name: str = "opencli"
    description: str = (
        "Control websites via the user's existing Chrome browser session using OpenCLI. "
        "Supports 90+ pre-built site adapters (bilibili, xiaohongshu, github, twitter, etc.) "
        "and low-level browser primitives. Reuses Chrome login state — no re-authentication needed.\n\n"
        "mode='browser': Low-level browser control.\n"
        "  Subcommands: state, find, click, type, select, keys, get, extract, "
        "screenshot, scroll, back, eval, network, tab, wait, open, verify, close\n"
        "  Examples:\n"
        "    command='state'                          → DOM snapshot with element refs\n"
        "    command='find --css \"button.submit\"'     → find elements by CSS\n"
        "    command='click [3]'                      → click element ref 3\n"
        "    command='type [5] hello world'           → type text into ref 5\n"
        "    command='open https://example.com'       → open URL in current tab\n"
        "    command='screenshot'                     → take screenshot\n"
        "    command='extract'                        → extract structured page data\n"
        "    command='network'                        → list recent network requests\n"
        "    command='eval document.title'            → run JS expression\n"
        "    command='tab list'                       → list open tabs\n\n"
        "mode='adapter': High-level site-specific commands.\n"
        "  Format: '<site> <command> [flags]'\n"
        "  Examples:\n"
        "    command='bilibili search --keyword python'\n"
        "    command='xiaohongshu notifications'\n"
        "    command='github issues list --repo owner/repo'\n"
        "    command='twitter timeline'\n\n"
        "Output is JSON. On error the response contains an 'error' key with code and message."
    )

    params: dict = {
        "type": "object",
        "properties": {
            "mode": {
                "type": "string",
                "description": "Operation mode: 'browser' for low-level primitives, 'adapter' for site-specific commands",
                "enum": ["browser", "adapter"]
            },
            "command": {
                "type": "string",
                "description": (
                    "The command string to pass to opencli after the mode prefix. "
                    "For mode='browser': subcommand and args, e.g. 'click [3]' or 'find --css input'. "
                    "For mode='adapter': site and command, e.g. 'bilibili search --keyword python'."
                )
            },
            "timeout": {
                "type": "integer",
                "description": f"Timeout in seconds (default: {DEFAULT_TIMEOUT})"
            }
        },
        "required": ["mode", "command"]
    }

    def __init__(self, config: dict = None):
        self.config = config or {}

    @staticmethod
    def is_available() -> bool:
        """Return True if the opencli binary is on PATH."""
        return shutil.which("opencli") is not None

    def execute(self, args: Dict[str, Any]) -> ToolResult:
        if not self.is_available():
            return ToolResult.fail(
                "opencli is not installed. "
                "Run: npm install -g @jackwener/opencli\n"
                "Then install the Browser Bridge Chrome extension and run: opencli doctor"
            )

        mode: str = args.get("mode", "").strip()
        command: str = args.get("command", "").strip()
        timeout: int = int(args.get("timeout", DEFAULT_TIMEOUT))

        if not mode:
            return ToolResult.fail("'mode' is required")
        if not command:
            return ToolResult.fail("'command' is required")

        if mode == "browser":
            argv = ["opencli", "browser"] + shlex.split(command)
        elif mode == "adapter":
            argv = ["opencli"] + shlex.split(command)
        else:
            return ToolResult.fail(f"Unknown mode '{mode}'. Use 'browser' or 'adapter'.")

        logger.info(f"[OpenCLI] Running: {' '.join(argv)}")

        try:
            proc = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return ToolResult.fail(f"opencli timed out after {timeout}s")
        except FileNotFoundError:
            return ToolResult.fail(
                "opencli binary not found. Run: npm install -g @jackwener/opencli"
            )
        except Exception as e:
            logger.error(f"[OpenCLI] Subprocess error: {e}")
            return ToolResult.fail(f"Failed to run opencli: {e}")

        stdout = proc.stdout.strip()
        stderr = proc.stderr.strip()

        if proc.returncode != 0:
            msg = stderr or stdout or f"opencli exited with code {proc.returncode}"
            logger.warning(f"[OpenCLI] Non-zero exit ({proc.returncode}): {msg}")
            # Still try to parse stdout as JSON — opencli may put error detail there
            parsed = _try_parse_json(stdout)
            if parsed is not None:
                return ToolResult.fail(json.dumps(parsed, ensure_ascii=False))
            return ToolResult.fail(msg)

        if not stdout:
            return ToolResult.success("(no output)")

        parsed = _try_parse_json(stdout)
        if parsed is not None:
            return ToolResult.success(json.dumps(parsed, ensure_ascii=False, indent=2))

        return ToolResult.success(stdout)


def _try_parse_json(text: str) -> Optional[Any]:
    """Return parsed JSON if text is valid JSON, else None."""
    if not text:
        return None
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
