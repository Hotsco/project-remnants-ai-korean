"""Portable Setup and conversation-data locations, independent of game launchers."""
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent
PATH_KEYS = {"setup_path", "zomboid_path"}


def state_dir():
    return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "NPCFW-Luna-Adapter"


def read_settings(root=None):
    root = root or ROOT
    settings = {}
    for path in (root / "launcher-settings.json", state_dir() / "paths.json"):
        if path.exists():
            doc = json.loads(path.read_text(encoding="utf-8-sig"))
            if not isinstance(doc, dict):
                raise ValueError("Path settings must be a JSON object: " + str(path))
            settings.update({key: value for key, value in doc.items() if key in PATH_KEYS and value})
    return settings


def expand_path(value, root=None):
    path = Path(os.path.expandvars(value)).expanduser()
    return (path if path.is_absolute() else (root or ROOT) / path).resolve()


def remember(key, path):
    if key not in PATH_KEYS:
        raise ValueError("Unknown path setting")
    folder = state_dir()
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "paths.json"
    previous = json.loads(target.read_text(encoding="utf-8-sig")) if target.exists() else {}
    settings = {name: value for name, value in previous.items() if name in PATH_KEYS}
    path = Path(path).resolve()
    settings[key] = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
    fd, name = tempfile.mkstemp(dir=folder, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(settings, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(name, target)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def powershell(command):
    executable = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    return subprocess.run([str(executable), "-NoProfile", "-NonInteractive", "-Command", command],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          encoding="utf-8", errors="replace", creationflags=subprocess.CREATE_NO_WINDOW)


def pick_path(title, directory=False):
    # This dialog asks the user to choose; it does not automate another program.
    quote = lambda text: "'" + text.replace("'", "''") + "'"
    command = ("[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false); "
               "Add-Type -AssemblyName System.Windows.Forms; ")
    if directory:
        command += ("$d=New-Object System.Windows.Forms.FolderBrowserDialog; "
                    "$d.ShowNewFolderButton=$false; $d.Description=" + quote(title) + "; "
                    "if($d.ShowDialog() -eq 'OK'){[Console]::Write($d.SelectedPath)}")
    else:
        command += ("$d=New-Object System.Windows.Forms.OpenFileDialog; "
                    "$d.Title=" + quote(title) + "; "
                    "$d.Filter='Project Remnants Setup|ProjectRemnantsSetup.exe'; "
                    "if($d.ShowDialog() -eq 'OK'){[Console]::Write($d.FileName)}")
    result = powershell(command)
    if result.returncode or not result.stdout.strip():
        raise ValueError("경로 선택이 취소되었습니다. 다시 실행해서 위치를 선택해주세요.")
    return Path(result.stdout.strip()).resolve()


def unique(paths):
    found = []
    seen = set()
    for path in paths:
        path = Path(path).resolve()
        key = os.path.normcase(str(path))
        if key not in seen:
            seen.add(key)
            found.append(path)
    return found


def zomboid_dir():
    value = read_settings().get("zomboid_path")
    return expand_path(value) if value else Path.home() / "Zomboid"


def setup_executable(interactive=False):
    saved = read_settings().get("setup_path")
    if saved:
        path = expand_path(saved)
        if path.name.lower() == "projectremnantssetup.exe" and path.is_file():
            return path
    # A packaged Setup takes precedence over files left in Downloads.
    for path in (ROOT / "Setup/ProjectRemnantsSetup.exe", ROOT / "ProjectRemnantsSetup.exe"):
        if path.is_file():
            return path.resolve()
    candidates = unique(path for path in (zomboid_dir() / "Workshop/ProjectRemnantsSetup.exe",
                                          Path.home() / "Downloads/ProjectRemnantsSetup.exe") if path.is_file())
    if len(candidates) == 1:
        return candidates[0]
    if interactive:
        path = pick_path("ProjectRemnantsSetup.exe 파일을 선택하세요.")
        if path.name.lower() != "projectremnantssetup.exe" or not path.is_file():
            raise ValueError("ProjectRemnantsSetup.exe 파일을 선택해주세요.")
        remember("setup_path", path)
        return path
    raise ValueError("Setup 위치를 확인하지 못했습니다. 바로가기를 실행해 파일을 선택해주세요.")
