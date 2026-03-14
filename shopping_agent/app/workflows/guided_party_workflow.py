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
    add_urls_to_browserbase_cart,
    build_guided_request,
    budget_inr_to_paisa,
    get_curated_listing_results,
    select_top_product_urls,
)
from shopping_agent.app.models import GuidedPartyPlanResult, ShoppingPlan
from shopping_agent.app.tools.pinelabs import create_budget_preauth, capture_preauth, get_preauth_status


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
        listing_results, curation_mode = get_curated_listing_results(plan)
        selected_product_urls = select_top_product_urls(listing_results)

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
            curation_mode=curation_mode,
            listing_results=listing_results,
            selected_product_urls=selected_product_urls,
        )
        return {
            "success": True,
            **result.model_dump(),
            "listing_results": [entry.model_dump() for entry in listing_results],
        }

    def add_to_cart(
        self,
        *,
        listing_results: List[Dict],
        selected_urls: Optional[List[str]] = None,
    ) -> Dict:
        """Add curated products to Amazon cart using Browserbase."""
        import logging
        logger = logging.getLogger(__name__)

        urls = selected_urls or []
        logger.warning("[cart] selected_urls received: %s", urls)
        if not urls:
            from shopping_agent.app.models import SearchResults

            normalized_results = []
            for entry in listing_results:
                normalized_results.append(
                    entry if isinstance(entry, SearchResults) else SearchResults(**entry)
                )
            urls = select_top_product_urls(normalized_results)

        if not urls:
            return {
                "success": False,
                "stage": "cart",
                "error": "No curated product URLs available to add to cart",
            }
        if any("placeholder.local" in url for url in urls):
            return {
                "success": False,
                "stage": "cart",
                "error": "Cart add requires real curated product URLs, not placeholder results",
                "selected_product_urls": urls,
            }

        logger.warning("[cart] URLs going to browserbase: %s", urls)
        try:
            cart_result = add_urls_to_browserbase_cart(urls)
            logger.warning("[cart] browserbase result: %s", cart_result)
        except Exception as exc:
            logger.warning("[cart] browserbase exception: %s", exc)
            return {
                "success": False,
                "stage": "cart",
                "error": str(exc),
                "selected_product_urls": urls,
            }

        return {
            "success": True,
            "selected_product_urls": urls,
            "cart": cart_result,
        }

    def capture_payment(
        self,
        *,
        order_id: str,
        capture_amount_paisa: int,
    ) -> Dict:
        """Capture the pre-authorized payment after cart is confirmed."""
        try:
            result = capture_preauth(
                order_id=order_id,
                capture_amount_paisa=capture_amount_paisa,
                wait_for_authorized=False,
            )
        except Exception as exc:
            return {
                "success": False,
                "stage": "capture",
                "error": str(exc),
                "order_id": order_id,
            }

        return {
            "success": True,
            "order_id": order_id,
            "captured_amount_paisa": capture_amount_paisa,
            "capture_status": result.get("capture_status"),
            "final_order_status": result.get("final_order_status"),
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
