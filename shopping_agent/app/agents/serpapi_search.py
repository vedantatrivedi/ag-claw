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

    def _search_site(self, query: str, site: str) -> List[SearchResult]:
        """Search a specific site via Google organic search."""
        params = {
            "engine": "google",
            "q": f"{query} site:{site}",
            "location": "India",
            "gl": "in",
            "hl": "en",
            "api_key": self.api_key,
            "num": 5,
        }
        try:
            results_data = GoogleSearch(params).get_dict()
        except Exception as e:
            print(f"SerpAPI organic search error ({site}): {e}")
            return []

        source_label = "Amazon" if "amazon" in site else "Flipkart"
        products: List[SearchResult] = []

        for item in results_data.get("organic_results", [])[:5]:
            link = item.get("link", "")
            if not link or site not in link:
                continue
            # Skip search/listing pages, only keep product pages
            if "amazon" in site and "/dp/" not in link and "/gp/" not in link:
                continue
            if "flipkart" in site and "/p/" not in link:
                continue

            title = item.get("title", "Unknown Product")
            image_url = ""
            if item.get("thumbnail"):
                image_url = item["thumbnail"]

            # Try to extract price from snippet
            price = None
            snippet = item.get("snippet", "")
            import re
            price_match = re.search(r'₹\s*([\d,]+)', snippet)
            if price_match:
                try:
                    price = float(price_match.group(1).replace(",", ""))
                except ValueError:
                    pass

            # Extract rating from rich snippet
            rating = None
            review_count = None
            rich = item.get("rich_snippet", {}).get("top", {})
            if "rating" in rich:
                try:
                    rating = float(rich["rating"])
                except (ValueError, TypeError):
                    pass
            if "reviews" in rich:
                try:
                    review_count = int(str(rich["reviews"]).replace(",", ""))
                except (ValueError, TypeError):
                    pass

            products.append(SearchResult(
                title=title,
                url=link,
                price=price,
                source=source_label,
                relevance_score=0.9,
                rating=rating,
                review_count=review_count,
                in_stock=True,
                image_url=image_url,
            ))

        return products

    def search(self, search_task: SearchTask) -> SearchResults:
        """Search Amazon.in and Flipkart via SerpAPI Google organic search."""
        search_query = search_task.plan_item.search_query or search_task.search_query

        try:
            # Search both sites
            amazon_results = self._search_site(search_query, "amazon.in")
            flipkart_results = self._search_site(search_query, "flipkart.com")

            products = amazon_results + flipkart_results

            # Apply ranking algorithm
            ranked_products = self._rank_products(products, search_query)

            # Return top 3
            top_results = ranked_products[:3]

            return SearchResults(
                task=search_task,
                results=top_results,
                total_found=len(products),
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
