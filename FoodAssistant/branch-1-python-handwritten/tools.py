"""Four read-only tools and a small character n-gram recipe retriever."""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


BRANCH_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BRANCH_DIR.parent
RECIPES_PATH = PROJECT_ROOT / "datasets" / "recipes.json"
INGREDIENTS_PATH = PROJECT_ROOT / "datasets" / "ingredients.json"
MAX_TOOL_TEXT_LENGTH = 160
MAX_LIST_LENGTH = 30


def _success(data: Any, message: str, source: str) -> dict[str, Any]:
    return {
        "ok": True,
        "data": data,
        "error_type": None,
        "message": message,
        "source": source,
    }


def _failure(error_type: str, message: str, source: str) -> dict[str, Any]:
    return {
        "ok": False,
        "data": None,
        "error_type": error_type,
        "message": message,
        "source": source,
    }


class DatasetError(ValueError):
    pass


class RecipeRepository:
    def __init__(
        self,
        recipes_path: Path = RECIPES_PATH,
        ingredients_path: Path = INGREDIENTS_PATH,
    ) -> None:
        recipes_document = self._read_json(recipes_path, "recipes")
        ingredients_document = self._read_json(ingredients_path, "ingredients")
        self.version = str(recipes_document.get("version", "unknown"))
        self.recipes = recipes_document.get("recipes")
        self.ingredients = ingredients_document.get("ingredients")
        if not isinstance(self.recipes, list) or not isinstance(self.ingredients, list):
            raise DatasetError("Dataset collections must be JSON arrays")
        self._validate_recipes()
        self._validate_ingredients()
        self._by_id = {recipe["id"]: recipe for recipe in self.recipes}
        self._by_name = {recipe["name"].casefold(): recipe for recipe in self.recipes}

    @staticmethod
    def _read_json(path: Path, label: str) -> dict[str, Any]:
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise DatasetError(f"{label} dataset could not be loaded") from exc
        if not isinstance(document, dict):
            raise DatasetError(f"{label} dataset must be a JSON object")
        return document

    def _validate_recipes(self) -> None:
        required = {
            "id",
            "name",
            "description",
            "ingredients",
            "steps",
            "cook_time_minutes",
            "flavor",
            "suitable_weather",
            "difficulty",
            "allergen_notes",
        }
        ids: set[str] = set()
        names: set[str] = set()
        for recipe in self.recipes:
            if not isinstance(recipe, dict) or not required.issubset(recipe):
                raise DatasetError("A recipe is missing required fields")
            recipe_id = recipe["id"]
            recipe_name = recipe["name"]
            if not isinstance(recipe_id, str) or not isinstance(recipe_name, str):
                raise DatasetError("Recipe id and name must be strings")
            if recipe_id in ids or recipe_name.casefold() in names:
                raise DatasetError("Recipe ids and names must be unique")
            ids.add(recipe_id)
            names.add(recipe_name.casefold())
            if not isinstance(recipe["ingredients"], list) or not recipe["ingredients"]:
                raise DatasetError("Recipe ingredients must be a non-empty list")
            if not isinstance(recipe["steps"], list) or not recipe["steps"]:
                raise DatasetError("Recipe steps must be a non-empty list")
            if not isinstance(recipe["cook_time_minutes"], int) or recipe["cook_time_minutes"] <= 0:
                raise DatasetError("Recipe cooking time must be a positive integer")

    def _validate_ingredients(self) -> None:
        ids: set[str] = set()
        for ingredient in self.ingredients:
            if not isinstance(ingredient, dict):
                raise DatasetError("Ingredient entries must be objects")
            if not {"id", "name", "quantity", "unit"}.issubset(ingredient):
                raise DatasetError("An ingredient is missing required fields")
            if ingredient["id"] in ids:
                raise DatasetError("Ingredient ids must be unique")
            ids.add(ingredient["id"])

    def find_recipe(self, recipe_id: str | None, name: str | None) -> dict[str, Any] | None:
        if recipe_id:
            return self._by_id.get(recipe_id)
        if name:
            return self._by_name.get(name.casefold())
        return None


MOCK_WEATHER = {
    "北京": {"condition": "晴朗干燥", "temperature_c": 24, "feels_like": "舒适"},
    "上海": {"condition": "小雨", "temperature_c": 20, "feels_like": "微凉"},
    "苏州": {"condition": "阴有小雨", "temperature_c": 19, "feels_like": "偏凉"},
    "杭州": {"condition": "多云", "temperature_c": 23, "feels_like": "舒适"},
    "成都": {"condition": "阴天", "temperature_c": 18, "feels_like": "偏凉"},
    "武汉": {"condition": "晴热", "temperature_c": 32, "feels_like": "炎热"},
    "广州": {"condition": "雷阵雨", "temperature_c": 30, "feels_like": "闷热"},
    "深圳": {"condition": "阵雨", "temperature_c": 29, "feels_like": "闷热"},
}


def _normalized_text(value: str) -> str:
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", value.casefold())


def _char_ngrams(value: str) -> Counter[str]:
    normalized = _normalized_text(value)
    grams: Counter[str] = Counter()
    for size in (1, 2):
        if len(normalized) < size:
            continue
        grams.update(normalized[index : index + size] for index in range(len(normalized) - size + 1))
    return grams


def _cosine(left: Counter[str], right: Counter[str]) -> float:
    if not left or not right:
        return 0.0
    numerator = sum(value * right.get(key, 0) for key, value in left.items())
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if not left_norm or not right_norm:
        return 0.0
    return numerator / (left_norm * right_norm)


def _string(value: Any, name: str, *, required: bool = False) -> str:
    if value is None and not required:
        return ""
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    result = value.strip()
    if required and not result:
        raise ValueError(f"{name} must not be empty")
    if len(result) > MAX_TOOL_TEXT_LENGTH:
        raise ValueError(f"{name} is too long")
    return result


def _string_list(value: Any, name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > MAX_LIST_LENGTH:
        raise ValueError(f"{name} must be a bounded string list")
    result = [_string(item, name, required=True) for item in value]
    return list(dict.fromkeys(result))


@dataclass(frozen=True)
class ToolExecution:
    result: dict[str, Any]
    cache_hit: bool
    signature: str


class ToolRegistry:
    def __init__(self, repository: RecipeRepository | None = None) -> None:
        self.repository = repository or RecipeRepository()
        self._cache: dict[str, dict[str, Any]] = {}
        self._handlers: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
            "get_weather": self._get_weather,
            "get_available_ingredients": self._get_available_ingredients,
            "search_recipes": self._search_recipes,
            "get_recipe": self._get_recipe,
        }

    @property
    def schemas(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "获取指定中国城市的只读模拟天气；用户已明确描述天气时无需调用。",
                    "parameters": {
                        "type": "object",
                        "properties": {"city": {"type": "string"}},
                        "required": ["city"],
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_available_ingredients",
                    "description": "读取模拟冰箱中当前可用的食材，不会扣减库存。",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "search_recipes",
                    "description": "按关键词、耗时、口味、天气和已有食材检索菜谱候选。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "keywords": {
                                "anyOf": [
                                    {"type": "string"},
                                    {"type": "array", "items": {"type": "string"}},
                                ]
                            },
                            "max_cook_time_minutes": {"type": "integer", "minimum": 1},
                            "flavor": {"type": "string"},
                            "suitable_weather": {"type": "string"},
                            "available_ingredients": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "limit": {"type": "integer", "minimum": 1, "maximum": 5},
                        },
                        "required": ["keywords"],
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_recipe",
                    "description": "用候选中的 recipe_id 或准确菜名读取完整菜谱，二选一。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "recipe_id": {"type": "string"},
                            "name": {"type": "string"},
                        },
                        "additionalProperties": False,
                    },
                },
            },
        ]

    def execute(self, name: str, arguments: Any) -> ToolExecution:
        if not isinstance(name, str) or name not in self._handlers:
            result = _failure(
                "invalid_tool_request", "Unknown or unavailable tool", "tool-registry"
            )
            return ToolExecution(result, False, "unknown")
        if not isinstance(arguments, dict):
            result = _failure(
                "invalid_tool_request", "Tool arguments must be an object", name
            )
            return ToolExecution(result, False, f"{name}:invalid")

        signature = f"{name}:{json.dumps(arguments, ensure_ascii=False, sort_keys=True, separators=(',', ':'))}"
        cached = self._cache.get(signature)
        if cached is not None:
            return ToolExecution(deepcopy(cached), True, signature)
        try:
            result = self._handlers[name](arguments)
        except ValueError as exc:
            result = _failure("invalid_tool_request", str(exc), name)
        except DatasetError:
            result = _failure("internal_error", "Dataset is unavailable", name)
        except Exception:
            result = _failure("internal_error", "Tool execution failed", name)
        self._cache[signature] = deepcopy(result)
        return ToolExecution(result, False, signature)

    @staticmethod
    def _reject_extra(arguments: dict[str, Any], allowed: set[str]) -> None:
        extras = set(arguments) - allowed
        if extras:
            raise ValueError("Tool request contains unsupported fields")

    def _get_weather(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self._reject_extra(arguments, {"city"})
        city = _string(arguments.get("city"), "city", required=True).removesuffix("市")
        weather = MOCK_WEATHER.get(city)
        if weather is None:
            return _failure("not_found", "No mock weather is available for this city", "mock-weather-v1")
        return _success(
            {
                "city": city,
                **weather,
                "observed_at": "mock-scenario-v1",
                "is_mock": True,
            },
            "Mock weather found",
            "mock-weather-v1",
        )

    def _get_available_ingredients(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self._reject_extra(arguments, set())
        return _success(
            {"items": deepcopy(self.repository.ingredients), "count": len(self.repository.ingredients)},
            "Available ingredients loaded",
            "ingredients-v1",
        )

    def _search_recipes(self, arguments: dict[str, Any]) -> dict[str, Any]:
        allowed = {
            "keywords",
            "max_cook_time_minutes",
            "flavor",
            "suitable_weather",
            "available_ingredients",
            "limit",
        }
        self._reject_extra(arguments, allowed)
        raw_keywords = arguments.get("keywords")
        if isinstance(raw_keywords, list):
            keywords = " ".join(_string_list(raw_keywords, "keywords"))
        else:
            keywords = _string(raw_keywords, "keywords", required=True)
        if not _normalized_text(keywords):
            raise ValueError("keywords must contain searchable characters")

        flavor = _string(arguments.get("flavor"), "flavor")
        weather = _string(arguments.get("suitable_weather"), "suitable_weather")
        available = _string_list(arguments.get("available_ingredients"), "available_ingredients")
        max_time = arguments.get("max_cook_time_minutes")
        if max_time is not None and (not isinstance(max_time, int) or not 1 <= max_time <= 240):
            raise ValueError("max_cook_time_minutes must be between 1 and 240")
        limit = arguments.get("limit", 3)
        if not isinstance(limit, int) or not 1 <= limit <= 5:
            raise ValueError("limit must be between 1 and 5")

        query_grams = _char_ngrams(" ".join([keywords, flavor, weather, *available]))
        available_normalized = {_normalized_text(item) for item in available}
        ranked: list[tuple[float, dict[str, Any], list[str]]] = []
        for recipe in self.repository.recipes:
            if max_time is not None and recipe["cook_time_minutes"] > max_time:
                continue
            ingredient_names = [item["name"] for item in recipe["ingredients"]]
            document = " ".join(
                [
                    recipe["name"],
                    recipe["description"],
                    " ".join(ingredient_names),
                    recipe["flavor"],
                    " ".join(recipe["suitable_weather"]),
                ]
            )
            score = _cosine(query_grams, _char_ngrams(document))
            reasons: list[str] = []
            if flavor and _normalized_text(flavor) in _normalized_text(recipe["flavor"]):
                score += 0.15
                reasons.append("口味匹配")
            if weather and any(
                _normalized_text(weather) in _normalized_text(item)
                or _normalized_text(item) in _normalized_text(weather)
                for item in recipe["suitable_weather"]
            ):
                score += 0.12
                reasons.append("天气匹配")
            if available_normalized:
                required = {_normalized_text(item) for item in ingredient_names}
                overlap = len(required & available_normalized)
                coverage = overlap / max(len(required), 1)
                score += coverage * 0.25
                if overlap:
                    reasons.append(f"已有{overlap}种所需食材")
            if max_time is not None:
                reasons.append("耗时符合限制")
            if score > 0.05:
                ranked.append((score, recipe, reasons or ["关键词相关"]))

        ranked.sort(key=lambda item: (-item[0], item[1]["cook_time_minutes"], item[1]["name"]))
        items = [
            {
                "recipe_id": recipe["id"],
                "name": recipe["name"],
                "score": round(min(score, 1.0), 4),
                "cook_time_minutes": recipe["cook_time_minutes"],
                "flavor": recipe["flavor"],
                "suitable_weather": recipe["suitable_weather"],
                "difficulty": recipe["difficulty"],
                "match_reason": reasons,
            }
            for score, recipe, reasons in ranked[:limit]
        ]
        message = "Recipe candidates found" if items else "No matching recipes found"
        return _success(
            {"items": items, "count": len(items)},
            message,
            self.repository.version,
        )

    def _get_recipe(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self._reject_extra(arguments, {"recipe_id", "name"})
        recipe_id = _string(arguments.get("recipe_id"), "recipe_id")
        name = _string(arguments.get("name"), "name")
        if bool(recipe_id) == bool(name):
            raise ValueError("Provide exactly one of recipe_id or name")
        recipe = self.repository.find_recipe(recipe_id or None, name or None)
        if recipe is None:
            return _failure("not_found", "Recipe was not found", self.repository.version)
        return _success(deepcopy(recipe), "Recipe loaded", self.repository.version)
