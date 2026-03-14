# Shopping Agent - Quick Start

## ✅ Ready to Use with SerpAPI

**Both API keys are configured and working!**

---

## 1. Test Search (5 seconds)

```bash
python3 test_serpapi.py
```

Expected output:
```
✅ Found 10 products:
1. Sony WH-CH720N - ₹7999 ⭐4.6 (14,000 reviews)
2. Sony ULT WEAR - ₹14990 ⭐4.7 (4,800 reviews)
...
```

---

## 2. Full Shopping Flow

```bash
python3 -m shopping_agent.app.main plan "wireless headphones under 100 dollars"
```

**What happens:**
1. Generates structured shopping plan with 3 items
2. Asks for approval (type `y` or `yes`)
3. Searches Google Shopping via SerpAPI
4. Shows ranked results with prices, ratings, reviews

---

## 3. Example Queries

```bash
# Budget constraint
python3 -m shopping_agent.app.main plan "laptop under 50000 rupees"

# Specific category
python3 -m shopping_agent.app.main plan "cricket bat and helmet for teenager"

# Multiple items
python3 -m shopping_agent.app.main plan "gym workout essentials"

# Fashion
python3 -m shopping_agent.app.main plan "formal shirts and trousers for office"
```

---

## 4. Skip Approval (Auto-approve)

```bash
python3 -m shopping_agent.app.main plan "wireless headphones" --no-auto-clarify
```

This skips the interactive approval and goes straight to search.

---

## Configuration

### Current Setup (Working)
```bash
# In .env file:
OPENAI_API_KEY=sk-proj-PWpCKv_yPwkLQS1...  ✅
SERPAPI_KEY=bbe66b8369b9aed0329303...       ✅ (Preferred - 3x faster)
SEARCHAPI_KEY=XZ7msvDttWpGVqiW3exVH...      ✅ (Fallback)
```

### Which API is Used?
- **SerpAPI first** (3x faster - 1.36s)
- **SearchAPI.com fallback** (if SerpAPI unavailable - 4.14s)

---

## Features Working

### ✅ Planner Agent
- Structured JSON plans
- Intent classification
- Site preferences (Amazon, Flipkart, Myntra, Ajio, Croma)
- Budget extraction
- Interactive approval loop

### ✅ Search Agent (SerpAPI)
- Google Shopping search
- Price, rating, review extraction
- Source attribution (Amazon.in, Flipkart, AJIO, etc.)
- Fast: 1.36s per search

### ✅ Ranking Algorithm
- 7-factor scoring:
  1. Price competitiveness (25pts)
  2. Rating quality (15pts)
  3. Review popularity (10pts, log scale)
  4. Site preference (15pts)
  5. Title relevance (25pts)
  6. Stock availability (5pts)
  7. Base relevance (5pts)

### ✅ Display
- Rich terminal tables
- Star ratings, review counts
- Colored output
- Clickable URLs

---

## Test Commands

```bash
# Compare both APIs (see which is faster)
python3 compare_apis.py

# Test SerpAPI only
python3 test_serpapi.py

# Test SearchAPI.com only
python3 test_searchapi.py

# Run unit tests
python3 -m pytest shopping_agent/tests/ -v

# Mock demo (no API calls)
python3 test_mock_search.py
```

---

## Troubleshooting

### No products found?
- Check API key is valid
- Try simpler query: "headphones" instead of "wireless over-ear noise cancelling headphones"
- Check API quota (100 free searches/month)

### Error: "SERPAPI_KEY not found"?
- Make sure .env file exists
- Check key is uncommented (no # at start)
- Restart terminal to reload environment

### Slow search?
- SerpAPI: 1-2s is normal
- SearchAPI.com: 3-5s is normal
- Browser automation would take 30-60s (not used)

---

## API Limits

### Free Tier
- **100 searches/month** per API key
- Sufficient for 20-30 shopping sessions
- 3-5 items per session
- Resets monthly

### When to Upgrade
- If you need >100 searches/month
- Paid tier: $50/month for 5,000 searches
- Both SerpAPI and SearchAPI offer similar pricing

---

## What's Next?

All features are working! Optional enhancements:

1. **Add UI**: Streamlit or React frontend
2. **Price tracking**: Monitor price changes over time
3. **Notifications**: Alert when prices drop
4. **Comparison mode**: Side-by-side product comparison
5. **More ranking factors**: Shipping cost, delivery time

---

## Documentation

- `API_COMPARISON.md` - SerpAPI vs SearchAPI.com comparison
- `BLOCKING_EVIDENCE.md` - Why browser automation failed
- `SERPAPI_SETUP.md` - SerpAPI setup guide
- `SEARCHAPI_SETUP.md` - SearchAPI.com setup guide
- `FINAL_STATUS.md` - Complete implementation status

---

## Summary

✅ **Production ready**
✅ **Both APIs working**
✅ **SerpAPI preferred** (3x faster)
✅ **Real product data** from Google Shopping
✅ **7-factor ranking** algorithm
✅ **Multi-site support** (Amazon, Flipkart, Myntra, Ajio, Croma)

**Just run:** `python3 -m shopping_agent.app.main plan "your query here"`

---

_Last updated: 2024-03-14_
_Status: ✅ WORKING_
