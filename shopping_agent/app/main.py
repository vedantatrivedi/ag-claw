"""
CLI application for the shopping agent system.
"""

import json
import sys
import typer
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich import print as rprint
from rich.prompt import Confirm

from typing import List

from shopping_agent.app.orchestrator import ShoppingOrchestrator
from shopping_agent.app.config import Config
from shopping_agent.app.interactive import (
    run_interactive_planning,
    prompt_for_budget,
    prompt_for_required_budget,
    prompt_for_quantity,
    build_enhanced_request,
    gather_guided_preferences,
)
from shopping_agent.app.models import PlanItem, SearchResults

app = typer.Typer(help="Shopping Agent - Multi-agent shopping intent system")
console = Console()


def _execute_search(orchestrator: ShoppingOrchestrator, plan_items: List[dict]) -> None:
    """Execute product search for approved plan items."""
    import os

    items = [PlanItem(**item) for item in plan_items]

    # Try SerpAPI first (3x faster), then fall back to SearchAPI.com
    search_agent = None

    if os.getenv("SERPAPI_KEY"):
        try:
            from shopping_agent.app.agents.serpapi_search import SerpAPISearchAgent
            search_agent = SerpAPISearchAgent()
        except ValueError:
            pass

    if not search_agent and os.getenv("SEARCHAPI_KEY"):
        try:
            from shopping_agent.app.agents.searchapi_search import SearchAPISearchAgent
            search_agent = SearchAPISearchAgent()
        except ValueError:
            pass

    if not search_agent:
        console.print("\n[yellow]⚠ No search API key configured[/yellow]")
        console.print("[dim]Options:[/dim]")
        console.print("[dim]  1. SearchAPI.com (recommended): https://www.searchapi.io/[/dim]")
        console.print("[dim]     Then add to .env: SEARCHAPI_KEY=your_key_here[/dim]")
        console.print("[dim]  2. SerpAPI: https://serpapi.com/users/sign_up[/dim]")
        console.print("[dim]     Then add to .env: SERPAPI_KEY=your_key_here[/dim]\n")
        return

    with console.status("[bold green]Searching across the web..."):
        search_results = search_agent.search_multiple(items)

    _display_search_results(search_results)


def _display_search_results(search_results: List[SearchResults]) -> None:
    """Display search results with rich formatting."""
    from rich.panel import Panel
    from rich.columns import Columns
    from rich import box
    from rich.console import Group

    if not search_results:
        console.print("[yellow]No search results found[/yellow]\n")
        return

    console.print("\n[bold cyan]🎯 Top Ranked Products[/bold cyan]\n")

    for idx, search_result in enumerate(search_results, 1):
        item_desc = search_result.task.plan_item.description

        if not search_result.results:
            console.print(f"[bold yellow]📦 {item_desc}[/bold yellow]")
            console.print("[dim]  No products found[/dim]\n")
            continue

        console.print(f"[bold yellow]📦 {item_desc}[/bold yellow]")
        console.print(f"[dim]Found {search_result.total_found} products, showing top {len(search_result.results)} by score[/dim]\n")

        # Sort by score (highest first) - should already be sorted but ensure it
        sorted_products = sorted(search_result.results, key=lambda p: p.final_score or 0, reverse=True)

        # Create cards for side-by-side display
        cards = []
        for rank, product in enumerate(sorted_products, 1):
            # Truncate title for better display
            title = product.title[:50] + "..." if len(product.title) > 50 else product.title

            # Build product card content
            price_str = f"[bold green]₹{product.price:,.0f}[/bold green]" if product.price else "[dim]Price N/A[/dim]"

            # Rating with stars
            rating_display = ""
            if product.rating:
                stars = "⭐" * int(product.rating)
                rating_display = f"{stars} {product.rating:.1f}"
                if product.review_count:
                    if product.review_count >= 1000:
                        rating_display += f"\n[dim]({product.review_count//1000}K+ reviews)[/dim]"
                    else:
                        rating_display += f"\n[dim]({product.review_count} reviews)[/dim]"
            else:
                rating_display = "[dim]No ratings[/dim]"

            score_display = f"[bold magenta]Score: {product.final_score:.1f}[/bold magenta]" if product.final_score else ""

            # Image link (clickable)
            if product.image_url:
                image_indicator = f"[link={product.image_url}]🖼️  [blue]View Image[/blue][/link]"
            else:
                image_indicator = "[dim]No image[/dim]"

            # Build compact card with proper link handling
            buy_link = ""
            if product.url:
                # Clean URL for display
                if "google.com/search" in product.url:
                    buy_link = f"[link={product.url}][blue]🔍 View on Google Shopping[/blue][/link]"
                else:
                    buy_link = f"[link={product.url}][blue]🛒 Buy on {product.source}[/blue][/link]"
            else:
                buy_link = "[dim]Link not available[/dim]"

            card_content = f"""[bold]{title}[/bold]

{price_str}

{rating_display}

{score_display}

{image_indicator}

[yellow]{product.source}[/yellow]

{buy_link}"""

            # Create panel
            border_color = "green" if rank == 1 else "blue" if rank == 2 else "yellow"
            panel = Panel(
                card_content,
                title=f"[bold white]#{rank}[/bold white]",
                border_style=border_color,
                box=box.ROUNDED,
                padding=(1, 2),
                width=35,  # Fixed width for consistent layout
            )
            cards.append(panel)

        # Display cards side by side (3 columns)
        console.print(Columns(cards, equal=True, expand=False))
        console.print()

    # Summary
    console.print("[bold cyan]💳 Ready to purchase?[/bold cyan]")
    console.print("[dim]Click the 🛒 Buy Now links above to visit the product pages[/dim]")
    console.print("[dim]💡 Tip: Hold Ctrl/Cmd and click links to open in browser[/dim]\n")


@app.command()
def plan(
    request: str = typer.Argument(..., help="Shopping request in natural language"),
    no_postprocess: bool = typer.Option(
        False,
        "--no-postprocess",
        help="Disable post-processing of planner output",
    ),
    show_original: bool = typer.Option(
        False,
        "--show-original",
        help="Show original plan before post-processing",
    ),
    show_violations: bool = typer.Option(
        False,
        "--show-violations",
        help="Show guardrail violations (if any)",
    ),
    auto_clarify: bool = typer.Option(
        True,
        "--auto-clarify/--no-auto-clarify",
        help="Automatically ask for clarifications if scope is too wide",
    ),
) -> None:
    """
    Generate a shopping plan from a user request.

    Example:
        shopping-agent plan "Darth Vader themed birthday party for a 10-year-old"
    """
    console.print("\n[bold cyan]Shopping Agent - Planning[/bold cyan]\n")
    console.print(f"[yellow]Request:[/yellow] {request}\n")

    # Show helpful tips
    console.print("[dim]💡 Tip: For better results, include:[/dim]")
    console.print("[dim]   • Budget (e.g., 'under $150')[/dim]")
    console.print("[dim]   • Quantity (e.g., 'for 5 people')[/dim]")
    console.print("[dim]   • Context (e.g., 'outdoor in hot weather')[/dim]")
    console.print("[dim]   • Duration (e.g., 'for weekend trip')[/dim]\n")

    # Initialize orchestrator
    orchestrator = ShoppingOrchestrator()

    # Create shopping plan
    with console.status("[bold green]Generating shopping plan..."):
        result = orchestrator.create_shopping_plan(
            user_request=request,
            apply_postprocessing=not no_postprocess,
        )

    if not result.get("success"):
        console.print(f"[bold red]Error:[/bold red] {result.get('error')}")

        # Show error details if available
        error_data = result.get("error_data", {})
        if error_data:
            console.print("\n[dim]Error Details:[/dim]")
            if "error_type" in error_data:
                console.print(f"[dim]Type: {error_data['error_type']}[/dim]")
            if "traceback" in error_data and "--verbose" in sys.argv:
                console.print("\n[dim]Traceback:[/dim]")
                console.print(f"[dim]{error_data['traceback']}[/dim]")

        raise typer.Exit(code=1)

    # Display results FIRST
    plan = result.get("plan", {})

    # Show original plan if requested and available
    if show_original and result.get("original_plan"):
        console.print("[bold magenta]Original Plan (before post-processing):[/bold magenta]\n")
        original_json = json.dumps(result["original_plan"], indent=2)
        syntax = Syntax(original_json, "json", theme="monokai", line_numbers=False)
        console.print(Panel(syntax, title="Original Plan"))
        console.print()

    # Show final plan
    console.print("[bold green]Shopping Plan:[/bold green]\n")
    _display_plan(plan)

    # Show metadata
    console.print("\n[bold cyan]Metadata:[/bold cyan]")
    metadata = result.get("planner_metadata", {})
    metadata_table = Table(show_header=False)
    metadata_table.add_row("Model", metadata.get("model", "N/A"))
    metadata_table.add_row("Temperature", str(metadata.get("temperature", "N/A")))
    metadata_table.add_row("Tokens Used", str(metadata.get("tokens_used", "N/A")))
    metadata_table.add_row("Post-processing", str(metadata.get("postprocessing_applied", False)))
    console.print(metadata_table)

    # Show guardrail violations if requested
    if show_violations:
        violations = result.get("guardrail_violations", [])
        if violations:
            console.print("\n[bold yellow]Guardrail Violations:[/bold yellow]")
            for violation in violations:
                console.print(f"  • {violation}")
        else:
            console.print("\n[bold green]No guardrail violations detected[/bold green]")

    # ALWAYS ask for approval and loop until user confirms (if auto-clarify enabled)
    if auto_clarify:
        from shopping_agent.app.interactive import ask_if_plan_looks_good, prompt_for_modifications

        approved = False
        current_request = request

        while not approved:
            # Get clarifications from current plan
            plan_data = result.get("plan", {})
            clarifications = plan_data.get("clarifications_needed", [])

            # Ask if plan looks good (showing clarifications)
            if ask_if_plan_looks_good(clarifications):
                # User approved - break the loop
                console.print("\n[bold green]✓ Plan approved![/bold green]")
                approved = True

                # Execute browser search
                if plan_data and plan_data.get("items"):
                    _execute_search(orchestrator, plan_data["items"])

                break

            # User wants to refine
            modification = prompt_for_modifications()

            if not modification:
                # User skipped modification - ask again
                console.print("\n[dim]No changes requested. Showing current plan...[/dim]")
                continue

            # Build enhanced request
            current_request = f"{current_request}\n\nAdditional requirements: {modification}"

            # Re-run planning
            console.print("\n[bold cyan]Refining plan...[/bold cyan]\n")
            refined_result = orchestrator.create_shopping_plan(
                user_request=current_request,
                apply_postprocessing=not no_postprocess,
            )

            if refined_result.get("success"):
                # Update result for next iteration
                result = refined_result

                # Show refined plan
                console.print("[bold green]Refined Shopping Plan:[/bold green]\n")
                refined_plan = refined_result.get("plan", {})
                _display_plan(refined_plan)

                # Show updated metadata
                console.print("\n[bold cyan]Metadata:[/bold cyan]")
                metadata = refined_result.get("planner_metadata", {})
                metadata_table = Table(show_header=False)
                metadata_table.add_row("Model", metadata.get("model", "N/A"))
                metadata_table.add_row("Tokens Used", str(metadata.get("tokens_used", "N/A")))
                console.print(metadata_table)
                console.print()
            else:
                console.print(f"[bold red]Error refining plan:[/bold red] {refined_result.get('error')}")
                console.print("[dim]Keeping previous plan...[/dim]\n")

    console.print()


@app.command()
def info() -> None:
    """
    Show information about the shopping agent system.
    """
    orchestrator = ShoppingOrchestrator()

    console.print("\n[bold cyan]Shopping Agent System Information[/bold cyan]\n")

    # Show agent info
    info = orchestrator.get_agent_info()

    # Agents table
    console.print("[bold]Agents:[/bold]")
    agents_table = Table()
    agents_table.add_column("Name")
    agents_table.add_column("Model")
    agents_table.add_column("Temperature")
    agents_table.add_column("Status")

    for agent in info["agents"]:
        status_color = "green" if agent["implemented"] else "yellow"
        agents_table.add_row(
            agent["name"],
            agent["model"],
            str(agent["temperature"]),
            f"[{status_color}]{agent['status']}[/{status_color}]",
        )

    console.print(agents_table)
    console.print()

    # Workflows table
    console.print("[bold]Workflows:[/bold]")
    workflows_table = Table()
    workflows_table.add_column("Name")
    workflows_table.add_column("Description")
    workflows_table.add_column("Status")

    for workflow in info["workflows"]:
        status_color = "green" if workflow["status"] == "active" else "yellow"
        workflows_table.add_row(
            workflow["name"],
            workflow["description"],
            f"[{status_color}]{workflow['status']}[/{status_color}]",
        )

    console.print(workflows_table)
    console.print()


@app.command()
def architecture() -> None:
    """
    Explain the multi-agent architecture.
    """
    orchestrator = ShoppingOrchestrator()
    explanation = orchestrator.explain_architecture()

    console.print(Panel(explanation, title="Architecture", border_style="cyan"))


@app.command()
def interactive(
    request: str = typer.Argument(..., help="Shopping request in natural language"),
    no_postprocess: bool = typer.Option(
        False,
        "--no-postprocess",
        help="Disable post-processing of planner output",
    ),
    ask_budget: bool = typer.Option(
        False,
        "--ask-budget",
        help="Always prompt for budget upfront",
    ),
) -> None:
    """
    Interactive mode - fully interactive with all prompts.

    Example:
        shopping-agent interactive "cricket equipment for my son" --ask-budget
    """
    console.print("\n[bold cyan]Shopping Agent - Interactive Mode[/bold cyan]\n")
    console.print(f"[yellow]Request:[/yellow] {request}\n")

    budget = None
    quantity = None

    # Only prompt for budget if explicitly requested
    if ask_budget:
        budget = prompt_for_budget()
        quantity = prompt_for_quantity()

    # Build enhanced request
    enhanced_request = build_enhanced_request(request, budget, quantity)

    # Run interactive planning with clarification loop
    result = run_interactive_planning(
        user_request=enhanced_request,
        apply_postprocessing=not no_postprocess,
    )

    if not result.get("success"):
        console.print(f"[bold red]Error:[/bold red] {result.get('error')}")

        # Show error details if available
        error_data = result.get("error_data", {})
        if error_data:
            console.print("\n[dim]Error Details:[/dim]")
            if "error_type" in error_data:
                console.print(f"[dim]Type: {error_data['error_type']}[/dim]")

        raise typer.Exit(code=1)

    # Display results
    plan = result.get("plan", {})

    console.print("\n[bold green]Final Shopping Plan:[/bold green]\n")
    _display_plan(plan)

    # Show metadata
    console.print("\n[bold cyan]Metadata:[/bold cyan]")
    metadata = result.get("planner_metadata", {})
    metadata_table = Table(show_header=False)
    metadata_table.add_row("Model", metadata.get("model", "N/A"))
    metadata_table.add_row("Temperature", str(metadata.get("temperature", "N/A")))
    metadata_table.add_row("Tokens Used", str(metadata.get("tokens_used", "N/A")))
    if budget:
        metadata_table.add_row("Budget", f"${budget:.2f}")
    console.print(metadata_table)
    console.print()


@app.command("guided-party")
def guided_party(
    request: str = typer.Argument(..., help="Broad party-planning request"),
    no_postprocess: bool = typer.Option(
        False,
        "--no-postprocess",
        help="Disable post-processing of planner output",
    ),
) -> None:
    """
    Guided party planning with preference collection and budget pre-auth.
    """
    console.print("\n[bold cyan]Shopping Agent - Guided Party Planning[/bold cyan]\n")
    console.print(f"[yellow]Request:[/yellow] {request}\n")

    orchestrator = ShoppingOrchestrator()

    with console.status("[bold green]Generating party preference questions..."):
        questions = orchestrator.generate_guided_party_questions(request)

    console.print("[bold]Tell me a bit more before I lock the budget:[/bold]\n")
    preferences = gather_guided_preferences(questions)
    budget_inr = prompt_for_required_budget()

    console.print("\n[bold cyan]Creating pre-authorization...[/bold cyan]")
    preauth_result = orchestrator.create_guided_party_preauth(
        preferences_answers=preferences,
        budget_inr=budget_inr,
    )

    if not preauth_result.get("success"):
        console.print(f"[bold red]Error:[/bold red] {preauth_result.get('error')}")
        raise typer.Exit(code=1)

    preauth = preauth_result.get("preauth", {})
    console.print("\n[bold green]Pre-auth created[/bold green]")
    console.print(f"[dim]Order ID:[/dim] {preauth.get('order_id', 'N/A')}")
    console.print(f"[dim]Redirect URL:[/dim] {preauth.get('redirect_url', 'N/A')}")
    console.print("\n[bold yellow]Open the checkout URL and authorize the pre-auth before continuing.[/bold yellow]")

    if not Confirm.ask("[bold cyan]Continue after authorization is complete?[/bold cyan]", default=True):
        console.print("[yellow]Stopped before authorization polling.[/yellow]")
        raise typer.Exit(code=0)

    console.print("\n[bold cyan]Waiting for authorization...[/bold cyan]")
    result = orchestrator.complete_guided_party_after_authorization(
        user_request=request,
        preferences_answers=preferences,
        budget_inr=budget_inr,
        preauth=preauth,
        apply_postprocessing=not no_postprocess,
    )

    if not result.get("success"):
        console.print(f"[bold red]Error:[/bold red] {result.get('error')}")
        if result.get("stage") == "authorization":
            console.print("[dim]Pre-auth was created but not authorized successfully.[/dim]")
        raise typer.Exit(code=1)

    preauth = result.get("preauth", {})
    console.print("\n[bold green]Pre-auth authorized[/bold green]")
    console.print(f"[dim]Order ID:[/dim] {preauth.get('order_id', 'N/A')}")
    console.print(f"[dim]Redirect URL:[/dim] {preauth.get('redirect_url', 'N/A')}")
    console.print(f"[dim]Authorized Status:[/dim] {preauth.get('authorized_status', 'N/A')}\n")

    console.print("[bold green]Shopping Plan:[/bold green]\n")
    _display_plan(result.get("plan", {}))

    console.print("\n[bold cyan]Placeholder Listing Results:[/bold cyan]\n")
    listing_results = [SearchResults(**entry) for entry in result.get("listing_results", [])]
    _display_search_results(listing_results)


@app.command()
def example(
    name: str = typer.Argument("party", help="Example name: party, interview, etc."),
) -> None:
    """
    Run a predefined example.

    Available examples: party, interview, gift, desk
    """
    examples = {
        "party": "Darth Vader themed birthday party for a 10-year-old under $150",
        "interview": "Software engineering interview prep kit",
        "gift": "Gift basket for a new mom",
        "desk": "Desk setup for a remote software engineer",
    }

    if name not in examples:
        console.print(f"[red]Unknown example: {name}[/red]")
        console.print(f"Available examples: {', '.join(examples.keys())}")
        raise typer.Exit(code=1)

    request = examples[name]
    console.print(f"\n[bold cyan]Running example:[/bold cyan] {name}\n")

    # Run the plan command with the example request
    plan(request=request, show_original=False, show_violations=False)


def _display_plan(plan: dict) -> None:
    """Display a shopping plan in a formatted way."""
    items = plan.get("items", [])

    # Items table
    if items:
        items_table = Table(title="Items", show_lines=True)
        items_table.add_column("Description", style="cyan", width=40)
        items_table.add_column("Qty", justify="center", width=5)
        items_table.add_column("Required", justify="center", width=10)
        items_table.add_column("Intent", style="dim", width=30)

        for item in items:
            required_icon = "✓" if item.get("required") else "○"
            required_color = "green" if item.get("required") else "yellow"

            items_table.add_row(
                item.get("description", ""),
                str(item.get("quantity", 1)),
                f"[{required_color}]{required_icon}[/{required_color}]",
                item.get("intent", ""),
            )

        console.print(items_table)

    # Assumptions
    assumptions = plan.get("assumptions", [])
    if assumptions:
        console.print("\n[bold]Assumptions:[/bold]")
        for assumption in assumptions:
            console.print(f"  • {assumption}")

    # Clarifications needed
    clarifications = plan.get("clarifications_needed", [])
    if clarifications:
        console.print("\n[bold yellow]Clarifications Needed:[/bold yellow]")
        for clarification in clarifications:
            console.print(f"  ? {clarification}")


@app.command()
def discord() -> None:
    """
    Start the Discord bot.

    Requires DISCORD_BOT_TOKEN in .env or environment variables.
    """
    from shopping_agent.app.discord_bot import run_bot

    console.print("\n[bold cyan]Starting Discord Bot...[/bold cyan]\n")
    run_bot()


if __name__ == "__main__":
    app()
