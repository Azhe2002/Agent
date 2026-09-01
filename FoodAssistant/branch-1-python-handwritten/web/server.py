"""Local-only web adapter for the handwritten Food Assistant Agent."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import BoundedSemaphore
from typing import Any
from urllib.parse import urlsplit


WEB_DIR = Path(__file__).resolve().parent
BRANCH_DIR = WEB_DIR.parent
if str(BRANCH_DIR) not in sys.path:
    sys.path.insert(0, str(BRANCH_DIR))

from agent import AgentError, HandwrittenAgent
from config import ConfigurationError, load_settings
from model_client import OpenAICompatibleChatClient
from tools import DatasetError, RecipeRepository, ToolRegistry


MAX_REQUEST_BYTES = 8_192
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
}
WEB_PROVIDERS = (
    {"id": "deepseek", "label": "DeepSeek", "model": "deepseek-v4-flash"},
    {"id": "mimo", "label": "MiMo", "model": "mimo-v2.5"},
    {"id": "kimi", "label": "Kimi", "model": "kimi-k2.6"},
    {"id": "nvidia", "label": "NVIDIA", "model": "openai/gpt-oss-20b"},
)


def load_provider_options() -> dict[str, Any]:
    """Return configured providers without exposing credentials or endpoints."""

    providers = []
    for item in WEB_PROVIDERS:
        provider_id = item["id"]
        try:
            settings = load_settings(
                provider_override=provider_id,
                model_override=item["model"],
            )
        except ConfigurationError:
            available = False
            model = item["model"]
        else:
            available = True
            model = settings.model
        providers.append(
            {
                "id": provider_id,
                "label": item["label"],
                "model": model,
                "available": available,
            }
        )
    default_provider = next(
        (item["id"] for item in providers if item["available"]),
        WEB_PROVIDERS[0]["id"],
    )
    return {
        "ok": True,
        "default_provider": default_provider,
        "providers": providers,
    }


def run_agent(query: str, provider: str) -> dict[str, Any]:
    """Execute one isolated Agent run and return a browser-safe payload."""

    if provider not in {item["id"] for item in WEB_PROVIDERS}:
        raise AgentError("invalid_request", "所选模型供应商不在白名单中")
    selected = next(item for item in WEB_PROVIDERS if item["id"] == provider)
    settings = load_settings(
        provider_override=provider,
        model_override=selected["model"],
    )
    repository = RecipeRepository()
    tools = ToolRegistry(repository)
    client = OpenAICompatibleChatClient(settings)
    agent = HandwrittenAgent(
        client,
        tools,
        max_steps=settings.max_agent_steps,
        verbose=False,
    )
    result = agent.run(query)
    return {
        "ok": True,
        "answer": result.final_answer,
        "summary": {
            "completed": result.completed,
            "steps": result.steps,
            "model_calls": result.model_calls,
            "tool_calls": result.tool_calls,
            "cache_hits": result.cache_hits,
            "elapsed_ms": result.elapsed_ms,
            "usage": result.usage,
            "provider": settings.provider,
            "model": settings.model,
        },
    }


class FoodAssistantHTTPServer(ThreadingHTTPServer):
    """HTTP server carrying the injectable Agent runner used by the handler."""

    daemon_threads = True

    def __init__(
        self,
        server_address: tuple[str, int],
        runner: Callable[[str, str], dict[str, Any]],
        provider_loader: Callable[[], dict[str, Any]],
    ) -> None:
        super().__init__(server_address, FoodAssistantHandler)
        self.runner = runner
        self.provider_loader = provider_loader
        self.agent_slots = BoundedSemaphore(value=2)


class FoodAssistantHandler(BaseHTTPRequestHandler):
    server: FoodAssistantHTTPServer

    def _send_headers(
        self,
        status: int,
        content_type: str,
        content_length: int,
        *,
        cache_control: str = "no-store",
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(content_length))
        self.send_header("Cache-Control", cache_control)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; base-uri 'none'; "
            "form-action 'self'; frame-ancestors 'none'",
        )
        self.end_headers()

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
        self._send_headers(status, "application/json; charset=utf-8", len(body))
        self.wfile.write(body)

    def _send_error(self, status: int, error_type: str, message: str) -> None:
        self._send_json(
            status,
            {"ok": False, "error": {"type": error_type, "message": message}},
        )

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        path = urlsplit(self.path).path
        if path == "/api/providers":
            try:
                payload = self.server.provider_loader()
            except Exception:
                self._send_error(500, "internal_error", "供应商列表暂时不可用")
            else:
                self._send_json(200, payload)
            return

        static_file = STATIC_FILES.get(path)
        if static_file is None:
            self._send_error(404, "not_found", "页面不存在")
            return

        filename, content_type = static_file
        try:
            body = (WEB_DIR / filename).read_bytes()
        except OSError:
            self._send_error(500, "internal_error", "页面资源暂时不可用")
            return
        self._send_headers(
            200,
            content_type,
            len(body),
            cache_control="no-cache",
        )
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if urlsplit(self.path).path != "/api/chat":
            self._send_error(404, "not_found", "接口不存在")
            return

        content_type = self.headers.get_content_type()
        if content_type != "application/json":
            self._send_error(415, "invalid_request", "请求必须使用 JSON")
            return

        raw_length = self.headers.get("Content-Length")
        try:
            content_length = int(raw_length or "")
        except ValueError:
            self._send_error(400, "invalid_request", "请求长度无效")
            return
        if content_length <= 0:
            self._send_error(400, "invalid_request", "请求不能为空")
            return
        if content_length > MAX_REQUEST_BYTES:
            self._send_error(413, "invalid_request", "请求内容过长")
            return

        try:
            payload = json.loads(self.rfile.read(content_length))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_error(400, "invalid_request", "JSON 格式无效")
            return
        if not isinstance(payload, dict) or not isinstance(payload.get("message"), str):
            self._send_error(400, "invalid_request", "message 必须是字符串")
            return

        message = payload["message"].strip()
        if not message:
            self._send_error(400, "invalid_request", "请先描述午餐需求")
            return
        if len(message) > 2_000:
            self._send_error(413, "invalid_request", "需求不能超过 2000 个字符")
            return

        try:
            provider_catalog = self.server.provider_loader()
        except Exception:
            self._send_error(500, "internal_error", "供应商列表暂时不可用")
            return
        raw_provider = payload.get(
            "provider",
            provider_catalog.get("default_provider"),
        )
        if not isinstance(raw_provider, str):
            self._send_error(400, "invalid_request", "provider 必须是字符串")
            return
        known_providers = {
            item.get("id")
            for item in provider_catalog.get("providers", [])
            if isinstance(item, dict)
            and isinstance(item.get("id"), str)
        }
        if raw_provider not in known_providers:
            self._send_error(400, "invalid_request", "所选模型供应商不在白名单中")
            return
        available_providers = {
            item.get("id")
            for item in provider_catalog.get("providers", [])
            if isinstance(item, dict)
            and item.get("available") is True
            and isinstance(item.get("id"), str)
        }
        if raw_provider not in available_providers:
            self._send_error(503, "configuration_error", "所选模型尚未完成本地配置")
            return

        if not self.server.agent_slots.acquire(blocking=False):
            self._send_error(429, "busy", "当前已有测试在运行，请稍后再试")
            return
        try:
            response = self.server.runner(message, raw_provider)
        except ConfigurationError as exc:
            self._send_error(503, "configuration_error", str(exc))
        except DatasetError:
            self._send_error(500, "internal_error", "菜谱数据暂时不可用")
        except AgentError as exc:
            status = 400 if exc.error_type == "invalid_request" else 502
            self._send_error(status, exc.error_type, str(exc))
        except Exception:
            self._send_error(500, "internal_error", "服务运行失败，请查看终端日志")
        else:
            self._send_json(200, response)
        finally:
            self.server.agent_slots.release()

    def log_message(self, format: str, *args: object) -> None:
        # The standard log line contains method/path/status only; request bodies and
        # model payloads are intentionally never logged.
        super().log_message(format, *args)


def create_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    *,
    runner: Callable[[str, str], dict[str, Any]] = run_agent,
    provider_loader: Callable[[], dict[str, Any]] = load_provider_options,
) -> FoodAssistantHTTPServer:
    if host not in {"127.0.0.1", "localhost"}:
        raise ValueError("The quick-test server may only bind to localhost")
    if not 0 <= port <= 65_535:
        raise ValueError("port must be between 0 and 65535")
    return FoodAssistantHTTPServer((host, port), runner, provider_loader)


def main() -> int:
    parser = argparse.ArgumentParser(description="美食小助手本地 Web 快速测试页")
    parser.add_argument("--port", type=int, default=8000, help="本地监听端口")
    args = parser.parse_args()
    server = create_server(port=args.port)
    print(f"美食小助手 Web 已启动：http://127.0.0.1:{server.server_port}")
    print("按 Ctrl+C 停止；页面不会保存输入或回答。")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务已停止。")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
