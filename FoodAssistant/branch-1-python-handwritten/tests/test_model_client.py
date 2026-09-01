from __future__ import annotations

import sys
import unittest
from pathlib import Path


BRANCH_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BRANCH_DIR))

from config import Settings
from model_client import build_chat_payload


def settings_for(provider: str, model: str) -> Settings:
    return Settings(
        provider=provider,
        api_key="TEST_ONLY_NOT_A_REAL_KEY",
        base_url="https://example.invalid",
        model=model,
        timeout_seconds=10,
        max_agent_steps=4,
        max_output_tokens=300,
        reasoning_effort="low",
        temperature=0.2,
        verbose=False,
    )


class ModelClientPayloadTests(unittest.TestCase):
    def test_mimo_uses_completion_limit_and_disables_thinking(self) -> None:
        payload = build_chat_payload(
            settings_for("mimo", "mimo-v2.5"),
            [{"role": "user", "content": "test"}],
            [{"type": "function", "function": {"name": "test_tool"}}],
        )
        self.assertEqual(payload["max_completion_tokens"], 300)
        self.assertEqual(payload["thinking"], {"type": "disabled"})
        self.assertNotIn("reasoning_effort", payload)
        self.assertEqual(payload["tool_choice"], "auto")

    def test_kimi_and_deepseek_use_openai_max_tokens(self) -> None:
        for provider, model in (
            ("deepseek", "deepseek-v4-flash"),
            ("kimi", "kimi-k2.6"),
        ):
            with self.subTest(provider=provider):
                payload = build_chat_payload(
                    settings_for(provider, model),
                    [{"role": "user", "content": "test"}],
                    [],
                )
                self.assertEqual(payload["max_tokens"], 300)
                self.assertEqual(payload["thinking"], {"type": "disabled"})
                if provider == "kimi":
                    self.assertNotIn("temperature", payload)

    def test_nvidia_keeps_reasoning_effort_compatibility(self) -> None:
        payload = build_chat_payload(
            settings_for("nvidia", "openai/gpt-oss-20b"),
            [{"role": "user", "content": "test"}],
            [],
        )
        self.assertEqual(payload["reasoning_effort"], "low")
        self.assertNotIn("thinking", payload)


if __name__ == "__main__":
    unittest.main()
