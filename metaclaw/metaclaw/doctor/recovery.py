"""Recovery actions for MetaClaw.

Restart, kill-and-restart, and other recovery operations.
"""

import os
import subprocess
import sys
import time

from common.log import logger


class RecoveryManager:
    """Perform recovery actions on MetaClaw."""

    @staticmethod
    def _get_metaclaw_cli() -> str:
        """Return the path to the metaclaw CLI executable."""
        home_bin = os.path.expanduser("~/.local/bin/metaclaw")
        if os.path.exists(home_bin):
            return home_bin
        # Try PATH
        return "metaclaw"

    def restart_metaclaw(self) -> tuple:
        """Restart MetaClaw via CLI. Return (success: bool, output: str)."""
        cli = self._get_metaclaw_cli()
        try:
            logger.info("[Metadoctor] Restarting MetaClaw...")
            result = subprocess.run(
                [cli, "restart"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            output = result.stdout.strip() + result.stderr.strip()
            success = result.returncode == 0
            logger.info(f"[Metadoctor] restart result: success={success}, output={output[:200]}")
            return success, output
        except Exception as e:
            logger.error(f"[Metadoctor] restart failed: {e}")
            return False, str(e)

    def kill_and_restart(self) -> tuple:
        """Force kill then start MetaClaw. Return (success: bool, output: str)."""
        cli = self._get_metaclaw_cli()
        try:
            logger.info("[Metadoctor] Force killing MetaClaw...")
            subprocess.run([cli, "stop"], capture_output=True, text=True, timeout=10)
            time.sleep(2)
            result = subprocess.run(
                [cli, "start"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            output = result.stdout.strip() + result.stderr.strip()
            success = result.returncode == 0
            logger.info(f"[Metadoctor] kill-and-restart result: success={success}")
            return success, output
        except Exception as e:
            logger.error(f"[Metadoctor] kill-and-restart failed: {e}")
            return False, str(e)

    def get_last_logs(self, n: int = 20) -> str:
        """Return the last N lines of the run log."""
        log_path = os.path.expanduser("~/metaclaw/logs/run.log")
        if not os.path.exists(log_path):
            return f"Log file not found: {log_path}"
        try:
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            last = lines[-n:] if len(lines) >= n else lines
            return "".join(last)
        except Exception as e:
            return f"Failed to read logs: {e}"
