# UI Implementation Plan

## Quick Option: Streamlit (Fastest - 2-3 hours)

### Why Streamlit?
- Zero frontend code needed
- Built-in components for forms, tables, progress
- Hot reload during development
- Deploy to Streamlit Cloud (free)

### Implementation
```python
# streamlit_app.py
import streamlit as st
from shopping_agent.app.orchestrator import ShoppingOrchestrator
from shopping_agent.app.agents.browser_search import BrowserSearchAgent

st.title("🛒 AI Shopping Agent")

# Input
request = st.text_area("What are you shopping for?",
    placeholder="e.g., cricket bat for under 16 in hot weather")

if st.button("Generate Plan"):
    with st.spinner("Planning..."):
        orchestrator = ShoppingOrchestrator()
        result = orchestrator.create_shopping_plan(request)

    # Display plan
    for item in result['plan']['items']:
        with st.expander(f"📦 {item['description']}"):
            st.write(f"**Quantity:** {item['quantity']}")
            st.write(f"**Intent:** {item['intent']}")

    # Approval
    if st.button("Search Products"):
        with st.spinner("Searching across sites..."):
            browser = BrowserSearchAgent()
            results = browser.search_multiple(plan_items)

        # Display results
        for search_result in results:
            st.subheader(search_result.task.plan_item.description)
            df = pd.DataFrame([
                {
                    "Site": r.source,
                    "Product": r.title,
                    "Price": f"₹{r.price:.0f}" if r.price else "N/A",
                    "Rating": f"⭐{r.rating:.1f}" if r.rating else "N/A",
                    "Reviews": r.review_count or "N/A",
                    "Link": r.url
                }
                for r in search_result.results
            ])
            st.dataframe(df)
```

### Install & Run
```bash
pip install streamlit
streamlit run streamlit_app.py
```

---

## Full Option: FastAPI + React (4-5 days)

### Architecture
```
Backend (FastAPI)          Frontend (React)
├── /api/plan              ├── PlanInput.tsx
├── /api/search            ├── PlanDisplay.tsx
├── /api/refine            └── ProductResults.tsx
└── WebSocket for progress
```

### Why This?
- Professional look/feel
- Fine-grained control
- Mobile responsive
- API reusable for future integrations

### Tech Stack
- Backend: FastAPI + Pydantic (reuse existing models)
- Frontend: Next.js + Tailwind CSS
- State: React Query for caching
- Deploy: Vercel (frontend) + Railway (backend)

---

## Recommendation

**Start with Streamlit** - Get feedback on UX before investing in custom frontend. Can always rebuild in React later if needed.

**Timeline:**
- Streamlit MVP: 2-3 hours
- Polish + deployment: +2 hours
- Full React app: 4-5 days

**Cost:**
- Streamlit Cloud: Free (public apps)
- Vercel + Railway: ~$10/month (if going React route)
