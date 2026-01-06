"""
Base agent framework with personality system, cost tracking, and resilience.

Every agent has a distinct identity, thinking style, and approach.
They're not just functions—they're specialists with opinions and expertise.
"""

import asyncio
import json
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, TypeVar
from uuid import UUID

import anthropic
import structlog
from pydantic import BaseModel, ValidationError

from config import get_settings

logger = structlog.get_logger()
T = TypeVar("T", bound=BaseModel)


# Context variable for tracking organization context in agent calls
# This is set by the API layer when making authenticated requests
_current_org_id: ContextVar[UUID | None] = ContextVar("current_org_id", default=None)
_current_request_id: ContextVar[str | None] = ContextVar("current_request_id", default=None)


def set_agent_context(organization_id: UUID | None, request_id: str | None = None) -> None:
    """Set the current organization context for agent cost tracking."""
    _current_org_id.set(organization_id)
    _current_request_id.set(request_id)


def get_agent_context() -> tuple[UUID | None, str | None]:
    """Get the current organization context."""
    return _current_org_id.get(), _current_request_id.get()


# Cost per million tokens (approximate, as of 2025)
# Update these based on actual Anthropic pricing
MODEL_COSTS = {
    "claude-sonnet-4-20250514": {"input": Decimal("3.00"), "output": Decimal("15.00")},
    "claude-3-5-sonnet-20241022": {"input": Decimal("3.00"), "output": Decimal("15.00")},
    "claude-3-opus-20240229": {"input": Decimal("15.00"), "output": Decimal("75.00")},
    "claude-3-haiku-20240307": {"input": Decimal("0.25"), "output": Decimal("1.25")},
}


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreaker:
    """
    Circuit breaker for preventing cascade failures.

    When failures exceed threshold, the circuit opens and rejects requests
    for a cooldown period before allowing test requests through.
    """
    failure_threshold: int = 5
    recovery_timeout: int = 60  # seconds
    half_open_max_calls: int = 3

    _failures: int = field(default=0, init=False)
    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _last_failure_time: float | None = field(default=None, init=False)
    _half_open_calls: int = field(default=0, init=False)

    def record_success(self) -> None:
        """Record a successful call."""
        if self._state == CircuitState.HALF_OPEN:
            self._half_open_calls += 1
            if self._half_open_calls >= self.half_open_max_calls:
                # Recovered, close the circuit
                self._state = CircuitState.CLOSED
                self._failures = 0
                self._half_open_calls = 0
                logger.info("circuit_breaker_closed", reason="recovery_confirmed")
        else:
            self._failures = 0

    def record_failure(self) -> None:
        """Record a failed call."""
        self._failures += 1
        self._last_failure_time = time.time()

        if self._state == CircuitState.HALF_OPEN:
            # Failed during recovery test, reopen
            self._state = CircuitState.OPEN
            self._half_open_calls = 0
            logger.warning("circuit_breaker_reopened", reason="recovery_failed")
        elif self._failures >= self.failure_threshold:
            self._state = CircuitState.OPEN
            logger.warning(
                "circuit_breaker_opened",
                failures=self._failures,
                threshold=self.failure_threshold,
            )

    def allow_request(self) -> bool:
        """Check if a request should be allowed."""
        if self._state == CircuitState.CLOSED:
            return True

        if self._state == CircuitState.OPEN:
            # Check if cooldown has passed
            if self._last_failure_time is None:
                return True

            elapsed = time.time() - self._last_failure_time
            if elapsed >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
                logger.info("circuit_breaker_half_open", elapsed_seconds=elapsed)
                return True
            return False

        # HALF_OPEN: allow limited requests
        return True

    @property
    def state(self) -> CircuitState:
        return self._state


# Global circuit breakers per model
_circuit_breakers: dict[str, CircuitBreaker] = defaultdict(CircuitBreaker)


@dataclass
class LLMUsageRecord:
    """Record of LLM usage for cost tracking."""
    organization_id: UUID | None
    agent_name: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal
    request_id: str | None
    timestamp: datetime = field(default_factory=datetime.utcnow)


# In-memory usage buffer (flush to DB periodically or use message queue in production)
_usage_buffer: list[LLMUsageRecord] = []


def record_llm_usage(
    agent_name: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> Decimal:
    """
    Record LLM usage and calculate cost.

    Returns the cost in USD.
    """
    org_id, request_id = get_agent_context()

    # Calculate cost
    costs = MODEL_COSTS.get(model, MODEL_COSTS["claude-sonnet-4-20250514"])
    input_cost = (Decimal(input_tokens) / Decimal(1_000_000)) * costs["input"]
    output_cost = (Decimal(output_tokens) / Decimal(1_000_000)) * costs["output"]
    total_cost = input_cost + output_cost

    record = LLMUsageRecord(
        organization_id=org_id,
        agent_name=agent_name,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=total_cost,
        request_id=request_id,
    )

    _usage_buffer.append(record)

    logger.info(
        "llm_usage_recorded",
        agent=agent_name,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=float(total_cost),
        organization_id=str(org_id) if org_id else None,
    )

    return total_cost


async def flush_usage_to_db() -> None:
    """
    Flush usage records to the database.

    Call this periodically or on shutdown.
    In production, use a message queue for reliability.
    """
    global _usage_buffer

    if not _usage_buffer:
        return

    records = _usage_buffer
    _usage_buffer = []

    # Import here to avoid circular imports
    from db.deps import get_session_context
    from db.queries import record_llm_usage as db_record_usage

    try:
        async with get_session_context() as session:
            for record in records:
                if record.organization_id:
                    await db_record_usage(
                        session,
                        record.organization_id,
                        record.agent_name,
                        record.model,
                        record.input_tokens,
                        record.output_tokens,
                        record.cost_usd,
                        {"request_id": record.request_id} if record.request_id else None,
                    )
        logger.info("usage_records_flushed", count=len(records))
    except Exception as e:
        # Put records back on failure
        _usage_buffer = records + _usage_buffer
        logger.error("usage_flush_failed", error=str(e), records=len(records))


class AgentPersonality(BaseModel):
    """Defines an agent's personality and approach."""

    name: str
    title: str
    identity: str  # First-person statement of who they are
    personality_traits: list[str]
    core_mission: str
    thinking_style: str  # How they approach problems


class RetryConfig(BaseModel):
    """Configuration for retry behavior."""
    max_retries: int = 3
    base_delay: float = 1.0  # seconds
    max_delay: float = 60.0  # seconds
    exponential_base: float = 2.0
    jitter: bool = True  # Add randomness to prevent thundering herd


class Agent(ABC):
    """
    Base class for all AEO agents.

    Each agent has:
    - A distinct personality that influences their outputs
    - Access to the Anthropic API for LLM calls
    - Structured output parsing via Pydantic
    - Cost tracking and usage recording
    - Retry logic with exponential backoff
    - Circuit breaker for resilience
    - Logging and error handling
    """

    def __init__(
        self,
        retry_config: RetryConfig | None = None,
    ) -> None:
        settings = get_settings()
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.model = "claude-sonnet-4-20250514"
        self.retry_config = retry_config or RetryConfig()
        self._log = logger.bind(agent=self.personality.name)

    @property
    @abstractmethod
    def personality(self) -> AgentPersonality:
        """Define the agent's personality."""
        ...

    @abstractmethod
    async def run(self, **kwargs: Any) -> Any:
        """Execute the agent's primary task."""
        ...

    def _build_system_prompt(self, task_context: str = "") -> str:
        """Build the system prompt incorporating personality."""
        p = self.personality
        prompt = f"""You are {p.name}, the {p.title}.

{p.identity}

PERSONALITY TRAITS:
{chr(10).join(f"- {trait}" for trait in p.personality_traits)}

CORE MISSION:
{p.core_mission}

HOW YOU THINK:
{p.thinking_style}

{task_context}

Remember: You are not just executing a function. You are a specialist with opinions,
expertise, and a distinct way of approaching problems. Let your personality come through
in your analysis and recommendations while maintaining rigor and accuracy."""
        return prompt

    def _calculate_retry_delay(self, attempt: int) -> float:
        """Calculate delay for retry with exponential backoff and jitter."""
        delay = self.retry_config.base_delay * (
            self.retry_config.exponential_base ** attempt
        )
        delay = min(delay, self.retry_config.max_delay)

        if self.retry_config.jitter:
            import random
            delay = delay * (0.5 + random.random())

        return delay

    def _call_llm(
        self,
        user_prompt: str,
        task_context: str = "",
        max_tokens: int = 4096,
    ) -> str:
        """Make a call to the Anthropic API with retry logic and cost tracking."""
        circuit = _circuit_breakers[self.model]

        # Check circuit breaker
        if not circuit.allow_request():
            self._log.error("circuit_breaker_open", model=self.model)
            raise RuntimeError(
                f"Circuit breaker open for {self.model}. Service is experiencing issues."
            )

        self._log.info("calling_llm", prompt_length=len(user_prompt))

        last_error: Exception | None = None

        for attempt in range(self.retry_config.max_retries + 1):
            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    system=self._build_system_prompt(task_context),
                    messages=[{"role": "user", "content": user_prompt}],
                )

                content = response.content[0]
                if content.type != "text":
                    raise ValueError(f"Unexpected response type: {content.type}")

                # Record success and usage
                circuit.record_success()
                record_llm_usage(
                    agent_name=self.personality.name,
                    model=self.model,
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens,
                )

                self._log.info(
                    "llm_response_received",
                    tokens=response.usage.output_tokens,
                    attempt=attempt + 1,
                )
                return content.text

            except anthropic.RateLimitError as e:
                last_error = e
                circuit.record_failure()
                if attempt < self.retry_config.max_retries:
                    delay = self._calculate_retry_delay(attempt)
                    self._log.warning(
                        "rate_limit_hit_retrying",
                        attempt=attempt + 1,
                        delay=delay,
                    )
                    time.sleep(delay)
                else:
                    self._log.error("rate_limit_exceeded", attempts=attempt + 1)

            except anthropic.APIConnectionError as e:
                last_error = e
                circuit.record_failure()
                if attempt < self.retry_config.max_retries:
                    delay = self._calculate_retry_delay(attempt)
                    self._log.warning(
                        "connection_error_retrying",
                        attempt=attempt + 1,
                        delay=delay,
                        error=str(e),
                    )
                    time.sleep(delay)
                else:
                    self._log.error("connection_failed", attempts=attempt + 1)

            except anthropic.APIStatusError as e:
                last_error = e
                # Don't retry on 4xx errors (except 429 which is RateLimitError)
                if 400 <= e.status_code < 500:
                    circuit.record_success()  # Not a service failure
                    self._log.error("api_client_error", status=e.status_code)
                    raise
                # Retry on 5xx errors
                circuit.record_failure()
                if attempt < self.retry_config.max_retries:
                    delay = self._calculate_retry_delay(attempt)
                    self._log.warning(
                        "server_error_retrying",
                        attempt=attempt + 1,
                        delay=delay,
                        status=e.status_code,
                    )
                    time.sleep(delay)
                else:
                    self._log.error("server_error", attempts=attempt + 1)

        # All retries exhausted
        raise RuntimeError(
            f"LLM call failed after {self.retry_config.max_retries + 1} attempts: {last_error}"
        )

    def _call_llm_structured(
        self,
        user_prompt: str,
        output_schema: type[T],
        task_context: str = "",
        max_tokens: int = 4096,
    ) -> T:
        """
        Make a call to the Anthropic API with structured output.

        Uses Pydantic to validate and parse the response.
        """
        schema_json = json.dumps(output_schema.model_json_schema(), indent=2)

        enhanced_prompt = f"""{user_prompt}

You MUST respond with valid JSON that matches this schema:
```json
{schema_json}
```

Respond ONLY with the JSON object, no other text."""

        response_text = self._call_llm(
            enhanced_prompt,
            task_context=task_context,
            max_tokens=max_tokens,
        )

        # Extract JSON from response (handle markdown code blocks)
        json_text = response_text.strip()
        if json_text.startswith("```"):
            # Remove markdown code block
            lines = json_text.split("\n")
            json_text = "\n".join(lines[1:-1]) if lines[-1] == "```" else "\n".join(lines[1:])

        try:
            data = json.loads(json_text)
            return output_schema.model_validate(data)
        except json.JSONDecodeError as e:
            self._log.error("json_parse_error", error=str(e), response=response_text[:500])
            raise ValueError(f"Failed to parse LLM response as JSON: {e}") from e
        except ValidationError as e:
            self._log.error("validation_error", error=str(e))
            raise ValueError(f"LLM response failed schema validation: {e}") from e

    def _log_task_start(self, task: str, **context: Any) -> None:
        """Log the start of a task."""
        self._log.info("task_started", task=task, **context)

    def _log_task_complete(self, task: str, **context: Any) -> None:
        """Log task completion."""
        self._log.info("task_completed", task=task, **context)

    def _log_error(self, task: str, error: Exception, **context: Any) -> None:
        """Log an error."""
        self._log.error("task_failed", task=task, error=str(error), **context)


def get_circuit_breaker_status() -> dict[str, dict]:
    """Get status of all circuit breakers for monitoring."""
    return {
        model: {
            "state": cb.state.value,
            "failures": cb._failures,
            "threshold": cb.failure_threshold,
        }
        for model, cb in _circuit_breakers.items()
    }
