import unittest

from core import calculate_daily_targets, demo_preference_pick, load_eval_cases, load_menu, optimize
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

    def test_backend_evaluation_passes_fixed_cases(self):
        report = run_evaluation("optimizer")
        self.assertEqual(report["summary"]["cases"], 20)
        self.assertEqual(report["summary"]["constraint_pass_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
