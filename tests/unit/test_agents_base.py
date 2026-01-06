"""
Unit tests for agents/base.py.

Tests:
- Circuit breaker behavior
- LLM usage tracking and cost calculation
- Retry logic
- Agent context management
"""

import time
from decimal import Decimal
from uuid import uuid4

import pytest

from agents.base import (
    CircuitBreaker,
    CircuitState,
    MODEL_COSTS,
    RetryConfig,
    record_llm_usage,
    set_agent_context,
    get_agent_context,
    _usage_buffer,
)


class TestCircuitBreaker:
    """Tests for CircuitBreaker class."""

    def test_initial_state_is_closed(self):
        """Circuit breaker starts in closed state."""
        cb = CircuitBreaker()
        assert cb.state == CircuitState.CLOSED
        assert cb.allow_request() is True

    def test_stays_closed_on_success(self):
        """Circuit stays closed after successful calls."""
        cb = CircuitBreaker()
        cb.record_success()
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_opens_after_threshold_failures(self):
        """Circuit opens after reaching failure threshold."""
        cb = CircuitBreaker(failure_threshold=3)

        cb.record_failure()
        assert cb.state == CircuitState.CLOSED

        cb.record_failure()
        assert cb.state == CircuitState.CLOSED

        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_open_circuit_rejects_requests(self):
        """Open circuit breaker rejects requests."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=10)

        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.allow_request() is False

    def test_circuit_transitions_to_half_open(self):
        """Circuit transitions to half-open after recovery timeout."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0)

        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # Simulate time passing (recovery_timeout=0 means immediate)
        time.sleep(0.01)
        assert cb.allow_request() is True
        assert cb.state == CircuitState.HALF_OPEN

    def test_half_open_closes_on_success(self):
        """Half-open circuit closes after enough successes."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0, half_open_max_calls=2)

        # Open the circuit
        cb.record_failure()
        time.sleep(0.01)
        cb.allow_request()  # Triggers half-open

        assert cb.state == CircuitState.HALF_OPEN

        cb.record_success()
        assert cb.state == CircuitState.HALF_OPEN  # Still half-open

        cb.record_success()
        assert cb.state == CircuitState.CLOSED  # Now closed

    def test_half_open_reopens_on_failure(self):
        """Half-open circuit reopens on failure."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0)

        # Open the circuit
        cb.record_failure()
        time.sleep(0.01)
        cb.allow_request()  # Triggers half-open

        assert cb.state == CircuitState.HALF_OPEN

        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_success_resets_failure_count(self):
        """Success resets the failure counter."""
        cb = CircuitBreaker(failure_threshold=3)

        cb.record_failure()
        cb.record_failure()
        assert cb._failures == 2

        cb.record_success()
        assert cb._failures == 0


class TestAgentContext:
    """Tests for agent context management."""

    def test_set_and_get_context(self):
        """Can set and get organization context."""
        org_id = uuid4()
        request_id = "req-123"

        set_agent_context(org_id, request_id)
        retrieved_org, retrieved_req = get_agent_context()

        assert retrieved_org == org_id
        assert retrieved_req == request_id

    def test_clear_context(self):
        """Can clear context by setting None."""
        org_id = uuid4()
        set_agent_context(org_id, "req-456")

        set_agent_context(None, None)
        retrieved_org, retrieved_req = get_agent_context()

        assert retrieved_org is None
        assert retrieved_req is None

    def test_default_context_is_none(self):
        """Default context is None."""
        set_agent_context(None, None)  # Reset any previous state
        org_id, request_id = get_agent_context()
        assert org_id is None
        assert request_id is None


class TestLLMUsageTracking:
    """Tests for LLM usage and cost tracking."""

    def setup_method(self):
        """Clear usage buffer before each test."""
        global _usage_buffer
        _usage_buffer.clear()
        set_agent_context(None, None)

    def test_cost_calculation_sonnet(self):
        """Calculate cost correctly for Sonnet model."""
        cost = record_llm_usage(
            agent_name="test_agent",
            model="claude-sonnet-4-20250514",
            input_tokens=1_000_000,  # 1M tokens
            output_tokens=500_000,  # 0.5M tokens
        )

        # Input: $3.00 per 1M, Output: $15.00 per 1M
        # Expected: $3.00 + $7.50 = $10.50
        expected_cost = Decimal("3.00") + Decimal("7.50")
        assert cost == expected_cost

    def test_cost_calculation_opus(self):
        """Calculate cost correctly for Opus model."""
        cost = record_llm_usage(
            agent_name="test_agent",
            model="claude-3-opus-20240229",
            input_tokens=1_000_000,
            output_tokens=1_000_000,
        )

        # Input: $15.00 per 1M, Output: $75.00 per 1M
        expected_cost = Decimal("15.00") + Decimal("75.00")
        assert cost == expected_cost

    def test_cost_calculation_haiku(self):
        """Calculate cost correctly for Haiku model."""
        cost = record_llm_usage(
            agent_name="test_agent",
            model="claude-3-haiku-20240307",
            input_tokens=1_000_000,
            output_tokens=1_000_000,
        )

        # Input: $0.25 per 1M, Output: $1.25 per 1M
        expected_cost = Decimal("0.25") + Decimal("1.25")
        assert cost == expected_cost

    def test_unknown_model_uses_default(self):
        """Unknown model uses Sonnet pricing as default."""
        cost = record_llm_usage(
            agent_name="test_agent",
            model="unknown-model",
            input_tokens=1_000_000,
            output_tokens=0,
        )

        # Uses Sonnet pricing
        expected_cost = Decimal("3.00")
        assert cost == expected_cost

    def test_usage_record_added_to_buffer(self):
        """Usage record is added to buffer."""
        org_id = uuid4()
        set_agent_context(org_id, "req-123")

        record_llm_usage(
            agent_name="cartographer",
            model="claude-sonnet-4-20250514",
            input_tokens=100,
            output_tokens=50,
        )

        assert len(_usage_buffer) == 1
        record = _usage_buffer[0]
        assert record.organization_id == org_id
        assert record.agent_name == "cartographer"
        assert record.model == "claude-sonnet-4-20250514"
        assert record.input_tokens == 100
        assert record.output_tokens == 50
        assert record.request_id == "req-123"

    def test_multiple_records_accumulate(self):
        """Multiple usage records accumulate in buffer."""
        record_llm_usage("agent1", "claude-sonnet-4-20250514", 100, 50)
        record_llm_usage("agent2", "claude-sonnet-4-20250514", 200, 100)
        record_llm_usage("agent3", "claude-sonnet-4-20250514", 300, 150)

        assert len(_usage_buffer) == 3


class TestRetryConfig:
    """Tests for RetryConfig."""

    def test_default_values(self):
        """Default retry config has sensible values."""
        config = RetryConfig()
        assert config.max_retries == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 60.0
        assert config.exponential_base == 2.0
        assert config.jitter is True

    def test_custom_values(self):
        """Can create config with custom values."""
        config = RetryConfig(
            max_retries=5,
            base_delay=0.5,
            max_delay=30.0,
            exponential_base=3.0,
            jitter=False,
        )
        assert config.max_retries == 5
        assert config.base_delay == 0.5
        assert config.max_delay == 30.0
        assert config.exponential_base == 3.0
        assert config.jitter is False


class TestModelCosts:
    """Tests for MODEL_COSTS configuration."""

    def test_all_models_have_input_and_output(self):
        """All models have both input and output costs defined."""
        for model, costs in MODEL_COSTS.items():
            assert "input" in costs, f"{model} missing input cost"
            assert "output" in costs, f"{model} missing output cost"
            assert isinstance(costs["input"], Decimal)
            assert isinstance(costs["output"], Decimal)

    def test_costs_are_positive(self):
        """All costs are positive."""
        for model, costs in MODEL_COSTS.items():
            assert costs["input"] > 0, f"{model} input cost should be positive"
            assert costs["output"] > 0, f"{model} output cost should be positive"

    def test_sonnet_model_exists(self):
        """Sonnet model (default) is defined."""
        assert "claude-sonnet-4-20250514" in MODEL_COSTS
