"""Build a Workshop upload folder from repository-relative addon files."""
from pathlib import Path
import shutil

root = Path(__file__).resolve().parent
output = root / 'dist/ProjectRemnants_AI_Korean'
if output.exists():
    raise SystemExit('Output already exists. Keep any published Workshop ID before rebuilding.')
output.mkdir(parents=True)
for name in ('workshop.txt', 'preview.png'):
    shutil.copy2(root / 'workshop' / name, output / name)
shutil.copytree(root / 'tool/addons/ProjectRemnants_KoreanCommands',
                output / 'Contents/mods/ProjectRemnants_KoreanCommands')
print(output)
