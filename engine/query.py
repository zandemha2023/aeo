"""
Query functions for AI engines.

Makes actual API calls to ChatGPT, Claude, Perplexity, and Gemini.
"""

import asyncio
from datetime import datetime
from typing import Literal

import anthropic
import httpx
import structlog

from config import get_settings
from knowledge.schemas import AIQuery, AIResponse

logger = structlog.get_logger()

EngineType = Literal["chatgpt", "claude", "perplexity", "gemini"]


async def query_engine(
    engine: EngineType,
    query: AIQuery,
) -> AIResponse:
    """
    Query a specific AI engine.

    Args:
        engine: The engine to query
        query: The query to send

    Returns:
        AIResponse with the engine's response
    """
    start_time = datetime.utcnow()
    logger.info("querying_engine", engine=engine, query=query.query_text[:50])

    try:
        if engine == "chatgpt":
            response = await _query_chatgpt(query)
        elif engine == "claude":
            response = await _query_claude(query)
        elif engine == "perplexity":
            response = await _query_perplexity(query)
        elif engine == "gemini":
            response = await _query_gemini(query)
        else:
            raise ValueError(f"Unknown engine: {engine}")

        latency = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        response.latency_ms = latency

        logger.info(
            "engine_response_received",
            engine=engine,
            latency_ms=latency,
            response_length=len(response.response_text),
        )
        return response

    except Exception as e:
        logger.error("engine_query_failed", engine=engine, error=str(e))
        return AIResponse(
            engine=engine,
            query=query.query_text,
            response_text="",
            sources_cited=[],
            error=str(e),
        )


async def query_all_engines(
    query: AIQuery,
    engines: list[EngineType] | None = None,
) -> list[AIResponse]:
    """
    Query multiple AI engines in parallel.

    Args:
        query: The query to send
        engines: List of engines to query (defaults to all)

    Returns:
        List of AIResponses from each engine
    """
    if engines is None:
        engines = ["chatgpt", "claude", "perplexity", "gemini"]

    logger.info("querying_all_engines", engines=engines, query=query.query_text[:50])

    tasks = [query_engine(engine, query) for engine in engines]
    responses = await asyncio.gather(*tasks, return_exceptions=True)

    # Convert exceptions to error responses
    results = []
    for engine, response in zip(engines, responses):
        if isinstance(response, Exception):
            results.append(
                AIResponse(
                    engine=engine,
                    query=query.query_text,
                    response_text="",
                    sources_cited=[],
                    error=str(response),
                )
            )
        else:
            results.append(response)

    return results


async def _query_chatgpt(query: AIQuery) -> AIResponse:
    """Query OpenAI's ChatGPT."""
    settings = get_settings()

    if not settings.openai_api_key:
        return AIResponse(
            engine="chatgpt",
            query=query.query_text,
            response_text="",
            sources_cited=[],
            error="OpenAI API key not configured",
        )

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "gpt-4o",
                "messages": [
                    {
                        "role": "user",
                        "content": query.query_text,
                    }
                ],
                "max_tokens": 2048,
            },
        )
        response.raise_for_status()
        data = response.json()

        content = data["choices"][0]["message"]["content"]

        return AIResponse(
            engine="chatgpt",
            query=query.query_text,
            response_text=content,
            sources_cited=[],  # ChatGPT doesn't cite sources by default
        )


async def _query_claude(query: AIQuery) -> AIResponse:
    """Query Anthropic's Claude."""
    settings = get_settings()

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    response = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2048,
        messages=[
            {
                "role": "user",
                "content": query.query_text,
            }
        ],
    )

    content = response.content[0].text if response.content else ""

    return AIResponse(
        engine="claude",
        query=query.query_text,
        response_text=content,
        sources_cited=[],
    )


async def _query_perplexity(query: AIQuery) -> AIResponse:
    """Query Perplexity AI."""
    settings = get_settings()

    if not settings.perplexity_api_key:
        return AIResponse(
            engine="perplexity",
            query=query.query_text,
            response_text="",
            sources_cited=[],
            error="Perplexity API key not configured",
        )

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            "https://api.perplexity.ai/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.perplexity_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "llama-3.1-sonar-large-128k-online",
                "messages": [
                    {
                        "role": "user",
                        "content": query.query_text,
                    }
                ],
            },
        )
        response.raise_for_status()
        data = response.json()

        content = data["choices"][0]["message"]["content"]

        # Perplexity includes citations
        citations = data.get("citations", [])

        return AIResponse(
            engine="perplexity",
            query=query.query_text,
            response_text=content,
            sources_cited=citations,
        )


async def _query_gemini(query: AIQuery) -> AIResponse:
    """Query Google's Gemini."""
    settings = get_settings()

    if not settings.google_api_key:
        return AIResponse(
            engine="gemini",
            query=query.query_text,
            response_text="",
            sources_cited=[],
            error="Google API key not configured",
        )

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent?key={settings.google_api_key}",
            headers={"Content-Type": "application/json"},
            json={
                "contents": [
                    {
                        "parts": [{"text": query.query_text}],
                    }
                ],
                "generationConfig": {
                    "maxOutputTokens": 2048,
                },
            },
        )
        response.raise_for_status()
        data = response.json()

        # Extract text from Gemini response
        content = ""
        if "candidates" in data and data["candidates"]:
            parts = data["candidates"][0].get("content", {}).get("parts", [])
            content = "".join(p.get("text", "") for p in parts)

        return AIResponse(
            engine="gemini",
            query=query.query_text,
            response_text=content,
            sources_cited=[],
        )
