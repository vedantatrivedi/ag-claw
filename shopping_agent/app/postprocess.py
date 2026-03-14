"""
Deterministic post-processing for planner outputs.
"""

from typing import List, Set
from difflib import SequenceMatcher

from shopping_agent.app.models import PlanItem, ShoppingPlan
from shopping_agent.app.config import Config


def trim_whitespace(plan: ShoppingPlan) -> ShoppingPlan:
    """Trim whitespace from all string fields."""
    for item in plan.items:
        item.description = item.description.strip()
        item.intent = item.intent.strip()
        item.search_hints = [hint.strip() for hint in item.search_hints]
        item.constraints = [constraint.strip() for constraint in item.constraints]

    plan.assumptions = [assumption.strip() for assumption in plan.assumptions]
    plan.clarifications_needed = [
        clarification.strip() for clarification in plan.clarifications_needed
    ]

    return plan


def normalize_quantities(plan: ShoppingPlan) -> ShoppingPlan:
    """Ensure all quantities are positive integers."""
    for item in plan.items:
        if item.quantity < 1:
            item.quantity = 1

    return plan


def remove_vague_items(plan: ShoppingPlan) -> ShoppingPlan:
    """
    Remove items with vague descriptions that would be hard to search.

    Vague items include single-word descriptions or generic terms.
    """
    vague_keywords = {
        "stuff",
        "things",
        "items",
        "decorations",
        "accessories",
        "supplies",
        "equipment",
        "tools",
        "materials",
    }

    filtered_items = []
    for item in plan.items:
        description_lower = item.description.lower()
        words = description_lower.split()

        # Remove if description is too short
        if len(item.description) < Config.MIN_DESCRIPTION_LENGTH:
            continue

        # Remove if description is a single vague word
        if len(words) == 1 and words[0] in vague_keywords:
            continue

        filtered_items.append(item)

    plan.items = filtered_items
    return plan


def calculate_similarity(text1: str, text2: str) -> float:
    """Calculate similarity between two strings (0.0 to 1.0)."""
    return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()


def deduplicate_items(plan: ShoppingPlan) -> ShoppingPlan:
    """
    Remove near-duplicate items based on description similarity.

    Keep the item with more constraints/hints (better specified).
    """
    if len(plan.items) <= 1:
        return plan

    unique_items: List[PlanItem] = []
    seen_descriptions: Set[str] = set()

    for item in plan.items:
        is_duplicate = False

        for existing_item in unique_items:
            similarity = calculate_similarity(item.description, existing_item.description)

            if similarity >= Config.SIMILARITY_THRESHOLD:
                is_duplicate = True

                # If current item has more details, replace the existing one
                current_details = len(item.search_hints) + len(item.constraints)
                existing_details = len(existing_item.search_hints) + len(
                    existing_item.constraints
                )

                if current_details > existing_details:
                    unique_items.remove(existing_item)
                    unique_items.append(item)

                break

        if not is_duplicate:
            unique_items.append(item)

    plan.items = unique_items
    return plan


def sort_items(plan: ShoppingPlan) -> ShoppingPlan:
    """Sort items: required items first, then optional items."""
    plan.items = sorted(plan.items, key=lambda x: (not x.required, x.description))
    return plan


def limit_items(plan: ShoppingPlan) -> ShoppingPlan:
    """Limit total number of items to prevent overly long plans."""
    if len(plan.items) > Config.MAX_ITEMS_PER_PLAN:
        # Keep all required items, then add optional items up to the limit
        required_items = [item for item in plan.items if item.required]
        optional_items = [item for item in plan.items if not item.required]

        if len(required_items) > Config.MAX_ITEMS_PER_PLAN:
            # Too many required items - just truncate
            plan.items = required_items[: Config.MAX_ITEMS_PER_PLAN]
        else:
            remaining_slots = Config.MAX_ITEMS_PER_PLAN - len(required_items)
            plan.items = required_items + optional_items[:remaining_slots]

    return plan


def postprocess_plan(plan: ShoppingPlan) -> ShoppingPlan:
    """
    Apply all post-processing steps to a shopping plan.

    Steps (in order):
    1. Trim whitespace
    2. Normalize quantities
    3. Remove vague items
    4. Deduplicate items
    5. Sort items (required first)
    6. Limit total items
    """
    plan = trim_whitespace(plan)
    plan = normalize_quantities(plan)
    plan = remove_vague_items(plan)
    plan = deduplicate_items(plan)
    plan = sort_items(plan)
    plan = limit_items(plan)

    return plan
