from __future__ import annotations

import itertools
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parent
MENU_PATH = ROOT / "data" / "menu.json"
NUTRITION_PATH = ROOT / "data" / "nutrition.json"
EVAL_PATH = ROOT / "data" / "eval_cases.json"


@dataclass(frozen=True)
class MenuItem:
    item_id: str
    shop: str
    item: str
    cuisine: str
    price_sgd: float
    location_name: str
    origin_name: str
    distance_km: float
    walk_min: int
    kcal: int
    protein_g: float
    carbs_g: float
    fat_g: float
    fibre_g: float
    sodium_mg: int
    source_family: str
    source_match: str
    mapping_method: str
    mapped_by: str
    mapped_on: str
    confidence: str


def load_menu(menu_path: Path = MENU_PATH, nutrition_path: Path = NUTRITION_PATH) -> list[MenuItem]:
    """Join the price/location dataset to the nutrition dataset by item_id."""
    nutrition_rows = json.loads(nutrition_path.read_text(encoding="utf-8"))
    nutrition = {row["item_id"]: row for row in nutrition_rows}

    rows = []
    for menu_row in json.loads(menu_path.read_text(encoding="utf-8")):
        item_id = menu_row["item_id"]
        if item_id not in nutrition:
            raise ValueError(f"Missing nutrition row for {item_id}.")
        rows.append(MenuItem(**{**menu_row, **nutrition[item_id]}))

    menu_ids = {x.item_id for x in rows}
    unused_nutrition = set(nutrition) - menu_ids
    if unused_nutrition:
        raise ValueError(f"Nutrition rows without menu records: {sorted(unused_nutrition)}")
    return rows


def load_eval_cases(path: Path = EVAL_PATH) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


ACTIVITY_MULTIPLIERS = {
    "sedentary": 1.2,
    "lightly_active": 1.375,
    "moderately_active": 1.55,
    "very_active": 1.725,
    "extra_active": 1.9,
}

GOAL_ADJUSTMENTS = {
    "lose": -300,
    "maintain": 0,
    "gain": 300,
}


def calculate_daily_targets(
    age: int,
    weight_kg: float,
    height_cm: float,
    calculation_sex: str,
    activity_level: str,
    goal: str,
) -> dict:
    """Estimate adult wellness targets with deterministic, auditable math."""
    if not 18 <= age <= 100:
        raise ValueError("Age must be between 18 and 100 for this adult-only prototype.")
    if not 35 <= weight_kg <= 300 or not 120 <= height_cm <= 230:
        raise ValueError("Weight or height is outside the supported prototype range.")
    if calculation_sex not in {"female", "male"}:
        raise ValueError("Calculation sex must be female or male.")
    if activity_level not in ACTIVITY_MULTIPLIERS or goal not in GOAL_ADJUSTMENTS:
        raise ValueError("Activity level or goal is not supported.")

    sex_constant = 5 if calculation_sex == "male" else -161
    bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + sex_constant
    maintenance = bmr * ACTIVITY_MULTIPLIERS[activity_level]
    calories = max(1200, maintenance + GOAL_ADJUSTMENTS[goal])

    # Balanced general-wellness default within adult AMDR ranges:
    # 20% protein, 50% carbohydrate, 30% fat.
    protein_g = calories * 0.20 / 4
    carbs_g = calories * 0.50 / 4
    fat_g = calories * 0.30 / 9
    return {
        "estimated_bmr_kcal": round(bmr),
        "estimated_maintenance_kcal": round(maintenance),
        "estimated_daily_calories_kcal": round(calories),
        "protein_target_g": round(protein_g),
        "carb_target_g": round(carbs_g),
        "fat_target_g": round(fat_g),
        "calculation_method": "Mifflin-St Jeor; activity multiplier; goal adjustment; 20/50/30 macro split",
        "medical_advice": False,
    }


def _totals(items: Iterable[MenuItem]) -> dict:
    items = tuple(items)
    return {
        "price_sgd": round(sum(x.price_sgd for x in items), 2),
        "kcal": sum(x.kcal for x in items),
        "protein_g": round(sum(x.protein_g for x in items), 1),
        "carbs_g": round(sum(x.carbs_g for x in items), 1),
        "fat_g": round(sum(x.fat_g for x in items), 1),
        "fibre_g": round(sum(x.fibre_g for x in items), 1),
        "sodium_mg": sum(x.sodium_mg for x in items),
        "max_distance_km": round(max((x.distance_km for x in items), default=0), 1),
        "max_walk_min": max((x.walk_min for x in items), default=0),
    }


def _score(totals: dict, budget: float, protein: float, carbs: float, shops: int) -> tuple:
    protein_floor = protein * 0.9
    carbs_floor = carbs * 0.9
    budget_gap = max(0.0, totals["price_sgd"] - budget) / max(budget, 1)
    protein_gap = max(0.0, protein_floor - totals["protein_g"]) / max(protein_floor, 1)
    carbs_gap = max(0.0, carbs_floor - totals["carbs_g"]) / max(carbs_floor, 1)
    feasible = budget_gap == protein_gap == carbs_gap == 0

    # Once feasible, prefer closeness and leave a little budget headroom.
    protein_distance = abs(totals["protein_g"] - protein) / max(protein, 1)
    carbs_distance = abs(totals["carbs_g"] - carbs) / max(carbs, 1)
    budget_use = totals["price_sgd"] / max(budget, 1)
    travel_penalty = totals["max_distance_km"] / 3 * 0.04
    multi_shop_penalty = max(0, shops - 1) * 0.015
    if feasible:
        distance = protein_distance * 0.46 + carbs_distance * 0.36 + budget_use * 0.12 + travel_penalty + multi_shop_penalty
    else:
        distance = 10 + budget_gap * 5 + protein_gap * 3 + carbs_gap * 3 + travel_penalty + multi_shop_penalty
    return feasible, round(distance, 5), {
        "budget_gap": round(budget_gap, 4),
        "protein_gap": round(protein_gap, 4),
        "carbs_gap": round(carbs_gap, 4),
    }


def optimize(menu: list[MenuItem], budget: float, protein_g: float, carbs_g: float, shortlist_size: int = 5) -> dict:
    if not 3 <= budget <= 100:
        raise ValueError("Budget must be between S$3 and S$100.")
    if not 10 <= protein_g <= 250 or not 20 <= carbs_g <= 500:
        raise ValueError("Macro targets are outside the supported prototype range.")

    candidates = []
    seen = set()
    for count in range(1, 4):
        for combo in itertools.combinations(menu, count):
            ids = tuple(sorted(item.item_id for item in combo))
            if ids in seen:
                continue
            seen.add(ids)
            totals = _totals(combo)
            feasible, score, gaps = _score(totals, budget, protein_g, carbs_g, len({x.shop for x in combo}))
            candidates.append({
                "plan_id": "+".join(ids),
                "items": [asdict(x) for x in combo],
                "totals": totals,
                "feasible": feasible,
                "score": score,
                "gaps": gaps,
            })

    candidates.sort(key=lambda x: (not x["feasible"], x["score"], x["totals"]["price_sgd"], x["plan_id"]))
    shortlist = candidates[:shortlist_size]
    return {
        "inputs": {"budget": budget, "protein_g": protein_g, "carbs_g": carbs_g, "threshold": 0.9},
        "feasible_count": sum(1 for x in candidates if x["feasible"]),
        "evaluated_count": len(candidates),
        "shortlist": shortlist,
        "optimizer_pick": shortlist[0],
    }


def demo_preference_pick(shortlist: list[dict], preferences: str) -> dict:
    """Transparent, non-LLM demo only; never count this as model evidence."""
    text = preferences.lower()
    scored = []
    for plan in shortlist:
        blob = " ".join(f"{x['item']} {x['cuisine']} {x['shop']}" for x in plan["items"]).lower()
        bonus = 0
        for token in ("chicken", "vegetarian", "indian", "chinese", "malay", "western", "rice", "noodle", "spicy", "fish"):
            if token in text and token in blob:
                bonus += 1
        if "variety" in text:
            bonus += len({x["cuisine"] for x in plan["items"]}) * 0.35
        scored.append((bonus, -plan["score"], plan))
    chosen = max(scored, key=lambda x: (x[0], x[1]))[2]
    return {
        "plan_id": chosen["plan_id"],
        "reason": "Demo heuristic matched stated food words and variety, then used optimizer score as a tie-breaker.",
        "mode": "demo_heuristic",
    }
