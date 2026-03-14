#!/usr/bin/env python3
"""Test the new product display with ranking."""

import os
from dotenv import load_dotenv
from shopping_agent.app.models import PlanItem
from shopping_agent.app.agents.serpapi_search import SerpAPISearchAgent

load_dotenv()

def test_new_display():
    """Test new display format."""
    print("\n🎯 Testing New Product Display\n")
    print("=" * 80)

    # Single test item
    plan_item = PlanItem(
        description="Cricket helmet for youth",
        quantity=1,
        intent="purchase",
        search_query="youth cricket helmet with faceguard",
        preferred_sites=["amazon", "flipkart"],
        search_hints=["ISI certified", "adjustable"],
        constraints=[]
    )

    agent = SerpAPISearchAgent()
    task = agent.create_search_task(plan_item)

    print(f"📦 Searching for: {plan_item.description}")
    print(f"   Query: {task.search_query}\n")

    results = agent.search(task)

    print(f"✅ Found {results.total_found} products")
    print(f"   Showing top {len(results.results)} ranked results\n")
    print("=" * 80)

    # Display ranked results
    for rank, product in enumerate(results.results, 1):
        print(f"\n🏆 RANK #{rank}")
        print(f"   Score: {product.final_score:.1f}/100")
        print(f"   Title: {product.title}")
        print(f"   Price: ₹{product.price:,.0f}" if product.price else "   Price: N/A")

        if product.rating:
            stars = "⭐" * int(product.rating)
            print(f"   Rating: {stars} {product.rating:.1f}", end="")
            if product.review_count:
                print(f" ({product.review_count:,} reviews)")
            else:
                print()
        else:
            print("   Rating: No ratings yet")

        print(f"   Source: {product.source}")

        if product.image_url:
            print(f"   Image: {product.image_url[:60]}...")

        if product.url:
            print(f"   Link: {product.url[:60]}...")

        print()

if __name__ == "__main__":
    test_new_display()
