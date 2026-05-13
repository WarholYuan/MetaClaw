import hashlib
import os
import platform
import subprocess
import uuid

from common.brand import DEFAULT_ENV_DIR

DEVICE_ID_FILE = os.path.expanduser(f"{DEFAULT_ENV_DIR}/device_id")


def _read_cpu_serial() -> str:
    system = platform.system()
    try:
        if system == "Darwin":
            result = subprocess.run(
                ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                capture_output=True, text=True, timeout=5,
            )
            for line in result.stdout.splitlines():
                if "IOPlatformSerialNumber" in line:
                    return line.split("=")[-1].strip().strip('"')
        elif system == "Linux":
            for path in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
                if os.path.isfile(path):
                    with open(path) as f:
                        return f.read().strip()
        elif system == "Windows":
            result = subprocess.run(
                ["wmic", "bios", "get", "serialnumber"],
                capture_output=True, text=True, timeout=5,
            )
            lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]
            if len(lines) >= 2:
                return lines[1]
    except Exception:
        pass
    return ""


def _generate_device_code() -> str:
    serial = _read_cpu_serial()
    if serial:
        return hashlib.sha256(serial.encode()).hexdigest()[:32]
    host_id = f"{uuid.getnode()}-{platform.node()}"
    return hashlib.sha256(host_id.encode()).hexdigest()[:32]


def get_device_code() -> str:
    path = DEVICE_ID_FILE
    if os.path.isfile(path):
        with open(path, "r") as f:
            code = f.read().strip()
            if code:
                return code
    code = _generate_device_code()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(code)
    return code
