import discord
from discord.ext import commands
from config import BOT_PREFIX, logger

# Initialize Discord bot with intents
intents = discord.Intents.default()
intents.voice_states = True
intents.messages = True
intents.message_content = True

# Create bot instance
bot = commands.Bot(command_prefix=BOT_PREFIX, intents=intents)
bot.remove_command('help')  # Remove the built-in help command

def setup_bot():
    from bot.commands import setup_commands
    from bot.events import setup_events
    
    # Set up commands
    setup_commands(bot)
    
    # Set up events
    setup_events(bot)
    
    # Set default sensitivity
    bot.sensitivity_multiplier = 1.0
    
    return bot