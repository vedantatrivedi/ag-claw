"""
Planner Agent implementation.

Converts raw user shopping requests into structured shopping plans.
"""

import json
import time
from typing import Optional
from openai import OpenAI, APIConnectionError

from shopping_agent.app.config import Config
from shopping_agent.app.models import ShoppingPlan, AgentResponse
from shopping_agent.app.prompts import PLANNER_SYSTEM_PROMPT
from shopping_agent.app.guardrails import apply_guardrails, validate_schema
from shopping_agent.app.postprocess import postprocess_plan


class PlannerAgent:
    """
    Shopping Planner Agent.

    Responsible for:
    - Parsing user shopping intents
    - Breaking down requests into concrete items
    - Generating structured JSON plans
    """

    def __init__(self, client: Optional[OpenAI] = None):
        """
        Initialize the planner agent.

        Args:
            client: OpenAI client (creates new one if not provided)
        """
        if client is None:
            # Validate config when creating client
            Config.validate()
            client_kwargs = {"api_key": Config.OPENAI_API_KEY}
            if Config.OPENAI_BASE_URL:
                client_kwargs["base_url"] = Config.OPENAI_BASE_URL
            self.client = OpenAI(**client_kwargs)
        else:
            self.client = client
        self.model = Config.get_model(Config.PLANNER_AGENT_NAME)
        self.temperature = Config.get_temperature(Config.PLANNER_AGENT_NAME)
        self.name = Config.PLANNER_AGENT_NAME

    def plan(self, user_request: str, apply_postprocessing: bool = True) -> AgentResponse:
        """
        Generate a shopping plan from a user request.

        Args:
            user_request: The user's shopping intent in natural language
            apply_postprocessing: Whether to apply post-processing steps

        Returns:
            AgentResponse with the shopping plan
        """
        # Retry logic for connection errors
        max_retries = Config.MAX_RETRIES
        last_error = None

        for attempt in range(max_retries):
            try:
                # Call OpenAI API with structured output (with timeout)
                response = self.client.chat.completions.create(
                    model=self.model,
                    temperature=self.temperature,
                    messages=[
                        {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
                        {"role": "user", "content": user_request},
                    ],
                    response_format={"type": "json_object"},
                    timeout=60.0,
                )
                # Success - break out of retry loop
                break

            except APIConnectionError as e:
                last_error = e
                if attempt < max_retries - 1:
                    # Wait before retrying (exponential backoff)
                    wait_time = 2 ** attempt  # 1s, 2s, 4s
                    time.sleep(wait_time)
                    continue
                else:
                    # Final attempt failed, will raise below
                    raise

        try:

            # Extract the JSON response
            content = response.choices[0].message.content
            if not content:
                return AgentResponse(
                    success=False,
                    error="Empty response from OpenAI API",
                    data={},
                )

            plan_dict = json.loads(content)

            # Validate schema
            is_valid, error_msg = validate_schema(plan_dict)
            if not is_valid:
                return AgentResponse(
                    success=False,
                    error=f"Schema validation failed: {error_msg}",
                    data={"raw_response": plan_dict},
                )

            # Create ShoppingPlan object
            plan = ShoppingPlan(**plan_dict)

            # Apply guardrails (non-strict mode - just log violations)
            guardrails_passed, violations = apply_guardrails(plan, strict=False)

            # Apply post-processing if requested
            original_plan = plan.model_copy(deep=True)
            if apply_postprocessing:
                plan = postprocess_plan(plan)

            # Build response
            return AgentResponse(
                success=True,
                data={
                    "plan": plan.model_dump(),
                    "original_plan": original_plan.model_dump() if apply_postprocessing else None,
                    "guardrails_passed": guardrails_passed,
                    "guardrail_violations": violations if not guardrails_passed else [],
                },
                metadata={
                    "model": self.model,
                    "temperature": self.temperature,
                    "tokens_used": response.usage.total_tokens if response.usage else 0,
                    "postprocessing_applied": apply_postprocessing,
                },
            )

        except json.JSONDecodeError as e:
            return AgentResponse(
                success=False,
                error=f"Failed to parse JSON response: {str(e)}",
                data={"error_type": "JSONDecodeError"},
            )
        except Exception as e:
            import traceback
            error_details = {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "traceback": traceback.format_exc(),
            }

            # Concise error message
            error_msg = f"{type(e).__name__}: {str(e)}"

            # Add retry count for connection errors
            if "Connection" in str(e) or "connection" in str(e):
                error_msg += f" (retried {Config.MAX_RETRIES} times)"

            return AgentResponse(
                success=False,
                error=error_msg,
                data=error_details,
            )

    def get_instructions(self) -> str:
        """Get the agent's system instructions."""
        return PLANNER_SYSTEM_PROMPT
