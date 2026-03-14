#!/usr/bin/env python3
"""Full end-to-end test with actual browser search."""

from shopping_agent.app.orchestrator import ShoppingOrchestrator
from shopping_agent.app.agents.browser_search import BrowserSearchAgent
from shopping_agent.app.models import PlanItem
from rich.console import Console
from rich.table import Table

console = Console()

def main():
    console.print("\n[bold cyan]🛒 Shopping Agent - Full Test with Browser Search[/bold cyan]\n")

    # Step 1: Generate plan
    console.print("[yellow]Step 1:[/yellow] Generating shopping plan...")
    orchestrator = ShoppingOrchestrator()

    result = orchestrator.create_shopping_plan(
        'wireless headphones under 100 dollars',
        apply_postprocessing=True
    )

    if not result['success']:
        console.print(f"[red]❌ Plan failed:[/red] {result['error']}")
        return

    plan = result['plan']
    items = plan['items']

    console.print(f"[green]✅ Plan generated with {len(items)} items:[/green]")
    for i, item in enumerate(items, 1):
        console.print(f"   {i}. {item['description']}")

    # Step 2: Execute browser search
    console.print("\n[yellow]Step 2:[/yellow] Searching for products across sites...")
    console.print("[dim]This will take 30-60 seconds...[/dim]\n")

    browser_agent = BrowserSearchAgent()

    if not browser_agent.is_implemented():
        console.print("[red]❌ browser-use not available[/red]")
        return

    # Convert to PlanItem objects
    plan_items = [PlanItem(**item) for item in items]

    # Execute search
    with console.status("[bold green]Searching Amazon, Flipkart, Croma..."):
        search_results = browser_agent.search_multiple(plan_items)

    # Step 3: Display results
    console.print("\n[bold cyan]📊 Search Results:[/bold cyan]\n")

    for search_result in search_results:
        item_desc = search_result.task.plan_item.description
        console.print(f"\n[bold yellow]📦 {item_desc}[/bold yellow]")

        if not search_result.results:
            console.print("[dim]  No products found[/dim]")
            continue

        # Create results table
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Rank", style="dim", width=5)
        table.add_column("Site", style="yellow", width=10)
        table.add_column("Product", style="cyan", no_wrap=False, width=40)
        table.add_column("Price", style="green", width=10)
        table.add_column("Rating", style="yellow", width=12)
        table.add_column("Stock", style="dim", width=6)

        for rank, product in enumerate(search_result.results[:5], 1):
            price_str = f"₹{product.price:,.0f}" if product.price else "N/A"
            rating_str = f"⭐{product.rating:.1f} ({product.review_count:,})" if product.rating else "N/A"
            stock_str = "✓" if product.in_stock else "✗"

            table.add_row(
                str(rank),
                product.source,
                product.title[:40] + "..." if len(product.title) > 40 else product.title,
                price_str,
                rating_str,
                stock_str
            )

        console.print(table)
        console.print(f"[dim]Total found: {search_result.total_found} products[/dim]")

        # Show best value
        if search_result.results:
            best = search_result.results[0]
            console.print(f"\n[bold green]💡 Best value:[/bold green] {best.title[:50]}")
            if best.price:
                console.print(f"   Price: ₹{best.price:,.0f}")
            if best.rating:
                console.print(f"   Rating: ⭐{best.rating:.1f} ({best.review_count:,} reviews)")
            console.print(f"   Link: [link={best.url}]{best.url}[/link]")

    console.print("\n[bold green]✅ Search complete![/bold green]\n")

if __name__ == "__main__":
    main()
