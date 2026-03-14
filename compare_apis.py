#!/usr/bin/env python3
"""Compare SearchAPI.com vs SerpAPI side by side."""

import os
from dotenv import load_dotenv
from shopping_agent.app.models import PlanItem
from shopping_agent.app.agents.searchapi_search import SearchAPISearchAgent
from shopping_agent.app.agents.serpapi_search import SerpAPISearchAgent
import time

load_dotenv()

def compare_apis():
    """Compare both APIs with same query."""
    print("\n🔬 API Comparison: SearchAPI.com vs SerpAPI\n")

    # Test query
    plan_item = PlanItem(
        description="Sony wireless headphones",
        quantity=1,
        intent="purchase",
        search_query="Sony wireless headphones noise cancelling",
        preferred_sites=["amazon", "flipkart"],
        search_hints=["WH-1000XM5", "bluetooth"],
        constraints=[]
    )

    print(f"📦 Query: {plan_item.search_query}\n")
    print("=" * 80)

    # Test SearchAPI.com
    print("\n🔵 SearchAPI.com Results:")
    print("-" * 80)
    try:
        start = time.time()
        searchapi_agent = SearchAPISearchAgent()
        task = searchapi_agent.create_search_task(plan_item)
        searchapi_results = searchapi_agent.search(task)
        searchapi_time = time.time() - start

        print(f"⏱️  Time: {searchapi_time:.2f}s")
        print(f"📊 Found: {searchapi_results.total_found} products\n")

        for i, p in enumerate(searchapi_results.results[:5], 1):
            price = f"₹{p.price:.0f}" if p.price else "N/A"
            rating = f"⭐{p.rating:.1f}" if p.rating else "—"
            reviews = f"({p.review_count:,})" if p.review_count else ""
            print(f"{i}. {p.title[:55]}")
            print(f"   {price} | {rating} {reviews} | {p.source}")
    except Exception as e:
        print(f"❌ Error: {e}")
        searchapi_results = None
        searchapi_time = 0

    # Test SerpAPI
    print("\n🟢 SerpAPI Results:")
    print("-" * 80)
    try:
        start = time.time()
        serpapi_agent = SerpAPISearchAgent()
        task = serpapi_agent.create_search_task(plan_item)
        serpapi_results = serpapi_agent.search(task)
        serpapi_time = time.time() - start

        print(f"⏱️  Time: {serpapi_time:.2f}s")
        print(f"📊 Found: {serpapi_results.total_found} products\n")

        for i, p in enumerate(serpapi_results.results[:5], 1):
            price = f"₹{p.price:.0f}" if p.price else "N/A"
            rating = f"⭐{p.rating:.1f}" if p.rating else "—"
            reviews = f"({p.review_count:,})" if p.review_count else ""
            print(f"{i}. {p.title[:55]}")
            print(f"   {price} | {rating} {reviews} | {p.source}")
    except Exception as e:
        print(f"❌ Error: {e}")
        serpapi_results = None
        serpapi_time = 0

    # Comparison
    print("\n" + "=" * 80)
    print("📊 Comparison Summary\n")

    if searchapi_results and serpapi_results:
        print(f"⏱️  Speed:")
        print(f"   SearchAPI.com: {searchapi_time:.2f}s")
        print(f"   SerpAPI:       {serpapi_time:.2f}s")
        faster = "SearchAPI.com" if searchapi_time < serpapi_time else "SerpAPI"
        print(f"   Winner: {faster}\n")

        print(f"📊 Results Count:")
        print(f"   SearchAPI.com: {searchapi_results.total_found}")
        print(f"   SerpAPI:       {serpapi_results.total_found}\n")

        # Count products with ratings
        searchapi_ratings = sum(1 for p in searchapi_results.results if p.rating)
        serpapi_ratings = sum(1 for p in serpapi_results.results if p.rating)

        print(f"⭐ Products with Ratings:")
        print(f"   SearchAPI.com: {searchapi_ratings}/{searchapi_results.total_found}")
        print(f"   SerpAPI:       {serpapi_ratings}/{serpapi_results.total_found}\n")

        # Count products with prices
        searchapi_prices = sum(1 for p in searchapi_results.results if p.price)
        serpapi_prices = sum(1 for p in serpapi_results.results if p.price)

        print(f"💰 Products with Prices:")
        print(f"   SearchAPI.com: {searchapi_prices}/{searchapi_results.total_found}")
        print(f"   SerpAPI:       {serpapi_prices}/{serpapi_results.total_found}\n")

        # Recommendation
        print("🏆 Recommendation:")
        searchapi_score = searchapi_results.total_found + searchapi_ratings * 2 + searchapi_prices
        serpapi_score = serpapi_results.total_found + serpapi_ratings * 2 + serpapi_prices

        if searchapi_score > serpapi_score:
            print("   Use SearchAPI.com (better data quality)")
        elif serpapi_score > searchapi_score:
            print("   Use SerpAPI (better data quality)")
        else:
            print(f"   Both equal - use faster one ({faster})")

if __name__ == "__main__":
    compare_apis()
