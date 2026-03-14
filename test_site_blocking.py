#!/usr/bin/env python3
"""Test e-commerce sites to show blocking evidence."""

import asyncio
from browser_use import Agent, BrowserProfile
from rich.console import Console
from rich.table import Table

console = Console()

SITES_TO_TEST = {
    "amazon": "https://amazon.in",
    "flipkart": "https://flipkart.com",
    "myntra": "https://myntra.com",
    "ajio": "https://ajio.com",
    "croma": "https://croma.com",
}

async def test_site_access(site_name: str, site_url: str):
    """Test if we can access a site and search for products."""
    console.print(f"\n[bold cyan]Testing {site_name.upper()}[/bold cyan]")
    console.print(f"URL: {site_url}")
    console.print("-" * 80)

    browser_profile = BrowserProfile(
        headless=True,
        disable_security=True,
    )

    agent = Agent(
        task=f"Go to {site_url} and search for 'wireless headphones'. Tell me if you see: 1) A search bar, 2) Product listings, 3) CAPTCHA, 4) Access Denied message, 5) Login requirement.",
        browser_profile=browser_profile,
    )

    blocking_evidence = {
        "accessible": False,
        "captcha": False,
        "access_denied": False,
        "login_required": False,
        "search_available": False,
        "error_message": None,
        "steps_taken": []
    }

    try:
        console.print("🔍 Attempting to access site...")
        result = await asyncio.wait_for(agent.run(max_steps=5), timeout=30)

        # Analyze agent history for blocking evidence
        if hasattr(result, 'history'):
            for step in result.history:
                if hasattr(step, 'model_output'):
                    output = str(step.model_output)
                    blocking_evidence["steps_taken"].append(output[:200])

                    # Check for blocking indicators
                    output_lower = output.lower()
                    if 'captcha' in output_lower:
                        blocking_evidence["captcha"] = True
                    if 'access denied' in output_lower or 'blocked' in output_lower:
                        blocking_evidence["access_denied"] = True
                    if 'login' in output_lower or 'sign in' in output_lower:
                        blocking_evidence["login_required"] = True
                    if 'search bar' in output_lower or 'search box' in output_lower:
                        blocking_evidence["search_available"] = True

        # Check final result
        if hasattr(result, 'final_result'):
            final = result.final_result()
            if final:
                console.print(f"\n[green]Final Result:[/green] {str(final)[:300]}")
                blocking_evidence["accessible"] = True

    except asyncio.TimeoutError:
        blocking_evidence["error_message"] = "Timeout after 30 seconds"
        console.print("[red]❌ Timeout[/red]")
    except Exception as e:
        blocking_evidence["error_message"] = str(e)[:200]
        console.print(f"[red]❌ Error: {type(e).__name__}[/red]")

    # Display blocking evidence
    console.print("\n[bold yellow]Blocking Evidence:[/bold yellow]")
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Check", style="cyan")
    table.add_column("Status", style="yellow")

    table.add_row("✅ Site Accessible", "✓" if blocking_evidence["accessible"] else "✗")
    table.add_row("🔍 Search Available", "✓" if blocking_evidence["search_available"] else "✗")
    table.add_row("🤖 CAPTCHA Detected", "✓ BLOCKING" if blocking_evidence["captcha"] else "✗")
    table.add_row("🚫 Access Denied", "✓ BLOCKING" if blocking_evidence["access_denied"] else "✗")
    table.add_row("🔐 Login Required", "✓ BLOCKING" if blocking_evidence["login_required"] else "✗")

    if blocking_evidence["error_message"]:
        table.add_row("⚠️  Error", blocking_evidence["error_message"])

    console.print(table)

    # Show steps taken
    if blocking_evidence["steps_taken"]:
        console.print("\n[dim]Steps taken:[/dim]")
        for i, step in enumerate(blocking_evidence["steps_taken"][:3], 1):
            console.print(f"  {i}. {step}")

    # Summary
    is_blocked = (
        blocking_evidence["captcha"] or
        blocking_evidence["access_denied"] or
        (blocking_evidence["login_required"] and not blocking_evidence["search_available"])
    )

    if is_blocked:
        console.print(f"\n[bold red]🚫 {site_name.upper()} IS BLOCKING AUTOMATION[/bold red]")
    elif blocking_evidence["accessible"]:
        console.print(f"\n[bold green]✅ {site_name.upper()} IS ACCESSIBLE[/bold green]")
    else:
        console.print(f"\n[bold yellow]⚠️  {site_name.upper()} STATUS UNCLEAR[/bold yellow]")

    return blocking_evidence

async def main():
    console.print("\n[bold cyan]🤖 E-Commerce Site Blocking Test[/bold cyan]")
    console.print("[dim]Testing if major Indian e-commerce sites block browser automation...[/dim]\n")

    results = {}

    for site_name, site_url in SITES_TO_TEST.items():
        try:
            results[site_name] = await test_site_access(site_name, site_url)
            await asyncio.sleep(2)  # Brief pause between tests
        except KeyboardInterrupt:
            console.print("\n[yellow]Test interrupted by user[/yellow]")
            break

    # Final Summary
    console.print("\n" + "=" * 80)
    console.print("[bold cyan]📊 FINAL SUMMARY[/bold cyan]\n")

    summary_table = Table(show_header=True, header_style="bold magenta")
    summary_table.add_column("Site", style="cyan")
    summary_table.add_column("CAPTCHA", style="yellow")
    summary_table.add_column("Access Denied", style="red")
    summary_table.add_column("Login Wall", style="blue")
    summary_table.add_column("Status", style="bold")

    blocked_count = 0
    for site_name, evidence in results.items():
        captcha = "✓" if evidence.get("captcha") else "✗"
        denied = "✓" if evidence.get("access_denied") else "✗"
        login = "✓" if evidence.get("login_required") else "✗"

        is_blocked = evidence.get("captcha") or evidence.get("access_denied")
        status = "[red]BLOCKED[/red]" if is_blocked else "[green]OK[/green]"

        if is_blocked:
            blocked_count += 1

        summary_table.add_row(
            site_name.upper(),
            captcha,
            denied,
            login,
            status
        )

    console.print(summary_table)

    console.print(f"\n[bold red]🚫 {blocked_count}/{len(results)} sites are blocking automation[/bold red]")
    console.print("\n[dim]This is why browser-use cannot extract product data from these sites.[/dim]")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[yellow]Test cancelled[/yellow]")
