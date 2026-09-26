import json
import os
import unittest
from unittest.mock import patch

from app import MENU, openrouter_rank
from core import optimize


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


class OpenRouterTests(unittest.TestCase):
    def test_openrouter_request_and_validated_selection(self):
        shortlist = optimize(MENU, 18, 70, 150)["shortlist"]
        chosen = shortlist[1]["plan_id"]
        payload = {"choices": [{"message": {"content": json.dumps({"plan_id": chosen, "reason": "Matches the stated preference."})}}]}

        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key", "OPENROUTER_MODEL": "qwen/qwen3.8-flash"}, clear=False):
            with patch("urllib.request.urlopen", return_value=FakeResponse(payload)) as mocked:
                result = openrouter_rank(shortlist, "I want chicken and rice")

        request = mocked.call_args.args[0]
        request_body = json.loads(request.data)
        self.assertEqual(request.full_url, "https://openrouter.ai/api/v1/chat/completions")
        self.assertEqual(request_body["model"], "qwen/qwen3.8-flash")
        self.assertEqual(request_body["response_format"]["type"], "json_schema")
        self.assertEqual(result["plan_id"], chosen)
        self.assertEqual(result["mode"], "openrouter")


if __name__ == "__main__":
    unittest.main()
