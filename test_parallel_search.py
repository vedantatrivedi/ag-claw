#!/usr/bin/env python3
"""Test parallel vs sequential search performance."""

import os
import time
from dotenv import load_dotenv
from shopping_agent.app.models import PlanItem
from shopping_agent.app.agents.serpapi_search import SerpAPISearchAgent

load_dotenv()

def test_parallel_search():
    """Test parallel search with cricket equipment."""
    print("\n🏏 Testing Parallel Search - Cricket Equipment\n")
    print("=" * 80)

    # Multiple cricket items (typical planner output)
    plan_items = [
        PlanItem(
            description="Cricket bat for youth player",
            quantity=1,
            intent="purchase",
            search_query="youth cricket bat lightweight",
            preferred_sites=["amazon", "flipkart"],
            search_hints=["size 5", "english willow"],
            constraints=[]
        ),
        PlanItem(
            description="Cricket helmet with face guard",
            quantity=1,
            intent="purchase",
            search_query="cricket helmet face guard youth",
            preferred_sites=["amazon", "flipkart"],
            search_hints=["adjustable", "ISI certified"],
            constraints=[]
        ),
        PlanItem(
            description="Cricket batting pads",
            quantity=1,
            intent="purchase",
            search_query="cricket batting pads youth size",
            preferred_sites=["amazon", "flipkart"],
            search_hints=["lightweight", "comfortable"],
            constraints=[]
        ),
        PlanItem(
            description="Cricket batting gloves",
            quantity=1,
            intent="purchase",
            search_query="cricket batting gloves youth",
            preferred_sites=["amazon", "flipkart"],
            search_hints=["padded", "grip"],
            constraints=[]
        ),
    ]

    print(f"📦 Searching for {len(plan_items)} items:\n")
    for i, item in enumerate(plan_items, 1):
        print(f"   {i}. {item.description}")
    print()

    agent = SerpAPISearchAgent()

    # Test with parallel search
    print("🔄 Running PARALLEL search...")
    start = time.time()
    parallel_results = agent.search_multiple(plan_items)
    parallel_time = time.time() - start

    print(f"⏱️  Parallel time: {parallel_time:.2f}s")
    print(f"📊 Results:")
    for i, result in enumerate(parallel_results, 1):
        print(f"   Item {i}: {result.total_found} products found")
    print()

    # Show estimated sequential time
    avg_time_per_search = 1.4  # Average SerpAPI response time
    estimated_sequential = len(plan_items) * avg_time_per_search
    speedup = estimated_sequential / parallel_time if parallel_time > 0 else 0

    print("=" * 80)
    print("📊 PERFORMANCE COMPARISON\n")
    print(f"Items searched:        {len(plan_items)}")
    print(f"Parallel time:         {parallel_time:.2f}s")
    print(f"Estimated sequential:  {estimated_sequential:.2f}s")
    print(f"Speedup:               {speedup:.1f}x faster")
    print(f"Time saved:            {estimated_sequential - parallel_time:.2f}s")
    print()

    # Show sample results
    print("=" * 80)
    print("🏏 SAMPLE RESULTS\n")

    for i, result in enumerate(parallel_results[:2], 1):  # Show first 2 items
        if result.results:
            item_desc = result.task.plan_item.description
            print(f"{i}. {item_desc}")
            print(f"   Found {result.total_found} products:\n")

            for j, product in enumerate(result.results[:3], 1):
                price = f"₹{product.price:.0f}" if product.price else "N/A"
                rating = f"⭐{product.rating:.1f}" if product.rating else "—"
                reviews = f"({product.review_count:,})" if product.review_count else ""

                print(f"   {j}. {product.title[:55]}")
                print(f"      {price} | {rating} {reviews} | {product.source}")
            print()

if __name__ == "__main__":
    test_parallel_search()
