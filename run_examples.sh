#!/bin/bash
# Example commands for the shopping agent system

set -e

echo "Shopping Agent - Example Commands"
echo "=================================="
echo ""

# Check if API key is set
if [ -z "$OPENAI_API_KEY" ]; then
    echo "Error: OPENAI_API_KEY environment variable is not set"
    echo "Please set it in .env or export it"
    exit 1
fi

echo "1. Running: Birthday party example"
echo "-----------------------------------"
poetry run shopping-agent example party
echo ""
echo ""

echo "2. Running: Interview prep example"
echo "-----------------------------------"
poetry run shopping-agent example interview
echo ""
echo ""

echo "3. Running: Custom request"
echo "--------------------------"
poetry run shopping-agent plan "Gift basket for a new mom"
echo ""
echo ""

echo "4. Showing system information"
echo "-----------------------------"
poetry run shopping-agent info
echo ""
echo ""

echo "All examples completed successfully!"
