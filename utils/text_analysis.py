import re
from config import TILT_KEYWORDS, POSITIVE_KEYWORDS, logger

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