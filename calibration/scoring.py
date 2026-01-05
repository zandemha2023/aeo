"""
Scoring algorithms for AEO metrics.

Converts raw metrics into calibrated scores and grades.
"""

from knowledge.schemas import (
    AEOMetrics,
    CitabilitySignals,
    HealthGrade,
    MentionQuality,
)

from calibration.benchmarks import ABSOLUTE_BENCHMARKS


def calculate_health_score(metrics: AEOMetrics) -> float:
    """
    Calculate overall AEO health score (0-100).

    Weights different metrics based on importance.
    """
    b = ABSOLUTE_BENCHMARKS

    # Mention rate score (35% weight)
    if metrics.mention_rate >= b.mention_rate_excellent:
        mention_score = 100
    elif metrics.mention_rate >= b.mention_rate_good:
        mention_score = 80
    elif metrics.mention_rate >= b.mention_rate_fair:
        mention_score = 60
    elif metrics.mention_rate >= b.mention_rate_poor:
        mention_score = 40
    else:
        mention_score = 20

    # Recommendation rate score (25% weight)
    if metrics.recommendation_rate >= b.recommendation_rate_excellent:
        rec_score = 100
    elif metrics.recommendation_rate >= b.recommendation_rate_good:
        rec_score = 75
    elif metrics.recommendation_rate >= b.recommendation_rate_fair:
        rec_score = 50
    else:
        rec_score = 25

    # Citation rate score (20% weight)
    if metrics.citation_rate >= b.citation_rate_excellent:
        cite_score = 100
    elif metrics.citation_rate >= b.citation_rate_good:
        cite_score = 70
    elif metrics.citation_rate >= b.citation_rate_fair:
        cite_score = 40
    else:
        cite_score = 20

    # Accuracy score (15% weight) - critical, heavily penalizes poor accuracy
    if metrics.accuracy_rate >= 0.98:
        accuracy_score = 100
    elif metrics.accuracy_rate >= b.accuracy_rate_acceptable:
        accuracy_score = 80
    elif metrics.accuracy_rate >= 0.80:
        accuracy_score = 50
    else:
        accuracy_score = 0  # Critical issue

    # Sentiment score (5% weight)
    positive = metrics.sentiment_breakdown.get("positive", 0)
    negative = metrics.sentiment_breakdown.get("negative", 0)

    if positive >= b.sentiment_positive_min and negative <= b.sentiment_negative_max:
        sentiment_score = 100
    elif negative <= 0.20:
        sentiment_score = 70
    elif negative <= 0.30:
        sentiment_score = 40
    else:
        sentiment_score = 20

    # Weighted average
    total_score = (
        mention_score * 0.35
        + rec_score * 0.25
        + cite_score * 0.20
        + accuracy_score * 0.15
        + sentiment_score * 0.05
    )

    return round(total_score, 1)


def calculate_health_grade(score: float) -> HealthGrade:
    """Convert health score to letter grade."""
    if score >= 90:
        return HealthGrade.A
    elif score >= 80:
        return HealthGrade.B
    elif score >= 70:
        return HealthGrade.C
    elif score >= 60:
        return HealthGrade.D
    else:
        return HealthGrade.F


def score_mention_quality(mention: MentionQuality) -> float:
    """Score a single mention's quality (0-100)."""
    return mention.calculate_score()


def score_citability(signals: CitabilitySignals) -> float:
    """Score content citability (0-100)."""
    return signals.calculate_score()


def assess_trend(current: float, previous: float, threshold: float = 0.05) -> str:
    """Assess trend direction based on change."""
    change = current - previous
    if change > threshold:
        return "improving"
    elif change < -threshold:
        return "declining"
    else:
        return "stable"


def calculate_competitive_score(
    our_rate: float,
    competitor_rates: dict[str, float],
) -> dict[str, float]:
    """
    Calculate relative scores vs competitors.

    Returns dict of competitor -> relative score where:
    - > 0 means we're winning
    - < 0 means we're losing
    - magnitude indicates how much
    """
    results = {}
    for competitor, rate in competitor_rates.items():
        # Normalize to -100 to +100 scale
        if rate == 0:
            results[competitor] = 100.0 if our_rate > 0 else 0.0
        else:
            relative = ((our_rate - rate) / rate) * 100
            results[competitor] = round(max(-100, min(100, relative)), 1)
    return results
