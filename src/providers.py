"""Optional LangChain chat-model selection shared by extraction and Q&A."""

from __future__ import annotations

import os
from typing import Any


def provider_config() -> tuple[str, str] | None:
    provider = os.getenv("LLM_PROVIDER", "").strip().lower()
    openai_key = os.getenv("OPENAI_API_KEY")
    gemini_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if provider in ("openai", "gemini"):
        key = openai_key if provider == "openai" else gemini_key
        return (provider, key) if key else None
    if openai_key:
        return "openai", openai_key
    if gemini_key:
        return "gemini", gemini_key
    return None


def create_chat_model(provider: str, temperature: float = 0.0) -> Any:
    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model="gpt-4o-mini", temperature=temperature)
    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=temperature)
    raise ValueError(f"Unsupported LLM provider: {provider}")
