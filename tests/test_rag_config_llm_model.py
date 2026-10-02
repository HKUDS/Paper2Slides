"""APIConfig resolves llm_model through get_llm_model (issue #37)."""
import logging
import os
import sys
import types
import unittest
from contextlib import contextmanager
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

# paper2slides.rag imports lightrag at module level; stub it so the config
# module can be tested without the full RAG stack installed.
if "lightrag" not in sys.modules:
    _lightrag = types.ModuleType("lightrag")
    _lightrag_llm = types.ModuleType("lightrag.llm")
    _lightrag_openai = types.ModuleType("lightrag.llm.openai")
    setattr(_lightrag_openai, "openai_complete_if_cache", lambda *a, **k: None)
    setattr(_lightrag_openai, "openai_embed", lambda *a, **k: None)
    _lightrag_utils = types.ModuleType("lightrag.utils")

    class _EmbeddingFunc:
        def __init__(self, **kwargs):
            pass

    setattr(_lightrag_utils, "EmbeddingFunc", _EmbeddingFunc)
    sys.modules["lightrag"] = _lightrag
    sys.modules["lightrag.llm"] = _lightrag_llm
    sys.modules["lightrag.llm.openai"] = _lightrag_openai
    sys.modules["lightrag.utils"] = _lightrag_utils

from paper2slides.rag.config import APIConfig


@contextmanager
def _capture_warnings(logger_name: str):
    """Python 3.9 stand-in for assertLogs/assertNoLogs (assertLogs is 3.4+
    but has no "no logs" counterpart; assertNoLogs only exists on 3.10+)."""
    records = []
    handler = logging.Handler()
    handler.emit = lambda record: records.append(record)
    logger = logging.getLogger(logger_name)
    logger.addHandler(handler)
    try:
        yield records
    finally:
        logger.removeHandler(handler)


class APIConfigLLMModelTests(unittest.TestCase):
    def setUp(self):
        self._patched = {}
        for key in ("LLM_MODEL", "RAG_LLM_BASE_URL"):
            self._patched[key] = os.environ.pop(key, None)

    def tearDown(self):
        for key, value in self._patched.items():
            if value is not None:
                os.environ[key] = value

    def test_llm_model_env_wins(self):
        os.environ["LLM_MODEL"] = "deepseek-v4-pro"
        self.assertEqual(APIConfig(llm_api_key="k").llm_model, "deepseek-v4-pro")

    def test_deepseek_base_url_without_llm_model_falls_back_with_warning(self):
        os.environ["RAG_LLM_BASE_URL"] = "https://api.deepseek.com/v1"
        with _capture_warnings("paper2slides.utils.llm_model") as records:
            config = APIConfig(llm_api_key="k")
        self.assertTrue(
            any(r.levelno >= logging.WARNING for r in records),
            "expected a WARNING when RAG_LLM_BASE_URL points at DeepSeek without LLM_MODEL",
        )
        self.assertEqual(config.llm_model, "gpt-4o-mini")

    def test_deepseek_base_url_with_llm_model_is_silent(self):
        os.environ["RAG_LLM_BASE_URL"] = "https://api.deepseek.com/v1"
        os.environ["LLM_MODEL"] = "deepseek-v4-pro"
        with _capture_warnings("paper2slides.utils.llm_model") as records:
            config = APIConfig(llm_api_key="k")
        self.assertFalse(
            any(r.levelno >= logging.WARNING for r in records),
            "expected no warning when LLM_MODEL is set",
        )
        self.assertEqual(config.llm_model, "deepseek-v4-pro")

    def test_openai_default_without_base_url_is_silent(self):
        with _capture_warnings("paper2slides.utils.llm_model") as records:
            config = APIConfig(llm_api_key="k")
        self.assertFalse(
            any(r.levelno >= logging.WARNING for r in records),
            "expected no warning against the OpenAI default endpoint",
        )
        self.assertEqual(config.llm_model, "gpt-4o-mini")


if __name__ == "__main__":
    unittest.main()