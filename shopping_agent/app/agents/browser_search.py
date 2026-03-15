"""
Browser Search Agent - Multi-site product search using browser-use.

This agent is responsible for:
- Taking plan items from the planner
- Searching multiple e-commerce sites in parallel
- Extracting and ranking product results
- Validating site appropriateness based on item category
"""

import asyncio
from typing import List, Optional, Dict, Any
from openai import OpenAI

from shopping_agent.app.config import Config
from shopping_agent.app.models import (
    PlanItem,
    SearchTask,
    SearchResults,
    SearchResult,
    AgentResponse,
)
from shopping_agent.app.prompts import BROWSER_SEARCH_SYSTEM_PROMPT


# Curated list of top 5 Indian e-commerce platforms with specializations
SITE_CONFIGS = {
    "amazon": {
        "domain": "amazon.in",
        "name": "Amazon",
        "strong_categories": ["electronics", "books", "home", "sports", "general"],
        "weak_categories": []  # Good for everything
    },
    "flipkart": {
        "domain": "flipkart.com",
        "name": "Flipkart",
        "strong_categories": ["electronics", "fashion", "books", "home", "sports", "general"],
        "weak_categories": []  # Good for everything
    },
    "myntra": {
        "domain": "myntra.com",
        "name": "Myntra",
        "strong_categories": ["fashion", "clothing", "footwear", "accessories"],
        "weak_categories": ["electronics", "sports", "books", "home", "toys"]
    },
    "ajio": {
        "domain": "ajio.com",
        "name": "Ajio",
        "strong_categories": ["fashion", "clothing", "footwear", "accessories"],
        "weak_categories": ["electronics", "sports", "books", "home", "toys"]
    },
    "croma": {
        "domain": "croma.com",
        "name": "Croma",
        "strong_categories": ["electronics", "appliances", "gadgets"],
        "weak_categories": ["fashion", "clothing", "books", "sports", "toys"]
    },
}

# Category keyword mapping for item classification
CATEGORY_KEYWORDS = {
    "fashion": ["clothing", "shirt", "pant", "dress", "jeans", "jacket", "coat",
                "wear", "outfit", "apparel", "garment", "fashion"],
    "footwear": ["shoe", "sandal", "slipper", "boot", "sneaker", "footwear"],
    "accessories": ["bag", "wallet", "belt", "watch", "jewelry", "accessory",
                    "sunglasses", "hat", "scarf"],
    "electronics": ["laptop", "phone", "tablet", "camera", "headphone", "speaker",
                    "tv", "monitor", "electronic", "gadget", "device"],
    "sports": ["cricket", "football", "tennis", "gym", "fitness", "yoga",
               "sports", "exercise", "equipment", "bat", "ball"],
    "books": ["book", "novel", "textbook", "magazine", "journal", "reading"],
    "home": ["furniture", "decor", "kitchen", "bed", "table", "chair",
             "home", "household", "utensil"],
    "toys": ["toy", "game", "puzzle", "doll", "action figure", "kids", "children"],
}


class BrowserSearchAgent:
    """
    Browser Search Agent - Multi-site product search.

    RESPONSIBILITIES:
    - Convert plan items into search tasks
    - Execute browser searches across multiple e-commerce sites
    - Extract structured product data using browser-use
    - Validate site appropriateness based on item category
    - Handle parallel search execution with rate limiting
    """

    def __init__(self, client: Optional[OpenAI] = None):
        """
        Initialize the browser search agent.

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
        self.model = Config.get_model(Config.BROWSER_AGENT_NAME)
        self.temperature = Config.get_temperature(Config.BROWSER_AGENT_NAME)
        self.name = Config.BROWSER_AGENT_NAME
        self.browser_use_available = self._check_browser_use()
        self.max_parallel_searches = Config.MAX_PARALLEL_SEARCHES
        self.search_timeout = Config.BROWSER_SEARCH_TIMEOUT

    def _check_browser_use(self) -> bool:
        """Check if browser-use library is available."""
        try:
            import browser_use
            return True
        except ImportError:
            return False

    def _classify_item_category(self, description: str) -> str:
        """
        Classify item into category based on description keywords.

        Args:
            description: Item description

        Returns:
            Category name or "general" if no match
        """
        description_lower = description.lower()

        for category, keywords in CATEGORY_KEYWORDS.items():
            if any(keyword in description_lower for keyword in keywords):
                return category

        return "general"

    def _validate_preferred_sites(self, plan_item: PlanItem) -> List[str]:
        """
        Generic site validation - filter out sites that are weak for this item category.

        Strategy:
        - Classify item into category (fashion, electronics, sports, etc.)
        - Remove sites where this category is in their weak_categories list
        - Always keep at least amazon/flipkart as fallback

        Args:
            plan_item: The plan item with preferred_sites

        Returns:
            Validated list of site keys
        """
        preferred = plan_item.preferred_sites or ["amazon", "flipkart"]
        item_category = self._classify_item_category(plan_item.description)

        # Filter out sites that are weak for this category
        validated = []
        for site in preferred:
            site_config = SITE_CONFIGS.get(site, {})
            weak_categories = site_config.get("weak_categories", [])

            # Skip site if item category is in its weak list
            if item_category not in weak_categories:
                validated.append(site)

        # Ensure at least one site remains (fallback to broad sites)
        if not validated:
            validated = ["amazon", "flipkart"]

        return validated

    def _score_product(
        self,
        product: SearchResult,
        search_query: str,
        preferred_sites: List[str],
        all_prices: List[float]
    ) -> float:
        """
        Calculate deterministic relevance score for a product.

        Scoring factors:
        1. Price competitiveness (0-25 points): Lower price = higher score
        2. Rating quality (0-15 points): Higher rating = higher score
        3. Review popularity (0-10 points): More reviews = higher score
        4. Site preference (0-15 points): Preferred sites get bonus
        5. Title relevance (0-25 points): Keyword match in title
        6. Stock availability (0-5 points): In stock gets bonus
        7. Base relevance (0-5 points): From browser-use extraction

        Args:
            product: Product to score
            search_query: Original search query
            preferred_sites: User's preferred sites
            all_prices: All product prices for normalization

        Returns:
            Score from 0-100
        """
        score = 0.0

        # 1. Price competitiveness (0-25 points)
        if product.price and all_prices:
            min_price = min(all_prices)
            max_price = max(all_prices)
            if max_price > min_price:
                price_score = 25 * (1 - (product.price - min_price) / (max_price - min_price))
                score += price_score
            else:
                score += 12.5

        # 2. Rating quality (0-15 points)
        if product.rating:
            score += (product.rating / 5.0) * 15

        # 3. Review popularity (0-10 points)
        if product.review_count:
            # Logarithmic scale: 1 review=1pt, 100 reviews=5pts, 10000 reviews=10pts
            import math
            review_score = min(10, math.log10(product.review_count + 1) * 2.5)
            score += review_score

        # 4. Site preference (0-15 points)
        site_key = product.source.lower()
        if any(pref in site_key for pref in preferred_sites):
            score += 15

        # 5. Title relevance (0-25 points)
        query_keywords = set(search_query.lower().split())
        title_keywords = set(product.title.lower().split())
        if query_keywords:
            match_ratio = len(query_keywords & title_keywords) / len(query_keywords)
            score += 25 * match_ratio

        # 6. Stock availability (0-5 points)
        if product.in_stock:
            score += 5

        # 7. Base relevance (0-5 points)
        score += product.relevance_score * 5

        return score

    async def _search_site_async(
        self,
        search_query: str,
        site_key: str,
        search_task: SearchTask
    ) -> List[SearchResult]:
        """
        Search a specific site using browser-use with structured output.

        Args:
            search_query: The search query
            site_key: Site identifier (e.g., "amazon", "flipkart")
            search_task: The search task context

        Returns:
            List of SearchResult objects
        """
        if not self.browser_use_available:
            return []

        try:
            from browser_use import Agent, BrowserProfile
            from pydantic import BaseModel, Field

            # Define structured output schema for browser-use (v0.11+)
            class ProductExtraction(BaseModel):
                """Schema for product extraction from e-commerce site."""
                products: List[dict] = Field(
                    description="List of products with title (str), url (str), price (float/null), rating (float 0-5/null), review_count (int/null), in_stock (bool/null)"
                )

            site_config = SITE_CONFIGS.get(site_key, {})
            site_name = site_config.get("name", site_key)
            site_domain = site_config.get("domain", f"{site_key}.com")

            # Configure browser profile with headless mode
            browser_profile = BrowserProfile(
                headless=Config.BROWSER_HEADLESS,  # Run in headless mode (no visible browser)
                disable_security=True,  # Allow cross-origin for e-commerce sites
            )

            # Create agent with structured output (browser-use v0.11+ API)
            # browser-use will auto-detect BROWSER_USE_API_KEY from environment
            agent = Agent(
                task=f"Go to {site_domain} and search for '{search_query}'. Extract top 5 products with: title (str), url (str), price (float in INR or null), rating (float 0-5 or null), review_count (int or null), in_stock (bool/null).",
                output_model_schema=ProductExtraction,
                browser_profile=browser_profile,
            )

            # Execute search with timeout
            result = await asyncio.wait_for(agent.run(max_steps=10), timeout=self.search_timeout)

            # Extract final result - browser-use v0.11 returns AgentHistoryList
            # The structured output is in the final result
            products = []
            if hasattr(result, 'final_result') and result.final_result:
                products = result.final_result().get('products', []) if isinstance(result.final_result(), dict) else []

            # Convert to SearchResult objects
            return [
                SearchResult(
                    title=p.get("title", "Unknown Product"),
                    url=p.get("url", ""),
                    price=p.get("price"),
                    source=site_name,
                    relevance_score=0.9,
                    rating=p.get("rating"),
                    review_count=p.get("review_count"),
                    in_stock=p.get("in_stock")
                )
                for p in products[:5] if isinstance(p, dict)
            ]
        except (asyncio.TimeoutError, Exception) as e:
            # Silent failure - return empty results
            return []

    async def _search_async(self, search_task: SearchTask) -> SearchResults:
        """
        Search all preferred sites for this item in parallel.

        Args:
            search_task: The search task to execute

        Returns:
            SearchResults with products from all sites
        """
        if not self.browser_use_available:
            return SearchResults(task=search_task, results=[], total_found=0)

        search_query = search_task.plan_item.search_query or search_task.search_query

        # Validate and filter preferred sites (removes Myntra for non-fashion)
        preferred_sites = self._validate_preferred_sites(search_task.plan_item)

        # Create search coroutines for each site
        site_coros = [
            self._search_site_async(search_query, site, search_task)
            for site in preferred_sites
        ]

        # Execute all site searches in parallel
        site_results = await asyncio.gather(*site_coros, return_exceptions=True)

        # Flatten results from all sites
        all_results = []
        for result in site_results:
            if isinstance(result, list):
                all_results.extend(result)

        # Score and rank products deterministically
        if all_results:
            # Get all prices for normalization
            all_prices = [r.price for r in all_results if r.price]

            # Score each product
            scored_results = [
                (self._score_product(r, search_query, preferred_sites, all_prices), r)
                for r in all_results
            ]

            # Sort by score (highest first), then by price (lowest first) as tiebreaker
            scored_results.sort(key=lambda x: (-x[0], x[1].price if x[1].price else float('inf')))

            # Extract sorted products
            all_results = [r for _, r in scored_results]

        return SearchResults(
            task=search_task,
            results=all_results[:10],  # Top 10 across all sites
            total_found=len(all_results)
        )

    def create_search_task(self, plan_item: PlanItem) -> SearchTask:
        """
        Convert a plan item into a search task.

        This method generates an optimized search query and filters
        based on the plan item's description, hints, and constraints.

        Args:
            plan_item: The item from the shopping plan

        Returns:
            SearchTask with query and filters
        """
        # Build search query from description and hints
        query_parts = [plan_item.description]
        query_parts.extend(plan_item.search_hints[:3])  # Top 3 hints
        search_query = " ".join(query_parts)

        # Parse constraints into filters
        filters = {}
        for constraint in plan_item.constraints:
            # Parse common constraint patterns
            constraint_lower = constraint.lower()

            if "budget:" in constraint_lower or "under $" in constraint_lower:
                # Extract price limit
                try:
                    price_str = constraint_lower.split("$")[1].split()[0]
                    filters["max_price"] = float(price_str)
                except (IndexError, ValueError):
                    pass

            if "color:" in constraint_lower:
                color = constraint_lower.split("color:")[1].strip()
                filters["color"] = color

            if "size:" in constraint_lower:
                size = constraint_lower.split("size:")[1].strip()
                filters["size"] = size

        return SearchTask(
            plan_item=plan_item,
            search_query=search_query,
            filters=filters,
        )

    def search(self, search_task: SearchTask) -> SearchResults:
        """
        Execute a search task (synchronous wrapper).

        Args:
            search_task: The search task to execute

        Returns:
            SearchResults with found products
        """
        from shopping_agent.app.async_utils import run_async
        return run_async(self._search_async(search_task))

    def search_multiple(self, plan_items: List[PlanItem]) -> List[SearchResults]:
        """
        Search for multiple plan items in parallel with rate limiting.

        Args:
            plan_items: List of items from the shopping plan

        Returns:
            List of SearchResults for each item
        """
        from shopping_agent.app.async_utils import run_async_parallel

        if not self.browser_use_available:
            return [
                SearchResults(task=self.create_search_task(item), results=[], total_found=0)
                for item in plan_items
            ]

        search_tasks = [self.create_search_task(item) for item in plan_items]
        all_results = []

        # Process in batches of max_parallel_searches
        for i in range(0, len(search_tasks), self.max_parallel_searches):
            batch = search_tasks[i:i + self.max_parallel_searches]
            coros = [self._search_async(task) for task in batch]
            batch_results = run_async_parallel(coros)

            # Handle exceptions gracefully
            for result in batch_results:
                if isinstance(result, Exception):
                    all_results.append(SearchResults(task=batch[0], results=[], total_found=0))
                else:
                    all_results.append(result)

        return all_results

    def get_instructions(self) -> str:
        """Get the agent's system instructions."""
        return BROWSER_SEARCH_SYSTEM_PROMPT

    def is_implemented(self) -> bool:
        """Check if this agent is fully implemented."""
        return self.browser_use_available
