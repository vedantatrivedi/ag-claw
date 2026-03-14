"""
SearchAPI.com-based product search (free tier: 100 searches/month).
Drop-in replacement for serpapi_search.py using searchapi.com.
"""

import os
import requests
from typing import List

from shopping_agent.app.config import Config
from shopping_agent.app.models import (
    PlanItem,
    SearchTask,
    SearchResults,
    SearchResult,
)


class SearchAPISearchAgent:
    """Product search using SearchAPI.com (Google Shopping)."""

    def __init__(self):
        self.api_key = os.getenv("SEARCHAPI_KEY")
        if not self.api_key:
            raise ValueError("SEARCHAPI_KEY not found in environment")

        self.base_url = "https://www.searchapi.io/api/v1/search"

    def create_search_task(self, plan_item: PlanItem) -> SearchTask:
        """Convert plan item to search task."""
        query_parts = [plan_item.description]
        query_parts.extend(plan_item.search_hints[:3])
        search_query = " ".join(query_parts)

        filters = {}
        for constraint in plan_item.constraints:
            constraint_lower = constraint.lower()
            if "budget:" in constraint_lower or "under $" in constraint_lower:
                try:
                    price_str = constraint_lower.split("$")[1].split()[0]
                    filters["max_price"] = float(price_str)
                except (IndexError, ValueError):
                    pass

        return SearchTask(
            plan_item=plan_item,
            search_query=search_query,
            filters=filters,
        )

    def search(self, search_task: SearchTask) -> SearchResults:
        """Search Google Shopping via SearchAPI.com."""
        search_query = search_task.plan_item.search_query or search_task.search_query

        # SearchAPI.com parameters for Google Shopping
        params = {
            "engine": "google_shopping",
            "q": search_query,
            "location": "India",
            "gl": "in",
            "hl": "en",
            "api_key": self.api_key,
            "num": 10,
        }

        try:
            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            results_data = response.json()

            shopping_results = results_data.get("shopping_results", [])

            products = []
            for item in shopping_results[:10]:
                # Extract price
                price = None
                if "price" in item:
                    price_str = str(item["price"]).replace("₹", "").replace(",", "").strip()
                    try:
                        price = float(price_str)
                    except ValueError:
                        pass
                elif "extracted_price" in item:
                    try:
                        price = float(item["extracted_price"])
                    except (ValueError, TypeError):
                        pass

                # Extract rating
                rating = None
                review_count = None
                if "rating" in item:
                    try:
                        rating = float(item["rating"])
                    except (ValueError, TypeError):
                        pass
                if "reviews" in item:
                    try:
                        review_count = int(item["reviews"])
                    except (ValueError, TypeError):
                        pass
                elif "reviews_count" in item:
                    try:
                        review_count = int(item["reviews_count"])
                    except (ValueError, TypeError):
                        pass

                # Extract URL and title
                title = item.get("title", "Unknown Product")
                url = item.get("link", "") or item.get("product_link", "")
                source = item.get("source", "Google Shopping")

                products.append(
                    SearchResult(
                        title=title,
                        url=url,
                        price=price,
                        source=source,
                        relevance_score=0.9,
                        rating=rating,
                        review_count=review_count,
                        in_stock=True,  # Google Shopping usually shows in-stock items
                    )
                )

            return SearchResults(
                task=search_task,
                results=products,
                total_found=len(products),
            )

        except requests.exceptions.RequestException as e:
            print(f"SearchAPI error: {e}")
            return SearchResults(
                task=search_task,
                results=[],
                total_found=0,
            )
        except Exception as e:
            print(f"SearchAPI error: {e}")
            return SearchResults(
                task=search_task,
                results=[],
                total_found=0,
            )

    def search_multiple(self, plan_items: List[PlanItem]) -> List[SearchResults]:
        """Search multiple items."""
        results = []
        for item in plan_items:
            task = self.create_search_task(item)
            search_results = self.search(task)
            results.append(search_results)
        return results

    def is_implemented(self) -> bool:
        """Check if API key is configured."""
        return bool(self.api_key)
