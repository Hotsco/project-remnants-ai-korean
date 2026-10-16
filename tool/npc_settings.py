"""Local, authenticated NPC settings window. No AI requests are made here."""
import argparse
import hmac
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import threading
import time
import webbrowser

import paths
from npc_profiles import Profiles, ProfileError, atomic_file, json_bytes, HIDDEN

SERVICE = 'remnants-npc-settings'
VERSION = '1'
ASSETS = {'/': ('npc-settings.html', 'text/html'), '/npc-settings.js': ('npc-settings.js', 'text/javascript'),
          '/npc-settings.css': ('npc-settings.css', 'text/css')}


def choose_location(kind):
    if kind not in ('game', 'mod', 'userdata'):
        raise ProfileError('잘못된 위치 선택입니다.')
    if kind != 'mod':
        return str(paths.pick_path('게임 설치 폴더' if kind == 'game' else 'Zomboid 사용자 데이터 폴더', directory=True))
    result = paths.powershell(
        "[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false); Add-Type -AssemblyName System.Windows.Forms; "
        "$d=New-Object System.Windows.Forms.OpenFileDialog; $d.Title='Remnants NPCFW.jar'; "
        "$d.Filter='Remnants|NPCFW.jar'; if($d.ShowDialog() -eq 'OK'){[Console]::Write($d.FileName)}")
    if result.returncode or not result.stdout.strip():
        raise ProfileError('위치 선택을 취소했습니다.')
    return result.stdout.strip()


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, profiles, token):
        super().__init__(('127.0.0.1', 0), Handler)
        self.profiles, self.token = profiles, token
        self.origin = f'http://127.0.0.1:{self.server_port}'

    def status(self):
        try:
            return {'running': self.profiles.running(), 'error': ''}
        except (OSError, ValueError) as error:
            return {'running': None, 'error': str(error)}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def reply(self, status, data, content_type='application/json'):
        body = data if isinstance(data, bytes) else json_bytes(data)
        self.send_response(status)
        self.send_header('Content-Type', content_type + '; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def authorized(self):
        origin = self.headers.get('Origin')
        valid = self.headers.get('Host') == f'127.0.0.1:{self.server.server_port}'
        valid = valid and (origin is None or origin == self.server.origin)
        supplied = self.headers.get('X-NPC-Token', '').encode()
        valid = valid and hmac.compare_digest(supplied, self.server.token.encode())
        if not valid:
            self.reply(403, {'error': '설정창 연결을 확인할 수 없습니다. 실행 파일로 다시 열어주세요.'})
        return valid

    def do_GET(self):
        if self.path in ASSETS:
            if self.headers.get('Host') != f'127.0.0.1:{self.server.server_port}':
                return self.reply(403, {'error': 'Invalid host'})
            name, content_type = ASSETS[self.path]
            return self.reply(200, (paths.ROOT / name).read_bytes(), content_type)
        if not self.authorized():
            return
        try:
            if self.path == '/api/health':
                result = {'service': SERVICE, 'version': VERSION, 'root': str(paths.ROOT)}
            elif self.path == '/api/status':
                result = self.server.status()
            elif self.path == '/api/bootstrap':
                app = self.server.profiles
                result = {'settings': app.settings, 'saves': app.saves(), 'status': self.server.status()}
            else:
                return self.reply(404, {'error': 'Not found'})
            return self.reply(200, result)
        except (OSError, ValueError) as error:
            self.reply(400, {'error': str(error)})

    def do_POST(self):
        if not self.authorized():
            return
        if self.headers.get('Content-Type') != 'application/json' or self.headers.get('Transfer-Encoding'):
            return self.reply(400, {'error': 'Invalid request'})
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 262144:
                raise ProfileError('요청 크기를 확인해주세요.')
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict):
                raise ProfileError('요청 형식을 확인해주세요.')
            app = self.server.profiles
            if self.path == '/api/load':
                result = app.inspect(data['save'])
            elif self.path == '/api/save':
                result = app.save(data['save'], data['npc'], data['profile'], data['etag'])
            elif self.path == '/api/configure':
                result = app.configure(data)
            elif self.path == '/api/choose':
                result = {'path': choose_location(data['kind'])}
            elif self.path == '/api/quit':
                self.reply(200, {'closed': True})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            else:
                return self.reply(404, {'error': 'Not found'})
            self.reply(200, result)
        except (OSError, ValueError, KeyError, TypeError) as error:
            self.reply(400, {'error': str(error) if isinstance(error, (ProfileError, OSError)) else '요청 내용을 확인해주세요.'})


def control(info, endpoint='/api/health', data=None):
    connection = http.client.HTTPConnection('127.0.0.1', int(info['port']), timeout=3)
    try:
        headers = {'X-NPC-Token': info['token']}
        if data is not None:
            headers['Content-Type'] = 'application/json'
        connection.request('POST' if data is not None else 'GET', endpoint,
                           body=json_bytes(data) if data is not None else None, headers=headers)
        response = connection.getresponse()
        result = json.loads(response.read())
        if response.status != 200 or (endpoint == '/api/health' and result.get('service') != SERVICE):
            raise ValueError('Settings service is unavailable')
        return result
    finally:
        connection.close()


def start(state, open_window=True):
    record = state / 'window.json'
    try:
        info = json.loads(record.read_text(encoding='utf-8'))
        health = control(info)
        if health.get('version') != VERSION or health.get('root') != str(paths.ROOT):
            raise ValueError('Different package')
    except (OSError, ValueError, KeyError, TypeError):
        state.mkdir(parents=True, exist_ok=True)
        pythonw = Path(sys.executable).with_name('pythonw.exe')
        command = [str(pythonw if pythonw.exists() else Path(sys.executable)), str(Path(__file__).resolve()),
                   'serve', '--state-dir', str(state)]
        child = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, creationflags=HIDDEN)
        for _ in range(100):
            if child.poll() is not None:
                raise ProfileError('설정창을 시작하지 못했습니다. 도구 폴더 전체를 다시 확인해주세요.')
            time.sleep(.1)
            try:
                info = json.loads(record.read_text(encoding='utf-8'))
                if info.get('pid') == child.pid and control(info).get('root') == str(paths.ROOT):
                    break
            except (OSError, ValueError, KeyError):
                continue
        else:
            raise ProfileError('설정창 준비 시간이 초과되었습니다.')
    if open_window:
        webbrowser.open(f"http://127.0.0.1:{info['port']}/#{info['token']}", new=1)
    return info


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('start', 'serve', 'stop'), nargs='?', default='start')
    parser.add_argument('--state-dir', type=Path)
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    state = args.state_dir or paths.state_dir() / 'npc-settings'
    if args.command == 'serve':
        app = Profiles(state=state)
        server = Server(app, secrets.token_urlsafe(32))
        info = {'port': server.server_port, 'token': server.token, 'pid': os.getpid()}
        atomic_file(state / 'window.json', json_bytes(info))
        try:
            server.serve_forever(poll_interval=.2)
        finally:
            server.server_close()
    elif args.command == 'stop':
        control(json.loads((state / 'window.json').read_text(encoding='utf-8')), '/api/quit', {})
    else:
        start(state, not args.no_browser)
        if sys.stdout:
            print('NPC settings window is ready.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError) as error:
        if sys.stderr:
            print(str(error), file=sys.stderr)
        raise SystemExit(1)
