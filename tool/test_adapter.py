import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest
import time

import adapter as a
import model_compat


class ConversionTests(unittest.TestCase):
    def test_luna_preserves_korean_messages_and_schema(self):
        request = {"model": "gpt-6-luna", "max_tokens": 512,
                   "messages": [{"role": "user", "content": "안녕, 테스트동료."}],
                   "stream": True, "temperature": 0.7, "top_p": 0.9,
                   "response_format": {"type": "json_schema", "json_schema": {"name": "test"}}}
        raw, changed = a.adapt_request(a.encode(request))
        result = a.decode(raw)
        self.assertTrue(changed)
        self.assertEqual(result.pop("max_completion_tokens"), request.pop("max_tokens"))
        self.assertEqual(result.pop("reasoning_effort"), "none")
        self.assertEqual(result, request)

    def test_existing_budget_and_reasoning_are_respected(self):
        raw, _ = a.adapt_request(a.encode({"model": "gpt-6-luna-2026-10-01", "max_tokens": 3,
                                           "max_completion_tokens": 20, "reasoning_effort": "low",
                                           "temperature": 1, "top_p": 0.9}))
        self.assertEqual(a.decode(raw), {"model": "gpt-6-luna-2026-10-01",
                                        "max_completion_tokens": 20, "reasoning_effort": "low"})

    def test_other_models_are_byte_identical(self):
        raw = b'{ "model": "another-model", "max_tokens": 50 }'
        self.assertEqual(a.adapt_request(raw), (raw, False))

    def test_sol_budget_and_explicit_reasoning(self):
        for model in ("gpt-6-sol", "gpt-6-sol-2026-10-01", "openai/gpt-6-sol"):
            for effort in ("none", "low", "high"):
                with self.subTest(model=model, effort=effort):
                    raw, _ = a.adapt_request(a.encode({"model": model, "max_tokens": 512,
                        "reasoning_effort": effort, "temperature": 0.7, "top_p": 0.9}))
                    result = a.decode(raw)
                    self.assertEqual(result["max_completion_tokens"], 512)
                    self.assertEqual(result["reasoning_effort"], effort)
                    self.assertEqual(result["model"], model)
                    self.assertEqual("temperature" in result, effort == "none")

    def test_newer_sol_does_not_inherit_luna_reasoning_default(self):
        raw, _ = a.adapt_request(a.encode({"model": "gpt-6.1-sol", "max_tokens": 512,
                                          "temperature": 0.7}))
        result = a.decode(raw)
        self.assertEqual(result["reasoning_effort"], "low")
        self.assertEqual(result["max_completion_tokens"], 512)
        self.assertNotIn("temperature", result)

    def test_claude_and_gemini_do_not_receive_openai_specific_parameters(self):
        for model in ("claude-sonnet-4-6", "anthropic/claude-sonnet-4.6", "gemini-3.8-flash"):
            with self.subTest(model=model):
                raw, _ = a.adapt_request(a.encode({"model": model, "max_tokens": 512,
                    "temperature": 0.7, "top_p": 0.9}))
                result = a.decode(raw)
                self.assertEqual(result["max_tokens"], 512)
                self.assertNotIn("max_completion_tokens", result)
                self.assertNotIn("reasoning_effort", result)
                self.assertEqual("temperature" in result, model.startswith("gemini"))

    def test_custom_model_rules_work_without_code_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "rules.json"
            path.write_text(json.dumps({"schema": 1, "rules": [{"match": ["my-deployment"],
                "token_parameter": "max_completion_tokens", "default_reasoning": "low",
                "drop_sampling_with_reasoning": True}]}), encoding="utf-8")
            raw = a.encode({"model": "my-deployment", "max_tokens": 512, "temperature": 0.7})
            result = a.decode(a.adapt_request(raw, rules_path=path)[0])
            self.assertEqual(result, {"model": "my-deployment", "max_completion_tokens": 512,
                                      "reasoning_effort": "low"})
            path.write_text('{"schema":1,"rules":[]}', encoding="utf-8")
            self.assertEqual(a.adapt_request(raw, rules_path=path), (raw, False))

    def test_bad_rules_never_apply_partial_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "rules.json"
            for value in ("{", '{"schema":2,"rules":[]}',
                          '{"schema":1,"rules":[{"match":["*"],"drop_parameters":["messages"]}]}'):
                path.write_text(value, encoding="utf-8")
                doc = {"model": "gpt-6-sol", "max_tokens": 512}
                self.assertFalse(model_compat.adapt_parameters(doc, path))
                self.assertEqual(doc, {"model": "gpt-6-sol", "max_tokens": 512})

    def test_remote_upstreams_are_rejected(self):
        for endpoint in ("https://example.com/v1/chat/completions", "http://127.0.0.1:20140/v1/chat/completions",
                         "http://127.0.0.1:20129/other", "http://x@127.0.0.1:20129/v1/chat/completions"):
            with self.assertRaises(ValueError):
                a.validate_upstream({"provider": "openai", "endpoint": endpoint, "apiKey": "test"})


class MockBridge(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_POST(self):
        server = self.server
        server.calls += 1
        server.received = a.decode(self.rfile.read(int(self.headers["Content-Length"])))
        server.authorization = self.headers.get("Authorization")
        status = server.response_status
        self.send_response(status)
        self.send_header("Content-Type", "text/event-stream" if status == 200 else "application/json")
        self.end_headers()
        if status != 200:
            self.wfile.write(b'{"error":{"message":"mock error"}}')
            return
        first = 'data: {"choices":[{"delta":{"content":"안녕"}}]}\n\n'.encode()
        self.wfile.write(first)
        self.wfile.flush()
        if server.pause_stream:
            server.release.wait(3)
        self.wfile.write(b'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n')


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.bridge = ThreadingHTTPServer(("127.0.0.1", 0), MockBridge)
        self.bridge.calls = 0
        self.bridge.response_status = 200
        self.bridge.pause_stream = False
        self.bridge.release = threading.Event()
        self.port = self.bridge.server_port
        self.original = a.encode({"provider": "openai", "model": "gpt-6-luna",
                                  "endpoint": f"http://127.0.0.1:{self.port}{a.ROUTE}", "apiKey": "setup-token"})
        self.provider = self.root / "provider.json"
        self.provider.write_bytes(self.original)
        self.adapter = a.Adapter(self.provider, self.root / "state", allowed_ports=[self.port])
        self.server = a.Server(("127.0.0.1", 0), self.adapter)
        self.adapter.endpoint = f"http://127.0.0.1:{self.server.server_port}{a.ROUTE}"
        self.adapter.sync()
        self.threads = []
        for server in (self.bridge, self.server):
            thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
            thread.start()
            self.threads.append(thread)

    def tearDown(self):
        self.bridge.release.set()
        self.server.shutdown()
        self.bridge.shutdown()
        self.server.server_close()
        self.bridge.server_close()
        for thread in self.threads:
            thread.join(3)
        self.temp.cleanup()

    def request(self, token=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=2)
        body = a.encode({"model": "gpt-6-luna", "max_tokens": 512, "stream": True,
                         "messages": [{"role": "user", "content": "안녕"}]})
        connection.request("POST", a.ROUTE, body, {"Authorization": "Bearer " + (token or self.adapter.token),
                                                   "Content-Type": "application/json"})
        return connection, connection.getresponse()

    def test_stream_is_delivered_before_upstream_finishes(self):
        self.bridge.pause_stream = True
        conn, response = self.request()
        self.assertEqual(response.status, 200)
        first = response.readline()
        self.assertIn("안녕".encode(), first)
        self.assertFalse(self.bridge.release.is_set())
        self.bridge.release.set()
        self.assertIn(b"[DONE]", response.read())
        conn.close()
        self.assertEqual(self.bridge.authorization, "Bearer setup-token")
        self.assertNotIn("max_tokens", self.bridge.received)
        self.assertEqual(self.bridge.received["max_completion_tokens"], 512)

    def test_unauthorized_request_never_reaches_bridge(self):
        conn, response = self.request("wrong-token")
        self.assertEqual(response.status, 401)
        response.read()
        conn.close()
        self.assertEqual(self.bridge.calls, 0)

    def test_dialogue_supplement_reaches_bridge_for_all_models_with_matching_game_context(self):
        from test_dialogue import request, record
        stamp = int(time.time()*1000)
        (self.root / "Lua").mkdir()
        (self.root / "Lua/NPCFW_LunaContext.json").write_bytes(a.encode({"schema": 1, "records": [
            record(captured_ms=stamp, session=str(stamp))]}))
        (self.root / "console.txt").write_text(
            f"LOG : Lua f:1> [NPCFW Luna Context] session {stamp}\n"
            "LOG : General f:2> chopper: activated\n", encoding="utf-8")
        models = ("gpt-6-luna", "gpt-6-sol", "gpt-6.1-sol", "claude-sonnet-4-6",
                  "gemini-3.8-flash", "another-model")
        for model in models:
            with self.subTest(model=model):
                doc = request()
                doc.update(model=model, stream=True)
                conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=2)
                conn.request("POST", a.ROUTE, a.encode(doc), {"Authorization": "Bearer "+self.adapter.token})
                response = conn.getresponse()
                self.assertEqual(response.status, 200)
                self.assertIn(b"[DONE]", response.read())
                conn.close()
                forwarded = self.bridge.received
                self.assertIn("event active: true", forwarded["messages"][0]["content"])
                self.assertEqual(forwarded["messages"][-1], doc["messages"][-1])
                self.assertEqual(forwarded["model"], model)
        self.assertEqual(self.bridge.calls, len(models))

    def test_upstream_error_is_preserved(self):
        self.bridge.response_status = 400
        conn, response = self.request()
        self.assertEqual(response.status, 400)
        self.assertEqual(json.loads(response.read()), {"error": {"message": "mock error"}})
        conn.close()

    def test_setup_rotation_and_exact_restore(self):
        new = a.decode(self.original)
        new["apiKey"] = "rotated-setup-token"
        replacement = a.encode(new)
        old_adapter_token = self.adapter.token
        self.provider.write_bytes(replacement)
        self.adapter.sync()
        self.assertEqual(self.adapter.token, old_adapter_token)
        self.assertEqual(self.adapter.upstream()[1], "rotated-setup-token")
        self.adapter.restore()
        self.assertEqual(self.provider.read_bytes(), replacement)

    def test_restart_recovery_uses_saved_upstream_not_itself(self):
        recovered = a.Adapter(self.provider, self.root / "state", self.adapter.endpoint, [self.port])
        recovered.sync()
        self.assertEqual(recovered.upstream(), (self.port, "setup-token"))
        self.assertEqual(recovered.token, self.adapter.token)
        recovered.restore()
        self.assertEqual(self.provider.read_bytes(), self.original)

    def test_unrelated_provider_change_is_not_overwritten(self):
        foreign = a.encode({"provider": "ollama", "endpoint": "http://127.0.0.1:11434"})
        self.provider.write_bytes(foreign)
        with self.assertRaises(ValueError):
            self.adapter.sync()
        self.adapter.restore()
        self.assertEqual(self.provider.read_bytes(), foreign)


if __name__ == "__main__":
    unittest.main()
