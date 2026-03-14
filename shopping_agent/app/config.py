"""
Configuration management for the shopping agent system.
"""

import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Application configuration."""

    # OpenAI Configuration
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "") or os.getenv("AWS_BEARER_TOKEN_BEDROCK", "")
    OPENAI_BASE_URL: Optional[str] = os.getenv("OPENAI_BASE_URL", None)
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # Agent Configuration
    PLANNER_TEMPERATURE: float = float(os.getenv("PLANNER_TEMPERATURE", "0.3"))
    BROWSER_TEMPERATURE: float = float(os.getenv("BROWSER_TEMPERATURE", "0.5"))

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Agent names
    PLANNER_AGENT_NAME: str = "planner"
    BROWSER_AGENT_NAME: str = "browser_search"

    # Timeouts and limits
    MAX_RETRIES: int = 3
    REQUEST_TIMEOUT: int = 60

    # Post-processing configuration
    MAX_ITEMS_PER_PLAN: int = 20
    MIN_DESCRIPTION_LENGTH: int = 3
    SIMILARITY_THRESHOLD: float = 0.85  # For deduplication

    # Browser search configuration
    BROWSER_SEARCH_ENABLED: bool = os.getenv("BROWSER_SEARCH_ENABLED", "true").lower() == "true"
    BROWSER_HEADLESS: bool = os.getenv("BROWSER_HEADLESS", "true").lower() == "true"
    BROWSER_SEARCH_TIMEOUT: int = int(os.getenv("BROWSER_SEARCH_TIMEOUT", "30"))
    MAX_PARALLEL_SEARCHES: int = int(os.getenv("MAX_PARALLEL_SEARCHES", "3"))

    @classmethod
    def validate(cls) -> None:
        """Validate required configuration."""
        if not cls.OPENAI_API_KEY:
            raise ValueError(
                "OPENAI_API_KEY is required. Set it in .env or environment variables."
            )

    @classmethod
    def get_model(cls, agent_name: str) -> str:
        """Get model for specific agent (allows per-agent model overrides in future)."""
        return cls.OPENAI_MODEL

    @classmethod
    def get_temperature(cls, agent_name: str) -> float:
        """Get temperature for specific agent."""
        if agent_name == cls.PLANNER_AGENT_NAME:
            return cls.PLANNER_TEMPERATURE
        elif agent_name == cls.BROWSER_AGENT_NAME:
            return cls.BROWSER_TEMPERATURE
        return 0.5


# Note: Config validation is done lazily when agents are initialized
# This allows tests to set environment variables before validation
