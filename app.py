from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from core import ROOT, demo_preference_pick, load_eval_cases, load_menu, optimize
from guardrails import validate_model_selection, validate_untrusted_text


MENU = load_menu()
EVAL_CASES = load_eval_cases()


def claude_rank(shortlist: list[dict], preferences: str) -> dict:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    model = os.environ.get("ANTHROPIC_MODEL", "").strip()
    if not api_key or not model:
        raise RuntimeError("Set both ANTHROPIC_API_KEY and ANTHROPIC_MODEL on the server to enable Claude.")

    preferences = validate_untrusted_text(preferences, "food preferences")
    compact = [{
        "plan_id": p["plan_id"],
        "items": [f"{x['item']} ({x['shop']}, {x['cuisine']})" for x in p["items"]],
        "totals": p["totals"],
        "feasible": p["feasible"],
    } for p in shortlist]
    prompt = f"""You are the preference layer in MacroFit. A deterministic solver created the shortlist below.
Choose exactly one listed plan that this person would most likely enjoy and follow. Do not redo the macro math, invent items, or change values.

Preferences: {preferences or 'No extra preferences stated.'}
Shortlist: {json.dumps(compact, ensure_ascii=True)}

Return only JSON in this form:
{{"plan_id":"an exact listed plan_id","reason":"one or two concise sentences tied to stated preferences"}}"""
    body = json.dumps({
        "model": model,
        "max_tokens": 260,
        "temperature": 0.2,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    request = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:500]
        raise RuntimeError(f"Claude API returned {exc.code}: {detail}") from exc

    text = "".join(x.get("text", "") for x in payload.get("content", []) if x.get("type") == "text")
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise RuntimeError("Claude did not return a JSON object.")
    result = json.loads(match.group(0))
    valid_ids = {p["plan_id"] for p in shortlist}
    validate_model_selection(result.get("plan_id", ""), valid_ids)
    return {"plan_id": result["plan_id"], "reason": str(result.get("reason", ""))[:500], "mode": "claude"}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / "static"), **kwargs)

    def log_message(self, format, *args):
        print(f"[MacroFit] {self.address_string()} {format % args}")

    def _json(self, payload, status=200):
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/api/meta":
            self._json({
                "menu_count": len(MENU),
                "shop_count": len({x.shop for x in MENU}),
                "eval_count": len(EVAL_CASES),
                "claude_ready": bool(os.environ.get("ANTHROPIC_API_KEY") and os.environ.get("ANTHROPIC_MODEL")),
                "menu": [x.__dict__ for x in MENU],
            })
            return
        if self.path == "/api/eval-cases":
            self._json(EVAL_CASES)
            return
        return super().do_GET()

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length > 32_000:
                self._json({"error": "Request is too large."}, 413)
                return
            body = json.loads(self.rfile.read(length) or b"{}")
            if self.path == "/api/optimize":
                result = optimize(MENU, float(body["budget"]), float(body["protein_g"]), float(body["carbs_g"]))
                self._json(result)
                return
            if self.path in ("/api/rank", "/api/eval-pair"):
                body["preferences"] = validate_untrusted_text(str(body.get("preferences", "")), "food preferences")
                solution = optimize(MENU, float(body["budget"]), float(body["protein_g"]), float(body["carbs_g"]))
                mode = body.get("mode", "claude")
                ranking = demo_preference_pick(solution["shortlist"], body.get("preferences", "")) if mode == "demo" else claude_rank(solution["shortlist"], body.get("preferences", ""))
                model_pick = next(p for p in solution["shortlist"] if p["plan_id"] == ranking["plan_id"])
                self._json({"solution": solution, "model_pick": model_pick, "ranking": ranking})
                return
            self._json({"error": "Not found"}, 404)
        except (KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
            self._json({"error": str(exc)}, 400)
        except Exception as exc:
            self._json({"error": str(exc)}, 502)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    print(f"MacroFit is running at http://localhost:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
