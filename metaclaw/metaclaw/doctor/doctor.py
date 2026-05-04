"""Metadoctor main entry point.

Runs as a separate process alongside MetaClaw. Monitors health and
accepts commands via Feishu IM.

Usage:
    python -m doctor.doctor  (or via CLI: metaclaw doctor start)
"""

import json
import os
import signal
import subprocess
import sys
import threading
import time

from common.brand import APP_NAME
from common.log import logger
from config import conf
from doctor.feishu_client import MetadoctorFeishuClient
from doctor.health import HealthChecker
from doctor.recovery import RecoveryManager
from doctor.commands import CommandRouter

# Ensure project root is on sys.path so relative imports work
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# File paths (mirroring process.py pattern)
PID_FILE = os.path.expanduser("~/metaclaw/logs/.metadoctor.pid")
LOG_FILE = os.path.expanduser("~/metaclaw/logs/metadoctor.log")


class Metadoctor:
    """The main Metadoctor daemon."""

    def __init__(self):
        self.config = conf()
        self.enabled = self.config.get("metadoctor_enabled", False)
        self.check_interval = self.config.get("metadoctor_check_interval", 30)
        self.app_id = self.config.get("metadoctor_feishu_app_id", "")
        self.app_secret = self.config.get("metadoctor_feishu_app_secret", "")
        self.notify_open_id = self.config.get("metadoctor_notify_open_id", "")

        self.feishu: MetadoctorFeishuClient = None
        self.health = HealthChecker()
        self.recovery = RecoveryManager()
        self.router: CommandRouter = None
        self._running = False
        self._health_thread = None
        self._last_notify_status = None

        # Install signal handlers
        signal.signal(signal.SIGTERM, self._on_signal)
        signal.signal(signal.SIGINT, self._on_signal)

    def _on_signal(self, signum, frame):
        logger.info(f"[Metadoctor] Received signal {signum}, shutting down...")
        self.stop()
        sys.exit(0)

    def _write_pid(self):
        try:
            os.makedirs(os.path.dirname(PID_FILE), exist_ok=True)
            with open(PID_FILE, "w") as f:
                f.write(str(os.getpid()))
            logger.info(f"[Metadoctor] PID written to {PID_FILE}")
        except Exception as e:
            logger.error(f"[Metadoctor] Failed to write PID file: {e}")

    def _remove_pid(self):
        try:
            if os.path.exists(PID_FILE):
                os.remove(PID_FILE)
        except Exception:
            pass

    def _notify(self, text: str):
        """Send a notification to the configured Feishu open_id."""
        if self.feishu and self.notify_open_id:
            self.feishu.send_text(self.notify_open_id, text)

    def _on_feishu_message(self, open_id: str, text: str):
        """Callback when a Feishu message is received."""
        # Route to command handler
        if self.router:
            self.router.handle(open_id, text)

    def _health_check_loop(self):
        """Background thread: periodic health checks."""
        logger.info(f"[Metadoctor] Health check loop started (interval={self.check_interval}s)")
        while self._running:
            try:
                report = self.health.full_check()
                # Notify only on state change
                if self._last_notify_status != report.status:
                    self._last_notify_status = report.status
                    if report.status == "critical":
                        details = "\n".join(f"- {d}" for d in report.details)
                        self._notify(f"[CRITICAL] MetaClaw issue detected:\n{details}\n\nReply 'restart' to restart MetaClaw.")
                    elif report.status == "warning":
                        details = "\n".join(f"- {d}" for d in report.details)
                        self._notify(f"[WARNING] MetaClaw warning:\n{details}")
            except Exception as e:
                logger.error(f"[Metadoctor] Health check error: {e}", exc_info=True)

            # Sleep with early exit on stop()
            for _ in range(self.check_interval):
                if not self._running:
                    break
                time.sleep(1)

    def start(self):
        """Start the Metadoctor daemon."""
        if not self.enabled:
            logger.info("[Metadoctor] Not enabled in config, exiting.")
            logger.info("Metadoctor is not enabled. Set metadoctor_enabled=true in config.json.")
            return

        if not self.app_id or not self.app_secret:
            logger.error("[Metadoctor] Missing feishu config: metadoctor_feishu_app_id / metadoctor_feishu_app_secret")
            logger.error("Error: metadoctor_feishu_app_id and metadoctor_feishu_app_secret are required.")
            sys.exit(1)

        self._write_pid()
        self._running = True

        # Initialize Feishu client
        self.feishu = MetadoctorFeishuClient(self.app_id, self.app_secret)

        # Initialize command router (reply goes back to sender; notify goes to notify_open_id)
        self.router = CommandRouter(
            self.health,
            self.recovery,
            lambda open_id, text: self.feishu.send_text(open_id, text),
        )

        # Start WebSocket listener
        try:
            self.feishu.start_websocket(self._on_feishu_message)
        except Exception as e:
            logger.error(f"[Metadoctor] Failed to start Feishu WebSocket: {e}")
            logger.error(f"Error: Could not connect to Feishu: {e}")
            self.stop()
            sys.exit(1)

        # Start health check thread
        self._health_thread = threading.Thread(target=self._health_check_loop, daemon=True)
        self._health_thread.start()

        # Notify startup
        self._notify(f"Metadoctor started. Monitoring {APP_NAME}.\nType 'help' for commands.")
        logger.info("[Metadoctor] Daemon started successfully")
        logger.info("Metadoctor started.")

        # Main loop
        while self._running:
            time.sleep(1)

    def stop(self):
        """Stop the Metadoctor daemon."""
        logger.info("[Metadoctor] Stopping daemon...")
        self._running = False
        if self.feishu:
            try:
                self.feishu.stop()
            except Exception:
                pass
        self._remove_pid()
        logger.info("[Metadoctor] Daemon stopped")


# Entry point when run directly
if __name__ == "__main__":
    # Load config before importing doctor modules
    from config import load_config
    load_config()

    doctor = Metadoctor()
    doctor.start()
