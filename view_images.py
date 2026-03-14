#!/usr/bin/env python3
"""Open product images in browser for viewing."""

import os
import sys
import webbrowser
import tempfile
from dotenv import load_dotenv
from shopping_agent.app.models import PlanItem
from shopping_agent.app.agents.serpapi_search import SerpAPISearchAgent

load_dotenv()

def create_image_gallery(search_results):
    """Create HTML gallery with product images."""
    html = """
<!DOCTYPE html>
<html>
<head>
    <title>Product Images</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }
        h1 {
            color: #333;
            text-align: center;
        }
        .product-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        .product-card {
            background: white;
            border-radius: 8px;
            padding: 15px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .product-card img {
            width: 100%;
            height: 250px;
            object-fit: contain;
            border-radius: 4px;
            background: #f9f9f9;
        }
        .product-title {
            font-weight: bold;
            margin: 10px 0;
            color: #333;
        }
        .product-price {
            color: #2e7d32;
            font-size: 1.2em;
            font-weight: bold;
        }
        .product-rating {
            color: #ff9800;
            margin: 5px 0;
        }
        .product-score {
            background: #e3f2fd;
            padding: 5px 10px;
            border-radius: 4px;
            display: inline-block;
            margin: 5px 0;
        }
        .buy-button {
            display: inline-block;
            background: #1976d2;
            color: white;
            padding: 10px 20px;
            text-decoration: none;
            border-radius: 4px;
            margin-top: 10px;
        }
        .buy-button:hover {
            background: #1565c0;
        }
        .rank-badge {
            position: absolute;
            top: 10px;
            right: 10px;
            background: #4caf50;
            color: white;
            padding: 5px 10px;
            border-radius: 20px;
            font-weight: bold;
        }
        .product-card {
            position: relative;
        }
    </style>
</head>
<body>
    <h1>🎯 Product Gallery</h1>
"""

    for result in search_results:
        item_desc = result.task.plan_item.description
        html += f'<h2>📦 {item_desc}</h2>\n<div class="product-grid">\n'

        for rank, product in enumerate(result.results, 1):
            price_str = f"₹{product.price:,.0f}" if product.price else "Price N/A"

            rating_html = ""
            if product.rating:
                stars = "⭐" * int(product.rating)
                rating_html = f"{stars} {product.rating:.1f}"
                if product.review_count:
                    rating_html += f" ({product.review_count:,} reviews)"

            score_html = f"Score: {product.final_score:.1f}/100" if product.final_score else ""

            img_url = product.image_url if product.image_url else "https://via.placeholder.com/300x250?text=No+Image"

            html += f"""
    <div class="product-card">
        <div class="rank-badge">#{rank}</div>
        <img src="{img_url}" alt="{product.title}">
        <div class="product-title">{product.title}</div>
        <div class="product-price">{price_str}</div>
        <div class="product-rating">{rating_html}</div>
        <div class="product-score">{score_html}</div>
        <div style="color: #666; margin: 5px 0;">From: {product.source}</div>
        <a href="{product.url}" class="buy-button" target="_blank">🛒 Buy Now</a>
    </div>
"""

        html += '</div>\n'

    html += """
</body>
</html>
"""
    return html

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 view_images.py 'search query'")
        print("Example: python3 view_images.py 'cricket helmet youth'")
        sys.exit(1)

    query = sys.argv[1]

    print(f"\n🔍 Searching for: {query}")
    print("⏳ Please wait...\n")

    plan_item = PlanItem(
        description=query,
        quantity=1,
        intent="purchase",
        search_query=query,
        preferred_sites=["amazon", "flipkart"],
        search_hints=[],
        constraints=[]
    )

    agent = SerpAPISearchAgent()
    task = agent.create_search_task(plan_item)
    result = agent.search(task)

    if not result.results:
        print("❌ No products found")
        sys.exit(1)

    print(f"✅ Found {result.total_found} products")
    print("📸 Opening image gallery in browser...\n")

    # Create HTML gallery
    html_content = create_image_gallery([result])

    # Save to temp file
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.html') as f:
        f.write(html_content)
        temp_path = f.name

    # Open in browser
    webbrowser.open('file://' + temp_path)
    print(f"✅ Gallery opened in browser!")
    print(f"   File: {temp_path}")
    print("\n💡 Close the browser tab when done viewing images\n")

if __name__ == "__main__":
    main()
