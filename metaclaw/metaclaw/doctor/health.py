"""Health check module for Metadoctor.

Monitors MetaClaw process health: alive, log activity, and optional memory.
"""

import os
import time
from dataclasses import dataclass
from typing import Optional

from common.log import logger
from common.brand import DEFAULT_AGENT_WORKSPACE


@dataclass
class HealthReport:
    """Aggregated health check result."""
    pid: Optional[int]
    process_alive: bool
    log_updated_seconds_ago: Optional[float]
    log_stuck: bool  # no update for > 5 min
    log_dead: bool   # no update for > 15 min
    memory_mb: Optional[float]
    memory_high: bool
    status: str  # "ok" | "warning" | "critical"
    details: list  # list of human-readable strings


class HealthChecker:
    """Check MetaClaw health from process and log files."""

    PID_FILE = os.path.expanduser(os.path.join(DEFAULT_AGENT_WORKSPACE, "logs", ".metaclaw.pid"))
    RUN_LOG = os.path.expanduser(os.path.join(DEFAULT_AGENT_WORKSPACE, "logs", "run.log"))

    def __init__(self):
        self._last_report: Optional[HealthReport] = None

    @staticmethod
    def _read_pid() -> Optional[int]:
        if not os.path.exists(HealthChecker.PID_FILE):
            return None
        try:
            with open(HealthChecker.PID_FILE, "r") as f:
                pid = int(f.read().strip())
            return pid
        except (ValueError, OSError):
            return None

    @staticmethod
    def _is_pid_alive(pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except (ProcessLookupError, PermissionError):
            return False

    @staticmethod
    def _get_log_mtime() -> Optional[float]:
        try:
            return os.path.getmtime(HealthChecker.RUN_LOG)
        except (OSError, FileNotFoundError):
            return None

    @staticmethod
    def _get_memory_mb(pid: int) -> Optional[float]:
        try:
            import psutil
            proc = psutil.Process(pid)
            return proc.memory_info().rss / (1024 * 1024)
        except Exception:
            return None

    def check_process(self) -> tuple:
        """Return (pid, alive)."""
        pid = self._read_pid()
        alive = False
        if pid:
            alive = self._is_pid_alive(pid)
        return pid, alive

    def check_log_activity(self) -> tuple:
        """Return (seconds_since_update, stuck, dead)."""
        mtime = self._get_log_mtime()
        if mtime is None:
            return None, False, False
        ago = time.time() - mtime
        return ago, ago > 300, ago > 900  # 5min, 15min

    def check_memory(self, pid: int) -> tuple:
        """Return (memory_mb, high)."""
        mem = self._get_memory_mb(pid)
        return mem, (mem is not None and mem > 2048)

    def full_check(self) -> HealthReport:
        """Run all checks and return a report."""
        pid, alive = self.check_process()
        ago, stuck, dead = self.check_log_activity()
        mem, mem_high = self.check_memory(pid) if pid else (None, False)

        details = []
        status = "ok"

        if not alive:
            status = "critical"
            details.append(f"MetaClaw process not alive (PID: {pid})")
        else:
            details.append(f"MetaClaw process alive (PID: {pid})")

        if alive and stuck:
            status = "warning" if status == "ok" else status
            details.append(f"No log update for {int(ago)}s (stuck threshold: 300s)")
        if alive and dead:
            status = "critical"
            details.append(f"No log update for {int(ago)}s (dead threshold: 900s)")

        if mem_high:
            status = "warning" if status == "ok" else status
            details.append(f"Memory usage high: {mem:.0f}MB (> 2048MB)")
        elif mem is not None:
            details.append(f"Memory: {mem:.0f}MB")

        if not details:
            details.append("All checks passed")

        report = HealthReport(
            pid=pid,
            process_alive=alive,
            log_updated_seconds_ago=ago,
            log_stuck=stuck,
            log_dead=dead,
            memory_mb=mem,
            memory_high=mem_high,
            status=status,
            details=details,
        )
        self._last_report = report
        return report

    def state_changed(self, report: HealthReport) -> bool:
        """Return True if the report represents a state change from the previous one."""
        if self._last_report is None:
            return True
        return report.status != self._last_report.status
