from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from core import ROOT, demo_preference_pick, load_eval_cases, load_menu, optimize


def run_evaluation(mode: str = "optimizer") -> dict:
    """Run the fixed 20-case backend evaluation and return JSON-safe results."""
    if mode not in {"optimizer", "demo", "claude"}:
        raise ValueError("mode must be optimizer, demo, or claude")

    menu = load_menu()
    results = []
    for case in load_eval_cases():
        solution = optimize(menu, case["budget"], case["protein_g"], case["carbs_g"])
        pick = solution["optimizer_pick"]
        row = {
            "case_id": case["id"],
            "inputs": {
                "budget": case["budget"],
                "protein_g": case["protein_g"],
                "carbs_g": case["carbs_g"],
                "preferences": case["preferences"],
            },
            "optimizer_plan_id": pick["plan_id"],
            "optimizer_totals": pick["totals"],
            "constraint_checks": {
                "within_budget": pick["totals"]["price_sgd"] <= case["budget"],
                "protein_at_least_90_percent": pick["totals"]["protein_g"] >= case["protein_g"] * 0.9,
                "carbs_at_least_90_percent": pick["totals"]["carbs_g"] >= case["carbs_g"] * 0.9,
            },
            "feasible_plan_count": solution["feasible_count"],
            "plans_evaluated": solution["evaluated_count"],
        }
        row["all_constraints_pass"] = all(row["constraint_checks"].values())

        if mode == "demo":
            ranking = demo_preference_pick(solution["shortlist"], case["preferences"])
            row["preference_pick"] = ranking
        elif mode == "claude":
            from app import claude_rank

            row["preference_pick"] = claude_rank(solution["shortlist"], case["preferences"])
        results.append(row)

    passing = sum(x["all_constraints_pass"] for x in results)
    preference_rows = [x for x in results if "preference_pick" in x]
    changed = sum(
        x["preference_pick"]["plan_id"] != x["optimizer_plan_id"]
        for x in preference_rows
    )
    return {
        "summary": {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "mode": mode,
            "dataset_items": len(menu),
            "dataset_outlets": len({x.shop for x in menu}),
            "origin": "NTU North Spine",
            "cases": len(results),
            "constraint_pass_count": passing,
            "constraint_pass_rate": round(passing / len(results), 4),
            "preference_layer_cases": len(preference_rows),
            "preference_pick_changed_count": changed,
            "note": "Changed picks are not wins. Human blind judgments from the web app are required to measure preference win rate.",
        },
        "cases": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run MacroFit's fixed backend evaluation.")
    parser.add_argument("--mode", choices=("optimizer", "demo", "claude"), default="optimizer")
    parser.add_argument("--output", type=Path, default=ROOT / "output" / "evaluation" / "evaluation_results.json")
    args = parser.parse_args()
    report = run_evaluation(args.mode)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    print(f"Full results: {args.output}")


if __name__ == "__main__":
    main()
