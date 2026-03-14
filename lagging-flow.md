# AG-CLAW Slow Flow Analysis

## Flow 1: After Pre-Authorization → Shopping Plan + Cart Products

**API Endpoint**: `POST /guided-party/complete`

This is the heaviest endpoint. After the user authorizes the preauth, `complete_after_authorization()` runs these steps **sequentially**:

| Step | What happens | Integration | Why it's slow |
|------|-------------|-------------|---------------|
| 1 | **Poll preauth status** | Pine Labs/Plural API (`get_preauth_status`) | Polls repeatedly until `AUTHORIZED` status — configurable timeout & interval |
| 2 | **Generate shopping plan** | OpenAI API (planner agent) | LLM call to convert preferences → structured `ShoppingPlan` |
| 3 | **Post-process plan** | Local (deterministic) | Fast — 6-step cleanup, no external calls |
| 4 | **Guardrails check** | Local (deterministic) | Fast — 5 validation checks |
| 5 | **Curate listings** (`get_curated_listing_results`) | **Browserbase** (browser automation) or **SerpAPI** | For each plan item, spins up a browser session to search Amazon — parallel via ThreadPoolExecutor (max 5 workers), but each browser session is slow |
| 6 | **Select top product URLs** | Local | Fast — picks best URL per item |

**Likely bottlenecks**:
- **Step 1**: Preauth polling — depends on how fast Pine Labs confirms authorization
- **Step 2**: OpenAI LLM call — latency varies (1-10s+)
- **Step 5**: Browserbase curation — this is almost certainly the **biggest bottleneck**. It launches real browser sessions per plan item to search products on Amazon

**Key files to investigate**:
- `shopping_agent/app/workflows/guided_party_workflow.py` — `complete_after_authorization()`
- `shopping_agent/app/guided_party.py` — `get_curated_listing_results()`
- `shopping_agent/app/tools/browserbase.py` — browser session management
- `shopping_agent/app/agents/planner.py` — LLM plan generation
- `shopping_agent/app/tools/pinelabs.py` — `get_preauth_status()` polling

---

## Flow 2: After Selecting Final Cart → Add to Cart

**API Endpoint**: `POST /guided-party/cart`

After the user confirms their product selection, `add_to_cart()` runs:

| Step | What happens | Integration | Why it's slow |
|------|-------------|-------------|---------------|
| 1 | **Select product URLs** | Local | Fast |
| 2 | **Add URLs to cart** (`add_urls_to_browserbase_cart`) | **Browserbase** (browser automation) | Launches a browser, navigates to each Amazon URL, and clicks "Add to Cart" — sequential browser interactions |

**Likely bottleneck**:
- **Step 2**: Browserbase cart addition — real browser automation on Amazon for each product URL (navigate → interact → verify). This is inherently slow.

**Key files to investigate**:
- `shopping_agent/app/workflows/guided_party_workflow.py` — `add_to_cart()`
- `shopping_agent/app/guided_party.py` — `add_urls_to_browserbase_cart()`
- `shopping_agent/app/tools/browserbase.py` — actual browser add-to-cart logic

---

## Summary of External Integrations Causing Latency

| Integration | Used In | Latency Impact |
|------------|---------|----------------|
| **Browserbase** (browser automation) | Product curation search + Cart add | **Highest** — real browser sessions are slow |
| **OpenAI API** (LLM) | Plan generation | **Medium** — LLM inference latency |
| **Pine Labs/Plural API** | Preauth status polling | **Medium** — depends on authorization speed |
| **SerpAPI** (if used as curation fallback) | Product search | **Medium** — external API call per item |

The **Browserbase integration is the primary bottleneck** in both flows.
