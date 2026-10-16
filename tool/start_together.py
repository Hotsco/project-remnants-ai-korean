"""Open Setup, wait for its local bridge, then start the existing Luna adapter."""
import argparse
import base64
import ctypes
from ctypes import wintypes
import hashlib
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import adapter
import paths

ROOT = Path(__file__).resolve().parent
POWERSHELL = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"


def setup_path(interactive=False):
    return paths.setup_executable(interactive=interactive)


def setup_running():
    command = ("$ErrorActionPreference='Stop'; if(Get-Process -Name ProjectRemnantsSetup "
               "-ErrorAction SilentlyContinue){exit 0}else{exit 1}")
    result = subprocess.run([str(POWERSHELL), "-NoProfile", "-NonInteractive", "-Command", command],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode not in (0, 1):
        raise ValueError("Could not check whether Project Remnants Setup is running")
    return result.returncode == 0


def bridge_configuration(provider=adapter.PROVIDER, state_dir=adapter.STATE_DIR):
    raw = provider.read_bytes()
    doc = adapter.decode(raw)
    if doc.get("endpoint") == adapter.ENDPOINT:
        saved = adapter.decode((state_dir / "state.json").read_bytes())
        if saved.get("service") != adapter.SERVICE or saved.get("proxy_token") != doc.get("apiKey"):
            raise ValueError("Adapter recovery settings do not match the provider")
        raw = base64.b64decode(saved["upstream_base64"], validate=True)
        doc = adapter.decode(raw)
    # No API request: validate the local address and test only the TCP listener.
    return adapter.validate_upstream(doc), hashlib.sha256(raw).digest()


def bridge_listening(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def start_when_ready(timeout):
    print("Setup의 LLM Companion 탭에서 Configure and Start를 눌러주세요.", flush=True)
    print("중계 서버를 확인하면 Luna 변환기를 자동으로 시작합니다.", flush=True)
    deadline = time.monotonic() + timeout
    stable_signature, stable_since = None, None
    while time.monotonic() < deadline:
        try:
            port, signature = bridge_configuration()
            listening = bridge_listening(port)
        except (OSError, ValueError, KeyError, TypeError):
            listening = False
        now = time.monotonic()
        if not listening:
            stable_signature, stable_since = None, None
        elif signature != stable_signature:
            stable_signature, stable_since = signature, now
        elif now - stable_since >= 2:
            status = adapter.start()
            # An already-running adapter may need its next one-second sync cycle.
            for _ in range(30):
                if status.get("ready"):
                    return
                time.sleep(0.2)
                status = adapter.control()
            raise ValueError("Adapter is running but its configuration is not ready")
        time.sleep(1)
    raise ValueError("Setup bridge did not start within the wait period. Run Configure and Start, then retry.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Check paths without opening programs or changing settings")
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()
    path = setup_path(interactive=not args.check)
    if args.check:
        print("Setup: " + str(path))
        print("Luna: " + str(ROOT / "adapter.py"))
        print("Python: " + str(Path(sys.executable)))
        return 0
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.CreateMutexW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.CreateMutexW(None, False, "Local\\NPCFW-Luna-CombinedLauncher")
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    already_running = ctypes.get_last_error() == 183
    try:
        if already_running:
            print("이미 실행 준비 중입니다. 열린 Setup에서 Configure and Start를 눌러주세요.")
            return 0
        if not setup_running():
            # Setup is the interactive GUI explicitly requested by the user.
            subprocess.Popen([str(path)], cwd=str(path.parent))
        start_when_ready(args.timeout)
        print("Setup 중계 서버와 Luna 변환기가 실행 중입니다. 이제 게임을 실행하세요.", flush=True)
        ctypes.windll.user32.MessageBoxW(None,
            "Setup 중계 서버와 Luna 변환기가 실행 중입니다.\n이제 좀보이드를 실행하세요.",
            "좀보이드 Luna 실행 준비 완료", 0x40)
        return 0
    finally:
        kernel.CloseHandle(handle)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, TypeError) as error:
        print("실행 준비 실패: " + str(error), file=sys.stderr)
        raise SystemExit(1)
