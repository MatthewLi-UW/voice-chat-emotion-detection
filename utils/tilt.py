import time
import discord
from config import user_tilt_scores, TILT_DECAY_RATE, logger

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