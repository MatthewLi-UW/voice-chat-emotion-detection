from config import logger, user_tilt_scores
from utils.speech import analyze_text_for_tilt
from utils.tilt import update_tilt_score

def setup_events(bot):
    @bot.event
    async def on_ready():
        logger.info(f'{bot.user.name} has connected to Discord!')

    @bot.event
    async def on_message(message):
        """Process text messages for tilt indicators"""
        if message.author == bot.user:
            return
        
        # Process commands first
        await bot.process_commands(message)
        
        # Skip command messages for tilt analysis
        if message.content.startswith(bot.command_prefix):
            return
        
        # Only analyze messages in voice channels or their associated text channels
        if message.author.voice:
            tilt_score_increase = analyze_text_for_tilt(message.content.lower())
            
            if tilt_score_increase != 0:
                # Apply sensitivity multiplier if set
                if hasattr(bot, 'sensitivity_multiplier'):
                    tilt_score_increase *= bot.sensitivity_multiplier
                    
                update_tilt_score(message.author.id, tilt_score_increase, trigger=message.content)
                
                # Log based on whether it's positive or negative
                if tilt_score_increase > 0:
                    logger.debug(f"Increased {message.author.name}'s tilt by {tilt_score_increase} to {user_tilt_scores[message.author.id]['score']}")
                else:
                    logger.debug(f"Decreased {message.author.name}'s tilt by {abs(tilt_score_increase)} to {user_tilt_scores[message.author.id]['score']}")
                
                # If someone gets very tilted, send a notification
                if user_tilt_scores[message.author.id]["score"] >= 90:
                    await message.channel.send(f"⚠️ **Tilt Alert**: {message.author.mention} is reaching critical tilt levels! ({user_tilt_scores[message.author.id]['score']}/100)")
    
    return bot