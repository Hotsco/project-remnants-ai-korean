"""Save profile editing through the installed reader, with backup and read-back."""
from contextlib import contextmanager
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import threading
import zipfile

import paths

MAX_SAVE = 64 * 1024 * 1024
HIDDEN = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


class ProfileError(ValueError):
    pass


def digest(data):
    return hashlib.sha256(data).hexdigest()


def atomic_file(destination, data):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.' + destination.name + '.', dir=destination.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)


def json_bytes(value):
    return json.dumps(value, ensure_ascii=False, indent=2).encode('utf-8')


def steam_libraries():
    roots = []
    try:
        import winreg
        for hive, key, value in ((winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam', 'SteamPath'),
                                 (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\WOW6432Node\Valve\Steam', 'InstallPath')):
            try:
                with winreg.OpenKey(hive, key) as handle:
                    roots.append(Path(winreg.QueryValueEx(handle, value)[0]))
            except OSError:
                pass
    except ImportError:
        pass
    for variable in ('ProgramFiles(x86)', 'ProgramFiles'):
        if os.environ.get(variable):
            roots.append(Path(os.environ[variable]) / 'Steam')
    libraries = list(roots)
    for root in roots:
        try:
            text = (root / 'steamapps/libraryfolders.vdf').read_text(encoding='utf-8-sig')
            libraries.extend(Path(value.replace('\\\\', '\\')) for value in re.findall(r'"path"\s+"([^"\r\n]+)"', text))
        except OSError:
            pass
    return paths.unique(p for p in libraries if p.is_dir())


def is_remnants_jar(path):
    try:
        with zipfile.ZipFile(path) as jar:
            return 'npcfw/data/NPCData.class' in jar.namelist()
    except (OSError, zipfile.BadZipFile):
        return False


def find_installations(userdata):
    games, mods = [], []
    for library in steam_libraries():
        apps = library / 'steamapps'
        try:
            manifest = (apps / 'appmanifest_108600.acf').read_text(encoding='utf-8-sig')
            match = re.search(r'"installdir"\s+"([^"\r\n]+)"', manifest)
            if match and Path(match[1]).name == match[1]:
                candidate = apps / 'common' / match[1]
                if (candidate / 'projectzomboid.jar').is_file():
                    games.append(candidate)
        except OSError:
            pass
        mods.extend((apps / 'workshop/content/108600').glob('*/mods/*/NPCFW.jar'))
    mods.extend((Path(userdata) / 'mods').glob('*/NPCFW.jar'))
    return paths.unique(games), paths.unique(p for p in mods if is_remnants_jar(p))


def game_running():
    # A failed process query is not permission to write a save.
    result = paths.powershell(
        "$ErrorActionPreference='Stop'; [Console]::OutputEncoding=[Text.UTF8Encoding]::new($false); "
        "$p=Get-CimInstance Win32_Process | Where-Object { "
        "$_.Name -match '^ProjectZomboid(32|64)?\\.exe$' -or "
        "($_.Name -match '^javaw?\\.exe$' -and $_.CommandLine -match 'projectzomboid\\.jar|zombie\\.(GameWindow|gameStates|network\\.GameServer)') }; "
        "if($p){[Console]::Write('RUNNING')}else{[Console]::Write('STOPPED')}")
    if result.returncode or result.stdout not in ('RUNNING', 'STOPPED'):
        raise ProfileError('게임 실행 상태를 확인하지 못했습니다. 저장하지 않았습니다.')
    return result.stdout == 'RUNNING'


@contextmanager
def edit_lock(folder):
    import msvcrt
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / 'editor.lock').open('a+b') as stream:
        if stream.tell() == 0:
            stream.write(b'0')
            stream.flush()
        stream.seek(0)
        try:
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            raise ProfileError('다른 설정창에서 저장 중입니다. 잠시 후 다시 시도해주세요.')
        try:
            yield
        finally:
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


class Codec:
    def __init__(self, game, mod):
        self.game, self.mod = Path(game), Path(mod)
        self.java = next((self.game / p for p in ('jre64/bin/java.exe', 'jre/bin/java.exe', 'jre/bin/java')
                          if (self.game / p).is_file()), None)
        if not self.java or not (self.game / 'projectzomboid.jar').is_file() or not is_remnants_jar(self.mod):
            raise ProfileError('게임 설치 폴더와 Remnants의 NPCFW.jar 위치를 확인해주세요.')

    def run(self, data, folder, npc=None, profile=None):
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='read-', dir=folder) as temporary:
            base = Path(temporary)
            source, result, staged = base / 'input.bin', base / 'result.json', base / 'staged.bin'
            source.write_bytes(data)
            command = [str(self.java), '-Xmx512m', '-Dfile.encoding=UTF-8', '-cp', os.pathsep.join((
                str(paths.ROOT / 'profile-helper'), str(self.mod), str(self.game / 'projectzomboid.jar'))),
                'NpcProfileCodec', 'patch' if npc is not None else 'inspect', str(source), str(result)]
            if npc is not None:
                text = base / 'profile.txt'
                text.write_text(profile, encoding='utf-8', newline='')
                command.extend((npc, str(text), str(staged)))
            try:
                process = subprocess.run(command, cwd=base, stdout=subprocess.DEVNULL,
                                         stderr=subprocess.DEVNULL, timeout=60, creationflags=HIDDEN)
                document = json.loads(result.read_text(encoding='utf-8'))
            except (OSError, subprocess.TimeoutExpired, ValueError):
                raise ProfileError('세이브를 읽지 못했습니다. 게임과 Remnants 위치 또는 파일 호환성을 확인해주세요.')
            if process.returncode or 'error' in document:
                if document.get('error') == 'PROFILE_LIMIT':
                    raise ProfileError('프로필이 원본 모드의 글자 수 또는 형식 제한을 넘었습니다. 내용을 줄이고 앞뒤 공백을 확인해주세요.')
                raise ProfileError('현재 설치된 Remnants로 이 세이브의 프로필을 안전하게 읽거나 수정할 수 없습니다. 저장하지 않았습니다.')
            return document, staged.read_bytes() if npc is not None else data


class Profiles:
    def __init__(self, state=None, settings=None, codec_factory=Codec, running=game_running):
        self.state = Path(state) if state else paths.state_dir() / 'npc-settings'
        self.config_file = self.state / 'locations.json'
        self.settings = settings or self.load_settings()
        self.codec_factory, self.running = codec_factory, running
        self.mutex = threading.RLock()

    def load_settings(self):
        try:
            config = json.loads(self.config_file.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            config = {}
        userdata = config.get('userdata') or str(paths.zomboid_dir())
        games, mods = find_installations(userdata)
        for key, candidates in (('game', games), ('mod', mods)):
            if not config.get(key) or not Path(config[key]).exists():
                config[key] = str(candidates[0]) if len(candidates) == 1 else ''
        config['userdata'] = userdata
        config['mod_choices'] = [str(p) for p in mods]
        return config

    def configure(self, data):
        config = {key: str(Path(data.get(key, '')).expanduser().resolve()) for key in ('game', 'mod', 'userdata')}
        self.codec_factory(config['game'], config['mod'])
        if not Path(config['userdata']).is_dir():
            raise ProfileError('사용자 데이터 폴더를 확인해주세요.')
        with self.mutex:
            atomic_file(self.config_file, json_bytes(config))
            self.settings = config
        return config

    def saves(self):
        root = (Path(self.settings['userdata']) / 'Saves').resolve()
        rows = []
        for path in root.glob('*/*/NPCFW_Data.bin'):
            resolved = path.resolve()
            if not resolved.is_relative_to(root) or not path.is_file():
                continue
            rows.append({'id': digest(str(resolved).encode()), 'name': path.parent.name,
                         'mode': path.parent.parent.name, 'modified': path.stat().st_mtime})
        return sorted(rows, key=lambda row: row['modified'], reverse=True)

    def resolve_save(self, identity):
        root = (Path(self.settings['userdata']) / 'Saves').resolve()
        for path in root.glob('*/*/NPCFW_Data.bin'):
            resolved = path.resolve()
            if resolved.is_relative_to(root) and digest(str(resolved).encode()) == identity:
                return resolved
        raise ProfileError('선택한 세이브를 찾을 수 없습니다. 목록을 새로 불러와주세요.')

    @staticmethod
    def read_file(path):
        with path.open('rb') as stream:
            data = stream.read(MAX_SAVE + 1)
        if len(data) > MAX_SAVE:
            raise ProfileError('이 도구에서 읽을 수 있는 세이브 크기를 넘었습니다.')
        return data

    def codec(self):
        return self.codec_factory(self.settings.get('game', ''), self.settings.get('mod', ''))

    def inspect(self, identity):
        with self.mutex:
            path = self.resolve_save(identity)
            original = self.read_file(path)
            result, _ = self.codec().run(original, self.state / 'temporary')
            if self.read_file(path) != original:
                raise ProfileError('읽는 동안 세이브가 변경되었습니다. 다시 불러와주세요.')
            result.update(etag=digest(original), save_id=identity)
            return result

    def save(self, identity, npc, profile, expected):
        if not isinstance(profile, str) or len(profile.encode('utf-8')) > 65535:
            raise ProfileError('프로필이 너무 깁니다.')
        with self.mutex, edit_lock(self.state):
            if self.running():
                raise ProfileError('게임을 저장하고 완전히 종료한 뒤 다시 저장해주세요.')
            path = self.resolve_save(identity)
            original = self.read_file(path)
            if digest(original) != expected:
                raise ProfileError('불러온 뒤 세이브가 변경되었습니다. 기존 내용을 다시 불러와주세요.')
            codec = self.codec()
            proposed, changed = codec.run(original, self.state / 'temporary', npc, profile)
            if not any(row['id'] == npc and row['profile'] == profile for row in proposed['npcs']):
                raise ProfileError('프로필 변경을 확인하지 못했습니다. 저장하지 않았습니다.')
            if self.running() or self.read_file(path) != original:
                raise ProfileError('게임이 실행됐거나 세이브가 변경되었습니다. 저장하지 않았습니다.')
            backup = None
            if changed != original:
                backup = self.state / 'backups' / identity / datetime.now().strftime('%Y%m%d-%H%M%S-%f') / 'NPCFW_Data.bin'
                atomic_file(backup, original)
                if backup.read_bytes() != original:
                    raise ProfileError('이전 내용의 백업을 확인하지 못했습니다. 저장하지 않았습니다.')
                # Recheck immediately before replacement, after backup IO.
                if self.running() or self.read_file(path) != original:
                    raise ProfileError('저장 직전에 세이브가 변경되었습니다. 다시 불러와주세요.')
                atomic_file(path, changed)
            # Success requires parsing bytes read from the actual destination.
            persisted = self.read_file(path)
            if persisted != changed:
                raise ProfileError('저장 후 세이브가 변경되어 확인하지 못했습니다. 이전 내용은 백업에 있습니다.')
            try:
                verified, _ = codec.run(persisted, self.state / 'temporary')
            except (OSError, ValueError):
                detail = '\n이전 내용 백업: ' + str(backup) if backup else ''
                raise ProfileError('파일을 쓴 뒤 프로필 재확인에 실패했습니다. 다시 불러와 확인해주세요.' + detail)
            if self.read_file(path) != persisted or not any(row['id'] == npc and row['profile'] == profile for row in verified['npcs']):
                raise ProfileError('저장 후 프로필이 일치하지 않습니다. 다시 불러와 확인해주세요.')
            verified.update(etag=digest(persisted), save_id=identity)
            return {'verified': True, 'snapshot': verified, 'backup': str(backup) if backup else None}
