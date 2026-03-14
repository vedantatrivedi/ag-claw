"""
Main orchestrator for the shopping agent system.

Coordinates multiple agents and workflows.
"""

from typing import Optional, Dict, Any
from openai import OpenAI

from shopping_agent.app.config import Config
from shopping_agent.app.workflows.planning_workflow import PlanningWorkflow
from shopping_agent.app.workflows.guided_party_workflow import GuidedPartyWorkflow
from shopping_agent.app.agents.planner import PlannerAgent
from shopping_agent.app.agents.browser_search import BrowserSearchAgent


class ShoppingOrchestrator:
    """
    Main orchestrator for the shopping agent system.

    Responsibilities:
    - Initialize and manage agents
    - Route requests to appropriate workflows
    - Handle agent handoffs (future)
    - Coordinate multi-agent interactions
    """

    def __init__(self):
        """Initialize the orchestrator and all agents."""
        # Create shared OpenAI client
        client_kwargs = {"api_key": Config.OPENAI_API_KEY}
        if Config.OPENAI_BASE_URL:
            client_kwargs["base_url"] = Config.OPENAI_BASE_URL
        self.client = OpenAI(**client_kwargs)

        # Initialize agents
        self.planner = PlannerAgent(client=self.client)
        self.browser_search = BrowserSearchAgent(client=self.client)

        # Initialize workflows
        self.planning_workflow = PlanningWorkflow(client=self.client)
        self.guided_party_workflow = GuidedPartyWorkflow(client=self.client)

    def create_shopping_plan(
        self,
        user_request: str,
        apply_postprocessing: bool = True,
    ) -> Dict[str, Any]:
        """
        Create a shopping plan from a user request.

        This is the main entry point for the planning workflow.

        Args:
            user_request: User's shopping intent in natural language
            apply_postprocessing: Whether to apply post-processing

        Returns:
            Dictionary with plan and metadata
        """
        return self.planning_workflow.run(
            user_request=user_request,
            apply_postprocessing=apply_postprocessing,
            execute_search=False,  # Not implemented yet
        )

    def search_for_products(self, plan_data: dict) -> Dict[str, Any]:
        """
        Execute browser search for a shopping plan (future implementation).

        Args:
            plan_data: Shopping plan dictionary

        Returns:
            Dictionary with search results
        """
        if not self.browser_search.is_implemented():
            return {
                "success": False,
                "error": "Browser search agent is not yet implemented",
                "note": "This feature will be available in the next phase",
            }

        # Future implementation will:
        # 1. Parse the plan
        # 2. Create search tasks for each item
        # 3. Execute searches across platforms
        # 4. Return ranked results

        return {
            "success": False,
            "error": "Not implemented",
        }

    def run_full_workflow(
        self,
        user_request: str,
        apply_postprocessing: bool = True,
        execute_search: bool = False,
    ) -> Dict[str, Any]:
        """
        Run the complete workflow: planning + search.

        Args:
            user_request: User's shopping intent
            apply_postprocessing: Whether to post-process plan
            execute_search: Whether to execute search (future)

        Returns:
            Dictionary with complete workflow results
        """
        # Step 1: Create shopping plan
        plan_result = self.planning_workflow.run(
            user_request=user_request,
            apply_postprocessing=apply_postprocessing,
            execute_search=False,
        )

        if not plan_result.get("success"):
            # Include error details from the planner
            return {
                "success": False,
                "error": plan_result.get("error"),
                "error_data": plan_result.get("error_data", {}),
                "stage": plan_result.get("stage", "planning"),
            }

        result = {
            "success": True,
            "plan": plan_result.get("plan"),
            "planner_metadata": plan_result.get("planner_metadata"),
        }

        # Step 2: Optionally execute search
        if execute_search:
            search_result = self.search_for_products(plan_result.get("plan", {}))
            result["search"] = search_result

        return result

    def run_guided_party_flow(
        self,
        *,
        user_request: str,
        preferences_answers: dict,
        budget_inr: float,
        apply_postprocessing: bool = True,
    ) -> Dict[str, Any]:
        """Run the guided party flow with preauth gating."""
        return self.guided_party_workflow.run(
            user_request=user_request,
            preferences_answers=preferences_answers,
            budget_inr=budget_inr,
            apply_postprocessing=apply_postprocessing,
        )

    def generate_guided_party_questions(self, user_request: str) -> list[str]:
        """Return model-generated preference questions for the guided flow."""
        return self.guided_party_workflow.generate_preference_questions(user_request)

    def create_guided_party_preauth(
        self,
        *,
        preferences_answers: dict,
        budget_inr: float,
    ) -> Dict[str, Any]:
        """Create the guided-party preauth and return the checkout handoff details."""
        return self.guided_party_workflow.create_preauth(
            preferences_answers=preferences_answers,
            budget_inr=budget_inr,
        )

    def complete_guided_party_after_authorization(
        self,
        *,
        user_request: str,
        preferences_answers: dict,
        budget_inr: float,
        preauth: dict,
        apply_postprocessing: bool = True,
    ) -> Dict[str, Any]:
        """Wait for authorization and finish the guided-party flow."""
        return self.guided_party_workflow.complete_after_authorization(
            user_request=user_request,
            preferences_answers=preferences_answers,
            budget_inr=budget_inr,
            preauth=preauth,
            apply_postprocessing=apply_postprocessing,
        )

    def add_guided_party_items_to_cart(
        self,
        *,
        listing_results: list[dict],
        selected_urls: Optional[list[str]] = None,
    ) -> Dict[str, Any]:
        """Add selected or top-ranked guided-party items to cart."""
        return self.guided_party_workflow.add_to_cart(
            listing_results=listing_results,
            selected_urls=selected_urls,
        )

    def get_agent_info(self) -> Dict[str, Any]:
        """
        Get information about all agents.

        Returns:
            Dictionary with agent details
        """
        return {
            "agents": [
                {
                    "name": self.planner.name,
                    "model": self.planner.model,
                    "temperature": self.planner.temperature,
                    "status": "active",
                    "implemented": True,
                },
                {
                    "name": self.browser_search.name,
                    "model": self.browser_search.model,
                    "temperature": self.browser_search.temperature,
                    "status": "scaffolded",
                    "implemented": False,
                },
            ],
            "workflows": [
                {
                    "name": "planning_workflow",
                    "description": "Convert user request to shopping plan",
                    "status": "active",
                },
                {
                    "name": "search_workflow",
                    "description": "Search for products based on plan",
                    "status": "scaffolded",
                },
            ],
        }

    def explain_architecture(self) -> str:
        """
        Explain the multi-agent architecture.

        Returns:
            Human-readable architecture description
        """
        return """
Shopping Agent Multi-Agent Architecture
========================================

CURRENT STATE (v1):
-------------------
1. Planner Agent (ACTIVE)
   - Converts user requests to structured plans
   - Generates searchable item descriptions
   - Identifies constraints and search hints
   - Model: {planner_model}

2. Browser Search Agent (SCAFFOLD)
   - Ready for implementation
   - Will search e-commerce platforms
   - Will extract and rank products
   - Model: {browser_model}

WORKFLOW:
---------
User Request → Planner Agent → Structured Plan → (Future: Browser Search) → Products

NEXT PHASE:
-----------
- Implement web scraping in Browser Search Agent
- Add search tools (Amazon, eBay, Walmart APIs)
- Implement product ranking and comparison
- Add price tracking and deal finding
- Enable agent handoffs with context passing

DESIGN PRINCIPLES:
------------------
- Clean separation of concerns
- Each agent has a single, clear responsibility
- Structured data exchange between agents
- Easy to extend and add new agents
- Production-ready architecture from day one
        """.format(
            planner_model=self.planner.model,
            browser_model=self.browser_search.model,
        )
