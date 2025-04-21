import os
from pydub import AudioSegment
from config import logger

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
        
        # We could analyze other characteristics here like pitch, speaking rate, etc.
        # For simplicity, we're mainly using volume
        
        return volume_score
    
    except Exception as e:
        logger.error(f"Error analyzing audio: {e}")
        return 0