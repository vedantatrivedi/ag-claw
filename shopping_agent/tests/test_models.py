"""
Tests for Pydantic models.
"""

import pytest
from pydantic import ValidationError

from shopping_agent.app.models import (
    PlanItem,
    ShoppingPlan,
    SearchResult,
    SearchTask,
    AgentResponse,
)


class TestPlanItem:
    """Tests for PlanItem model."""

    def test_valid_plan_item(self) -> None:
        """Test creating a valid plan item."""
        item = PlanItem(
            description="Darth Vader birthday banner",
            quantity=2,
            intent="Party decoration",
            required=True,
            search_hints=["Star Wars", "birthday"],
            constraints=["budget: under $30"],
        )

        assert item.description == "Darth Vader birthday banner"
        assert item.quantity == 2
        assert item.intent == "Party decoration"
        assert item.required is True
        assert len(item.search_hints) == 2
        assert len(item.constraints) == 1

    def test_plan_item_defaults(self) -> None:
        """Test plan item with default values."""
        item = PlanItem(
            description="Test item",
            intent="Test intent",
        )

        assert item.quantity == 1
        assert item.required is True
        assert item.search_hints == []
        assert item.constraints == []

    def test_plan_item_empty_description(self) -> None:
        """Test that empty description is rejected."""
        with pytest.raises(ValidationError):
            PlanItem(
                description="",
                intent="Test intent",
            )

    def test_plan_item_whitespace_description(self) -> None:
        """Test that whitespace-only description is rejected."""
        with pytest.raises(ValidationError):
            PlanItem(
                description="   ",
                intent="Test intent",
            )

    def test_plan_item_invalid_quantity(self) -> None:
        """Test that negative quantity is rejected."""
        with pytest.raises(ValidationError):
            PlanItem(
                description="Test item",
                intent="Test intent",
                quantity=0,
            )


class TestShoppingPlan:
    """Tests for ShoppingPlan model."""

    def test_valid_shopping_plan(self) -> None:
        """Test creating a valid shopping plan."""
        items = [
            PlanItem(
                description="Item 1",
                intent="Intent 1",
            ),
            PlanItem(
                description="Item 2",
                intent="Intent 2",
            ),
        ]

        plan = ShoppingPlan(
            items=items,
            assumptions=["Assumption 1"],
            clarifications_needed=["Question 1"],
        )

        assert len(plan.items) == 2
        assert len(plan.assumptions) == 1
        assert len(plan.clarifications_needed) == 1

    def test_shopping_plan_defaults(self) -> None:
        """Test shopping plan with default values."""
        items = [
            PlanItem(description="Item 1", intent="Intent 1"),
        ]

        plan = ShoppingPlan(items=items)

        assert len(plan.items) == 1
        assert plan.assumptions == []
        assert plan.clarifications_needed == []

    def test_shopping_plan_empty_items(self) -> None:
        """Test that plan with no items is rejected."""
        with pytest.raises(ValidationError):
            ShoppingPlan(items=[])


class TestSearchResult:
    """Tests for SearchResult model."""

    def test_valid_search_result(self) -> None:
        """Test creating a valid search result."""
        result = SearchResult(
            title="Product Title",
            url="https://example.com/product",
            price=29.99,
            source="Amazon",
            relevance_score=0.95,
        )

        assert result.title == "Product Title"
        assert result.url == "https://example.com/product"
        assert result.price == 29.99
        assert result.source == "Amazon"
        assert result.relevance_score == 0.95

    def test_search_result_defaults(self) -> None:
        """Test search result with default values."""
        result = SearchResult(
            title="Product Title",
            url="https://example.com/product",
            source="Amazon",
        )

        assert result.price is None
        assert result.relevance_score == 0.0


class TestAgentResponse:
    """Tests for AgentResponse model."""

    def test_success_response(self) -> None:
        """Test creating a success response."""
        response = AgentResponse(
            success=True,
            data={"key": "value"},
            metadata={"tokens": 100},
        )

        assert response.success is True
        assert response.data == {"key": "value"}
        assert response.error is None
        assert response.metadata == {"tokens": 100}

    def test_error_response(self) -> None:
        """Test creating an error response."""
        response = AgentResponse(
            success=False,
            error="Something went wrong",
        )

        assert response.success is False
        assert response.error == "Something went wrong"
        assert response.data == {}
        assert response.metadata == {}
