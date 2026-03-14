"""
Pydantic models for structured data throughout the shopping agent system.
"""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class PlanItem(BaseModel):
    """A single item in the shopping plan."""

    description: str = Field(
        ...,
        description="Specific, searchable description of the item",
        min_length=3,
    )
    quantity: int = Field(default=1, ge=1, description="Number of items needed")
    intent: str = Field(
        ...,
        description="Why this item belongs in the plan",
        min_length=5,
    )
    required: bool = Field(
        default=True,
        description="Whether this item is essential or optional",
    )
    search_hints: List[str] = Field(
        default_factory=list,
        description="Keywords or hints to help downstream product search",
    )
    constraints: List[str] = Field(
        default_factory=list,
        description="Item-specific constraints (e.g., budget, color, size)",
    )
    search_query: str = Field(
        default="",
        description="Generic search query for this item (works across all sites)",
    )
    preferred_sites: List[str] = Field(
        default_factory=list,
        description="LLM-suggested sites to search based on item category (e.g., ['amazon', 'flipkart'])",
    )

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str) -> str:
        """Ensure description is not just whitespace."""
        v = v.strip()
        if not v:
            raise ValueError("Description cannot be empty or whitespace")
        return v

    @field_validator("intent")
    @classmethod
    def validate_intent(cls, v: str) -> str:
        """Ensure intent is not just whitespace."""
        v = v.strip()
        if not v:
            raise ValueError("Intent cannot be empty or whitespace")
        return v


class ShoppingPlan(BaseModel):
    """Complete shopping plan from the planner agent."""

    items: List[PlanItem] = Field(
        ...,
        description="List of items to search for and potentially purchase",
        min_length=1,
    )
    assumptions: List[str] = Field(
        default_factory=list,
        description="Assumptions made when generating the plan",
    )
    clarifications_needed: List[str] = Field(
        default_factory=list,
        description="Questions that would help refine the search",
    )

    @field_validator("items")
    @classmethod
    def validate_items(cls, v: List[PlanItem]) -> List[PlanItem]:
        """Ensure at least one item exists."""
        if not v:
            raise ValueError("Plan must contain at least one item")
        return v


class PreferenceQuestions(BaseModel):
    """Structured question set for guided party planning."""

    questions: List[str] = Field(
        ...,
        min_length=1,
        max_length=6,
        description="Preference questions to ask before budget collection",
    )

    @field_validator("questions")
    @classmethod
    def validate_questions(cls, v: List[str]) -> List[str]:
        cleaned = [question.strip() for question in v if question and question.strip()]
        if not cleaned:
            raise ValueError("At least one preference question is required")
        return cleaned[:6]


class SearchResult(BaseModel):
    """A single product search result."""

    title: str = Field(..., description="Product title")
    url: str = Field(..., description="Product URL")
    price: Optional[float] = Field(None, description="Product price if available")
    source: str = Field(..., description="Source website or marketplace")
    relevance_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Relevance score from search",
    )
    rating: Optional[float] = Field(
        None,
        ge=0.0,
        le=5.0,
        description="Product rating (0-5 stars)",
    )
    review_count: Optional[int] = Field(
        None,
        ge=0,
        description="Number of reviews",
    )
    in_stock: Optional[bool] = Field(
        None,
        description="Stock availability",
    )
    image_url: Optional[str] = Field(
        None,
        description="Product thumbnail image URL",
    )
    final_score: Optional[float] = Field(
        None,
        description="Computed ranking score (0-100)",
    )


class SearchTask(BaseModel):
    """A search task derived from a plan item (scaffold for browser agent)."""

    plan_item: PlanItem = Field(..., description="The plan item to search for")
    search_query: str = Field(..., description="Optimized search query")
    filters: dict = Field(
        default_factory=dict,
        description="Search filters (price range, category, etc.)",
    )


class SearchResults(BaseModel):
    """Collection of search results for a search task."""

    task: SearchTask = Field(..., description="The search task")
    results: List[SearchResult] = Field(
        default_factory=list,
        description="List of search results",
    )
    total_found: int = Field(default=0, description="Total results found")


class AgentResponse(BaseModel):
    """Standard response format for agent outputs."""

    success: bool = Field(..., description="Whether the agent succeeded")
    data: dict = Field(default_factory=dict, description="Response data")
    error: Optional[str] = Field(None, description="Error message if failed")
    metadata: dict = Field(
        default_factory=dict,
        description="Additional metadata (timing, tokens used, etc.)",
    )


class GuidedPartyPlanResult(BaseModel):
    """Final result for the guided party-planning flow."""

    preferences_asked: List[str] = Field(default_factory=list)
    preferences_answers: Dict[str, str] = Field(default_factory=dict)
    budget_inr: float = Field(..., ge=0.0)
    preauth: dict = Field(default_factory=dict)
    plan: dict = Field(default_factory=dict)
    planner_metadata: dict = Field(default_factory=dict)
    listing_results: List[SearchResults] = Field(default_factory=list)
