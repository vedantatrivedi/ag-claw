"""
Guardrails and validation for agent outputs.
"""

from typing import List, Tuple
from pydantic import ValidationError

from shopping_agent.app.models import ShoppingPlan, PlanItem


class GuardrailViolation(Exception):
    """Raised when a guardrail check fails."""

    pass


def validate_schema(data: dict) -> Tuple[bool, str]:
    """
    Validate that data matches ShoppingPlan schema.

    Returns:
        (is_valid, error_message)
    """
    try:
        ShoppingPlan(**data)
        return True, ""
    except ValidationError as e:
        return False, str(e)


def check_no_urls(plan: ShoppingPlan) -> Tuple[bool, List[str]]:
    """
    Ensure plan contains no URLs (planner should not return product links).

    Returns:
        (is_valid, list_of_violations)
    """
    violations = []
    url_indicators = ["http://", "https://", "www.", ".com", ".org", ".net"]

    for item in plan.items:
        for indicator in url_indicators:
            if indicator in item.description.lower():
                violations.append(f"URL detected in item description: {item.description}")
            if indicator in item.intent.lower():
                violations.append(f"URL detected in item intent: {item.intent}")
            for hint in item.search_hints:
                if indicator in hint.lower():
                    violations.append(f"URL detected in search hint: {hint}")

    return len(violations) == 0, violations


def check_no_stores(plan: ShoppingPlan) -> Tuple[bool, List[str]]:
    """
    Ensure plan doesn't mention specific stores (planner should be store-agnostic).

    Returns:
        (is_valid, list_of_violations)
    """
    violations = []
    store_names = {
        "amazon",
        "walmart",
        "target",
        "ebay",
        "etsy",
        "alibaba",
        "costco",
        "home depot",
        "best buy",
        "macy's",
        "nordstrom",
    }

    for item in plan.items:
        description_lower = item.description.lower()
        intent_lower = item.intent.lower()

        for store in store_names:
            if store in description_lower:
                violations.append(f"Store name '{store}' in description: {item.description}")
            if store in intent_lower:
                violations.append(f"Store name '{store}' in intent: {item.intent}")

    return len(violations) == 0, violations


def check_item_concreteness(plan: ShoppingPlan) -> Tuple[bool, List[str]]:
    """
    Ensure all items are concrete and searchable.

    Returns:
        (is_valid, list_of_violations)
    """
    violations = []
    abstract_terms = {
        "something",
        "anything",
        "whatever",
        "miscellaneous",
        "various",
        "assorted",
        "general",
    }

    for item in plan.items:
        description_lower = item.description.lower()

        # Check for abstract terms
        for term in abstract_terms:
            if term in description_lower:
                violations.append(
                    f"Abstract term '{term}' in description: {item.description}"
                )

        # Check description length
        word_count = len(description_lower.split())
        if word_count < 2:
            violations.append(f"Description too short (single word): {item.description}")

    return len(violations) == 0, violations


def check_plan_completeness(plan: ShoppingPlan) -> Tuple[bool, List[str]]:
    """
    Ensure plan has minimum required fields populated.

    Returns:
        (is_valid, list_of_violations)
    """
    violations = []

    if not plan.items:
        violations.append("Plan has no items")

    for idx, item in enumerate(plan.items):
        if not item.description:
            violations.append(f"Item {idx} has empty description")
        if not item.intent:
            violations.append(f"Item {idx} has empty intent")
        if item.quantity < 1:
            violations.append(f"Item {idx} has invalid quantity: {item.quantity}")

    return len(violations) == 0, violations


def apply_guardrails(plan: ShoppingPlan, strict: bool = False) -> Tuple[bool, List[str]]:
    """
    Apply all guardrails to a shopping plan.

    Args:
        plan: The shopping plan to validate
        strict: If True, raise exception on any violation. If False, return violations.

    Returns:
        (is_valid, list_of_all_violations)

    Raises:
        GuardrailViolation: If strict=True and any check fails
    """
    all_violations = []

    # Check plan completeness
    is_valid, violations = check_plan_completeness(plan)
    if not is_valid:
        all_violations.extend(violations)

    # Check for URLs
    is_valid, violations = check_no_urls(plan)
    if not is_valid:
        all_violations.extend(violations)

    # Check for store names
    is_valid, violations = check_no_stores(plan)
    if not is_valid:
        all_violations.extend(violations)

    # Check item concreteness
    is_valid, violations = check_item_concreteness(plan)
    if not is_valid:
        all_violations.extend(violations)

    if strict and all_violations:
        raise GuardrailViolation(f"Guardrail violations detected:\n" + "\n".join(all_violations))

    return len(all_violations) == 0, all_violations
