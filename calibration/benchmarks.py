"""
Benchmark definitions for AEO calibration.

This module defines what "good" looks like across different dimensions:
- Absolute benchmarks (universal standards)
- Industry benchmarks (category-specific)
- Query type benchmarks (expectations by query type)
"""

from pydantic import BaseModel


class AbsoluteBenchmarks(BaseModel):
    """Universal standards across all clients."""

    # Mention Rates - % of relevant queries where mentioned
    mention_rate_excellent: float = 0.70  # 70%+ = excellent
    mention_rate_good: float = 0.50  # 50-69% = good
    mention_rate_fair: float = 0.30  # 30-49% = fair
    mention_rate_poor: float = 0.15  # 15-29% = poor
    # Below 15% = critical

    # Recommendation Rates - when mentioned, are you recommended?
    recommendation_rate_excellent: float = 0.60
    recommendation_rate_good: float = 0.40
    recommendation_rate_fair: float = 0.25

    # Citation Rates - is your content directly cited?
    citation_rate_excellent: float = 0.30
    citation_rate_good: float = 0.15
    citation_rate_fair: float = 0.05

    # Accuracy - of AI statements about you
    accuracy_rate_acceptable: float = 0.90  # Below this = problem

    # Sentiment thresholds
    sentiment_positive_min: float = 0.50  # At least 50% positive
    sentiment_neutral_max: float = 0.40  # Up to 40% neutral is fine
    sentiment_negative_max: float = 0.10  # Max 10% negative


class IndustryBenchmark(BaseModel):
    """Benchmarks specific to an industry/category."""

    industry: str
    average_mention_rate: float
    average_recommendation_rate: float
    top_performer_mention_rate: float
    typical_content_types: list[str]
    authority_sources_that_matter: list[str]
    notes: str


class QueryTypeBenchmark(BaseModel):
    """Benchmarks for different query types."""

    query_type: str
    expected_mention_rate: float
    notes: str


# Singleton instance of absolute benchmarks
ABSOLUTE_BENCHMARKS = AbsoluteBenchmarks()


# Industry-specific benchmarks
INDUSTRY_BENCHMARKS: dict[str, IndustryBenchmark] = {
    "saas_b2b": IndustryBenchmark(
        industry="SaaS B2B",
        average_mention_rate=0.45,
        average_recommendation_rate=0.35,
        top_performer_mention_rate=0.75,
        typical_content_types=[
            "comparison_pages",
            "feature_documentation",
            "integration_guides",
            "case_studies",
            "roi_calculators",
        ],
        authority_sources_that_matter=[
            "g2",
            "capterra",
            "trustradius",
            "gartner",
            "forrester",
            "industry_publications",
        ],
        notes="High mention rates expected due to frequent 'what tool' queries",
    ),
    "d2c_retail": IndustryBenchmark(
        industry="D2C Retail",
        average_mention_rate=0.25,
        average_recommendation_rate=0.20,
        top_performer_mention_rate=0.55,
        typical_content_types=[
            "product_pages",
            "buying_guides",
            "comparisons",
            "reviews_aggregation",
        ],
        authority_sources_that_matter=[
            "wirecutter",
            "consumer_reports",
            "reddit",
            "youtube_reviews",
        ],
        notes="Lower rates - fewer tool queries, more brand-specific searches",
    ),
    "professional_services": IndustryBenchmark(
        industry="Professional Services",
        average_mention_rate=0.35,
        average_recommendation_rate=0.30,
        top_performer_mention_rate=0.60,
        typical_content_types=[
            "thought_leadership",
            "methodology_content",
            "case_studies",
            "industry_reports",
        ],
        authority_sources_that_matter=[
            "industry_publications",
            "conferences",
            "academic_citations",
            "client_testimonials",
        ],
        notes="Mid rates - expertise queries drive visibility",
    ),
    "healthcare": IndustryBenchmark(
        industry="Healthcare",
        average_mention_rate=0.30,
        average_recommendation_rate=0.25,
        top_performer_mention_rate=0.50,
        typical_content_types=[
            "clinical_content",
            "research_summaries",
            "patient_education",
            "provider_resources",
        ],
        authority_sources_that_matter=[
            "pubmed",
            "medical_journals",
            "cdc",
            "medical_associations",
        ],
        notes="Lower rates but highest accuracy stakes - misinformation is critical",
    ),
    "fintech": IndustryBenchmark(
        industry="Fintech",
        average_mention_rate=0.40,
        average_recommendation_rate=0.30,
        top_performer_mention_rate=0.65,
        typical_content_types=[
            "product_comparisons",
            "educational_content",
            "compliance_guides",
            "api_documentation",
        ],
        authority_sources_that_matter=[
            "fintech_publications",
            "financial_media",
            "regulatory_bodies",
            "developer_communities",
        ],
        notes="Trust and security messaging critical for recommendations",
    ),
    "ecommerce_platform": IndustryBenchmark(
        industry="E-commerce Platform",
        average_mention_rate=0.50,
        average_recommendation_rate=0.40,
        top_performer_mention_rate=0.80,
        typical_content_types=[
            "platform_comparisons",
            "migration_guides",
            "integration_docs",
            "success_stories",
        ],
        authority_sources_that_matter=[
            "builtwith",
            "ecommerce_publications",
            "developer_forums",
            "agency_recommendations",
        ],
        notes="High query volume for platform recommendations",
    ),
}


# Query type benchmarks
QUERY_TYPE_BENCHMARKS: dict[str, QueryTypeBenchmark] = {
    "best_category": QueryTypeBenchmark(
        query_type="best [category]",
        expected_mention_rate=0.60,
        notes="Should appear if relevant to category - these are high-intent queries",
    ),
    "brand_info": QueryTypeBenchmark(
        query_type="what is [brand]",
        expected_mention_rate=0.95,
        notes="MUST appear with high accuracy - direct brand queries",
    ),
    "comparison": QueryTypeBenchmark(
        query_type="[brand] vs [competitor]",
        expected_mention_rate=0.90,
        notes="Should appear balanced - both brands typically mentioned",
    ),
    "how_to": QueryTypeBenchmark(
        query_type="how to [task]",
        expected_mention_rate=0.40,
        notes="Depends on content quality and authority in the topic",
    ),
    "review": QueryTypeBenchmark(
        query_type="[brand] review",
        expected_mention_rate=0.85,
        notes="Should have positive/accurate information present",
    ),
    "alternatives": QueryTypeBenchmark(
        query_type="[brand] alternatives",
        expected_mention_rate=0.80,
        notes="Competitor opportunity - should monitor and respond",
    ),
    "pricing": QueryTypeBenchmark(
        query_type="[brand] pricing",
        expected_mention_rate=0.90,
        notes="Must be accurate - pricing misinformation is high impact",
    ),
}


def get_benchmark_for_industry(industry: str) -> IndustryBenchmark | None:
    """Get industry benchmark, with fuzzy matching."""
    # Direct match
    if industry.lower().replace(" ", "_") in INDUSTRY_BENCHMARKS:
        return INDUSTRY_BENCHMARKS[industry.lower().replace(" ", "_")]

    # Fuzzy match
    for key, benchmark in INDUSTRY_BENCHMARKS.items():
        if industry.lower() in benchmark.industry.lower():
            return benchmark

    return None


def get_benchmark_for_query_type(query_type: str) -> QueryTypeBenchmark | None:
    """Get query type benchmark."""
    return QUERY_TYPE_BENCHMARKS.get(query_type)
