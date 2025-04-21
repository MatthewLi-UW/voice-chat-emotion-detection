import asyncio
import tempfile
import os
import threading
import queue
import discord
from config import logger, processing_queues, voice_clients
from utils.tilt import update_tilt_score
from utils.speech import whisper_model, analyze_text_for_tilt
from utils.text_analysis import correct_gaming_terms, correct_usernames
from utils.audio_processing import preprocess_audio

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
    ctx.bot.loop.create_task(process_recordings_regularly(ctx, voice_client))

async def process_recordings_regularly(ctx, voice_client):
    """Regularly stop and restart recording to process chunks"""
    while ctx.voice_client and ctx.voice_client.is_connected():
        await asyncio.sleep(10)  # Process every 10 seconds
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
        from bot.client import bot
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
                
                if tilt_score_increase != 0:
                    # Apply sensitivity multiplier if set
                    from bot.client import bot
                    if hasattr(bot, 'sensitivity_multiplier'):
                        tilt_score_increase *= bot.sensitivity_multiplier
                    
                    update_tilt_score(user_id, tilt_score_increase, trigger=corrected_text)
                    if tilt_score_increase > 0:
                        logger.info(f"Voice caused tilt increase of {tilt_score_increase} for user {user_id}")
                    else:
                        logger.info(f"Voice caused tilt decrease of {abs(tilt_score_increase)} for user {user_id}")
            
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