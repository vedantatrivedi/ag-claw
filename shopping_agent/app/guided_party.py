"""
Helpers for the guided party-planning flow.
"""

from __future__ import annotations

import json
import re
import time
from typing import Dict, List, Optional
from urllib.parse import quote

from openai import APIConnectionError, OpenAI

from shopping_agent.app.config import Config
from shopping_agent.app.models import (
    AgentResponse,
    PlanItem,
    PreferenceQuestions,
    SearchResult,
    SearchResults,
    SearchTask,
    ShoppingPlan,
)
from shopping_agent.app.prompts import PREFERENCE_QUESTION_SYSTEM_PROMPT

DEFAULT_PARTY_QUESTIONS = [
    "What theme or characters does he like?",
    "Anything he dislikes or should we avoid?",
    "What is his favorite color?",
    "How many guests are expected?",
]


class PreferenceQuestionAgent:
    """Generate structured preference questions for guided party planning."""

    def __init__(self, client: Optional[OpenAI] = None):
        if client is None:
            client_kwargs = {"api_key": Config.OPENAI_API_KEY}
            if Config.OPENAI_BASE_URL:
                client_kwargs["base_url"] = Config.OPENAI_BASE_URL
            self.client = OpenAI(**client_kwargs)
        else:
            self.client = client
        self.model = Config.get_model(Config.PLANNER_AGENT_NAME)
        self.temperature = 0.2

    def generate_questions(self, user_request: str) -> AgentResponse:
        """Generate preference questions with a deterministic fallback."""
        max_retries = Config.MAX_RETRIES

        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    temperature=self.temperature,
                    messages=[
                        {"role": "system", "content": PREFERENCE_QUESTION_SYSTEM_PROMPT},
                        {"role": "user", "content": user_request},
                    ],
                    response_format={"type": "json_object"},
                    timeout=60.0,
                )
                break
            except APIConnectionError:
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                return AgentResponse(
                    success=True,
                    data={"questions": DEFAULT_PARTY_QUESTIONS},
                    metadata={"fallback_used": True, "tokens_used": 0},
                )
            except Exception:
                return AgentResponse(
                    success=True,
                    data={"questions": DEFAULT_PARTY_QUESTIONS},
                    metadata={"fallback_used": True, "tokens_used": 0},
                )
        else:
            return AgentResponse(
                success=True,
                data={"questions": DEFAULT_PARTY_QUESTIONS},
                metadata={"fallback_used": True, "tokens_used": 0},
            )

        try:
            content = response.choices[0].message.content or "{}"
            payload = json.loads(content)
            questions = PreferenceQuestions(**payload)
            return AgentResponse(
                success=True,
                data={"questions": questions.questions},
                metadata={
                    "fallback_used": False,
                    "tokens_used": response.usage.total_tokens if response.usage else 0,
                },
            )
        except Exception:
            return AgentResponse(
                success=True,
                data={"questions": DEFAULT_PARTY_QUESTIONS},
                metadata={"fallback_used": True, "tokens_used": 0},
            )


def build_guided_request(
    original_request: str,
    preferences: Dict[str, str],
    budget_inr: float,
) -> str:
    """Build the planner input for the post-preauth planning step."""
    lines = [original_request.strip(), "", "Collected preferences:"]
    for question, answer in preferences.items():
        lines.append(f"- {question} {answer}")
    lines.append("")
    lines.append(f"Budget: INR {budget_inr:.2f}")
    lines.append("Plan this as a child's themed birthday party.")
    return "\n".join(lines)


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return normalized or "item"


def build_placeholder_listing_results(plan: ShoppingPlan) -> List[SearchResults]:
    """Build deterministic placeholder listing results from a shopping plan."""
    listing_results: List[SearchResults] = []

    for item in plan.items:
        slug = _slugify(item.description)
        task = SearchTask(
            plan_item=item,
            search_query=item.search_query or item.description,
            filters={"placeholder": True},
        )
        result = SearchResult(
            title=f"Placeholder match for {item.description}",
            url=f"https://placeholder.local/products/{quote(slug)}",
            price=None,
            source="placeholder",
            relevance_score=0.5,
            in_stock=True,
        )
        listing_results.append(
            SearchResults(
                task=task,
                results=[result],
                total_found=1,
            )
        )

    return listing_results


def budget_inr_to_paisa(budget_inr: float) -> int:
    """Convert rupees to paisa using the standard integer representation."""
    return int(round(budget_inr * 100))
