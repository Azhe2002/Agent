from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


BRANCH_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BRANCH_DIR))

from config import ConfigurationError, EnvValue, Settings, _base_url, parse_env_file


class ConfigTests(unittest.TestCase):
    def test_parse_env_file_keeps_pointer_origin(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text(
                "MODEL_PROVIDER=nvidia\nNVIDIA_API_KEY_FILE=../APIKEY/key.md\n",
                encoding="utf-8",
            )
            values = parse_env_file(path)
        self.assertEqual(values["MODEL_PROVIDER"].value, "nvidia")
        self.assertEqual(values["NVIDIA_API_KEY_FILE"].value, "../APIKEY/key.md")
        self.assertTrue(values["NVIDIA_API_KEY_FILE"].base_dir.is_absolute())

    def test_base_url_rejects_non_nvidia_host(self) -> None:
        values = {
            "NVIDIA_BASE_URL": EnvValue(
                "https://example.invalid/v1", Path.cwd()
            )
        }
        with self.assertRaises(ConfigurationError):
            _base_url(values)

    def test_settings_repr_does_not_reveal_api_key(self) -> None:
        settings = Settings(
            provider="nvidia",
            api_key="SECRET_SENTINEL",
            base_url="https://integrate.api.nvidia.com/v1",
            model="example/model",
            timeout_seconds=10,
            max_agent_steps=4,
            max_output_tokens=100,
            reasoning_effort="low",
            temperature=0.2,
            verbose=False,
        )
        self.assertNotIn("SECRET_SENTINEL", repr(settings))


if __name__ == "__main__":
    unittest.main()
