"""Install only this package's Lua addon; never enable mods or edit a save."""
from datetime import datetime
from pathlib import Path
import shutil
import sys

import paths

MOD_ID = "ProjectRemnants_KoreanCommands"
FILES = ["42/mod.info"] + ["42/media/lua/client/"+name for name in (
    "NPCFW_KoreanCommandConfig.lua", "NPCFW_KoreanCommandParser.lua",
    "NPCFW_LunaContext.lua", "ZZ_NPCFW_KoreanCommands.lua")] + ["42/preview.png"]


def install(source, userdata, backup_root):
    source, userdata = Path(source).resolve(), Path(userdata).resolve()
    mods = (userdata / "mods").resolve()
    target = (mods / MOD_ID).resolve()
    if target.parent != mods:
        raise ValueError("Addon folder points outside the selected mods directory")
    if any(not (source / name).is_file() for name in FILES):
        raise ValueError("Addon files are missing. Extract the complete ZIP.")
    info = target / "42/mod.info"
    if target.exists() and (not info.is_file() or
            "id="+MOD_ID not in info.read_text(encoding="utf-8-sig").splitlines()):
        raise ValueError("The destination contains a different mod; it was not changed.")
    for name in FILES:
        if not (target / name).resolve().is_relative_to(target):
            raise ValueError("An addon file points outside its folder")
    backup = Path(backup_root) / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    installed, preserved, unchanged = [], [], []
    for name in FILES:
        destination = target / name
        # Preserve each user's custom vocabulary when updating the common addon.
        if name.endswith("NPCFW_KoreanCommandConfig.lua") and destination.exists():
            preserved.append(name)
            continue
        if destination.is_file() and destination.read_bytes() == (source / name).read_bytes():
            unchanged.append(name)
            continue
        if destination.exists():
            saved = backup / name
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(destination, saved)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / name, destination)
        installed.append(name)
    return {"target": str(target), "backup": str(backup) if backup.exists() else None,
            "installed": installed, "preserved": preserved, "unchanged": unchanged}


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    try:
        result = install(paths.ROOT / "addons" / MOD_ID, paths.zomboid_dir(),
                         paths.state_dir() / "addon-backups")
        print("설치 완료: " + result["target"])
        if result["installed"]:
            print("게임을 완전히 종료한 뒤 다시 실행해주세요.")
        else:
            print("설치된 파일이 배포본과 같아 다시 복사하지 않았습니다.")
        print("처음 설치했다면 사용할 세이브의 모드 설정에서 Project Remnants AI 대화 한국어 변환을 켜주세요.")
        print("NPC 프로필 편집: Open-NPC-Settings.cmd / 명령·상황 가이드: GUIDE.html")
        if result["preserved"]:
            print("기존 한국어 명령 낱말 설정은 유지했습니다.")
        return 0
    except (OSError, ValueError) as error:
        print("설치 실패: " + str(error))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
