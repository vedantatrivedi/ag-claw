"""
Helpers for the guided party-planning flow.
"""

from __future__ import annotations

import json
import os
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


def _raw_to_search_result(r: dict, source: str) -> SearchResult:
    return SearchResult(
        title=r.get("title", ""),
        url=r.get("url", ""),
        price=_parse_price(r.get("price", "")),
        source=source,
        relevance_score=0.9,
        rating=_parse_float(r.get("rating", "")),
        review_count=None,
        in_stock=True,
        image_url=r.get("image", ""),
    )


def get_curated_listing_results(plan: ShoppingPlan) -> tuple[List[SearchResults], str]:
    """For each plan item, search Amazon via Browserbase and return top 1 result.

    All item searches run in parallel for speed.
    Falls back to placeholders if Browserbase is unavailable.
    """
    import logging
    from concurrent.futures import ThreadPoolExecutor, as_completed

    logger = logging.getLogger(__name__)

    try:
        from shopping_agent.app.tools.browserbase import BrowserbaseManager
        manager = BrowserbaseManager()
    except Exception:
        logger.warning("[curate] Browserbase unavailable, falling back to placeholders")
        return build_placeholder_listing_results(plan), "placeholder"

    items = plan.items

    def _search_amazon_item(idx: int, query: str) -> tuple[int, list[dict]]:
        try:
            return idx, manager.search_amazon(query, max_results=2)
        except Exception as exc:
            logger.warning("[curate] Amazon search failed for '%s': %s", query, exc)
            return idx, []

    results_by_item: dict[int, list[SearchResult]] = {i: [] for i in range(len(items))}

    max_workers = min(len(items), 5)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_search_amazon_item, i, item.search_query or item.description): i
            for i, item in enumerate(items)
        }
        for future in as_completed(futures):
            idx, raw = future.result()
            for r in raw[:2]:
                if r.get("url"):
                    results_by_item[idx].append(_raw_to_search_result(r, "Amazon"))

    listing_results: List[SearchResults] = []
    for i, item in enumerate(items):
        query = item.search_query or item.description
        task = SearchTask(plan_item=item, search_query=query, filters={})
        listing_results.append(SearchResults(
            task=task,
            results=results_by_item[i],
            total_found=len(results_by_item[i]),
        ))

    return listing_results, "browserbase"


def _parse_price(price_str: str) -> Optional[float]:
    """Extract numeric price from strings like '₹499' or '₹1,299'."""
    if not price_str:
        return None
    cleaned = re.sub(r"[^\d.]", "", price_str.replace(",", ""))
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


def _parse_float(val: str) -> Optional[float]:
    """Extract a float from strings like '4.2 out of 5 stars'."""
    if not val:
        return None
    m = re.search(r"(\d+\.?\d*)", val)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    return None


def _is_amazon_url(url: str) -> bool:
    return "amazon.in" in url or "amazon.com" in url

def _is_flipkart_url(url: str) -> bool:
    return "flipkart.com" in url

def select_top_product_urls(listing_results: List[SearchResults]) -> List[str]:
    """Select the top-ranked Amazon or Flipkart product URL for each curated item."""
    urls: List[str] = []
    for result in listing_results:
        for r in result.results:
            if r.url and (_is_amazon_url(r.url) or _is_flipkart_url(r.url)):
                urls.append(r.url)
                break
    return urls


def add_urls_to_browserbase_cart(urls: List[str]) -> dict:
    """Add Amazon URLs to cart via Browserbase."""
    from shopping_agent.app.tools.browserbase import BrowserbaseManager

    amazon_urls = [u for u in urls if _is_amazon_url(u)]
    if not amazon_urls:
        raise ValueError("No Amazon URLs provided — cannot add to cart")

    manager = BrowserbaseManager()
    return manager.add_to_cart(amazon_urls)


def budget_inr_to_paisa(budget_inr: float) -> int:
    """Convert rupees to paisa using the standard integer representation."""
    return int(round(budget_inr * 100))
