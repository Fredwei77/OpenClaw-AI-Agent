"""
Chrome launcher with remote debugging support.
Launches Chrome with --remote-debugging-port for browser-harness CDP connection.
"""
import os
import sys
import subprocess
import socket
import logging
import urllib.request
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_DEBUG_PORT = 9222


def is_debug_port_open(port: int = DEFAULT_DEBUG_PORT) -> bool:
    """Check if Chrome remote debugging port is responding."""
    try:
        resp = urllib.request.urlopen(
            f"http://127.0.0.1:{port}/json/version", timeout=2
        )
        resp.close()
        return True
    except OSError:
        return False


def get_ws_debug_url(port: int = DEFAULT_DEBUG_PORT) -> str | None:
    """Get the WebSocket debugger URL from Chrome's /json/version endpoint."""
    try:
        resp = urllib.request.urlopen(
            f"http://127.0.0.1:{port}/json/version", timeout=2
        )
        import json
        data = json.loads(resp.read())
        resp.close()
        return data.get("webSocketDebuggerUrl")
    except Exception:
        return None


def _find_chrome_executable() -> str | None:
    """Find Chrome executable on Windows."""
    candidates = [
        os.environ.get("CHROME_PATH"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    return None


def launch_chrome_with_debugging(
    port: int = DEFAULT_DEBUG_PORT,
    user_data_dir: str | None = None,
) -> subprocess.Popen | None:
    """
    Launch Chrome with remote debugging enabled.

    Args:
        port: Debugging port (default 9222)
        user_data_dir: Chrome user data directory (uses default if None)

    Returns:
        Popen process handle, or None if Chrome is already running / launch failed
    """
    if is_debug_port_open(port):
        logger.info(f"Chrome debugging already available on port {port}")
        return None

    chrome_exe = _find_chrome_executable()
    if not chrome_exe:
        logger.error("Chrome executable not found. Set CHROME_PATH environment variable.")
        return None

    args = [
        chrome_exe,
        f"--remote-debugging-port={port}",
        "--remote-debugging-address=127.0.0.1",
        "--remote-allow-origins=*",
    ]
    if user_data_dir:
        args.append(f"--user-data-dir={user_data_dir}")

    # Windows-specific: don't inherit console
    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW

    try:
        proc = subprocess.Popen(
            args,
            creationflags=creationflags,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        logger.info(f"Chrome launched with debugging on port {port} (pid={proc.pid})")

        # Wait for debugging port to become available
        import time
        for _ in range(30):
            if is_debug_port_open(port):
                logger.info("Chrome debugging port is ready")
                return proc
            time.sleep(0.5)

        logger.warning("Chrome launched but debugging port not responding within 15s")
        return proc

    except Exception as e:
        logger.error(f"Failed to launch Chrome: {e}")
        return None


def kill_chrome_debug(port: int = DEFAULT_DEBUG_PORT) -> bool:
    """Kill Chrome processes started with debugging port. Returns True if killed."""
    if sys.platform != "win32":
        return False

    try:
        # Find PIDs listening on the debug port
        result = subprocess.run(
            ["netstat", "-ano"], capture_output=True, text=True, timeout=10
        )
        pids = set()
        for line in result.stdout.splitlines():
            if f" 127.0.0.1:{port} " in line and "LISTENING" in line:
                parts = line.split()
                if parts:
                    pids.add(parts[-1])

        for pid in pids:
            try:
                subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True, timeout=5)
                logger.info(f"Killed Chrome process {pid}")
            except Exception:
                pass
        return bool(pids)
    except Exception as e:
        logger.error(f"Failed to kill Chrome: {e}")
        return False
