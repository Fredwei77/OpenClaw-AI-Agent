"""Regression coverage for named browser-harness daemon startup."""

from pathlib import Path


def test_browser_harness_starts_the_same_named_daemon_it_pings():
    manager = Path(
        "browser_cluster/manager/browser_harness_manager.py"
    ).read_text(encoding="utf-8")
    assert "ensure_daemon(name=self.name)" in manager
    assert "ipc.ping, self.name" in manager


def test_windows_launcher_starts_chrome_before_backend():
    launcher = Path("scripts/dev.ps1").read_text(encoding="utf-8")
    chrome = launcher.index("Starting Chrome debug port 9222")
    backend = launcher.index("Starting backend at http://127.0.0.1:8000")
    assert chrome < backend
    assert "browser_harness._ipc" in launcher
