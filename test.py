"""Safely verify NVIDIA's OpenAI-compatible chat-completions API.

The script never prints the API key, request headers, response body, or model
reply. Local development should use NVIDIA_API_KEY_FILE so the credential stays
inside the ignored APIKEY directory.

中文说明：这是一个"安全连通性探测"脚本——只验证 NVIDIA 的 OpenAI 兼容
API 是否可用，不打印任何密钥 / 请求头 / 响应体 / 模型回复。
"""

from __future__ import annotations

# ---- 标准库导入：故意不使用第三方库（如 openai / requests），
#      用 urllib 直接发 HTTP 请求，减少依赖面、便于在任何环境跑。 ----
import argparse  # 命令行参数解析（--config / --model）
import json      # 构造请求体、解析响应 JSON、输出结果
import os        # 读取进程环境变量
import re        # 校验变量名 / 模型名 / key 格式
import sys       # 退出码
import time      # 计时（统计请求耗时）
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn
from urllib.error import HTTPError, URLError  # HTTP/网络错误类型
from urllib.parse import urlparse             # 校验 base_url
from urllib.request import Request, urlopen   # 发起 HTTP 请求


# ---- 路径与默认值常量 ----
REPO_ROOT = Path(__file__).resolve().parent        # 仓库根目录（本文件所在目录）
DEFAULT_CONFIG = REPO_ROOT / "FoodAssistant" / ".env"  # 默认配置文件位置
APIKEY_ROOT = (REPO_ROOT / "APIKEY").resolve()    # 存放密钥文件的白名单目录
# 允许读取的密钥文件必须精确等于这个路径（安全白名单，防止读到任意文件）
ALLOWED_NVIDIA_KEY_FILE = (APIKEY_ROOT / "nvidia-api-key.md").resolve()
DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"  # NVIDIA OpenAI 兼容端点
DEFAULT_MODEL = "openai/gpt-oss-20b"  # 默认探测用模型
DEFAULT_TIMEOUT_SECONDS = 45.0        # 默认请求超时（秒）
MAX_TIMEOUT_SECONDS = 120.0           # 超时上限，防止配置写错


class ConfigurationError(ValueError):
    """A safe-to-report configuration error without secret material.

    配置错误类型：消息里只含安全信息，绝不含密钥内容。
    单独定义以便在顶层统一捕获并给出友好报错。
    """


@dataclass(frozen=True)
class EnvValue:
    """从配置文件解析出的一个变量值，附带其所在的基准目录。

    base_dir 用于把相对路径（如密钥文件路径）解析成绝对路径。
    """

    value: str
    base_dir: Path


def emit_result(ok: bool, **fields: object) -> None:
    """Print a bounded result that never contains credentials or raw payloads.

    输出一条 JSON 结果（一行、字段固定、按 key 排序）。
    ok=True 表示探测成功。绝不含密钥或原始响应体。
    """
    print(json.dumps({"ok": ok, **fields}, ensure_ascii=False, sort_keys=True))


def fail(error_type: str, message: str, *, exit_code: int = 1) -> NoReturn:
    """打印失败结果并退出进程。exit_code 用于区分失败类别（如 2=配置错误）。"""
    emit_result(False, error_type=error_type, message=message)
    raise SystemExit(exit_code)


def parse_env_file(path: Path) -> dict[str, EnvValue]:
    """Parse a small dotenv subset without echoing values or importing packages.

    解析 .env 文件的一个子集（KEY=VALUE，支持 # 注释、引号包裹）。
    不打印值、不依赖第三方包。返回 {变量名: EnvValue}。
    """
    if not path.is_file():
        raise ConfigurationError(f"Configuration file not found: {path.name}")

    result: dict[str, EnvValue] = {}
    try:
        # utf-8-sig：自动去掉开头的 BOM（Windows 记事本可能写入 BOM）
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError as exc:
        raise ConfigurationError("Configuration file could not be read") from exc

    # 逐行解析；空行和 # 注释跳过
    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ConfigurationError(
                f"Invalid configuration syntax at line {line_number}"
            )

        name, value = line.split("=", 1)  # 只按第一个 = 切分，值里可含 =
        name = name.strip()
        value = value.strip()
        # 变量名必须是合法的环境变量名（大写字母/数字/下划线）
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", name):
            raise ConfigurationError(
                f"Invalid variable name at line {line_number}"
            )
        # 去掉包裹值的成对引号（单引号或双引号）
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        result[name] = EnvValue(value=value, base_dir=path.parent.resolve())

    return result


def configured_value(
    name: str,
    file_values: dict[str, EnvValue],
    *,
    default: str = "",
) -> EnvValue:
    """Prefer the process environment, then the selected local config file.

    取值优先级：进程环境变量 > 配置文件 .env > 默认值。
    环境变量可为空/未设置时回退到文件。
    """
    process_value = os.environ.get(name, "").strip()
    if process_value:
        return EnvValue(value=process_value, base_dir=REPO_ROOT)
    value = file_values.get(name)
    if value and value.value.strip():
        return EnvValue(value=value.value.strip(), base_dir=value.base_dir)
    return EnvValue(value=default, base_dir=REPO_ROOT)


def load_api_key(file_values: dict[str, EnvValue]) -> str:
    """加载 API key。两种方式二选一：
      1) NVIDIA_API_KEY      直接写 key（适合 CI / 一次性环境）
      2) NVIDIA_API_KEY_FILE 写"密钥文件路径"（本地开发，key 存白名单文件里）
    两者都设置时报错（避免歧义）；都不设置时报错。
    从密钥文件读取时，路径必须等于 APIKEY/nvidia-api-key.md，且文件内容
    必须恰好一行、无空白、长度 >= 20，否则拒绝——这些校验都防止误用。
    """
    direct = configured_value("NVIDIA_API_KEY", file_values)
    pointer = configured_value("NVIDIA_API_KEY_FILE", file_values)

    if direct.value and pointer.value:
        raise ConfigurationError(
            "Set NVIDIA_API_KEY or NVIDIA_API_KEY_FILE, not both"
        )
    if direct.value:
        return direct.value
    if not pointer.value:
        raise ConfigurationError("NVIDIA credential source is not configured")

    # 把相对路径基于配置文件所在目录解析为绝对路径
    candidate = Path(pointer.value)
    if not candidate.is_absolute():
        candidate = pointer.base_dir / candidate
    try:
        resolved = candidate.resolve(strict=True)  # strict=True：不存在即抛错
    except OSError as exc:
        raise ConfigurationError("NVIDIA key file does not exist") from exc

    # 安全白名单：只允许读固定位置的文件，防止被配置指引到任意路径
    if resolved != ALLOWED_NVIDIA_KEY_FILE:
        raise ConfigurationError(
            "NVIDIA key file must be APIKEY/nvidia-api-key.md"
        )

    # 读取文件，过滤空行
    try:
        nonempty_lines = [
            line.strip()
            for line in resolved.read_text(encoding="utf-8-sig").splitlines()
            if line.strip()
        ]
    except OSError as exc:
        raise ConfigurationError("NVIDIA key file could not be read") from exc

    # key 必须恰好一行，且不含空白、长度够，防止格式错误
    if len(nonempty_lines) != 1:
        raise ConfigurationError(
            "NVIDIA key file must contain exactly one non-empty line"
        )
    api_key = nonempty_lines[0]
    if len(api_key) < 20 or any(character.isspace() for character in api_key):
        raise ConfigurationError("NVIDIA key file has an invalid format")
    return api_key


def validate_base_url(value: str) -> str:
    """校验 base_url 必须是 https://integrate.api.nvidia.com/v1，
    防止配置被篡改成别的地址（如把密钥发到恶意服务器）。
    校验通过后一律返回规范化常量，忽略多余细节。
    """
    parsed = urlparse(value.rstrip("/"))
    if (
        parsed.scheme != "https"                    # 必须 HTTPS
        or parsed.hostname != "integrate.api.nvidia.com"
        or parsed.username is not None              # URL 里不允许带账号密码
        or parsed.password is not None
        or parsed.port not in (None, 443)           # 端口只允许默认 443
        or parsed.path not in ("", "/v1")           # 路径只能是 /v1
        or parsed.query
        or parsed.fragment
    ):
        raise ConfigurationError(
            "NVIDIA_BASE_URL must be https://integrate.api.nvidia.com/v1"
        )
    return DEFAULT_BASE_URL


def load_timeout(file_values: dict[str, EnvValue]) -> float:
    """读取并校验超时秒数：必须是数字，且落在 [1, 120] 区间。"""
    raw_value = configured_value(
        "NVIDIA_TIMEOUT_SECONDS",
        file_values,
        default=str(DEFAULT_TIMEOUT_SECONDS),
    ).value
    try:
        timeout = float(raw_value)
    except ValueError as exc:
        raise ConfigurationError("NVIDIA_TIMEOUT_SECONDS must be numeric") from exc
    if not 1.0 <= timeout <= MAX_TIMEOUT_SECONDS:
        raise ConfigurationError("NVIDIA_TIMEOUT_SECONDS must be between 1 and 120")
    return timeout


def classify_http_error(status_code: int) -> str:
    """把 HTTP 状态码归类为语义化错误类型，方便脚本调用方判断。"""
    if status_code in (401, 403):
        return "authentication_error"      # key 无效 / 无权限
    if status_code == 402:
        return "quota_or_payment_required" # 余额不足 / 需要付费
    if status_code == 404:
        return "model_or_endpoint_not_found"  # 模型名或端点写错
    if status_code == 429:
        return "rate_limit"                # 限流
    if status_code >= 500:
        return "provider_error"            # 服务端错误
    return "http_error"


def run_probe(config_path: Path, model_override: str | None) -> int:
    """探测主流程：读配置 -> 发请求 -> 分类结果 -> 输出 JSON。返回进程退出码。"""
    # ---- 阶段 1：加载并校验所有配置（任何配置错误 -> exit 2）----
    try:
        file_values = parse_env_file(config_path.resolve())
        api_key = load_api_key(file_values)
        base_url = validate_base_url(
            configured_value(
                "NVIDIA_BASE_URL", file_values, default=DEFAULT_BASE_URL
            ).value
        )
        # 命令行 --model 优先，其次配置文件，最后默认值
        model = (
            model_override
            or configured_value(
                "NVIDIA_MODEL", file_values, default=DEFAULT_MODEL
            ).value
        ).strip()
        # 模型名必须是安全字符集（字母/数字/点/下划线/斜杠/短横线），防止注入
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{1,127}", model):
            raise ConfigurationError("NVIDIA_MODEL has an invalid format")
        timeout = load_timeout(file_values)
    except ConfigurationError as exc:
        fail("configuration_error", str(exc), exit_code=2)

    # ---- 阶段 2：构造并发送 OpenAI 兼容的 chat/completions 请求 ----
    endpoint = f"{base_url}/chat/completions"
    body = json.dumps(
        {
            "model": model,
            "messages": [
                # 探测消息：让模型必须回复固定令牌 NVIDIA_API_OK，
                # 便于用响应内容判断链路是否真的通。
                {"role": "user", "content": "Reply with exactly NVIDIA_API_OK"}
            ],
            "max_tokens": 32,
            "temperature": 0,
            "stream": False,
        }
    ).encode("utf-8")
    request = Request(
        endpoint,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",  # key 只存在于内存中，绝不打印
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Agent-NVIDIA-Connectivity-Test/1.0",
        },
    )

    # ---- 阶段 3：发送请求并捕获异常 ----
    started = time.perf_counter()  # 记录起始时间，用于计算耗时
    try:
        with urlopen(request, timeout=timeout) as response:
            status_code = response.status
            response_bytes = response.read(1_000_000)  # 最多读 1MB，防恶意大响应
    except HTTPError as exc:
        # HTTP 层错误：把状态码归类后输出（不输出响应体）
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        emit_result(
            False,
            provider="nvidia",
            model=model,
            http_status=exc.code,
            latency_ms=elapsed_ms,
            error_type=classify_http_error(exc.code),
            message="NVIDIA API rejected the request",
        )
        return 1
    except (TimeoutError, URLError):
        # 超时 / 网络不可达
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        emit_result(
            False,
            provider="nvidia",
            model=model,
            latency_ms=elapsed_ms,
            error_type="network_error",
            message="NVIDIA API could not be reached before the timeout",
        )
        return 1

    # ---- 阶段 4：分析响应 ----
    elapsed_ms = round((time.perf_counter() - started) * 1000)
    if status_code == 202:
        # 202 = 已接受异步处理，未返回最终结果，也算"链路可用"
        emit_result(
            True,
            provider="nvidia",
            model=model,
            http_status=status_code,
            latency_ms=elapsed_ms,
            response_received=False,
            message="NVIDIA API accepted the request for asynchronous processing",
        )
        return 0

    # 尝试解析 JSON 响应体；解析失败或没有 choices 都视为异常形态
    try:
        payload = json.loads(response_bytes)
        choices = payload.get("choices") if isinstance(payload, dict) else None
        response_received = bool(choices)
    except (UnicodeDecodeError, json.JSONDecodeError):
        response_received = False

    if status_code != 200 or not response_received:
        # 状态码不是 200 或响应结构不对
        emit_result(
            False,
            provider="nvidia",
            model=model,
            http_status=status_code,
            latency_ms=elapsed_ms,
            error_type="invalid_response",
            message="NVIDIA API returned an unexpected response shape",
        )
        return 1

    # 一切正常：输出成功结果
    emit_result(
        True,
        provider="nvidia",
        model=model,
        http_status=status_code,
        latency_ms=elapsed_ms,
        response_received=True,
        message="NVIDIA API is available",
    )
    return 0


def main() -> int:
    """命令行入口：解析参数并调用探测主流程。"""
    parser = argparse.ArgumentParser(
        description="Safely test NVIDIA's OpenAI-compatible API"
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="Path to the local pointer-based .env file",
    )
    parser.add_argument(
        "--model",
        help="Optional model override; defaults to NVIDIA_MODEL or a safe default",
    )
    args = parser.parse_args()
    return run_probe(args.config, args.model)


if __name__ == "__main__":
    # 仅在作为脚本直接运行时执行（被 import 时不执行）
    sys.exit(main())
