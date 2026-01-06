"""
Quality Gates System for AEO.

Every output must pass quality gates before execution.
Ensures content meets citability, brand alignment, and accuracy standards.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

import structlog

from knowledge.schemas import CitabilitySignals, ClientIntelligenceProfile

logger = structlog.get_logger()


class GateStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    SKIPPED = "skipped"


@dataclass
class GateResult:
    """Result of a single quality gate check."""

    gate_name: str
    status: GateStatus
    score: float | None
    threshold: float | None
    details: str
    recommendations: list[str]

    def to_dict(self) -> dict:
        return {
            "gate_name": self.gate_name,
            "status": self.status.value,
            "score": self.score,
            "threshold": self.threshold,
            "details": self.details,
            "recommendations": self.recommendations,
        }


@dataclass
class QualityGateReport:
    """Complete quality gate report for content."""

    content_id: str
    content_title: str
    overall_passed: bool
    gate_results: list[GateResult]
    total_gates: int
    passed_gates: int
    failed_gates: int
    warnings: int
    created_at: datetime

    def to_dict(self) -> dict:
        return {
            "content_id": self.content_id,
            "content_title": self.content_title,
            "overall_passed": self.overall_passed,
            "gate_results": [g.to_dict() for g in self.gate_results],
            "total_gates": self.total_gates,
            "passed_gates": self.passed_gates,
            "failed_gates": self.failed_gates,
            "warnings": self.warnings,
            "created_at": self.created_at.isoformat(),
        }


class ContentQualityGates:
    """Quality gates for content creation."""

    # Gate thresholds
    MIN_CITABILITY_SCORE = 0.70
    MIN_WORD_COUNT = 500
    MAX_WORD_COUNT = 10000
    MIN_SECTIONS = 2
    MIN_CITABLE_EXCERPTS_RATIO = 0.8
    MAX_FLUFF_RATIO = 0.2

    def __init__(self):
        self._log = logger.bind(component="quality_gates")

    def run_all_gates(
        self,
        content: dict,
        blueprint: dict | None = None,
        client_profile: ClientIntelligenceProfile | None = None,
    ) -> QualityGateReport:
        """
        Run all quality gates on content.

        Args:
            content: Content dict with title, sections, citability_score, etc.
            blueprint: Optional blueprint to check against
            client_profile: Optional client profile for brand alignment

        Returns:
            Complete QualityGateReport
        """
        self._log.info("running_quality_gates", title=content.get("title", ""))

        results = []

        # Gate 1: Citability Score
        results.append(self._check_citability(content))

        # Gate 2: Word Count
        results.append(self._check_word_count(content, blueprint))

        # Gate 3: Structure
        results.append(self._check_structure(content, blueprint))

        # Gate 4: Citable Excerpts
        results.append(self._check_citable_excerpts(content))

        # Gate 5: No Placeholders
        results.append(self._check_no_placeholders(content))

        # Gate 6: Schema Markup
        results.append(self._check_schema_markup(content, blueprint))

        # Gate 7: Brand Alignment (if profile provided)
        if client_profile:
            results.append(self._check_brand_alignment(content, client_profile))

        # Gate 8: Factual Claims
        results.append(self._check_factual_claims(content))

        # Calculate summary
        passed = sum(1 for r in results if r.status == GateStatus.PASSED)
        failed = sum(1 for r in results if r.status == GateStatus.FAILED)
        warnings = sum(1 for r in results if r.status == GateStatus.WARNING)

        # Overall pass requires no failures
        overall_passed = failed == 0

        report = QualityGateReport(
            content_id=content.get("id", ""),
            content_title=content.get("title", ""),
            overall_passed=overall_passed,
            gate_results=results,
            total_gates=len(results),
            passed_gates=passed,
            failed_gates=failed,
            warnings=warnings,
            created_at=datetime.utcnow(),
        )

        self._log.info(
            "quality_gates_complete",
            overall_passed=overall_passed,
            passed=passed,
            failed=failed,
            warnings=warnings,
        )

        return report

    def _check_citability(self, content: dict) -> GateResult:
        """Check citability score meets threshold."""
        score = content.get("citability_score", 0)

        if score >= self.MIN_CITABILITY_SCORE:
            return GateResult(
                gate_name="Citability Score",
                status=GateStatus.PASSED,
                score=score,
                threshold=self.MIN_CITABILITY_SCORE,
                details=f"Citability score {score:.0%} meets threshold",
                recommendations=[],
            )
        elif score >= self.MIN_CITABILITY_SCORE * 0.8:
            return GateResult(
                gate_name="Citability Score",
                status=GateStatus.WARNING,
                score=score,
                threshold=self.MIN_CITABILITY_SCORE,
                details=f"Citability score {score:.0%} is close to threshold",
                recommendations=[
                    "Add more specific statistics and data",
                    "Improve lead sentences to be more citable",
                    "Include authoritative sources",
                ],
            )
        else:
            return GateResult(
                gate_name="Citability Score",
                status=GateStatus.FAILED,
                score=score,
                threshold=self.MIN_CITABILITY_SCORE,
                details=f"Citability score {score:.0%} below threshold of {self.MIN_CITABILITY_SCORE:.0%}",
                recommendations=[
                    "Restructure content with clear hierarchy",
                    "Add specific facts and statistics",
                    "Make each section answer a clear question",
                    "Include expert credentials and sources",
                ],
            )

    def _check_word_count(self, content: dict, blueprint: dict | None) -> GateResult:
        """Check word count meets requirements."""
        word_count = content.get("word_count", 0)

        # Get target from blueprint or use defaults
        min_words = self.MIN_WORD_COUNT
        max_words = self.MAX_WORD_COUNT

        if blueprint:
            target = blueprint.get("target_length", "")
            if "-" in target:
                try:
                    parts = target.replace(",", "").replace("words", "").split("-")
                    min_words = int(parts[0].strip())
                    max_words = int(parts[1].strip()) if len(parts) > 1 else min_words * 2
                except (ValueError, IndexError):
                    pass

        if min_words <= word_count <= max_words:
            return GateResult(
                gate_name="Word Count",
                status=GateStatus.PASSED,
                score=word_count,
                threshold=min_words,
                details=f"Word count {word_count} within range ({min_words}-{max_words})",
                recommendations=[],
            )
        elif word_count < min_words:
            return GateResult(
                gate_name="Word Count",
                status=GateStatus.FAILED,
                score=word_count,
                threshold=min_words,
                details=f"Word count {word_count} below minimum {min_words}",
                recommendations=[
                    f"Add {min_words - word_count} more words",
                    "Expand sections with more detail and examples",
                    "Add additional relevant sections",
                ],
            )
        else:
            return GateResult(
                gate_name="Word Count",
                status=GateStatus.WARNING,
                score=word_count,
                threshold=max_words,
                details=f"Word count {word_count} exceeds target {max_words}",
                recommendations=[
                    "Consider splitting into multiple pieces",
                    "Remove redundant content",
                ],
            )

    def _check_structure(self, content: dict, blueprint: dict | None) -> GateResult:
        """Check content structure meets requirements."""
        sections = content.get("sections", [])
        section_count = len(sections)

        expected_sections = self.MIN_SECTIONS
        if blueprint:
            expected_sections = max(
                len(blueprint.get("sections", [])),
                self.MIN_SECTIONS,
            )

        if section_count >= expected_sections:
            return GateResult(
                gate_name="Content Structure",
                status=GateStatus.PASSED,
                score=section_count,
                threshold=expected_sections,
                details=f"Content has {section_count} sections (expected {expected_sections})",
                recommendations=[],
            )
        else:
            return GateResult(
                gate_name="Content Structure",
                status=GateStatus.FAILED,
                score=section_count,
                threshold=expected_sections,
                details=f"Content has {section_count} sections, expected {expected_sections}",
                recommendations=[
                    f"Add {expected_sections - section_count} more sections",
                    "Review blueprint for required sections",
                ],
            )

    def _check_citable_excerpts(self, content: dict) -> GateResult:
        """Check that sections have citable excerpts."""
        sections = content.get("sections", [])

        if not sections:
            return GateResult(
                gate_name="Citable Excerpts",
                status=GateStatus.SKIPPED,
                score=None,
                threshold=None,
                details="No sections to check",
                recommendations=[],
            )

        excerpts_present = sum(
            1 for s in sections
            if s.get("citable_excerpt") or s.get("citable_excerpts")
        )
        ratio = excerpts_present / len(sections)

        if ratio >= self.MIN_CITABLE_EXCERPTS_RATIO:
            return GateResult(
                gate_name="Citable Excerpts",
                status=GateStatus.PASSED,
                score=ratio,
                threshold=self.MIN_CITABLE_EXCERPTS_RATIO,
                details=f"{excerpts_present}/{len(sections)} sections have citable excerpts",
                recommendations=[],
            )
        else:
            missing = len(sections) - excerpts_present
            return GateResult(
                gate_name="Citable Excerpts",
                status=GateStatus.FAILED,
                score=ratio,
                threshold=self.MIN_CITABLE_EXCERPTS_RATIO,
                details=f"Only {excerpts_present}/{len(sections)} sections have citable excerpts",
                recommendations=[
                    f"Add citable excerpts to {missing} sections",
                    "Ensure each section has a clear, quotable statement",
                ],
            )

    def _check_no_placeholders(self, content: dict) -> GateResult:
        """Check that content has no placeholder text."""
        text = str(content)
        placeholder_patterns = [
            "[TODO]",
            "[TBD]",
            "[PLACEHOLDER]",
            "Lorem ipsum",
            "INSERT",
            "[ADD",
            "XXX",
            "FIXME",
        ]

        found = [p for p in placeholder_patterns if p.upper() in text.upper()]

        if not found:
            return GateResult(
                gate_name="No Placeholders",
                status=GateStatus.PASSED,
                score=1.0,
                threshold=1.0,
                details="No placeholder text found",
                recommendations=[],
            )
        else:
            return GateResult(
                gate_name="No Placeholders",
                status=GateStatus.FAILED,
                score=0,
                threshold=1.0,
                details=f"Found placeholder patterns: {', '.join(found)}",
                recommendations=[
                    "Replace all placeholder text with actual content",
                    "Review for TODO markers",
                ],
            )

    def _check_schema_markup(self, content: dict, blueprint: dict | None) -> GateResult:
        """Check that schema markup is present and valid."""
        schema = content.get("schema_markup")

        if not blueprint or not blueprint.get("schema_markup_type"):
            return GateResult(
                gate_name="Schema Markup",
                status=GateStatus.SKIPPED,
                score=None,
                threshold=None,
                details="No schema markup required",
                recommendations=[],
            )

        if schema and schema.get("@type"):
            expected_type = blueprint.get("schema_markup_type", "")
            actual_type = schema.get("@type", "")

            if expected_type.lower() in actual_type.lower():
                return GateResult(
                    gate_name="Schema Markup",
                    status=GateStatus.PASSED,
                    score=1.0,
                    threshold=1.0,
                    details=f"Schema markup present ({actual_type})",
                    recommendations=[],
                )
            else:
                return GateResult(
                    gate_name="Schema Markup",
                    status=GateStatus.WARNING,
                    score=0.5,
                    threshold=1.0,
                    details=f"Schema type {actual_type} differs from expected {expected_type}",
                    recommendations=[
                        f"Consider using {expected_type} schema type",
                    ],
                )
        else:
            return GateResult(
                gate_name="Schema Markup",
                status=GateStatus.FAILED,
                score=0,
                threshold=1.0,
                details="Schema markup missing",
                recommendations=[
                    f"Add {blueprint.get('schema_markup_type', 'Article')} schema markup",
                    "Ensure schema.org structured data is included",
                ],
            )

    def _check_brand_alignment(
        self,
        content: dict,
        profile: ClientIntelligenceProfile,
    ) -> GateResult:
        """Check content aligns with brand voice."""
        text = str(content).lower()

        # Check for things they never say
        violations = []
        for forbidden in profile.brand_voice.things_they_never_say:
            if forbidden.lower() in text:
                violations.append(forbidden)

        if not violations:
            return GateResult(
                gate_name="Brand Alignment",
                status=GateStatus.PASSED,
                score=1.0,
                threshold=1.0,
                details="Content aligns with brand voice",
                recommendations=[],
            )
        else:
            return GateResult(
                gate_name="Brand Alignment",
                status=GateStatus.WARNING,
                score=0.5,
                threshold=1.0,
                details=f"Found brand voice violations: {', '.join(violations[:3])}",
                recommendations=[
                    f"Remove or rephrase: {v}" for v in violations[:3]
                ],
            )

    def _check_factual_claims(self, content: dict) -> GateResult:
        """Check that factual claims appear substantiated."""
        sections = content.get("sections", [])

        # Look for unsupported superlatives and claims
        warning_patterns = [
            "the best",
            "the only",
            "guaranteed",
            "always",
            "never fails",
            "100%",
            "proven",
        ]

        all_text = " ".join(
            s.get("content", "") for s in sections
        ).lower()

        unsupported = [
            p for p in warning_patterns
            if p in all_text and "according to" not in all_text and "study" not in all_text
        ]

        if not unsupported:
            return GateResult(
                gate_name="Factual Claims",
                status=GateStatus.PASSED,
                score=1.0,
                threshold=1.0,
                details="No unsupported absolute claims found",
                recommendations=[],
            )
        else:
            return GateResult(
                gate_name="Factual Claims",
                status=GateStatus.WARNING,
                score=0.7,
                threshold=1.0,
                details=f"Found potentially unsupported claims: {', '.join(unsupported[:3])}",
                recommendations=[
                    "Add sources for absolute claims",
                    "Consider softening language or adding citations",
                ],
            )


class OptimizationQualityGates:
    """Quality gates for content optimization."""

    MIN_IMPROVEMENT = 0.05  # 5% minimum improvement

    def __init__(self):
        self._log = logger.bind(component="optimization_gates")

    def run_gates(self, optimization: dict) -> QualityGateReport:
        """Run quality gates on optimization results."""
        results = []

        # Gate 1: Improvement achieved
        results.append(self._check_improvement(optimization))

        # Gate 2: Changes preserve meaning
        results.append(self._check_meaning_preserved(optimization))

        # Gate 3: Changes are specific
        results.append(self._check_changes_specific(optimization))

        passed = sum(1 for r in results if r.status == GateStatus.PASSED)
        failed = sum(1 for r in results if r.status == GateStatus.FAILED)
        warnings = sum(1 for r in results if r.status == GateStatus.WARNING)

        return QualityGateReport(
            content_id=optimization.get("original_url", ""),
            content_title=optimization.get("original_title", ""),
            overall_passed=failed == 0,
            gate_results=results,
            total_gates=len(results),
            passed_gates=passed,
            failed_gates=failed,
            warnings=warnings,
            created_at=datetime.utcnow(),
        )

    def _check_improvement(self, optimization: dict) -> GateResult:
        """Check that optimization achieved meaningful improvement."""
        improvement = optimization.get("improvement_percentage", 0) / 100

        if improvement >= self.MIN_IMPROVEMENT:
            return GateResult(
                gate_name="Improvement Achieved",
                status=GateStatus.PASSED,
                score=improvement,
                threshold=self.MIN_IMPROVEMENT,
                details=f"Achieved {improvement:.1%} improvement",
                recommendations=[],
            )
        else:
            return GateResult(
                gate_name="Improvement Achieved",
                status=GateStatus.WARNING,
                score=improvement,
                threshold=self.MIN_IMPROVEMENT,
                details=f"Only {improvement:.1%} improvement (target: {self.MIN_IMPROVEMENT:.0%})",
                recommendations=[
                    "Consider more significant structural changes",
                    "Add more specific data and citations",
                ],
            )

    def _check_meaning_preserved(self, optimization: dict) -> GateResult:
        """Check that core meaning is preserved in optimizations."""
        changes = optimization.get("changes", [])

        if not changes:
            return GateResult(
                gate_name="Meaning Preserved",
                status=GateStatus.PASSED,
                score=1.0,
                threshold=1.0,
                details="No changes to evaluate",
                recommendations=[],
            )

        # All changes should have rationale
        with_rationale = sum(1 for c in changes if c.get("rationale"))

        if with_rationale == len(changes):
            return GateResult(
                gate_name="Meaning Preserved",
                status=GateStatus.PASSED,
                score=1.0,
                threshold=1.0,
                details="All changes have documented rationale",
                recommendations=[],
            )
        else:
            return GateResult(
                gate_name="Meaning Preserved",
                status=GateStatus.WARNING,
                score=with_rationale / len(changes),
                threshold=1.0,
                details=f"{len(changes) - with_rationale} changes lack rationale",
                recommendations=[
                    "Document rationale for all changes",
                ],
            )

    def _check_changes_specific(self, optimization: dict) -> GateResult:
        """Check that changes are specific and actionable."""
        changes = optimization.get("changes", [])

        if not changes:
            return GateResult(
                gate_name="Changes Specific",
                status=GateStatus.PASSED,
                score=1.0,
                threshold=1.0,
                details="No changes to evaluate",
                recommendations=[],
            )

        specific = sum(
            1 for c in changes
            if c.get("original") and c.get("optimized")
        )

        if specific == len(changes):
            return GateResult(
                gate_name="Changes Specific",
                status=GateStatus.PASSED,
                score=1.0,
                threshold=1.0,
                details="All changes have specific before/after text",
                recommendations=[],
            )
        else:
            return GateResult(
                gate_name="Changes Specific",
                status=GateStatus.FAILED,
                score=specific / len(changes),
                threshold=1.0,
                details=f"{len(changes) - specific} changes lack specific text",
                recommendations=[
                    "Provide exact original and optimized text for each change",
                ],
            )


def run_content_quality_gates(
    content: dict,
    blueprint: dict | None = None,
    client_profile: ClientIntelligenceProfile | None = None,
) -> QualityGateReport:
    """Convenience function to run content quality gates."""
    gates = ContentQualityGates()
    return gates.run_all_gates(content, blueprint, client_profile)


def run_optimization_quality_gates(optimization: dict) -> QualityGateReport:
    """Convenience function to run optimization quality gates."""
    gates = OptimizationQualityGates()
    return gates.run_gates(optimization)
