"""
Base agent framework with personality system.

Every agent has a distinct identity, thinking style, and approach.
They're not just functions—they're specialists with opinions and expertise.
"""

import json
from abc import ABC, abstractmethod
from typing import Any, TypeVar

import anthropic
import structlog
from pydantic import BaseModel, ValidationError

from config import get_settings

logger = structlog.get_logger()
T = TypeVar("T", bound=BaseModel)


class AgentPersonality(BaseModel):
    """Defines an agent's personality and approach."""

    name: str
    title: str
    identity: str  # First-person statement of who they are
    personality_traits: list[str]
    core_mission: str
    thinking_style: str  # How they approach problems


class Agent(ABC):
    """
    Base class for all AEO agents.

    Each agent has:
    - A distinct personality that influences their outputs
    - Access to the Anthropic API for LLM calls
    - Structured output parsing via Pydantic
    - Logging and error handling
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.model = "claude-sonnet-4-20250514"
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

    def _call_llm(
        self,
        user_prompt: str,
        task_context: str = "",
        max_tokens: int = 4096,
    ) -> str:
        """Make a call to the Anthropic API."""
        self._log.info("calling_llm", prompt_length=len(user_prompt))

        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=self._build_system_prompt(task_context),
            messages=[{"role": "user", "content": user_prompt}],
        )

        content = response.content[0]
        if content.type != "text":
            raise ValueError(f"Unexpected response type: {content.type}")

        self._log.info("llm_response_received", tokens=response.usage.output_tokens)
        return content.text

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
