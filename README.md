# Shopping Agent - Multi-Agent Shopping Intent System

A production-quality Python multi-agent system built with the OpenAI Agents SDK for converting shopping intents into structured, actionable plans.

## Overview

This system uses multiple AI agents to help users plan shopping tasks:

- **Planner Agent** (v1 - Active): Converts natural language shopping requests into structured, searchable item plans
- **Browser Search Agent** (Scaffolded): Ready to search e-commerce platforms for products (next phase)

## Features

### Current (v1)
- ✅ Natural language shopping intent parsing
- ✅ Structured JSON output with strict schema validation
- ✅ Deterministic post-processing (deduplication, sorting, cleanup)
- ✅ Guardrails for output quality (no URLs, no store names, concrete items only)
- ✅ Rich CLI interface with examples
- ✅ Production-ready architecture
- ✅ Comprehensive test suite

### Next Phase
- 🔄 Web search integration (Amazon, eBay, Walmart)
- 🔄 Product ranking and comparison
- 🔄 Price tracking
- 🔄 Agent handoffs with context passing

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
# Edit .env and add your OPENAI_API_KEY
```

4. Activate the virtual environment:
```bash
poetry shell
```

## Usage

### CLI Commands

#### Generate a shopping plan:
```bash
shopping-agent plan "Darth Vader themed birthday party for a 10-year-old"
```

#### Run predefined examples:
```bash
# Birthday party example
shopping-agent example party

# Interview prep example
shopping-agent example interview

# Gift basket example
shopping-agent example gift

# Desk setup example
shopping-agent example desk
```

#### Show system information:
```bash
shopping-agent info
```

#### Show architecture details:
```bash
shopping-agent architecture
```

### CLI Options

```bash
# Disable post-processing
shopping-agent plan "request" --no-postprocess

# Show original plan before post-processing
shopping-agent plan "request" --show-original

# Show guardrail violations
shopping-agent plan "request" --show-violations
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
OPENAI_API_KEY=your-api-key-here

# Optional (defaults shown)
OPENAI_MODEL=gpt-4o-2024-11-20
PLANNER_TEMPERATURE=0.3
BROWSER_TEMPERATURE=0.5
LOG_LEVEL=INFO
```

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

## Next Phase: Browser Search

The browser search agent is scaffolded and ready for implementation:

### Planned Features
- Multi-platform search (Amazon, eBay, Walmart, etc.)
- Product data extraction
- Relevance scoring
- Price comparison
- Filtering and pagination
- Rate limiting and retries

### Implementation Roadmap
1. Add web scraping utilities
2. Implement e-commerce API integrations
3. Build product ranking system
4. Add price tracking
5. Implement agent handoffs
6. Add caching and optimization

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
