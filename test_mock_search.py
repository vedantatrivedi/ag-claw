#!/usr/bin/env python3
"""Mock test showing full search flow without real API calls."""

from shopping_agent.app.models import PlanItem, SearchResult, SearchTask, SearchResults
from shopping_agent.app.agents.browser_search import BrowserSearchAgent

def test_full_flow():
    """Simulate complete search flow with mock data."""

    # Create mock plan items (what planner would generate)
    items = [
        PlanItem(
            description="Wireless noise cancelling headphones",
            quantity=1,
            intent="Primary audio device for music and calls",
            required=True,
            search_hints=["bluetooth", "noise cancelling", "over-ear"],
            constraints=["budget: under $100"],
            search_query="wireless noise cancelling headphones bluetooth",
            preferred_sites=["amazon", "flipkart", "croma"]
        ),
        PlanItem(
            description="Headphone carrying case",
            quantity=1,
            intent="Protection for travel",
            required=False,
            search_hints=["hard case", "travel"],
            constraints=["compact"],
            search_query="headphone hard case compact",
            preferred_sites=["amazon", "flipkart"]
        )
    ]

    # Create browser agent
    agent = BrowserSearchAgent()

    print("🔍 Mock Product Search Results\n")
    print("=" * 80)

    # Mock search results (simulating what browser-use would return)
    for item in items:
        print(f"\n📦 {item.description}")
        print("-" * 80)

        # Simulate site validation
        validated_sites = agent._validate_preferred_sites(item)
        print(f"Searching sites: {', '.join(validated_sites)}")

        # Create mock products
        mock_products = [
            SearchResult(
                title=f"Sony WH-1000XM5 Wireless Noise Cancelling Headphones",
                url="https://amazon.in/dp/B09XS7JWHH",
                price=24990.0,
                source="Amazon",
                relevance_score=0.95,
                rating=4.6,
                review_count=12450,
                in_stock=True
            ),
            SearchResult(
                title=f"JBL Tune 760NC Wireless Over-Ear NC Headphones",
                url="https://flipkart.com/jbl-tune-760nc",
                price=6999.0,
                source="Flipkart",
                relevance_score=0.88,
                rating=4.3,
                review_count=8920,
                in_stock=True
            ),
            SearchResult(
                title=f"Bose QuietComfort 45 Wireless Headphones",
                url="https://croma.com/bose-qc45",
                price=29900.0,
                source="Croma",
                relevance_score=0.92,
                rating=4.7,
                review_count=3240,
                in_stock=True
            ),
            SearchResult(
                title=f"Sony WH-CH720N Wireless NC Headphones",
                url="https://amazon.in/dp/B0BYWK9VCV",
                price=7990.0,
                source="Amazon",
                relevance_score=0.85,
                rating=4.4,
                review_count=5680,
                in_stock=True
            ),
            SearchResult(
                title=f"Sennheiser HD 450BT Wireless NC Headphones",
                url="https://flipkart.com/sennheiser-hd-450bt",
                price=8999.0,
                source="Flipkart",
                relevance_score=0.83,
                rating=4.2,
                review_count=2150,
                in_stock=False
            ),
        ]

        # Score products
        all_prices = [p.price for p in mock_products if p.price]
        scored_products = []
        for product in mock_products:
            score = agent._score_product(
                product,
                item.search_query,
                validated_sites,
                all_prices
            )
            scored_products.append((score, product))

        # Sort by score
        scored_products.sort(key=lambda x: -x[0])

        # Display results
        print(f"\n{'Rank':<6}{'Site':<12}{'Product':<45}{'Price':<12}{'Rating':<12}{'Score':<8}")
        print("-" * 100)

        for rank, (score, product) in enumerate(scored_products[:5], 1):
            price_str = f"₹{product.price:,.0f}" if product.price else "N/A"
            rating_str = f"⭐{product.rating:.1f} ({product.review_count:,})" if product.rating else "N/A"
            stock_indicator = "✓" if product.in_stock else "✗"

            print(f"{rank:<6}{product.source:<12}{product.title[:43]:<45}{price_str:<12}{rating_str:<12}{score:.1f} {stock_indicator}")

        print(f"\n💡 Best value: {scored_products[0][1].title[:50]} - ₹{scored_products[0][1].price:,.0f}")

    print("\n" + "=" * 80)
    print("✅ Mock search complete! This shows how results would be ranked.")
    print("\nRanking factors:")
    print("  • Price competitiveness (25 pts)")
    print("  • Rating quality (15 pts)")
    print("  • Review popularity (10 pts)")
    print("  • Site preference (15 pts)")
    print("  • Title relevance (25 pts)")
    print("  • Stock availability (5 pts)")
    print("  • Base relevance (5 pts)")

if __name__ == "__main__":
    import os
    os.environ['AWS_BEARER_TOKEN_BEDROCK'] = 'mock-token'
    test_full_flow()
