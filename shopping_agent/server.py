"""
FastAPI server exposing the shopping agent APIs (Browserbase + SerpAPI).

Usage:
    uvicorn shopping_agent.server:app --reload --port 8000
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

try:
    from shopping_agent.app.tools.browserbase import BrowserbaseManager
    BROWSERBASE_AVAILABLE = True
except ImportError:
    BROWSERBASE_AVAILABLE = False
    BrowserbaseManager = None

from shopping_agent.app.orchestrator import ShoppingOrchestrator
from shopping_agent.app.agents.serpapi_search import SerpAPISearchAgent
from shopping_agent.app.models import PlanItem

app = FastAPI(title="Shopping Agent API", version="1.0.0")


def get_manager():
    if not BROWSERBASE_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Browserbase endpoints not available. Install dependencies: pip install browserbase playwright"
        )
    try:
        return BrowserbaseManager()
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---- Request / Response models ---- #

# SerpAPI endpoints
class PlanRequest(BaseModel):
    request: str = Field(..., min_length=1, description="Natural language shopping request")
    postprocess: bool = Field(default=True, description="Apply post-processing to clean up plan")


class PlanItemResponse(BaseModel):
    description: str
    quantity: int
    intent: str
    required: bool
    search_hints: list[str]
    constraints: list[str]
    search_query: str = ""
    preferred_sites: list[str] = []


class PlanResponse(BaseModel):
    items: list[PlanItemResponse]
    assumptions: list[str]
    clarifications_needed: list[str]
    metadata: dict


class SerpSearchRequest(BaseModel):
    items: list[dict] = Field(..., min_length=1, description="List of plan items to search for")


class SerpProductResult(BaseModel):
    title: str
    url: str
    price: Optional[float] = None
    source: str
    rating: Optional[float] = None
    review_count: Optional[int] = None
    in_stock: Optional[bool] = None
    image_url: Optional[str] = None
    final_score: Optional[float] = None


class SerpSearchResults(BaseModel):
    item_description: str
    total_found: int
    results: list[SerpProductResult]


class SerpSearchResponse(BaseModel):
    count: int
    results: list[SerpSearchResults]


# Guided party flow endpoints
class GuidedPartyQuestionRequest(BaseModel):
    request: str = Field(..., min_length=1, description="Broad party-planning request")


class GuidedPartyQuestionResponse(BaseModel):
    questions: list[str]


class GuidedPartyPreauthRequest(BaseModel):
    request: str = Field(..., min_length=1, description="Original party-planning request")
    preferences_answers: dict[str, str] = Field(
        ...,
        min_length=1,
        description="Collected answers keyed by question",
    )
    budget_inr: float = Field(..., gt=0, description="Approved budget in INR")


class GuidedPartyPreauthResponse(BaseModel):
    request: str
    preferences_answers: dict[str, str]
    budget_inr: float
    preauth: dict


class GuidedPartyCompleteRequest(BaseModel):
    request: str = Field(..., min_length=1, description="Original party-planning request")
    preferences_answers: dict[str, str] = Field(
        ...,
        min_length=1,
        description="Collected answers keyed by question",
    )
    budget_inr: float = Field(..., gt=0, description="Approved budget in INR")
    preauth: dict = Field(..., description="Preauth response from the creation step")
    postprocess: bool = Field(default=True, description="Apply post-processing to clean up plan")


class GuidedPartyCompleteResponse(BaseModel):
    preferences_asked: list[str]
    preferences_answers: dict[str, str]
    budget_inr: float
    preauth: dict
    plan: dict
    planner_metadata: dict
    curation_mode: str
    listing_results: list[dict]
    selected_product_urls: list[str]


class GuidedPartyCartRequest(BaseModel):
    listing_results: list[dict] = Field(..., min_length=1, description="Curated listing results from the completion step")
    selected_urls: list[str] = Field(default_factory=list, description="Explicit curated URLs to add to cart")


class GuidedPartyCartResponse(BaseModel):
    selected_product_urls: list[str]
    cart: dict


# Browserbase endpoints
class StartLoginRequest(BaseModel):
    timeout: int = Field(default=900, description="Session timeout in seconds")


class StartLoginResponse(BaseModel):
    session_id: str
    cdp_url: str
    debug_url: str


class SaveCookiesResponse(BaseModel):
    amazon_cookies: int
    total_cookies: int
    local_storage_keys: int


class SearchRequest(BaseModel):
    query: str
    max_results: int = Field(default=8, ge=1, le=20)


class ProductResult(BaseModel):
    title: str = ""
    price: str = ""
    rating: str = ""
    reviews: str = ""
    asin: str = ""
    url: str = ""
    image: str = ""


class SearchResponse(BaseModel):
    query: str
    count: int
    results: list[ProductResult]


class AddToCartRequest(BaseModel):
    urls: list[str] = Field(..., min_length=1, description="Product URLs or ASINs")


class CartItemStatus(BaseModel):
    url: str
    title: str = ""
    image: str = ""
    success: bool
    message: str = ""


class AddToCartResponse(BaseModel):
    total: int
    added: int
    failed: int
    items: list[CartItemStatus]
    cart_screenshot: str = Field(default="", description="Base64 PNG screenshot of the final cart page")


# ---- Flipkart models ---- #

class SaveFlipkartCookiesResponse(BaseModel):
    flipkart_cookies: int
    total_cookies: int
    local_storage_keys: int


class FlipkartProductResult(BaseModel):
    title: str = ""
    price: str = ""
    rating: str = ""
    reviews: str = ""
    pid: str = ""
    url: str = ""
    image: str = ""


class FlipkartSearchResponse(BaseModel):
    query: str
    count: int
    results: list[FlipkartProductResult]


# ---- Amazon Endpoints ---- #

# SerpAPI endpoints
@app.post("/plan", response_model=PlanResponse)
def create_plan(req: PlanRequest):
    """Generate a structured shopping plan from a natural language request."""
    orchestrator = ShoppingOrchestrator()
    result = orchestrator.create_shopping_plan(
        user_request=req.request,
        apply_postprocessing=req.postprocess
    )

    if not result.get("success", False):
        raise HTTPException(status_code=500, detail=result.get("error", "Plan generation failed"))

    plan_data = result["plan"]
    return PlanResponse(
        items=[PlanItemResponse(**item) for item in plan_data["items"]],
        assumptions=plan_data.get("assumptions", []),
        clarifications_needed=plan_data.get("clarifications_needed", []),
        metadata=result.get("metadata", {})
    )


@app.post("/serp/search", response_model=SerpSearchResponse)
def search_serp(req: SerpSearchRequest):
    """Search for products using SerpAPI across 49+ e-commerce sites. Returns top 3 ranked products per item."""
    agent = SerpAPISearchAgent()

    # Convert dict items to PlanItem objects
    plan_items = []
    for item_dict in req.items:
        try:
            plan_items.append(PlanItem(**item_dict))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid plan item: {str(e)}")

    # Search all items
    search_results = agent.search_multiple(plan_items)

    # Format response
    formatted_results = []
    for search_result in search_results:
        formatted_results.append(SerpSearchResults(
            item_description=search_result.task.plan_item.description,
            total_found=search_result.total_found,
            results=[
                SerpProductResult(
                    title=p.title,
                    url=p.url,
                    price=p.price,
                    source=p.source,
                    rating=p.rating,
                    review_count=p.review_count,
                    in_stock=p.in_stock,
                    image_url=p.image_url,
                    final_score=p.final_score
                )
                for p in search_result.results
            ]
        ))

    return SerpSearchResponse(
        count=len(formatted_results),
        results=formatted_results
    )


@app.post("/guided-party/questions", response_model=GuidedPartyQuestionResponse)
def guided_party_questions(req: GuidedPartyQuestionRequest):
    """Generate guided party preference questions from an initial broad request."""
    orchestrator = ShoppingOrchestrator()
    questions = orchestrator.generate_guided_party_questions(req.request)
    return GuidedPartyQuestionResponse(questions=questions)


@app.post("/guided-party/preauth", response_model=GuidedPartyPreauthResponse)
def guided_party_preauth(req: GuidedPartyPreauthRequest):
    """Create a Pine Labs preauth and return the redirect URL for manual authorization."""
    orchestrator = ShoppingOrchestrator()
    result = orchestrator.create_guided_party_preauth(
        preferences_answers=req.preferences_answers,
        budget_inr=req.budget_inr,
    )

    if not result.get("success", False):
        raise HTTPException(status_code=500, detail=result.get("error", "Preauth creation failed"))

    return GuidedPartyPreauthResponse(
        request=req.request,
        preferences_answers=req.preferences_answers,
        budget_inr=req.budget_inr,
        preauth=result["preauth"],
    )


@app.post("/guided-party/complete", response_model=GuidedPartyCompleteResponse)
def guided_party_complete(req: GuidedPartyCompleteRequest):
    """Finish the guided party flow after the user authorizes the preauth."""
    orchestrator = ShoppingOrchestrator()
    result = orchestrator.complete_guided_party_after_authorization(
        user_request=req.request,
        preferences_answers=req.preferences_answers,
        budget_inr=req.budget_inr,
        preauth=req.preauth,
        apply_postprocessing=req.postprocess,
    )

    if not result.get("success", False):
        raise HTTPException(status_code=500, detail=result.get("error", "Guided party completion failed"))

    return GuidedPartyCompleteResponse(
        preferences_asked=result.get("preferences_asked", []),
        preferences_answers=result.get("preferences_answers", {}),
        budget_inr=result.get("budget_inr", req.budget_inr),
        preauth=result.get("preauth", {}),
        plan=result.get("plan", {}),
        planner_metadata=result.get("planner_metadata", {}),
        curation_mode=result.get("curation_mode", "placeholder"),
        listing_results=result.get("listing_results", []),
        selected_product_urls=result.get("selected_product_urls", []),
    )


@app.post("/guided-party/cart", response_model=GuidedPartyCartResponse)
def guided_party_cart(req: GuidedPartyCartRequest):
    """Add selected or top-ranked curated guided-party products to Amazon cart."""
    orchestrator = ShoppingOrchestrator()
    result = orchestrator.add_guided_party_items_to_cart(
        listing_results=req.listing_results,
        selected_urls=req.selected_urls or None,
    )

    if not result.get("success", False):
        raise HTTPException(status_code=500, detail=result.get("error", "Cart add failed"))

    return GuidedPartyCartResponse(
        selected_product_urls=result.get("selected_product_urls", []),
        cart=result.get("cart", {}),
    )


# Browserbase endpoints
@app.post("/login/start", response_model=StartLoginResponse)
def start_login(req: StartLoginRequest = StartLoginRequest()):
    """Start a browser session for manual Amazon login. Returns a debug URL to open in your browser."""
    mgr = get_manager()
    data = mgr.start_login_session(timeout=req.timeout)
    return StartLoginResponse(**data)


@app.post("/login/save-cookies", response_model=SaveCookiesResponse)
def save_cookies():
    """Extract cookies from the running login session and save them locally."""
    mgr = get_manager()
    try:
        summary = mgr.save_cookies()
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return SaveCookiesResponse(**summary)


@app.post("/search", response_model=SearchResponse)
def search_amazon(req: SearchRequest):
    """Search Amazon.in and return top non-sponsored results."""
    mgr = get_manager()
    results = mgr.search_amazon(req.query, req.max_results)
    return SearchResponse(
        query=req.query,
        count=len(results),
        results=[ProductResult(**r) for r in results],
    )


@app.post("/cart/add", response_model=AddToCartResponse)
def add_to_cart(req: AddToCartRequest):
    """Add products to Amazon cart by URL or ASIN. Returns product images and a cart screenshot."""
    mgr = get_manager()
    result = mgr.add_to_cart(req.urls)
    items = result["items"]
    added = sum(1 for s in items if s["success"])
    return AddToCartResponse(
        total=len(items),
        added=added,
        failed=len(items) - added,
        items=[CartItemStatus(**s) for s in items],
        cart_screenshot=result["cart_screenshot"],
    )


# ---- Flipkart Endpoints ---- #

@app.post("/flipkart/login/start", response_model=StartLoginResponse)
def start_flipkart_login(req: StartLoginRequest = StartLoginRequest()):
    """Start a browser session for manual Flipkart login. Returns a debug URL to open in your browser."""
    mgr = get_manager()
    data = mgr.start_flipkart_login_session(timeout=req.timeout)
    return StartLoginResponse(**data)


@app.post("/flipkart/login/save-cookies", response_model=SaveFlipkartCookiesResponse)
def save_flipkart_cookies():
    """Extract cookies from the running Flipkart login session and save them locally."""
    mgr = get_manager()
    try:
        summary = mgr.save_flipkart_cookies()
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return SaveFlipkartCookiesResponse(**summary)


@app.post("/flipkart/search", response_model=FlipkartSearchResponse)
def search_flipkart(req: SearchRequest):
    """Search Flipkart and return top non-sponsored results."""
    mgr = get_manager()
    results = mgr.search_flipkart(req.query, req.max_results)
    return FlipkartSearchResponse(
        query=req.query,
        count=len(results),
        results=[FlipkartProductResult(**r) for r in results],
    )


@app.post("/flipkart/cart/add", response_model=AddToCartResponse)
def add_to_cart_flipkart(req: AddToCartRequest):
    """Add products to Flipkart cart by URL. Returns product images and a cart screenshot."""
    mgr = get_manager()
    result = mgr.add_to_cart_flipkart(req.urls)
    items = result["items"]
    added = sum(1 for s in items if s["success"])
    return AddToCartResponse(
        total=len(items),
        added=added,
        failed=len(items) - added,
        items=[CartItemStatus(**s) for s in items],
        cart_screenshot=result["cart_screenshot"],
    )


@app.get("/health")
def health():
    return {"status": "ok"}
