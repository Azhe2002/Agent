from __future__ import annotations

import json
import sys
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


BRANCH_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BRANCH_DIR))

from web.server import create_server


MODELS = {
    "deepseek": "deepseek-v4-flash",
    "mimo": "mimo-v2.5",
    "kimi": "kimi-k2.6",
    "nvidia": "openai/gpt-oss-20b",
}


def fake_runner(query: str, provider: str) -> dict[str, object]:
    return {
        "ok": True,
        "answer": f"测试回答：{len(query)} 个字符",
        "summary": {
            "completed": True,
            "steps": 2,
            "model_calls": 2,
            "tool_calls": 1,
            "cache_hits": 0,
            "elapsed_ms": 15,
            "usage": {"total_tokens": 20},
            "provider": provider,
            "model": MODELS[provider],
        },
    }


def fake_provider_loader() -> dict[str, object]:
    return {
        "ok": True,
        "default_provider": "deepseek",
        "providers": [
            {"id": "deepseek", "label": "DeepSeek", "model": MODELS["deepseek"], "available": True},
            {"id": "mimo", "label": "MiMo", "model": MODELS["mimo"], "available": True},
            {"id": "kimi", "label": "Kimi", "model": MODELS["kimi"], "available": True},
            {"id": "nvidia", "label": "NVIDIA", "model": MODELS["nvidia"], "available": True},
        ],
    }


class WebServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runs: list[tuple[str, str]] = []

        def recording_runner(query: str, provider: str) -> dict[str, object]:
            self.runs.append((query, provider))
            return fake_runner(query, provider)

        self.server = create_server(
            port=0,
            runner=recording_runner,
            provider_loader=fake_provider_loader,
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def test_home_serves_page_with_security_headers(self) -> None:
        with urlopen(f"{self.base_url}/", timeout=2) as response:
            body = response.read().decode("utf-8")
            self.assertEqual(response.status, 200)
            self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
            self.assertIn("default-src 'self'", response.headers["Content-Security-Policy"])
        self.assertIn("美食小助手", body)
        self.assertIn('id="chat-form"', body)

    def test_chat_returns_answer_and_redacted_summary(self) -> None:
        request = Request(
            f"{self.base_url}/api/chat",
            data=json.dumps({"message": "番茄鸡蛋，二十分钟"}).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urlopen(request, timeout=2) as response:
            payload = json.load(response)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["summary"]["tool_calls"], 1)
        self.assertEqual(payload["summary"]["provider"], "deepseek")
        self.assertEqual(payload["summary"]["model"], "deepseek-v4-flash")
        self.assertNotIn("messages", payload)
        self.assertNotIn("api_key", json.dumps(payload))

    def test_providers_endpoint_lists_configured_choices(self) -> None:
        with urlopen(f"{self.base_url}/api/providers", timeout=2) as response:
            payload = json.load(response)
        self.assertEqual(payload["default_provider"], "deepseek")
        self.assertEqual(
            [provider["id"] for provider in payload["providers"]],
            ["deepseek", "mimo", "kimi", "nvidia"],
        )

    def test_chat_uses_selected_provider_and_model(self) -> None:
        request = Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(
                {
                    "message": "想吃清淡午餐",
                    "provider": "kimi",
                }
            ).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urlopen(request, timeout=2) as response:
            payload = json.load(response)
        self.assertEqual(payload["summary"]["provider"], "kimi")
        self.assertEqual(payload["summary"]["model"], "kimi-k2.6")
        self.assertEqual(self.runs, [("想吃清淡午餐", "kimi")])

    def test_chat_uses_nvidia_as_fourth_provider(self) -> None:
        request = Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(
                {
                    "message": "想吃快手午餐",
                    "provider": "nvidia",
                }
            ).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urlopen(request, timeout=2) as response:
            payload = json.load(response)
        self.assertEqual(payload["summary"]["provider"], "nvidia")
        self.assertEqual(payload["summary"]["model"], "openai/gpt-oss-20b")
        self.assertEqual(self.runs, [("想吃快手午餐", "nvidia")])

    def test_chat_rejects_provider_outside_allowlist(self) -> None:
        request = Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(
                {"message": "测试", "provider": "untrusted-provider"}
            ).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with self.assertRaises(HTTPError) as captured:
            urlopen(request, timeout=2)
        self.assertEqual(captured.exception.code, 400)
        self.assertEqual(self.runs, [])

    def test_chat_rejects_empty_message_before_runner(self) -> None:
        request = Request(
            f"{self.base_url}/api/chat",
            data=b'{"message":"   "}',
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with self.assertRaises(HTTPError) as captured:
            urlopen(request, timeout=2)
        self.assertEqual(captured.exception.code, 400)
        payload = json.loads(captured.exception.read())
        self.assertEqual(payload["error"]["type"], "invalid_request")

    def test_chat_rejects_non_json_content_type(self) -> None:
        request = Request(
            f"{self.base_url}/api/chat",
            data=b"message=test",
            method="POST",
            headers={"Content-Type": "text/plain"},
        )
        with self.assertRaises(HTTPError) as captured:
            urlopen(request, timeout=2)
        self.assertEqual(captured.exception.code, 415)

    def test_chat_rejects_message_over_agent_limit(self) -> None:
        request = Request(
            f"{self.base_url}/api/chat",
            data=json.dumps({"message": "x" * 2_001}).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with self.assertRaises(HTTPError) as captured:
            urlopen(request, timeout=2)
        self.assertEqual(captured.exception.code, 413)


if __name__ == "__main__":
    unittest.main()
