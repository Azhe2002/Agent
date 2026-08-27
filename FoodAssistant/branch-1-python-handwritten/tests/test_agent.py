from __future__ import annotations

import contextlib
import io
import json
import sys
import unittest
from pathlib import Path
from typing import Any


BRANCH_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BRANCH_DIR))

from agent import AgentError, HandwrittenAgent, SafeEventLogger
from model_client import ChatResponse
from tools import ToolExecution, ToolRegistry


def tool_call(call_id: str, name: str, arguments: dict[str, Any]) -> ChatResponse:
    return ChatResponse(
        message={
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": call_id,
                    "type": "function",
                    "function": {
                        "name": name,
                        "arguments": json.dumps(arguments, ensure_ascii=False),
                    },
                }
            ],
        },
        latency_ms=1,
        usage={"total_tokens": 10},
    )


class SequenceClient:
    def __init__(self, responses: list[ChatResponse]) -> None:
        self.responses = responses
        self.calls = 0
        self.snapshots: list[list[dict[str, Any]]] = []

    def chat(
        self,
        messages: list[dict[str, Any]],
        tool_schemas: list[dict[str, Any]],
    ) -> ChatResponse:
        self.snapshots.append(list(messages))
        response = self.responses[min(self.calls, len(self.responses) - 1)]
        self.calls += 1
        return response


class AgentTests(unittest.TestCase):
    def test_complete_search_detail_answer_loop(self) -> None:
        client = SequenceClient(
            [
                tool_call(
                    "call-search",
                    "search_recipes",
                    {"keywords": "土豆 胡萝卜 暖和", "limit": 2},
                ),
                tool_call(
                    "call-detail",
                    "get_recipe",
                    {"recipe_id": "carrot_potato_chicken_stew"},
                ),
                ChatResponse(
                    message={"role": "assistant", "content": "推荐胡萝卜土豆炖鸡。"},
                    latency_ms=1,
                    usage={"total_tokens": 5},
                ),
            ]
        )
        result = HandwrittenAgent(
            client, ToolRegistry(), max_steps=5, verbose=False
        ).run("下雨有点冷，想吃暖和的，家里有土豆胡萝卜。")
        self.assertTrue(result.completed)
        self.assertEqual(result.model_calls, 3)
        self.assertEqual(result.tool_calls, 2)
        self.assertIn("胡萝卜土豆炖鸡", result.final_answer)
        self.assertTrue(
            any(message.get("role") == "tool" for message in client.snapshots[-1])
        )

    def test_repeated_call_is_cached_and_loop_is_bounded(self) -> None:
        repeated = tool_call(
            "same-call", "search_recipes", {"keywords": "番茄 鸡蛋"}
        )
        client = SequenceClient([repeated])
        result = HandwrittenAgent(
            client, ToolRegistry(), max_steps=3, verbose=False
        ).run("想吃番茄鸡蛋。")
        self.assertFalse(result.completed)
        self.assertEqual(result.model_calls, 3)
        self.assertEqual(result.tool_calls, 3)
        self.assertGreaterEqual(result.cache_hits, 2)

    def test_logger_never_prints_argument_values(self) -> None:
        logger = SafeEventLogger(True)
        execution = ToolExecution(
            result={"ok": True, "error_type": None},
            cache_hit=False,
            signature="safe",
        )
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            logger.tool_call(
                1,
                "search_recipes",
                {"keywords": "SECRET_SENTINEL"},
                execution,
            )
        self.assertNotIn("SECRET_SENTINEL", output.getvalue())
        self.assertIn("keywords", output.getvalue())

    def test_tool_calls_per_response_are_capped_without_breaking_protocol(self) -> None:
        calls = [
            {
                "id": f"call-{index}",
                "type": "function",
                "function": {
                    "name": "search_recipes",
                    "arguments": json.dumps({"keywords": f"菜谱 {index}"}),
                },
            }
            for index in range(5)
        ]
        client = SequenceClient(
            [
                ChatResponse(
                    message={"role": "assistant", "content": None, "tool_calls": calls},
                    latency_ms=1,
                    usage={},
                ),
                ChatResponse(
                    message={"role": "assistant", "content": "已完成。"},
                    latency_ms=1,
                    usage={},
                ),
            ]
        )

        result = HandwrittenAgent(
            client, ToolRegistry(), max_steps=2, verbose=False
        ).run("给我几个午餐建议。")

        self.assertTrue(result.completed)
        self.assertEqual(result.tool_calls, 4)
        assistant_messages = [
            message
            for message in client.snapshots[-1]
            if message.get("role") == "assistant"
        ]
        tool_messages = [
            message
            for message in client.snapshots[-1]
            if message.get("role") == "tool"
        ]
        self.assertEqual(len(assistant_messages[-1]["tool_calls"]), 4)
        self.assertEqual(len(tool_messages), 4)

    def test_length_finish_reason_is_not_reported_as_complete(self) -> None:
        client = SequenceClient(
            [
                ChatResponse(
                    message={"role": "assistant", "content": "未完成的回答"},
                    latency_ms=1,
                    usage={},
                    finish_reason="length",
                )
            ]
        )

        result = HandwrittenAgent(
            client, ToolRegistry(), max_steps=1, verbose=False
        ).run("请推荐午餐。")

        self.assertFalse(result.completed)
        self.assertIn("输出上限", result.final_answer)

    def test_known_gpt_oss_channel_suffix_is_removed_from_tool_name(self) -> None:
        client = SequenceClient(
            [
                tool_call(
                    "call-search",
                    "search_recipes<|channel|>commentary",
                    {"keywords": "土豆 胡萝卜"},
                ),
                ChatResponse(
                    message={"role": "assistant", "content": "已检索。"},
                    latency_ms=1,
                    usage={},
                ),
            ]
        )

        result = HandwrittenAgent(
            client, ToolRegistry(), max_steps=2, verbose=False
        ).run("想吃土豆。")

        self.assertTrue(result.completed)
        assistant_call = next(
            message
            for message in client.snapshots[-1]
            if message.get("role") == "assistant"
        )["tool_calls"][0]
        self.assertEqual(assistant_call["function"]["name"], "search_recipes")
        tool_result = next(
            message
            for message in client.snapshots[-1]
            if message.get("role") == "tool"
        )
        self.assertEqual(tool_result["name"], "search_recipes")

    def test_unsafe_tool_name_is_rejected_before_logging_or_execution(self) -> None:
        client = SequenceClient(
            [tool_call("call-unsafe", "search_recipes\nforged-log", {"keywords": "土豆"})]
        )

        with self.assertRaises(AgentError) as raised:
            HandwrittenAgent(
                client, ToolRegistry(), max_steps=1, verbose=False
            ).run("想吃土豆。")

        self.assertEqual(raised.exception.error_type, "invalid_response")


if __name__ == "__main__":
    unittest.main()
