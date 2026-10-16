"""Local request adapter. Never opens a game JAR, launcher, or save file."""
import argparse
import base64
import copy
import hmac
import http.client
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
import paths
import dialogue

SERVICE = "npcfw-luna-adapter"
VERSION = "1.1"
PORT = 20140
ROUTE = "/v1/chat/completions"
ENDPOINT = f"http://127.0.0.1:{PORT}{ROUTE}"
MAX_BODY = 2 * 1024 * 1024
PROVIDER = paths.zomboid_dir() / "NPCFW_LLM_PROVIDER.json"
STATE_DIR = paths.state_dir()


def decode(raw):
    doc = json.loads(raw.decode("utf-8-sig"))
    if not isinstance(doc, dict):
        raise ValueError("Expected a JSON object")
    return doc


def encode(doc):
    return (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def atomic_write(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def validate_upstream(doc, allowed_ports=range(20129, 20140)):
    url = urlsplit(doc.get("endpoint", ""))
    if (doc.get("provider") != "openai" or url.scheme != "http"
            or url.hostname not in ("127.0.0.1", "localhost")
            or url.port not in allowed_ports or url.path != ROUTE
            or url.username or url.password or url.query or url.fragment):
        raise ValueError("Only the local Project Remnants Setup bridge is supported")
    token = doc.get("apiKey")
    if not isinstance(token, str) or not 1 <= len(token) <= 512 or "\r" in token or "\n" in token:
        raise ValueError("Missing or invalid local bridge token")
    return url.port


def adapt_request(raw, context_path=None):
    doc = decode(raw)
    model = doc.get("model", "")
    if not isinstance(model, str):
        raise ValueError("Invalid model")
    model = model.lower()
    if model != "gpt-6-luna" and not model.startswith("gpt-6-luna-"):
        return raw, False
    if "max_tokens" in doc:
        limit = doc.pop("max_tokens")
        doc.setdefault("max_completion_tokens", limit)
    doc.setdefault("reasoning_effort", "none")
    if doc["reasoning_effort"] != "none":
        doc.pop("temperature", None)
        doc.pop("top_p", None)
    dialogue.enhance(doc, context_path=context_path)
    return encode(doc), True


class Adapter:
    def __init__(self, provider=PROVIDER, state_dir=STATE_DIR, endpoint=ENDPOINT,
                 allowed_ports=range(20129, 20140)):
        self.provider, self.state_dir, self.endpoint = provider, state_dir, endpoint
        self.state_path = state_dir / "state.json"
        self.allowed_ports = allowed_ports
        self.lock = threading.RLock()
        self.capacity = threading.BoundedSemaphore(4)
        self.active = 0
        self.stopping = False
        self.ready = False
        self.upstream_raw = None
        self.token = secrets.token_hex(32)
        if self.state_path.exists():
            saved = decode(self.state_path.read_bytes())
            if saved.get("service") != SERVICE:
                raise ValueError("Unknown state file")
            self.token = saved["proxy_token"]
            self.upstream_raw = base64.b64decode(saved["upstream_base64"], validate=True)
            validate_upstream(decode(self.upstream_raw), self.allowed_ports)

    def owned(self, doc):
        return doc.get("endpoint") == self.endpoint and doc.get("apiKey") == self.token

    def sync(self):
        with self.lock:
            if self.stopping:
                raise ValueError("Adapter is stopping")
            raw = self.provider.read_bytes()
            doc = decode(raw)
            if self.owned(doc):
                if self.upstream_raw is None:
                    raise ValueError("Original Setup connection is missing")
                self.ready = True
                return
            validate_upstream(doc, self.allowed_ports)
            saved = {"service": SERVICE, "version": VERSION, "proxy_token": self.token,
                     "upstream_base64": base64.b64encode(raw).decode("ascii")}
            atomic_write(self.state_path, encode(saved))
            # Persist recovery information before changing the provider settings.
            if self.provider.read_bytes() != raw:
                raise ValueError("Setup configuration changed; retrying")
            self.upstream_raw = raw
            replacement = copy.deepcopy(doc)
            replacement["endpoint"], replacement["apiKey"] = self.endpoint, self.token
            atomic_write(self.provider, encode(replacement))
            self.ready = True
            logging.info("Setup connection captured; provider routed through adapter")

    def restore(self):
        with self.lock:
            self.stopping = True
            if self.upstream_raw is not None and self.provider.exists():
                raw = self.provider.read_bytes()
                current = decode(raw)
                if self.owned(current):
                    original = decode(self.upstream_raw)
                    expected = dict(original, endpoint=self.endpoint, apiKey=self.token)
                    if current == expected:
                        restored = self.upstream_raw
                    else:
                        current["endpoint"], current["apiKey"] = original["endpoint"], original["apiKey"]
                        restored = encode(current)
                    atomic_write(self.provider, restored)
                    logging.info("Original Setup provider settings restored")

    def upstream(self):
        self.sync()
        with self.lock:
            doc = decode(self.upstream_raw)
            return validate_upstream(doc, self.allowed_ports), doc["apiKey"]


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, adapter):
        self.adapter = adapter
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def setup(self):
        super().setup()
        self.connection.settimeout(30)

    def log_message(self, *_):
        pass  # Never log prompts, headers, or tokens.

    def reply(self, status, doc):
        body = encode(doc)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)
        self.close_connection = True

    def do_GET(self):
        if self.path != "/health":
            return self.reply(404, {"error": "Not found"})
        adapter = self.server.adapter
        return self.reply(200, {"service": SERVICE, "version": VERSION,
                                "pid": os.getpid(), "ready": adapter.ready,
                                "active_requests": adapter.active})

    def do_POST(self):
        adapter = self.server.adapter
        expected = ("Bearer " + adapter.token).encode("utf-8")
        provided = self.headers.get("Authorization", "").encode("utf-8")
        if not hmac.compare_digest(provided, expected):
            return self.reply(401, {"error": "Invalid local adapter token"})
        if self.path == "/stop":
            with adapter.lock:
                if adapter.active:
                    return self.reply(409, {"error": "A request is active; try again after it completes"})
                adapter.stopping = True
            self.reply(200, {"stopping": True})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return
        if self.path != ROUTE:
            return self.reply(404, {"error": "Not found"})
        if self.headers.get("Transfer-Encoding"):
            return self.reply(400, {"error": "Content-Length is required"})
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            size = 0
        if not 0 < size <= MAX_BODY:
            return self.reply(413, {"error": "Invalid request size"})
        if not adapter.capacity.acquire(blocking=False):
            return self.reply(429, {"error": "Adapter is busy"})
        connection, headers_sent = None, False
        with adapter.lock:
            adapter.active += 1
        try:
            raw = self.rfile.read(size)
            if len(raw) != size:
                return self.reply(400, {"error": "Incomplete request"})
            try:
                body, changed = adapt_request(raw, adapter.provider.parent / "Lua" / dialogue.CONTEXT_FILE)
            except (ValueError, UnicodeError):
                return self.reply(400, {"error": "Invalid JSON request"})
            port, token = adapter.upstream()
            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=180)
            connection.request("POST", ROUTE, body, {
                "Authorization": "Bearer " + token,
                "Content-Type": "application/json; charset=utf-8",
                "Accept": "text/event-stream, application/json",
            })
            response = connection.getresponse()
            self.send_response(response.status)
            self.send_header("Content-Type", response.getheader("Content-Type", "application/json"))
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.end_headers()
            headers_sent = True
            self.close_connection = True
            # read1 returns available bytes so SSE tokens are not buffered to EOF.
            while chunk := response.read1(8192):
                self.wfile.write(chunk)
                self.wfile.flush()
            logging.info("Request complete: upstream_status=%s luna_conversion=%s", response.status, changed)
        except (OSError, http.client.HTTPException, ValueError):
            logging.warning("Request failed: check that Setup is configured and running")
            if not headers_sent:
                try:
                    self.reply(502, {"error": "Setup bridge unavailable; run Configure and Start in Setup"})
                except OSError:
                    pass
            else:
                self.close_connection = True
        finally:
            if connection:
                connection.close()
            with adapter.lock:
                adapter.active -= 1
            adapter.capacity.release()


def monitor(adapter, done):
    previous_error = False
    while not done.wait(1):
        try:
            adapter.sync()
            previous_error = False
        except (OSError, ValueError):
            adapter.ready = False
            if not previous_error:
                logging.warning("Provider settings unavailable or unrelated; leaving them untouched")
                previous_error = True


def serve():
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(STATE_DIR / "adapter.log", maxBytes=256000, backupCount=2, encoding="utf-8")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", handlers=[handler])
    adapter = Adapter()
    server = Server(("127.0.0.1", PORT), adapter)  # Bind before changing configuration.
    done = threading.Event()
    try:
        adapter.sync()
        thread = threading.Thread(target=monitor, args=(adapter, done), daemon=True)
        thread.start()
        logging.info("Adapter started on loopback port %s; pid=%s", PORT, os.getpid())
        server.serve_forever(poll_interval=0.2)
    finally:
        done.set()
        adapter.restore()
        server.server_close()
        logging.info("Adapter stopped")


def control(path="/health", token=None):
    connection = http.client.HTTPConnection("127.0.0.1", PORT, timeout=2)
    try:
        headers = {"Authorization": "Bearer " + token} if token else {}
        connection.request("POST" if token else "GET", path, body=b"", headers=headers)
        response = connection.getresponse()
        result = decode(response.read())
        if response.status != 200:
            raise ValueError(result.get("error", "Adapter error"))
        if not token and result.get("service") != SERVICE:
            raise ValueError("Port is in use by another service")
        return result
    finally:
        connection.close()


def start():
    try:
        return control()
    except OSError:
        pass
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    executable = pythonw if pythonw.exists() else Path(sys.executable)
    with (STATE_DIR / "bootstrap.log").open("ab") as log:
        child = subprocess.Popen([str(executable), str(Path(__file__).resolve()), "serve"],
                                 stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                 creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                                 close_fds=True)
    for _ in range(60):
        time.sleep(0.2)
        if child.poll() is not None:
            raise ValueError("Adapter could not start; see the local bootstrap.log")
        try:
            status = control()
            if status["ready"]:
                return status
        except OSError:
            pass
    raise ValueError("Adapter startup timed out; see the local logs")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("start", "stop", "status", "serve"))
    args = parser.parse_args()
    try:
        if args.command == "serve":
            serve()
        elif args.command == "start":
            print(json.dumps(start()))
        elif args.command == "status":
            print(json.dumps(control()))
        else:
            saved = decode((STATE_DIR / "state.json").read_bytes())
            try:
                print(json.dumps(control("/stop", saved["proxy_token"])))
            except ConnectionRefusedError:
                # Recovery after a crashed adapter; do not stop any unrelated process.
                Adapter().restore()
                print("Adapter is not running; original provider settings restored if still owned.")
    except (OSError, ValueError, KeyError) as error:
        print("Adapter error: " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
