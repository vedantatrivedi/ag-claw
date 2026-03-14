"""
Interactive clarification workflow for the shopping agent.
"""

from typing import Dict, List, Optional
from rich.console import Console
from rich.prompt import Prompt, Confirm

from shopping_agent.app.orchestrator import ShoppingOrchestrator
from shopping_agent.app.models import ShoppingPlan


console = Console()


def gather_clarifications(
    clarifications_needed: List[str],
    assumptions: List[str]
) -> Dict[str, str]:
    """
    Interactively gather answers to clarification questions.

    Args:
        clarifications_needed: List of questions to ask the user
        assumptions: List of assumptions made by the planner

    Returns:
        Dictionary of question -> answer pairs
    """
    answers = {}

    if not clarifications_needed:
        return answers

    console.print("\n[bold yellow]The planner needs some clarifications:[/bold yellow]\n")

    # Show assumptions first
    if assumptions:
        console.print("[dim]Current assumptions:[/dim]")
        for assumption in assumptions:
            console.print(f"[dim]  • {assumption}[/dim]")
        console.print()

    # Ask each clarification question
    for idx, question in enumerate(clarifications_needed, 1):
        console.print(f"[cyan]{idx}. {question}[/cyan]")
        answer = Prompt.ask("   [dim]Your answer[/dim]", default="skip")

        if answer.lower() != "skip":
            answers[question] = answer

        console.print()

    return answers


def should_refine_plan(clarifications_needed: List[str]) -> bool:
    """
    Ask user if they want to refine the plan with clarifications.

    Only prompts if clarifications are critical (not just nice-to-haves).

    Args:
        clarifications_needed: List of clarification questions

    Returns:
        True if user wants to provide clarifications
    """
    # Check if any clarifications are critical (contain keywords)
    critical_keywords = ["budget", "how many", "which", "what type", "duration"]
    has_critical = any(
        any(keyword in q.lower() for keyword in critical_keywords)
        for q in clarifications_needed
    )

    if not has_critical:
        # Not critical - skip interaction
        return False

    return Confirm.ask(
        "\n[bold yellow]The scope seems wide. Would you like to provide more details?[/bold yellow]",
        default=False
    )


def ask_if_plan_looks_good(clarifications: List[str] = None) -> bool:
    """
    Ask user if the plan looks good, showing clarifications if any.

    Args:
        clarifications: List of clarification questions

    Returns:
        True if user approves the plan (wants to proceed)
        False if user wants to refine/modify
    """
    if clarifications:
        console.print("\n[bold yellow]📋 To improve this plan, consider:[/bold yellow]")
        for idx, clarification in enumerate(clarifications, 1):
            console.print(f"   {idx}. {clarification}")
        console.print()

    response = Confirm.ask(
        "[bold cyan]Approve this plan?[/bold cyan] [dim](yes = proceed, no = refine)[/dim]",
        default=True
    )
    return response


def prompt_for_modifications() -> Optional[str]:
    """
    Prompt user for what they want to add or change.

    Returns:
        User's modification request or None
    """
    console.print("\n[cyan]What would you like to add or change?[/cyan]")
    console.print("[dim]Examples: 'add more hydration items', 'remove optional items', 'add budget of $150'[/dim]")

    modification = Prompt.ask("   [dim]Your request[/dim]", default="")

    if modification.strip():
        return modification
    return None


def run_interactive_planning(
    user_request: str,
    apply_postprocessing: bool = True,
) -> Dict:
    """
    Run interactive planning with post-plan clarification.

    Shows the plan first, then asks if user wants to refine it.

    Args:
        user_request: Initial user shopping request
        apply_postprocessing: Whether to apply post-processing

    Returns:
        Final plan result
    """
    orchestrator = ShoppingOrchestrator()

    # Initial planning
    result = orchestrator.create_shopping_plan(
        user_request=user_request,
        apply_postprocessing=apply_postprocessing,
    )

    if not result.get("success"):
        return result

    # Plan was successful - it's already been displayed by the caller
    # Now check if user wants to refine

    # Check for critical clarifications that suggest scope is too wide
    plan_data = result.get("plan", {})
    clarifications = plan_data.get("clarifications_needed", [])

    # Only auto-prompt if there are critical clarifications
    critical_keywords = ["budget", "how many", "which type", "what type", "duration"]
    has_critical = any(
        any(keyword in q.lower() for keyword in critical_keywords)
        for q in clarifications
    )

    if not has_critical:
        # No critical clarifications - plan is good as-is
        return result

    # Has critical clarifications - ask if they want to refine
    if not ask_if_plan_looks_good():
        # User wants to refine
        modification = prompt_for_modifications()

        if modification:
            # Build enhanced request
            enhanced_request = f"{user_request}\n\nAdditional requirements: {modification}"

            # Re-run planning
            console.print("\n[bold cyan]Refining plan...[/bold cyan]\n")
            refined_result = orchestrator.create_shopping_plan(
                user_request=enhanced_request,
                apply_postprocessing=apply_postprocessing,
            )
            return refined_result

    return result


def prompt_for_budget() -> Optional[float]:
    """
    Prompt user for budget constraint.

    Returns:
        Budget amount or None if not specified
    """
    if Confirm.ask("\n[bold]Do you have a budget in mind?[/bold]", default=False):
        budget_str = Prompt.ask("   [dim]Budget amount (e.g., 150)[/dim]")
        try:
            return float(budget_str)
        except ValueError:
            console.print("[yellow]Invalid budget, continuing without budget constraint[/yellow]")
            return None
    return None


def prompt_for_required_budget() -> float:
    """
    Prompt until a valid budget is provided.

    Returns:
        Budget amount in INR
    """
    while True:
        budget_str = Prompt.ask("\n[bold]Approved budget in INR[/bold]")
        try:
            budget = float(budget_str)
        except ValueError:
            console.print("[yellow]Enter a numeric budget amount[/yellow]")
            continue

        if budget <= 0:
            console.print("[yellow]Budget must be greater than zero[/yellow]")
            continue

        return budget


def gather_guided_preferences(questions: List[str]) -> Dict[str, str]:
    """
    Ask a fixed sequence of guided preference questions.

    Args:
        questions: Questions to ask

    Returns:
        Mapping of question to answer
    """
    answers: Dict[str, str] = {}
    for idx, question in enumerate(questions, 1):
        console.print(f"[cyan]{idx}. {question}[/cyan]")
        answers[question] = Prompt.ask("   [dim]Answer[/dim]").strip()
        console.print()
    return answers


def prompt_for_quantity() -> Optional[int]:
    """
    Prompt user for quantity if applicable.

    Returns:
        Quantity or None if not specified
    """
    if Confirm.ask("\n[bold]Do you need multiple of something?[/bold]", default=False):
        quantity_str = Prompt.ask("   [dim]How many? (e.g., 5)[/dim]")
        try:
            return int(quantity_str)
        except ValueError:
            console.print("[yellow]Invalid quantity, continuing without quantity constraint[/yellow]")
            return None
    return None


def build_enhanced_request(
    original_request: str,
    budget: Optional[float] = None,
    quantity: Optional[int] = None,
    additional_context: Optional[str] = None,
) -> str:
    """
    Build an enhanced request with additional context.

    Args:
        original_request: Original user request
        budget: Optional budget constraint
        quantity: Optional quantity constraint
        additional_context: Any additional context to include

    Returns:
        Enhanced request string
    """
    enhanced = original_request

    if budget:
        enhanced += f"\n\nBudget: ${budget:.2f}"

    if quantity:
        enhanced += f"\nQuantity needed: {quantity}"

    if additional_context:
        enhanced += f"\n\nAdditional context: {additional_context}"

    return enhanced
