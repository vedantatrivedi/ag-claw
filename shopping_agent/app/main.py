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

from typing import List

from shopping_agent.app.orchestrator import ShoppingOrchestrator
from shopping_agent.app.config import Config
from shopping_agent.app.interactive import (
    run_interactive_planning,
    prompt_for_budget,
    prompt_for_quantity,
    build_enhanced_request,
)
from shopping_agent.app.models import PlanItem, SearchResults

app = typer.Typer(help="Shopping Agent - Multi-agent shopping intent system")
console = Console()


def _execute_search(orchestrator: ShoppingOrchestrator, plan_items: List[dict]) -> None:
    """Execute browser search for approved plan items."""
    from shopping_agent.app.agents.browser_search import BrowserSearchAgent

    items = [PlanItem(**item) for item in plan_items]
    browser_agent = BrowserSearchAgent()

    if not browser_agent.is_implemented():
        console.print("\n[yellow]⚠ Browser search not available (browser-use not installed)[/yellow]")
        console.print("[dim]Install with: poetry add browser-use langchain-openai[/dim]\n")
        return

    console.print("\n[bold cyan]🔍 Searching for products...[/bold cyan]\n")

    with console.status("[bold green]Searching across Amazon, Flipkart, Myntra, Ajio, Croma..."):
        search_results = browser_agent.search_multiple(items)

    _display_search_results(search_results)


def _display_search_results(search_results: List[SearchResults]) -> None:
    """Display search results with rich formatting."""
    if not search_results:
        console.print("[yellow]No search results found[/yellow]\n")
        return

    for search_result in search_results:
        item_desc = search_result.task.plan_item.description
        console.print(f"\n[bold cyan]📦 {item_desc}[/bold cyan]")

        if not search_result.results:
            console.print("[dim]  No products found[/dim]")
            continue

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Site", style="yellow", width=10)
        table.add_column("Product", style="cyan", no_wrap=False, width=35)
        table.add_column("Price", style="green", width=10)
        table.add_column("Rating", style="yellow", width=10)
        table.add_column("Reviews", style="dim", width=8)
        table.add_column("URL", style="blue", no_wrap=False, width=25)

        for product in search_result.results[:10]:  # Show top 10 (multi-site)
            price_str = f"₹{product.price:.0f}" if product.price else "N/A"
            rating_str = f"⭐{product.rating:.1f}" if product.rating else "N/A"
            reviews_str = str(product.review_count) if product.review_count else "N/A"
            url_display = product.url[:25] + "..." if len(product.url) > 25 else product.url

            table.add_row(
                product.source,
                product.title[:35],
                price_str,
                rating_str,
                reviews_str,
                f"[link={product.url}]{url_display}[/link]"
            )

        console.print(table)
        console.print(f"[dim]Total found: {search_result.total_found}[/dim]")

    console.print()


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
