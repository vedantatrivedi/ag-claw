"""Tests for browser search agent."""

import pytest
from shopping_agent.app.models import PlanItem
from shopping_agent.app.agents.browser_search import BrowserSearchAgent
from shopping_agent.app.async_utils import run_async, run_async_parallel
import asyncio


class TestBrowserSearchAgent:
    """Test browser search agent functionality."""

    def test_initialization(self):
        """Test agent initialization."""
        agent = BrowserSearchAgent()
        assert agent.name == "browser_search"
        assert agent.max_parallel_searches == 3
        assert agent.search_timeout == 30

    def test_classify_item_category(self):
        """Test item category classification."""
        agent = BrowserSearchAgent()

        # Fashion items
        assert agent._classify_item_category("blue denim jeans") == "fashion"
        assert agent._classify_item_category("cotton t-shirt") == "fashion"

        # Footwear
        assert agent._classify_item_category("running shoes") == "footwear"

        # Electronics
        assert agent._classify_item_category("wireless headphones") == "electronics"
        assert agent._classify_item_category("laptop 16GB RAM") == "electronics"

        # Sports
        assert agent._classify_item_category("cricket bat") == "sports"

        # General
        assert agent._classify_item_category("random item") == "general"

    def test_validate_preferred_sites_fashion(self):
        """Test site validation for fashion items."""
        agent = BrowserSearchAgent()

        # Fashion item suggested to Myntra - should be kept
        item = PlanItem(
            description="blue denim jeans",
            intent="clothing",
            preferred_sites=["myntra", "ajio"]
        )
        validated = agent._validate_preferred_sites(item)
        assert "myntra" in validated
        assert "ajio" in validated

    def test_validate_preferred_sites_electronics(self):
        """Test site validation for electronics items."""
        agent = BrowserSearchAgent()

        # Electronics item suggested to Myntra - should be filtered out
        item = PlanItem(
            description="wireless headphones",
            intent="audio device",
            preferred_sites=["myntra", "croma", "amazon"]
        )
        validated = agent._validate_preferred_sites(item)
        assert "myntra" not in validated  # Myntra is weak for electronics
        assert "croma" in validated
        assert "amazon" in validated

    def test_validate_preferred_sites_fallback(self):
        """Test fallback when all sites filtered out."""
        agent = BrowserSearchAgent()

        # Electronics to fashion-only sites - should fall back to amazon/flipkart
        item = PlanItem(
            description="laptop",
            intent="work device",
            preferred_sites=["myntra", "ajio"]
        )
        validated = agent._validate_preferred_sites(item)
        assert "amazon" in validated or "flipkart" in validated

    def test_create_search_task(self):
        """Test search task creation."""
        agent = BrowserSearchAgent()

        item = PlanItem(
            description="wireless headphones",
            quantity=1,
            intent="audio device",
            search_hints=["noise cancelling", "bluetooth"],
            constraints=["budget: under $100", "color: black"]
        )

        task = agent.create_search_task(item)
        assert "wireless headphones" in task.search_query
        assert task.filters.get("max_price") == 100.0
        assert task.filters.get("color") == "black"

    def test_is_implemented(self):
        """Test implementation check."""
        agent = BrowserSearchAgent()
        # May be True or False depending on whether browser-use is installed
        assert isinstance(agent.is_implemented(), bool)

    def test_score_product(self):
        """Test deterministic product scoring."""
        from shopping_agent.app.models import SearchResult
        agent = BrowserSearchAgent()

        # Create test products
        cheap_product = SearchResult(
            title="wireless headphones noise cancelling bluetooth",
            url="http://example.com/1",
            price=50.0,
            source="amazon",
            relevance_score=0.9,
            rating=4.5,
            review_count=1000,
            in_stock=True
        )

        expensive_product = SearchResult(
            title="premium wireless headphones",
            url="http://example.com/2",
            price=150.0,
            source="flipkart",
            relevance_score=0.8,
            rating=3.5,
            review_count=50,
            in_stock=False
        )

        search_query = "wireless headphones noise cancelling"
        preferred_sites = ["amazon"]
        all_prices = [50.0, 150.0]

        # Score both products
        score1 = agent._score_product(cheap_product, search_query, preferred_sites, all_prices)
        score2 = agent._score_product(expensive_product, search_query, preferred_sites, all_prices)

        # Cheap product from preferred site with good title match should score higher
        assert score1 > score2

        # Scores should be deterministic
        assert score1 == agent._score_product(cheap_product, search_query, preferred_sites, all_prices)

    def test_score_product_price_competitiveness(self):
        """Test price scoring component."""
        from shopping_agent.app.models import SearchResult
        agent = BrowserSearchAgent()

        cheap = SearchResult(title="item", url="url", price=100.0, source="site", relevance_score=0.5)
        expensive = SearchResult(title="item", url="url", price=200.0, source="site", relevance_score=0.5)

        all_prices = [100.0, 200.0]

        score_cheap = agent._score_product(cheap, "item", [], all_prices)
        score_expensive = agent._score_product(expensive, "item", [], all_prices)

        # Cheaper product should have higher score
        assert score_cheap > score_expensive


class TestAsyncUtils:
    """Test async utility functions."""

    def test_run_async(self):
        """Test run_async helper."""
        async def sample_coro():
            await asyncio.sleep(0.01)
            return "result"

        result = run_async(sample_coro())
        assert result == "result"

    def test_run_async_parallel(self):
        """Test run_async_parallel helper."""
        async def sample_coro(value):
            await asyncio.sleep(0.01)
            return value * 2

        coros = [sample_coro(i) for i in range(3)]
        results = run_async_parallel(coros)
        assert results == [0, 2, 4]

    def test_run_async_parallel_with_exception(self):
        """Test run_async_parallel handles exceptions."""
        async def failing_coro():
            raise ValueError("test error")

        async def success_coro():
            return "success"

        results = run_async_parallel([failing_coro(), success_coro()])
        assert len(results) == 2
        assert isinstance(results[0], ValueError)
        assert results[1] == "success"
