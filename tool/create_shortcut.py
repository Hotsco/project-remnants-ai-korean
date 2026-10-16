"""Create a shortcut using the current package folder and Windows Desktop location."""
import os
from pathlib import Path
import sys
import paths


def main():
    quote = lambda text: "'" + str(text).replace("'", "''") + "'"
    target = Path(os.environ["SystemRoot"]) / "System32/cmd.exe"
    command = paths.ROOT / "Start-Setup-And-Luna.cmd"
    args = '/d /c ""' + str(command) + '""'
    script = ("$ErrorActionPreference='Stop'; [Console]::OutputEncoding=[Text.UTF8Encoding]::new($false); "
              "$desktop=[Environment]::GetFolderPath('Desktop'); "
              "$file=Join-Path $desktop '좀보이드 Luna 대화 시작.lnk'; "
              "$shell=New-Object -ComObject WScript.Shell; $link=$shell.CreateShortcut($file); "
              "$link.TargetPath=" + quote(target) + "; $link.Arguments=" + quote(args) + "; "
              "$link.WorkingDirectory=" + quote(paths.ROOT) + "; $link.WindowStyle=1; "
              "$link.Description='Project Remnants Setup + Luna'; $link.Save(); "
              "[Console]::Write($file)")
    result = paths.powershell(script)
    if result.returncode:
        raise ValueError("바로가기 생성에 실패했습니다: " + result.stderr.strip())
    print("바로가기를 만들었습니다: " + result.stdout)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
