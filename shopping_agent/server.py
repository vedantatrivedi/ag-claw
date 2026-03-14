"""
FastAPI server exposing the Browserbase shopping agent APIs.

Usage:
    uvicorn shopping_agent.server:app --reload --port 8000
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from shopping_agent.app.tools.browserbase import BrowserbaseManager

app = FastAPI(title="Shopping Agent API", version="1.0.0")


def get_manager() -> BrowserbaseManager:
    try:
        return BrowserbaseManager()
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---- Request / Response models ---- #

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


# ---- Endpoints ---- #

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


@app.get("/health")
def health():
    return {"status": "ok"}
