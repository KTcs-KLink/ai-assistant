"""Launcher tests: never start, install, or access the user's original local index."""
import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "launch_local_demo.py"
spec = importlib.util.spec_from_file_location("local_demo_launcher", SCRIPT)
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


def test_identifies_fastapi_entrypoint_without_running_it(tmp_path):
    demo = tmp_path / "chat" / "kepco_hr_demo_20261102"
    demo.mkdir(parents=True)
    path = demo / "app.py"
    path.write_text("from fastapi import FastAPI\napp = FastAPI()\n")
    assert launcher.find_app_entry(demo) == path
    args, cwd = launcher.original_launch(demo, tmp_path, 8811)
    assert args[1:3] == ["-m", "uvicorn"]
    assert "app:app" in args
    assert args[-1] == "8811"
    assert cwd == demo


def test_identifies_start_script_without_running_it(tmp_path):
    demo = tmp_path / "demo"
    demo.mkdir()
    starter = demo / "start.ps1"
    starter.write_text("# original entrypoint\n")
    cmd, cwd = launcher.original_launch(demo, tmp_path, 8811)
    assert cmd[:3] == ["powershell.exe", "-NoProfile", "-ExecutionPolicy"]
    assert str(starter) in cmd
    assert cwd == demo


def test_fails_instead_of_guessing_when_entrypoint_ambiguous(tmp_path):
    demo = tmp_path / "demo"
    demo.mkdir()
    (demo / "a.py").write_text("from fastapi import FastAPI\napp = FastAPI()\n")
    (demo / "b.py").write_text("from fastapi import FastAPI\napp = FastAPI()\n")
    assert launcher.find_app_entry(demo) is None
    with pytest.raises(RuntimeError, match="진입점|시작 파일"):
        launcher.original_launch(demo, tmp_path, 8811)


def test_python_selector_keeps_preexisting_virtual_environment(tmp_path):
    demo = tmp_path / "demo"
    demo.mkdir()
    exe = demo / ".venv" / "Scripts" / "python.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"")
    assert launcher.python_for(demo, tmp_path) == str(exe)
