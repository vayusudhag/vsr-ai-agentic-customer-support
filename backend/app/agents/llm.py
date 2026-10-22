"""Optional LLM provider. With LLM_PROVIDER=none the agents run deterministic
policies so the platform (and its evaluation) works without any API key."""
from functools import lru_cache

from app.config import get_settings


@lru_cache
def get_llm():
    s = get_settings()
    try:
        if s.llm_provider == "openai" and s.openai_api_key:
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(model=s.openai_model, api_key=s.openai_api_key, temperature=0,
                              timeout=s.llm_timeout_seconds, max_retries=1)
        if s.llm_provider == "anthropic" and s.anthropic_api_key:
            from langchain_anthropic import ChatAnthropic

            return ChatAnthropic(model=s.anthropic_model, api_key=s.anthropic_api_key, temperature=0,
                                 timeout=s.llm_timeout_seconds, max_retries=1)
    except Exception:
        return None
    return None


def llm_mode() -> str:
    return get_settings().llm_provider if get_llm() is not None else "deterministic"
