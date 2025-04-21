# Imports for easy access to utility functions
from utils.tilt import update_tilt_score, update_tilt_decay, get_tilt_message, get_tilt_color
from utils.text_analysis import fallback_analyze_text_for_tilt, correct_gaming_terms, correct_usernames
from utils.speech import analyze_text_for_tilt, whisper_model, tilt_pipeline
from utils.audio_processing import preprocess_audio, analyze_audio_characteristics