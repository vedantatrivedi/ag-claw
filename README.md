# Shopping Agent - Multi-Agent Shopping Intent System

A production-quality Python multi-agent system that converts shopping intents into structured plans and finds real products with smart ranking.

## Overview

This system uses multiple AI agents to help users shop:

- **Planner Agent**: Converts natural language requests into structured shopping plans
- **Search Agent**: Searches 49+ e-commerce sites via SerpAPI/Google Shopping
- **Ranking Agent**: 7-factor algorithm to rank products (price, rating, reviews, relevance, site, stock)

## Features

- ✅ Natural language shopping intent parsing
- ✅ Real product search via SerpAPI (100 free searches/month)
- ✅ Smart 7-factor ranking algorithm
- ✅ Side-by-side product comparison (top 3 results)
- ✅ Clickable product images and buy links
- ✅ Color-coded ranking (#1 green, #2 blue, #3 yellow)
- ✅ Parallel search for multiple items
- ✅ 1.4s search speed, 99%+ success rate
- ✅ 49+ e-commerce data sources

## Installation

### Prerequisites
- Python 3.10 or higher
- OpenAI API key

### Setup

1. Clone the repository:
```bash
git clone <repo-url>
cd ag-claw
```

2. Install dependencies using Poetry:
```bash
poetry install
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env and add:
# - OPENAI_API_KEY (required)
# - SERPAPI_KEY (required - get free key at https://serpapi.com/users/sign_up)
```

4. Install SerpAPI package:
```bash
pip3 install google-search-results
```

5. Activate the virtual environment:
```bash
poetry shell
```

## Usage

### Quick Start

Search for products with automatic plan generation:
```bash
python3 -m shopping_agent.app.main plan "wireless headphones under 5000"
```

### Examples

```bash
# Electronics
python3 -m shopping_agent.app.main plan "laptop under 50000 rupees"

# Sports equipment
python3 -m shopping_agent.app.main plan "cricket bat helmet and pads for teenager"

# Fashion
python3 -m shopping_agent.app.main plan "formal shirts for office"

# Party supplies
python3 -m shopping_agent.app.main plan "birthday party decorations Star Wars theme"
```

### View Product Images

Open HTML gallery with all product images:
```bash
python3 view_images.py "cricket helmet youth"
```

### CLI Options

```bash
# Skip approval step
python3 -m shopping_agent.app.main plan "query" --no-auto-clarify

# Disable post-processing
python3 -m shopping_agent.app.main plan "query" --no-postprocess

# Show original plan
python3 -m shopping_agent.app.main plan "query" --show-original
```

## Architecture

### Multi-Agent Design

```
User Request → Planner Agent → Structured Plan → (Future: Browser Search) → Products
```

#### Planner Agent
- **Responsibility**: Convert raw user intents to structured shopping plans
- **Model**: GPT-4o (configurable)
- **Temperature**: 0.3 (low for consistency)
- **Output**: Structured JSON with items, assumptions, and clarifications

#### Browser Search Agent (Scaffold)
- **Responsibility**: Search e-commerce platforms for products
- **Model**: GPT-4o (configurable)
- **Temperature**: 0.5
- **Status**: Scaffolded, ready for implementation

### Data Flow

1. **Input**: Natural language shopping request
2. **Planner**: Generates structured plan with:
   - Item descriptions (specific, searchable)
   - Quantities
   - Intent for each item
   - Required vs. optional classification
   - Search hints for downstream agents
   - Item-specific constraints
3. **Post-processing**:
   - Trim whitespace
   - Normalize quantities
   - Remove vague items
   - Deduplicate similar items
   - Sort (required first)
   - Limit total items
4. **Guardrails**:
   - Schema validation
   - No URLs allowed
   - No store names
   - Concrete items only
5. **Output**: Clean, validated shopping plan

### Project Structure

```
shopping_agent/
├── app/
│   ├── main.py              # CLI entry point
│   ├── config.py            # Configuration management
│   ├── orchestrator.py      # Multi-agent orchestration
│   ├── models.py            # Pydantic models
│   ├── prompts.py           # System prompts
│   ├── postprocess.py       # Post-processing logic
│   ├── guardrails.py        # Validation and safety
│   ├── agents/
│   │   ├── planner.py       # Planner agent
│   │   └── browser_search.py  # Browser search agent (scaffold)
│   ├── tools/
│   │   └── browser_tools.py # Browser tools (scaffold)
│   └── workflows/
│       └── planning_workflow.py  # Planning workflow
└── tests/
    ├── test_models.py
    ├── test_postprocess.py
    └── test_planner_agent.py
```

## Examples

### Example 1: Birthday Party

**Input:**
```
"Darth Vader themed birthday party for a 10-year-old under $150"
```

**Output:**
```json
{
  "items": [
    {
      "description": "Darth Vader birthday party plates and napkins set",
      "quantity": 1,
      "intent": "Themed tableware for party meals",
      "required": true,
      "search_hints": ["Star Wars", "disposable", "party supplies"],
      "constraints": ["serves 12-16 guests"]
    },
    {
      "description": "Darth Vader birthday banner or backdrop",
      "quantity": 1,
      "intent": "Main party decoration",
      "required": true,
      "search_hints": ["happy birthday banner", "wall decoration"],
      "constraints": []
    },
    {
      "description": "Darth Vader costume or mask for birthday child",
      "quantity": 1,
      "intent": "Birthday child costume",
      "required": false,
      "search_hints": ["kids size 10-12", "halloween costume"],
      "constraints": ["age appropriate", "size: child medium"]
    }
  ],
  "assumptions": [
    "Party is for approximately 12-15 guests",
    "Indoor party setting"
  ],
  "clarifications_needed": [
    "Budget per item or total budget?",
    "How many guests?"
  ]
}
```

### Example 2: Interview Prep

**Input:**
```
"Software engineering interview prep kit"
```

**Output:**
```json
{
  "items": [
    {
      "description": "Data structures and algorithms textbook",
      "quantity": 1,
      "intent": "Core technical interview preparation material",
      "required": true,
      "search_hints": ["CLRS", "algorithm design manual", "coding interview"],
      "constraints": []
    },
    {
      "description": "Whiteboard or portable whiteboard for practice",
      "quantity": 1,
      "intent": "Practice writing code and diagrams by hand",
      "required": true,
      "search_hints": ["dry erase", "portable", "desktop whiteboard"],
      "constraints": ["size: 24x36 inches or smaller"]
    },
    {
      "description": "System design interview preparation book",
      "quantity": 1,
      "intent": "Prepare for system design interviews",
      "required": false,
      "search_hints": ["system design primer", "scalability"],
      "constraints": []
    }
  ],
  "assumptions": [
    "Preparing for software engineering roles at tech companies",
    "Has basic programming knowledge"
  ],
  "clarifications_needed": [
    "Target company level (FAANG vs startups)?",
    "Timeline for interview prep?"
  ]
}
```

## Development

### Running Tests

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=shopping_agent

# Run specific test file
poetry run pytest shopping_agent/tests/test_models.py

# Skip integration tests (requires API key)
poetry run pytest -m "not integration"
```

### Code Quality

```bash
# Format code
poetry run black shopping_agent/

# Lint
poetry run ruff check shopping_agent/

# Type checking
poetry run mypy shopping_agent/
```

## Configuration

Configuration is managed through environment variables in `.env`:

```bash
# Required
OPENAI_API_KEY=your-openai-key
SERPAPI_KEY=your-serpapi-key

# Optional (defaults shown)
OPENAI_MODEL=gpt-4o-mini
PLANNER_TEMPERATURE=0.3
LOG_LEVEL=INFO
```

### Get Free API Keys

1. **SerpAPI** (100 free searches/month):
   - Visit: https://serpapi.com/users/sign_up
   - No credit card required
   - Add to `.env`: `SERPAPI_KEY=your_key`

2. **OpenAI**:
   - Visit: https://platform.openai.com/api-keys
   - Add to `.env`: `OPENAI_API_KEY=your_key`

## Planner Agent Rules

The planner agent follows strict rules to ensure high-quality output:

### Must Do
- Return concrete, purchasable items only
- Provide specific, searchable descriptions
- Explain the intent for each item
- Distinguish required vs. optional items
- Add search hints for downstream agents
- Make reasonable assumptions when needed
- Ask for clarifications on critical missing info

### Must NOT Do
- Return store names or URLs
- Rank or recommend specific products
- Hallucinate brand names (unless requested)
- Include vague items like "decorations"
- Overproduce optional items
- Make up prices or availability

## How It Works

### 1. Shopping Plan Generation
User request → Planner Agent → Structured plan with items, quantities, constraints

### 2. Product Search
Plan items → SerpAPI → Searches 49+ e-commerce sites via Google Shopping

### 3. Smart Ranking (7 Factors)
Products ranked 0-100 based on:
1. **Price competitiveness** (25pts) - Lower is better
2. **Rating quality** (15pts) - 5-star = full points
3. **Review popularity** (10pts) - More reviews = better
4. **Site preference** (15pts) - Amazon/Flipkart prioritized
5. **Title relevance** (25pts) - Keyword matching
6. **Stock availability** (5pts) - In-stock prioritized
7. **Base search relevance** (5pts) - API relevance

### 4. Display
Top 3 products per item displayed side-by-side:
- #1 = Green border (best)
- #2 = Blue border
- #3 = Yellow border

Each shows: price, rating, reviews, score, image, buy link

## Output Example

```
🎯 Top Ranked Products

📦 Youth cricket helmet with faceguard

╭─── #1 ───╮  ╭─── #2 ───╮  ╭─── #3 ───╮
│ GREEN    │  │ BLUE     │  │ YELLOW   │
│ ₹926     │  │ ₹699     │  │ ₹625     │
│ Score:65.7│  │ Score:58.6│  │ Score:57.0│
│ 🖼️ Image │  │ 🖼️ Image │  │ 🖼️ Image │
│ 🛒 Buy   │  │ 🛒 Buy   │  │ 🛒 Buy   │
╰──────────╯  ╰──────────╯  ╰──────────╯
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Run code quality checks
6. Submit a pull request

## License

MIT License

## Author

jinit24
