#!/usr/bin/env python3
"""Quick integration test for browser search agent."""

import os

# Set test token BEFORE imports (config validates on import)
os.environ['AWS_BEARER_TOKEN_BEDROCK'] = 'test-token-for-validation'

from shopping_agent.app.agents.browser_search import BrowserSearchAgent
from shopping_agent.app.models import PlanItem

def test_site_validation():
    """Test site validation logic."""
    agent = BrowserSearchAgent()

    # Test 1: Fashion item should keep Myntra
    fashion_item = PlanItem(
        description="blue denim jeans",
        intent="clothing",
        preferred_sites=["myntra", "ajio", "amazon"]
    )
    validated = agent._validate_preferred_sites(fashion_item)
    print(f"✓ Fashion item validation: {validated}")
    assert "myntra" in validated

    # Test 2: Electronics should filter out Myntra
    electronics_item = PlanItem(
        description="wireless headphones",
        intent="audio",
        preferred_sites=["myntra", "croma", "amazon"]
    )
    validated = agent._validate_preferred_sites(electronics_item)
    print(f"✓ Electronics item validation: {validated}")
    assert "myntra" not in validated
    assert "croma" in validated

    # Test 3: Scoring determinism
    from shopping_agent.app.models import SearchResult

    product = SearchResult(
        title="wireless headphones noise cancelling",
        url="http://test.com",
        price=100.0,
        source="amazon",
        relevance_score=0.9,
        rating=4.5,
        review_count=500,
        in_stock=True
    )

    score1 = agent._score_product(product, "wireless headphones", ["amazon"], [100.0])
    score2 = agent._score_product(product, "wireless headphones", ["amazon"], [100.0])
    print(f"✓ Scoring determinism: {score1} == {score2}")
    assert score1 == score2

    print("\n✅ All validation tests passed!")

if __name__ == "__main__":
    test_site_validation()
