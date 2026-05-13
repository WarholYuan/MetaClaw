import os
import sys
import unittest.mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from common.device import get_device_code, DEVICE_ID_FILE


def test_get_device_code_returns_non_empty_string():
    code = get_device_code()
    assert isinstance(code, str)
    assert len(code) > 0


def test_get_device_code_stable(tmp_path, monkeypatch):
    monkeypatch.setattr("common.device.DEVICE_ID_FILE", str(tmp_path / "device_id"))
    code1 = get_device_code()
    code2 = get_device_code()
    assert code1 == code2


def test_get_device_code_persisted(tmp_path, monkeypatch):
    path = str(tmp_path / "device_id")
    monkeypatch.setattr("common.device.DEVICE_ID_FILE", path)
    code = get_device_code()
    assert os.path.isfile(path)
    with open(path) as f:
        assert f.read().strip() == code


def test_get_device_code_reads_existing(tmp_path, monkeypatch):
    path = str(tmp_path / "device_id")
    with open(path, "w") as f:
        f.write("existing-code-12345")
    monkeypatch.setattr("common.device.DEVICE_ID_FILE", path)
    assert get_device_code() == "existing-code-12345"
