from __future__ import annotations

import sys
import unittest
from pathlib import Path


BRANCH_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BRANCH_DIR))

from tools import RecipeRepository, ToolRegistry


class ToolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repository = RecipeRepository()

    def setUp(self) -> None:
        self.tools = ToolRegistry(self.repository)

    def test_dataset_has_25_unique_recipes(self) -> None:
        self.assertEqual(len(self.repository.recipes), 25)
        self.assertEqual(
            len({recipe["id"] for recipe in self.repository.recipes}), 25
        )

    def test_inventory_is_read_only_and_bounded(self) -> None:
        first = self.tools.execute("get_available_ingredients", {})
        second = self.tools.execute("get_available_ingredients", {})
        self.assertTrue(first.result["ok"])
        self.assertGreater(first.result["data"]["count"], 0)
        self.assertTrue(second.cache_hit)
        self.assertEqual(first.result, second.result)

    def test_cold_rainy_potato_carrot_query_returns_warm_stew(self) -> None:
        execution = self.tools.execute(
            "search_recipes",
            {
                "keywords": "下雨 寒冷 暖和 土豆 胡萝卜",
                "suitable_weather": "寒冷",
                "available_ingredients": ["土豆", "胡萝卜", "鸡腿肉"],
                "limit": 3,
            },
        )
        self.assertTrue(execution.result["ok"])
        names = [item["name"] for item in execution.result["data"]["items"]]
        self.assertIn("胡萝卜土豆炖鸡", names)

    def test_hot_light_query_respects_twenty_minute_limit(self) -> None:
        result = self.tools.execute(
            "search_recipes",
            {
                "keywords": "天气炎热 想吃清淡",
                "flavor": "清淡",
                "suitable_weather": "炎热",
                "max_cook_time_minutes": 20,
                "limit": 3,
            },
        ).result
        self.assertTrue(result["ok"])
        items = result["data"]["items"]
        self.assertGreater(len(items), 0)
        self.assertTrue(all(item["cook_time_minutes"] <= 20 for item in items))
        self.assertIn("炎热", items[0]["suitable_weather"])

    def test_search_rejects_punctuation_only_query(self) -> None:
        execution = self.tools.execute("search_recipes", {"keywords": "!!!"})
        self.assertFalse(execution.result["ok"])
        self.assertEqual(execution.result["error_type"], "invalid_tool_request")

    def test_recipe_requires_exactly_one_identifier(self) -> None:
        execution = self.tools.execute(
            "get_recipe", {"recipe_id": "tomato_scrambled_egg", "name": "番茄炒蛋"}
        )
        self.assertFalse(execution.result["ok"])
        self.assertEqual(execution.result["error_type"], "invalid_tool_request")

    def test_unknown_tool_returns_structured_error(self) -> None:
        execution = self.tools.execute("read_api_key", {})
        self.assertFalse(execution.result["ok"])
        self.assertEqual(execution.result["error_type"], "invalid_tool_request")


if __name__ == "__main__":
    unittest.main()
