"""
Planning workflow implementation.

Orchestrates the planner agent and prepares for future handoff to browser search.
"""

from typing import Optional
from openai import OpenAI

from shopping_agent.app.agents.planner import PlannerAgent
from shopping_agent.app.agents.browser_search import BrowserSearchAgent
from shopping_agent.app.models import ShoppingPlan, AgentResponse


class PlanningWorkflow:
    """
    Planning workflow orchestrator.

    Current responsibilities:
    - Run the planner agent
    - Return structured plan

    Future responsibilities:
    - Hand off plan to browser search agent
    - Coordinate between planner and browser search
    - Handle clarification loops
    """

    def __init__(self, client: Optional[OpenAI] = None):
        """
        Initialize the planning workflow.

        Args:
            client: OpenAI client (shared across agents)
        """
        self.planner = PlannerAgent(client=client)
        self.browser_search = BrowserSearchAgent(client=client)

    def run(
        self,
        user_request: str,
        apply_postprocessing: bool = True,
        execute_search: bool = False,
    ) -> dict:
        """
        Execute the planning workflow.

        Args:
            user_request: User's shopping intent
            apply_postprocessing: Whether to post-process planner output
            execute_search: Whether to execute browser search (future feature)

        Returns:
            Dictionary with workflow results including plan and optionally search results
        """
        # Step 1: Run planner
        planner_response = self.planner.plan(
            user_request=user_request,
            apply_postprocessing=apply_postprocessing,
        )

        if not planner_response.success:
            return {
                "success": False,
                "error": planner_response.error,
                "error_data": planner_response.data,
                "stage": "planning",
            }

        # Extract the plan
        plan_data = planner_response.data.get("plan", {})
        plan = ShoppingPlan(**plan_data)

        result = {
            "success": True,
            "plan": plan.model_dump(),
            "planner_metadata": planner_response.metadata,
            "guardrails_passed": planner_response.data.get("guardrails_passed", True),
            "guardrail_violations": planner_response.data.get("guardrail_violations", []),
        }

        # Add original plan if post-processing was applied
        if apply_postprocessing and planner_response.data.get("original_plan"):
            result["original_plan"] = planner_response.data["original_plan"]

        # Step 2: Optionally execute browser search (future feature)
        if execute_search:
            if not self.browser_search.is_implemented():
                result["search_results"] = None
                result["search_note"] = (
                    "Browser search agent is scaffolded but not yet implemented. "
                    "Search execution will be available in the next phase."
                )
            else:
                # This will be implemented when browser search is ready
                search_results = self.browser_search.search_multiple(plan.items)
                result["search_results"] = [sr.model_dump() for sr in search_results]

        return result

    def explain_next_steps(self, plan: ShoppingPlan) -> str:
        """
        Explain what would happen next in the workflow.

        This helps users understand how the browser search agent will be used.

        Args:
            plan: The shopping plan

        Returns:
            String explaining next steps
        """
        explanation = "Next steps (when browser search is implemented):\n\n"

        for idx, item in enumerate(plan.items, 1):
            explanation += f"{idx}. Search for: {item.description}\n"
            explanation += f"   Query: {item.description} {' '.join(item.search_hints[:2])}\n"
            if item.constraints:
                explanation += f"   Filters: {', '.join(item.constraints)}\n"
            explanation += "\n"

        explanation += (
            "The browser search agent will:\n"
            "- Generate optimized search queries\n"
            "- Search multiple e-commerce platforms\n"
            "- Extract and rank product results\n"
            "- Return top candidates for each item\n"
        )

        return explanation
