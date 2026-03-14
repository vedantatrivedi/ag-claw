# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Multi-agent shopping system (Python 3.11+) that converts natural language shopping requests into structured plans. Built with OpenAI SDK, Pydantic, Typer CLI, and managed with Poetry.

## Commands

```bash
# Install & setup
poetry install
cp .env.example .env    # add OPENAI_API_KEY
poetry shell

# Run
shopping-agent plan "birthday party supplies"
shopping-agent example party          # predefined examples: party, interview, gift, desk
shopping-agent interactive "request"  # interactive clarification mode
shopping-agent info                   # system info
shopping-agent architecture           # architecture details

# Test
poetry run pytest                                    # all tests
poetry run pytest shopping_agent/tests/test_models.py  # single file
poetry run pytest -m "not integration"               # skip API-dependent tests
poetry run pytest --cov=shopping_agent                # with coverage

# Code quality
poetry run black shopping_agent/     # format (100-char line length)
poetry run ruff check shopping_agent/  # lint
poetry run mypy shopping_agent/      # type check (strict: disallow_untyped_defs)
```

## Architecture

**Pipeline:** User input → Planner Agent → Post-processing → Guardrails → (optional) Interactive refinement → (future) Browser Search Agent

### Key modules

- **`app/main.py`** — Typer CLI entry point, defines all commands and options
- **`app/agents/planner.py`** — Planner agent: calls OpenAI Chat Completions (JSON mode, temp 0.3) with retry logic (exponential backoff, 3 attempts)
- **`app/agents/browser_search.py`** — Browser search agent (scaffolded, not fully active): multi-site product search with deterministic 7-factor ranking
- **`app/models.py`** — Pydantic v2 models: `PlanItem`, `ShoppingPlan`, `SearchResult`, `AgentResponse`
- **`app/prompts.py`** — System prompts for LLM agents including site selection rules and output format spec
- **`app/postprocess.py`** — Deterministic 6-step cleanup: trim, normalize quantities, remove vague items, deduplicate (0.85 similarity threshold), sort required-first, cap at 20 items
- **`app/guardrails.py`** — 5 non-breaking validation checks (schema, no URLs, no store names, item concreteness, plan completeness)
- **`app/orchestrator.py`** — Coordinates multi-agent pipeline
- **`app/interactive.py`** — Interactive clarification loop workflow
- **`app/config.py`** — Configuration from env vars; validates API key on import

### Design decisions

- **Non-breaking guardrails**: violations are logged, not hard failures
- **JSON mode**: OpenAI structured output ensures valid JSON responses
- **Post-processing is deterministic**: no LLM calls, pure data transformation
- **Pydantic v2 throughout**: all data exchange uses typed models
- **All code quality tools target 100-char line length and Python 3.11**

## Environment Variables

- `OPENAI_API_KEY` (required)
- `OPENAI_MODEL` (default: gpt-4o-2024-11-20)
- `PLANNER_TEMPERATURE` (default: 0.3)
- `BROWSER_TEMPERATURE` (default: 0.5)
- `BROWSER_SEARCH_ENABLED`, `BROWSER_HEADLESS` — browser search config
