"""LLM model resolution: LLM_MODEL env must reach every stage (issue #37)."""
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

_SPEC = importlib.util.spec_from_file_location(
    "llm_model_under_test", _REPO / "paper2slides" / "utils" / "llm_model.py"
)
_mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_mod)
get_llm_model = _mod.get_llm_model


class GetLLMModelTests(unittest.TestCase):
    def setUp(self):
        self._patched = {}
        for key in ("LLM_MODEL", "RAG_LLM_BASE_URL"):
            self._patched[key] = os.environ.pop(key, None)

    def tearDown(self):
        for key, value in self._patched.items():
            if value is not None:
                os.environ[key] = value

    def test_env_model_wins(self):
        os.environ["LLM_MODEL"] = "deepseek-v4-pro"
        self.assertEqual(get_llm_model(), "deepseek-v4-pro")

    def test_openai_default_without_base_url(self):
        self.assertEqual(get_llm_model(), "gpt-4o-mini")

    def test_stage_defaults_keep_their_cloud_default(self):
        os.environ["LLM_MODEL"] = ""
        self.assertEqual(get_llm_model(default="gpt-4o"), "gpt-4o")

    def test_custom_default_without_base_url_is_silent(self):
        os.environ["LLM_MODEL"] = ""
        # No RAG_LLM_BASE_URL: gpt-4o default is valid against api.openai.com
        self.assertEqual(get_llm_model(default="gpt-4o"), "gpt-4o")


class StageHardcodeTests(unittest.TestCase):
    """The exact call sites from issue #37 must not carry hardcoded model names."""

    def _read(self, rel):
        return (_REPO / rel).read_text(encoding="utf-8")

    def test_summary_stage_uses_resolver(self):
        src = self._read("paper2slides/core/stages/summary_stage.py")
        self.assertIn("get_llm_model()", src)
        self.assertNotIn('model="gpt-4o-mini"', src)

    def test_rag_stage_fast_queries_use_resolver(self):
        src = self._read("paper2slides/core/stages/rag_stage.py")
        self.assertIn("get_llm_model(default=\"gpt-4o\")", src)
        self.assertIn("model=model,", src)
        self.assertNotIn("Running queries with GPT-4o", src)

    def test_plan_stage_uses_resolver(self):
        src = self._read("paper2slides/core/stages/plan_stage.py")
        self.assertIn("get_llm_model(default=\"gpt-4o\")", src)

    def test_content_planner_prefers_explicit_model(self):
        src = self._read("paper2slides/generator/content_planner.py")
        self.assertIn("model or get_llm_model", src)
        self.assertNotIn('model: str = "gpt-4o"', src)

    def test_custom_style_uses_resolver(self):
        src = self._read("paper2slides/generator/image_generator.py")
        self.assertIn("model or get_llm_model()", src)
        self.assertNotIn("openai/gpt-4o-mini", src)

    def test_custom_style_retries_without_json_mode(self):
        src = self._read("paper2slides/generator/image_generator.py")
        self.assertIn("for use_json in [True, False]", src)


if __name__ == "__main__":
    unittest.main()