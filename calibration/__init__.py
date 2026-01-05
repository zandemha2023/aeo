"""Calibration system for AEO benchmarks and scoring."""

from calibration.benchmarks import (
    ABSOLUTE_BENCHMARKS,
    INDUSTRY_BENCHMARKS,
    QUERY_TYPE_BENCHMARKS,
    get_benchmark_for_industry,
)
from calibration.scoring import (
    calculate_health_grade,
    calculate_health_score,
    score_citability,
    score_mention_quality,
)

__all__ = [
    "ABSOLUTE_BENCHMARKS",
    "INDUSTRY_BENCHMARKS",
    "QUERY_TYPE_BENCHMARKS",
    "get_benchmark_for_industry",
    "calculate_health_score",
    "calculate_health_grade",
    "score_mention_quality",
    "score_citability",
]
