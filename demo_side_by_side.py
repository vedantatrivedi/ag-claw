#!/usr/bin/env python3
"""Demo the side-by-side display."""

from rich.console import Console
from rich.panel import Panel
from rich.columns import Columns
from rich import box

console = Console()

# Create sample product cards
cards = []

# Card 1 - Best (Green)
card1 = Panel(
    """[bold]Cricket Helmet with Faceguard – Lightweigh...[/bold]

[bold green]₹926[/bold green]

[dim]No ratings[/dim]

[bold magenta]Score: 65.7[/bold magenta]

🖼️  [dim]Image available[/dim]

[yellow]amazon.in[/yellow]

[blue]🛒 Buy Now[/blue]""",
    title="[bold white]#1[/bold white]",
    border_style="green",
    box=box.ROUNDED,
    padding=(1, 2),
    width=35,
)

# Card 2 - Second (Blue)
card2 = Panel(
    """[bold]Klapp 20-20 Cricket Helmet + Neck Guard...[/bold]

[bold green]₹699[/bold green]

⭐⭐⭐⭐ 4.2
[dim](1K+ reviews)[/dim]

[bold magenta]Score: 58.6[/bold magenta]

🖼️  [dim]Image available[/dim]

[yellow]amazon.in[/yellow]

[blue]🛒 Buy Now[/blue]""",
    title="[bold white]#2[/bold white]",
    border_style="blue",
    box=box.ROUNDED,
    padding=(1, 2),
    width=35,
)

# Card 3 - Third (Yellow)
card3 = Panel(
    """[bold]JJ Jonex Economy Cricket Helmet With Steel...[/bold]

[bold green]₹625[/bold green]

[dim]No ratings[/dim]

[bold magenta]Score: 57.0[/bold magenta]

🖼️  [dim]Image available[/dim]

[yellow]Sppartos[/yellow]

[blue]🛒 Buy Now[/blue]""",
    title="[bold white]#3[/bold white]",
    border_style="yellow",
    box=box.ROUNDED,
    padding=(1, 2),
    width=35,
)

cards = [card1, card2, card3]

console.print("\n[bold cyan]🎯 Top Ranked Products[/bold cyan]\n")
console.print("[bold yellow]📦 Youth cricket helmet with faceguard[/bold yellow]")
console.print("[dim]Found 20 products, showing top 3 by score[/dim]\n")

# Display side by side
console.print(Columns(cards, equal=True, expand=False))

console.print()
console.print("[bold cyan]💳 Ready to purchase?[/bold cyan]")
console.print("[dim]Click the 🛒 Buy Now links above to visit the product pages[/dim]\n")
