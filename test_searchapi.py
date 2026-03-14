#!/usr/bin/env python3
"""Quick test of SearchAPI.com integration."""

import os
from dotenv import load_dotenv
from shopping_agent.app.models import PlanItem
from shopping_agent.app.agents.searchapi_search import SearchAPISearchAgent

load_dotenv()

def test_searchapi():
    """Test SearchAPI.com with a simple search."""
    print("\n🔍 Testing SearchAPI.com Integration\n")

    # Check API key
    api_key = os.getenv("SEARCHAPI_KEY")
    if not api_key:
        print("❌ SEARCHAPI_KEY not found in .env")
        print("\nGet free API key at: https://www.searchapi.io/")
        print("Then add to .env: SEARCHAPI_KEY=your_key_here")
        return

    print(f"✅ API key found: {api_key[:10]}...")

    # Create test item
    plan_item = PlanItem(
        description="wireless headphones",
        quantity=1,
        intent="purchase",
        search_query="wireless headphones under $100",
        preferred_sites=["amazon", "flipkart"],
        search_hints=["noise cancelling", "bluetooth"],
        constraints=["budget: under $100"]
    )

    print(f"\n📦 Searching for: {plan_item.description}")
    print(f"   Query: {plan_item.search_query}")

    # Search
    agent = SearchAPISearchAgent()
    task = agent.create_search_task(plan_item)
    results = agent.search(task)

    # Display results
    print(f"\n✅ Found {results.total_found} products:\n")

    if not results.results:
        print("⚠️  No products found")
        return

    for i, product in enumerate(results.results[:5], 1):
        price_str = f"₹{product.price:.2f}" if product.price else "N/A"
        rating_str = f"⭐{product.rating}" if product.rating else "No rating"
        reviews = f"({product.review_count:,} reviews)" if product.review_count else ""

        print(f"{i}. {product.title[:60]}")
        print(f"   {price_str} {rating_str} {reviews}")
        print(f"   {product.source}")
        print(f"   {product.url[:80]}...")
        print()

if __name__ == "__main__":
    test_searchapi()
