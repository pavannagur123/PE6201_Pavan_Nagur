import unittest

from core import (
    analyze_actual_intake,
    calculate_daily_targets,
    demo_preference_pick,
    load_eval_cases,
    load_menu,
    minimum_three_meal_budget,
    optimize,
    optimize_daily_meal_plan,
    parse_meal_preferences,
)
from evaluate import run_evaluation


class MacroFitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.menu = load_menu()

    def test_dataset_size_and_shops(self):
        self.assertEqual(len(self.menu), 60)
        self.assertEqual(len({x.shop for x in self.menu}), 10)
        self.assertTrue(all(x.mapped_by == "Nagur Pavan" for x in self.menu))
        self.assertTrue(all(x.origin_name == "NTU North Spine" for x in self.menu))
        self.assertTrue(all(x.distance_km >= 0 for x in self.menu))

    def test_evaluation_has_twenty_cases(self):
        self.assertEqual(len(load_eval_cases()), 20)

    def test_profile_is_converted_to_targets_deterministically(self):
        targets = calculate_daily_targets(25, 72, 175, "male", "moderately_active", "maintain")
        self.assertEqual(targets["estimated_bmr_kcal"], 1694)
        self.assertEqual(targets["estimated_daily_calories_kcal"], 2625)
        self.assertEqual(targets["protein_target_g"], 131)
        self.assertEqual(targets["carb_target_g"], 328)
        self.assertFalse(targets["medical_advice"])

    def test_feasible_pick_respects_constraints(self):
        result = optimize(self.menu, 18, 70, 150)
        pick = result["optimizer_pick"]
        self.assertTrue(pick["feasible"])
        self.assertLessEqual(pick["totals"]["price_sgd"], 18)
        self.assertGreaterEqual(pick["totals"]["protein_g"], 63)
        self.assertGreaterEqual(pick["totals"]["carbs_g"], 135)

    def test_shortlist_is_sorted_and_bounded(self):
        result = optimize(self.menu, 16, 60, 140)
        self.assertEqual(len(result["shortlist"]), 5)
        self.assertEqual(result["optimizer_pick"], result["shortlist"][0])
        self.assertEqual(result["shortlist"], sorted(result["shortlist"], key=lambda x: (not x["feasible"], x["score"], x["totals"]["price_sgd"], x["plan_id"])))

    def test_invalid_inputs_are_rejected(self):
        with self.assertRaises(ValueError):
            optimize(self.menu, -1, 70, 150)

    def test_demo_pick_never_leaves_shortlist(self):
        result = optimize(self.menu, 18, 70, 150)
        pick = demo_preference_pick(result["shortlist"], "I like Indian chicken")
        self.assertIn(pick["plan_id"], {p["plan_id"] for p in result["shortlist"]})

    def test_daily_plan_has_light_breakfast_lunch_and_dinner(self):
        result = optimize_daily_meal_plan(self.menu, 25, 2200, 110, 275)
        self.assertTrue(result["available"])
        plan = result["optimizer_pick"]
        self.assertLessEqual(plan["totals"]["price_sgd"], 25)
        self.assertGreaterEqual(plan["totals"]["kcal"], 2200 * 0.9)
        self.assertEqual([entry["meal"] for entry in plan["schedule"]], ["breakfast", "lunch", "dinner"])
        self.assertLessEqual(plan["schedule"][0]["item"]["kcal"], 500)
        self.assertNotEqual(plan["schedule"][0]["item"]["item"], "Chicken Rice")
        self.assertEqual([entry["eat_at"] for entry in plan["schedule"]], ["08:00", "13:00", "19:00"])

    def test_three_meal_budget_floor_is_enforced(self):
        minimum = minimum_three_meal_budget(self.menu)
        self.assertEqual(minimum, 14.8)
        result = optimize_daily_meal_plan(self.menu, minimum - 0.1, 2200, 110, 275)
        self.assertFalse(result["available"])
        self.assertIn("minimum", result["message"].lower())

    def test_meal_specific_text_becomes_hard_constraints(self):
        preferences = parse_meal_preferences("Maybe veg for lunch and chicken for dinner")
        self.assertEqual(preferences, {"breakfast": "any", "lunch": "vegetarian", "dinner": "chicken"})
        result = optimize_daily_meal_plan(self.menu, 30, 2633, 132, 329, meal_preferences=preferences)
        self.assertTrue(result["available"])
        plan = result["optimizer_pick"]
        self.assertEqual(plan["schedule"][1]["item"]["cuisine"], "Vegetarian")
        self.assertIn("Chicken", plan["schedule"][2]["item"]["item"])
        self.assertGreaterEqual(plan["totals"]["kcal"], 2633 * 0.9)

    def test_underfunded_target_returns_no_plan_and_required_budget(self):
        result = optimize_daily_meal_plan(self.menu, 18, 2633, 132, 329)
        self.assertFalse(result["available"])
        self.assertGreater(result["minimum_target_budget_sgd"], 18)
        self.assertIn("90%", result["message"])

    def test_actual_intake_analysis_uses_dataset_values(self):
        result = analyze_actual_intake(
            self.menu,
            [
                {"meal": "breakfast", "item_id": "B01", "quantity": 1},
                {"meal": "lunch", "item_id": "H01", "quantity": 1},
                {"meal": "dinner", "item_id": "I01", "quantity": 1},
            ],
            {"calories_kcal": 1800, "protein_g": 90, "carbs_g": 225, "fat_g": 60},
            20,
        )
        self.assertEqual(result["actual_totals"]["kcal"], 1800)
        self.assertEqual(result["status"], "at_estimate")
        self.assertTrue(result["within_budget"])

    def test_backend_evaluation_passes_fixed_cases(self):
        report = run_evaluation("optimizer")
        self.assertEqual(report["summary"]["cases"], 20)
        self.assertEqual(report["summary"]["constraint_pass_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
