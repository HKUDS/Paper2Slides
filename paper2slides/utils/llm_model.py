"""
LLM model resolution utilities
"""
import logging
import os

logger = logging.getLogger(__name__)

DEFAULT_LLM_MODEL = "gpt-4o-mini"


def get_llm_model(default: str = DEFAULT_LLM_MODEL) -> str:
    """Resolve the chat model from LLM_MODEL env with a fail-fast warning.

    Every stage used to fall back to a hardcoded gpt-4o-family model name.
    Pointing RAG_LLM_BASE_URL at DeepSeek or a local server without setting
    LLM_MODEL then crashed with cryptic 400 errors -- so warn loudly here.
    """
    model = os.getenv("LLM_MODEL", "").strip()
    if model:
        return model

    base_url = os.getenv("RAG_LLM_BASE_URL", "").strip()
    if base_url and "api.openai.com" not in base_url:
        logger.warning(
            "RAG_LLM_BASE_URL points at %s but LLM_MODEL is not set -- "
            "falling back to '%s', which that endpoint most likely does not "
            "serve. Set LLM_MODEL to the model name your endpoint expects "
            "(e.g. deepseek-v4-pro or a local model tag).",
            base_url,
            default,
        )
    return default