# MacroFit

MacroFit is a course-project prototype for people who eat out and want a practical meal plan that fits a daily budget and macro targets.

The architecture deliberately separates two jobs:

1. **Constraint solver (the knife):** enumerates meal combinations and creates a shortlist that satisfies budget, protein, and carbohydrate constraints whenever possible.
2. **Foundation model (the sword):** chooses *within the exact same shortlist* using human preferences such as variety, cuisine, and whether the meals sound enjoyable, then explains its choice.

This separation answers the central evaluation question: if a solver already guarantees the numbers, what does the model add?

## Run locally

No Python packages are required.

```bash
python3 app.py
```

Open <http://localhost:8000>.

The optimizer and demo preference mode work immediately. To use a real Claude call:

```bash
export ANTHROPIC_API_KEY="your-key"
export ANTHROPIC_MODEL="your-enabled-model-id"
python3 app.py
```

The API key stays on the local server and is never sent to the browser or written to disk.

## What is in the prototype

- 60 synthetic menu items across 10 dummy NTU-area outlets.
- Per-item price, energy, protein, carbohydrate, fat, fibre, and sodium.
- Nutrition mapping method, source family, mapper, date, and confidence for every row.
- Exact enumeration of 1-3 item daily plans, with fixed dummy distance from NTU North Spine included in ranking.
- A five-plan shortlist with explicit feasibility and normalized distance scores.
- Optional Claude ranking, restricted to that shortlist.
- A blind A/B evaluator with 20 fixed user cases, randomized left/right display, local progress, and CSV export.
- A methodology/data page that makes the dummy-data limitations visible.

## Evaluation protocol

For each of the 20 fixed cases:

1. The optimizer produces the shortlist and selects its top mathematical plan.
2. Claude receives the *same shortlist* plus the case's stated food preferences and chooses one plan.
3. The app randomizes the two plans as A and B and hides which system chose which.
4. The evaluator answers: **Which one would you actually eat?**
5. After all cases, export the CSV and report the model win rate, optimizer win rate, ties, and valid sample size.

The primary model-value metric is:

`model preference win rate = model wins / (model wins + optimizer wins)`

Ties are reported separately. A 20-case exercise is directional rather than statistically conclusive; it is appropriate for the course prototype but should not be presented as a population result.

If demo mode is used, the output is labelled **demo heuristic** and must not be reported as LLM evidence.

## Data statement

The dataset is manually authored synthetic data for pipeline validation, not a representation of current restaurant prices or medically reliable nutrition.

- **Size:** 60 items, 10 outlets, 6 items per outlet.
- **Dataset 1:** `data/menu.json` contains item, outlet, price, NTU location, fixed distance, and walking time.
- **Dataset 2:** `data/nutrition.json` contains energy, macros, sodium, matching method, source family, mapper, date, and confidence.
- **Macros:** kcal, protein, carbohydrates, fat, fibre, and sodium per listed serving.
- **Mapping owner:** Nagur Pavan (project author).
- **Method:** nearest generic dish/category match, followed by explicit portion scaling where needed.
- **Source families:** [USDA FoodData Central](https://fdc.nal.usda.gov/) and Singapore's [HealthHub nutrition guidance](https://www.healthhub.sg/programmes/nutrition-hub).
- **Important limitation:** source-family labels document the intended reference type; this dummy set has not been independently dietitian-verified. The row-level confidence field exposes uncertainty instead of hiding it.

Before any real-world pilot, replace the dummy prices with timestamped shop observations and have the nutrition mapping independently reviewed.

## Tests

```bash
python3 -m unittest discover -s tests -v
python3 evaluate.py --mode optimizer
```

The evaluation command writes a detailed JSON report under `output/evaluation/`. Use `--mode demo` to exercise the transparent preference heuristic or `--mode claude` after configuring Claude. The automated report checks constraints; the web app's blind A/B study measures which recommendation a human would actually eat.

## Project structure

```text
app.py                 local web server and Claude API adapter
core.py                dataset loading and deterministic optimizer
data/menu.json         60 item/outlet/price/location/distance records
data/nutrition.json    60 macro and nutrition-provenance records
data/eval_cases.json   20 fixed blind-evaluation cases
evaluate.py            backend evaluation runner and JSON report writer
static/                browser interface
tests/                 optimizer tests
```

## Responsible-use boundaries

MacroFit is a planning aid, not medical or clinical nutrition advice. Nutrition and prices are estimates. The model is not allowed to invent menu items or change numerical values; its output is validated against shortlist IDs, and invalid output falls back safely to the optimizer choice.

## Tool contracts and security guardrails

- `config/tool_descriptors.json` defines strict input schemas, output contracts, preconditions, and tool-specific safety rules for the five planned tools.
- `config/agent_guardrails.json` defines the assistant scope, trust boundaries, prompt-injection policy, confirmation requirements, health boundaries, privacy rules, and monitoring events.
- `guardrails.py` enforces the allowlist, rejects unknown fields and oversized payloads, validates ranges and item IDs, detects common prompt-injection attempts, prevents model selections outside a server shortlist, and requires confirmation for consumption or above-target extra food.

Prompt wording is not the security boundary. The server owns the datasets, calculations, state, and tool permissions. All user and model text is treated as untrusted data.
