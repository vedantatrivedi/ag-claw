"""
Tests for the planner agent.

Note: These tests require a valid OPENAI_API_KEY environment variable.
They can be run with pytest or skipped if the API key is not available.
"""

import os
import pytest

from shopping_agent.app.agents.planner import PlannerAgent
from shopping_agent.app.models import ShoppingPlan


# Skip all tests in this file if OPENAI_API_KEY is not set
pytestmark = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set",
)


class TestPlannerAgent:
    """Tests for PlannerAgent."""

    @pytest.fixture
    def planner(self) -> PlannerAgent:
        """Create a planner agent for testing."""
        return PlannerAgent()

    def test_planner_initialization(self, planner: PlannerAgent) -> None:
        """Test that planner initializes correctly."""
        assert planner.name == "planner"
        assert planner.model is not None
        assert planner.temperature >= 0.0
        assert planner.client is not None

    def test_plan_simple_request(self, planner: PlannerAgent) -> None:
        """Test planning with a simple request."""
        request = "Buy a notebook and pen for school"

        response = planner.plan(request, apply_postprocessing=False)

        assert response.success is True
        assert "plan" in response.data
        assert len(response.data["plan"]["items"]) >= 1

        # Validate the plan structure
        plan_dict = response.data["plan"]
        plan = ShoppingPlan(**plan_dict)
        assert len(plan.items) >= 1

    def test_plan_party_request(self, planner: PlannerAgent) -> None:
        """Test planning for a birthday party."""
        request = "Darth Vader themed birthday party for a 10-year-old"

        response = planner.plan(request, apply_postprocessing=True)

        assert response.success is True
        plan_dict = response.data["plan"]
        plan = ShoppingPlan(**plan_dict)

        # Should have multiple party-related items
        assert len(plan.items) >= 2

        # Items should be related to party/Star Wars theme
        descriptions = [item.description.lower() for item in plan.items]
        assert any("vader" in desc or "star wars" in desc for desc in descriptions)

    def test_plan_interview_prep_request(self, planner: PlannerAgent) -> None:
        """Test planning for interview preparation."""
        request = "Software engineering interview prep kit"

        response = planner.plan(request, apply_postprocessing=True)

        assert response.success is True
        plan_dict = response.data["plan"]
        plan = ShoppingPlan(**plan_dict)

        # Should have multiple prep-related items
        assert len(plan.items) >= 1

        # Items should be related to learning/preparation
        descriptions = [item.description.lower() for item in plan.items]
        assert any(
            keyword in " ".join(descriptions)
            for keyword in ["book", "whiteboard", "algorithm", "system design"]
        )

    def test_plan_with_postprocessing(self, planner: PlannerAgent) -> None:
        """Test that post-processing is applied correctly."""
        request = "I need party supplies"

        response = planner.plan(request, apply_postprocessing=True)

        assert response.success is True
        assert response.metadata["postprocessing_applied"] is True

        # Original plan should be included
        assert response.data.get("original_plan") is not None

    def test_plan_without_postprocessing(self, planner: PlannerAgent) -> None:
        """Test that post-processing can be disabled."""
        request = "I need party supplies"

        response = planner.plan(request, apply_postprocessing=False)

        assert response.success is True
        assert response.metadata["postprocessing_applied"] is False

        # Original plan should not be included
        assert response.data.get("original_plan") is None

    def test_plan_includes_metadata(self, planner: PlannerAgent) -> None:
        """Test that response includes metadata."""
        request = "Buy groceries"

        response = planner.plan(request)

        assert "model" in response.metadata
        assert "temperature" in response.metadata
        assert "tokens_used" in response.metadata

    def test_get_instructions(self, planner: PlannerAgent) -> None:
        """Test getting agent instructions."""
        instructions = planner.get_instructions()

        assert isinstance(instructions, str)
        assert len(instructions) > 100
        assert "planner" in instructions.lower() or "plan" in instructions.lower()
