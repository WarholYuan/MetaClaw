"""CLI commands for Metadoctor."""

import os
import sys
import subprocess
import time

import click

from cli.utils import get_project_root
from common.brand import APP_NAME

_IS_WIN = sys.platform == "win32"

# Same path pattern as main process PID file
from common.brand import DEFAULT_AGENT_WORKSPACE

_DOCTOR_PID_FILE = os.path.expanduser(os.path.join(DEFAULT_AGENT_WORKSPACE, "logs", ".metadoctor.pid"))
_DOCTOR_LOG_FILE = os.path.expanduser(os.path.join(DEFAULT_AGENT_WORKSPACE, "logs", "metadoctor.log"))


def _read_pid():
    if not os.path.exists(_DOCTOR_PID_FILE):
        return None
    try:
        with open(_DOCTOR_PID_FILE, "r") as f:
            pid = int(f.read().strip())
        # Check if alive
        try:
            os.kill(pid, 0)
            return pid
        except (ProcessLookupError, PermissionError):
            os.remove(_DOCTOR_PID_FILE)
            return None
    except (ValueError, OSError):
        try:
            os.remove(_DOCTOR_PID_FILE)
        except OSError:
            pass
        return None


def _write_pid(pid: int):
    os.makedirs(os.path.dirname(_DOCTOR_PID_FILE), exist_ok=True)
    with open(_DOCTOR_PID_FILE, "w") as f:
        f.write(str(pid))


def _remove_pid():
    if os.path.exists(_DOCTOR_PID_FILE):
        os.remove(_DOCTOR_PID_FILE)


def _kill_pid(pid: int, force: bool = False):
    if _IS_WIN:
        cmd = ["taskkill"]
        if force:
            cmd.append("/F")
        cmd.extend(["/PID", str(pid)])
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        import signal
        sig = signal.SIGKILL if force else signal.SIGTERM
        os.kill(pid, sig)


@click.group(name="doctor")
def doctor_group():
    """Manage Metadoctor (health monitor for MetaClaw)."""
    pass


@doctor_group.command()
@click.option("--foreground", "-f", is_flag=True, help="Run in foreground")
def start(foreground):
    """Start the Metadoctor daemon."""
    pid = _read_pid()
    if pid:
        click.echo(f"Metadoctor is already running (PID: {pid}).")
        return

    root = get_project_root()
    doctor_py = os.path.join(root, "doctor", "doctor.py")
    if not os.path.exists(doctor_py):
        click.echo("Error: doctor/doctor.py not found.", err=True)
        sys.exit(1)

    python = sys.executable

    if foreground:
        click.echo("Starting Metadoctor in foreground...")
        if _IS_WIN:
            sys.exit(subprocess.call([python, doctor_py], cwd=root))
        else:
            os.execv(python, [python, doctor_py])
    else:
        os.makedirs(os.path.dirname(_DOCTOR_LOG_FILE), exist_ok=True)
        click.echo("Starting Metadoctor...")
        with open(_DOCTOR_LOG_FILE, "a") as log:
            if _IS_WIN:
                p = subprocess.Popen(
                    [python, doctor_py],
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    cwd=root,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            else:
                p = subprocess.Popen(
                    [python, doctor_py],
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    cwd=root,
                    start_new_session=True,
                )
        _write_pid(p.pid)
        click.echo(f"Metadoctor started (PID: {p.pid}).")
        click.echo(f"Logs: {_DOCTOR_LOG_FILE}")


@doctor_group.command()
def stop():
    """Stop the Metadoctor daemon."""
    pid = _read_pid()
    if not pid:
        click.echo("Metadoctor is not running.")
        return

    click.echo(f"Stopping Metadoctor (PID: {pid})...")
    _kill_pid(pid)
    for _ in range(30):
        time.sleep(0.1)
        try:
            os.kill(pid, 0)
        except (ProcessLookupError, PermissionError):
            click.echo("Metadoctor stopped.")
            _remove_pid()
            return
    # Force kill
    _kill_pid(pid, force=True)
    _remove_pid()
    click.echo("Metadoctor force-killed.")


@doctor_group.command()
def status():
    """Show Metadoctor running status."""
    pid = _read_pid()
    if pid:
        click.echo(f"Metadoctor is running (PID: {pid}).")
    else:
        click.echo("Metadoctor is not running.")


@doctor_group.command()
@click.option("--follow", "-f", is_flag=True, help="Follow log output")
def logs(follow):
    """View Metadoctor logs."""
    if not os.path.exists(_DOCTOR_LOG_FILE):
        click.echo(f"No log file found at {_DOCTOR_LOG_FILE}")
        return

    if follow:
        click.echo(f"Tailing {_DOCTOR_LOG_FILE} (Ctrl+C to exit)...")
        try:
            if _IS_WIN:
                subprocess.run(["powershell", "-Command", "Get-Content", "-Path", _DOCTOR_LOG_FILE, "-Wait"])
            else:
                subprocess.run(["tail", "-f", _DOCTOR_LOG_FILE])
        except KeyboardInterrupt:
            click.echo("")
    else:
        try:
            with open(_DOCTOR_LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            last = lines[-50:] if len(lines) >= 50 else lines
            click.echo("".join(last))
        except Exception as e:
            click.echo(f"Error reading log: {e}")
