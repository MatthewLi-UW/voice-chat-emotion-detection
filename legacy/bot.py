import discord
import asyncio
import time
import numpy as np
from discord.ext import commands
import re
import os
import wave
import json
from collections import defaultdict
import logging
import tempfile
import subprocess
import threading
import queue
from pydub import AudioSegment
import whisper
import torch

from dotenv import load_dotenv
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
import torch

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('JustFF')

# environment variables from .env file
load_dotenv()

# Initialize Discord bot with intents
intents = discord.Intents.default()
intents.voice_states = True
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)
bot.remove_command('help')

# Global variables
user_tilt_scores = defaultdict(lambda: {"score": 0, "last_updated": time.time(), "samples": []})
TILT_DECAY_RATE = 5  # Points per minute that tilt score decreases
MAX_SAMPLES = 10  # Maximum number of voice samples to store per user
voice_clients = {}  # Store voice clients for each guild
processing_queues = {}  # Audio processing queues

# lightweight Whisper model
WHISPER_MODEL_SIZE = "base"  # Options: "tiny", "base", "small", "medium", "large"
logger.info(f"Loading Whisper {WHISPER_MODEL_SIZE} model...")
whisper_model = whisper.load_model(WHISPER_MODEL_SIZE)
logger.info(f"Whisper model loaded successfully")

# Load a lightweight local LLM for tilt analysis
logger.info("Loading local LLM for tilt analysis...")
try:
    
    model_name = "distilbert/distilbert-base-uncased-finetuned-sst-2-english"
    
    # simpler sentiment analysis pipeline without 8-bit quantization
    tilt_pipeline = pipeline(
        "sentiment-analysis",
        model=model_name,
        device=-1  # Use CPU
    )
    
    logger.info("Local sentiment analysis model loaded successfully")
except Exception as e:
    logger.error(f"Failed to load sentiment model: {e}")
    logger.info("Falling back to keyword-based tilt analysis")
    tilt_pipeline = None

# Tilt keywords and their weights
TILT_KEYWORDS = {
    r'\bf+\s*(?:u+|you+)\b': 10,  # f u, f you
    r'\bwhat\s+(?:the\s+)?(?:f+|hell|heck)\b': 7,  # what the f, what the hell
    r'\bbs\b': 5,  # bs
    r'\b(?:this|that)\s+is\s+(?:bs|bullshit)\b': 8,  # this is bs
    r'\bgarbage\b': 6,  # garbage
    r'\btrash\b': 6,  # trash
    r'\bthrow(?:ing)?\b': 5,  # throw, throwing
    r'\bfeeding\b': 5,  # feeding
    r'\bint(?:ing)?\b': 5,  # int, inting
    r'\btoxic\b': 6,  # toxic
    r'\buninstall\b': 8,  # uninstall
    r'\bdumb\b': 5,  # dumb
    r'\bstupid\b': 5,  # stupid
    r'\breport\b': 4,  # report
    r'\brage\b': 7,  # rage
    r'\bquit(?:ting)?\b': 7,  # quit
    r'\bdc\b': 3,  # dc (disconnect)
    r'\bafk\b': 3,  # afk
    r'\btilt(?:ed)?\b': 5,  # tilt, tilted
    r'\bgg\s+(?:wp|ez)\b': 4,  # gg wp, gg ez
    r'\bomg\b': 3,  # omg
    r'\bomfg\b': 5,  # omfg
    r'\bunbelievable\b': 4,  # unbelievable
    r'\bunreal\b': 4,  # unreal
    r'\blagg?(?:ing)?\b': 3,  # lag, lagging
    r'\bwhy\b': 2,  # why (context dependent but often used in frustration)
    r'\bcan\'?t\s+believe\b': 4,  # can't believe
    r'\bseriously\b': 3,  # seriously
    r'\bwow\b': 2,  # wow (context dependent)
    r'\bunplayable\b': 6,  # unplayable
    r'\bbroken\b': 5,  # broken
    r'\bnerf\b': 3,  # nerf
    r'\bop\b': 2,  # op (overpowered)
    r'\bbad\b': 3,  # bad
    r'\bworst\b': 5,  # worst
    r'\bhate\b': 6,  # hate
    r'\bfeed(?:ing)?\b': 5,  # feed, feeding
    r'\bsmurf\b': 4,  # smurf
    r'\bhack(?:s|er|ing)?\b': 7,  # hack, hacker, hacking
    r'\bscript(?:er|ing)?\b': 7,  # script, scripter, scripting
    r'\bbot\b': 3,  # bot (as an insult)
    r'\bnoob\b': 4,  # noob
    r'\bretard(?:ed)?\b': 9,  # retard
    r'\bidiot\b': 7,  # idiot
    r'\bmoron\b': 7,  # moron
    r'!!+': 3,  # Multiple exclamation marks
    r'\bcmon\b': 3,  # cmon
    r'\bcome\s+on\b': 3,  # come on
    r'\bdude\b': 2,  # dude (context dependent)
    r'\bwtf\b': 6,  # wtf
    r'\bomg\b': 3,  # omg
    r'\bholy\s+(?:shit|crap)\b': 7,  # holy shit, holy crap
    r'\bare\s+you\s+(?:serious|kidding)\b': 5,  # are you serious, are you kidding
    r'\bwhat\s+are\s+you\s+doing\b': 4,  # what are you doing
    r'\bliterally\b': 3,  # literally (often used in frustration)
    r'\bno\s+way\b': 3,  # no way
    r'\bthrowing\b': 5,  # throwing
    r'\bno\s+(?:cs|farm)\b': 4,  # no cs, no farm
    r'\bgank\b': 3,  # gank (context dependent)
    r'\bjungle\s+(?:diff|gap)\b': 5,  # jungle diff/gap
    r'\b(?:mid|top|bot|adc|supp?)\s+(?:diff|gap)\b': 5,  # lane diff/gap
    r'\bjustff\b': 5, # just ff
}

# Add this after your TILT_KEYWORDS dictionary
POSITIVE_KEYWORDS = {
    r'\bgood\s+(?:job|play|kill|shot|ult|move|call)\b': 3,  # good job, good play, etc.
    r'\bnice\s+(?:job|play|kill|shot|ult|move|call)\b': 3,  # nice job, nice play, etc.
    r'\bgreat\s+(?:job|play|kill|shot|ult|move|call)\b': 4,  # great job, great play, etc.
    r'\bwell\s+played\b': 4,  # well played
    r'\bwell\s+done\b': 3,  # well done
    r'\bgood\s+try\b': 2,  # good try
    r'\bthank\s+(?:you|u)\b': 2,  # thank you
    r'\bthanks\b': 1,  # thanks
    r'\bwe\s+can\s+(?:win|do)\s+(?:this)\b': 4,  # we can win this, we can do this
    r'\bwe\s+got\s+this\b': 3,  # we got this
    r'\bno\s+(?:problem|worries)\b': 2,  # no problem, no worries
    r'\byou\'?re?\s+(?:good|great|amazing|awesome)\b': 3,  # you're good, you're great
    r'\bnp\b': 1,  # np (no problem)
    r'\bI\'?ll?\s+help\b': 3,  # I'll help
    r'\blet\'?s\s+group\b': 2,  # let's group
    r'\bstick\s+together\b': 2,  # stick together
    r'\bI\s+believe\b': 3,  # I believe
    r'\bcomeback\b': 2,  # comeback
    r'\bwinnable\b': 2,  # winnable
    r'\bthat\s+was\s+(?:awesome|amazing|sick|insane)\b': 4,  # that was awesome
    r'\bgood\s+game\b': 2,  # good game (not sarcastic)
    r'\bgg\b': 1,  # gg (not "gg ez")
    r'\bcarry\s+(?:on|us)\b': 3,  # carry on, carry us
    r'\bhave\s+fun\b': 2,  # have fun
}

# Voice indicators of tilt
VOICE_TILT_INDICATORS = {
    'amplitude': {'threshold': 0.7, 'score': 5},  # Loud volume
    'speaking_rate': {'threshold': 3.5, 'score': 3},  # Fast speaking
    'interruptions': {'threshold': 2, 'score': 4},  # Interrupting others
}

class VoiceReceiver(discord.VoiceClient):
    def __init__(self, client, channel):
        super().__init__(client, channel)
        self.user_audio_buffer = defaultdict(list)
        self.speaking_users = set()
        self.guild_id = channel.guild.id

    def handle_voice_data(self, user_id, audio_data):
        # Add audio data to user's buffer
        self.user_audio_buffer[user_id].append(audio_data)
        
        # If we have enough data, process it
        if len(self.user_audio_buffer[user_id]) >= 50:  # ~1 second of audio at 50 packets/sec
            # Process audio in a separate thread to avoid blocking
            audio_data = b''.join(self.user_audio_buffer[user_id])
            self.user_audio_buffer[user_id] = []
            
            if self.guild_id in processing_queues:
                processing_queues[self.guild_id].put((user_id, audio_data))

@bot.event
async def on_ready():
    logger.info(f'{bot.user.name} has connected to Discord!')

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

async def start_listening(ctx, voice_client):
    """Set up voice reception"""
    logger.info(f"Starting to listen in guild {ctx.guild.id}")
    
    # Create a new MP3Sink for recording
    recording_sink = discord.sinks.MP3Sink()
    
    # Start recording
    voice_client.start_recording(
        recording_sink,
        finished_callback,
        ctx.channel
    )
    
    logger.info("Recording started")
    
    # Schedule regular processing of audio
    bot.loop.create_task(process_recordings_regularly(ctx, voice_client))

async def process_recordings_regularly(ctx, voice_client):
    """Regularly stop and restart recording to process chunks"""
    while ctx.voice_client and ctx.voice_client.is_connected():
        await asyncio.sleep(10)  # Process every 5 seconds
        if hasattr(voice_client, 'recording') and voice_client.recording:
            try:
                voice_client.stop_recording()  # This triggers the callback
                await asyncio.sleep(0.5)  # Give time for callback to complete
                
                # Start recording again with new sink
                recording_sink = discord.sinks.MP3Sink()
                voice_client.start_recording(
                    recording_sink,
                    finished_callback,
                    ctx.channel
                )
            except Exception as e:
                logger.error(f"Error in process_recordings_regularly: {e}")

async def finished_callback(sink, channel):
    """Callback for when recording is finished"""
    logger.info("Recording callback triggered")
    
    try:
        # Process the recorded audio data
        for user_id, audio in sink.audio_data.items():
            # Add to processing queue for analysis
            if channel.guild.id in processing_queues:
                try:
                    # Create a temporary file for the audio data
                    with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
                        # Get audio bytes from the sink's audio object
                        audio.file.seek(0)  # Go to start of file
                        audio_bytes = audio.file.read()
                        temp_file.write(audio_bytes)
                        temp_path = temp_file.name
                    
                    # Add file path to processing queue instead of raw bytes
                    processing_queues[channel.guild.id].put((user_id, temp_path))
                except Exception as e:
                    logger.error(f"Error processing audio data: {e}")
    except Exception as e:
        logger.error(f"Error in finished_callback: {e}")

def process_audio_thread(guild_id, channel_id):
    """Thread for processing audio data"""
    logger.info(f"Started audio processing thread for guild {guild_id}")
    
    while True:
        try:
            # Get the next audio packet from the queue
            task = processing_queues[guild_id].get()
            
            # None is the signal to exit
            if task is None:
                logger.info(f"Stopping audio processing thread for guild {guild_id}")
                break
            
            user_id, audio_data = task
            
            # Process the audio data
            process_audio(guild_id, channel_id, user_id, audio_data)
            
        except Exception as e:
            logger.error(f"Error in audio processing thread: {e}")
    
    logger.info(f"Audio processing thread for guild {guild_id} exited")

def process_audio(guild_id, channel_id, user_id, audio_path):
    """Process audio data for a user"""
    try:
        # Get the guild object
        guild = bot.get_guild(guild_id)
        
        # Preprocess the audio
        processed_path = f"{audio_path}_processed.wav"
        processed_path = preprocess_audio(audio_path, processed_path)
        
        # Use Whisper to transcribe the audio
        try:
            result = whisper_model.transcribe(
                processed_path, 
                language="en",
                word_timestamps=True,  # Get timestamps for words
                fp16=False  # Explicitly disable FP16
            )
            
            transcription = result["text"].strip()
            
            if transcription:
                # Apply gaming term corrections
                corrected_text = correct_gaming_terms(transcription)
                
                # Apply username corrections
                corrected_text = correct_usernames(corrected_text, guild)
                
                logger.info(f"Transcribed: {transcription}")
                logger.info(f"Corrected: {corrected_text}")
                
                # Analyze the corrected transcription for tilt
                tilt_score_increase = analyze_text_for_tilt(corrected_text.lower())
                
                if tilt_score_increase > 0:
                    # Apply sensitivity multiplier if set
                    if hasattr(bot, 'sensitivity_multiplier'):
                        tilt_score_increase *= bot.sensitivity_multiplier
                    
                    update_tilt_score(user_id, tilt_score_increase, trigger=corrected_text)
                    logger.info(f"Voice caused tilt increase of {tilt_score_increase} for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error in speech recognition: {e}")
        
        # Clean up temporary files
        try:
            os.unlink(audio_path)
            if processed_path != audio_path:
                os.unlink(processed_path)
        except Exception as e:
            logger.error(f"Error cleaning up temp files: {e}")
        
    except Exception as e:
        logger.error(f"Error processing audio: {e}")

def preprocess_audio(input_path, output_path):
    """Improve audio quality before transcription"""
    try:
        # Load audio
        audio = AudioSegment.from_file(input_path)
        
        # Normalize volume
        audio = audio.normalize()
        
        # Boost speech frequencies (human voice is mostly 85-255 Hz)
        audio = audio.high_pass_filter(80).low_pass_filter(8000)
        
        # Export processed file
        audio.export(output_path, format="wav")
        return output_path
    except Exception as e:
        logger.error(f"Error preprocessing audio: {e}")
        return input_path  # Return original if processing fails

def correct_gaming_terms(text):
    """Apply corrections for commonly misrecognized gaming terms"""
    # General Gaming Terms
    GENERAL_GAMING_TERMS = {
        "gank": "gank",
        "inting": "inting",
        "camping": "camping",
        "smurf": "smurf",
        "toxic": "toxic",
        "lag": "lag",
        "rage quit": "rage quit",
        "afk": "afk", 
        "gg": "gg",
        "gg ez": "gg ez",
        "clutch": "clutch",
        "nerf": "nerf",
        "buff": "buff",
        "op": "op",
        "meta": "meta",
        "respawn": "respawn",
        "cooldown": "cooldown",
        "spawn kill": "spawn kill"
    }
    
    # MOBA Terms (League of Legends, Dota 2)
    MOBA_TERMS = {
        "cs": "cs",
        "last hit": "last hit",
        "adc": "adc",
        "jungle": "jungle",
        "gank": "gank",
        "leashing": "leashing",
        "mid": "mid",
        "top": "top",
        "bot": "bot",
        "support": "support",
        "inting": "inting",
        "feeding": "feeding",
        "jungler": "jungler",
        "ward": "ward",
        "baron": "baron",
        "drake": "drake",
        "dragon": "dragon",
        "herald": "herald",
        "elder": "elder",
        "inhibitor": "inhibitor",
        "nexus": "nexus",
        "turret": "turret",
        "tower": "tower",
        "minions": "minions",
        "creeps": "creeps",
        "lane phase": "lane phase",
        "mid game": "mid game",
        "late game": "late game",
        "ult": "ult",
        "ultimate": "ultimate",
        "first blood": "first blood",
        "penta": "penta",
        "penta kill": "penta kill"
    }
    
    # FPS Terms (CS:GO, Valorant, Call of Duty)
    FPS_TERMS = {
        "ace": "ace",
        "headshot": "headshot",
        "wallbang": "wallbang",
        "camp": "camp",
        "camping": "camping",
        "flank": "flank",
        "push": "push",
        "rotate": "rotate",
        "defuse": "defuse",
        "plant": "plant",
        "clutch": "clutch",
        "scope": "scope",
        "crosshair": "crosshair",
        "spray": "spray",
        "awp": "awp",
        "awping": "awping",
        "peek": "peek",
        "strafe": "strafe",
        "boost": "boost",
        "drop": "drop",
        "eco": "eco",
        "frag": "frag",
        "hold": "hold",
        "lurk": "lurk",
        "op": "op",
        "operator": "operator",
        "trade": "trade",
        "spawn": "spawn",
        "spawn kill": "spawn kill",
        "wall hack": "wall hack"
    }
    
    # Battle Royale Terms
    BR_TERMS = {
        "drop": "drop",
        "hot drop": "hot drop",
        "zone": "zone",
        "circle": "circle",
        "loot": "loot",
        "third party": "third party",
        "thirded": "thirded",
        "shield": "shield",
        "cracked": "cracked",
        "one shot": "one shot",
        "rotate": "rotate",
        "push": "push",
        "box": "box",
        "death box": "death box",
        "res": "res",
        "revive": "revive",
        "pick up": "pick up",
        "ping": "ping",
        "marked": "marked",
        "knocked": "knocked"
    }
    
    # Difference/Comparison Terms
    DIFF_TERMS = {
        "diff": "diff",
        "gap": "gap",
        "mid diff": "mid diff",
        "top diff": "top diff",
        "bot diff": "bot diff",
        "jungle diff": "jungle diff",
        "support diff": "support diff",
        "skill issue": "skill issue",
        "better player": "better player",
        "outplayed": "outplayed"
    }
    
    # Common Phrases/Expressions
    EXPRESSIONS = {
        "just ff": "just ff",
        "surrender": "surrender",
        "ff fifteen": "ff fifteen",
        "ff at 15": "ff at 15",
        "open mid": "open mid",
        "trash talk": "trash talk",
        "grief": "grief",
        "griefing": "griefing",
        "throwing": "throwing",
        "winnable": "winnable",
        "not winnable": "not winnable",
        "report": "report",
        "report for": "report for",
        "broken champ": "broken champ",
        "broken character": "broken character",
        "lobby diff": "lobby diff",
        "team diff": "team diff"
    }
    
    # Common speech recognition mistakes
    COMMON_MISTAKES = {
        "see us": "cs",
        "a dc": "adc",
        "is he": "ez",
        "easy": "ez",
        "just have": "just ff",
        "just have have": "just ff",
        "medium": "mid lane",
        "top playing": "top lane",
        "bottom": "bot lane",
        "supporting": "support",
        "supporting role": "support",
        "in the jungle": "jungle",
        "middle": "mid",
        "middle lane": "mid lane",
        "bottom lane": "bot lane",
        "report him": "report",
        "reporter": "report her",
        "gank me": "gank",
        "ganking": "ganking",
        "farming": "farming",
        "feed": "feed",
        "feeding": "feeding",
        "he's feeding": "feeding",
        "she's feeding": "feeding",
        "they're feeding": "feeding",
        "i'm feeding": "feeding",
        "int": "int",
        "inting": "inting",
        "in ting": "inting",
        "jungler": "jungler",
        "dragons": "dragons",
        "baron": "baron"
    }
    
    # Combine all term dictionaries
    ALL_TERMS = {}
    ALL_TERMS.update(GENERAL_GAMING_TERMS)
    ALL_TERMS.update(MOBA_TERMS)
    ALL_TERMS.update(FPS_TERMS)
    ALL_TERMS.update(BR_TERMS)
    ALL_TERMS.update(DIFF_TERMS)
    ALL_TERMS.update(EXPRESSIONS)
    
    corrected = text.lower()
    
    # First apply regex for exact terms with word boundaries
    for term, correction in ALL_TERMS.items():
        # Use regex with word boundaries to replace whole words only
        corrected = re.sub(r'\b' + re.escape(term) + r'\b', correction, corrected, flags=re.IGNORECASE)
    
    # Then handle common speech recognition mistakes (which may need more complex replacements)
    for wrong, right in COMMON_MISTAKES.items():
        corrected = corrected.replace(wrong, right)
    
    return corrected

# Add this function after correct_gaming_terms or near other utility functions
def correct_usernames(text, guild):
    """Correct usernames/gamer tags in transcribed text"""
    if not guild:
        return text
        
    corrected = text
    
    try:
        # Build a dictionary of possible name variations for each member
        username_variations = {}
        
        for member in guild.members:
            # Skip bots
            if member.bot:
                continue
                
            # Add display name, username, and nickname
            variations = [
                member.name.lower(),
                member.display_name.lower()
            ]
            
            # Add nickname if it exists and is different
            if member.nick and member.nick.lower() not in variations:
                variations.append(member.nick.lower())
                
            # Add common speech recognition errors for each name
            for name in list(variations):  # Create a copy of the list to modify
                # Add versions without spaces
                if ' ' in name:
                    variations.append(name.replace(' ', ''))
                
                # Add phonetic variations (common speech-to-text errors)
                variations.extend(generate_name_variations(name))
            
            # Map all variations to the correct display name
            for variation in variations:
                username_variations[variation] = member.display_name
        
        # Replace variations with correct names using word boundary regex
        for variation, correct_name in username_variations.items():
            if len(variation) > 2:  # Ignore very short names to avoid false positives
                corrected = re.sub(
                    r'\b' + re.escape(variation) + r'\b', 
                    correct_name, 
                    corrected, 
                    flags=re.IGNORECASE
                )
                
        return corrected
        
    except Exception as e:
        logger.error(f"Error correcting usernames: {e}")
        return text

def generate_name_variations(name):
    """Generate common speech recognition variations of a name"""
    variations = []
    
    # Common speech recognition substitutions
    substitutions = {
        'c': ['see', 'sea'],
        'k': ['kay'],
        'x': ['ex'],
        'z': ['zee'],
        'ph': ['f'],
        'y': ['why'],
        '2': ['two', 'to', 'too'],
        '4': ['four', 'for'],
        '8': ['eight', 'ate'],
        '0': ['zero', 'oh'],
        # Add more common substitutions
    }
    
    # Generate variations by replacing characters/patterns
    for char, replacements in substitutions.items():
        if char in name:
            for replacement in replacements:
                variations.append(name.replace(char, replacement))
    
    return variations

def analyze_audio_characteristics(audio_file):
    """Analyze audio characteristics for signs of tilt"""
    try:
        # Load audio with pydub
        audio = AudioSegment.from_file(audio_file)
        
        # Analyze volume (dBFS is pydub's measure of volume)
        volume_score = 0
        if abs(audio.dBFS) < 20:  # Loud audio has values closer to 0
            volume_score = 3
        elif abs(audio.dBFS) < 30:
            volume_score = 2
        elif abs(audio.dBFS) < 40:
            volume_score = 1
        
        
        return volume_score
    
    except Exception as e:
        logger.error(f"Error analyzing audio: {e}")
        return 0

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
        
        if tilt_score_increase > 0:
            # Apply sensitivity multiplier if set
            if hasattr(bot, 'sensitivity_multiplier'):
                tilt_score_increase *= bot.sensitivity_multiplier
                
            update_tilt_score(message.author.id, tilt_score_increase, trigger=message.content)
            logger.debug(f"Increased {message.author.name}'s tilt by {tilt_score_increase} to {user_tilt_scores[message.author.id]['score']}")
            
            # If someone gets very tilted, send a notification
            if user_tilt_scores[message.author.id]["score"] >= 90:
                await message.channel.send(f"⚠️ **Tilt Alert**: {message.author.mention} is reaching critical tilt levels! ({user_tilt_scores[message.author.id]['score']}/100)")

def analyze_text_for_tilt(text):
    """Analyze text for signs of tilt or positive statements"""
    # Fall back to keyword method if text is too short or LLM not available
    if tilt_pipeline is None or len(text) < 5:
        logger.info(f"Using keyword fallback for: '{text}' (LLM available: {tilt_pipeline is not None}, text length: {len(text)})")
        return fallback_analyze_text_for_tilt(text)
    
    try:
        # Use sentiment analysis to determine tilt or positivity
        logger.info(f"Sending to sentiment analyzer: '{text}'")
        result = tilt_pipeline(text)[0]
        logger.info(f"Sentiment analysis result: {result}")
        
        # Convert sentiment to tilt score (-20 to 20)
        # Negative sentiment = positive tilt score (increasing tilt)
        # Positive sentiment = negative tilt score (decreasing tilt)
        if result['label'] == 'NEGATIVE':
            # Convert confidence score (0-1) to tilt score (0-20)
            tilt_score = int(result['score'] * 20)
            logger.info(f"Sentiment tilt analysis (negative): '{text}' -> Score: {tilt_score}")
            return tilt_score
        else:
            # If positive sentiment, reduce tilt (negative score)
            tilt_reduction = -int(result['score'] * 15)  # Max 15 point reduction
            logger.info(f"Sentiment tilt analysis (positive): '{text}' -> Score: {tilt_reduction}")
            return tilt_reduction
            
    except Exception as e:
        logger.error(f"Error in sentiment analysis: {e}")
        return fallback_analyze_text_for_tilt(text)

# Rename existing keyword-based analysis as fallback
def fallback_analyze_text_for_tilt(text):
    """Analyze text for signs of tilt or positivity using keywords"""
    score_change = 0
    
    # Check for tilt keywords (increase tilt)
    for pattern, value in TILT_KEYWORDS.items():
        matches = re.findall(pattern, text, re.IGNORECASE)
        score_change += len(matches) * value
    
    # Check for positive keywords (decrease tilt)
    for pattern, value in POSITIVE_KEYWORDS.items():
        matches = re.findall(pattern, text, re.IGNORECASE)
        score_change -= len(matches) * value
    
    # Check for all caps (shouting) - only if the overall message isn't positive
    if score_change >= 0 and len(text) > 5 and text.isupper():
        score_change += 5
    
    # Check for repeated punctuation (!!! or ???) - only if the overall message isn't positive
    if score_change >= 0 and re.search(r'[!?]{3,}', text):
        score_change += 3
    
    # Cap the score change (both positive and negative)
    return max(-15, min(score_change, 20))

def update_tilt_score(user_id, score_change, trigger=None):
    """Update a user's tilt score - positive values increase tilt, negative values reduce it"""
    update_tilt_decay(user_id)
    
    # Initialize if new user
    if user_id not in user_tilt_scores:
        user_tilt_scores[user_id] = {
            "score": 50, 
            "last_updated": time.time(), 
            "samples": [],
            "triggers": []
        }
    
    current_score = user_tilt_scores[user_id]["score"]
    
    # Handle positive score_change (increasing tilt)
    if score_change > 0:
        # Apply non-linear scaling based on detected tilt severity
        if score_change <= 5:
            scaled_change = score_change * 0.7  # Mild tilt: Reduced impact
        elif score_change <= 10:
            scaled_change = score_change * 1.2  # Moderate tilt: Slightly amplified
        elif score_change <= 15:
            scaled_change = score_change * 1.8  # High tilt: Significantly amplified
        else:
            scaled_change = score_change * 2.5  # Extreme tilt: Greatly amplified
        
        # Additional multiplier based on current tilt level
        if current_score >= 80:
            tilt_multiplier = 1.5  # Critical tilt - escalates quickly
        elif current_score >= 70:
            tilt_multiplier = 1.3  # Highly tilted
        elif current_score >= 60:
            tilt_multiplier = 1.15  # Moderately tilted
        else:
            tilt_multiplier = 1.0  # Normal state
            
        # Apply both adjustments
        final_change = scaled_change * tilt_multiplier
        
        logger.info(f"Tilt increase: raw={score_change}, scaled={scaled_change:.1f}, " +
                  f"with multiplier={final_change:.1f} (current={current_score})")
        
        # Update score with safeguard against exceeding 100
        user_tilt_scores[user_id]["score"] = min(100, current_score + final_change)
        
    # Handle negative score_change (decreasing tilt)
    elif score_change < 0:
        # Apply non-linear scaling for positivity impact
        # More effective when player is highly tilted (helps recovery)
        tilt_reduction = abs(score_change)
        
        if current_score >= 80:
            positivity_multiplier = 1.8  # Critical tilt - positivity has greater impact
        elif current_score >= 70:
            positivity_multiplier = 1.5  # Highly tilted
        elif current_score >= 60:
            positivity_multiplier = 1.2  # Moderately tilted
        else:
            positivity_multiplier = 1.0  # Normal state - standard impact
        
        final_reduction = tilt_reduction * positivity_multiplier
        
        logger.info(f"Tilt reduction: raw={score_change}, with multiplier={final_reduction:.1f} (current={current_score})")
        
        # Update score with safeguard against going below 0
        user_tilt_scores[user_id]["score"] = max(0, current_score - final_reduction)
    
    user_tilt_scores[user_id]["last_updated"] = time.time()
    
    # Store the trigger if provided
    if trigger and score_change != 0:
        if "triggers" not in user_tilt_scores[user_id]:
            user_tilt_scores[user_id]["triggers"] = []
        
        # Prefix positive triggers with a "+" sign
        trigger_text = ("+" if score_change < 0 else "") + trigger[:50]
        
        # Limit to last 10 triggers
        user_tilt_scores[user_id]["triggers"].append(trigger_text)
        if len(user_tilt_scores[user_id]["triggers"]) > 10:
            user_tilt_scores[user_id]["triggers"] = user_tilt_scores[user_id]["triggers"][-10:]

def update_tilt_decay(user_id):
    """Apply time-based decay to tilt scores"""
    if user_id not in user_tilt_scores:
        return
    
    current_time = time.time()
    last_updated = user_tilt_scores[user_id]["last_updated"]
    elapsed_minutes = (current_time - last_updated) / 60
    
    # Calculate decay
    decay = min(elapsed_minutes * TILT_DECAY_RATE, user_tilt_scores[user_id]["score"] - 50)
    
    # Don't go below 50 (neutral)
    if user_tilt_scores[user_id]["score"] > 50:
        user_tilt_scores[user_id]["score"] = max(50, user_tilt_scores[user_id]["score"] - decay)
    
    user_tilt_scores[user_id]["last_updated"] = current_time

def get_tilt_message(score):
    """Get a message describing the tilt level"""
    if score < 30:
        return "Extremely calm and collected. Are they even playing?"
    elif score < 50:
        return "Very chill. Nothing seems to bother this player."
    elif score < 60:
        return "Normal gaming state. Focused but composed."
    elif score < 70:
        return "Slightly annoyed. Starting to get frustrated."
    elif score < 80:
        return "Definitely tilted. Patience wearing thin."
    elif score < 90:
        return "Major tilt detected! They're getting really heated."
    else:
        return "CRITICAL TILT LEVELS! Keyboard/controller in danger!"

def get_tilt_color(score):
    """Get a color based on tilt level"""
    if score < 50:
        return discord.Color.green()
    elif score < 70:
        return discord.Color.gold()
    elif score < 90:
        return discord.Color.orange()
    else:
        return discord.Color.red()

# TOKEN
bot.run(os.getenv("DISCORD_BOT_TOKEN"))