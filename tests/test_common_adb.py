"""The shared device layer.

Covers the three guarantees that matter: exclusive access, one dump per cycle,
and loud failure. None of it needs a device.
"""
import subprocess
import threading
import time

import pytest

from common.adb import AdbDevice, DeviceLock, NoDeviceError


# --- loud failure -----------------------------------------------------------

def test_a_missing_adb_binary_raises_rather_than_simulating(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda *_: None)
    with pytest.raises(NoDeviceError, match="not on PATH"):
        AdbDevice.list_devices()


def test_no_attached_device_raises(monkeypatch):
    monkeypatch.setattr(AdbDevice, "list_devices", staticmethod(lambda adb="adb": []))
    with pytest.raises(NoDeviceError, match="no Android device"):
        AdbDevice()


def test_an_unknown_serial_raises(monkeypatch):
    monkeypatch.setattr(AdbDevice, "list_devices", staticmethod(lambda adb="adb": ["abc"]))
    with pytest.raises(NoDeviceError, match="not attached"):
        AdbDevice(serial="zzz")


def test_two_devices_without_a_serial_raises_rather_than_guessing(monkeypatch):
    monkeypatch.setattr(AdbDevice, "list_devices", staticmethod(lambda adb="adb": ["a", "b"]))
    with pytest.raises(NoDeviceError, match="pass serial="):
        AdbDevice()


def test_a_single_device_is_adopted(monkeypatch):
    monkeypatch.setattr(AdbDevice, "list_devices", staticmethod(lambda adb="adb": ["only"]))
    assert AdbDevice().serial == "only"


def test_a_missing_binary_surfaces_as_one_exception_type(monkeypatch):
    d = AdbDevice(serial="x", verify=False)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(FileNotFoundError()))
    with pytest.raises(NoDeviceError):
        d.run("devices")


# --- exclusive access -------------------------------------------------------

def test_the_lock_serialises_concurrent_holders():
    order = []

    def hold(n):
        with DeviceLock("unit-test"):
            order.append(f"{n}-in")
            time.sleep(0.03)
            order.append(f"{n}-out")

    threads = [threading.Thread(target=hold, args=(i,)) for i in range(4)]
    for t in threads: t.start()
    for t in threads: t.join()
    # every entry is immediately followed by its own exit: never interleaved
    assert all(order[i].endswith("-in") and order[i + 1].endswith("-out")
               for i in range(0, len(order), 2))


def test_the_lock_is_released_even_when_the_body_raises():
    with pytest.raises(ValueError):
        with DeviceLock("unit-test-raise"):
            raise ValueError("boom")
    with DeviceLock("unit-test-raise"):   # would block forever if still held
        pass


def test_different_devices_do_not_block_each_other():
    with DeviceLock("device-a"):
        with DeviceLock("device-b"):      # separate lock file
            pass


# --- one dump per cycle -----------------------------------------------------

HIERARCHY = '<hierarchy><node bounds="[0,0][10,10]"/></hierarchy>'


def _stub_dump(monkeypatch, device):
    calls = {"n": 0}

    def fake(argv, **kw):
        if "exec-out" in argv:
            calls["n"] += 1
            return subprocess.CompletedProcess(argv, 0, stdout=HIERARCHY, stderr="")
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake)
    return calls


def test_a_fresh_enough_dump_is_reused(monkeypatch):
    d = AdbDevice(serial="x", verify=False)
    calls = _stub_dump(monkeypatch, d)
    for _ in range(5):
        d.dump_hierarchy(max_age_s=10.0)
    assert calls["n"] == 1
    assert d.dump_count == 1


def test_a_stale_dump_is_refreshed(monkeypatch):
    d = AdbDevice(serial="x", verify=False)
    calls = _stub_dump(monkeypatch, d)
    d.dump_hierarchy(max_age_s=0.0)
    d.dump_hierarchy(max_age_s=0.0)
    assert calls["n"] == 2


def test_the_dump_is_parsed_into_a_tree(monkeypatch):
    d = AdbDevice(serial="x", verify=False)
    _stub_dump(monkeypatch, d)
    assert d.hierarchy_root().tag == "hierarchy"


def test_a_dump_without_a_hierarchy_element_raises(monkeypatch):
    d = AdbDevice(serial="x", verify=False)
    monkeypatch.setattr(subprocess, "run",
                        lambda argv, **kw: subprocess.CompletedProcess(argv, 0, "junk", ""))
    with pytest.raises(RuntimeError, match="hierarchy"):
        d.dump_hierarchy()


# --- invocation hygiene -----------------------------------------------------

def test_the_serial_is_passed_to_adb():
    d = AdbDevice(serial="emulator-5554", verify=False)
    assert d._argv(["shell", "x"]) == ["adb", "-s", "emulator-5554", "shell", "x"]


def test_commands_are_argument_lists_never_shell_strings():
    d = AdbDevice(serial="x", verify=False)
    argv = d._argv(["shell", "input text", "a;rm -rf /"])
    assert argv[-1] == "a;rm -rf /"          # stays one argument, never interpreted
    assert all(isinstance(a, str) for a in argv)
