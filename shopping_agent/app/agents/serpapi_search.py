"""
SerpAPI-based product search (free tier: 100 searches/month).
Drop-in replacement for browser_search.py that actually works.
"""

import os
from typing import List
from serpapi import GoogleSearch
from concurrent.futures import ThreadPoolExecutor, as_completed

from shopping_agent.app.config import Config
from shopping_agent.app.models import (
    PlanItem,
    SearchTask,
    SearchResults,
    SearchResult,
)


class SerpAPISearchAgent:
    """Product search using SerpAPI (Google Shopping)."""

    def __init__(self):
        self.api_key = os.getenv("SERPAPI_KEY")
        if not self.api_key:
            raise ValueError("SERPAPI_KEY not found in environment")

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

    def _rank_products(self, products: List[SearchResult], search_query: str) -> List[SearchResult]:
        """Rank products using 7-factor algorithm."""
        if not products:
            return []

        # Get all prices for competitiveness calculation
        all_prices = [p.price for p in products if p.price]
        min_price = min(all_prices) if all_prices else 0
        max_price = max(all_prices) if all_prices else 0

        # Score each product
        for product in products:
            score = 0.0

            # 1. Price competitiveness (25pts) - lower is better
            if product.price and max_price > min_price:
                price_ratio = (max_price - product.price) / (max_price - min_price)
                score += price_ratio * 25
            elif product.price == min_price:
                score += 25

            # 2. Rating quality (15pts)
            if product.rating:
                score += (product.rating / 5.0) * 15

            # 3. Review popularity (10pts) - logarithmic scale
            if product.review_count:
                import math
                review_score = min(math.log10(product.review_count + 1) / 5.0, 1.0)
                score += review_score * 10

            # 4. Site preference (15pts) - major sites preferred
            major_sites = ["amazon", "flipkart", "myntra", "ajio", "croma"]
            source_lower = product.source.lower()
            if any(site in source_lower for site in major_sites):
                score += 15
            else:
                score += 7.5  # Half points for other sites

            # 5. Title relevance (25pts) - keyword matching
            query_words = set(search_query.lower().split())
            title_words = set(product.title.lower().split())
            if query_words and title_words:
                overlap = len(query_words & title_words) / len(query_words)
                score += overlap * 25

            # 6. Stock availability (5pts)
            if product.in_stock:
                score += 5

            # 7. Base relevance (5pts) - from search API
            score += product.relevance_score * 5

            product.final_score = round(score, 1)

        # Sort by score descending
        ranked = sorted(products, key=lambda p: p.final_score or 0, reverse=True)
        return ranked

    def search(self, search_task: SearchTask) -> SearchResults:
        """Search Google Shopping via SerpAPI."""
        search_query = search_task.plan_item.search_query or search_task.search_query

        # Google Shopping search
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
            search = GoogleSearch(params)
            results_data = search.get_dict()

            shopping_results = results_data.get("shopping_results", [])

            products = []
            for item in shopping_results[:20]:  # Get more for better ranking
                # Extract price
                price = None
                if "price" in item:
                    price_str = str(item["price"]).replace("₹", "").replace(",", "").strip()
                    try:
                        price = float(price_str)
                    except ValueError:
                        pass

                # Extract rating
                rating = None
                review_count = None
                if "rating" in item:
                    rating = float(item["rating"])
                if "reviews" in item:
                    review_count = int(item["reviews"])

                # Extract URLs - try to get direct merchant link if available
                # First priority: direct merchant link (if available in offers)
                product_url = ""
                if "link" in item:  # Direct merchant link (when available)
                    product_url = item["link"]
                elif "product_link" in item:  # Google Shopping aggregator page
                    product_url = item["product_link"]

                image_url = item.get("thumbnail") or ""

                products.append(
                    SearchResult(
                        title=item.get("title", "Unknown Product"),
                        url=product_url,
                        price=price,
                        source=item.get("source", "Google Shopping"),
                        relevance_score=0.9,
                        rating=rating,
                        review_count=review_count,
                        in_stock=True,  # Google Shopping usually shows in-stock items
                        image_url=image_url,
                    )
                )

            # Apply ranking algorithm
            ranked_products = self._rank_products(products, search_query)

            # Return only top 3 results
            top_results = ranked_products[:3]

            return SearchResults(
                task=search_task,
                results=top_results,
                total_found=len(products),  # Total before filtering
            )

        except Exception as e:
            print(f"SerpAPI error: {e}")
            return SearchResults(
                task=search_task,
                results=[],
                total_found=0,
            )

    def search_multiple(self, plan_items: List[PlanItem]) -> List[SearchResults]:
        """Search multiple items in parallel."""
        if not plan_items:
            return []

        # Use ThreadPoolExecutor for parallel API calls
        max_workers = min(len(plan_items), 5)  # Max 5 concurrent searches

        def search_item(item: PlanItem) -> SearchResults:
            """Search a single item."""
            task = self.create_search_task(item)
            return self.search(task)

        results = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all search tasks
            future_to_item = {
                executor.submit(search_item, item): i
                for i, item in enumerate(plan_items)
            }

            # Collect results in original order
            result_dict = {}
            for future in as_completed(future_to_item):
                index = future_to_item[future]
                try:
                    result_dict[index] = future.result()
                except Exception as e:
                    print(f"Search failed for item {index}: {e}")
                    # Return empty results for failed searches
                    result_dict[index] = SearchResults(
                        task=self.create_search_task(plan_items[index]),
                        results=[],
                        total_found=0,
                    )

            # Return results in original order
            results = [result_dict[i] for i in range(len(plan_items))]

        return results

    def is_implemented(self) -> bool:
        """Check if API key is configured."""
        return bool(self.api_key)
