"""Command parser and executor for Metadoctor Feishu messages.

Users send text commands to Metadoctor via Feishu, and this module
routes them to the appropriate action.
"""

from typing import Callable

from doctor.health import HealthChecker
from doctor.recovery import RecoveryManager
from common.log import logger


class CommandRouter:
    """Parse and execute commands sent via Feishu."""

    def __init__(self, health_checker: HealthChecker, recovery: RecoveryManager,
                 reply_callback: Callable[[str, str], None]):
        self.health = health_checker
        self.recovery = recovery
        self.reply = reply_callback

    def handle(self, open_id: str, text: str):
        """Route a message to the correct handler."""
        text_lower = text.strip().lower()
        parts = text_lower.split()
        cmd = parts[0] if parts else ""
        args = parts[1:] if len(parts) > 1 else []

        logger.info(f"[Metadoctor] command from {open_id}: {cmd} args={args}")

        if cmd in ("status", "状态"):
            self._cmd_status(open_id)
        elif cmd in ("restart", "重启"):
            self._cmd_restart(open_id)
        elif cmd in ("logs", "日志"):
            n = 20
            if args:
                try:
                    n = int(args[0])
                except ValueError:
                    pass
            self._cmd_logs(open_id, n)
        elif cmd in ("diagnose", "诊断"):
            self._cmd_diagnose(open_id)
        elif cmd in ("help", "帮助", "?"):
            self._cmd_help(open_id)
        else:
            self.reply(open_id, f"Unknown command: '{cmd}'. Type 'help' for available commands.")

    def _cmd_status(self, open_id: str):
        report = self.health.full_check()
        lines = [
            f"**Status: {report.status.upper()}**",
            f"Process: {'Alive' if report.process_alive else 'DEAD'} (PID: {report.pid})",
        ]
        if report.log_updated_seconds_ago is not None:
            lines.append(f"Log updated: {int(report.log_updated_seconds_ago)}s ago")
        if report.memory_mb is not None:
            lines.append(f"Memory: {report.memory_mb:.0f}MB")
        self.reply(open_id, "\n".join(lines))

    def _cmd_restart(self, open_id: str):
        self.reply(open_id, "Restarting MetaClaw...")
        success, output = self.recovery.restart_metaclaw()
        if success:
            self.reply(open_id, "MetaClaw restarted successfully.")
        else:
            self.reply(open_id, f"Restart failed:\n{output[:500]}")

    def _cmd_logs(self, open_id: str, n: int):
        logs = self.recovery.get_last_logs(n)
        msg = f"Last {n} lines of run.log:\n```\n{logs[:3000]}\n```"
        self.reply(open_id, msg)

    def _cmd_diagnose(self, open_id: str):
        report = self.health.full_check()
        lines = [f"**Diagnose: {report.status.upper()}**"]
        for d in report.details:
            lines.append(f"- {d}")
        self.reply(open_id, "\n".join(lines))

    def _cmd_help(self, open_id: str):
        self.reply(open_id,
            "Metadoctor commands:\n"
            "- `status` / `状态` — Show MetaClaw process status\n"
            "- `restart` / `重启` — Restart MetaClaw\n"
            "- `logs [N]` / `日志 [N]` — Show last N lines of log (default 20)\n"
            "- `diagnose` / `诊断` — Full health diagnosis\n"
            "- `help` / `帮助` — Show this message"
        )
