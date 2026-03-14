"""
Discord bot integration for the shopping agent system.

Connects to Discord and handles incoming messages.
Currently sends a "please wait" acknowledgement, then processes and responds.
"""

import asyncio
import logging
import os
from typing import Optional

import discord
from discord.ext import commands

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv loaded by config.py or not available

logger = logging.getLogger("shopping_agent.discord")

DISCORD_BOT_TOKEN: str = os.getenv("DISCORD_BOT_TOKEN", "")
DISCORD_CHANNEL_ID: Optional[int] = (
    int(os.getenv("DISCORD_CHANNEL_ID")) if os.getenv("DISCORD_CHANNEL_ID") else None
)

# Bot setup with message content intent
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready() -> None:
    """Called when the bot has connected to Discord."""
    logger.info(f"Bot connected as {bot.user} (ID: {bot.user.id})")
    logger.info(f"Connected to {len(bot.guilds)} guild(s)")
    for guild in bot.guilds:
        logger.info(f"  - {guild.name} (ID: {guild.id})")


@bot.event
async def on_message(message: discord.Message) -> None:
    """Handle incoming messages."""
    # Ignore messages from the bot itself
    if message.author == bot.user:
        return

    # If a specific channel is configured, only respond there
    if DISCORD_CHANNEL_ID and message.channel.id != DISCORD_CHANNEL_ID:
        # Still process commands in any channel
        await bot.process_commands(message)
        return

    # Ignore messages that are bot commands (let the command handler deal with them)
    if message.content.startswith("!"):
        await bot.process_commands(message)
        return

    logger.info(
        f"Message from {message.author} in #{message.channel}: {message.content}"
    )

    # Step 1: Acknowledge immediately
    await message.reply("Please wait, processing your request...")

    # Step 2: Process the message (hardcoded for now, replace with real logic later)
    response = await process_message(message.content, str(message.author))

    # Step 3: Send the response
    await message.reply(response)


async def process_message(content: str, author: str) -> str:
    """
    Process an incoming message and return a response.

    This is the hook point — replace this with real agent logic later.
    Currently returns a hardcoded acknowledgement.
    """
    # TODO: Wire up to ShoppingOrchestrator for real processing
    # Example future implementation:
    #   orchestrator = ShoppingOrchestrator()
    #   result = orchestrator.create_shopping_plan(user_request=content)
    #   return format_plan_for_discord(result)

    return (
        f"Got your message: **{content}**\n\n"
        "I'm the Shopping Agent bot. "
        "This feature is under development — full responses coming soon!"
    )


@bot.command(name="plan")
async def plan_command(ctx: commands.Context, *, request: str) -> None:
    """Generate a shopping plan. Usage: !plan birthday party supplies"""
    await ctx.reply("Please wait, generating your shopping plan...")

    response = await process_message(request, str(ctx.author))
    await ctx.reply(response)


@bot.command(name="ping")
async def ping_command(ctx: commands.Context) -> None:
    """Check if the bot is alive."""
    await ctx.reply(f"Pong! Latency: {round(bot.latency * 1000)}ms")


@bot.command(name="status")
async def status_command(ctx: commands.Context) -> None:
    """Show bot status."""
    await ctx.reply(
        f"Shopping Agent Bot\n"
        f"Status: Online\n"
        f"Guilds: {len(bot.guilds)}\n"
        f"Latency: {round(bot.latency * 1000)}ms"
    )


async def send_message(channel_id: int, content: str) -> None:
    """
    Send a message to a specific Discord channel.

    Use this to push messages from the server side (e.g., after async processing).
    The bot must be running for this to work.
    """
    channel = bot.get_channel(channel_id)
    if channel is None:
        logger.error(f"Channel {channel_id} not found")
        return
    await channel.send(content)


def run_bot() -> None:
    """Start the Discord bot. Blocks until the bot is stopped."""
    if not DISCORD_BOT_TOKEN:
        raise ValueError(
            "DISCORD_BOT_TOKEN is required. Set it in .env or environment variables.\n"
            "See: https://discord.com/developers/applications"
        )

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    logger.info("Starting Discord bot...")
    bot.run(DISCORD_BOT_TOKEN)


if __name__ == "__main__":
    run_bot()
