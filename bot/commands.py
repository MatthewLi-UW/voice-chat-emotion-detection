import discord
import threading
import queue
from discord.ext import commands
from config import user_tilt_scores, voice_clients, processing_queues, logger
from utils.tilt import update_tilt_decay, get_tilt_message, get_tilt_color
from bot.voice import start_listening, process_audio_thread

def setup_commands(bot):
    @bot.command(name='join')
    async def join(ctx):
        """Join the voice channel the user is in"""
        if ctx.author.voice and ctx.author.voice.channel:
            channel = ctx.author.voice.channel
            if ctx.voice_client is not None:
                await ctx.voice_client.move_to(channel)
            else:
                voice_client = await channel.connect()
                voice_clients[ctx.guild.id] = voice_client
                
                # Set up audio processing queue for this guild
                processing_queues[ctx.guild.id] = queue.Queue()
                
                # Start audio processing thread
                threading.Thread(
                    target=process_audio_thread, 
                    args=(ctx.guild.id, ctx.channel.id),
                    daemon=True
                ).start()
                
                await ctx.send(f"JustFF joined {channel} and is monitoring tilt levels!")
                
                # Start listening
                await start_listening(ctx, voice_client)
        else:
            await ctx.send("You need to be in a voice channel for me to join!")

    @bot.command(name='leave')
    async def leave(ctx):
        """Leave the voice channel"""
        if ctx.voice_client:
            guild_id = ctx.guild.id
            
            # Clean up resources
            if guild_id in voice_clients:
                del voice_clients[guild_id]
            
            if guild_id in processing_queues:
                # Signal the processing thread to stop
                processing_queues[guild_id].put(None)
                del processing_queues[guild_id]
            
            await ctx.voice_client.disconnect()
            await ctx.send("JustFF left the voice channel!")
        else:
            await ctx.send("I'm not in a voice channel!")

    @bot.command(name='tilt')
    async def tilt(ctx, member: discord.Member = None):
        """Check a player's tilt level"""
        if member is None:
            member = ctx.author
        
        update_tilt_decay(member.id)
        tilt_score = user_tilt_scores[member.id]["score"]
        
        tilt_message = get_tilt_message(tilt_score)
        
        embed = discord.Embed(
            title=f"🌡️ Tilt Level: {member.display_name}",
            description=f"Current tilt level: **{tilt_score}/100**\n{tilt_message}",
            color=get_tilt_color(tilt_score)
        )
        
        # Add a progress bar - convert to integer here
        progress = "█" * int(tilt_score // 10) + "░" * int(10 - (tilt_score // 10))
        embed.add_field(name="Tilt Meter", value=f"`{progress}`", inline=False)
        
        # Add recent triggers if available
        if user_tilt_scores[member.id].get("triggers", []):
            triggers = user_tilt_scores[member.id]["triggers"][-3:]  # Get last 3 triggers
            formatted_triggers = []
            for trigger in triggers:
                if trigger.startswith("+"):  # Positive triggers
                    formatted_triggers.append(f"• 🟢 {trigger[1:]}")  # Green circle for positive
                else:
                    formatted_triggers.append(f"• 🔴 {trigger}")  # Red circle for negative
                    
            embed.add_field(
                name="Recent Triggers",
                value="\n".join(formatted_triggers) or "None detected",
                inline=False
            )
        
        await ctx.send(embed=embed)

    @bot.command(name='tilts')
    async def tilts(ctx):
        """Check all players' tilt levels"""
        # Apply tilt decay to all users
        for user_id in list(user_tilt_scores.keys()):
            update_tilt_decay(user_id)
        
        if not user_tilt_scores:
            await ctx.send("No tilt data available yet!")
            return
        
        embed = discord.Embed(
            title="🌡️ Team Tilt Levels",
            description="Current tilt levels for all tracked players",
            color=discord.Color.purple()
        )
        
        # Sort users by tilt score
        sorted_users = sorted(user_tilt_scores.items(), 
                            key=lambda x: x[1]["score"], 
                            reverse=True)
        
        users_added = 0
        
        for user_id, data in sorted_users:
            tilt_score = data["score"]
            
            # Try both methods to get the user
            user = bot.get_user(user_id)
            if not user and ctx.guild:
                user = ctx.guild.get_member(user_id)
                
            if user:
                # Round the tilt score to avoid float display issues
                tilt_score = round(tilt_score, 1)
                progress = "█" * int(tilt_score // 10) + "░" * int(10 - (tilt_score // 10))
                embed.add_field(
                    name=f"{user.display_name}: {tilt_score}/100",
                    value=f"`{progress}`\n{get_tilt_message(tilt_score)[:50]}",
                    inline=False
                )
                users_added += 1
                
                # Discord has a 25 field limit per embed
                if users_added >= 25:
                    break
        
        if users_added > 0:
            await ctx.send(embed=embed)
        else:
            # If we have scores but couldn't find any users
            if user_tilt_scores:
                await ctx.send("Could not find any users with tilt scores. They may have left the server.")
            else:
                await ctx.send("No tilt data available yet!")

    @bot.command(name='reset')
    async def reset(ctx, member: discord.Member = None):
        """Reset tilt scores for a user or everyone"""
        if member:
            user_tilt_scores[member.id] = {"score": 0, "last_updated": time.time(), "samples": [], "triggers": []}
            await ctx.send(f"Reset tilt score for {member.display_name} to 0.")
        else:
            for user_id in list(user_tilt_scores.keys()):
                user_tilt_scores[user_id] = {"score": 0, "last_updated": time.time(), "samples": [], "triggers": []}
            await ctx.send("Reset tilt scores for all users to 0.")

    @bot.command(name='help')
    async def help_command(ctx):
        """Display help information"""
        embed = discord.Embed(
            title="JustFF Bot Commands",
            description="Monitor and analyze how tilted players are in voice chat",
            color=discord.Color.blue()
        )
        
        embed.add_field(name="!join", value="Bot joins your voice channel and starts monitoring", inline=False)
        embed.add_field(name="!leave", value="Bot leaves the voice channel", inline=False)
        embed.add_field(name="!tilt [@user]", value="Check tilt level of yourself or mentioned user", inline=False)
        embed.add_field(name="!tilts", value="Check tilt levels of all tracked players", inline=False)
        embed.add_field(name="!reset [@user]", value="Reset tilt score for yourself or mentioned user (no mention = reset all)", inline=False)
        embed.add_field(name="!sensitivity [low|medium|high]", value="Adjust tilt detection sensitivity", inline=False)
        
        await ctx.send(embed=embed)

    @bot.command(name='sensitivity')
    async def sensitivity(ctx, level: str = None):
        """Set the tilt detection sensitivity"""
        if level is None:
            await ctx.send("Please specify a sensitivity level: low, medium, or high")
            return
        
        level = level.lower()
        if level not in ["low", "medium", "high"]:
            await ctx.send("Invalid sensitivity level. Choose from: low, medium, high")
            return
        
        multipliers = {
            "low": 0.5,
            "medium": 1.0,
            "high": 1.5
        }
        
        # Store the sensitivity multiplier in the bot's state
        bot.sensitivity_multiplier = multipliers[level]
        
        await ctx.send(f"Tilt detection sensitivity set to {level.upper()}")

    @bot.command(name='analyze')
    async def analyze_command(ctx, *, text: str = None):
        """Analyze text with the sentiment analyzer to see tilt score calculation"""
        if not text:
            await ctx.send("Please provide some text to analyze.")
            return
            
        await ctx.send(f"Analyzing: '{text}'...")
        
        from utils.speech import analyze_text_for_tilt, tilt_pipeline
        from utils.text_analysis import fallback_analyze_text_for_tilt
        
        # Use the sentiment analyzer first
        if tilt_pipeline is not None:
            score = analyze_text_for_tilt(text)
            keyword_score = fallback_analyze_text_for_tilt(text)
            
            embed = discord.Embed(
                title="Tilt Analysis Results",
                description=f"Text: '{text}'",
                color=get_tilt_color(abs(score) * 5)  # Scale to match 0-100 color scale
            )
            
            if score >= 0:
                embed.add_field(name="Sentiment Score", value=f"+{score}/20 (increases tilt)", inline=True)
            else:
                embed.add_field(name="Sentiment Score", value=f"{score}/20 (decreases tilt)", inline=True)
                
            embed.add_field(name="Keyword Score", value=f"{keyword_score}/20", inline=True)
            
            await ctx.send(embed=embed)
        else:
            await ctx.send("Sentiment analysis is not available. Using keyword analysis only.")
            score = fallback_analyze_text_for_tilt(text)
            await ctx.send(f"Keyword analysis score: {score}/20")
    
    return bot