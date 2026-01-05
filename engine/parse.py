"""
Response parsing for AI engine outputs.

Analyzes AI responses to extract brand mentions, sentiment, accuracy, etc.
"""

import re
from datetime import datetime

import anthropic
import structlog

from config import get_settings
from knowledge.schemas import AIQuery, AIResponse, BrandMention, MentionQuality

logger = structlog.get_logger()


def extract_brand_mentions(
    response: AIResponse,
    query: AIQuery,
) -> list[BrandMention]:
    """
    Extract brand mentions from an AI response.

    This does basic extraction. Use parse_response for deeper analysis.
    """
    mentions = []
    response_lower = response.response_text.lower()

    for i, brand in enumerate(query.brand_names):
        brand_lower = brand.lower()

        if brand_lower in response_lower:
            # Find the position (how early in the list of brands)
            position = _find_mention_position(response.response_text, brand, query.brand_names)

            mentions.append(
                BrandMention(
                    query=query.query_text,
                    engine=response.engine,
                    mentioned=True,
                    position=position,
                    context=_extract_context(response.response_text, brand),
                    sources_cited=response.sources_cited,
                    competitors_mentioned=[
                        c for c in query.competitor_names if c.lower() in response_lower
                    ],
                    response_text=response.response_text,
                )
            )
        else:
            mentions.append(
                BrandMention(
                    query=query.query_text,
                    engine=response.engine,
                    mentioned=False,
                    context="",
                    sources_cited=[],
                    competitors_mentioned=[
                        c for c in query.competitor_names if c.lower() in response_lower
                    ],
                    response_text=response.response_text,
                )
            )

    return mentions


def _find_mention_position(text: str, brand: str, all_brands: list[str]) -> int:
    """Find the position of a brand mention relative to other brands."""
    text_lower = text.lower()
    brand_lower = brand.lower()

    brand_idx = text_lower.find(brand_lower)
    if brand_idx == -1:
        return 0

    # Count how many other brands appear before this one
    position = 1
    for other_brand in all_brands:
        if other_brand.lower() == brand_lower:
            continue
        other_idx = text_lower.find(other_brand.lower())
        if other_idx != -1 and other_idx < brand_idx:
            position += 1

    return position


def _extract_context(text: str, brand: str) -> str:
    """Extract the sentence containing the brand mention."""
    # Find the brand mention (case insensitive)
    idx = text.lower().find(brand.lower())
    if idx == -1:
        return ""

    # Find sentence boundaries
    start = max(0, text.rfind(".", 0, idx) + 1)
    end = text.find(".", idx)
    if end == -1:
        end = min(len(text), idx + 200)
    else:
        end += 1

    return text[start:end].strip()


async def parse_response(
    response: AIResponse,
    query: AIQuery,
) -> BrandMention:
    """
    Perform deep analysis of an AI response using LLM.

    Analyzes sentiment, accuracy, recommendation status, etc.
    """
    if not response.response_text:
        return BrandMention(
            query=query.query_text,
            engine=response.engine,
            mentioned=False,
            context="",
            response_text="",
        )

    settings = get_settings()
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    primary_brand = query.brand_names[0] if query.brand_names else "the brand"

    analysis_prompt = f"""Analyze this AI response for brand mentions of "{primary_brand}".

QUERY: {query.query_text}

RESPONSE:
{response.response_text}

Analyze and respond with a JSON object:
{{
    "mentioned": true/false,  // Is {primary_brand} mentioned?
    "position": number or null,  // Position in list if multiple options (1 = first)
    "recommended": true/false,  // Is {primary_brand} explicitly recommended?
    "sentiment": "positive"/"neutral"/"negative",  // Sentiment toward {primary_brand}
    "accuracy": "accurate"/"inaccurate"/"partially_accurate"/"unknown",  // Accuracy of info about {primary_brand}
    "context": "string",  // The exact text mentioning {primary_brand}
    "competitors_mentioned": ["list", "of", "competitors"],  // Other brands mentioned
    "mention_quality": {{
        "mentioned_first": true/false,
        "mentioned_prominently": true/false,
        "framed_positively": true/false,
        "recommended": true/false,
        "content_cited": true/false
    }}
}}

Respond ONLY with the JSON object."""

    try:
        api_response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[{"role": "user", "content": analysis_prompt}],
        )

        content = api_response.content[0].text

        # Extract JSON from response
        import json

        # Try to find JSON in the response
        json_match = re.search(r"\{[\s\S]*\}", content)
        if json_match:
            data = json.loads(json_match.group())
        else:
            logger.warning("no_json_in_response", response=content[:200])
            return _basic_mention_analysis(response, query)

        # Build MentionQuality
        mq_data = data.get("mention_quality", {})
        mention_quality = MentionQuality(
            mentioned_first=mq_data.get("mentioned_first", False),
            mentioned_prominently=mq_data.get("mentioned_prominently", False),
            recommended=data.get("recommended", False),
            framed_positively=mq_data.get("framed_positively", False),
            content_cited=mq_data.get("content_cited", False),
        )

        return BrandMention(
            query=query.query_text,
            engine=response.engine,
            mentioned=data.get("mentioned", False),
            position=data.get("position"),
            recommended=data.get("recommended", False),
            sentiment=data.get("sentiment"),
            accuracy=data.get("accuracy"),
            context=data.get("context", ""),
            sources_cited=response.sources_cited,
            competitors_mentioned=data.get("competitors_mentioned", []),
            response_text=response.response_text,
        )

    except Exception as e:
        logger.error("parse_response_failed", error=str(e))
        return _basic_mention_analysis(response, query)


def _basic_mention_analysis(response: AIResponse, query: AIQuery) -> BrandMention:
    """Fallback to basic regex-based analysis."""
    primary_brand = query.brand_names[0] if query.brand_names else ""
    mentioned = primary_brand.lower() in response.response_text.lower()

    return BrandMention(
        query=query.query_text,
        engine=response.engine,
        mentioned=mentioned,
        context=_extract_context(response.response_text, primary_brand) if mentioned else "",
        sources_cited=response.sources_cited,
        response_text=response.response_text,
    )


def calculate_mention_quality_score(mention: BrandMention) -> float:
    """Calculate a quality score for a mention."""
    if not mention.mentioned:
        return 0.0

    score = 0.0

    # Position bonus
    if mention.position == 1:
        score += 25
    elif mention.position and mention.position <= 3:
        score += 15

    # Recommendation bonus
    if mention.recommended:
        score += 30

    # Sentiment bonus
    if mention.sentiment == "positive":
        score += 20
    elif mention.sentiment == "neutral":
        score += 10

    # Accuracy bonus
    if mention.accuracy == "accurate":
        score += 15
    elif mention.accuracy == "partially_accurate":
        score += 5

    # Citation bonus
    if mention.sources_cited:
        score += 10

    return min(100.0, score)
