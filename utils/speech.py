import whisper
import torch
from transformers import pipeline
from config import WHISPER_MODEL_SIZE, SENTIMENT_MODEL, logger

# Initialize models
def load_models():
    """Load and initialize speech-to-text and sentiment analysis models"""
    global whisper_model, tilt_pipeline
    
    # Load Whisper model
    logger.info(f"Loading Whisper {WHISPER_MODEL_SIZE} model...")
    whisper_model = whisper.load_model(WHISPER_MODEL_SIZE)
    logger.info(f"Whisper model loaded successfully")
    
    # Load sentiment analysis model
    logger.info("Loading sentiment analysis model for tilt detection...")
    try:
        tilt_pipeline = pipeline(
            "sentiment-analysis",
            model=SENTIMENT_MODEL,
            device=-1  # Use CPU
        )
        logger.info("Sentiment analysis model loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load sentiment model: {e}")
        logger.info("Falling back to keyword-based tilt analysis")
        tilt_pipeline = None
        
    return whisper_model, tilt_pipeline

# Load models
whisper_model, tilt_pipeline = load_models()

def analyze_text_for_tilt(text):
    """Analyze text for signs of tilt or positive statements"""
    from utils.text_analysis import fallback_analyze_text_for_tilt
    
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