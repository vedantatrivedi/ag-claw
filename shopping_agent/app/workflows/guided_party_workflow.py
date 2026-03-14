"""
Guided party-planning workflow with budget pre-authorization.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from openai import OpenAI

from shopping_agent.app.agents.planner import PlannerAgent
from shopping_agent.app.guided_party import (
    DEFAULT_PARTY_QUESTIONS,
    PreferenceQuestionAgent,
    build_guided_request,
    build_placeholder_listing_results,
    budget_inr_to_paisa,
)
from shopping_agent.app.models import GuidedPartyPlanResult, ShoppingPlan
from shopping_agent.app.tools.pinelabs import create_budget_preauth, get_preauth_status


class GuidedPartyWorkflow:
    """Run the staged guided party flow."""

    def __init__(
        self,
        client: Optional[OpenAI] = None,
        *,
        planner: Optional[PlannerAgent] = None,
        question_agent: Optional[PreferenceQuestionAgent] = None,
    ):
        self.planner = planner or PlannerAgent(client=client)
        self.question_agent = question_agent or PreferenceQuestionAgent(client=client)

    def generate_preference_questions(self, user_request: str) -> List[str]:
        """Return preference questions with fallback behavior handled by the agent."""
        response = self.question_agent.generate_questions(user_request)
        questions = response.data.get("questions", [])
        return questions or DEFAULT_PARTY_QUESTIONS

    def create_preauth(
        self,
        *,
        preferences_answers: Dict[str, str],
        budget_inr: float,
    ) -> Dict:
        """Create the budget preauth and return the checkout handoff details."""
        budget_paisa = budget_inr_to_paisa(budget_inr)

        try:
            preauth = create_budget_preauth(budget_paisa=budget_paisa)
        except Exception as exc:
            return {
                "success": False,
                "stage": "preauth",
                "error": str(exc),
                "preferences_answers": preferences_answers,
                "budget_inr": budget_inr,
            }

        return {
            "success": True,
            "stage": "preauth_created",
            "preferences_answers": preferences_answers,
            "budget_inr": budget_inr,
            "preauth": preauth,
        }

    def complete_after_authorization(
        self,
        *,
        user_request: str,
        preferences_answers: Dict[str, str],
        budget_inr: float,
        preauth: Dict,
        apply_postprocessing: bool = True,
    ) -> Dict:
        """Wait for authorization, then generate the plan and placeholder results."""
        try:
            authorized = get_preauth_status(
                preauth["order_id"],
                wait_for_status="AUTHORIZED",
            )
        except Exception as exc:
            return {
                "success": False,
                "stage": "authorization",
                "error": str(exc),
                "preauth": preauth,
                "preferences_answers": preferences_answers,
                "budget_inr": budget_inr,
            }

        enriched_request = build_guided_request(
            original_request=user_request,
            preferences=preferences_answers,
            budget_inr=budget_inr,
        )
        planner_response = self.planner.plan(
            enriched_request,
            apply_postprocessing=apply_postprocessing,
        )

        if not planner_response.success:
            return {
                "success": False,
                "stage": "planning",
                "error": planner_response.error,
                "preauth": {
                    **preauth,
                    "authorized_status": authorized.get("status"),
                },
                "preferences_answers": preferences_answers,
                "budget_inr": budget_inr,
                "error_data": planner_response.data,
            }

        plan_dict = planner_response.data.get("plan", {})
        plan = ShoppingPlan(**plan_dict)
        listing_results = build_placeholder_listing_results(plan)

        result = GuidedPartyPlanResult(
            preferences_asked=list(preferences_answers.keys()),
            preferences_answers=preferences_answers,
            budget_inr=budget_inr,
            preauth={
                **preauth,
                "authorized_status": authorized.get("status"),
            },
            plan=plan.model_dump(),
            planner_metadata=planner_response.metadata,
            listing_results=listing_results,
        )
        return {
            "success": True,
            **result.model_dump(),
            "listing_results": [entry.model_dump() for entry in listing_results],
        }

    def run(
        self,
        *,
        user_request: str,
        preferences_answers: Dict[str, str],
        budget_inr: float,
        apply_postprocessing: bool = True,
    ) -> Dict:
        """Execute the full guided flow in one call."""
        preauth_result = self.create_preauth(
            preferences_answers=preferences_answers,
            budget_inr=budget_inr,
        )
        if not preauth_result.get("success"):
            return preauth_result

        return self.complete_after_authorization(
            user_request=user_request,
            preferences_answers=preferences_answers,
            budget_inr=budget_inr,
            preauth=preauth_result["preauth"],
            apply_postprocessing=apply_postprocessing,
        )
