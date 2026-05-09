from langchain_openai import ChatOpenAI

from app.config import settings


def get_chat_model() -> ChatOpenAI:
    """LangChain ChatOpenAI wrapper for the Qwen3 chat model."""
    return ChatOpenAI(
        model=settings.qwen3_model_id,
        base_url=settings.qwen3_llm_mux_url,
        api_key=settings.qwen3_llm_mux_api_key or "not-needed",
        temperature=0.2,
        extra_body={"chat_template_kwargs": {"enable_thinking": True}},
    )


def get_keyword_extraction_model() -> ChatOpenAI:
    """LangChain ChatOpenAI wrapper for the GPT-OSS keyword extraction model."""
    return ChatOpenAI(
        model=settings.gpt_oss_model_id,
        base_url=settings.gpt_oss_llm_url,
        api_key=settings.qwen3_llm_mux_api_key or "not-needed",
        temperature=0.1,
        max_tokens=600,
    )


def get_langfuse_handler():
    """Initialize the global Langfuse client and return a CallbackHandler for LangChain tracing.
    
    In langfuse v4, the CallbackHandler relies on a pre-configured global Langfuse client
    that reads credentials from environment variables or explicit initialization.
    """
    from langfuse import Langfuse
    from langfuse.langchain import CallbackHandler

    # Initialize the global Langfuse client (reads from env vars as fallback)
    Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
    )

    return CallbackHandler()
