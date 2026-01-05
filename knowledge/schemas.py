"""
Pydantic schemas for all AEO data models.

These schemas define the structured data that flows between agents,
gets stored in the database, and is returned via API.
"""

from datetime import datetime
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


# === ENUMS ===


class HealthGrade(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    F = "F"


class Severity(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"
    OPPORTUNITY = "opportunity"


class MarketPosition(str, Enum):
    LEADER = "leader"
    CHALLENGER = "challenger"
    NICHE = "niche"
    EMERGING = "emerging"


class ContentPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TrendDirection(str, Enum):
    IMPROVING = "improving"
    STABLE = "stable"
    DECLINING = "declining"


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    APPROVED = "approved"
    EXECUTED = "executed"
    FAILED = "failed"


# === CLIENT INTELLIGENCE (Cartographer Output) ===


class Offering(BaseModel):
    """A product or service the client offers."""

    name: str
    description: str
    target_user: str
    key_differentiators: list[str]
    common_use_cases: list[str]
    pricing_model: str = ""


class Audience(BaseModel):
    """A target audience segment."""

    segment: str
    needs: list[str]
    pain_points: list[str]
    how_they_find_solutions: str
    decision_criteria: list[str]


class BrandPerception(BaseModel):
    """How the brand is perceived."""

    what_customers_praise: list[str]
    what_customers_criticize: list[str]
    sentiment_summary: str
    trust_signals: list[str]
    credibility_gaps: list[str]


class BrandVoice(BaseModel):
    """The brand's voice and tone."""

    tone: str
    personality_traits: list[str]
    vocabulary_preferences: list[str]
    things_they_never_say: list[str]
    example_content: list[str]


class ClientIntelligenceProfile(BaseModel):
    """Complete client intelligence gathered by The Cartographer."""

    # Core Identity
    company_essence: str = Field(description="One paragraph capturing what they really are")
    founding_story: str = ""
    core_problem_solved: str
    unique_value_proposition: str = Field(
        description="What's actually different, not marketing speak"
    )

    # Products & Services
    offerings: list[Offering]

    # Audience Understanding
    primary_audiences: list[Audience]

    # Market Position
    category: str
    subcategories: list[str]
    market_position: MarketPosition
    brand_perception: BrandPerception

    # Voice & Tone
    brand_voice: BrandVoice

    # Authority & Expertise
    topics_of_authority: list[str] = Field(description="What they have genuine expertise in")
    topics_of_aspiration: list[str] = Field(description="What they want to be known for")
    authority_evidence: list[str] = Field(description="Awards, certifications, patents, etc.")
    thought_leadership_gaps: list[str]

    # Business Context
    business_goals: list[str]
    growth_stage: str
    key_metrics_they_care_about: list[str]

    last_updated: datetime = Field(default_factory=datetime.utcnow)


# === COMPETITIVE INTELLIGENCE (Scout Output) ===


class QueryComparison(BaseModel):
    """Comparison of query performance vs competitor."""

    query: str
    why_they_win: str
    what_we_need: str


class CompetitorProfile(BaseModel):
    """Profile of a single competitor."""

    name: str
    website: str

    # AI Visibility
    ai_mention_rate: float = Field(ge=0, le=1, description="% of relevant queries where mentioned")
    ai_recommendation_rate: float = Field(ge=0, le=1, description="% where they're recommended")
    ai_citation_rate: float = Field(ge=0, le=1, description="% where their content is cited")
    engines_strong_on: list[str]
    engines_weak_on: list[str]

    # Content Analysis
    content_strengths: list[str]
    content_gaps: list[str]
    authority_sources: list[str]

    # Strategic Position
    positioning: str
    key_differentiators: list[str]
    vulnerabilities: list[str]

    # Comparison to Client
    beating_us_on: list[QueryComparison]
    we_beat_them_on: list[QueryComparison]
    neither_winning: list[str]


class MarketOpportunity(BaseModel):
    """A market opportunity identified by competitive analysis."""

    opportunity: str
    competitors_missing: list[str]
    difficulty: str
    potential_impact: str


class CompetitiveAlert(BaseModel):
    """An alert about competitive movement."""

    competitor: str
    event: str
    threat_level: Literal["monitor", "respond", "urgent"]
    recommended_response: str


class CompetitiveIntelligence(BaseModel):
    """Complete competitive intelligence gathered by The Scout."""

    competitors: list[CompetitorProfile]

    # Market-Level Insights
    share_of_voice: dict[str, float] = Field(description="Competitor -> % of mentions")
    market_opportunities: list[MarketOpportunity]
    competitive_alerts: list[CompetitiveAlert]

    last_updated: datetime = Field(default_factory=datetime.utcnow)


# === PERFORMANCE MONITORING (Auditor Output) ===


class EngineScore(BaseModel):
    """Performance score for a specific AI engine."""

    engine: str
    mention_rate: float
    recommendation_rate: float
    trend: TrendDirection
    notes: str = ""


class AEOMetrics(BaseModel):
    """Core AEO performance metrics."""

    # Visibility
    mention_rate: float = Field(ge=0, le=1, description="% of relevant queries where mentioned")
    mention_rate_benchmark: float = Field(ge=0, le=1, description="Industry average")
    mention_rate_trend: TrendDirection

    # Quality of Mentions
    recommendation_rate: float = Field(ge=0, le=1, description="% where actually recommended")
    first_position_rate: float = Field(ge=0, le=1, description="% where mentioned first")
    citation_rate: float = Field(ge=0, le=1, description="% where content is cited")

    # Accuracy & Sentiment
    accuracy_rate: float = Field(ge=0, le=1, description="% of mentions that are accurate")
    sentiment_breakdown: dict[str, float] = Field(
        description="positive/neutral/negative percentages"
    )
    misinformation_count: int = 0

    # By Engine
    engine_scores: dict[str, EngineScore]


class PerformanceTrend(BaseModel):
    """A detected performance trend."""

    metric: str
    direction: TrendDirection
    magnitude: str
    significance: str
    explanation: str


class PerformanceComparison(BaseModel):
    """Performance comparison between two time periods."""

    period: str
    mention_rate_change: float
    recommendation_rate_change: float
    overall_assessment: str


class PerformanceIssue(BaseModel):
    """A detected performance issue."""

    severity: Severity
    issue: str
    evidence: list[str]
    recommended_action: str


class AEOPerformanceReport(BaseModel):
    """Complete AEO performance report from The Auditor."""

    # Current State
    overall_health_score: float = Field(ge=0, le=100, description="0-100 calibrated score")
    health_grade: HealthGrade

    # Core Metrics
    metrics: AEOMetrics

    # Trends
    trends: list[PerformanceTrend]

    # Comparisons
    vs_last_week: PerformanceComparison | None = None
    vs_last_month: PerformanceComparison | None = None
    vs_competitors: dict[str, float] = Field(default_factory=dict)

    # Issues Detected
    issues: list[PerformanceIssue]

    last_updated: datetime = Field(default_factory=datetime.utcnow)


# === CONTENT ANALYSIS (Librarian Output) ===


class CitableContent(BaseModel):
    """Analysis of a content piece for AI citability."""

    url: str
    title: str
    content_type: str
    topics_covered: list[str]
    citability_score: float = Field(ge=0, le=1, description="How likely AI will cite this")
    citability_factors: list[str]
    improvement_opportunities: list[str]
    actual_citations_detected: int = 0


class AuthoritySource(BaseModel):
    """An external source of authority."""

    source_type: str  # "wikipedia", "press", "industry_pub", etc.
    url: str
    authority_level: str
    what_it_says_about_client: str
    opportunity_to_improve: str


class ContentGap(BaseModel):
    """An identified gap in content coverage."""

    topic: str
    why_needed: str
    queries_this_would_answer: list[str]
    competitor_content_exists: bool
    recommended_content_type: str
    priority: ContentPriority
    effort_to_create: str


class CitationOpportunity(BaseModel):
    """An opportunity to get cited on an external platform."""

    platform: str
    topic: str
    why_valuable: str
    current_status: str  # "not present", "weak presence", etc.
    action_required: str


class ContentAuthorityAnalysis(BaseModel):
    """Complete content and authority analysis from The Librarian."""

    # Content Inventory
    total_content_pieces: int
    content_by_type: dict[str, int]

    # Quality Assessment
    ai_citable_content: list[CitableContent]

    # Authority Sources
    external_authority: list[AuthoritySource]

    # Gaps
    content_gaps: list[ContentGap]

    # Citation Opportunities
    citation_opportunities: list[CitationOpportunity]

    last_updated: datetime = Field(default_factory=datetime.utcnow)


# === MONITORING RESULTS ===


class BrandMention(BaseModel):
    """A single brand mention in an AI response."""

    query: str
    engine: str
    mentioned: bool
    position: int | None = Field(description="Position in list of mentions, 1-indexed")
    recommended: bool = False
    sentiment: Literal["positive", "neutral", "negative"] | None = None
    accuracy: Literal["accurate", "inaccurate", "partially_accurate"] | None = None
    context: str = Field(description="The context in which the brand was mentioned")
    sources_cited: list[str] = Field(default_factory=list)
    competitors_mentioned: list[str] = Field(default_factory=list)
    response_text: str = ""
    queried_at: datetime = Field(default_factory=datetime.utcnow)


class MonitoringResult(BaseModel):
    """Results from a monitoring run."""

    client_id: UUID
    mentions: list[BrandMention]
    metrics: AEOMetrics
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# === AI ENGINE QUERY/RESPONSE ===


class AIQuery(BaseModel):
    """A query to send to AI engines."""

    query_text: str
    query_type: str  # "brand", "product", "comparison", "category", "how_to"
    brand_names: list[str]  # Brands to look for in response
    competitor_names: list[str] = Field(default_factory=list)


class AIResponse(BaseModel):
    """Response from an AI engine."""

    engine: str
    query: str
    response_text: str
    sources_cited: list[str]
    queried_at: datetime = Field(default_factory=datetime.utcnow)
    latency_ms: int = 0
    error: str | None = None


# === QUALITY SIGNALS ===


class MentionQuality(BaseModel):
    """Quality signals for a brand mention."""

    # Position signals
    mentioned_first: bool = False
    mentioned_prominently: bool = False

    # Context signals
    recommended: bool = False
    framed_positively: bool = False

    # Accuracy signals
    information_accurate: bool = True
    information_current: bool = True
    key_differentiators_mentioned: bool = False

    # Authority signals
    content_cited: bool = False
    expertise_acknowledged: bool = False

    def calculate_score(self) -> float:
        """Calculate mention quality score 0-100."""
        score = 0
        if self.mentioned_first:
            score += 20
        if self.mentioned_prominently:
            score += 15
        if self.recommended:
            score += 25
        if self.framed_positively:
            score += 10
        if self.information_accurate:
            score += 15
        if self.content_cited:
            score += 15
        return score


class CitabilitySignals(BaseModel):
    """Signals that determine content citability."""

    # Structure
    clear_hierarchy: bool = False
    answerable_sections: bool = False
    lead_sentences_extractable: bool = False

    # Authority
    has_citations: bool = False
    has_credentials: bool = False
    has_data: bool = False
    has_freshness: bool = False

    # Specificity
    specific_claims: bool = False
    concrete_examples: bool = False
    actionable_content: bool = False

    # Technical
    has_schema_markup: bool = False
    mobile_friendly: bool = True
    fast_loading: bool = True

    def calculate_score(self) -> float:
        """Calculate citability score 0-100."""
        score = 0
        # Structure: 30 points
        if self.clear_hierarchy:
            score += 10
        if self.answerable_sections:
            score += 10
        if self.lead_sentences_extractable:
            score += 10
        # Authority: 30 points
        if self.has_citations:
            score += 10
        if self.has_credentials:
            score += 10
        if self.has_data:
            score += 5
        if self.has_freshness:
            score += 5
        # Specificity: 25 points
        if self.specific_claims:
            score += 10
        if self.concrete_examples:
            score += 10
        if self.actionable_content:
            score += 5
        # Technical: 15 points
        if self.has_schema_markup:
            score += 10
        if self.mobile_friendly:
            score += 2.5
        if self.fast_loading:
            score += 2.5
        return score


# === PRE-FLIGHT AND EXECUTION ===


class PreFlightCheck(BaseModel):
    """Mandatory check before any workflow execution."""

    work_type: Literal[
        "monitoring",
        "strategy",
        "content_creation",
        "optimization",
        "citation_building",
        "technical",
        "analysis",
    ]
    completion_criteria: list[str]
    total_deliverables: int
    deliverable_list: list[str]
    understanding_statement: str


class ProgressCheckpoint(BaseModel):
    """Mandatory progress report during execution."""

    checkpoint_number: int
    total_tasks: int
    completed_tasks: int
    completed_list: list[str]
    remaining_list: list[str]
    blockers: list[str]

    # Drift check
    still_following_spec: bool
    items_skipped: list[str]
    deviations: list[str]

    # Quality gate status
    quality_gates_passed: bool
    quality_gate_results: dict[str, bool]


class QualityGateResult(BaseModel):
    """Result of running quality gates."""

    gate_name: str
    passed: bool
    details: str
    score: float | None = None


# === API MODELS ===


class ClientCreate(BaseModel):
    """Request to create a new client."""

    name: str
    domain: str


class ClientResponse(BaseModel):
    """Response containing client data."""

    id: UUID
    name: str
    domain: str
    status: str
    created_at: datetime


class MonitoringQueryCreate(BaseModel):
    """Request to create a monitoring query."""

    query: str
    query_type: str
    priority: int = 50


class AlertResponse(BaseModel):
    """Response containing an alert."""

    id: UUID
    client_id: UUID
    severity: Severity
    alert_type: str
    title: str
    details: dict
    status: str
    created_at: datetime
