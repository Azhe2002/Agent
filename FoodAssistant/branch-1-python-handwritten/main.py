"""Command-line entry point for the handwritten Food Assistant Agent."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from agent import AgentError, HandwrittenAgent
from config import ConfigurationError, DEFAULT_CONFIG_PATH, load_settings
from model_client import OpenAICompatibleChatClient
from tools import DatasetError, RecipeRepository, ToolRegistry


def _configure_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Python 手写 Agent Loop 美食助手（OpenAI 兼容 API）"
    )
    parser.add_argument(
        "query",
        nargs="?",
        help="自然语言需求；省略时进入单次交互输入",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="本地指针式 .env 路径",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="隐藏脱敏步骤日志，只显示答案与摘要",
    )
    return parser


def main() -> int:
    _configure_console()
    args = build_parser().parse_args()
    query = args.query
    if query is None:
        try:
            query = input("请描述今天的午餐需求：").strip()
        except EOFError:
            query = ""

    try:
        settings = load_settings(args.config)
        repository = RecipeRepository()
        tools = ToolRegistry(repository)
        client = OpenAICompatibleChatClient(settings)
        agent = HandwrittenAgent(
            client,
            tools,
            max_steps=settings.max_agent_steps,
            verbose=settings.verbose and not args.quiet,
        )
        result = agent.run(query)
    except (ConfigurationError, DatasetError) as exc:
        print(f"配置错误：{exc}", file=sys.stderr)
        return 2
    except AgentError as exc:
        print(f"Agent 失败（{exc.error_type}）：{exc}", file=sys.stderr)
        return 1

    print("\n=== 推荐结果 ===")
    print(result.final_answer)
    print("\n=== 脱敏运行摘要 ===")
    print(
        json.dumps(
            {
                "completed": result.completed,
                "steps": result.steps,
                "model_calls": result.model_calls,
                "tool_calls": result.tool_calls,
                "cache_hits": result.cache_hits,
                "elapsed_ms": result.elapsed_ms,
                "usage": result.usage,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if result.completed else 3


if __name__ == "__main__":
    raise SystemExit(main())
