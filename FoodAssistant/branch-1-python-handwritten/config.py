"""Secure configuration loading for the handwritten Agent branch."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse


BRANCH_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BRANCH_DIR.parent
REPO_ROOT = PROJECT_ROOT.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / ".env"
APIKEY_ROOT = (REPO_ROOT / "APIKEY").resolve()
ALLOWED_NVIDIA_KEY_FILE = (APIKEY_ROOT / "nvidia-api-key.md").resolve()
DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"
DEFAULT_MODEL = "openai/gpt-oss-20b"


class ConfigurationError(ValueError):
    """A configuration failure whose message never contains secret values."""


@dataclass(frozen=True)
class EnvValue:
    value: str
    base_dir: Path


@dataclass(frozen=True)
class Settings:
    provider: str
    base_url: str
    model: str
    timeout_seconds: float
    max_agent_steps: int
    max_output_tokens: int
    reasoning_effort: str
    temperature: float
    verbose: bool
    api_key: str = field(repr=False, compare=False)


def parse_env_file(path: Path) -> dict[str, EnvValue]:
    """Parse the small dotenv subset used by this project."""

    if not path.is_file():
        raise ConfigurationError(f"Configuration file not found: {path.name}")
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError as exc:
        raise ConfigurationError("Configuration file could not be read") from exc

    parsed: dict[str, EnvValue] = {}
    base_dir = path.parent.resolve()
    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ConfigurationError(
                f"Invalid configuration syntax at line {line_number}"
            )
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip()
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", name):
            raise ConfigurationError(
                f"Invalid variable name at line {line_number}"
            )
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        parsed[name] = EnvValue(value=value, base_dir=base_dir)
    return parsed


def _value(
    name: str,
    file_values: dict[str, EnvValue],
    *,
    default: str = "",
) -> EnvValue:
    process_value = os.environ.get(name, "").strip()
    if process_value:
        return EnvValue(process_value, REPO_ROOT)
    file_value = file_values.get(name)
    if file_value and file_value.value.strip():
        return EnvValue(file_value.value.strip(), file_value.base_dir)
    return EnvValue(default, PROJECT_ROOT)


def _boolean(name: str, file_values: dict[str, EnvValue], default: bool) -> bool:
    raw_value = _value(name, file_values, default=str(default).lower()).value.lower()
    if raw_value in {"1", "true", "yes", "on"}:
        return True
    if raw_value in {"0", "false", "no", "off"}:
        return False
    raise ConfigurationError(f"{name} must be true or false")


def _integer(
    name: str,
    file_values: dict[str, EnvValue],
    *,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    raw_value = _value(name, file_values, default=str(default)).value
    try:
        result = int(raw_value)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be an integer") from exc
    if not minimum <= result <= maximum:
        raise ConfigurationError(f"{name} must be between {minimum} and {maximum}")
    return result


def _number(
    name: str,
    file_values: dict[str, EnvValue],
    *,
    default: float,
    minimum: float,
    maximum: float,
) -> float:
    raw_value = _value(name, file_values, default=str(default)).value
    try:
        result = float(raw_value)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be numeric") from exc
    if not minimum <= result <= maximum:
        raise ConfigurationError(f"{name} must be between {minimum} and {maximum}")
    return result


def _api_key(file_values: dict[str, EnvValue]) -> str:
    direct = _value("NVIDIA_API_KEY", file_values)
    pointer = _value("NVIDIA_API_KEY_FILE", file_values)
    if direct.value and pointer.value:
        raise ConfigurationError(
            "Set NVIDIA_API_KEY or NVIDIA_API_KEY_FILE, not both"
        )
    if direct.value:
        return direct.value
    if not pointer.value:
        raise ConfigurationError("NVIDIA credential source is not configured")

    candidate = Path(pointer.value)
    if not candidate.is_absolute():
        candidate = pointer.base_dir / candidate
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise ConfigurationError("NVIDIA key file does not exist") from exc
    if resolved != ALLOWED_NVIDIA_KEY_FILE:
        raise ConfigurationError(
            "NVIDIA key file must be APIKEY/nvidia-api-key.md"
        )

    try:
        lines = [
            line.strip()
            for line in resolved.read_text(encoding="utf-8-sig").splitlines()
            if line.strip()
        ]
    except OSError as exc:
        raise ConfigurationError("NVIDIA key file could not be read") from exc
    if len(lines) != 1:
        raise ConfigurationError(
            "NVIDIA key file must contain exactly one non-empty line"
        )
    key = lines[0]
    if len(key) < 20 or any(character.isspace() for character in key):
        raise ConfigurationError("NVIDIA key file has an invalid format")
    return key


def _base_url(file_values: dict[str, EnvValue]) -> str:
    value = _value(
        "NVIDIA_BASE_URL", file_values, default=DEFAULT_BASE_URL
    ).value.rstrip("/")
    parsed = urlparse(value)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "integrate.api.nvidia.com"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in (None, 443)
        or parsed.path not in ("", "/v1")
        or parsed.query
        or parsed.fragment
    ):
        raise ConfigurationError(
            "NVIDIA_BASE_URL must be https://integrate.api.nvidia.com/v1"
        )
    return DEFAULT_BASE_URL


def load_settings(config_path: Path | None = None) -> Settings:
    path = (config_path or DEFAULT_CONFIG_PATH).resolve()
    file_values = parse_env_file(path)

    provider = _value("MODEL_PROVIDER", file_values, default="nvidia").value.lower()
    if provider != "nvidia":
        raise ConfigurationError("Branch 1 currently supports only MODEL_PROVIDER=nvidia")
    if _boolean("PAID_FALLBACK_ENABLED", file_values, False):
        raise ConfigurationError("Paid-provider fallback is not implemented in Branch 1")

    model = _value("NVIDIA_MODEL", file_values, default=DEFAULT_MODEL).value
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{1,127}", model):
        raise ConfigurationError("NVIDIA_MODEL has an invalid format")

    reasoning_effort = _value(
        "AGENT_REASONING_EFFORT", file_values, default="low"
    ).value.lower()
    if reasoning_effort not in {"low", "medium", "high"}:
        raise ConfigurationError(
            "AGENT_REASONING_EFFORT must be low, medium, or high"
        )

    return Settings(
        provider=provider,
        api_key=_api_key(file_values),
        base_url=_base_url(file_values),
        model=model,
        timeout_seconds=_number(
            "MODEL_TIMEOUT_SECONDS",
            file_values,
            default=45.0,
            minimum=1.0,
            maximum=120.0,
        ),
        max_agent_steps=_integer(
            "MAX_AGENT_STEPS",
            file_values,
            default=8,
            minimum=1,
            maximum=8,
        ),
        max_output_tokens=_integer(
            "AGENT_MAX_OUTPUT_TOKENS",
            file_values,
            default=1200,
            minimum=64,
            maximum=4096,
        ),
        reasoning_effort=reasoning_effort,
        temperature=_number(
            "AGENT_TEMPERATURE",
            file_values,
            default=0.2,
            minimum=0.0,
            maximum=1.0,
        ),
        verbose=_boolean("AGENT_VERBOSE", file_values, True),
    )
